import os
import json
import ssl
from typing import Any, Dict, Optional, Tuple
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    import certifi  # type: ignore
except Exception:  # pragma: no cover
    certifi = None

load_dotenv()  # reads .env from project root

SIGNATURE_SQL = """
SELECT
  zone_id,
  zone_name,
  strata_id,
  strata_code,
  land_cover_id,
  land_cover_name,
  pop_density,
  elev_min,
  elev_max,
  runoff,
  discharge_yr,
  -- geometry handling: return a GeoJSON string (good for Leaflet)
  ST_AsGeoJSON(geom, 6) AS geom_geojson
FROM public.v_basin08_basic
WHERE ST_Covers(
  geom,
  ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)
)
ORDER BY area_km2 ASC
LIMIT 1;
"""

# -----------------------
# Elevation provider (external, swappable)
# Pattern B: try OpenTopoData (mapzen) first, then Open-Meteo elevation API.
# -----------------------

# Very small in-process cache (per worker) to avoid repeated lookups.
# Key is rounded (lat, lon) to 5 decimals (~1m-2m at equator in lat; good enough for caching).
_ELEV_CACHE: Dict[Tuple[float, float], Dict[str, Any]] = {}
_ELEV_CACHE_MAX = 512


def _cache_get(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    key = (round(float(lat), 5), round(float(lon), 5))
    return _ELEV_CACHE.get(key)


def _cache_set(lat: float, lon: float, val: Dict[str, Any]) -> None:
    key = (round(float(lat), 5), round(float(lon), 5))
    if key in _ELEV_CACHE:
        _ELEV_CACHE[key] = val
        return
    if len(_ELEV_CACHE) >= _ELEV_CACHE_MAX:
        # Drop an arbitrary item (good enough for a pilot)
        _ELEV_CACHE.pop(next(iter(_ELEV_CACHE)))
    _ELEV_CACHE[key] = val


def _http_get_json(url: str, timeout_s: float = 4.0) -> Dict[str, Any]:
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "edop-pilot/0.1",
        },
        method="GET",
    )

    # Some environments (notably minimal Linux images) lack CA certificates,
    # causing CERTIFICATE_VERIFY_FAILED. Prefer certifi's bundle when available.
    # For local/dev emergency only, set EDOP_SSL_NO_VERIFY=1 to bypass verification.
    no_verify = os.getenv("EDOP_SSL_NO_VERIFY", "0") in ("1", "true", "True", "yes", "YES")

    if no_verify:
        ctx = ssl._create_unverified_context()
    else:
        if certifi is not None:
            ctx = ssl.create_default_context(cafile=certifi.where())
        else:
            ctx = ssl.create_default_context()

    with urlopen(req, timeout=timeout_s, context=ctx) as resp:
        data = resp.read().decode("utf-8")
        return json.loads(data)


def _elev_opentopodata_mapzen(lat: float, lon: float) -> Dict[str, Any]:
    # OpenTopoData uses locations=lat,lon
    qs = urlencode({"locations": f"{lat},{lon}"})
    url = f"https://api.opentopodata.org/v1/mapzen?{qs}"
    payload = _http_get_json(url)

    if payload.get("status") != "OK":
        raise RuntimeError(payload.get("error") or f"OpenTopoData status={payload.get('status')}")

    results = payload.get("results") or []
    if not results:
        raise RuntimeError("OpenTopoData returned no results")

    elev = results[0].get("elevation")
    if elev is None:
        raise RuntimeError("OpenTopoData result missing elevation")

    return {
        "elev_point": float(elev),
        "elev_source": "opentopodata",
        "elev_dataset": "mapzen",
        "elev_resolution_m": 30,
    }


def _elev_open_meteo(lat: float, lon: float) -> Dict[str, Any]:
    # Open-Meteo Elevation API uses latitude=..&longitude=..
    qs = urlencode({"latitude": str(lat), "longitude": str(lon)})
    url = f"https://api.open-meteo.com/v1/elevation?{qs}"
    payload = _http_get_json(url)

    elev = None
    # API commonly returns: {"elevation": [..], "latitude": [..], "longitude": [..]}
    if isinstance(payload.get("elevation"), list) and payload["elevation"]:
        elev = payload["elevation"][0]
    elif payload.get("elevation") is not None:
        elev = payload.get("elevation")

    if elev is None:
        raise RuntimeError("Open-Meteo elevation missing in response")

    return {
        "elev_point": float(elev),
        "elev_source": "open-meteo",
        "elev_dataset": "copernicus-dem-glo-90-2021",
        "elev_resolution_m": 90,
    }


