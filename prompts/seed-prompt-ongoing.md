# EDOP Session Seed

## Project Goal
EDOP (Environmental Dimensions of Place) generates environmental signatures for historical locations using
HydroATLAS basin data. Building a proof-of-concept for funding partners (ISHI/Pitt, KNAW/CLARIAH) demonstrating:
- Environmental profiling at scale
- Meaningful similarity detection (environmental + textual)
- Clean API design for gazetteer integration

## Current State
- **20 pilot World Heritage Sites** analyzed with:
  - 1,565-dimensional environmental signatures (PCA → 150 dims, k=20 clusters)
  - Wikipedia text corpus: 4 semantic bands (history, environment, culture, modern)
  - LLM-summarized band text → OpenAI embeddings → clustering
- **258 World Heritage cities** analyzed similarly
- **97k gazetteer places** (`gaz.edop_gaz`) imported from WHG export with:
  - Basin assignment via spatial join
  - PCA-based environmental similarity via pgvector (`basin08_pca` table, 50 dims)

**UI tabs and pills:**
- Main tab:
  - **WHG API** (default): reconcile-based search with multi-candidate map markers, country filter, "Similar WH Cities" button
  - EDOP Gazetteer: autocomplete search of 97k local places, Similar (env) button
  - Coordinates: manual lon/lat entry
  - Pill-specific explainer text (hides when signature displayed)
- Basins: list 20 clusters of 190k sub-basins; display on map & list WH cities contained
- Ecoregions: OneEarth biogeographic hierarchy drill-down (Realms → Subrealms → Bioregions → Ecoregions); map shows child features with distinct colors, hover/click sync between map and list, OneEarth external links for bioregions
- WH Cities: dropdown selection returns sig, options for similar cities (env + semantic)
- WH Sites: dropdown selection returns sig, options for similar sites

**Key tables:**
- `basin08` — 190k sub-basins with environmental fields and cluster_id
- `basin08_pca` — pgvector table with 50-dim PCA vectors for similarity search
- `gaz.edop_gaz` — 97k places with basin_id FK for environmental lookups
- `gaz.wh_cities` — 258 World Heritage cities
- `gaz."Realm2023"` — 14 OneEarth biogeographic realms
- `gaz."Subrealm2023"` — 53 subrealms (FK to realm via biogeorelm)
- `gaz."Bioregions2023"` — 185 bioregions (FK to subrealm via subrealm_fk)
- `gaz."Ecoregions2017"` — 847 ecoregions (FK to bioregion via bioregion_fk)
- `gaz.bioregion_meta` — human-readable titles and OneEarth URL slugs for bioregions
- `public.eco_wikitext` — Wikipedia extracts for 821/847 ecoregions (96.9% coverage), FK to Ecoregions2017; includes `summary` column with LLM-generated 150-200 word summaries
- `gaz.dplace_societies` — 1,291 D-PLACE societies with basin_id and eco_id FKs (87% coverage)
- `gaz.dplace_variables` — 94 anthropological variables
- `gaz.dplace_codes` — coded values for categorical variables
- `gaz.dplace_data` — 121k observations linking societies to variable values

## Key Findings
- Environmental and text similarity are complementary (45% cluster agreement)
- 20 clusters too coarse for gazetteer similarity → solved with pgvector PCA distance
- pgvector enables continuous similarity ranking instead of discrete cluster buckets
- MediaWiki extracts API silently limits full-text to 1 page/request (`exlimit`) — must fetch individually

## Ecoregion Wikipedia Harvest (15 Jan 2026)
Wikipedia text harvested for ecoregions to enable semantic enrichment of hierarchy UI.

**Scripts:**
- `scripts/refetch_wiki_extracts.py` — fetch full extracts one title at a time
- `scripts/load_eco_wikitext.py` — load JSONL to database
- `scripts/triage_missing_ecoregions.py` — find candidates for missing ecoregions
- `scripts/fetch_reviewed_extracts.py` — fetch full/section extracts for reviewed candidates
- `scripts/summarize_ecoregion_text.py` — Claude Sonnet summarization of wiki text → 150-200 word geo/eco summaries

**Coverage:** 821/847 (96.9%). Missing 26 are mostly Antarctic tundra and newer ecoregions without Wikipedia articles.

## Ecoregion Detail UI (completed 17 Jan 2026)
When user drills down to ecoregion level, the detail card shows:
- Header: name (`.fs-6`), OneEarth button, Wikipedia button (links to wiki_url, target=_blank)
- Body: LLM summary paragraph (150-200 words, geo/eco focus)

