# Session Log: 11 January 2026

## Objective
Cluster all 190,675 basin08 basins using the full 1,565-dimensional environmental signature (matching the pilot schema), and create supporting documentation.

---

## 1. Documentation Housekeeping

Created `docs/edop_database_schema.md` — comprehensive reference for all source and result tables to reduce context-building between Claude Code sessions.

Contents:
- Source data tables (basin08, eco847, wh_cities, gaz.* schema)
- Result tables organized by scope (20 WH pilot, 258 WHC, global basin)
- Key relationships, feature dimensions, example queries
- Session log index

---

## 2. Full-Dimensional Basin Clustering Pipeline

### Problem
The 9 Jan clustering used only 98 features (simplified). Goal: use the full 1,565 dimensions defined in `edop_matrix_schema.sql` for the 20 WH sites pilot.

### Feature Composition (1,565 total)

| Category | Count | Source |
|----------|-------|--------|
| Numerical | 31 | Normalized 0-1 from basin08 columns |
| PNV | 15 | Potential natural vegetation shares (0-1) |
| TEC | 847 | Terrestrial ecoregions (one-hot from lu_tec) |
| FEC | 449 | Freshwater ecoregions (one-hot from lu_fec) |
| CLS | 125 | Climate/land-use strata (one-hot from lu_cls) |
| GLC | 23 | Global land cover (one-hot from lu_glc) |
| CLZ | 18 | Climate zones (one-hot from lu_clz) |
| LIT | 16 | Lithology (one-hot from lu_lit) |
| TBI | 15 | Biomes (one-hot from lu_tbi) |
| FMH | 14 | Freshwater major habitat (one-hot from lu_fmh) |
| WET | 12 | Wetland types (one-hot from lu_wet) |

### Pipeline Scripts

#### Step 1: Sparse Matrix Generation
**Script:** `scripts/basin08_sparse_matrix.py`

- Queries all 190,675 basins from basin08
- Extracts and normalizes numerical/PNV features
- One-hot encodes categorical features using lu_* lookup tables
- Outputs scipy sparse matrix (CSR format)

**Results:**
- Matrix shape: 190,675 × 1,565
- Non-zero entries: 6,317,227
- Sparsity: 97.88%
- File size: 13 MB

**Output files:**
- `output/basin08_sparse_matrix.npz`
- `output/basin08_feature_names.json`
- `output/basin08_basin_ids.npy`

#### Step 2: PCA Dimensionality Reduction
**Script:** `scripts/basin08_pca.py`

- Uses TruncatedSVD (efficient for sparse matrices)
- Target: 90% variance (achieved 86.2% with 150 components)

**Results:**
```
Components for variance:
   10 components: 37.6%
   20 components: 52.2%
   50 components: 71.9%
  100 components: 81.8%
  150 components: 86.2%
```

Note: Variance is highly distributed (PC1 only 2.81%) — expected for 1,519 one-hot categorical columns.

**Top loadings (PC1):** slope_upstream, slope_avg, pct_clay, pct_silt, pct_sand (terrain/soil)

**Output files:**
- `output/basin08_pca_coords.npy` (109 MB)
- `output/basin08_pca_variance.json`
- `output/basin08_pca_loadings.npy`

#### Step 3: Cluster Analysis
**Script:** `scripts/basin08_cluster_analysis.py`

Tested k = [5, 10, 15, 20, 25, 30, 40, 50] using:
- Elbow method (inertia)
- Silhouette score (sampled, n=10,000)
- Calinski-Harabasz index

**Results:**
| k | Inertia | Silhouette | Calinski-Harabasz |
|---|---------|------------|-------------------|
| 5 | 971,722 | 0.111 | 735 |
| 10 | 844,901 | 0.107 | 544 |
| 20 | 748,511 | 0.102 | 357 |
| 50 | 611,203 | 0.123 | 217 |

**Recommendations:**
- Silhouette: k=50 (but all scores low: 0.10-0.12)
- Calinski-Harabasz: k=5
- Elbow: k=10

