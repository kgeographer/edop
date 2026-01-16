# Session Log: 6 January 2026

## Overview
Built Wikipedia text corpus pipeline for EDOP: harvesting, semantic band mapping, LLM summarization, and embedding generation. Pilot tested on 20 World Heritage Sites.

---

## Work Completed

### 1. Corpus Architecture Design
Reviewed and refined the planned approach from `wiki_corpus_path.md`:
- **Semantic bands**: history, environment, culture, modern
- **Aggressive mapping** over manual curation — let patterns catch most content
- **LLM summarization** per band to normalize heterogeneous Wikipedia articles
- **Embeddings** for similarity analysis

### 2. Wikipedia Harvesting (`scripts/corpus/harvest_sections.py`)
- Created harvesting script using `wikipediaapi` library
- Fetched all sections for 20 pilot sites
- Output: `output/corpus/wiki_sections_pilot.json` (674 sections total)

### 3. Band Mapping
Created `output/corpus/band_mapping_draft.json` with:
- **Exact matches**: specific section titles → bands
- **Contains patterns**: substring matching (e.g., "century" → history)
- **Endswith patterns**: suffix matching (e.g., "era", "dynasty" → history)
- **Exclusions**: References, See also, Sister cities, Sports, etc.

Final coverage: **67.1%** of harvested content mapped to bands

Key mapping additions during session:
- Period-based headings ("Middle Ages", "Roman period") → history
- Religion names (Christianity, Islam, Buddhism) → culture
- Transport subsections (Rail, Airport, Buses) → modern
- "places of worship", "biological resources", "political history"

### 4. LLM Summarization (`scripts/corpus/summarize_bands.py`)
- Used Claude API (claude-sonnet-4-20250514) to summarize each band
- Band-specific prompts focusing on relevant aspects
- System prompt enforces factual, source-only summaries

**Token usage**: 121k input, 25k output (~$0.40)

**Coverage**:
| Band | Sites with content |
|------|-------------------|
| history | 20/20 |
| environment | 19/20 |
| culture | 18/20 |
| modern | 14/20 |

Output: `output/corpus/band_summaries_pilot.json`

### 5. Embedding Generation (`scripts/corpus/generate_band_embeddings.py`)
- Used OpenAI `text-embedding-3-small` (1536 dimensions)
- Generated embeddings per band + composite (all bands concatenated)
- Computed pairwise cosine similarity
- Ran k-means clustering (k=5)

**Database tables created**:
- `edop_band_embeddings` — per-site per-band embeddings
- `edop_band_similarity` — pairwise similarity by band
- `edop_band_clusters` — cluster assignments by band

### 6. Database Updates
- Added `wiki_slug` column to `edop_wh_sites`
- Populated wiki slugs for all 20 pilot sites

---

## Key Findings

### Environment vs Text Correlation
Correlation between environmental distance (PCA) and text similarity (embeddings):

| Band | Correlation | Interpretation |
|------|-------------|----------------|
| environment | -0.191 | Strongest — physical similarity → similar geographic descriptions |
| culture | -0.055 | Near zero — cultural discourse independent of environment |
| modern | -0.064 | Near zero |
| history | +0.014 | Essentially zero — historical narratives don't track environment |
| composite | -0.062 | Diluted by mixing bands |

**Insight**: The environment text band *does* track physical reality (r=-0.19), but this doesn't bleed into historical/cultural framing. Wikipedia's geography sections reflect actual environmental similarity; history sections do not.

### Text-Based Clustering (k=5)

| Cluster | Sites | Interpretation |
|---------|-------|----------------|
| 0 | Vienna, Venice, Tallinn, Kyiv, Toledo | European historic capitals — imperial/medieval urban narrative |
| 1 | Machu Picchu, Iguazu, Uluru | UNESCO natural/remote — conservation + indigenous framing |
| 2 | Kyoto, Lijiang, Samarkand, Summer Palace, Timbuktu | Trade route heritage — cultural crossroads narrative |
| 3 | Göbekli Tepe, Petra | Ancient Near East archaeology — deep antiquity discourse |
| 4 | Angkor, Cahokia, Ellora, Head-Smashed-In, Taos | Indigenous/non-Western monumental — archaeological + spiritual |

**Cluster agreement with environmental clusters**: 45% (vs 20% chance)

### Most Similar Pairs by Text
```
Composite:
  0.677  Summer Palace ↔ Old Town of Lijiang (Chinese heritage)
  0.649  Vienna ↔ Venice (European imperial cities)
  0.613  Angkor ↔ Machu Picchu (monumental archaeological)

History band specifically:
  0.492  Timbuktu ↔ Samarkand (trade route cities)
  0.465  Summer Palace ↔ Lijiang (Chinese imperial context)

Culture band specifically:
  0.605  Vienna ↔ Venice (European art/architecture)
  0.552  Toledo ↔ Taos Pueblo (unexpected — religious heritage?)
```

---

## Files Created

```
scripts/corpus/
├── harvest_sections.py        # Wikipedia section harvesting
├── summarize_bands.py         # LLM summarization per band
└── generate_band_embeddings.py # Embedding generation + clustering

output/corpus/
├── wiki_sections_pilot.json   # 674 raw sections with band assignments
├── band_summaries_pilot.json  # LLM-generated summaries (20 sites × 4 bands)
├── band_embeddings_pilot.json # Embeddings + similarity matrices
├── band_mapping_draft.json    # Mapping rules (versioned)
├── coverage_report_pilot.tsv  # Per-site band coverage stats
├── pilot_sites.tsv            # 20 sites with wiki_slugs
└── unmapped_sections.tsv      # 317 unmapped headings (for reference)
```

---

## Observations & Open Questions

1. **"Layout" mapped to history** — questionable. Site layout (Petra, Machu Picchu) is arguably architectural/culture. May need refinement.

2. **Natural sites lack culture/modern bands** — expected but affects cross-site comparisons. Iguazu and Uluru cluster together partly because they're both missing the same bands.

3. **45% cluster agreement** — enough to suggest environment and text capture overlapping but distinct signals. Not redundant, not orthogonal.

4. **Weak history-environment correlation** — supports hypothesis that historical narratives in Wikipedia don't track physical environment. But: n=20 is small, and Wikipedia reflects modern scholarly discourse, not historical environmental adaptation.

---

## Next Steps

1. **Scale to full 258 WHC cities** — harvesting + summarization pipeline ready
2. **Archaeological site selection** — LLM classification of WH Sites by type
3. **Refine mapping** — review "layout", "daily life" assignments
4. **Cross-band divergence analysis** — which sites have high history similarity but low culture similarity?
5. **UI integration** — display text similarity alongside environmental similarity

---

## Technical Notes

- Wikipedia API rate limiting: 1 request/second (built into harvester)
- Claude API: claude-sonnet-4-20250514, ~$0.02 per site for summarization
- OpenAI embeddings: text-embedding-3-small, negligible cost for 20 sites
- Database: PostgreSQL with new tables for band-specific embeddings
