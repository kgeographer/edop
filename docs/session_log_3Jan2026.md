# EDOP Session Log - 3 January 2026

## Objective
Develop a persistence matrix for 20 World Heritage sites with normalized numerical attributes and one-hot encoded categorical dimensions from BasinATLAS data.

## Steps Completed

### 1. Matrix Design
- Identified 27 numerical fields for normalization (elevation, temperature, discharge, etc.)
- Identified 9 categorical lookup tables for one-hot encoding (1519 total categories)
- Added 15 PNV (potential natural vegetation) share columns as continuous 0-1 values
- **Total dimensions: 1561 columns**

### 2. Database Schema Created
- `edop_norm_ranges` - global min/max for normalization (1 row, 62 values)
- `edop_wh_sites` - site metadata with basin_id foreign key (20 rows)
- `edop_matrix` - wide feature matrix (20 rows × 1565 columns)

**Files:** `sql/edop_matrix_schema.sql`, `scripts/populate_matrix.py`

### 3. PCA Analysis
- Ran PCA on standardized matrix
- 19 components extracted (max for 20 samples)
- Variance distribution: PC1=11.8%, PC2=10.6%, PC3=8.7%
- No dominant component; need 13 components for 80% variance

**Key gradients identified:**
- PC1: Temperature/terrain (warm-flat ↔ cool-mountainous)
- PC2: Hydrology/development (dry-remote ↔ wet-urbanized)
- PC3: Wetland/runoff intensity

**Files:** `scripts/pca_analysis.py`, `docs/pca_results.md`, `docs/pca_*.png`

### 4. Persistence of PCA Products
Created additional tables:
- `edop_pca_coords` - site coordinates in 19-dimensional PCA space
- `edop_pca_variance` - explained variance per component
- `edop_similarity` - pairwise Euclidean distances (380 pairs)
- `edop_clusters` - K-means cluster assignments (k=5)

**Files:** `sql/edop_pca_schema.sql`, `scripts/pca_cluster_persist.py`

### 5. Clustering Results (K=5)

| Label | Sites | Environmental Character |
|-------|-------|------------------------|
| **Temperate Lowland Heritage** | Vienna, Kyiv, Venice, Kyoto, Tallinn, Beijing, Angkor, Head-Smashed-In | Moderate temps (0.64), low elevation, highest human footprint (0.46) |
| **Subtropical/Arid Wilderness** | Iguazu, Uluru, Petra | Hot (0.80), remote, low human impact (0.12) |
| **High Altitude Continental** | Machu Picchu, Lijiang, Taos | Cool (0.60), highest elevation (0.61), low discharge |
| **Arid Heritage Crossroads** | Timbuktu, Ellora, Toledo, Göbekli Tepe, Samarkand | Hot (0.79), driest (precip 0.05), most arid |
| **Major River Floodplain** | Cahokia | Outlier: highest discharge (0.03), highest human footprint (0.76) |

### 6. Similarity Analysis
Most similar pairs:
- Vienna ↔ Kyiv (dist=3.80)
- Tallinn ↔ Venice (dist=4.49)
- Toledo ↔ Göbekli Tepe (dist=4.92)

Sites most similar to Timbuktu: Göbekli Tepe, Uluru, Beijing, Samarkand

### 7. Loadings Persistence
Stored top 50 features per component (by absolute loading value) to enable interpretation queries.

**Files:** `scripts/persist_loadings.py`

## Products in Database

| Table | Rows | Description |
|-------|------|-------------|
| edop_wh_sites | 20 | Site metadata with basin FK |
| edop_norm_ranges | 1 | Global normalization bounds |
| edop_matrix | 20 | Raw feature matrix (1565 cols) |
| edop_pca_coords | 20 | PCA coordinates (19 dims) |
| edop_pca_variance | 19 | Variance per component |
| edop_similarity | 380 | Pairwise distances |
| edop_clusters | 20 | Cluster assignments (with labels) |
| edop_pca_loadings | 950 | Top 50 loadings per component (19×50) |

## Files Created

```
sql/
  edop_matrix_schema.sql    # Feature matrix tables
  edop_pca_schema.sql       # PCA persistence tables

scripts/
  populate_matrix.py        # Populates feature matrix
  pca_analysis.py           # Initial PCA exploration
  pca_cluster_persist.py    # PCA + clustering + persistence

docs/
  pca_results.md            # PCA interpretation
  pca_variance.png          # Scree plot
  pca_sites_2d.png          # Sites in PC1-PC2 space
  pca_sites_3d.png          # Sites in PC1-PC2-PC3 space
  pca_clusters.png          # Clustered visualization
```

## Example Queries Now Possible

```sql
-- Sites most similar to a given site
SELECT b.name_en, ROUND(distance::numeric, 2)
FROM edop_similarity s
JOIN edop_wh_sites a ON a.site_id = s.site_a
JOIN edop_wh_sites b ON b.site_id = s.site_b
WHERE a.name_en = 'Timbuktu'
ORDER BY distance LIMIT 5;

-- All sites in a cluster
SELECT s.name_en, c.cluster_id
FROM edop_clusters c
JOIN edop_wh_sites s ON s.site_id = c.site_id
WHERE c.cluster_id = 4;

-- PCA coordinates for visualization
SELECT s.name_en, p.pc1, p.pc2, p.pc3
FROM edop_pca_coords p
JOIN edop_wh_sites s ON s.site_id = p.site_id;
```

## Next Steps (potential)
- Assign interpretive labels to clusters based on centroid analysis
- Extend to full 1200+ WH site catalog
- Add text embeddings of site descriptions for multimodal similarity
- Build API endpoint for "sites like X" queries
