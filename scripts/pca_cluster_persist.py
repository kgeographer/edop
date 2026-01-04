#!/usr/bin/env python3
"""
PCA, Clustering, and Similarity Analysis for EDOP World Heritage Sites.

Runs PCA, K-means clustering, computes similarity matrix, and persists all
results to PostgreSQL for future querying.

Prerequisites:
- Run sql/edop_matrix_schema.sql (creates source matrix)
- Run scripts/populate_matrix.py (populates matrix)
- Run sql/edop_pca_schema.sql (creates output tables)

Usage:
    python scripts/pca_cluster_persist.py
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
N_CLUSTERS = 5  # Number of clusters for K-means
OUTPUT_DIR = Path(__file__).parent.parent / "docs"


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
    """Load matrix data and site names from database."""
    # Get site info
    sites_df = pd.read_sql(
        "SELECT site_id, id_no, name_en FROM edop_wh_sites ORDER BY site_id",
        conn
    )

    # Get matrix data
    matrix_df = pd.read_sql(
        "SELECT * FROM edop_matrix ORDER BY site_id",
        conn
    )

    site_ids = matrix_df["site_id"].values
    feature_cols = [c for c in matrix_df.columns if c != "site_id"]
    X = matrix_df[feature_cols].values

    site_names = sites_df.set_index("site_id").loc[site_ids, "name_en"].values

    return X, feature_cols, site_ids, site_names


def run_pca(X):
    """Run PCA on the feature matrix."""
    # Handle NaN
    X = np.nan_to_num(X, nan=0.0)

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PCA with all possible components
    n_components = min(X.shape[0] - 1, X.shape[1])
    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_scaled)

    return pca, X_pca, scaler


def compute_similarity_matrix(X_pca, n_components=10):
    """Compute pairwise Euclidean distances using top N components."""
    # Use top N components for distance (captures most variance, reduces noise)
    X_reduced = X_pca[:, :n_components]

    # Compute pairwise distances
    distances = squareform(pdist(X_reduced, metric='euclidean'))

    # Convert to similarity (bounded 0-1)
    similarity = 1 / (1 + distances)

    return distances, similarity


def run_clustering(X_pca, n_clusters, n_components=10):
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


def persist_pca_coords(conn, site_ids, X_pca):
    """Store PCA coordinates in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_pca_coords")

        for i, site_id in enumerate(site_ids):
            cols = ["site_id"] + [f"pc{j+1}" for j in range(X_pca.shape[1])]
            vals = [int(site_id)] + [float(X_pca[i, j]) for j in range(X_pca.shape[1])]
            placeholders = ", ".join(["%s"] * len(vals))
            col_names = ", ".join(cols)
            cur.execute(f"INSERT INTO edop_pca_coords ({col_names}) VALUES ({placeholders})", vals)


def persist_variance(conn, pca):
    """Store explained variance in database."""
    cumulative = np.cumsum(pca.explained_variance_ratio_)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_pca_variance")

        for i in range(len(pca.explained_variance_ratio_)):
            cur.execute(
                """INSERT INTO edop_pca_variance
                   (component, explained_variance, explained_ratio, cumulative_ratio)
                   VALUES (%s, %s, %s, %s)""",
                (i + 1, float(pca.explained_variance_[i]),
                 float(pca.explained_variance_ratio_[i]), float(cumulative[i]))
            )


def persist_similarity(conn, site_ids, distances, similarity):
    """Store similarity matrix in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_similarity")

        n = len(site_ids)
        for i in range(n):
            for j in range(n):
                if i != j:  # Skip self-comparisons
                    cur.execute(
                        """INSERT INTO edop_similarity (site_a, site_b, distance, similarity)
                           VALUES (%s, %s, %s, %s)""",
                        (int(site_ids[i]), int(site_ids[j]),
                         float(distances[i, j]), float(similarity[i, j]))
                    )


def persist_clusters(conn, site_ids, labels, distances_to_centroid):
    """Store cluster assignments in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_clusters")

        for i, site_id in enumerate(site_ids):
            cur.execute(
                """INSERT INTO edop_clusters (site_id, cluster_id, distance_to_centroid)
                   VALUES (%s, %s, %s)""",
                (int(site_id), int(labels[i]), float(distances_to_centroid[i]))
            )


def generate_cluster_labels(conn, site_names, labels, X_pca, pca):
    """Generate interpretive labels for clusters based on loadings."""
    # For now, use simple numeric labels
    # Could be enhanced to analyze centroid positions and dominant loadings
    cluster_descriptions = {
        0: None, 1: None, 2: None, 3: None, 4: None
    }

    # Group sites by cluster
    clusters = {}
    for i, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(site_names[i])

    return clusters


