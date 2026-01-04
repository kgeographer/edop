#!/usr/bin/env python3
"""
Populate EDOP matrix tables for World Heritage sites.

This script:
1. Loads WH sites from app/data/world_heritage_seed.json
2. Queries basin08 for each site's containing basin
3. Populates edop_wh_sites
4. Queries global min/max and populates edop_norm_ranges
5. Computes normalized values and one-hot encodings
6. Populates edop_matrix

Prerequisites:
- Run sql/edop_matrix_schema.sql first to create tables
- Database connection via environment variables (PGHOST, PGPORT, etc.)

Usage:
    python scripts/populate_matrix.py
"""

import json
import os
import re
from pathlib import Path

import psycopg

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to WH sites JSON (relative to project root)
WH_SITES_PATH = Path(__file__).parent.parent / "app" / "data" / "world_heritage_seed.json"

# Numerical fields mapping: (basin08 column, norm_ranges column prefix)
NUMERICAL_FIELDS = [
    # A: Physiographic Bedrock
    ("ele_mt_smn", "elev_min"),
    ("ele_mt_smx", "elev_max"),
    ("slp_dg_sav", "slope_avg"),
    ("slp_dg_uav", "slope_upstream"),
    ("sgr_dk_sav", "stream_gradient"),
    ("kar_pc_sse", "karst"),
    ("kar_pc_use", "karst_upstream"),
    # B: Hydro-Climatic Baselines
    ("dis_m3_pyr", "discharge_yr"),
    ("dis_m3_pmn", "discharge_min"),
    ("dis_m3_pmx", "discharge_max"),
    ("ria_ha_ssu", "river_area"),
    ("ria_ha_usu", "river_area_upstream"),
    ("run_mm_syr", "runoff"),
    ("gwt_cm_sav", "gw_table_depth"),
    ("cly_pc_sav", "pct_clay"),
    ("slt_pc_sav", "pct_silt"),
    ("snd_pc_sav", "pct_sand"),
    # C: Bioclimatic Proxies (note: tmp_dc fields need /10 conversion)
    ("tmp_dc_syr", "temp_yr"),
    ("tmp_dc_smn", "temp_min"),
    ("tmp_dc_smx", "temp_max"),
    ("pre_mm_syr", "precip_yr"),
    ("ari_ix_sav", "aridity"),
    ("wet_pc_sg1", "wet_pct_grp1"),
    ("wet_pc_sg2", "wet_pct_grp2"),
    ("prm_pc_sse", "permafrost_extent"),
    # D: Anthropocene Markers
    ("rev_mc_usu", "reservoir_vol"),
    ("crp_pc_sse", "cropland_extent"),
    ("ppd_pk_sav", "pop_density"),
    ("hft_ix_s09", "human_footprint_09"),
    ("gdp_ud_sav", "gdp_avg"),
    ("hdi_ix_sav", "human_dev_idx"),
]

# Temperature fields that need /10 conversion
TEMP_FIELDS = {"tmp_dc_syr", "tmp_dc_smn", "tmp_dc_smx"}

# Categorical fields mapping: (basin08 column, table prefix, id column in lookup)
CATEGORICAL_FIELDS = [
    ("tec_cl_smj", "tec", "eco_id"),      # Terrestrial ecoregions
    ("fec_cl_smj", "fec", "eco_id"),      # Freshwater ecoregions
    ("cls_cl_smj", "cls", "gens_id"),     # Climate/land-use strata
    ("glc_cl_smj", "glc", "glc_id"),      # Global land cover
    ("clz_cl_smj", "clz", "genz_id"),     # Climate zones
    ("lit_cl_smj", "lit", "glim_id"),     # Lithology
    ("tbi_cl_smj", "tbi", "biome_id"),    # Biomes
    ("fmh_cl_smj", "fmh", "mht_id"),      # Freshwater major habitat
    ("wet_cl_smj", "wet", "glwd_id"),     # Wetland types
]

# PNV percentage fields (pnv_pc_s01 through pnv_pc_s15)
PNV_FIELDS = [f"pnv_pc_s{i:02d}" for i in range(1, 16)]


