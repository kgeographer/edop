#!/usr/bin/env python3
"""
PCA, Clustering, and Similarity Analysis for WHC Cities (258).

Runs PCA, K-means clustering, computes similarity matrix, and persists all
results to PostgreSQL for future querying.

Prerequisites:
- whc_matrix_schema.sql run to create tables
- populate_whc_matrix.py run to populate whc_matrix

Usage:
    python scripts/whc_pca_cluster.py
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# Configuration
N_CLUSTERS = 10  # More clusters for 254 cities
N_PCA_COMPONENTS_FOR_CLUSTERING = 20  # Use more components with larger dataset
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "corpus_258"


def get_db_connection():
    """Create database connection from environment variables."""
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def load_matrix_data(conn):
    """Load matrix data and city names from database."""
    # Get city info
    cities_df = pd.read_sql(
        "SELECT id, city, country, region FROM gaz.wh_cities WHERE basin_id IS NOT NULL ORDER BY id",
        conn
    )

    # Get matrix data
    matrix_df = pd.read_sql(
        "SELECT * FROM whc_matrix ORDER BY city_id",
        conn
    )

    city_ids = matrix_df["city_id"].values
    feature_cols = [c for c in matrix_df.columns if c != "city_id"]
    X = matrix_df[feature_cols].values

    # Get city names matching matrix order
    cities_df = cities_df.set_index("id")
    city_names = [cities_df.loc[cid, "city"] for cid in city_ids]
    city_countries = [cities_df.loc[cid, "country"] for cid in city_ids]
    city_regions = [cities_df.loc[cid, "region"] for cid in city_ids]

    return X, feature_cols, city_ids, city_names, city_countries, city_regions


def run_pca(X, max_components=50):
    """Run PCA on the feature matrix."""
    # Handle NaN
    X = np.nan_to_num(X, nan=0.0)

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PCA with max components (limited for storage)
    n_components = min(max_components, X.shape[0] - 1, X.shape[1])
    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_scaled)

    return pca, X_pca, scaler


def compute_similarity_matrix(X_pca, n_components=20):
    """Compute pairwise Euclidean distances using top N components."""
    X_reduced = X_pca[:, :n_components]
    distances = squareform(pdist(X_reduced, metric='euclidean'))
    similarity = 1 / (1 + distances)
    return distances, similarity


def run_clustering(X_pca, n_clusters, n_components=20):
    """Run K-means clustering on PCA coordinates."""
    X_reduced = X_pca[:, :n_components]

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_reduced)

    # Compute distance to centroid for each point
    distances_to_centroid = []
    for i, label in enumerate(labels):
        centroid = kmeans.cluster_centers_[label]
        dist = np.linalg.norm(X_reduced[i] - centroid)
        distances_to_centroid.append(dist)

    return labels, kmeans, np.array(distances_to_centroid)


def persist_pca_coords(conn, city_ids, X_pca):
    """Store PCA coordinates in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM whc_pca_coords")

        n_cols = min(50, X_pca.shape[1])  # Table has 50 PC columns
        for i, city_id in enumerate(city_ids):
            cols = ["city_id"] + [f"pc{j+1}" for j in range(n_cols)]
            vals = [int(city_id)] + [float(X_pca[i, j]) for j in range(n_cols)]
            placeholders = ", ".join(["%s"] * len(vals))
            col_names = ", ".join(cols)
            cur.execute(f"INSERT INTO whc_pca_coords ({col_names}) VALUES ({placeholders})", vals)


def persist_variance(conn, pca):
    """Store explained variance in database."""
    cumulative = np.cumsum(pca.explained_variance_ratio_)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM whc_pca_variance")

        for i in range(len(pca.explained_variance_ratio_)):
            cur.execute(
                """INSERT INTO whc_pca_variance
                   (component, explained_variance, explained_ratio, cumulative_ratio)
                   VALUES (%s, %s, %s, %s)""",
                (i + 1, float(pca.explained_variance_[i]),
                 float(pca.explained_variance_ratio_[i]), float(cumulative[i]))
            )


