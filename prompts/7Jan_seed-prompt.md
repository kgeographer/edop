 # EDOP Session Seed — 7 Jan 2026

 ## Project Goal
 EDOP (Environmental Dimensions of Place) generates environmental signatures for historical locations using
 HydroATLAS basin data. Building a proof-of-concept for funding partners (ISHI/Pitt, KNAW/CLARIAH) demonstrating:
 - Environmental profiling at scale
 - Meaningful similarity detection (environmental + textual)
 - Clean API design for gazetteer integration

 ## Current State
 - **20 pilot World Hitage Sites** analyzed with:
   - 1,561-dimensional environmental signatures (PCA → 19 dims, k=5 clusters)
   - Wikipedia text corpus: 4 semantic bands (history, environment, culture, modern)
   - LLM-summarized band text → OpenAI embeddings → clustering
 - **Key finding**: Environmental and text similarity are complementary (45% cluster agreement, weak correlation
 except geography band r=-0.19)

 ## Key Files
 - `docs/EDOP_LOG.md` — running dev log
 - `docs/wiki_corpus_path.md` — corpus architecture plan
 - `docs/session_log_6Jan2026.md` — detailed yesterday's work
 - `output/corpus/band_summaries_pilot.json` — LLM summaries for 20 sites
 - `output/corpus/band_mapping_draft.json` — section→band mapping rules
 - `scripts/corpus/` — harvest, summarize, embed scripts

 ## Database Tables
 - `edop_wh_sites` (20 sites with wiki_slug), `edop_matrix`, `edop_similarity`, `edop_clusters`
 - `edop_band_embeddings`, `edop_band_similarity`, `edop_band_clusters`
 - `wh_cities` (258 WHC cities with wiki slugs)

 ## Next Steps
 1. Scale corpus pipeline to 258 WHC cities
 2. LLM classification of WH Sites for archaeological additions
 3. Refine band mapping (review "layout" → history assignment)
 4. UI integration of band-specific similarity

 ## Tech Stack
 FastAPI, PostgreSQL/PostGIS, Python (scikit-learn, openai, anthropic, wikipediaapi)
