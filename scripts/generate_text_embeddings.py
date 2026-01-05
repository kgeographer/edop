#!/usr/bin/env python3
"""
Generate text embeddings for World Heritage site Wikipedia descriptions.

Uses OpenAI text-embedding-3-small to embed wiki_lead text, computes
pairwise cosine similarity, runs k-means clustering, and persists
results to PostgreSQL for comparison with environmental similarity.

Prerequisites:
- OPENAI_API_KEY in .env
- app/data/wh_wikipedia_leads.tsv exists
- edop_wh_sites table populated

Usage:
    python scripts/generate_text_embeddings.py
"""

import csv
import os
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import KMeans

load_dotenv()

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
N_CLUSTERS = 5  # Match environmental clustering
DATA_FILE = Path(__file__).parent.parent / "app" / "data" / "wh_wikipedia_leads.tsv"


def get_db_connection():
    """Create database connection from environment variables."""
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def load_wikipedia_leads():
    """Load Wikipedia lead text from TSV file."""
    sites = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sites.append({
                "id_no": int(row["id_no"]),
                "wh_name": row["wh_name"],
                "wiki_lead": row["wiki_lead"],
            })
    return sites


def get_site_id_mapping(conn):
    """Get mapping from id_no to site_id."""
    with conn.cursor() as cur:
        cur.execute("SELECT id_no, site_id FROM edop_wh_sites")
        return {row[0]: row[1] for row in cur.fetchall()}


def generate_embeddings(sites):
    """Generate OpenAI embeddings for each site's wiki_lead."""
    client = OpenAI()

    print(f"   Generating embeddings for {len(sites)} sites...")

    embeddings = []
    for i, site in enumerate(sites):
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=site["wiki_lead"]
        )
        embedding = response.data[0].embedding
        embeddings.append(embedding)
        print(f"   [{i+1}/{len(sites)}] {site['wh_name'][:40]}")

    return np.array(embeddings)


def compute_cosine_similarity(embeddings):
    """Compute pairwise cosine similarity matrix."""
    # Cosine distance, then convert to similarity
    distances = squareform(pdist(embeddings, metric="cosine"))
    similarity = 1 - distances  # cosine similarity = 1 - cosine distance
    return distances, similarity


def run_clustering(embeddings, n_clusters):
    """Run K-means clustering on embeddings."""
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Compute distance to centroid for each point
    distances_to_centroid = []
    for i, label in enumerate(labels):
        centroid = kmeans.cluster_centers_[label]
        dist = np.linalg.norm(embeddings[i] - centroid)
        distances_to_centroid.append(dist)

    return labels, np.array(distances_to_centroid)


