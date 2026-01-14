-- =============================================================================
-- STEP 3: Run this in edop database after exporting WHG data
-- Imports WHG S-class places from CSV into gaz.edop_gaz
-- =============================================================================
INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
  SELECT source, source_id, title,
         CASE WHEN ccodes_csv IS NOT NULL AND ccodes_csv != ''
              THEN string_to_array(ccodes_csv, ',') ELSE NULL END,
         lon, lat,
         ST_SetSRID(ST_MakePoint(lon, lat), 4326)
  FROM gaz.whg_import_temp t
  WHERE t.lon IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM gaz.edop_gaz eg
        WHERE eg.title = t.title
          AND eg.ccodes && string_to_array(t.ccodes_csv, ',')
          AND ABS(eg.lon - t.lon) < 0.15
          AND ABS(eg.lat - t.lat) < 0.15
    ); -- 56159

select count(*) from gaz.edop_gaz eg;
 CREATE INDEX IF NOT EXISTS edop_gaz_title_idx ON gaz.edop_gaz (title);

SELECT pid, state, query, wait_event_type, wait_event
  FROM pg_stat_activity
  WHERE datname = current_database()
    AND pid != pg_backend_pid();

SELECT pg_terminate_backend(68002);

CREATE INDEX IF NOT EXISTS edop_gaz_title_idx ON gaz.edop_gaz (title);


SELECT indexname, indexdef
  FROM pg_indexes
  WHERE tablename = 'edop_gaz' AND indexdef LIKE '%gist%';
-- idx_edop_gaz_geom

 SELECT 'whg_import_temp' as tbl, count(*) FROM gaz.whg_import_temp
  UNION ALL
  SELECT 'edop_gaz', count(*) FROM gaz.edop_gaz;
--whg_import_temp	59062
--edop_gaz	41019

 CREATE INDEX IF NOT EXISTS edop_gaz_geom_geog_idx
  ON gaz.edop_gaz USING GIST ((geom::geography));
 
 SELECT COUNT(*) FROM gaz.whg_import_temp; -- 59062
 SELECT COUNT(*) FROM gaz.edop_gaz; -- 41019

  -- Insert with 100m dedup (reasonable for distinct sites)
  INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
  SELECT
      source, source_id, title,
      CASE WHEN ccodes_csv IS NOT NULL AND ccodes_csv != ''
           THEN string_to_array(ccodes_csv, ',') ELSE NULL END,
      lon, lat,
      ST_SetSRID(ST_MakePoint(lon, lat), 4326)
  FROM gaz.whg_import_temp
  WHERE lon IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM gaz.edop_gaz eg
        WHERE ST_DWithin(eg.geom::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography, 100)
    );

  SELECT COUNT(*) FROM gaz.edop_gaz;  -- Should be ~93k











---- ======= BLAH BULLSHIT due to Claude limit
-- Create temp table for import
DROP TABLE IF EXISTS gaz.whg_import_temp;
CREATE TABLE gaz.whg_import_temp (
    source TEXT,
    source_id TEXT,
    title TEXT,
    ccodes_csv TEXT,
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION
);

-- Import from CSV (adjust path as needed)
-- Option A: From file
COPY gaz.whg_import_temp FROM '/tmp/whg_s_class.csv' WITH CSV HEADER;

-- Option B: If you saved from DBeaver to a different location, use that path
-- COPY gaz.whg_import_temp FROM '/path/to/your/whg_s_class.csv' WITH CSV HEADER;

select * into bak.edop_gaz from gaz.edop_gaz; -- 41019
-- Insert into edop_gaz with dedup check
INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
SELECT
    source,
    source_id,
    title,
    CASE WHEN ccodes_csv IS NOT NULL AND ccodes_csv != ''
         THEN string_to_array(ccodes_csv, ',')
         ELSE NULL END,
    lon,
    lat,
    ST_SetSRID(ST_MakePoint(lon, lat), 4326)
FROM gaz.whg_import_temp
WHERE lon IS NOT NULL AND lat IS NOT NULL
  -- Dedup: skip if place within 500m already exists
  AND NOT EXISTS (
      SELECT 1 FROM gaz.edop_gaz eg
      WHERE ST_DWithin(
          eg.geom::geography,
          ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
          50
      )
  );

select count(*) from gaz.edop_gaz;
-- Cleanup
DROP TABLE gaz.whg_import_temp;

-- troubleshooting
SELECT
  MIN(lon), MAX(lon),
  MIN(lat), MAX(lat)
FROM gaz.whg_import_temp
WHERE lon IS NOT NULL AND lat IS NOT NULL;

SELECT ST_SRID(geom) AS srid, COUNT(*)
FROM gaz.edop_gaz
GROUP BY 1
ORDER BY 2 DESC;

SELECT COUNT(*) AS sample_total
FROM gaz.whg_import_temp
TABLESAMPLE SYSTEM (2)
WHERE lon IS NOT NULL AND lat IS NOT NULL;

SELECT COUNT(*) AS within_500m
FROM gaz.whg_import_temp t
TABLESAMPLE SYSTEM (2)
WHERE t.lon IS NOT NULL
  AND t.lat IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM gaz.edop_gaz eg
    WHERE eg.lon IS NOT NULL
      AND eg.lat IS NOT NULL
      AND ST_DWithin(
            ST_SetSRID(ST_MakePoint(eg.lon, eg.lat), 4326)::geography,
            ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326)::geography,
            500
          )
  );

ALTER TABLE gaz.whg_import_temp
  ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);

UPDATE gaz.whg_import_temp
SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
WHERE geom IS NULL AND lon IS NOT NULL AND lat IS NOT NULL;

CREATE INDEX IF NOT EXISTS whg_import_temp_geom_gix
ON gaz.whg_import_temp
USING GIST (geom);

ANALYZE gaz.whg_import_temp;

-------------

-- Create indexes for autocomplete
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_edop_gaz_title_trgm ON gaz.edop_gaz USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_edop_gaz_title_lower ON gaz.edop_gaz (lower(title));
CREATE INDEX IF NOT EXISTS idx_edop_gaz_geom ON gaz.edop_gaz USING gist (geom);
CREATE INDEX IF NOT EXISTS idx_edop_gaz_source ON gaz.edop_gaz (source);

-- Final counts
SELECT source, COUNT(*) as count FROM gaz.edop_gaz GROUP BY source ORDER BY count DESC;
SELECT COUNT(*) as total FROM gaz.edop_gaz;
