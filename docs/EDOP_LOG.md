### EDOP LOG
----
#### 19 Jan 2026
- **pre-launch bug fixes** for v0.1 demo to Pitt collaborators
- fixed ecoregion geometry: removed non-existent `oneearth_slug` column from `/api/eco/geom` query
- fixed societies map: changed `L.layerGroup()` to `L.featureGroup()` for `getBounds()` support
- fixed societies zoom: replaced `fitBounds()` with `setView([20, 0], 1)` for fixed global view
- fixed WHG search ranking: changed `mode: "exact"` to `mode: "fuzzy"` — Denver CO now ranks first
- fixed WHG popover close button: added `sanitize: false` and `html: true` to popover options
- **societies loading spinner**: shows during 6-7s initial fetch, hides accordions until ready
- **variable description tooltips**: question mark icons on EA042/EA034 headers, hover shows D-PLACE descriptions
- added `variable_info` to `/api/societies` response with variable names and descriptions
- header styling: smaller About/API links, subtle badge (`bg-secondary rounded-pill`)

#### 18 Jan 2026
- integrated D-PLACE cultural database: 1,291 societies, 94 anthropological variables, 121k observations
- spatial join: added `basin_id`, `eco_id`, `bioregion_id` to `dplace_societies` (87% basin, 99% bioregion coverage)
- created correlation scripts: `dplace_env_correlations_signature.py` uses EDOP signature fields by band
- **key finding**: temperature explains 40% of variance in agriculture intensity; runoff explains 17% of domestic animal type
- excluded Band D (Anthropocene markers) as anachronistic for historical inquiry
- output: `output/dplace/correlations_signature_bands_ABC.csv`, `analysis_narrative_18Jan2026.md`
- **Societies tab UI**: new tab displaying 1,291 societies as map markers
- `/api/societies` endpoint returns societies with bioregion and EA042 subsistence data
- accordion-style subsistence filter (EA042): 7 categories with color-coded radio buttons
- markers colored by subsistence type; filtered view fades non-matching markers
- **top ecoregions by realm**: selecting subsistence filter shows top 3 ecoregions per realm in 2-column display
- API joins through OneEarth hierarchy (Bioregions2023 → Subrealm2023 → Realm2023) for proper realm names
- **basin clusters display**: toggle between "Ecoregions by realm" and "Basin clusters" views
- fixed cluster join bug: was using `basin08_pca_clusters` table instead of `basin08.cluster_id`
- **renamed cluster labels**: replaced geographic names with environmental descriptors
  - "High Andes" → "Cold high plateau", "Mediterranean" → "Warm semi-arid upland", etc.
  - labels now based on temperature/moisture/elevation, no geographic references
- **Religion query (EA034)**: second accordion for "High gods" with 4 categories
  - Absent (277), Otiose (258), Active not moral (42), Active supporting morality (198)
  - color gradient from light pink to dark red reflecting belief intensity
  - selecting religion resets subsistence filter and vice versa (one query active at a time)
- **environmental correlation**: societies with moralizing high gods have half the precipitation of those without

#### 17 Jan 2026
- created `scripts/summarize_ecoregion_text.py` — Claude Sonnet batch summarization of ecoregion Wikipedia text
- added `summary` column to `eco_wikitext` table; generated 821 summaries (150-200 words, geo/eco focus)
- added `/api/eco/wikitext?eco_id=X` endpoint returning summary and wiki_url
- redesigned ecoregion detail card: name + OneEarth/Wikipedia buttons + summary paragraph
- reordered realms list: priority realms (Subarctic America, North America, Eastern Eurasia) sorted to top with note about completeness

#### 16 Jan 2026
- overhauled Ecoregions tab UX: map now shows child features matching the list (not parent geometry)
- added 3 new geometry endpoints: `/api/eco/subrealms/geom`, `/api/eco/bioregions/geom`, `/api/eco/ecoregions/geom`
- created `displayEcoFeatures()` function with 10-color palette, tooltips, bidirectional hover highlighting
- wired up `gaz.bioregion_meta` table: bioregion list shows human-readable titles where available
- added OneEarth external links with icon indicators (Bootstrap Icons CDN)
- fixed nested `<a>` tag issue in bioregion list rendering (invalid HTML → `<span>` with onclick)
- **added click-to-drill-down on map features** — clicking a polygon triggers same navigation as clicking list item

#### 15 Jan 2026
- diagnosed Wikipedia extraction issue: MediaWiki's `exlimit` silently limits full-text extracts to 1 page per batch request
- fixed `scripts/refetch_wiki_extracts.py` to fetch one title at a time (0.2s delay, ~3 min for 847 titles)
- created `public.eco_wikitext` table with FK to `gaz."Ecoregions2017"`, full-text search index
- loaded 751/847 ecoregion Wikipedia extracts (88.5% initial coverage)
- created `scripts/triage_missing_ecoregions.py` for automated candidate discovery
- triaged 96 missing ecoregions: 7 strong matches, 19 partial, 45 redirects, 25 no match
- manual review of 71 candidates: accepted 66 full articles + 4 section extracts, rejected 1 false positive
- created `scripts/fetch_reviewed_extracts.py` to handle section extraction from broader articles
- **final result: 821/847 ecoregions with Wikipedia text (96.9% coverage)**

