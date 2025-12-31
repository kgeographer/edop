SELECT DISTINCT GeometryType(geom) AS geom_type, ST_SRID(geom) AS srid
FROM eco847
LIMIT 10;
-- multipolygon 4326

CREATE INDEX CONCURRENTLY idx_eco847_geom_gist
  ON public.eco847
  USING GIST (geom);

select * from eco847 limit 10;
where lower(eco_name) like 'sahel%' limit 10;

SELECT
  (SELECT count(*) FROM eco847)          AS eco_rows,
  (SELECT count(*) FROM oneearth_links)  AS oneearth_rows;
-- 847, 844

SELECT count(*) AS exact_matches
FROM eco847 e
JOIN oneearth_links o
  ON e.eco_name = o.title;

-- missing one earth pages
SELECT e.eco_id, e.eco_name
FROM eco847 e
LEFT JOIN oneearth_links o
  ON lower(e.eco_name) = lower(o.title)
WHERE o.slug IS NULL
ORDER BY e.eco_name;

-- explain 88 missing matches
WITH
m AS (
  SELECT 1
  FROM eco847 e
  JOIN oneearth_links o
    ON lower(e.eco_name) = lower(o.title)
)
SELECT
  (SELECT count(*) FROM eco847) AS eco_rows,
  (SELECT count(*) FROM oneearth_links) AS oneearth_rows,
  (SELECT count(*) FROM m) AS ci_matches,
  (SELECT count(*) FROM eco847 e
     LEFT JOIN oneearth_links o
       ON lower(e.eco_name) = lower(o.title)
    WHERE o.slug IS NULL) AS eco_unmatched_ci,
  (SELECT count(*) FROM oneearth_links o
     LEFT JOIN eco847 e
       ON lower(e.eco_name) = lower(o.title)
    WHERE e.eco_id IS NULL) AS oneearth_unmatched_ci;

-- detail the issue
SELECT e.eco_id, e.eco_name
FROM eco847 e
LEFT JOIN oneearth_links o
  ON lower(e.eco_name) = lower(o.title)
WHERE o.slug IS NULL
ORDER BY e.eco_name
LIMIT 50;

-- 
SELECT count(*) AS matches_after_rainforest_fix
FROM eco847 e
JOIN oneearth_links o
  ON lower(
       regexp_replace(e.eco_name, '\brain\s+forests\b', 'rainforests', 'gi')
     )
   = lower(
       regexp_replace(o.title, '\brain\s+forests\b', 'rainforests', 'gi')
     );

--
SELECT count(*) AS matches_after_basic_normalization
FROM eco847 e
JOIN oneearth_links o
  ON
    trim(regexp_replace(
      lower(regexp_replace(e.eco_name, '\brain\s+forests\b', 'rainforests', 'gi')),
      '[^a-z0-9]+', ' ', 'g'
    ))
    =
    trim(regexp_replace(
      lower(regexp_replace(o.title, '\brain\s+forests\b', 'rainforests', 'gi')),
      '[^a-z0-9]+', ' ', 'g'
    ));

WITH
e AS (
  SELECT eco_id, eco_name
  FROM eco847
  WHERE eco_id = 135
),
o AS (
  SELECT slug, title
  FROM oneearth_links
  WHERE lower(title) LIKE 'admiralty islands%'
  ORDER BY title
  LIMIT 1
)
SELECT
  e.eco_id,
  e.eco_name,
  o.slug,
  o.title,
  encode(convert_to(e.eco_name, 'UTF8'), 'hex') AS eco_hex,
  encode(convert_to(o.title,   'UTF8'), 'hex') AS oneearth_hex
FROM e
CROSS JOIN o;

SELECT
  lower(regexp_replace(e.eco_name, '\brain\s+forests\b', 'rainforests', 'gi')) =
  lower(regexp_replace(o.title,    '\brain\s+forests\b', 'rainforests', 'gi')) AS matches
FROM eco847 e
JOIN oneearth_links o
  ON o.slug = 'admiralty-islands-lowland-rainforests'
WHERE e.eco_id = 135;

SELECT
  e.eco_name AS eco_raw,
  o.title    AS oneearth_raw,
  regexp_replace(e.eco_name, '\brain\s+forests\b', 'rainforests', 'gi') AS eco_rx,
  regexp_replace(o.title,    '\brain\s+forests\b', 'rainforests', 'gi') AS oneearth_rx
FROM eco847 e
JOIN oneearth_links o
  ON o.slug = 'admiralty-islands-lowland-rainforests'
WHERE e.eco_id = 135;

