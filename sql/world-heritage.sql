-- world heritage (what goes around comes around)
select * into bak.wh_cities from wh_cities;

-- CITIES
select city||', '||country from wh_cities wc
	order by country, city;
-- lp-tsv for reconciliation in WHG
select
    'whc_' || lpad(id::text, 3, '0') as id,
    city as title,
    'Organization of World Heritage Cities' as title_source,
    2026 as start,
    300008389 as aat_types,
    'https://en.wikipedia.org/' || href as title_uri,
    ccode as ccodes
from wh_cities wc order by id;	
	
select distinct country from wh_cities wc order by country;

select w.city, w.country, c.iso_a2 
	from wh_cities w
	left join ccodes c 
	on w.country = c."name";

update wh_cities wc set ccode = iso_a2 from ccodes c 
	where wc.country = c."name";

select 'https://en.wikipedia.org/' || href from wh_cities order by title;

-- SITES
--select id_no, name_en, w.short_description_en, category, w.justification_en from wh2025 w 
select id_no, name_en from wh2025 w 
where id_no in (303, 447, 1033, 668, 158, 880, 811, 
				822, 243, 394, 688, 326, 119, 274,
				379, 1572, 527, 492, 198, 603)
order by name_en;

SELECT count(*) AS rows_with_actual_newlines
FROM wh2025
WHERE name_en ~ E'[\\r\\n]';

SELECT id_no AS rows_with_literal_slashes
--SELECT name_en AS rows_with_literal_slashes
FROM wh2025
WHERE name_en LIKE '%\\n%' OR name_en LIKE '%\\r%';

UPDATE wh2025
SET name_en = replace(replace(name_en, '\r', ''), '\n', '')
WHERE id_no in (
SELECT id_no AS rows_with_literal_slashes
--SELECT name_en AS rows_with_literal_slashes
FROM wh2025
WHERE name_en LIKE '%\\n%' OR name_en LIKE '%\\r%'
);

