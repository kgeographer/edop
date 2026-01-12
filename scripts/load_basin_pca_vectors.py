#!/usr/bin/env python3
"""
Load basin PCA coordinates into PostgreSQL using pgvector.

Creates table basin08_pca with vector column for similarity search.
Uses first 50 components (~72% variance) for efficiency.

Usage:
    python scripts/load_basin_pca_vectors.py
"""

import numpy as np
import psycopg
import os
from pathlib import Path

# Config
N_COMPONENTS = 50  # Use first 50 of 150 components
BATCH_SIZE = 5000

def main():
    # Load numpy files
    output_dir = Path("output")
    coords = np.load(output_dir / "basin08_pca_coords.npy")
    basin_ids = np.load(output_dir / "basin08_basin_ids.npy")

    print(f"Loaded {len(basin_ids)} basins with {coords.shape[1]} components")
    print(f"Using first {N_COMPONENTS} components")

    # Truncate to N_COMPONENTS
    coords = coords[:, :N_COMPONENTS]

    # Connect to database
    conn = psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )

    with conn.cursor() as cur:
        # Create table
        print("Creating table basin08_pca...")
        cur.execute("DROP TABLE IF EXISTS basin08_pca CASCADE")
        cur.execute(f"""
            CREATE TABLE basin08_pca (
                basin_id INTEGER PRIMARY KEY,
                hybas_id BIGINT NOT NULL,
                pca vector({N_COMPONENTS})
            )
        """)

        # We need to map hybas_id to basin08.id
        # First, build a lookup from hybas_id to id
        print("Building hybas_id to basin_id lookup...")
        cur.execute("SELECT id, hybas_id FROM basin08")
        hybas_to_id = {int(row[1]): row[0] for row in cur.fetchall()}
        print(f"  Found {len(hybas_to_id)} basins in basin08")

        # Insert in batches
        print(f"Inserting {len(basin_ids)} rows in batches of {BATCH_SIZE}...")
        inserted = 0
        skipped = 0

        for i in range(0, len(basin_ids), BATCH_SIZE):
            batch_ids = basin_ids[i:i+BATCH_SIZE]
            batch_coords = coords[i:i+BATCH_SIZE]

            rows = []
            for hybas_id, pca in zip(batch_ids, batch_coords):
                hybas_id = int(hybas_id)
                basin_id = hybas_to_id.get(hybas_id)
                if basin_id is None:
                    skipped += 1
                    continue
                # Format vector as string for pgvector
                vec_str = "[" + ",".join(str(float(x)) for x in pca) + "]"
                rows.append((basin_id, hybas_id, vec_str))

            if rows:
                cur.executemany(
                    "INSERT INTO basin08_pca (basin_id, hybas_id, pca) VALUES (%s, %s, %s)",
                    rows
                )
                inserted += len(rows)

            if (i + BATCH_SIZE) % 50000 == 0 or i + BATCH_SIZE >= len(basin_ids):
                print(f"  Processed {min(i + BATCH_SIZE, len(basin_ids))}/{len(basin_ids)}")

        print(f"Inserted {inserted} rows, skipped {skipped}")

        # Create index for fast similarity search
        print("Creating IVFFlat index (this may take a minute)...")
        # Use 100 lists for ~190k rows (sqrt(n) is a good starting point)
        cur.execute("""
            CREATE INDEX basin08_pca_idx ON basin08_pca
            USING ivfflat (pca vector_l2_ops) WITH (lists = 100)
        """)

        # Also index basin_id for lookups
        cur.execute("CREATE INDEX basin08_pca_basin_id_idx ON basin08_pca (basin_id)")

        conn.commit()
        print("Done!")

        # Verify
        cur.execute("SELECT COUNT(*) FROM basin08_pca")
        count = cur.fetchone()[0]
        print(f"Table basin08_pca has {count} rows")

if __name__ == "__main__":
    main()
