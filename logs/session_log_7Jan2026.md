# Session Log: 7 January 2026

## Objective
Scale up the Wikipedia text corpus pipeline from 20 pilot World Heritage sites to 258 World Heritage Cities (WHC).
`
## Key Decisions

### Data Source
- Used `wh_cities` database table (258 rows) as source
- Included `region`, `country`, and `ccode` fields for categorical faceting
- Note: WHC cities are not official UNESCO products—they're cities associated with World Heritage sites, curated from external sources

### Output Strategy
- **File-only output** to `output/corpus_258/` (no database tables)
- Rationale: `wh_cities` lacks lon/lat coordinates needed for environmental analysis
- Database schema deferred until WHG reconciliation provides coordinates

### Technical Choices
- Increased k-means clusters from 5 (pilot) to 8 (full corpus)
- Store top-10 similar cities per city (not full 258×258 matrix)
- Checkpoint every 50 cities during summarization

---

## Pipeline Execution

### 1. Harvest Wikipedia Sections
**Script:** `scripts/corpus/harvest_whc.py`

```
python scripts/corpus/harvest_whc.py
```

**Results:**
- 258/258 cities processed
- 7,757 total sections harvested
- Average 3.7/4 bands present per city
- 1 city (Safranbolu) with 0/4 bands mapped

**Outputs:**
- `output/corpus_258/wiki_sections.json`
- `output/corpus_258/coverage_report.tsv`

**Notes:**
- URL-decoded Wikipedia slugs handled correctly (e.g., `%C4%8Cesk%C3%BD_Krumlov` → `Český_Krumlov`)
- Band mapping reused from pilot: `output/corpus/band_mapping_draft.json`

---

### 2. LLM Summarization
**Script:** `scripts/corpus/summarize_whc.py`

```
python scripts/corpus/summarize_whc.py
```

**Results:**
- 258 cities × 4 bands processed
- ~45 minutes runtime

**Token Usage:**
- Input: 1,316,697 tokens
- Output: 329,045 tokens
- Estimated cost: **$8.90**

**Band Coverage:**
| Band        | Cities |
|-------------|--------|
| history     | 257/258 |
| environment | 254/258 |
| culture     | 256/258 |
| modern      | 254/258 |

**Outputs:**
- `output/corpus_258/band_summaries.json`
- Checkpoints at 50, 100, 150, 200 cities

---

### 3. Generate Embeddings
**Script:** `scripts/corpus/embed_whc.py`

```
python scripts/corpus/embed_whc.py
```

**Configuration:**
- Model: `text-embedding-3-small` (1536 dimensions)
- Clusters: k=8

**Outputs:**
- `output/corpus_258/band_embeddings.json`
  - Per-band embeddings (history, environment, culture, modern)
  - Composite embedding (all bands concatenated as text, then embedded)
  - Top-10 similar cities per city per band
  - Cluster assignments and distances to centroids

---

## Clustering Results (Composite)

| Cluster | Size | Character | Example Cities |
|---------|------|-----------|----------------|
| 0 | 27 | Northern/Central European | Regensburg, Lübeck, Stralsund, Riga |
| 1 | 30 | Mediterranean/Southern European | Évora, Urbino, Ferrara, Verona |
| 2 | 43 | Hispanic World | Lima, Cusco, Oaxaca, Cartagena, Havana |
| 3 | 25 | South/Southeast Asian | Ahmedabad, Jaipur, Luang Prabang |
| 4 | 21 | Lusophone + Korean | Macau, Melaka, Gyeongju, Galle |
| 5 | 34 | Central/Eastern European | Prague, Kraków, Vilnius, Lviv |
| 6 | 42 | Islamic/Arab/North African | Fez, Marrakesh, Sana'a, Kairouan |
| 7 | 36 | Mixed/Colonial heritage | Various |

### Cluster × Region Cross-tab
```
Region                    C0  C1  C2  C3  C4  C5  C6  C7
---------------------------------------------------------
Arab States                -   -   -   -   -   -  14   3
Asia and the Pacific       2   -   2  25  13   1   6  17
Europe and North America  25  29   3   -   5  33   -  13
Latin America & Caribbean  -   1  38   -   3   -   -   3
```

---

## Most Similar City Pairs (Composite)

| City 1 | City 2 | Similarity | Notes |
|--------|--------|------------|-------|
| Istanbul | Istanbul | 0.976 | Duplicate entry (2 UNESCO regions) |
| Cuenca | Cuenca | 0.870 | Duplicate entry (Ecuador vs Spain) |
| Kutná Hora | Český Krumlov | 0.867 | Both Czech Republic |
| Quedlinburg | Goslar | 0.862 | Both German medieval towns |
| Bamberg | Regensburg | 0.861 | Both Bavarian heritage cities |
| Stralsund | Wismar | 0.858 | Both Hanseatic, same UNESCO inscription |
| Arequipa | Cusco | 0.855 | Both Peruvian colonial |
| Guanajuato | Zacatecas | 0.852 | Both Mexican silver cities |
| Córdoba | Úbeda | 0.851 | Both Andalusian |
| Évora | Angra do Heroísmo | 0.849 | Both Portuguese |

**Finding:** High similarity scores reflect same-country clusters and cross-regional linguistic/cultural ties (Spanish colonial, Hanseatic League, Portuguese empire).

---

## Embedding Methodology Note

The **composite** embedding uses **text concatenation before embedding**:

```python
def get_composite_text(city: dict) -> str | None:
    parts = []
    for band in BANDS:
        text = get_text_for_embedding(city, band)
        if text:
            parts.append(f"[{band.upper()}]\n{text}")
    return "\n\n".join(parts) if parts else None