**Decision:** k=20 chosen for balance of interpretability and continuity with previous work.

**Output files:**
- `output/basin08_cluster_analysis.json`
- `output/basin08_cluster_analysis.png`

#### Step 4: Final Clustering
**Script:** `scripts/basin08_clustering_k20.py`

- MiniBatch K-means with k=20
- Creates database table `basin08_pca_clusters`

**Cluster distribution:**
```
Cluster 13: 18,736 basins (9.8%)
Cluster  3: 17,852 basins (9.4%)
Cluster  9: 17,247 basins (9.0%)
Cluster 10: 13,991 basins (7.3%)
...
Cluster  2:  4,263 basins (2.2%)
```

Reasonably balanced: 4,263 to 18,736 basins per cluster.

**Output files:**
- `output/basin08_cluster_assignments.npy`
- `output/basin08_cluster_centroids.npy`
- `output/basin08_cluster_metadata.json`

---

## 3. Database Changes

### New Table: basin08_pca_clusters

```sql
CREATE TABLE basin08_pca_clusters (
    hybas_id BIGINT PRIMARY KEY,
    cluster_id INTEGER NOT NULL
);
CREATE INDEX idx_basin08_pca_clusters_cluster ON basin08_pca_clusters(cluster_id);
```

**Rows:** 190,675
**Comment:** K-means cluster assignments (k=20) for basin08 based on 1565-dim environmental signatures reduced via PCA to 150 components (86.2% variance). Created 11 Jan 2026.

---

## 4. Comparison: Simplified vs Full Clustering

| Aspect | 9 Jan (simplified) | 11 Jan (full) |
|--------|-------------------|---------------|
| Features | 98 | 1,565 |
| Categorical encoding | 52 one-hot | 1,519 one-hot |
| PCA | None | 150 components |
| k | 20 | 20 |
| Storage | `basin08.cluster_id` column | `basin08_pca_clusters` table |

The full clustering includes all categorical lookup tables (TEC, FEC, CLS, GLC, CLZ, LIT, TBI, FMH, WET) while the simplified version only had lithology and biome.

---

## Files Created

```
scripts/
├── basin08_sparse_matrix.py      # Sparse feature matrix generation
├── basin08_pca.py                # PCA dimensionality reduction
├── basin08_cluster_analysis.py   # Optimal k analysis
├── basin08_clustering_k20.py     # Final k=20 clustering
├── basin08_cluster_labels.py     # Cluster characterization and labeling
└── basin08_famd_comparison.py    # PCA vs FAMD validation

output/
├── basin08_sparse_matrix.npz     # 13 MB sparse matrix
├── basin08_feature_names.json    # 1,565 feature names
├── basin08_basin_ids.npy         # Basin ID ordering
├── basin08_pca_coords.npy        # 109 MB PCA coordinates
├── basin08_pca_variance.json     # Variance per component
├── basin08_pca_loadings.npy      # Feature loadings
├── basin08_cluster_analysis.json # k analysis results
├── basin08_cluster_analysis.png  # Elbow/silhouette plots
├── basin08_cluster_assignments.npy
├── basin08_cluster_centroids.npy
├── basin08_cluster_metadata.json
├── basin08_cluster_labels.json   # Auto-generated labels
├── basin08_cluster_labels_manual.json  # Editable labels
├── basin08_famd_comparison.json  # PCA vs FAMD metrics
└── basin08_famd_coords_sample.npy  # FAMD coords for 50k sample

docs/
├── edop_database_schema.md       # New schema reference
└── session_log_11Jan2026.md      # This file
```

---

---

## 5. Cluster Labeling

**Script:** `scripts/basin08_cluster_labels.py`

Analyzes each cluster by:
- Centroid characteristics (temp, precip, aridity, elevation)
- Dominant biome from lu_tbi lookup
- WHC cities contained (via basin08 join)