SELECT
  regexp_replace(lower(e.eco_name), '\brain\s+forests\b', 'rainforests', 'g') =
  regexp_replace(lower(o.title),    '\brain\s+forests\b', 'rainforests', 'g') AS matches
FROM eco847 e
JOIN oneearth_links o
  ON o.slug = 'admiralty-islands-lowland-rainforests'
WHERE e.eco_id = 135;

SELECT
  regexp_replace(lower(e.eco_name), 'rain\s+forests', 'rainforests', 'g') =
  regexp_replace(lower(o.title),    'rain\s+forests', 'rainforests', 'g') AS matches
FROM eco847 e
JOIN oneearth_links o
  ON o.slug = 'admiralty-islands-lowland-rainforests'
WHERE e.eco_id = 135;

SELECT count(*) AS matches_after_rainforest_collapse
FROM eco847 e
JOIN oneearth_links o
  ON regexp_replace(lower(e.eco_name), 'rain\s+forests', 'rainforests', 'g')
   = regexp_replace(lower(o.title),    'rain\s+forests', 'rainforests', 'g');

WITH one_norm AS (
  SELECT slug,
         regexp_replace(lower(title), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM oneearth_links
),
eco_norm AS (
  SELECT eco_id, eco_name,
         regexp_replace(lower(eco_name), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM eco847
)
SELECT e.eco_id, e.eco_name
FROM eco_norm e
LEFT JOIN one_norm o USING (k)
WHERE o.slug IS NULL
ORDER BY e.eco_name
LIMIT 30;

WITH one_norm AS (
  SELECT regexp_replace(lower(title), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM oneearth_links
),
eco_norm AS (
  SELECT regexp_replace(lower(eco_name), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM eco847
)
SELECT count(*) AS eco_unmatched_after
FROM eco_norm e
LEFT JOIN one_norm o ON e.k = o.k
WHERE o.k IS NULL;


WITH one_norm AS (
  SELECT DISTINCT
         regexp_replace(lower(title), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM oneearth_links
),
eco_norm AS (
  SELECT eco_id, eco_name,
         regexp_replace(lower(eco_name), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM eco847
)
SELECT e.eco_id, e.eco_name
FROM eco_norm e
LEFT JOIN one_norm o ON e.k = o.k
WHERE o.k IS NULL
ORDER BY e.eco_name;

WITH one_norm AS (
  SELECT DISTINCT
         regexp_replace(lower(title), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM oneearth_links
),
eco_norm AS (
  SELECT eco_id, eco_name,
         regexp_replace(lower(eco_name), 'rain\s+forests', 'rainforests', 'g') AS k
  FROM eco847
),
unmatched AS (
  SELECT e.eco_id, e.eco_name
  FROM eco_norm e
  LEFT JOIN one_norm o ON e.k = o.k
  WHERE o.k IS NULL
  ORDER BY e.eco_name
)
SELECT string_agg(format('%s\t%s', eco_id, eco_name), E'\n') AS unmatched_rows
FROM unmatched;

SELECT count(*) AS matches_after_ampersand_fix
FROM eco847 e
JOIN oneearth_links o
  ON regexp_replace(
       replace(regexp_replace(lower(e.eco_name), 'rain\s+forests', 'rainforests', 'g'), '&', 'and'),
       '\s+', ' ', 'g'
     )
   = regexp_replace(
       replace(regexp_replace(lower(o.title),    'rain\s+forests', 'rainforests', 'g'), '&', 'and'),
       '\s+', ' ', 'g'
     );

  SELECT
  (SELECT count(*) FROM eco847) AS eco_rows,
  (SELECT count(*) FROM oneearth_links) AS oneearth_rows,
  (SELECT count(*) FROM slug_override WHERE slug IS NOT NULL) AS override_with_slug,
  (SELECT count(*) FROM slug_override WHERE slug IS NULL) AS override_nulls,
  (SELECT count(*)
   FROM slug_override o
   LEFT JOIN oneearth_links l ON l.slug = o.slug
   WHERE o.slug IS NOT NULL AND l.slug IS NULL) AS override_slug_not_in_oneearth;
  
SELECT o.eco_id, o.slug
FROM slug_override o
LEFT JOIN oneearth_links l ON l.slug = o.slug
WHERE o.slug IS NOT NULL
  AND l.slug IS NULL
ORDER BY o.eco_id;


SELECT
  count(*) FILTER (WHERE slug IS NOT NULL) AS eco_with_slug,
  count(*) FILTER (WHERE slug IS NULL)     AS eco_without_slug
FROM eco847_oneearth_final;

SELECT
  (SELECT count(*) FROM eco847) AS eco_rows,
  (SELECT count(*) FROM oneearth_links) AS oneearth_rows,
  (SELECT count(*) FROM slug_override WHERE slug IS NOT NULL) AS override_with_slug,
  (SELECT count(*) FROM slug_override WHERE slug IS NULL) AS override_nulls,
  (SELECT count(*)
   FROM slug_override o
   LEFT JOIN oneearth_links l ON l.slug = o.slug
   WHERE o.slug IS NOT NULL AND l.slug IS NULL) AS override_slug_not_in_oneearth;

SELECT eco_id, slug, slug IS NULL AS is_null
FROM slug_override
ORDER BY eco_id;

UPDATE slug_override
SET slug = NULL
WHERE slug = 'NULL';


SELECT
  count(*) FILTER (WHERE slug IS NOT NULL) AS eco_with_slug,
  count(*) FILTER (WHERE slug IS NULL)     AS eco_without_slug
FROM eco847_oneearth_final;

-- culprit rows
SELECT eco_id, eco_name, slug_source
FROM eco847_oneearth_final
WHERE slug IS NULL
ORDER BY eco_id;

WITH
eco AS (
  SELECT
    eco_id,
    eco_name,
    trim(regexp_replace(
      regexp_replace(
        replace(
          regexp_replace(lower(eco_name), 'rain\s+forests', 'rainforests', 'g'),
          '&', 'and'
        ),
        '[^a-z0-9]+', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )) AS k
  FROM eco847
  WHERE eco_id = 153
),
one AS (
  SELECT
    slug,
    title,
    trim(regexp_replace(
      regexp_replace(
        replace(
          regexp_replace(lower(title), 'rain\s+forests', 'rainforests', 'g'),
          '&', 'and'
        ),
        '[^a-z0-9]+', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )) AS k
  FROM oneearth_links
)
SELECT
  eco.eco_id,
  eco.eco_name,
  eco.k AS eco_key,
  one.slug AS matched_slug,
  one.title AS matched_title,
  one.k AS one_key
FROM eco
LEFT JOIN one
  ON one.k = eco.k;

SELECT slug, title
FROM oneearth_links
WHERE lower(title) LIKE '%papuan%'
ORDER BY title;

WITH
eco AS (
  SELECT
    eco_id,
    eco_name,
    trim(regexp_replace(
      regexp_replace(
        replace(
          regexp_replace(
            replace(lower(eco_name), 'southeast', 'southeastern'),
            'rain\s+forests', 'rainforests', 'g'
          ),
          '&', 'and'
        ),
        '[^a-z0-9]+', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )) AS k
  FROM eco847
  WHERE eco_id = 153
),
one AS (
  SELECT
    slug,
    title,
    trim(regexp_replace(
      regexp_replace(
        replace(
          regexp_replace(
            replace(lower(title), 'southeast', 'southeastern'),
            'rain\s+forests', 'rainforests', 'g'
          ),
          '&', 'and'
        ),
        '[^a-z0-9]+', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )) AS k
  FROM oneearth_links
)
SELECT eco.eco_id, eco.eco_name, eco.k AS eco_key, one.slug, one.title
FROM eco
LEFT JOIN one
  ON one.k = eco.k;

SELECT
  eco_id,
  eco_name
FROM eco847_oneearth_final
WHERE slug_source = 'none'
ORDER BY eco_id;

--  #1 query
SELECT
  (SELECT count(*) FROM eco847) AS eco_rows,
  (SELECT count(*) FROM oneearth_links) AS oneearth_rows,
  (SELECT count(*) FROM slug_override WHERE slug IS NOT NULL) AS override_with_slug,
  (SELECT count(*) FROM slug_override WHERE slug IS NULL) AS override_nulls,
  (SELECT count(*)
   FROM slug_override o
   LEFT JOIN oneearth_links l ON l.slug = o.slug
   WHERE o.slug IS NOT NULL AND l.slug IS NULL) AS override_slug_not_in_oneearth;

-- ultimate check
SELECT
  count(*) FILTER (WHERE slug IS NOT NULL) AS eco_with_slug,
  count(*) FILTER (WHERE slug IS NULL)     AS eco_without_slug
FROM eco847_oneearth_final;

-- ultimate ultimate
SELECT slug, count(*) AS n, array_agg(eco_id ORDER BY eco_id) AS eco_ids
FROM eco847_oneearth_final
WHERE slug IS NOT NULL
GROUP BY slug
HAVING count(*) > 1
ORDER BY n DESC, slug;