def persist_similarity(conn, city_ids, distances, similarity):
    """Store similarity matrix in database (only store pairs where a < b to save space)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM whc_similarity")

        n = len(city_ids)
        batch = []
        batch_size = 1000

        for i in range(n):
            for j in range(i + 1, n):  # Only store upper triangle
                batch.append((
                    int(city_ids[i]), int(city_ids[j]),
                    float(distances[i, j]), float(similarity[i, j])
                ))

                if len(batch) >= batch_size:
                    cur.executemany(
                        """INSERT INTO whc_similarity (city_a, city_b, distance, similarity)
                           VALUES (%s, %s, %s, %s)""",
                        batch
                    )
                    batch = []

        # Insert remaining
        if batch:
            cur.executemany(
                """INSERT INTO whc_similarity (city_a, city_b, distance, similarity)
                   VALUES (%s, %s, %s, %s)""",
                batch
            )


def persist_clusters(conn, city_ids, labels, distances_to_centroid):
    """Store cluster assignments in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM whc_clusters")

        for i, city_id in enumerate(city_ids):
            cur.execute(
                """INSERT INTO whc_clusters (city_id, cluster_id, distance_to_centroid)
                   VALUES (%s, %s, %s)""",
                (int(city_id), int(labels[i]), float(distances_to_centroid[i]))
            )


def plot_clusters_2d(X_pca, labels, city_names, city_regions, pca, output_path, n_clusters):
    """Plot cities colored by cluster."""
    fig, ax = plt.subplots(figsize=(16, 12))

    colors = plt.cm.tab10(np.linspace(0, 1, n_clusters))

    for cluster_id in range(n_clusters):
        mask = labels == cluster_id
        ax.scatter(X_pca[mask, 0], X_pca[mask, 1], s=80,
                  c=[colors[cluster_id]], label=f"Cluster {cluster_id + 1}",
                  edgecolors="white", linewidth=1.5, alpha=0.8)

    # Add labels for subset (to avoid overcrowding)
    # Label only points far from center or cluster exemplars
    for i, name in enumerate(city_names):
        # Only label some points to avoid clutter
        if i % 5 == 0 or np.abs(X_pca[i, 0]) > 5 or np.abs(X_pca[i, 1]) > 5:
            short_name = name if len(name) < 20 else name[:17] + "..."
            ax.annotate(short_name, (X_pca[i, 0], X_pca[i, 1]),
                       fontsize=7, ha="left", va="bottom",
                       xytext=(3, 3), textcoords="offset points", alpha=0.7)

    var1 = pca.explained_variance_ratio_[0] * 100
    var2 = pca.explained_variance_ratio_[1] * 100
    ax.set_xlabel(f"PC1 ({var1:.1f}% variance)", fontsize=12)
    ax.set_ylabel(f"PC2 ({var2:.1f}% variance)", fontsize=12)
    ax.set_title(f"World Heritage Cities - Environmental Clusters (k={n_clusters}, n=254)", fontsize=14)

    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)

    ax.legend(loc="upper right", ncol=2)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def print_cluster_summary(city_names, city_countries, city_regions, labels, n_clusters):
    """Print cluster membership summary."""
    print("\n" + "=" * 70)
    print("CLUSTER ASSIGNMENTS")
    print("=" * 70)

    for cluster_id in range(n_clusters):
        members = [
            (name, country, region)
            for name, country, region, label in zip(city_names, city_countries, city_regions, labels)
            if label == cluster_id
        ]
        print(f"\nCluster {cluster_id + 1} ({len(members)} cities):")

        # Show first 10 members
        for name, country, region in members[:10]:
            print(f"  - {name}, {country} [{region}]")
        if len(members) > 10:
            print(f"  ... and {len(members) - 10} more")


def print_similarity_examples(conn):
    """Print example similarity queries."""
    print("\n" + "=" * 70)
    print("EXAMPLE SIMILARITY QUERIES")
    print("=" * 70)

    with conn.cursor() as cur:
        # Most similar pairs overall
        cur.execute("""
            SELECT c1.city, c1.country, c2.city, c2.country,
                   ROUND(s.distance::numeric, 2) as dist,
                   ROUND(s.similarity::numeric, 3) as sim
            FROM whc_similarity s
            JOIN gaz.wh_cities c1 ON c1.id = s.city_a
            JOIN gaz.wh_cities c2 ON c2.id = s.city_b
            ORDER BY s.distance ASC
            LIMIT 10
        """)

        print("\nMost Similar Pairs:")
        for row in cur.fetchall():
            print(f"  {row[0]}, {row[1][:15]:15s} <-> {row[2]}, {row[3][:15]:15s}  (dist={row[4]}, sim={row[5]})")

        # Sites most similar to Timbuktu
        cur.execute("""
            SELECT c2.city, c2.country, ROUND(s.distance::numeric, 2) as dist
            FROM whc_similarity s
            JOIN gaz.wh_cities c1 ON c1.id = s.city_a
            JOIN gaz.wh_cities c2 ON c2.id = s.city_b
            WHERE c1.city = 'Timbuktu'
            ORDER BY s.distance ASC
            LIMIT 5
        """)

        print("\nCities Most Similar to Timbuktu (environmental):")
        for row in cur.fetchall():
            print(f"  {row[0]}, {row[1]:20s} (dist={row[2]})")