#### 11 Jan 2026
- created `docs/edop_database_schema.md` — comprehensive reference for all source and result tables to reduce context-building between Claude Code sessions
- implemented full 1565-dimensional basin clustering pipeline for all 190,675 basins:
  - `scripts/basin08_sparse_matrix.py`: extracts 27 numerical + 15 PNV + 1519 one-hot categorical features → sparse matrix (97.88% sparse, 13 MB)
  - `scripts/basin08_pca.py`: TruncatedSVD reduces to 150 components (86.2% variance)
  - `scripts/basin08_cluster_analysis.py`: tests k=5-50, analyzes silhouette/elbow/Calinski-Harabasz
  - `scripts/basin08_clustering_k20.py`: final k=20 clustering, creates `basin08_pca_clusters` table
- new table `basin08_pca_clusters` (190,675 rows): hybas_id → cluster_id based on full environmental signature
- cluster sizes range from 4,263 to 18,736 basins (reasonably balanced)
- cluster labeling via `scripts/basin08_cluster_labels.py`: analyzes centroids, biomes, WHC city membership
- created `output/basin08_cluster_labels_manual.json` — editable labels derived from biome + city analysis (e.g., "Mediterranean / Warm Temperate", "Tropical Coastal", "Arctic Tundra")
- output files in `output/`: sparse matrix, PCA products, cluster assignments/centroids/labels
- **PCA vs FAMD validation** (`scripts/basin08_famd_comparison.py`): 50k sample comparison shows moderate agreement (ARI=0.437, NMI=0.609, ~60% best-match). PCA acceptable for exploratory work; FAMD more defensible for rigorous analysis.
- note: exploratory work; clusters subject to revision based on downstream utility

#### 10 Jan 2026


#### 09 Jan 2026
- scaled up environmental analysis from 20 pilot sites to 258 World Heritage Cities (WHC)
- merged WHG reconciliation data into `wh_cities` table: 258 geometries added, 254 basin_ids assigned (4 island cities outside HydroATLAS coverage)
- created `whc_*` schema parallel to pilot `edop_*`: `whc_matrix` (254×893 features), `whc_pca_coords` (50 components), `whc_similarity` (32,131 pairs), `whc_clusters` (k=10)
- environmental clustering reveals meaningful groups: Mediterranean (49), Arid/desert (21), Northern Europe (15), High altitude (22), Central Europe temperate (55), East Asia monsoon (39), Tropical wet (26)
- persisted wiki/semantic data to database: `whc_band_summaries` (1,032 rows), `whc_band_clusters` (1,217), `whc_band_similarity` (12,170)
- added 3 new API endpoints: `/api/whc-cities`, `/api/whc-similar`, `/api/whc-similar-text`
- created **WHC Cities** tab in UI with grouped dropdown (by UNESCO region), dual similarity buttons, cluster badges
- Timbuktu validation: env-similar → Agadez, Khiva, Zabid (arid); text-similar → Agadez, Dakar, Marrakesh (West African cultural)

#### 07 Jan 2026
- scaled up Wikipedia text corpus pipeline from 20 pilot sites to 258 WHC cities
- used `wh_cities` database table as source; output to `output/corpus_258/` (file-only, no database)
- harvested 7,757 Wikipedia sections; average 3.7/4 bands mapped per city
- LLM summarization: 258 cities × 4 bands; ~$8.90 cost (1.3M input tokens, 329k output)
- generated OpenAI embeddings (`text-embedding-3-small`) with k=8 clustering
- text clusters show regional/cultural coherence: Northern European, Mediterranean, Hispanic World, South Asian, Lusophone, Central/Eastern European, Islamic/Arab, Mixed/Colonial
- high similarity pairs validate approach: Kutná Hora↔Český Krumlov, Quedlinburg↔Goslar, Arequipa↔Cusco
- completed WHG reconciliation for coordinates: uploaded LP-TSV to WHG, matched 258/258, exported geometry

#### 06 Jan 2026
- built Wikipedia corpus pipeline: harvest → band mapping → LLM summarization → embeddings
- created `scripts/corpus/` with `harvest_sections.py`, `summarize_bands.py`, `generate_band_embeddings.py`
- harvested 674 Wikipedia sections for 20 pilot sites via MediaWiki API
- developed semantic band mapping (history, environment, culture, modern) with aggressive pattern matching — 67% content coverage
- used Claude API to summarize each band per site into 150-300 word normalized summaries
- generated OpenAI embeddings (`text-embedding-3-small`) per band + composite; stored in new tables `edop_band_embeddings`, `edop_band_similarity`, `edop_band_clusters`
- correlation analysis: environment text band tracks physical environment (r=-0.19); history band shows no relationship (r=+0.01)
- text clustering reveals discourse types: European imperial (Vienna, Venice), trade routes (Timbuktu, Samarkand), indigenous monuments (Angkor, Cahokia)
- cluster agreement between text and environmental: 45% (vs 20% chance) — complementary signals, not redundant
- added `wiki_slug` column to `edop_wh_sites`; populated for 20 pilot sites

#### 05 Jan 2026
- created `scripts/generate_text_embeddings.py`: OpenAI embeddings from Wikipedia lead+history text
- new tables: `edop_text_embeddings`, `edop_text_similarity`, `edop_text_clusters` (k=5)
- text clusters show semantic coherence: natural parks, archaeological sites, European cities, trade routes, Chinese heritage
- key finding: only 1/20 sites shares nearest neighbor between environmental and text similarity — dimensions largely orthogonal
- added `/api/similar-text` endpoint mirroring `/api/similar`
- UI updated with dual buttons: "Similar (env)" and "Similar (semantic)" with dynamic headings/descriptions
- created `scripts/cliopatria_to_lpf.py`: transforms Seshat/Cliopatria polities GeoJSON to Linked Places Format (1,547 polities, 449 MB)
- removed `.env` from git tracking (API keys); pushed clean `embedding` branch

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


