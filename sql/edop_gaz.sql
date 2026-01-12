--**----**----**-- 
--**-- edop_gaz --**--
--**----**----**--


-- DK atlas 6,566
drop table dkatlas_geom;
select id, title, ccodes, names, lon, lat, "start", "end", geom
	into dkatlas_geom from dkatlas d
	where geom is not null;
select * from gaz.dkatlas_geom dg;

-- pleiades 41,833
select id, title, gaz.pleiades.representative_longitude as lon,
	gaz.pleiades.representative_latitude as lat
	from gaz.pleiades;

-- WH cities 258
select id, city, title, wc.ccode, wc.country, wc.region, wc.geom 
	from gaz.wh_cities wc 
	order by region, ccode, city;

-- WH Sites 1,248
select id_no, name_en, upper(iso_code) as iso_code, w.states_name_en, longitude, latitude, region_en, short_description_en
	from gaz.wh2025 w order by region_en, iso_code, name_en ;


	