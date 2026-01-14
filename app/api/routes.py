from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List, Optional, Tuple
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
# WHG API and utility helpers
# -----------------------

def _http_get_json(url: str, timeout_sec: int = 20) -> Dict[str, Any]:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "EDOP/1.0"
    })
    with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str] = None, timeout_sec: int = 20) -> Dict[str, Any]:
    """POST JSON to URL and return parsed response."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    data = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "EDOP/1.0"
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
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


def _whg_suggest(prefix: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Call WHG suggest endpoint and return up to `limit` results."""
    if not settings.WHG_API_TOKEN:
        raise HTTPException(status_code=500, detail="WHG_API_TOKEN not configured on server")

    params = {
        "prefix": prefix,
        "limit": limit,
        "cursor": 0,
        "exact": "true",
        "token": settings.WHG_API_TOKEN,
    }

    url = "https://whgazetteer.org/suggest/entity?" + urllib.parse.urlencode(params)
    data = _http_get_json(url)
    results = data.get("result") or []
    # Filter to places only (IDs prefixed with "place:")
    return [r for r in results if r.get("id", "").startswith("place:")]


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


def _whg_reconcile_query(query: str, countries: List[str] = None, bounds: Dict = None, size: int = 10) -> Dict[str, Any]:
    """
    Call WHG /reconcile endpoint to search for places.
    Returns candidates with id, name, score, match, alt_names, description.
    """
    if not settings.WHG_API_TOKEN:
        raise HTTPException(status_code=500, detail="WHG_API_TOKEN not configured on server")

    # Build query payload
    q_params = {
        "query": query,
        "mode": "exact",
        "fclasses": ["P"],  # Places (settlements)
        "type": "https://whgazetteer.org/static/whg_schema.jsonld#Place",
        "size": size
    }

    if countries:
        q_params["countries"] = countries

    if bounds:
        q_params["bounds"] = bounds

    payload = {
        "queries": {
            "q1": q_params
        }
    }

    headers = {
        "Authorization": f"Bearer {settings.WHG_API_TOKEN}"
    }

    url = "https://whgazetteer.org/reconcile"
    data = _http_post_json(url, payload, headers=headers)

    # Extract results from q1
    q1_result = data.get("q1", {})
    return q1_result.get("result", [])


def _whg_reconcile_extend(place_ids: List[str]) -> Dict[str, Dict]:
    """
    Call WHG /reconcile extend to get geometry and details for place IDs.
    Returns dict keyed by place_id with geometry_wkt, countries, types, names.
    """
    if not settings.WHG_API_TOKEN:
        raise HTTPException(status_code=500, detail="WHG_API_TOKEN not configured on server")

    if not place_ids:
        return {}

    payload = {
        "extend": {
            "ids": place_ids,
            "type": "https://whgazetteer.org/static/whg_schema.jsonld#Place",
            "properties": [
                {"id": "whg:geometry_wkt"},
                {"id": "whg:countries_objects"},
                {"id": "whg:types_objects"},
                {"id": "whg:names_summary"}
            ]
        }
    }

    headers = {
        "Authorization": f"Bearer {settings.WHG_API_TOKEN}"
    }

    url = "https://whgazetteer.org/reconcile"
    data = _http_post_json(url, payload, headers=headers)

    return data.get("rows", {})


