### EDOP LOG
----
#### 04 Jan 2026 (w/ChatGPT)
- began integrating Wikipedia text as a second similarity signal for 20 exemplar World Heritage sites
- implemented `fetch_wikipedia_wh.py` using MediaWiki API (no HTML scraping); retrieves canonical title, pageid, URL, lead text
- added diagnostics showing large variance in lead length (≈30–550 words), making lead-only embeddings unreliable
- inventoried Wikipedia section structure via `action=parse&prop=sections`; stored section metadata as JSON
- found 16/20 sites include top-level “History*” sections (often “History” or “Historical overview”)
- implemented logic to retrieve history-like sections via section index and wikitext
- began constructing provisional documents as lead + history text; paused before embeddings to reason about normalization and truncation
- completed cleanup and normalization of Wikipedia-derived text; generated `wh_wikipedia_leads.tsv` suitable for text embeddings
- accepted residual variation in text length as reflective of WH site typology (ensemble vs city vs landscape); pipeline now ready for embedding-based similarity analysis- 

#### 04 Jan 2026 (w/Claude)
- exposed similarity analysis in web UI: cluster label badge displays on WH site selection (e.g., "Temperate Lowland Heritage")
- implemented "Most Similar" button with `/api/similar?id_no=<id>&limit=5` endpoint querying `edop_similarity` table
- color-coded similar sites: 5-color palette (ColorBrewer Set1) for map markers with matching swatches in ranked list
- map auto-zooms to fit source + all similar sites; same-cluster sites highlighted in green
- fixed description toggle bug: empty string display value was falsy, now uses `display = 'block'` with `=== 'none'` check
- modernized CSS: introduced custom properties (`--page-inline-padding: 1.5rem`) and logical properties (`padding-inline`, `padding-block`) for RTL-friendly layout
- work committed to `moregui` branch

#### 03 Jan 2026
- using Claude Code created persistence matrix for 20 WH sites: 1561 dimensions (27 numerical normalized, 9 categorical one-hot encoded [1519 total categories], 15 PNV share columns)
- new schema: `edop_norm_ranges`, `edop_wh_sites`, `edop_matrix` (20×1565)
- PCA analysis: 19 components, no dominant axis; PC1 (11.8%) temp/terrain, PC2 (10.6%) hydro/development, PC3 (8.7%) wetland
- persisted PCA products: `edop_pca_coords`, `edop_pca_variance`, `edop_similarity` (380 pairwise distances), `edop_clusters` (k=5)
- clustering reveals: temperate/urban (8 sites), extreme environments (3), high altitude (3), arid/warm (5), outlier Cahokia
- similarity queries now possible: e.g. sites most like Timbuktu → Göbekli Tepe, Uluru, Beijing, Samarkand

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


