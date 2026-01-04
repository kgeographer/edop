#!/usr/bin/env python3
"""
Persist top PCA loadings to database.

Stores top N features (by absolute loading value) for each principal component.
"""

import os
import numpy as np
import pandas as pd
import psycopg
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

TOP_N = 50  # Top features per component


def get_db_connection():
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def main():
    print("Persisting PCA Loadings")
    print("=" * 50)

    conn = get_db_connection()

    # Load matrix
    print("\n1. Loading matrix...")
    matrix_df = pd.read_sql("SELECT * FROM edop_matrix ORDER BY site_id", conn)
    feature_cols = [c for c in matrix_df.columns if c != "site_id"]
    X = matrix_df[feature_cols].values
    X = np.nan_to_num(X, nan=0.0)
    print(f"   {X.shape[0]} sites × {X.shape[1]} features")

    # Run PCA
    print("\n2. Running PCA...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    n_components = min(X.shape[0] - 1, X.shape[1])
    pca = PCA(n_components=n_components)
    pca.fit(X_scaled)
    print(f"   {n_components} components")

    # Extract and persist top loadings
    print(f"\n3. Extracting top {TOP_N} loadings per component...")

    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_pca_loadings")

        total_inserted = 0
        for pc_idx in range(n_components):
            loadings = pca.components_[pc_idx]
            abs_loadings = np.abs(loadings)

            # Get indices of top N by absolute value
            top_indices = np.argsort(abs_loadings)[-TOP_N:][::-1]

            for rank, feat_idx in enumerate(top_indices, 1):
                cur.execute(
                    """INSERT INTO edop_pca_loadings
                       (component, feature_name, loading, abs_loading, rank)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (pc_idx + 1, feature_cols[feat_idx],
                     float(loadings[feat_idx]), float(abs_loadings[feat_idx]), rank)
                )
                total_inserted += 1

        conn.commit()

    print(f"   Inserted {total_inserted} rows ({n_components} components × {TOP_N} features)")

    # Show example
    print("\n4. Top 10 loadings for PC1-3:")
    with conn.cursor() as cur:
        for pc in [1, 2, 3]:
            cur.execute("""
                SELECT feature_name, ROUND(loading::numeric, 3)
                FROM edop_pca_loadings
                WHERE component = %s
                ORDER BY rank
                LIMIT 10
            """, (pc,))
            print(f"\n   PC{pc}:")
            for row in cur.fetchall():
                sign = "+" if row[1] >= 0 else ""
                print(f"      {row[0]:30s} {sign}{row[1]}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