def _parse_wkt_point_coords(wkt: str) -> Optional[Tuple[float, float]]:
    """Parse WKT POINT to (lon, lat) tuple."""
    if not wkt:
        return None
    m = re.match(r"^\s*POINT\s*\(\s*([-0-9.]+)\s+([-0-9.]+)\s*\)\s*$", wkt, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def _merge_reconcile_results(candidates: List[Dict], extended: Dict[str, Dict]) -> List[Dict]:
    """
    Merge reconcile query results with extend data.
    Returns list of places with all fields combined.
    """
    results = []

    for c in candidates:
        place_id = c.get("id")
        ext = extended.get(place_id, {})

        # Parse geometry
        geom_wkt = None
        lon, lat = None, None
        geom_list = ext.get("whg:geometry_wkt", [])
        if geom_list and isinstance(geom_list, list) and len(geom_list) > 0:
            geom_wkt = geom_list[0].get("str")
            coords = _parse_wkt_point_coords(geom_wkt)
            if coords:
                lon, lat = coords

        # Parse countries
        countries = []
        countries_list = ext.get("whg:countries_objects", [])
        if countries_list and isinstance(countries_list, list) and len(countries_list) > 0:
            try:
                countries_json = countries_list[0].get("str", "[]")
                countries = json.loads(countries_json)
            except:
                pass

        # Parse types
        types = []
        types_list = ext.get("whg:types_objects", [])
        if types_list and isinstance(types_list, list) and len(types_list) > 0:
            try:
                types_json = types_list[0].get("str", "[]")
                types = json.loads(types_json)
            except:
                pass

        # Parse names
        names = []
        names_list = ext.get("whg:names_summary", [])
        if names_list and isinstance(names_list, list):
            names = [n.get("str") for n in names_list if n.get("str")]

        # Build merged result
        result = {
            "id": place_id,
            "name": c.get("name"),
            "score": c.get("score"),
            "match": c.get("match", False),
            "alt_names": c.get("alt_names", []),
            "description": c.get("description"),
            "lon": lon,
            "lat": lat,
            "countries": countries,
            "types": types,
            "names_summary": names
        }
        results.append(result)

    return results


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


def _get_cluster_labels() -> Dict[int, str]:
    """Fetch cluster labels for WH sites from database."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id_no, c.cluster_label
                FROM edop_clusters c
                JOIN edop_wh_sites s ON s.site_id = c.site_id
            """)
            return {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        return {}
    finally:
        if 'conn' in locals():
            conn.close()


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


@router.get("/whg-suggest")
def whg_suggest(q: str, limit: int = 5):
    """Return up to `limit` WHG suggest candidates for autocomplete.

    Each result includes: id, name, score, alt_names, description (country).
    """
    q = (q or "").strip()
    if not q:
        return {"results": []}

    if limit < 1:
        limit = 1
    elif limit > 20:
        limit = 20

    try:
        raw = _whg_suggest(q, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"WHG suggest failed: {e}")

    # Reshape for frontend: flatten to essentials
    results = []
    for r in raw:
        results.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "score": r.get("score"),
            "description": r.get("description"),  # e.g. "Country: ML"
            "alt_names": r.get("alt_names") or [],
        })

    return {"results": results}


@router.get("/whg-place")
def whg_place(id: str):
    """Fetch WHG entity by ID and return coordinates + metadata.

    Use this after user selects from whg-suggest dropdown.
    """
    id = (id or "").strip()
    if not id:
        raise HTTPException(status_code=400, detail="Missing required query parameter: id")

    try:
        entity = _whg_entity(id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"WHG entity failed: {e}")

    lonlat = _extract_lonlat(entity)
    if not lonlat:
        return {
            "id": id,
            "label": entity.get("title"),
            "source": "whg",
            "meta": {
                "status": "no_geometry",
                "ccodes": entity.get("ccodes"),
                "fclasses": entity.get("fclasses"),
            },
        }

    lon, lat = lonlat
    return {
        "id": id,
        "label": entity.get("title"),
        "source": "whg",
        "location": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "meta": {
            "status": "ok",
            "ccodes": entity.get("ccodes"),
            "fclasses": entity.get("fclasses"),
            "dataset": entity.get("dataset"),
        },
    }


@router.get("/whg-reconcile")
def whg_reconcile(q: str, countries: str = None, size: int = 10):
    """
    Search WHG using reconcile API with optional country filter.

    Returns up to `size` candidates with geometry, countries, types, and names.

    Args:
        q: Search query (place name)
        countries: Comma-separated country codes (e.g., "US" or "US,CA")
        size: Max number of results (default 10, max 20)
    """
    q = (q or "").strip()
    if not q:
        return {"results": []}

    if len(q) < 3:
        return {"results": []}

    if size < 1:
        size = 1
    elif size > 20:
        size = 20

    # Parse countries parameter
    country_list = None
    if countries:
        country_list = [c.strip().upper() for c in countries.split(",") if c.strip()]

    try:
        # Step 1: Query for candidates
        candidates = _whg_reconcile_query(q, countries=country_list, size=size)

        if not candidates:
            return {"results": []}

        # Step 2: Get geometry for all candidates
        place_ids = [c.get("id") for c in candidates if c.get("id")]
        extended = _whg_reconcile_extend(place_ids)

        # Step 3: Merge results
        results = _merge_reconcile_results(candidates, extended)

        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"WHG reconcile failed: {e}")


