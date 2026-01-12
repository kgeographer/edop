#!/usr/bin/env python3
"""
Update gaz.wh_cities table with geometry and basin_id.

This script:
1. Alters gaz.wh_cities table to add geom and basin_id columns
2. Parses whc_id_lookup.html to extract WHG_internal_id -> whc_id mapping
3. Reads whc_258_geom.tsv to get WHG_internal_id -> (lon, lat)
4. Joins to derive gaz.wh_cities.id -> (lon, lat)
5. Updates gaz.wh_cities with point geometry for each city
6. Populates basin_id from basin08 using ST_Contains

Prerequisites:
- gaz.wh_cities table must exist with id column
- basin08 table must exist with geometry
- Database connection via environment variables (PGHOST, PGPORT, etc.)

Usage:
    python scripts/update_wh_cities_geom.py
"""

import csv
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
GEOM_TSV_PATH = DATA_DIR / "whc_258_geom.tsv"
LOOKUP_HTML_PATH = DATA_DIR / "whc_id_lookup.html"


def get_db_connection():
    """Create database connection from environment variables."""
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def parse_lookup_html(filepath: Path) -> dict[int, int]:
    """
    Parse whc_id_lookup.html to extract WHG_internal_id -> gaz.wh_cities.id mapping.

    The HTML contains rows like:
    <tr ...><td>8349826</td><td>whc_034</td><td ...>Acre</td>...</tr>

    Returns dict mapping WHG internal ID (int) to gaz.wh_cities.id (int).
    """
    mapping = {}

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern to extract WHG ID and whc_id from each row
    # <td>8349826</td><td>whc_034</td>
    pattern = r"<td>(\d+)</td><td>(whc_\d+)</td>"

    for match in re.finditer(pattern, content):
        whg_id = int(match.group(1))
        whc_id_str = match.group(2)  # e.g., "whc_034"

        # Extract integer from whc_034 -> 34
        wh_cities_id = int(whc_id_str.replace("whc_", "").lstrip("0") or "0")

        mapping[whg_id] = wh_cities_id

    return mapping


def read_geom_tsv(filepath: Path) -> dict[int, tuple[float, float]]:
    """
    Read whc_258_geom.tsv to get WHG_internal_id -> (lon, lat).

    Returns dict mapping WHG internal ID (int) to (lon, lat) tuple.
    """
    geom_data = {}

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            whg_id = int(row["id"])
            lon = row["lon"]
            lat = row["lat"]

            # Skip rows with missing coordinates
            if lon and lat:
                try:
                    geom_data[whg_id] = (float(lon), float(lat))
                except ValueError:
                    print(f"  Warning: Invalid coordinates for WHG ID {whg_id}: lon={lon}, lat={lat}")

    return geom_data


def alter_table_add_columns(conn):
    """Add geom and basin_id columns to gaz.wh_cities if they don't exist."""
    with conn.cursor() as cur:
        # Check if geom column exists
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'gaz.wh_cities' AND column_name = 'geom'
        """)
        if not cur.fetchone():
            print("Adding 'geom' column to gaz.wh_cities...")
            cur.execute("""
                ALTER TABLE gaz.wh_cities
                ADD COLUMN geom geometry(Point, 4326)
            """)
        else:
            print("Column 'geom' already exists.")

        # Check if basin_id column exists
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'gaz.wh_cities' AND column_name = 'basin_id'
        """)
        if not cur.fetchone():
            print("Adding 'basin_id' column to gaz.wh_cities...")
            cur.execute("""
                ALTER TABLE gaz.wh_cities
                ADD COLUMN basin_id INTEGER
            """)
        else:
            print("Column 'basin_id' already exists.")

        conn.commit()


def update_geometries(conn, id_to_coords: dict[int, tuple[float, float]]):
    """Update gaz.wh_cities with point geometries."""
    print(f"\nUpdating geometries for {len(id_to_coords)} cities...")

    updated = 0
    not_found = 0

    with conn.cursor() as cur:
        for wh_id, (lon, lat) in id_to_coords.items():
            cur.execute("""
                UPDATE gaz.wh_cities
                SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                WHERE id = %s
            """, (lon, lat, wh_id))

            if cur.rowcount > 0:
                updated += 1
            else:
                not_found += 1
                print(f"  Warning: No gaz.wh_cities row with id={wh_id}")

        conn.commit()

    print(f"  Updated: {updated}, Not found: {not_found}")


