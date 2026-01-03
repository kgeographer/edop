### EDOP LOG
----
#### 02 Jan 2026
- gathered 47 attributes from `basins08` into a signature in 4 groups (A-D) in order of "peristence" as proposed by Gemini and agreed by committee (3 ots and KG). 
- new payload of all signature data to main UI page, rendered as a Summary (11 seleted fields, followed by 4 accordions for the groups
- relative elevation position within basin is now computed on the fly and part of payload.


#### 01 Jan 2026
- wired a "Resolve" button to WHG API endpoints (run a `/suggest/entity?` call, then an `/entity/{entity_id}/api` call with a resulting place id and it works nicely, ~1.8s
- index.html now with inputs for lon/lat or name, returning an "Environmental profile" (`signature` internally), and point feature on Leaflet map
- implemented World Heritage Site lookup for 20 varied locales on its own tab
- added point elevation from external sources (try OpenTopoData (mapzen) first, then Open-Meteo elevation API
- TODO: compute relative elevation position within the basin

```
Interpretation:
	•	~0.0 → near basin minimum (valley floor / lowlands)
	•	~1.0 → near basin maximum (ridge / highlands)
	•	~0.5 → mid-slope / plateau-ish
```

#### 31 Dec 2025
```
rsync -av --progress --partial \
  -e "ssh -i ~/.ssh/do_nov2016 -o ServerAliveInterval=1800" \
  basins_l08.gpkg \
  karlg@107.170.199.83:/home/karlg/xfer/
```
OR

```ssh edop-droplet
rsync -av --progress --partial basins_l08.gpkg edop-droplet:/home/karlg/xfer/
```
psql access: `on droplet: `sudo -u postgres psql`

```
sudo -u postgres ogr2ogr \
  -f PostgreSQL \
  PG:"dbname=edop user=postgres" \
  /tmp/basins_l08.gpkg \
  BasinATLAS_v10_lev08 \
  -nln basin08 \
  -lco GEOMETRY_NAME=geom \
  -lco FID=id \
  -lco SPATIAL_INDEX=GIST \
  -progress
```

#### 30 Dec 2025
- exported level 08 from BasinATLAS_v10.gdb as geopackage
  - `ogr2ogr -f GPKG basins_l08.gpkg BasinATLAS_v10.gdb BasinATLAS_v10_lev08`
- imported to local postgres db on :5435 __edop__ as __basin08__ table
- imported 3 of 11 'lookup' tables for codes in climate zones, climate strata, landcover fields: __lu_clz__, __lu_cls__, __lu_glc__.
- created view __v\_basin08\_basic__

```
select * FROM public.v_basin08_basic WHERE ST_Covers(
  geom, ST_SetSRID(ST_MakePoint(-3.00777252, 16.76618535), 4326)
) ORDER BY area_km2 ASC LIMIT 1;
```
- for Timbuktu:

```
{
	"zone_id" : 17,
	"zone_name" : "Extremely hot and xeric",
	"strata_id" : 124,
	"strata_code" : "Q5",
	"land_cover_id" : 14,
	"land_cover_name" : "Sparse herbaceous or sparse shrub cover",
	"pop_density" : 86.87200164794922,
	"elev_min" : 262,
	"elev_max" : 276,
	"runoff" : 18,
	"discharge_yr" : 0.7110000252723694,
	"geom" : "MULTIPOLYGON (((-3.2708333335914404 16.899999999600368,...)))
}
```

#### 29 Dec 2025
- settled on BasinAtlas as initial focus for data 
  - https://www.hydrosheds.org/products/hydrobasins
  - 299 fields; 12 hierarchical levels of spatial resolution
  - starting with level 08 (190675 rows)
  - license is CC-By 4.0
- ecoregions2017 has only __eco\_name__ available; download: [Ecoregions2017.zip](https://storage.googleapis.com/teow2016/Ecoregions2017.zip) (E. Dinerstein)
- OneEarth.org has nice landing pages for these, but licensing prevents hoped-for reuse in LLM schema induction. Map: [https://www.oneearth.org/navigator/](https://www.oneearth.org/navigator/); [Terms of use](https://www.oneearth.org/terms/)
- ecoregions are "areas of land containing a distinct set of natural communities and species, different from their nearest neighboring ecoregions"
- elevation data considered (future)
  - SRTM (Shuttle Radar Topography Mission): 30m (1 arc-second) global
  - NASADEM (30m): improved SRTM
  - Copernicus DEM (GLO-30 / GLO-90)


