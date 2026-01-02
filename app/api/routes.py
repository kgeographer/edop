from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional, Tuple
import json
import urllib.parse
import urllib.request
import ssl
import certifi

from app.db.signature import get_signature
from app.settings import settings

from pathlib import Path
import re

router = APIRouter(prefix="/api", tags=["api"])


# -----------------------
# Utility helpers
# -----------------------

def _http_get_json(url: str, timeout_sec: int = 20) -> Dict[str, Any]:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _whg_suggest_first(prefix: str) -> Optional[Dict[str, Any]]:
    """Call WHG suggest endpoint and return the top-ranked result, if any."""
    if not settings.WHG_API_TOKEN:
        raise HTTPException(status_code=500, detail="WHG_API_TOKEN not configured on server")

    params = {
        "prefix": prefix,
        "limit": 3,
        "cursor": 0,
        "exact": "false",
    }
    # WHG may require authentication for suggest; include token when configured.
    if settings.WHG_API_TOKEN:
        params["token"] = settings.WHG_API_TOKEN

    url = "https://whgazetteer.org/suggest/entity?" + urllib.parse.urlencode(params)
    data = _http_get_json(url)
    results = data.get("result") or []
    return results[0] if results else None


def _whg_entity(place_id: str) -> Dict[str, Any]:
    """Fetch WHG entity detail for a place id (e.g. 'place:5424806')."""
    if not settings.WHG_API_TOKEN:
        raise HTTPException(status_code=500, detail="WHG_API_TOKEN not configured on server")

    encoded_id = urllib.parse.quote(place_id, safe="")
    token = urllib.parse.quote(settings.WHG_API_TOKEN)
    url = f"https://whgazetteer.org/entity/{encoded_id}/api?token={token}"
    return _http_get_json(url)


def _extract_lonlat(entity: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Extract (lon, lat) from a WHG entity response."""
    geoms = entity.get("geoms") or []
    if not geoms:
        return None

    g0 = geoms[0] or {}

    # Preferred: GeoJSON coordinates
    gj = g0.get("geojson")
    if isinstance(gj, dict):
        coords = gj.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            return float(coords[0]), float(coords[1])

    # Fallbacks
    coords = g0.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        return float(coords[0]), float(coords[1])

    centroid = g0.get("centroid")
    if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
        return float(centroid[0]), float(centroid[1])

    return None


# -----------------------
# World Heritage seed helpers
# -----------------------

_WH_SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "world_heritage_seed.json"


def _parse_wkt_point(wkt: str) -> Optional[Tuple[float, float]]:
    """Parse WKT like 'POINT (lon lat)' or 'POINT(lon lat)' into (lon, lat)."""
    if not wkt:
        return None
    m = re.match(r"^\s*POINT\s*\(\s*([-0-9.]+)\s+([-0-9.]+)\s*\)\s*$", wkt)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def _load_wh_seed() -> list[Dict[str, Any]]:
    """Load and normalize the WH seed JSON into a list of dicts with GeoJSON Point."""
    if not _WH_SEED_PATH.exists():
        raise FileNotFoundError(f"World Heritage seed file not found at {_WH_SEED_PATH}")

    raw = json.loads(_WH_SEED_PATH.read_text(encoding="utf-8"))
    out: list[Dict[str, Any]] = []

    if not isinstance(raw, list):
        raise ValueError("World Heritage seed file must be a JSON array")

    for row in raw:
        if not isinstance(row, dict):
            continue
        wkt = row.get("geom")
        lonlat = _parse_wkt_point(wkt) if isinstance(wkt, str) else None
        if not lonlat:
            continue
        lon, lat = lonlat
        out.append(
            {
                "id_no": row.get("id_no"),
                "name_en": row.get("name_en"),
                "states_name_en": row.get("states_name_en"),
                "short_description_en": row.get("short_description_en"),
                "location": {"type": "Point", "coordinates": [lon, lat]},
            }
        )

    return out


# -----------------------
# API endpoints
# -----------------------

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/signature")
def signature(lat: float, lon: float):
    sig = get_signature(lat=lat, lon=lon)
    if sig is None:
        raise HTTPException(status_code=404, detail="No basin covers this point")
    return sig


@router.get("/resolve")
def resolve(name: str):
    """Resolve a place name using WHG suggest + entity detail.

    Returns a ResolvedPlace-style payload with GeoJSON Point coordinates
    when available.
    """
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing required query parameter: name")

    try:
        first = _whg_suggest_first(name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"WHG suggest failed: {e}")

    if not first:
        return {
            "label": name,
            "source": "whg",
            "meta": {"status": "not_found"},
        }

    place_id = first.get("id")
    if not place_id:
        return {
            "label": first.get("name") or name,
            "source": "whg",
            "meta": {"status": "no_id", "suggest": first},
        }

    try:
        entity = _whg_entity(str(place_id))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"WHG entity failed: {e}")

    lonlat = _extract_lonlat(entity)
    if not lonlat:
        return {
            "label": entity.get("title") or first.get("name") or name,
            "source": "whg",
            "meta": {
                "status": "no_geometry",
                "whg_id": place_id,
                "score": first.get("score"),
                "description": first.get("description"),
            },
        }

    lon, lat = lonlat
    return {
        "label": entity.get("title") or first.get("name") or name,
        "source": "whg",
        "location": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "meta": {
            "status": "ok",
            "whg_id": place_id,
            "score": first.get("score"),
            "description": first.get("description"),
            "ccodes": entity.get("ccodes"),
            "dataset": entity.get("dataset"),
            "dataset_id": entity.get("dataset_id"),
        },
    }

@router.get("/wh-sites")
def wh_sites():
    """Return the small World Heritage seed set used by the pilot UI."""
    try:
        sites = _load_wh_seed()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"count": len(sites), "sites": sites}