**API:** `GET /api/eco/wikitext?eco_id=X` returns `{eco_id, eco_name, summary, wiki_url}`

**Realm ordering:** Priority realms (Subarctic America, North America, Eastern Eurasia) sorted to top with note about bioregion data completeness.

## D-PLACE Integration (18 Jan 2026)
D-PLACE (Database of Places, Language, Culture, and Environment) integrated to explore environment-culture correlations.

**Data:** 1,291 societies, 94 anthropological variables, 121k coded observations. Focal years 1850-1940.

**Spatial joins:** `basin_id`, `eco_id`, and `bioregion_id` added to `dplace_societies` via PostGIS ST_Contains (87% basin, 99% bioregion coverage).

**Scripts:**
- `scripts/dplace_env_correlations_signature.py` — correlations using EDOP signature fields by band
- `scripts/dplace_env_correlations_exploratory.py` — exploratory analysis with hand-picked basin08 variables

**Key findings (Bands A-C, excluding D):**
- Temperature → agriculture intensity (η² = 0.40): warm climates enable farming
- Runoff → domestic animal type (η² = 0.17): camelids in arid, pigs in wet
- Band D (Anthropocene markers) excluded as anachronistic for historical inquiry

**Output:** `output/dplace/correlations_signature_bands_ABC.csv`, `analysis_narrative_18Jan2026.md`

## Societies Tab UI (18-19 Jan 2026)
- Map displays 1,291 D-PLACE societies as circle markers
- Two query accordions: Subsistence (EA042) and High gods (EA034)
- Radio button filters with color-coded markers
- Results display: toggle between "Ecoregions by realm" and "Basin clusters"
- Loading spinner during initial 6-7s data fetch
- Variable description tooltips on accordion headers (from `dplace_variables.description`)

**API:** `GET /api/societies` returns societies with bioregion, subsistence, religion, cluster_id, and `variable_info` for tooltips.

## Pre-launch Fixes (19 Jan 2026)
- Fixed ecoregion geometry rendering (removed non-existent `oneearth_slug` column)
- Fixed societies map: `L.featureGroup()` for bounds, `setView([20,0],1)` for zoom
- Fixed WHG search: `mode: "fuzzy"` for prominence ranking (Denver CO now first)
- Fixed WHG popover close button: `sanitize: false`, `html: true`
- Header styling: smaller links, subtle badge

## Key Files
- `docs/edop_database_schema.md` — comprehensive schema reference
- `logs/session_log_*.md` — detailed work per day
- `prompts/seed-prompt-ongoing.md` — this file; session context for Claude
- `scripts/load_basin_pca_vectors.py` — loads PCA coords into pgvector
- `misc/dump_for_deploy.sh` — database export for deployment
- `misc/restore_on_droplet.sh` — database restore on server

## Ecoregions API Endpoints
- `GET /api/eco/realms` — list realms with subrealm counts
- `GET /api/eco/subrealms?realm=X` — list subrealms with bioregion counts
- `GET /api/eco/bioregions?subrealm_id=X` — list bioregions with ecoregion counts (includes title from bioregion_meta)
- `GET /api/eco/ecoregions?bioregion=X` — list ecoregions with biome info
- `GET /api/eco/geom?level=X&id=Y` — GeoJSON geometry for any hierarchy level
- `GET /api/eco/realms/geom` — FeatureCollection of all realm geometries
- `GET /api/eco/subrealms/geom?realm=X` — FeatureCollection of subrealms within a realm
- `GET /api/eco/bioregions/geom?subrealm_id=X` — FeatureCollection of bioregions within a subrealm
- `GET /api/eco/ecoregions/geom?bioregion=X` — FeatureCollection of ecoregions within a bioregion

## Deployment
- **Production**: edop.kgeographer.org (Digital Ocean droplet)
- **Stack**: apache2 → gunicorn:8001 → FastAPI/uvicorn
- **Database**: PostgreSQL 5432 with PostGIS, pgvector, pg_trgm
- **Service**: systemd (`/etc/systemd/system/edop.service`)
- **Environment**: `/etc/edop/edop.env` or inline in service file
- **Code**: `/var/www/edop` (git checkout main)

**Key differences local vs server:**
- Local PostgreSQL: port 5435 (non-standard)
- Server PostgreSQL: port 5432 (standard)
- Environment vars must use `PGHOST`, `PGPORT`, etc. (not `DB_HOST`, `DB_PORT`)

## Tech Stack
FastAPI, PostgreSQL/PostGIS, pgvector, Python (scikit-learn, openai, anthropic, wikipediaapi)
