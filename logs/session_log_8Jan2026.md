# Session Log: 8 January 2026

## Objective
Complete the environmental analysis pipeline for 258 World Heritage Cities by merging WHG coordinate data into `wh_cities`, assigning basin_ids, generating environmental signatures, and running PCA/clustering.

---

## 1. Updated `wh_cities` Table with Geometry and Basin IDs

**Script:** `scripts/update_wh_cities_geom.py`

### Data Merge Process
Joined three data sources to populate geometry:
```
whc_258_geom.tsv (WHG_internal_id → lon, lat)
    ↓ join via
whc_id_lookup.html (WHG_internal_id → whc_id)
    ↓ parse whc_id to integer
wh_cities.id
```

### Schema Changes
```sql
ALTER TABLE wh_cities ADD COLUMN geom geometry(Point, 4326);
ALTER TABLE wh_cities ADD COLUMN basin_id INTEGER;
```

### Results
| Metric | Count |
|--------|-------|
| Total cities | 258 |
| Geometries added | 258 |
| Basin IDs assigned | 254 |
| Missing basin (islands) | 4 |

**Cities without basin_id** (small islands outside HydroATLAS coverage):
- Angra do Heroísmo, Portugal (Azores)
- Cidade Velha, Cape Verde
- Levuka, Fiji
- St. George's, Bermuda

---

## 2. Created WHC Environmental Matrix Schema

**SQL:** `sql/whc_matrix_schema.sql`

Created parallel tables to the pilot (edop_*) schema:
- `whc_matrix` — 893 feature columns (27 numerical + 15 PNV + 847 tec categorical)
- `whc_pca_coords` — PCA coordinates (50 components)
- `whc_pca_variance` — Explained variance per component
- `whc_similarity` — Pairwise environmental similarity
- `whc_clusters` — K-means cluster assignments

---

## 3. Populated Environmental Matrix

**Script:** `scripts/populate_whc_matrix.py`

### Process
1. Load 254 cities with basin_id from `wh_cities`
2. Query basin08 for each city's basin environmental data
3. Normalize using existing `edop_norm_ranges` (global min/max)
4. Insert into `whc_matrix`

### Results
```
254 cities × 893 features
```

**Sample normalized values:**
| City | Country | n_temp_yr | n_precip_yr | n_elev_min |
|------|---------|-----------|-------------|------------|
| Agadez | Niger | 0.932 | 0.014 | 0.176 |
| Dakar | Senegal | 0.892 | 0.057 | 0.102 |
| Harar Jugol | Ethiopia | 0.795 | 0.083 | 0.325 |
| Timbuktu | Mali | 0.937 | 0.012 | 0.103 |

---

## 4. PCA and K-means Clustering

**Script:** `scripts/whc_pca_cluster.py`

### Configuration
- PCA: 50 components (max)
- K-means: k=10 clusters
- Similarity: Top 20 PCA components for distance calculation

### Variance Explained
```
  PC    Variance    Cumulative
  --    --------    ----------
   1      4.29%       4.29%
   2      3.60%       7.88%
   3      3.21%      11.10%
   4      3.09%      14.19%
   5      2.34%      16.53%
  ...
  10      1.46%      24.35%
```

With 893 features, variance is more distributed than the 20-site pilot. ~50 components needed for 80% variance.

### Environmental Clusters

| Cluster | Size | Profile | Example Cities |
|---------|------|---------|----------------|
| 1 | 49 | Mediterranean/dry temperate | Fez, Algiers, Rome, Aleppo, Jerusalem |
| 2 | 21 | Arid/desert | Timbuktu, Khiva, Damascus, Marrakesh |
| 3 | 15 | Northern Europe/cold | Stockholm, Tallinn, Riga, St. Petersburg |
| 4 | 22 | High altitude/continental | Cusco, Lijiang, Quito, Potosí, Sanaa |
| 5 | 22 | Tropical/warm wet-dry | Zanzibar, Mombasa, Dakar, Harar, Jaipur |
| 6 | 55 | Central Europe temperate | Vienna, Prague, Bruges, Salzburg, Bern |
| 7 | 4 | Major river floodplains | Cairo, Luang Prabang, Pyay, Bolgar |
| 8 | 39 | East Asia monsoon | Seoul, Kyoto, Nara, Suzhou, Hanoi |
| 9 | 26 | Tropical wet | Singapore, Malacca, Galle, Hội An |
| 10 | 1 | Outlier (fjord/extreme precip) | Bergen |

### Similarity Examples

**Most similar pairs:**
| City 1 | City 2 | Distance | Notes |
|--------|--------|----------|-------|
| Biertan | Sighișoara | 0.00 | Same basin, Romania |
| Split | Trogir | 0.00 | Same basin, Croatia |
| Amsterdam | Beemster | 0.00 | Same basin, Netherlands |
| Lima | Rimac | 0.00 | Same basin, Peru |

**Cities most similar to Timbuktu (environmental):**
1. Khiva, Uzbekistan (dist=4.61)
2. Zabid, Yemen (dist=5.52)
3. Damascus, Syria (dist=5.90)
4. Erbil, Iraq (dist=6.13)
5. Aktau, Kazakhstan (dist=6.45)

All arid zone cities — clustering captures climate-environment relationships well.

---

## Persisted Data Summary

| Table | Rows | Description |
|-------|------|-------------|
| wh_cities | 258 | + geom, basin_id columns |
| whc_matrix | 254 | Environmental feature vectors |
| whc_pca_coords | 254 | 50 PCA components per city |
| whc_pca_variance | 50 | Explained variance |
| whc_similarity | 32,131 | Pairwise distances (upper triangle) |
| whc_clusters | 254 | Cluster assignments |