```

This concatenates all band summaries with headers (`[HISTORY]`, `[ENVIRONMENT]`, etc.) into ~800-1200 words, then generates a single 1536-dim embedding. This allows the model to capture cross-band relationships rather than treating bands independently.

---

## Files Created

```
output/corpus_258/
├── wiki_sections.json          # 7,757 sections with band mappings
├── coverage_report.tsv         # Per-city band coverage statistics
├── band_summaries.json         # 258 cities × 4 band summaries
├── band_summaries_checkpoint_50.json
├── band_summaries_checkpoint_100.json
├── band_summaries_checkpoint_150.json
├── band_summaries_checkpoint_200.json
└── band_embeddings.json        # Embeddings, clusters, similarities

scripts/corpus/
├── harvest_whc.py              # Wikipedia harvesting for WHC
├── summarize_whc.py            # Claude API summarization
└── embed_whc.py                # OpenAI embeddings (file-only)
```

---

## Known Issues

1. **Istanbul/Cuenca duplicates**: These cities appear twice in `wh_cities` (listed under different UNESCO regions), causing high "self-similarity" scores. Data artifact, not a bug.

2. **Safranbolu 0/4 bands**: Wikipedia sections didn't match any band patterns. Minor edge case.

---

## WHG Reconciliation (Late 7 Jan)

Coordinates were obtained via WHG reconciliation:

1. **LP-TSV upload**: Created `app/data/wh_cities_for-whg.tsv` with `whc_001` style IDs
2. **WHG reconciliation**: Matched 258/258 cities in WHG
3. **Geometry export**: Downloaded to `app/data/whc_258_geom.xlsx` (WHG internal IDs + coordinates)
4. **ID lookup scrape**: Extracted `app/data/whc_id_lookup.html` mapping WHG IDs → whc_ids

**Issue**: WHG download omits the upload IDs, requiring join via:
```
whc_258_geom.xlsx (WHG_id → coordinates)
    ↓
whc_id_lookup.html (WHG_id → whc_id)
    ↓
wh_cities.id (parsed from whc_id)
```

**Files created**:
- `app/data/whc_258_geom.tsv` — 258 cities with id, title, lon, lat, geowkt, ccodes
- `app/data/whc_id_lookup.html` — WHG ID to whc_id mapping

---

## Next Steps

- [x] WHG reconciliation to add coordinates to `wh_cities` — **DONE** (see above)
- [ ] Merge geometry data into `wh_cities` table
- [ ] Environmental signature generation for 258 cities
- [ ] Database schema for WHC corpus
- [ ] Cross-analysis: text similarity vs. environmental similarity