def get_elevation_point(lat: float, lon: float) -> Dict[str, Any]:
    """Return elevation metadata dict.

    Always returns a dict with keys:
      - elev_point (float) when available else None
      - elev_source, elev_dataset, elev_resolution_m when available
      - elev_error when both providers fail

    Pattern B fallback: OpenTopoData(mapzen) -> Open-Meteo elevation.
    """
    cached = _cache_get(lat, lon)
    if cached is not None:
        return cached

    last_err: Optional[str] = None

    # Provider 1: OpenTopoData /mapzen (~30m)
    try:
        val = _elev_opentopodata_mapzen(lat, lon)
        _cache_set(lat, lon, val)
        return val
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as e:
        last_err = f"opentopodata: {e}"

    # Provider 2: Open-Meteo elevation (Copernicus GLO-90)
    try:
        val = _elev_open_meteo(lat, lon)
        _cache_set(lat, lon, val)
        return val
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as e:
        last_err = (last_err + "; " if last_err else "") + f"open-meteo: {e}"

    val = {
        "elev_point": None,
        "elev_error": last_err or "elevation lookup failed",
    }
    _cache_set(lat, lon, val)
    return val


def get_signature(
    lat: float,
    lon: float,
) -> Dict[str, Any] | None:
    """Return a single basin signature dict for (lat, lon), or None if no basin covers point.

    Connection parameters are read from environment variables (typically via a .env file):
      DB_NAME, DB_USER, DB_HOST, DB_PORT, and optionally DB_PASSWORD.

    Notes:
    - Uses ST_Covers exactly as your SQL does.
    - Orders by smallest area_km2 to pick the smallest containing basin when multiple match.
    - Returns geom as a GeoJSON string in 'geom_geojson' (Leaflet-friendly).
    """

    conn_kwargs = dict(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        password=os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD") or None,
    )

    # Drop None values so psycopg/libpq can fall back to defaults / .pgpass when appropriate
    conn_kwargs = {k: v for k, v in conn_kwargs.items() if v not in (None, "")}

    with psycopg.connect(**conn_kwargs, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(SIGNATURE_SQL, {"lat": lat, "lon": lon})
            row = cur.fetchone()
            if not row:
                return None
            sig = dict(row)

            # Add point elevation via external providers (fallback chain)
            try:
                elev = get_elevation_point(lat=lat, lon=lon)
            except Exception as e:
                elev = {"elev_point": None, "elev_error": str(e)}
            sig.update(elev)

            # Derived relief metrics (requires elev_point + basin elev_min/elev_max)
            try:
                elev_point = sig.get("elev_point")
                elev_min = sig.get("elev_min")
                elev_max = sig.get("elev_max")

                if elev_point is None or elev_min is None or elev_max is None:
                    sig["relief_range_m"] = None
                    sig["relief_position"] = None
                else:
                    elev_point_f = float(elev_point)
                    elev_min_f = float(elev_min)
                    elev_max_f = float(elev_max)
                    relief_range = elev_max_f - elev_min_f

                    sig["relief_range_m"] = relief_range if relief_range > 0 else None

                    if relief_range > 0:
                        pos = (elev_point_f - elev_min_f) / relief_range
                        # Clamp to [0, 1] to absorb minor inconsistencies across datasets/resolution
                        if pos < 0:
                            pos = 0.0
                        elif pos > 1:
                            pos = 1.0
                        sig["relief_position"] = pos
                    else:
                        sig["relief_position"] = None
            except Exception:
                sig["relief_range_m"] = None
                sig["relief_position"] = None

            return sig


def main() -> None:
    # Your test coordinates (note: lon, lat order matches your SQL)
    lat = 16.76618535
    lon = -3.00777252

    sig = get_signature(lat=lat, lon=lon)

    if sig is None:
        print("No basin found covering that point.")
        return

    print(json.dumps(sig, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
