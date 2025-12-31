
-- view consolidates eco847 and slug_override
CREATE OR REPLACE VIEW eco847_oneearth_final AS
WITH eco_norm AS (
  SELECT
    e.eco_id,
    e.eco_name,
    trim(regexp_replace(
      regexp_replace(
        replace(
          regexp_replace(lower(e.eco_name), 'rain\s+forests', 'rainforests', 'g'),
          '&', 'and'
        ),
        '[^a-z0-9]+', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )) AS k
  FROM eco847 e
),
one_norm AS (
  SELECT
    l.slug,
    l.title,
    trim(regexp_replace(
      regexp_replace(
        replace(
          regexp_replace(lower(l.title), 'rain\s+forests', 'rainforests', 'g'),
          '&', 'and'
        ),
        '[^a-z0-9]+', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )) AS k
  FROM oneearth_links l
),
auto AS (
  SELECT e.eco_id, o.slug AS auto_slug
  FROM eco_norm e
  LEFT JOIN one_norm o USING (k)
)
SELECT
  e.eco_id,
  e.eco_name,
  COALESCE(o.slug, a.auto_slug) AS slug,
  CASE
    WHEN o.eco_id IS NOT NULL THEN 'override'
    WHEN a.auto_slug IS NOT NULL THEN 'auto'
    ELSE 'none'
  END AS slug_source,
  biome_num,
  biome_name,
  realm
FROM eco847 e
LEFT JOIN slug_override o ON o.eco_id = e.eco_id
LEFT JOIN auto a ON a.eco_id = e.eco_id;

-- list title and slug for all 847 
SELECT
  eco_id,
  eco_name,
  slug,
  realm,
  biome_num,
  biome_name,
  slug_source
FROM eco847_oneearth_final
WHERE slug_source != 'none'
ORDER BY eco_id;

-- select distinct biomes
select distinct(biome_name) from eco847_oneearth_final;
-- 15

-- select distinct realms
select distinct(realm) from eco847_oneearth_final;
-- 9

select distinct(biome_name) from eco847;
-- 15

--  "#1" summary query
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
