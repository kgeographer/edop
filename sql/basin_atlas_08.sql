-- basinATLAS
select count(*) from basin08 b; -- 190675
-- Count columns for table basins08 in the current schema
SELECT COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'basin08'
  AND table_schema = current_schema();

------------================------------================
-- ============================================================
-- Step 1: Verify spatial index + table stats
-- (Adjust schema/table/geom column names if needed)
-- Assumes: public."Basin08" and geometry column named "geom"
-- ============================================================

-- 1A) Confirm geometry column metadata (type + SRID)
-- x/y, 4326, multipolygon
SELECT
  f_table_schema,
  f_table_name,
  f_geometry_column,
  coord_dimension,
  srid,
  type
FROM public.geometry_columns
WHERE f_table_schema = 'public'
  AND f_table_name   = 'basin08';

-- 1B) List all indexes on Basin08 (look for a GiST index on geom)
SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename  = 'basin08'
ORDER BY indexname;
-- basin08_pkey; sidx_basin08_geom (gist)


-- Optional, heavier (do when you can tolerate a lock + time):
-- VACUUM (ANALYZE) public."Basin08";



-- ============================================================
-- Step 2: Geometry complexity diagnostics (in-database profiling)
-- ============================================================

-- 2A) Row count + basic geometry type distribution
SELECT
  COUNT(*) AS n_rows,
  ST_SRID(geom) AS srid,
  GeometryType(geom) AS geom_type,
  COUNT(*) AS n
FROM public."basin08"
GROUP BY ST_SRID(geom), GeometryType(geom)
ORDER BY n DESC;
-- all 4326, 190675 rows

-- 2B) Validity check counts (invalid geometries can slow/derail ops)
SELECT
  ST_IsValid(geom) AS is_valid,
  COUNT(*)         AS n
FROM public."basin08"
GROUP BY ST_IsValid(geom)
ORDER BY is_valid;

--|-----true------|
--|false	3326|
--|true 187349|


-- 2C) Point/part complexity distribution (vertex counts + multipolygon parts)
-- Note: ST_NPoints counts vertices; ST_NumGeometries counts parts in multi-*
-- 2C-1
SELECT
  COUNT(*) AS n,
  MIN(ST_NPoints(geom)) AS npoints_min,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ST_NPoints(geom)) AS npoints_p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY ST_NPoints(geom)) AS npoints_p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ST_NPoints(geom)) AS npoints_p99,
  MAX(ST_NPoints(geom)) AS npoints_max
FROM public."basin08";
-- n	npoints_min	npoints_p50	npoints_p90	npoints_p99	npoints_max
-- 190675	5  		158			332			575			5086

-- 2C-2
SELECT
  COUNT(*) AS n,
  MIN(ST_NumGeometries(geom)) AS nparts_min,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ST_NumGeometries(geom)) AS nparts_p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY ST_NumGeometries(geom)) AS nparts_p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ST_NumGeometries(geom)) AS nparts_p99,
  MAX(ST_NumGeometries(geom)) AS nparts_max
FROM public."basin08";
-- n	nparts_min	nparts_p50	nparts_p90	nparts_p99	nparts_max
-- 190675	1			1.0			1.0			4.0			424

-- 2D) Show the worst offenders by vertex count (inspect a handful)
-- Replace "HYBAS_ID" with your basin id column if it’s named differently
SELECT
  id,
  ST_NPoints(geom)       AS npoints,
  ST_NumGeometries(geom) AS nparts,
  ST_Area(geom::geography) / 1e6 AS area_km2
FROM public."basin08"
ORDER BY ST_NPoints(geom) DESC
LIMIT 25;

-- 2E) (Optional) How complex are polygons *relative to size* (useful for spotting over-densification)
SELECT
  id,
  ST_NPoints(geom) AS npoints,
  (ST_Area(geom::geography) / 1e6) AS area_km2,
  (ST_NPoints(geom) / NULLIF(ST_Area(geom::geography) / 1e6, 0)) AS points_per_km2
FROM public."basin08"
ORDER BY points_per_km2 DESC NULLS LAST
LIMIT 25;

-- geom Timbuktu -3.00777252,16.76618535
SELECT
  id,
  basin08.clz_cl_smj as zone,
  basin08.cls_cl_smj as strata,
  basin08.glc_cl_smj as land_cover,
  basin08.ppd_pk_sav as pop_density,
  ST_Area(geom::geography) / 1e6 AS area_km2
FROM public.basin08
WHERE ST_Contains(
  geom,
  ST_SetSRID(ST_MakePoint(-3.00777252, 16.76618535), 4326)
)
ORDER BY ST_Area(geom::geography) ASC
LIMIT 1;

-- pulling from lookups
-- Timbuktu: -3.00777252, 16.76618535
-- drop view v_basin08_basic;
CREATE OR REPLACE VIEW v_basin08_basic AS
SELECT
  b.id,
  b.geom,
  b.clz_cl_smj AS zone_id,
  z.genz_name  AS zone_name,      -- display field
  b.cls_cl_smj AS strata_id,
  s.gens_code  AS strata_code,    -- display field
  b.glc_cl_smj AS land_cover_id,
  g.glc_name   AS land_cover_name, -- display field
  b.ppd_pk_sav AS pop_density,
  b.ele_mt_smn as elev_min,
  b.ele_mt_smx as elev_max,
  b.run_mm_syr as runoff,
  b.dis_m3_pyr as discharge_yr,
  ST_Area(b.geom::geography) / 1e6 AS area_km2
FROM public.basin08 b
LEFT JOIN public.lu_clz z
  ON z.genz_id = b.clz_cl_smj
LEFT JOIN public.lu_cls s
  ON s.gens_id = b.cls_cl_smj::varchar
LEFT JOIN public.lu_glc g
  ON g.glc_id = b.glc_cl_smj::varchar
WHERE ST_Covers(
  b.geom,
  ST_SetSRID(ST_MakePoint(-3.00777252, 16.76618535), 4326)
)
ORDER BY ST_Area(b.geom::geography) ASC
LIMIT 1;

-- pass coordinates
select zone_id, zone_name, strata_id, strata_code, land_cover_id,
	land_cover_name, pop_density, elev_min, elev_max, runoff, discharge_yr, geom
FROM public.v_basin08_basic
WHERE ST_Covers(
  geom,
  ST_SetSRID(ST_MakePoint(-3.00777252, 16.76618535), 4326)
)
ORDER BY area_km2 ASC
LIMIT 1;

------------================------------================
-- temperatures are celsius x10; lowest mont, highest month
select tmp_dc_smn/10, tmp_dc_smx/10 from basin08 b limit 100;

-- climate zones
select b.clz_cl_smj from basin08 b limit 100;

-- land cover classes
select b.glc_cl_smj from basin08 b 
where glc_cl_smj = 6
limit 100;