-- =============================================================================
-- STEP 2: Run this in whgv3beta database
-- Exports WHG S-class places for import into edop gaz.edop_gaz
-- =============================================================================

-- Option A: Export to CSV (then COPY into edop)
-- Run in psql or DBeaver, save results as CSV

COPY (
    SELECT
        'whg' as source,
        p.id::text as source_id,
        p.title,
        array_to_string(p.ccodes, ',') as ccodes_csv,  -- CSV-friendly format
        ST_X(ST_Centroid(pg.geom)) as lon,
        ST_Y(ST_Centroid(pg.geom)) as lat
    FROM places p
    JOIN place_geom pg ON pg.place_id = p.id
    WHERE 'S' = ANY(p.fclasses)
      AND p.title IS NOT NULL
      AND pg.geom IS NOT NULL
    ORDER BY p.title
) TO '/tmp/whg_s_class.csv' WITH CSV HEADER;

-- Expected: ~62,000 rows actual 59062


-- =============================================================================
-- Option B: If COPY TO file doesn't work, run this SELECT and export from DBeaver
-- =============================================================================

SELECT
    'whg' as source,
    p.id::text as source_id,
    p.title,
    array_to_string(p.ccodes, ',') as ccodes_csv,
    ST_X(ST_Centroid(pg.geom)) as lon,
    ST_Y(ST_Centroid(pg.geom)) as lat
FROM places p
JOIN place_geom pg ON pg.place_id = p.id
WHERE 'S' = ANY(p.fclasses)
  AND p.title IS NOT NULL
  AND pg.geom IS NOT NULL
ORDER BY p.title;