def plot_clusters_2d(X_pca, labels, site_names, pca, output_path):
    """Plot sites colored by cluster."""
    fig, ax = plt.subplots(figsize=(14, 10))

    colors = plt.cm.Set2(np.linspace(0, 1, N_CLUSTERS))

    for cluster_id in range(N_CLUSTERS):
        mask = labels == cluster_id
        ax.scatter(X_pca[mask, 0], X_pca[mask, 1], s=150,
                  c=[colors[cluster_id]], label=f"Cluster {cluster_id + 1}",
                  edgecolors="white", linewidth=2, alpha=0.8)

    # Add labels
    for i, name in enumerate(site_names):
        short_name = name if len(name) < 25 else name[:22] + "..."
        ax.annotate(short_name, (X_pca[i, 0], X_pca[i, 1]),
                   fontsize=9, ha="left", va="bottom",
                   xytext=(5, 5), textcoords="offset points")

    var1 = pca.explained_variance_ratio_[0] * 100
    var2 = pca.explained_variance_ratio_[1] * 100
    ax.set_xlabel(f"PC1 ({var1:.1f}% variance)", fontsize=12)
    ax.set_ylabel(f"PC2 ({var2:.1f}% variance)", fontsize=12)
    ax.set_title(f"World Heritage Sites - K-means Clustering (k={N_CLUSTERS})", fontsize=14)

    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)

    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def print_similarity_examples(conn):
    """Print example similarity queries."""
    print("\n" + "=" * 70)
    print("EXAMPLE SIMILARITY QUERIES")
    print("=" * 70)

    with conn.cursor() as cur:
        # Most similar pairs overall
        cur.execute("""
            SELECT s.site_a, a.name_en, s.site_b, b.name_en,
                   ROUND(s.distance::numeric, 2) as dist,
                   ROUND(s.similarity::numeric, 3) as sim
            FROM edop_similarity s
            JOIN edop_wh_sites a ON a.site_id = s.site_a
            JOIN edop_wh_sites b ON b.site_id = s.site_b
            WHERE s.site_a < s.site_b
            ORDER BY s.distance ASC
            LIMIT 5
        """)

        print("\nMost Similar Pairs:")
        for row in cur.fetchall():
            print(f"  {row[1][:30]:30s} <-> {row[3][:30]:30s}  (dist={row[4]}, sim={row[5]})")

        # Sites most similar to Timbuktu
        cur.execute("""
            SELECT b.name_en, ROUND(s.distance::numeric, 2) as dist
            FROM edop_similarity s
            JOIN edop_wh_sites a ON a.site_id = s.site_a
            JOIN edop_wh_sites b ON b.site_id = s.site_b
            WHERE a.name_en = 'Timbuktu'
            ORDER BY s.distance ASC
            LIMIT 5
        """)

        print("\nSites Most Similar to Timbuktu:")
        for row in cur.fetchall():
            print(f"  {row[0]:40s} (dist={row[1]})")


def print_cluster_summary(site_names, labels):
    """Print cluster membership summary."""
    print("\n" + "=" * 70)
    print("CLUSTER ASSIGNMENTS")
    print("=" * 70)

    for cluster_id in range(N_CLUSTERS):
        members = [name for name, label in zip(site_names, labels) if label == cluster_id]
        print(f"\nCluster {cluster_id + 1} ({len(members)} sites):")
        for m in members:
            print(f"  - {m}")


def main():
    print("EDOP PCA + Clustering + Similarity Analysis")
    print("=" * 60)

    conn = get_db_connection()

    try:
        # Load data
        print("\n1. Loading matrix data...")
        X, feature_cols, site_ids, site_names = load_matrix_data(conn)
        print(f"   {X.shape[0]} sites × {X.shape[1]} features")

        # Run PCA
        print("\n2. Running PCA...")
        pca, X_pca, scaler = run_pca(X)
        print(f"   {X_pca.shape[1]} components extracted")
        print(f"   PC1-5 cumulative variance: {np.sum(pca.explained_variance_ratio_[:5])*100:.1f}%")

        # Compute similarity
        print("\n3. Computing similarity matrix...")
        distances, similarity = compute_similarity_matrix(X_pca, n_components=10)
        print(f"   {len(site_ids) * (len(site_ids) - 1)} pairwise comparisons")

        # Run clustering
        print(f"\n4. Running K-means clustering (k={N_CLUSTERS})...")
        labels, kmeans, dist_to_centroid = run_clustering(X_pca, N_CLUSTERS, n_components=10)

        # Persist all results
        print("\n5. Persisting to database...")

        print("   - PCA coordinates...")
        persist_pca_coords(conn, site_ids, X_pca)

        print("   - Variance explained...")
        persist_variance(conn, pca)

        print("   - Similarity matrix...")
        persist_similarity(conn, site_ids, distances, similarity)

        print("   - Cluster assignments...")
        persist_clusters(conn, site_ids, labels, dist_to_centroid)

        conn.commit()
        print("   Committed.")

        # Generate visualization
        print("\n6. Generating cluster plot...")
        plot_path = OUTPUT_DIR / "pca_clusters.png"
        plot_clusters_2d(X_pca, labels, site_names, pca, plot_path)
        print(f"   Saved: {plot_path}")

        # Print summaries
        print_cluster_summary(site_names, labels)
        print_similarity_examples(conn)

        # Final stats
        print("\n" + "=" * 70)
        print("PERSISTED DATA SUMMARY")
        print("=" * 70)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM edop_pca_coords")
            print(f"edop_pca_coords: {cur.fetchone()[0]} rows")

            cur.execute("SELECT COUNT(*) FROM edop_pca_variance")
            print(f"edop_pca_variance: {cur.fetchone()[0]} rows")

            cur.execute("SELECT COUNT(*) FROM edop_similarity")
            print(f"edop_similarity: {cur.fetchone()[0]} rows")

            cur.execute("SELECT COUNT(*) FROM edop_clusters")
            print(f"edop_clusters: {cur.fetchone()[0]} rows")

    finally:
        conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