@router.get("/wh-sites")
def wh_sites():
    """Return the small World Heritage seed set used by the pilot UI."""
    try:
        sites = _load_wh_seed()
        cluster_labels = _get_cluster_labels()

        # Add cluster_label to each site
        for site in sites:
            id_no = site.get("id_no")
            site["cluster_label"] = cluster_labels.get(id_no)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"count": len(sites), "sites": sites}


@router.get("/similar")
def similar(id_no: int, limit: int = 5):
    """Return most similar WH sites to the given site by id_no."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    b.id_no,
                    b.name_en,
                    b.lon,
                    b.lat,
                    ROUND(sim.distance::numeric, 2) as distance,
                    c.cluster_label
                FROM edop_similarity sim
                JOIN edop_wh_sites a ON a.site_id = sim.site_a
                JOIN edop_wh_sites b ON b.site_id = sim.site_b
                LEFT JOIN edop_clusters c ON c.site_id = b.site_id
                WHERE a.id_no = %s
                ORDER BY sim.distance ASC
                LIMIT %s
            """, (id_no, limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id_no": row[0],
                    "name_en": row[1],
                    "lon": float(row[2]),
                    "lat": float(row[3]),
                    "distance": float(row[4]),
                    "cluster_label": row[5]
                })

            return {"source_id_no": id_no, "similar": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/similar-text")
def similar_text(id_no: int, limit: int = 5):
    """Return most similar WH sites by text/semantic similarity."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    b.id_no,
                    b.name_en,
                    b.lon,
                    b.lat,
                    ROUND(sim.similarity::numeric, 3) as similarity,
                    c.cluster_label
                FROM edop_text_similarity sim
                JOIN edop_wh_sites a ON a.site_id = sim.site_a
                JOIN edop_wh_sites b ON b.site_id = sim.site_b
                LEFT JOIN edop_text_clusters c ON c.site_id = b.site_id
                WHERE a.id_no = %s
                ORDER BY sim.similarity DESC
                LIMIT %s
            """, (id_no, limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id_no": row[0],
                    "name_en": row[1],
                    "lon": float(row[2]),
                    "lat": float(row[3]),
                    "similarity": float(row[4]),
                    "cluster_label": row[5]
                })

            return {"source_id_no": id_no, "similar": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


# -----------------------
# WH Cities (258) endpoints
# -----------------------

@router.get("/whc-cities")
def whc_cities():
    """Return World Heritage Cities with coordinates and cluster info (excludes 4 without basin data)."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.city,
                    c.country,
                    c.region,
                    ST_X(c.geom) as lon,
                    ST_Y(c.geom) as lat,
                    ec.cluster_id as env_cluster,
                    ec.cluster_label as env_cluster_label
                FROM gaz.wh_cities c
                LEFT JOIN whc_clusters ec ON ec.city_id = c.id
                WHERE c.geom IS NOT NULL
                  AND c.basin_id IS NOT NULL
                ORDER BY c.region, c.country, c.city
            """)

            cities = []
            for row in cur.fetchall():
                cities.append({
                    "id": row[0],
                    "city": row[1],
                    "country": row[2],
                    "region": row[3],
                    "location": {
                        "type": "Point",
                        "coordinates": [float(row[4]), float(row[5])]
                    } if row[4] and row[5] else None,
                    "env_cluster": row[6],
                    "env_cluster_label": row[7]
                })

            return {"count": len(cities), "cities": cities}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/whc-similar")
