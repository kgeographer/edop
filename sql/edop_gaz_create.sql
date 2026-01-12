-- =============================================================================
-- STEP 1: Run this in edop database
-- Creates gaz.edop_gaz and populates from local sources
-- =============================================================================

DROP TABLE IF EXISTS gaz.edop_gaz;

CREATE TABLE gaz.edop_gaz (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT NOT NULL,
    ccodes TEXT[],
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    geom GEOMETRY(Point, 4326)
);

-- 1. Insert DK Atlas (6,566)
INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
SELECT
    'dkatlas',
    id::text,
    title,
    CASE WHEN ccodes IS NOT NULL AND ccodes != ''
         THEN string_to_array(replace(ccodes, ' ', ''), ',')
         ELSE NULL END,
    lon,
    lat,
    CASE WHEN geom IS NOT NULL THEN ST_Centroid(geom)
         ELSE ST_SetSRID(ST_MakePoint(lon, lat), 4326) END
FROM gaz.dkatlas_geom
WHERE title IS NOT NULL;

-- 2. Insert Pleiades (34,315)
INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
SELECT
    'pleiades',
    id::text,
    title,
    NULL,
    representative_longitude,
    representative_latitude,
    CASE
        WHEN geom IS NOT NULL THEN ST_Centroid(geom)
        WHEN representative_longitude IS NOT NULL
             THEN ST_SetSRID(ST_MakePoint(representative_longitude, representative_latitude), 4326)
        ELSE NULL
    END
FROM gaz.pleiades
WHERE title IS NOT NULL
  AND (geom IS NOT NULL OR representative_longitude IS NOT NULL);

-- 3. Insert WH cities (258) - with dedup check against existing entries (138 inserted)
INSERT INTO gaz.edop_gaz (source, source_id, title, ccodes, lon, lat, geom)
SELECT
    'wh_cities',
    wc.id::text,
    wc.title,
    ARRAY[wc.ccode],
    ST_X(ST_Centroid(wc.geom)),
    ST_Y(ST_Centroid(wc.geom)),
    ST_Centroid(wc.geom)
FROM gaz.wh_cities wc
WHERE wc.title IS NOT NULL
  AND wc.geom IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM gaz.edop_gaz eg
      WHERE ST_DWithin(eg.geom::geography, ST_Centroid(wc.geom)::geography, 1000)
  );

-- Check counts before WHG import
SELECT source, COUNT(*) as count FROM gaz.edop_gaz GROUP BY source ORDER BY count DESC;
SELECT COUNT(*) as total_before_whg FROM gaz.edop_gaz;


