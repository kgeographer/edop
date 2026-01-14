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
  - **WHG API** (default): reconcile-based search with multi-candidate map markers, country filter
  - EDOP Gazetteer: autocomplete search of 97k local places, Similar (env) button
  - Coordinates: manual lon/lat entry
- Basins: list 20 clusters of 190k sub-basins; display on map & list WH cities contained
- WH Cities: dropdown selection returns sig, options for similar cities (env + semantic)
- WH Sites: dropdown selection returns sig, options for similar sites

**Key tables:**
- `basin08` — 190k sub-basins with environmental fields and cluster_id
- `basin08_pca` — pgvector table with 50-dim PCA vectors for similarity search
- `gaz.edop_gaz` — 97k places with basin_id FK for environmental lookups
- `gaz.wh_cities` — 258 World Heritage cities

## Key Findings
- Environmental and text similarity are complementary (45% cluster agreement)
- 20 clusters too coarse for gazetteer similarity → solved with pgvector PCA distance
- pgvector enables continuous similarity ranking instead of discrete cluster buckets

## Key Files
- `docs/edop_database_schema.md` — comprehensive schema reference
- `docs/session_log_*.md` — detailed work per day
- `scripts/load_basin_pca_vectors.py` — loads PCA coords into pgvector
- `misc/dump_for_deploy.sh` — database export for deployment
- `misc/restore_on_droplet.sh` — database restore on server

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
