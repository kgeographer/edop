import os
import json
from typing import Any, Dict
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
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
            return dict(row) if row else None


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
