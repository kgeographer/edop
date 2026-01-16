 Session Seed: EDOP WHC Cities UI Polish (8 Jan 2026 continuation)

  Context

  EDOP project - Environmental Dimensions of Place. We've scaled from 20 pilot World Heritage Sites to 258 World Heritage Cities, completing both environmental and semantic analysis pipelines.

  Current State

  Read docs/session_log_8Jan2026.md for full details. Key points:

  Database (whc_ tables):*
  - wh_cities — 258 cities with geom, basin_id
  - whc_matrix — 254 environmental signatures (893 features)
  - whc_similarity — 32,131 pairwise env distances
  - whc_clusters — k=10 environmental clusters
  - whc_band_summaries — 1,032 LLM summaries
  - whc_band_similarity — 12,170 text similarity pairs
  - whc_band_clusters — k=8 text clusters (5 bands)

  API Endpoints (added today):
  - GET /api/whc-cities — 258 cities with coordinates, clusters
  - GET /api/whc-similar?city_id=X — environmental similarity
  - GET /api/whc-similar-text?city_id=X&band=composite — text similarity

  UI (added today):
  - New "WHC Cities" tab in app/templates/index.html (lines 83-103)
  - Dropdown grouped by UNESCO region
  - Dual similarity buttons + cluster badges
  - ~280 lines of JS added (functions: whcLoadCities, whcSelectById, whcShowSimilarEnv, whcShowSimilarText, renderWhcSimilarSites)

  Status

  ~80% functional. User tested and confirmed basic flow works. Needs polish.

  Remaining Work

  - UI polish and edge case testing
  - Any bugs discovered during testing
  - Cross-analysis: env clusters vs text clusters (future)

  Key Files

  - app/templates/index.html — main UI
  - app/api/routes.py — API endpoints (WHC at lines 374-555)
  - docs/session_log_8Jan2026.md — detailed log of today's work
  - docs/session_log_7Jan2026.md — text corpus scaling work

  User Preferences

  - Confirm writes before making them
  - Use whc_ prefix for 258-city tables (not edop_)
  - Session logs in docs/session_log_*Jan2026.md