def print_variance_summary(pca):
    """Print variance explained by components."""
    print("\n" + "=" * 70)
    print("VARIANCE EXPLAINED")
    print("=" * 70)

    cumulative = np.cumsum(pca.explained_variance_ratio_)
    print("\n  PC    Variance    Cumulative")
    print("  --    --------    ----------")
    for i in range(min(10, len(pca.explained_variance_ratio_))):
        print(f"  {i+1:2d}    {pca.explained_variance_ratio_[i]*100:6.2f}%     {cumulative[i]*100:6.2f}%")

    # Find components for 80% and 90%
    for threshold in [0.80, 0.90]:
        n_comps = np.argmax(cumulative >= threshold) + 1
        print(f"\n  Components for {threshold*100:.0f}% variance: {n_comps}")


def main():
    print("=" * 70)
    print("WHC Cities PCA + Clustering + Similarity Analysis")
    print("=" * 70)

    conn = get_db_connection()

    try:
        # Load data
        print("\n1. Loading matrix data...")
        X, feature_cols, city_ids, city_names, city_countries, city_regions = load_matrix_data(conn)
        print(f"   {X.shape[0]} cities × {X.shape[1]} features")

        # Run PCA
        print("\n2. Running PCA...")
        pca, X_pca, scaler = run_pca(X, max_components=50)
        print(f"   {X_pca.shape[1]} components extracted")
        print(f"   PC1-5 cumulative variance: {np.sum(pca.explained_variance_ratio_[:5])*100:.1f}%")

        # Compute similarity
        print("\n3. Computing similarity matrix...")
        distances, similarity = compute_similarity_matrix(X_pca, n_components=N_PCA_COMPONENTS_FOR_CLUSTERING)
        n_pairs = len(city_ids) * (len(city_ids) - 1) // 2
        print(f"   {n_pairs} unique pairwise comparisons")

        # Run clustering
        print(f"\n4. Running K-means clustering (k={N_CLUSTERS})...")
        labels, kmeans, dist_to_centroid = run_clustering(X_pca, N_CLUSTERS, n_components=N_PCA_COMPONENTS_FOR_CLUSTERING)

        # Persist all results
        print("\n5. Persisting to database...")

        print("   - PCA coordinates...")
        persist_pca_coords(conn, city_ids, X_pca)

        print("   - Variance explained...")
        persist_variance(conn, pca)

        print("   - Similarity matrix...")
        persist_similarity(conn, city_ids, distances, similarity)

        print("   - Cluster assignments...")
        persist_clusters(conn, city_ids, labels, dist_to_centroid)

        conn.commit()
        print("   Committed.")

        # Generate visualization
        print("\n6. Generating cluster plot...")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plot_path = OUTPUT_DIR / "env_clusters.png"
        plot_clusters_2d(X_pca, labels, city_names, city_regions, pca, plot_path, N_CLUSTERS)
        print(f"   Saved: {plot_path}")

        # Print summaries
        print_variance_summary(pca)
        print_cluster_summary(city_names, city_countries, city_regions, labels, N_CLUSTERS)
        print_similarity_examples(conn)

        # Final stats
        print("\n" + "=" * 70)
        print("PERSISTED DATA SUMMARY")
        print("=" * 70)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM whc_pca_coords")
            print(f"whc_pca_coords: {cur.fetchone()[0]} rows")

            cur.execute("SELECT COUNT(*) FROM whc_pca_variance")
            print(f"whc_pca_variance: {cur.fetchone()[0]} rows")

            cur.execute("SELECT COUNT(*) FROM whc_similarity")
            print(f"whc_similarity: {cur.fetchone()[0]} rows")

            cur.execute("SELECT COUNT(*) FROM whc_clusters")
            print(f"whc_clusters: {cur.fetchone()[0]} rows")

    finally:
        conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