def populate_basin_ids(conn):
    """Populate basin_id from basin08 using ST_Contains."""
    print("\nPopulating basin_id from basin08...")

    with conn.cursor() as cur:
        # Update basin_id for all cities with geometry
        # Use ST_Contains to find the smallest basin containing each point
        cur.execute("""
            UPDATE gaz.wh_cities w
            SET basin_id = subq.basin_id
            FROM (
                SELECT DISTINCT ON (w2.id)
                    w2.id as city_id,
                    b.id as basin_id
                FROM gaz.wh_cities w2
                JOIN basin08 b ON ST_Contains(b.geom, w2.geom)
                WHERE w2.geom IS NOT NULL
                ORDER BY w2.id, ST_Area(b.geom::geography) ASC
            ) subq
            WHERE w.id = subq.city_id
        """)

        updated = cur.rowcount
        conn.commit()

        # Check how many still have NULL basin_id
        cur.execute("""
            SELECT COUNT(*) FROM gaz.wh_cities
            WHERE geom IS NOT NULL AND basin_id IS NULL
        """)
        null_basin = cur.fetchone()[0]

        print(f"  Updated basin_id for {updated} cities")
        if null_basin > 0:
            print(f"  Warning: {null_basin} cities with geometry have no matching basin")
            # Show which ones
            cur.execute("""
                SELECT id, city, country FROM gaz.wh_cities
                WHERE geom IS NOT NULL AND basin_id IS NULL
                ORDER BY city
            """)
            for row in cur.fetchall():
                print(f"    - {row[1]}, {row[2]} (id={row[0]})")


def print_summary(conn):
    """Print summary statistics."""
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gaz.wh_cities")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM gaz.wh_cities WHERE geom IS NOT NULL")
        with_geom = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM gaz.wh_cities WHERE basin_id IS NOT NULL")
        with_basin = cur.fetchone()[0]

        print(f"Total cities:        {total}")
        print(f"With geometry:       {with_geom}")
        print(f"With basin_id:       {with_basin}")

        # Sample a few records
        print("\nSample records:")
        cur.execute("""
            SELECT id, city, country,
                   ST_X(geom) as lon, ST_Y(geom) as lat,
                   basin_id
            FROM gaz.wh_cities
            WHERE basin_id IS NOT NULL
            ORDER BY id
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  id={row[0]}: {row[1]}, {row[2]} | ({row[3]:.4f}, {row[4]:.4f}) | basin={row[5]}")


def main():
    print("="*60)
    print("Update gaz.wh_cities with geometry and basin_id")
    print("="*60)

    # Step 1: Parse lookup HTML
    print(f"\n1. Parsing {LOOKUP_HTML_PATH.name}...")
    whg_to_whcities = parse_lookup_html(LOOKUP_HTML_PATH)
    print(f"   Found {len(whg_to_whcities)} mappings")

    # Step 2: Read geometry TSV
    print(f"\n2. Reading {GEOM_TSV_PATH.name}...")
    whg_to_coords = read_geom_tsv(GEOM_TSV_PATH)
    print(f"   Found {len(whg_to_coords)} geometries")

    # Step 3: Join to get gaz.wh_cities.id -> coords
    print("\n3. Joining data...")
    id_to_coords = {}
    missing_geom = 0

    for whg_id, wh_id in whg_to_whcities.items():
        if whg_id in whg_to_coords:
            id_to_coords[wh_id] = whg_to_coords[whg_id]
        else:
            missing_geom += 1

    print(f"   Matched: {len(id_to_coords)}, Missing geometry: {missing_geom}")

    # Step 4: Database operations
    print("\n4. Connecting to database...")
    conn = get_db_connection()

    try:
        # Alter table to add columns
        print("\n5. Altering table structure...")
        alter_table_add_columns(conn)

        # Update geometries
        print("\n6. Updating geometries...")
        update_geometries(conn, id_to_coords)

        # Populate basin_ids
        print("\n7. Populating basin_ids...")
        populate_basin_ids(conn)

        # Print summary
        print_summary(conn)

    finally:
        conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