def create_tables(conn):
    """Create tables for text embeddings if they don't exist."""
    with conn.cursor() as cur:
        # Embeddings table (store as float array)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS edop_text_embeddings (
                site_id INTEGER PRIMARY KEY REFERENCES edop_wh_sites(site_id),
                embedding FLOAT8[] NOT NULL,
                model TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Text-based similarity table (mirrors edop_similarity)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS edop_text_similarity (
                site_a INTEGER NOT NULL REFERENCES edop_wh_sites(site_id),
                site_b INTEGER NOT NULL REFERENCES edop_wh_sites(site_id),
                distance FLOAT8,
                similarity FLOAT8,
                PRIMARY KEY (site_a, site_b)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_text_similarity_a ON edop_text_similarity(site_a)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_text_similarity_b ON edop_text_similarity(site_b)")

        # Text-based clusters table (mirrors edop_clusters)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS edop_text_clusters (
                site_id INTEGER PRIMARY KEY REFERENCES edop_wh_sites(site_id),
                cluster_id INTEGER NOT NULL,
                cluster_label TEXT,
                distance_to_centroid FLOAT8
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_text_clusters_cluster ON edop_text_clusters(cluster_id)")


def persist_embeddings(conn, site_ids, embeddings, model):
    """Store embeddings in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_text_embeddings")

        for site_id, embedding in zip(site_ids, embeddings):
            cur.execute(
                """INSERT INTO edop_text_embeddings (site_id, embedding, model)
                   VALUES (%s, %s, %s)""",
                (int(site_id), embedding.tolist(), model)
            )


def persist_similarity(conn, site_ids, distances, similarity):
    """Store similarity matrix in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_text_similarity")

        n = len(site_ids)
        for i in range(n):
            for j in range(n):
                if i != j:
                    cur.execute(
                        """INSERT INTO edop_text_similarity (site_a, site_b, distance, similarity)
                           VALUES (%s, %s, %s, %s)""",
                        (int(site_ids[i]), int(site_ids[j]),
                         float(distances[i, j]), float(similarity[i, j]))
                    )


def persist_clusters(conn, site_ids, labels, distances_to_centroid):
    """Store cluster assignments in database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM edop_text_clusters")

        for i, site_id in enumerate(site_ids):
            cur.execute(
                """INSERT INTO edop_text_clusters (site_id, cluster_id, distance_to_centroid)
                   VALUES (%s, %s, %s)""",
                (int(site_id), int(labels[i]), float(distances_to_centroid[i]))
            )


def print_cluster_summary(sites, site_ids, labels):
    """Print cluster membership summary."""
    # Build id_no -> name mapping
    id_to_name = {s["id_no"]: s["wh_name"] for s in sites}

    print("\n" + "=" * 60)
    print("TEXT-BASED CLUSTER ASSIGNMENTS")
    print("=" * 60)

    for cluster_id in range(N_CLUSTERS):
        members = [sites[i]["wh_name"]
                   for i, label in enumerate(labels) if label == cluster_id]
        print(f"\nCluster {cluster_id + 1} ({len(members)} sites):")
        for m in members:
            print(f"  - {m}")


def print_similarity_examples(conn):
    """Print example similarity queries."""
    print("\n" + "=" * 60)
    print("TEXT-BASED SIMILARITY EXAMPLES")
    print("=" * 60)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.name_en, b.name_en,
                   ROUND(s.similarity::numeric, 3) as sim
            FROM edop_text_similarity s
            JOIN edop_wh_sites a ON a.site_id = s.site_a
            JOIN edop_wh_sites b ON b.site_id = s.site_b
            WHERE s.site_a < s.site_b
            ORDER BY s.similarity DESC
            LIMIT 5
        """)

        print("\nMost Similar Pairs (by text):")
        for row in cur.fetchall():
            print(f"  {row[0][:30]:30s} <-> {row[1][:30]:30s}  (sim={row[2]})")


def main():
    print("EDOP Text Embedding Generation")
    print("=" * 60)

    # Load data
    print("\n1. Loading Wikipedia leads...")
    sites = load_wikipedia_leads()
    print(f"   Loaded {len(sites)} sites")

    conn = get_db_connection()

    try:
        # Map id_no -> site_id
        print("\n2. Mapping to database site IDs...")
        id_mapping = get_site_id_mapping(conn)
        site_ids = [id_mapping[s["id_no"]] for s in sites]
        print(f"   Mapped {len(site_ids)} sites")

        # Generate embeddings
        print("\n3. Generating OpenAI embeddings...")
        embeddings = generate_embeddings(sites)
        print(f"   Embedding shape: {embeddings.shape}")

        # Compute similarity
        print("\n4. Computing cosine similarity matrix...")
        distances, similarity = compute_cosine_similarity(embeddings)
        print(f"   {len(site_ids) * (len(site_ids) - 1)} pairwise comparisons")

        # Run clustering
        print(f"\n5. Running K-means clustering (k={N_CLUSTERS})...")
        labels, dist_to_centroid = run_clustering(embeddings, N_CLUSTERS)

        # Create tables and persist
        print("\n6. Persisting to database...")
        create_tables(conn)

        print("   - Embeddings...")
        persist_embeddings(conn, site_ids, embeddings, EMBEDDING_MODEL)

        print("   - Similarity matrix...")
        persist_similarity(conn, site_ids, distances, similarity)

        print("   - Cluster assignments...")
        persist_clusters(conn, site_ids, labels, dist_to_centroid)

        conn.commit()
        print("   Committed.")

        # Print summaries
        print_cluster_summary(sites, site_ids, labels)
        print_similarity_examples(conn)

    finally:
        conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