def get_db_connection():
    """Create database connection from environment variables."""
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def parse_wkt_point(wkt: str) -> tuple[float, float]:
    """Parse WKT POINT string to (lon, lat) tuple."""
    match = re.match(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", wkt)
    if not match:
        raise ValueError(f"Invalid WKT POINT: {wkt}")
    return float(match.group(1)), float(match.group(2))


def load_wh_sites() -> list[dict]:
    """Load World Heritage sites from JSON file."""
    with open(WH_SITES_PATH) as f:
        sites = json.load(f)

    # Parse geometry and extract coordinates
    for site in sites:
        lon, lat = parse_wkt_point(site["geom"])
        site["lon"] = lon
        site["lat"] = lat

    return sites


def get_basin_for_point(cur, lon: float, lat: float) -> dict | None:
    """Query basin08 for the smallest basin containing the given point."""
    # Build column list for numerical fields
    num_cols = ", ".join(f"b.{col}" for col, _ in NUMERICAL_FIELDS)

    # Build column list for categorical fields
    cat_cols = ", ".join(f"b.{col}" for col, _, _ in CATEGORICAL_FIELDS)

    # Build column list for PNV percentage fields
    pnv_cols = ", ".join(f"b.{col}" for col in PNV_FIELDS)

    sql = f"""
        SELECT
            b.id,
            {num_cols},
            {cat_cols},
            {pnv_cols}
        FROM basin08 b
        WHERE ST_Covers(b.geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        ORDER BY ST_Area(b.geom::geography) ASC
        LIMIT 1
    """

    cur.execute(sql, (lon, lat))
    row = cur.fetchone()

    if not row:
        return None

    # Build result dictionary
    result = {"id": row[0]}
    idx = 1

    # Numerical fields
    for _, name in NUMERICAL_FIELDS:
        result[name] = row[idx]
        idx += 1

    # Categorical fields
    for _, prefix, _ in CATEGORICAL_FIELDS:
        result[f"cat_{prefix}"] = row[idx]
        idx += 1

    # PNV fields
    for i in range(15):
        result[f"pnv_{i+1:02d}"] = row[idx]
        idx += 1

    return result


def compute_global_ranges(cur) -> dict:
    """Query global min/max for all numerical fields from basin08."""
    # Build aggregation expressions
    agg_parts = []
    for col, name in NUMERICAL_FIELDS:
        if col in TEMP_FIELDS:
            # Temperature fields need /10 conversion
            agg_parts.append(f"MIN({col}/10.0) AS {name}_min")
            agg_parts.append(f"MAX({col}/10.0) AS {name}_max")
        else:
            agg_parts.append(f"MIN({col}) AS {name}_min")
            agg_parts.append(f"MAX({col}) AS {name}_max")

    sql = f"SELECT {', '.join(agg_parts)} FROM basin08"
    cur.execute(sql)
    row = cur.fetchone()

    # Build result dictionary
    result = {}
    idx = 0
    for _, name in NUMERICAL_FIELDS:
        result[f"{name}_min"] = row[idx]
        result[f"{name}_max"] = row[idx + 1]
        idx += 2

    return result


def get_categorical_ids(cur) -> dict[str, set]:
    """Get all valid IDs for each categorical lookup table."""
    tables = {
        "tec": ("lu_tec", "eco_id"),
        "fec": ("lu_fec", "eco_id"),
        "cls": ("lu_cls", "gens_id"),
        "glc": ("lu_glc", "glc_id"),
        "clz": ("lu_clz", "genz_id"),
        "lit": ("lu_lit", "glim_id"),
        "tbi": ("lu_tbi", "biome_id"),
        "fmh": ("lu_fmh", "mht_id"),
        "wet": ("lu_wet", "glwd_id"),
    }

    result = {}
    for prefix, (table, id_col) in tables.items():
        cur.execute(f"SELECT DISTINCT {id_col} FROM {table}")
        result[prefix] = {row[0] for row in cur.fetchall()}

    return result


def normalize_value(value, min_val, max_val) -> float | None:
    """Normalize a value to 0-1 range."""
    if value is None or min_val is None or max_val is None:
        return None
    # Convert to float to handle Decimal types from database
    value = float(value)
    min_val = float(min_val)
    max_val = float(max_val)
    if max_val == min_val:
        return 0.5  # Avoid division by zero
    return (value - min_val) / (max_val - min_val)


def populate_norm_ranges(cur, ranges: dict):
    """Insert global normalization ranges into edop_norm_ranges."""
    cols = list(ranges.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)

    sql = f"INSERT INTO edop_norm_ranges (id, {col_names}) VALUES (1, {placeholders})"
    cur.execute(sql, [ranges[c] for c in cols])


def populate_wh_sites(cur, sites: list[dict]) -> dict[int, int]:
    """
    Insert WH sites and return mapping of id_no -> site_id.
    Also queries and stores basin_id for each site.
    """
    id_mapping = {}

    for site in sites:
        # Get basin for this site
        basin = get_basin_for_point(cur, site["lon"], site["lat"])
        basin_id = basin["id"] if basin else None

        cur.execute(
            """
            INSERT INTO edop_wh_sites (id_no, name_en, description_en, lon, lat, basin_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING site_id
            """,
            (
                site["id_no"],
                site["name_en"],
                site.get("short_description_en"),
                site["lon"],
                site["lat"],
                basin_id,
            ),
        )
        site_id = cur.fetchone()[0]
        id_mapping[site["id_no"]] = site_id

        # Store basin data for later matrix population
        site["site_id"] = site_id
        site["basin"] = basin

    return id_mapping


def build_matrix_row(site: dict, ranges: dict, cat_ids: dict) -> dict:
    """Build a single matrix row for a site."""
    basin = site.get("basin")
    if not basin:
        # No basin found - return row with just site_id
        return {"site_id": site["site_id"]}

    row = {"site_id": site["site_id"]}

    # Normalized numerical fields
    for _, name in NUMERICAL_FIELDS:
        raw_value = basin.get(name)
        # Temperature fields already converted in get_basin_for_point via SQL
        # But our raw query doesn't do the /10 conversion, so do it here
        if name in ("temp_yr", "temp_min", "temp_max") and raw_value is not None:
            raw_value = raw_value / 10.0

        min_val = ranges.get(f"{name}_min")
        max_val = ranges.get(f"{name}_max")
        norm_val = normalize_value(raw_value, min_val, max_val)
        row[f"n_{name}"] = norm_val

    # PNV share fields (rescale from 0-100 to 0-1)
    for i in range(1, 16):
        pnv_val = basin.get(f"pnv_{i:02d}")
        if pnv_val is not None:
            row[f"pnv_{i:02d}"] = pnv_val / 100.0
        else:
            row[f"pnv_{i:02d}"] = 0.0

    # Categorical one-hot fields
    for _, prefix, _ in CATEGORICAL_FIELDS:
        cat_value = basin.get(f"cat_{prefix}")
        valid_ids = cat_ids.get(prefix, set())

        for id_val in valid_ids:
            col_name = f"cat_{prefix}_{id_val}"
            row[col_name] = 1 if cat_value == id_val else 0

    return row


def insert_matrix_row(cur, row: dict):
    """Insert a single matrix row."""
    cols = list(row.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)

    sql = f"INSERT INTO edop_matrix ({col_names}) VALUES ({placeholders})"
    cur.execute(sql, [row[c] for c in cols])


def main():
    print("EDOP Matrix Population Script")
    print("=" * 50)

    # Load WH sites
    print(f"\n1. Loading WH sites from {WH_SITES_PATH}...")
    sites = load_wh_sites()
    print(f"   Loaded {len(sites)} sites")

    # Connect to database
    print("\n2. Connecting to database...")
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Clear existing data
            print("\n3. Clearing existing data...")
            cur.execute("DELETE FROM edop_matrix")
            cur.execute("DELETE FROM edop_wh_sites")
            cur.execute("DELETE FROM edop_norm_ranges")

            # Compute and store global ranges
            print("\n4. Computing global normalization ranges...")
            ranges = compute_global_ranges(cur)
            populate_norm_ranges(cur, ranges)
            print(f"   Stored {len(ranges)} range values")

            # Get categorical IDs
            print("\n5. Loading categorical lookup IDs...")
            cat_ids = get_categorical_ids(cur)
            total_cats = sum(len(ids) for ids in cat_ids.values())
            print(f"   Loaded {total_cats} categorical IDs across {len(cat_ids)} tables")

            # Populate WH sites
            print("\n6. Populating WH sites and querying basins...")
            id_mapping = populate_wh_sites(cur, sites)
            sites_with_basin = sum(1 for s in sites if s.get("basin"))
            print(f"   Inserted {len(sites)} sites, {sites_with_basin} have basin matches")

            # Build and insert matrix rows
            print("\n7. Building and inserting matrix rows...")
            for i, site in enumerate(sites):
                row = build_matrix_row(site, ranges, cat_ids)
                insert_matrix_row(cur, row)
                if (i + 1) % 5 == 0:
                    print(f"   Processed {i + 1}/{len(sites)} sites...")

            print(f"   Inserted {len(sites)} matrix rows")

            # Commit transaction
            conn.commit()
            print("\n8. Transaction committed successfully!")

            # Summary statistics
            print("\n" + "=" * 50)
            print("SUMMARY")
            print("=" * 50)
            cur.execute("SELECT COUNT(*) FROM edop_wh_sites")
            print(f"edop_wh_sites rows: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM edop_norm_ranges")
            print(f"edop_norm_ranges rows: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM edop_matrix")
            print(f"edop_matrix rows: {cur.fetchone()[0]}")

            # Count non-null numerical columns in first row
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'edop_matrix'
            """)
            print(f"edop_matrix columns: {cur.fetchone()[0]}")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