---

## Files Created

```
scripts/
├── update_wh_cities_geom.py    # Merge geometry + assign basin_id
├── populate_whc_matrix.py      # Environmental matrix population
└── whc_pca_cluster.py          # PCA + clustering + similarity

sql/
└── whc_matrix_schema.sql       # WHC environmental analysis tables

output/corpus_258/
└── env_clusters.png            # Cluster visualization (PC1 vs PC2)
```

---

## 5. Persisted Wiki/Semantic Data

**Schema:** `sql/whc_band_schema.sql`
**Script:** `scripts/populate_whc_band.py`

### Tables Created

| Table | Rows | Description |
|-------|------|-------------|
| whc_band_summaries | 1,032 | LLM-generated summaries (258 cities × 4 bands) |
| whc_band_clusters | 1,217 | K-means cluster assignments (5 bands incl. composite) |
| whc_band_similarity | 12,170 | Top-10 similar cities per city per band |
| whc_band_metadata | 1 | Model config (text-embedding-3-small, k=8) |

### Data Sources

```
band_summaries.json → whc_band_summaries
band_embeddings.json → whc_band_clusters, whc_band_similarity, whc_band_metadata
```

Note: Raw embeddings (1536-dim vectors) were not persisted to JSON during generation to save space. Tables store clusters and similarity scores only.

### Sample Queries

**Cities most similar to Timbuktu (composite text embedding):**
| City | Country | Similarity |
|------|---------|------------|
| Agadez | Niger | 0.708 |
| Dakar | Senegal | 0.695 |
| Saint-Louis | Senegal | 0.669 |
| Marrakesh | Morocco | 0.658 |
| Tétouan | Morocco | 0.654 |

**Composite cluster distribution:**
| Cluster | Cities |
|---------|--------|
| 0 | 50 |
| 1 | 26 |
| 2 | 52 |
| 3 | 26 |
| 4 | 18 |
| 5 | 16 |
| 6 | 31 |
| 7 | 38 |

---

## Persisted Data Summary (Complete)

| Table | Rows | Description |
|-------|------|-------------|
| wh_cities | 258 | + geom, basin_id columns |
| whc_matrix | 254 | Environmental feature vectors |
| whc_pca_coords | 254 | 50 PCA components per city |
| whc_pca_variance | 50 | Explained variance |
| whc_similarity | 32,131 | Pairwise environmental distances |
| whc_clusters | 254 | Environmental cluster assignments |
| whc_band_summaries | 1,032 | Wikipedia band summaries |
| whc_band_clusters | 1,217 | Text embedding clusters |
| whc_band_similarity | 12,170 | Text similarity (top-10 per city) |
| whc_band_metadata | 1 | Embedding model config |

---

## Files Created

```
scripts/
├── update_wh_cities_geom.py    # Merge geometry + assign basin_id
├── populate_whc_matrix.py      # Environmental matrix population
├── whc_pca_cluster.py          # PCA + clustering + similarity
└── populate_whc_band.py        # Wiki/semantic data to database

sql/
├── whc_matrix_schema.sql       # WHC environmental analysis tables
└── whc_band_schema.sql         # WHC text/semantic tables

output/corpus_258/
└── env_clusters.png            # Cluster visualization (PC1 vs PC2)
```

---

## 6. WHC Cities UI Integration

### New API Endpoints (`app/api/routes.py`)

| Endpoint | Description |
|----------|-------------|
| `GET /api/whc-cities` | Returns 258 cities with coordinates, env_cluster, text_cluster |
| `GET /api/whc-similar?city_id=X&limit=N` | Environmental similarity (PCA distance) |
| `GET /api/whc-similar-text?city_id=X&band=composite&limit=N` | Text similarity (cosine) |

### UI Changes (`app/templates/index.html`)

- Renamed existing "World Heritage" tab → "WH Pilot" (20 sites)
- Added new **"WHC Cities"** tab (default active):
  - Searchable dropdown of 258 cities grouped by UNESCO region
  - Shows combined cluster badges (Env: X | Text: Y)
  - "Similar (env)" and "Similar (semantic)" buttons
  - Results display below map with color-coded markers

### Validation

**Timbuktu similarity comparison:**
| Type | Top 5 Similar Cities |
|------|---------------------|
| Environmental | Agadez, Khiva, Zabid, Damascus, Erbil (all arid/desert) |
| Semantic | Agadez, Dakar, Saint-Louis, Marrakesh, Tétouan (West/North African) |

Environmental similarity groups by climate; semantic similarity groups by cultural/historical connections.

### Status
~80% functional. Known issues to address:
- Minor UI polish needed
- Testing across all 258 cities

---

## Files Created/Modified

```
app/api/routes.py              # +3 new endpoints (whc-cities, whc-similar, whc-similar-text)
app/templates/index.html       # +WHC Cities tab, ~280 lines of JS

scripts/
├── update_wh_cities_geom.py   # Merge geometry + assign basin_id
├── populate_whc_matrix.py     # Environmental matrix population
├── whc_pca_cluster.py         # PCA + clustering + similarity
└── populate_whc_band.py       # Wiki/semantic data to database

sql/
├── whc_matrix_schema.sql      # WHC environmental analysis tables
└── whc_band_schema.sql        # WHC text/semantic tables
```

---

## Next Steps

- [ ] UI polish and testing
- [ ] Cross-analysis: environmental clusters vs. text embedding clusters
- [ ] Add remaining categorical columns to whc_matrix (fec, cls, glc, etc.)
