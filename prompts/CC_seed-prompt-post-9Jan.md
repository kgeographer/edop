 ---
  Session Seed: EDOP Swappable City Lists (10 Jan 2026)

  Context

  EDOP project - Environmental Dimensions of Place. Read docs/session_log_9Jan2026.md for full context on recent work.

  Current State

  - 190k basins in basin08 now have cluster_id (1-20 environmental types)
  - Basins tab UI shows clusters, clicking shows WHC cities in that basin type
  - Architecture supports swappable city lists (see session log section 7, "Architecture Note")

  Current query pattern:
  SELECT c.* FROM wh_cities c
  JOIN basin08 b ON c.basin_id = b.id
  WHERE b.cluster_id = X;

  Tomorrow's Goal

  Enable swapping the city list from wh_cities (254 OWHC cities) to alternative gazetteers. User has other city lists to import.

  Key Questions to Address

  1. Schema: What columns are required? (name, country, lon/lat, optional basin_id)
  2. Import workflow: Script to load CSV/TSV → assign basin_id via spatial join
  3. UI: Dropdown or toggle to switch active city list?
  4. API: Parameterize /api/basin-clusters/{id}/cities?source=whc|gazetteer_x?

  Relevant Files

  - app/api/routes.py - basin cluster endpoints (lines 620-714)
  - app/templates/index.html - Basins tab UI
  - scripts/basin08_cluster.py - example of basin spatial operations
  - docs/session_log_9Jan2026.md - full context

  User Preferences

  - Confirm writes before making them
  - Session logs in docs/session_log_*Jan2026.md