def whc_similar(city_id: int, limit: int = 5):
    """Return most similar WH cities by environmental signature."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            # whc_similarity stores upper triangle (city_a < city_b)
            # Need to query both directions
            cur.execute("""
                WITH similarities AS (
                    SELECT city_b as other_id, distance, similarity
                    FROM whc_similarity
                    WHERE city_a = %s
                    UNION ALL
                    SELECT city_a as other_id, distance, similarity
                    FROM whc_similarity
                    WHERE city_b = %s
                )
                SELECT
                    c.id,
                    c.city,
                    c.country,
                    c.region,
                    ST_X(c.geom) as lon,
                    ST_Y(c.geom) as lat,
                    ROUND(s.distance::numeric, 2) as distance,
                    ec.cluster_id as env_cluster,
                    ec.cluster_label as env_cluster_label
                FROM similarities s
                JOIN gaz.wh_cities c ON c.id = s.other_id
                LEFT JOIN whc_clusters ec ON ec.city_id = c.id
                ORDER BY s.distance ASC
                LIMIT %s
            """, (city_id, city_id, limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "city": row[1],
                    "country": row[2],
                    "region": row[3],
                    "lon": float(row[4]) if row[4] else None,
                    "lat": float(row[5]) if row[5] else None,
                    "distance": float(row[6]),
                    "env_cluster": row[7],
                    "env_cluster_label": row[8]
                })

            return {"source_city_id": city_id, "similar": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/whc-similar-env-by-coord")
def whc_similar_env_by_coord(lon: float, lat: float, limit: int = 5):
    """Return most similar WH cities by environmental signature for any coordinate.

    Uses basin-level PCA vectors (pgvector) to find WH cities in environmentally
    similar basins to the input point.
    """
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            # First, find which basin contains this point
            cur.execute("""
                SELECT id FROM basin08
                WHERE ST_Covers(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                LIMIT 1
            """, (lon, lat))
            row = cur.fetchone()
            if not row:
                return {"error": "No basin found for coordinates", "similar": []}

            source_basin_id = row[0]

            # Check if source basin has PCA vector
            cur.execute("SELECT 1 FROM basin08_pca WHERE basin_id = %s", (source_basin_id,))
            if not cur.fetchone():
                return {"error": "Basin has no PCA vector", "similar": []}

            # Get distance distribution stats (source basin to all WH city basins)
            cur.execute("""
                WITH whc_basin_distances AS (
                    SELECT p1.pca <-> p2.pca AS distance
                    FROM basin08_pca p1, basin08_pca p2
                    JOIN gaz.wh_cities c ON c.basin_id = p2.basin_id
                    WHERE p1.basin_id = %s
                      AND p2.basin_id != %s
                      AND c.basin_id IS NOT NULL
                )
                SELECT
                    MIN(distance),
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY distance),
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY distance),
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY distance),
                    MAX(distance),
                    COUNT(*)
                FROM whc_basin_distances
            """, (source_basin_id, source_basin_id))
            stats_row = cur.fetchone()
            dist_stats = {
                "min": round(float(stats_row[0]), 4) if stats_row[0] else None,
                "p25": round(float(stats_row[1]), 4) if stats_row[1] else None,
                "median": round(float(stats_row[2]), 4) if stats_row[2] else None,
                "p75": round(float(stats_row[3]), 4) if stats_row[3] else None,
                "max": round(float(stats_row[4]), 4) if stats_row[4] else None,
                "count": int(stats_row[5]) if stats_row[5] else 0
            }

            # Find WH cities in the most similar basins by PCA vector distance
            # Also compute percentile rank for each result
            cur.execute("""
                WITH whc_basin_distances AS (
                    SELECT
                        c.id as city_id,
                        p1.pca <-> p2.pca AS distance
                    FROM basin08_pca p1, basin08_pca p2
                    JOIN gaz.wh_cities c ON c.basin_id = p2.basin_id
                    WHERE p1.basin_id = %s
                      AND p2.basin_id != %s
                      AND c.basin_id IS NOT NULL
                ),
                ranked AS (
                    SELECT
                        city_id,
                        distance,
                        PERCENT_RANK() OVER (ORDER BY distance) as pct_rank
                    FROM whc_basin_distances
                )
                SELECT
                    c.id,
                    c.city,
                    c.country,
                    c.region,
                    ST_X(c.geom) as lon,
                    ST_Y(c.geom) as lat,
                    ROUND(r.distance::numeric, 4) as distance,
                    ROUND((r.pct_rank * 100)::numeric, 1) as percentile,
                    ec.cluster_id as env_cluster,
                    ec.cluster_label as env_cluster_label
                FROM ranked r
                JOIN gaz.wh_cities c ON c.id = r.city_id
                LEFT JOIN whc_clusters ec ON ec.city_id = c.id
                ORDER BY r.distance ASC
                LIMIT %s
            """, (source_basin_id, source_basin_id, limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "city": row[1],
                    "country": row[2],
                    "region": row[3],
                    "location": {
                        "type": "Point",
                        "coordinates": [float(row[4]), float(row[5])]
                    } if row[4] and row[5] else None,
                    "distance": float(row[6]) if row[6] is not None else None,
                    "percentile": float(row[7]) if row[7] is not None else None,
                    "env_cluster": row[8],
                    "env_cluster_label": row[9]
                })

            return {
                "source_basin_id": source_basin_id,
                "count": len(results),
                "dist_stats": dist_stats,
                "similar": results
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/whc-similar-text")
def whc_similar_text(city_id: int, band: str = "composite", limit: int = 5):
    """Return most similar WH cities by text/semantic similarity."""
    import psycopg
    import os

    valid_bands = ['history', 'environment', 'culture', 'modern', 'composite']
    if band not in valid_bands:
        raise HTTPException(status_code=400, detail=f"Invalid band. Must be one of: {valid_bands}")

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.city,
                    c.country,
                    c.region,
                    ST_X(c.geom) as lon,
                    ST_Y(c.geom) as lat,
                    ROUND(s.similarity::numeric, 3) as similarity,
                    tc.cluster_id as text_cluster
                FROM whc_band_similarity s
                JOIN gaz.wh_cities c ON c.id = s.city_b
                LEFT JOIN whc_band_clusters tc ON tc.city_id = c.id AND tc.band = %s
                WHERE s.city_a = %s AND s.band = %s
                ORDER BY s.rank ASC
                LIMIT %s
            """, (band, city_id, band, limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "city": row[1],
                    "country": row[2],
                    "region": row[3],
                    "lon": float(row[4]) if row[4] else None,
                    "lat": float(row[5]) if row[5] else None,
                    "similarity": float(row[6]),
                    "text_cluster": row[7]
                })

            return {"source_city_id": city_id, "band": band, "similar": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/whc-summaries")
def whc_summaries(city_id: int):
    """Return band summaries for a WH city."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            # Get city name
            cur.execute("SELECT city, country FROM gaz.wh_cities WHERE id = %s", (city_id,))
            city_row = cur.fetchone()
            if not city_row:
                raise HTTPException(status_code=404, detail="City not found")

            # Get summaries in desired order
            cur.execute("""
                SELECT band, summary
                FROM whc_band_summaries
                WHERE city_id = %s AND status = 'ok'
                ORDER BY CASE band
                    WHEN 'environment' THEN 1
                    WHEN 'history' THEN 2
                    WHEN 'culture' THEN 3
                    WHEN 'modern' THEN 4
                END
            """, (city_id,))

            summaries = []
            for row in cur.fetchall():
                summaries.append({
                    "band": row[0],
                    "summary": row[1]
                })

            return {
                "city_id": city_id,
                "city": city_row[0],
                "country": city_row[1],
                "summaries": summaries
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


# -----------------------
# Basin Cluster endpoints
# -----------------------

@router.get("/basin-clusters")
def basin_clusters():
    """Return all basin clusters with basin and city counts."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    b.cluster_id,
                    COUNT(DISTINCT b.id) as basin_count,
                    COUNT(DISTINCT c.id) as city_count
                FROM basin08 b
                LEFT JOIN gaz.wh_cities c ON c.basin_id = b.id
                WHERE b.cluster_id IS NOT NULL
                GROUP BY b.cluster_id
                ORDER BY b.cluster_id
            """)

            clusters = []
            for row in cur.fetchall():
                clusters.append({
                    "cluster_id": row[0],
                    "basin_count": row[1],
                    "city_count": row[2]
                })

            return {"clusters": clusters}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/basin-clusters/{cluster_id}/cities")
def basin_cluster_cities(cluster_id: int):
    """Return cities in basins of a given cluster."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.city,
                    c.country,
                    c.region,
                    ST_X(c.geom) as lon,
                    ST_Y(c.geom) as lat
                FROM gaz.wh_cities c
                JOIN basin08 b ON c.basin_id = b.id
                WHERE b.cluster_id = %s
                ORDER BY c.country, c.city
            """, (cluster_id,))

            cities = []
            for row in cur.fetchall():
                cities.append({
                    "id": row[0],
                    "city": row[1],
                    "country": row[2],
                    "region": row[3],
                    "lon": float(row[4]) if row[4] else None,
                    "lat": float(row[5]) if row[5] else None
                })

            return {
                "cluster_id": cluster_id,
                "city_count": len(cities),
                "cities": cities
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


# -----------------------
# Gazetteer endpoints
# -----------------------

@router.get("/gaz-similar")
def gaz_similar(gaz_id: int, limit: int = 10):
    """Find environmentally similar gazetteer places using PCA vector distance."""
    import psycopg
    import os

    if limit < 1:
        limit = 1
    elif limit > 25:
        limit = 25

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            # Get the source place's basin
            cur.execute("""
                SELECT g.id, g.title, g.basin_id
                FROM gaz.edop_gaz g
                WHERE g.id = %s
            """, (gaz_id,))
            source = cur.fetchone()
            if not source:
                return {"error": "Place not found", "similar": []}

            source_id, source_title, source_basin_id = source

            if source_basin_id is None:
                return {"error": "Place has no basin assignment", "similar": []}

            # Check if source basin has PCA vector
            cur.execute("SELECT 1 FROM basin08_pca WHERE basin_id = %s", (source_basin_id,))
            if not cur.fetchone():
                return {"error": "Basin has no PCA vector", "similar": []}

            # Find places in the most similar basins by PCA vector distance
            # We find more similar basins than needed, then pick places from them
            cur.execute("""
                WITH similar_basins AS (
                    SELECT
                        p2.basin_id,
                        p1.pca <-> p2.pca AS distance
                    FROM basin08_pca p1, basin08_pca p2
                    WHERE p1.basin_id = %s
                      AND p2.basin_id != %s
                    ORDER BY p1.pca <-> p2.pca
                    LIMIT 500
                ),
                ranked_places AS (
                    SELECT
                        g.id, g.title, g.source, g.ccodes, g.lon, g.lat,
                        sb.distance,
                        b.cluster_id,
                        ROW_NUMBER() OVER (PARTITION BY g.basin_id ORDER BY random()) as rn
                    FROM gaz.edop_gaz g
                    JOIN similar_basins sb ON sb.basin_id = g.basin_id
                    JOIN basin08 b ON b.id = g.basin_id
                    WHERE g.id != %s
                      AND g.lon IS NOT NULL
                )
                SELECT id, title, source, ccodes, lon, lat,
                       ROUND(distance::numeric, 4) as distance, cluster_id
                FROM ranked_places
                WHERE rn = 1
                ORDER BY distance
                LIMIT %s
            """, (source_basin_id, source_basin_id, gaz_id, limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "source": row[2],
                    "ccodes": row[3],
                    "lon": float(row[4]) if row[4] else None,
                    "lat": float(row[5]) if row[5] else None,
                    "distance": float(row[6]),
                    "cluster_id": row[7]
                })

            return {
                "source_id": gaz_id,
                "source_title": source_title,
                "similar": results
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/gaz-suggest")
def gaz_suggest(q: str, limit: int = 10):
    """Search the edop_gaz gazetteer for autocomplete suggestions."""
    import psycopg
    import os

    q = (q or "").strip()
    if not q or len(q) < 3:
        return {"results": []}

    if limit < 1:
        limit = 1
    elif limit > 25:
        limit = 25

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            # Case-insensitive prefix search on title
            cur.execute("""
                SELECT id, source, source_id, title, ccodes, lon, lat
                FROM gaz.edop_gaz
                WHERE title ILIKE %s
                ORDER BY title
                LIMIT %s
            """, (q + '%', limit))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "source": row[1],
                    "source_id": row[2],
                    "title": row[3],
                    "ccodes": row[4],  # already an array
                    "lon": float(row[5]) if row[5] else None,
                    "lat": float(row[6]) if row[6] else None,
                })

            return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


# -----------------------
# Ecoregion Hierarchy endpoints
# -----------------------

@router.get("/eco/realms")
def eco_realms():
    """List all realms (top level of hierarchy)."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.realm, r.biogeorelm, COUNT(s.subrealmid) as subrealm_count
                FROM gaz."Realm2023" r
                LEFT JOIN gaz."Subrealm2023" s ON s.biogeorelm = r.biogeorelm
                GROUP BY r.realm, r.biogeorelm
                ORDER BY r.realm
            """)
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[1],  # biogeorelm as id for drilling down
                    "name": row[0],  # realm name for display
                    "subrealm_count": row[2]
                })
            return {"count": len(results), "realms": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/eco/subrealms")
def eco_subrealms(realm: str):
    """List subrealms within a realm."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.subrealmid, s.subrealm_n, COUNT(b.bioregions) as bioregion_count
                FROM gaz."Subrealm2023" s
                LEFT JOIN gaz."Bioregions2023" b ON b.subrealm_id = s.subrealmid
                WHERE s.biogeorelm = %s
                GROUP BY s.subrealmid, s.subrealm_n
                ORDER BY s.subrealm_n
            """, (realm,))
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "name": row[1],
                    "bioregion_count": row[2]
                })
            return {"realm": realm, "count": len(results), "subrealms": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/eco/bioregions")
def eco_bioregions(subrealm_id: int):
    """List bioregions within a subrealm."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            # Get subrealm name for context
            cur.execute('SELECT subrealm_n FROM gaz."Subrealm2023" WHERE subrealmid = %s', (subrealm_id,))
            sr = cur.fetchone()
            subrealm_name = sr[0] if sr else None

            cur.execute("""
                SELECT b.bioregions, COUNT(e.eco_id) as ecoregion_count
                FROM gaz."Bioregions2023" b
                LEFT JOIN gaz."Ecoregions2017" e ON e.bioregion = b.bioregions
                WHERE b.subrealm_id = %s
                GROUP BY b.bioregions
                ORDER BY b.bioregions
            """, (subrealm_id,))
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "name": row[0],
                    "ecoregion_count": row[1]
                })
            return {"subrealm_id": subrealm_id, "subrealm_name": subrealm_name, "count": len(results), "bioregions": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/eco/ecoregions")
def eco_ecoregions(bioregion: str):
    """List ecoregions within a bioregion."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.eco_id, e.eco_name, e.biome_name, e.realm
                FROM gaz."Ecoregions2017" e
                WHERE e.bioregion = %s
                ORDER BY e.eco_name
            """, (bioregion,))
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "name": row[1],
                    "biome": row[2],
                    "realm": row[3]
                })
            return {"bioregion": bioregion, "count": len(results), "ecoregions": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/eco/realms/geom")
def eco_realms_geom():
    """Get GeoJSON FeatureCollection of all realm geometries."""
    import psycopg
    import os

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT realm, biogeorelm, ST_AsGeoJSON(geom)::json
                FROM gaz."Realm2023"
                ORDER BY realm
            """)
            rows = cur.fetchall()

        features = []
        for row in rows:
            features.append({
                "type": "Feature",
                "properties": {"name": row[0], "id": row[1]},
                "geometry": row[2]
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/eco/geom")
def eco_geom(level: str, id: str):
    """Get GeoJSON geometry for a hierarchy level item."""
    import psycopg
    import os

    valid_levels = ['realm', 'subrealm', 'bioregion', 'ecoregion']
    if level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"Invalid level. Must be one of: {valid_levels}")

    try:
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5435"),
            dbname=os.environ.get("PGDATABASE", "edop"),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
        )
        with conn.cursor() as cur:
            if level == 'realm':
                cur.execute("""
                    SELECT realm, ST_AsGeoJSON(geom)::json
                    FROM gaz."Realm2023" WHERE biogeorelm = %s
                """, (id,))
            elif level == 'subrealm':
                cur.execute("""
                    SELECT subrealm_n, ST_AsGeoJSON(geom)::json
                    FROM gaz."Subrealm2023" WHERE subrealmid = %s
                """, (int(id),))
            elif level == 'bioregion':
                cur.execute("""
                    SELECT bioregions, ST_AsGeoJSON(geom)::json
                    FROM gaz."Bioregions2023" WHERE bioregions = %s
                """, (id,))
            elif level == 'ecoregion':
                cur.execute("""
                    SELECT eco_name, ST_AsGeoJSON(geom)::json
                    FROM gaz."Ecoregions2017" WHERE eco_id = %s
                """, (int(id),))

            row = cur.fetchone()
            if not row:
                return {"error": "Not found"}

            return {
                "level": level,
                "id": id,
                "name": row[0],
                "geometry": row[1]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()