**Key findings:**
- Clusters 7, 11 (76+64 cities): Mediterranean/Temperate — Amsterdam, Algiers, Aleppo
- Cluster 9 (18 cities): Tropical Coastal — Bridgetown, Denpasar, Galle
- Cluster 3 (3 cities): Arctic Tundra — Norwegian municipalities
- Clusters 5, 18 (0 cities): Extreme deserts — no WHC cities

**Output:** `output/basin08_cluster_labels_manual.json` — editable label mapping

---

## 6. PCA vs FAMD Validation

**Script:** `scripts/basin08_famd_comparison.py`

Tested whether PCA (with one-hot encoding) produces meaningfully different clusters than FAMD (which properly handles mixed continuous/categorical data).

**Method:**
- Sampled 50,000 basins
- Ran FAMD with 50 components on mixed data (46 continuous + 9 categorical)
- Clustered with k=20
- Compared to PCA cluster assignments

**Results:**
| Metric | Value |
|--------|-------|
| Adjusted Rand Index | 0.437 (moderate) |
| Normalized Mutual Info | 0.609 |
| Best-match agreement | ~60% |

**Key observation:** FAMD explains only 10.9% variance at 50 components vs PCA's 86.2%. MCA (for categoricals) produces many dimensions of similar weight—fundamentally different geometry than one-hot + PCA.

**Conclusion:** Moderate agreement. PCA is acceptable for exploratory work; FAMD would be more defensible for rigorous analysis.

**From ChatGPT** “We validated PCA-based clustering against FAMD (which properly handles mixed continuous/categorical data). Cluster agreement was moderate (ARI ≈ 0.44, NMI ≈ 0.61), indicating that PCA captures the dominant environmental gradients while FAMD introduces additional categorical nuance without overturning the overall structure.”
"PCA is acceptable because environmental continuous variables dominate basin similarity; FAMD reveals additional categorical nuance but does not overturn the core clustering structure."
---

## Notes

- This is exploratory/preliminary work; clusters subject to revision based on downstream utility
- Ultimate goal: compare cities within clustered basins using other methods TBD
- Low silhouette scores (0.10-0.12) indicate continuous environmental gradients rather than discrete clusters — expected for geographic data
- Centroids saved for assigning new points to existing clusters

---

## Next Steps (Potential)

- [ ] Compare with 9 Jan simplified clustering (agreement analysis)
- [x] Build edop_gaz table with autocomplete for UI signature lookup
- [ ] Resume WHG API integration when endpoint limitations resolved
- [ ] Address similarity granularity problem (see section 9)

---

## 7. Gazetteer Import (gaz.edop_gaz)

### Schema
```sql
CREATE TABLE gaz.edop_gaz (
    id SERIAL PRIMARY KEY,
    source TEXT,           -- e.g., 'whg', 'pleiades'
    source_id TEXT,        -- original ID from source
    title TEXT NOT NULL,
    ccodes TEXT[],         -- country codes array
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    geom GEOMETRY(Point, 4326),
    basin_id INTEGER       -- FK to basin08.id (added later)
);
```

### Import Process
Imported ~97k places from WHG export via temp table with deduplication:

```sql
INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
SELECT source, source_id, title,
       CASE WHEN ccodes_csv IS NOT NULL AND ccodes_csv != ''
            THEN string_to_array(ccodes_csv, ',') ELSE NULL END,
       lon, lat,
       ST_SetSRID(ST_MakePoint(lon, lat), 4326)
FROM gaz.whg_import_temp t
WHERE t.lon IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM gaz.edop_gaz eg
      WHERE eg.title = t.title
        AND eg.ccodes && string_to_array(t.ccodes_csv, ',')
        AND ABS(eg.lon - t.lon) < 0.15
        AND ABS(eg.lat - t.lat) < 0.15
  );
```

**Result:** 97,178 rows in gaz.edop_gaz

### Basin Assignment
Added `basin_id` column and populated via spatial join:

```sql
ALTER TABLE gaz.edop_gaz ADD COLUMN basin_id integer;
UPDATE gaz.edop_gaz g SET basin_id = b.id FROM basin08 b WHERE ST_Covers(b.geom, g.geom);
CREATE INDEX edop_gaz_basin_id_idx ON gaz.edop_gaz (basin_id);
```

---

## 8. UI: Gazetteer Pill

### New Features
Added "EDOP Gazetteer" pill to Main tab (now the default/first pill):

- **Autocomplete input** - searches gaz.edop_gaz by title prefix (ILIKE), triggers after 3 chars
- **API endpoint** `/api/gaz-suggest` - returns id, title, source, ccodes, lon, lat
- **Selection flow** - places marker, fetches environmental signature, renders profile
- **Similar (env) button** - finds places in basins of same cluster
- **Clear link** - resets input and all displayed state

### API Endpoints Added
```
GET /api/gaz-suggest?q=<prefix>&limit=10
GET /api/gaz-similar?gaz_id=<id>&limit=10
```

---

## 9. Similarity Granularity Problem

### Issue
The "Similar (env)" feature for gazetteer places uses basin cluster membership. However:

- 190,000 basins ÷ 20 clusters = ~9,500 basins per cluster
- With 97k gaz places, each cluster contains thousands of places
- Showing 10 random places from thousands is not meaningful "similarity"

### Current Behavior
Returns random places from basins in the same cluster. UI labels this as "places in basins of type: [cluster label]" to set expectations.

### Options to Fix

1. **Same-basin matching** - find places in the identical basin (hyper-local)
2. **PCA-space distance** - use actual basin PCA coordinates (`output/basin08_pca_coords.npy`) to find nearest basins by Euclidean distance
3. **Finer clustering** - re-run with k=100-200 instead of k=20
4. **Hybrid** - same basin first, then nearby basins by PCA distance

### Recommendation
Option 2 (PCA distance) provides continuous similarity. Requires:
- New table: `basin08_pca (hybas_id, pca_1, pca_2, ..., pca_n)`
- Load from numpy file (one-time ETL)
- Query: `ORDER BY euclidean_distance(source_pca, target_pca) LIMIT N`

### Status
**RESOLVED** - Implemented Option 2 (PCA distance) using pgvector.

---

## 10. PCA Vector Similarity (pgvector)

### Implementation
Loaded basin PCA coordinates into PostgreSQL using the pgvector extension for fast similarity search.

**Script:** `scripts/load_basin_pca_vectors.py`

**Table:**
```sql
CREATE TABLE basin08_pca (
    basin_id INTEGER PRIMARY KEY,
    hybas_id BIGINT NOT NULL,
    pca vector(50)  -- first 50 of 150 components (~72% variance)
);
CREATE INDEX basin08_pca_idx ON basin08_pca
    USING ivfflat (pca vector_l2_ops) WITH (lists = 100);
```

**Storage:** ~50 MB for 190,675 rows × 50 dimensions

### Updated API
`/api/gaz-similar` now uses vector distance:

```sql
WITH similar_basins AS (
    SELECT p2.basin_id, p1.pca <-> p2.pca AS distance
    FROM basin08_pca p1, basin08_pca p2
    WHERE p1.basin_id = <source_basin>
    ORDER BY p1.pca <-> p2.pca
    LIMIT 500
)
SELECT g.*, sb.distance
FROM gaz.edop_gaz g
JOIN similar_basins sb ON sb.basin_id = g.basin_id
ORDER BY distance LIMIT 10;
```

### Results
Example: Glasgow → similar places by environmental signature:
- Damn(on)ioi (Scotland): dist 0.19
- Glasgow Bridge (Scotland): dist 0.37
- Coleshill (England): dist 0.58
- Drumanagh (Ireland): dist 0.61
- Isonzo (Italy): dist 0.65

The vector distance provides continuous, meaningful similarity rather than random selection from coarse clusters.
