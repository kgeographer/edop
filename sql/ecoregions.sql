-- ecoregions stuff
--East Central Texas forests; east-central-texas-savanna-woodland
--Southeast US mixed woodlands and savannas; southeast-us-conifer-savannas
--Serengeti volcanic grasslands
--Rock and Ice
set search_path = public, gaz;
select * from gaz.matched84;
select count(*) from oneearth_links ol where slug is null;

select * from oneearth_links ol where lower(title) like '%southeast%';
-- drop table gaz.mapping;
select e.eco_id, e.eco_name, ol.title as oe_title, ol.slug as oe_slug
	into gaz.mapping
	from gaz."Ecoregions2017" e
	left join public.oneearth_links ol 
	on lower(e.eco_name) = lower(ol.title)
--	where ol.title is null
	order by eco_name; 
select * from gaz.mapping where oe_title is null order by eco_name;

-- viewing then importing matches
select gm.eco_name, m.oe_title, m.oe_slug from  
	gaz."mapping" gm join gaz.matched84 m 
	on gm.eco_name = m.eco_name;

update gaz."Ecoregions2017" set oneearth_slug = m.oe_slug
	from gaz.matched84 m
	where er.eco_name = m.eco_name;

select ol.title, ol.slug from oneearth_links ol
	order by ol.title;

-- equal: 28, 
-- lower(): 759; 88 missing
-- ilike: 759



-- Claude's FK instantiations
 -- Check what's in each column
  SELECT DISTINCT biogeorelm FROM gaz."Realm2023" LIMIT 5;
  SELECT DISTINCT biogeorelm FROM gaz."Subrealm2023" LIMIT 5;


-- Add FK columns
ALTER TABLE gaz."Ecoregions2017" ADD COLUMN bioregion varchar;
  ALTER TABLE gaz."Bioregions2023" ADD COLUMN subrealm_id int;

  -- Populate Ecoregion → Bioregion
  UPDATE gaz."Ecoregions2017" e
  SET bioregion = b.bioregions
  FROM gaz."Bioregions2023" b
  WHERE ST_Within(ST_Centroid(e.geom), b.geom); 
  -- only 842 not 847
  select eco_id, eco_name from "Ecoregions2017" e 
  	where bioregion is null; -- 5
--167	Chatham Island temperate forests
--635	Fiji tropical dry forests
--624	Kermadec Islands subtropical moist forests
--629	Samoan tropical moist forests
--783	Wrangel Island Arctic desert

  -- Populate Bioregion → Subrealm
  UPDATE gaz."Bioregions2023" b
  SET subrealm_id = s.subrealmid
  FROM gaz."Subrealm2023" s
  WHERE ST_Within(ST_Centroid(b.geom), s.geom);
select objectid, bioregions from "Bioregions2023" b 
	where subrealm_id is null; -- 4
--1	AN03
--11	AU02
--27	OC06
--38	AT18

----=====----=====----=====----=====----=====----=====----=====

select distinct biome_num, biome_name from "Ecoregions2017" e order by biome_num ; -- 15
--1	Tropical & Subtropical Moist Broadleaf Forests
--2	Tropical & Subtropical Dry Broadleaf Forests
--3	Tropical & Subtropical Coniferous Forests
--4	Temperate Broadleaf & Mixed Forests
--5	Temperate Conifer Forests
--6	Boreal Forests/Taiga
--7	Tropical & Subtropical Grasslands, Savannas & Shrublands
--8	Temperate Grasslands, Savannas & Shrublands
--9	Flooded Grasslands & Savannas
--10	Montane Grasslands & Shrublands
--11	Tundra
--11	N/A
--12	Mediterranean Forests, Woodlands & Scrub
--13	Deserts & Xeric Shrublands
--14	Mangroves

select distinct eco_biome_ from "Ecoregions2017" order by eco_biome_ ; -- 63
select distinct bioregions from "Bioregions2023" b 
	order by b.bioregions; -- 185 AN01, AN02, AN03, etc
select distinct biogeorelm from "Subrealm2023" s order by biogeorelm;

select count(*) from gaz."Ecoregions2017"; -- 847
select count(*) from gaz."Bioregions2023" b ; -- 185
select count(*) from gaz."Subrealm2023" s ; -- 53
select count(*) from gaz."Realm2023" r ; -- 14

-- Check for NULLs
SELECT COUNT(*) AS null_eco_ids
FROM gaz."Ecoregions2017"
WHERE eco_id IS NULL;

-- Check for duplicates
SELECT eco_id, COUNT(*)
FROM gaz."Ecoregions2017"
GROUP BY eco_id
HAVING COUNT(*) > 1;

ALTER TABLE gaz."Ecoregions2017"
DROP CONSTRAINT "Ecoregions2017_pkey";

ALTER TABLE gaz."Ecoregions2017"
ALTER COLUMN eco_id SET NOT null;

ALTER TABLE gaz."Ecoregions2017"
ADD CONSTRAINT "Ecoregions2017_pkey"
PRIMARY KEY (eco_id);

ALTER TABLE gaz."Ecoregions2017"
DROP COLUMN id;

ALTER TABLE gaz."Ecoregions2017"
DROP CONSTRAINT "Ecoregions2017_pkey";

ALTER TABLE gaz."Ecoregions2017"
ADD CONSTRAINT "Ecoregions2017_eco_id_pkey"
PRIMARY KEY (eco_id);