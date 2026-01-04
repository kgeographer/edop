-- EDOP PCA Persistence Schema
-- Stores PCA results, similarity matrix, and cluster assignments
-- Run with: psql -h localhost -p 5435 -U postgres -d edop < sql/edop_pca_schema.sql

-- Drop existing tables
DROP TABLE IF EXISTS edop_similarity CASCADE;
DROP TABLE IF EXISTS edop_pca_coords CASCADE;
DROP TABLE IF EXISTS edop_pca_variance CASCADE;
DROP TABLE IF EXISTS edop_clusters CASCADE;

--------------------------------------------------------------------------------
-- 1. PCA Coordinates - site positions in reduced space
--------------------------------------------------------------------------------
CREATE TABLE edop_pca_coords (
    site_id INTEGER PRIMARY KEY REFERENCES edop_wh_sites(site_id),
    pc1 DOUBLE PRECISION,
    pc2 DOUBLE PRECISION,
    pc3 DOUBLE PRECISION,
    pc4 DOUBLE PRECISION,
    pc5 DOUBLE PRECISION,
    pc6 DOUBLE PRECISION,
    pc7 DOUBLE PRECISION,
    pc8 DOUBLE PRECISION,
    pc9 DOUBLE PRECISION,
    pc10 DOUBLE PRECISION,
    pc11 DOUBLE PRECISION,
    pc12 DOUBLE PRECISION,
    pc13 DOUBLE PRECISION,
    pc14 DOUBLE PRECISION,
    pc15 DOUBLE PRECISION,
    pc16 DOUBLE PRECISION,
    pc17 DOUBLE PRECISION,
    pc18 DOUBLE PRECISION,
    pc19 DOUBLE PRECISION
);

COMMENT ON TABLE edop_pca_coords IS 'PCA-transformed coordinates for each WH site (19 components max for 20 samples)';

--------------------------------------------------------------------------------
-- 2. PCA Variance - explained variance per component
--------------------------------------------------------------------------------
CREATE TABLE edop_pca_variance (
    component INTEGER PRIMARY KEY,
    explained_variance DOUBLE PRECISION,
    explained_ratio DOUBLE PRECISION,
    cumulative_ratio DOUBLE PRECISION
);

COMMENT ON TABLE edop_pca_variance IS 'Explained variance for each principal component';

--------------------------------------------------------------------------------
-- 3. Similarity Matrix - pairwise distances between sites
--------------------------------------------------------------------------------
CREATE TABLE edop_similarity (
    site_a INTEGER REFERENCES edop_wh_sites(site_id),
    site_b INTEGER REFERENCES edop_wh_sites(site_id),
    distance DOUBLE PRECISION,
    similarity DOUBLE PRECISION,  -- 1 / (1 + distance) normalized
    PRIMARY KEY (site_a, site_b)
);

CREATE INDEX idx_similarity_a ON edop_similarity(site_a);
CREATE INDEX idx_similarity_b ON edop_similarity(site_b);

COMMENT ON TABLE edop_similarity IS 'Pairwise Euclidean distances in PCA space between WH sites';

--------------------------------------------------------------------------------
-- 4. Cluster Assignments
--------------------------------------------------------------------------------
CREATE TABLE edop_clusters (
    site_id INTEGER PRIMARY KEY REFERENCES edop_wh_sites(site_id),
    cluster_id INTEGER NOT NULL,
    cluster_label TEXT,
    distance_to_centroid DOUBLE PRECISION
);

CREATE INDEX idx_clusters_cluster ON edop_clusters(cluster_id);

COMMENT ON TABLE edop_clusters IS 'Cluster assignments from K-means on PCA coordinates';
