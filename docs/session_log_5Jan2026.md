# EDOP Session Log — 5 January 2026

## Objective
Generate text embeddings from Wikipedia descriptions and expose semantic similarity alongside environmental similarity in the UI.

---

## Steps Completed

### 1. Text Embedding Script
Created `scripts/generate_text_embeddings.py` to process Wikipedia lead text:

- Reads `app/data/wh_wikipedia_leads.tsv` (20 WH sites with lead + history text)
- Calls OpenAI `text-embedding-3-small` API (1536 dimensions)
- Computes pairwise cosine similarity matrix
- Runs k-means clustering (k=5 to match environmental)
- Persists to three new PostgreSQL tables

**Bug fixed:** CSV parser was only loading 16/20 rows due to quote handling. Some `wiki_lead` fields start with `"The...` which confused Python's csv module. Fixed by adding `quoting=csv.QUOTE_NONE` to disable quote processing for TSV.

**Tables created:**
- `edop_text_embeddings` (site_id, embedding[], model, created_at)
- `edop_text_similarity` (site_a, site_b, distance, similarity) — 380 pairwise
- `edop_text_clusters` (site_id, cluster_id, cluster_label, distance_to_centroid)

---

### 2. Cluster Analysis: Environmental vs Semantic

Compared the two clustering approaches:

**Text-based clusters show semantic coherence:**
| Cluster | Theme | Sites |
|---------|-------|-------|
| 1 | Natural parks | Iguazu, Uluru |
| 2 | Ancient/archaeological | Angkor, Cahokia, Ellora, Göbekli Tepe, Head-Smashed-In, Machu Picchu, Petra, Taos |
| 3 | European historic cities | Tallinn, Vienna, Toledo, Venice |
| 4 | Trade routes/religious centers | Kyoto, Kyiv, Samarkand, Timbuktu |
| 5 | Chinese heritage | Lijiang, Summer Palace |

**Key finding:** Only 1 of 20 sites (Iguazu) has the same nearest neighbor in both environmental and text similarity. The two dimensions are largely orthogonal — environmental captures physical geography while text captures cultural/historical narrative.

---

### 3. New API Endpoint
Added `/api/similar-text` endpoint in `app/api/routes.py`:

- Mirrors `/api/similar` but queries `edop_text_similarity` and `edop_text_clusters`
- Returns similarity score (higher = more similar) rather than distance
- Ordered by similarity descending

---

### 4. UI Updates for Dual Similarity
Modified `app/templates/index.html` to support both similarity types:

**Button changes:**
- Renamed "Most similar" → "Similar (env)" (`btn-outline-primary`)
- Added "Similar (semantic)" button (`btn-outline-info`)

**Results display:**
- Dynamic heading: "Similar Sites (Environmental)" or "Similar Sites (Semantic)"
- Dynamic description explaining the method
- Metric label adapts: "dist:" for env, "sim:" for text
- Both buttons clear previous results before populating

**JavaScript additions:**
- `fetchSimilarTextSites()` — calls `/api/similar-text`
- `whShowSimilarText()` — handler for semantic button
- Renamed `whShowSimilar()` → `whShowSimilarEnv()`
- Updated `renderSimilarSites()` to accept `similarityType` parameter
- Updated `whSelectById()` to enable both buttons

---

### 5. Git Housekeeping
- Removed `.env` from git tracking (contained API keys that triggered GitHub push protection)
- Created clean commit on `embedding` branch without secrets in history
- Pushed to origin

---

### 6. Cliopatria → Linked Places Format Transform

Created `scripts/cliopatria_to_lpf.py` to transform Seshat/Cliopatria polities GeoJSON into Linked Places Format for World Historical Gazetteer contribution.

**Source data:** `app/data/clio/cliopatria_polities_only.geojson`
- 15,690 features representing temporally-scoped polity extents
- ~6,000 years of historical polities
- Multiple features per polity (each with FromYear/ToYear extent)

**Transformation:**
- Groups features by polity name (1,618 unique → 1,547 after conflation)
- Conflates 71 parentheses-variant names (e.g., "Ottoman Empire" vs "(Ottoman Empire)") — all share identifiers
- Creates LPF Feature per polity with GeometryCollection of temporally-scoped geometries
- Each geometry includes `when.timespans` with start/end years in ISO 8601 format

**Identifier strategy:**
- 653 polities with SeshatID → `@id: https://seshat-db.com/core/polity/{id}`
- 894 polities with Wikipedia only → `@id: wp:{slug}`
- Wikipedia links added to `links[]` when SeshatID is primary

**Optimizations:**
- Reduced coordinate precision from 15 to 5 decimal places (~1 meter resolution)
- File size: 530 MB → 449 MB

**Output:** `app/data/clio/cliopatria_lpf.json` (449 MB, not committed due to size)

---

## Files Modified
- `scripts/generate_text_embeddings.py` (new)
- `scripts/cliopatria_to_lpf.py` (new)
- `app/api/routes.py` (added `/api/similar-text` endpoint)
- `app/templates/index.html` (dual similarity buttons + rendering)

## Dependencies Added
- `openai` Python package (for embeddings API)

## Environment
- Added `OPENAI_API_KEY` to `.env`

---

## Next Steps (Potential)
- Add human-readable labels to `edop_text_clusters` (currently null)
- Visualize cluster overlap/divergence in UI
- Extend to full WH corpus (~1,240 sites) via Wikidata sitelinks
