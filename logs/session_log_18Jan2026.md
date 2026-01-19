# Session Log: 18 January 2026

## Summary
Integrated D-PLACE cultural database with EDOP environmental signatures. Computed correlations between signature fields and cultural variables, identifying compelling environment-culture relationships for collaborator demos.

## D-PLACE Integration

### Data Overview
- **D-PLACE**: Database of Places, Language, Culture, and Environment
- 1,291 societies with coordinates, 94 anthropological variables, 121k coded observations
- Focal years typically 1850-1940 (ethnographic present)

### Tables Added (gaz schema)
- `dplace_societies` — 1,291 societies with coordinates, region, focal year
- `dplace_variables` — 94 anthropological variables (subsistence, kinship, housing, politics)
- `dplace_codes` — coded values for categorical variables
- `dplace_data` — 121k observations linking societies to variable values

### Spatial Joins
Added columns to `dplace_societies`:
- `basin_id` — FK to basin08.hybas_id (1,133 assigned, 87.8%)
- `eco_id` — FK to Ecoregions2017 (1,123 assigned, 87.0%)
- ~160 unassigned are island/coastal societies outside polygon coverage

## Correlation Analysis

### Scripts Created
1. `scripts/dplace_env_correlations_exploratory.py` — uses hand-picked basin08 variables
2. `scripts/dplace_env_correlations_signature.py` — uses EDOP curated signature fields (Bands A-C)

**Important distinction:** The signature script uses the 47 curated fields from `v_basin08_persist` organized by persistence band. This validates EDOP's framework rather than exploring arbitrary correlations.

### Key Finding: Band D Excluded
Band D (Anthropocene markers: GDP, HDI, etc.) shows strong correlations but is **anachronistic** — correlating 1850-1940 cultural patterns with 2000s economic data. Excluded from analysis.

### Results (Bands A-C, p < 0.001)

**Band C (Bioclimatic) — Strongest effects:**
- Temperature → Agriculture intensity (η² = 0.40)
  - No agriculture: 7.6°C; Extensive: 23.6°C
- Temperature → Dominant subsistence (η² = 0.38)
  - Hunting: -5.8°C min; Extensive agriculture: 21.4°C min

**Band B (Hydro-climatic) — Moderate effects:**
- Runoff → Domestic animal type (η² = 0.17)
  - Camelids: 55 mm/yr; Pigs: 1,431 mm/yr
- Groundwater depth → Agriculture intensity (η² = 0.14)

**Band A (Physiographic) — Weaker but stable:**
- Elevation → Subsistence patterns (η² = 0.05-0.07)
  - Fishing at low elevation; Gathering at high

### Summary by Band
| Band | Significant Correlations | Avg η² |
|------|-------------------------|--------|
| A (Physiographic) | 12 | 0.044 |
| B (Hydro-climatic) | 35 | 0.064 |
| C (Bioclimatic) | 65 | 0.144 |

## Output Files
- `output/dplace/correlations_signature_bands_ABC.csv` — full results (230 pairs)
- `output/dplace/analysis_narrative_18Jan2026.md` — demo narrative for collaborators

## Files Created/Modified
- `scripts/dplace_env_correlations_exploratory.py` — new
- `scripts/dplace_env_correlations_signature.py` — new
- `gaz.dplace_societies` — added basin_id, eco_id columns

## Demo Narrative
> "EDOP assigns environmental signatures to any geographic location. When linked to D-PLACE's 1,291 ethnographically documented societies, environmental dimensions—particularly temperature and water availability—explain substantial variance in subsistence strategies. Warm climates enabled agriculture; arid environments supported camelid pastoralism; wet environments supported pig husbandry. These correlations use signature fields organized by persistence bands, excluding modern Anthropocene markers to focus on historically relevant constraints."

## Societies Tab UI

### New Tab Added
- **Societies** tab with 1,291 D-PLACE societies displayed as map markers
- Explanatory text describing D-PLACE data and EDOP integration

### Spatial Join: Bioregions
- Added `bioregion_id` column to `dplace_societies` (varchar, e.g., 'AT20')
- 1,281/1,291 (99.2%) assigned via ST_Contains join to Bioregions2023
- Better coverage than basins since bioregion polygons include more islands

### API Endpoint
- `GET /api/societies` — returns all societies with coordinates, bioregion, and EA042 subsistence data
- Includes `subsistence_categories` with counts for UI

### Subsistence Filter (EA042)
- Accordion-style query panel with "Dominant subsistence (EA042)" header
- Click to expand: 8 radio buttons (All + 7 subsistence types)
- Categories: Gathering, Hunting, Fishing, Pastoralism, Extensive agriculture, Intensive agriculture, Agriculture type unknown
- Excluded "Two or more sources" as it indicates provenance, not subsistence
- Default: all societies with data colored by subsistence type; no-data greyed out
- Filter: selected category colored, others faded (reduced opacity)

### Output
- `output/dplace/unassigned_societies.csv` — 158 societies outside basin coverage for QGIS review

### Top Ecoregions by Realm Display
- When user selects a subsistence filter, displays top 3 ecoregions per realm below the map
- Grouped by OneEarth realm names in 2-column layout
- API enhanced to join through bioregion hierarchy: Bioregions2023 → Subrealm2023 → Realm2023
- Realm names stripped of parenthetical content (e.g., "South America" not "South America (lower Neotropic)")
- 14 realms represented: Afrotropics (496), North America (234), Australasia (100), etc.
- Generic `dplace-results` container created for reuse with future query outputs

### Basin Clusters Display Toggle
- Added "Show:" toggle in subsistence panel: Ecoregions by realm | Basin clusters
- Basin clusters view shows society counts per environmental cluster type
- **Bug fix**: Was joining to wrong table (`basin08_pca_clusters` instead of `basin08.cluster_id`)
  - Resulted in counter-intuitive results (e.g., "High Andes: 69" for intensive agriculture)
  - Detective work revealed two different clustering results stored in database

### Environmental Cluster Labels
- Replaced geographic cluster labels with environmental descriptors
- Old labels derived from WHC city distributions were geographically misleading
- New labels based on actual environmental characteristics (temp, precip, elevation):

| Old (Geographic) | New (Environmental) |
|------------------|---------------------|
| High Andes | Cold high plateau |
| Mediterranean | Warm semi-arid upland |
| Central Asian steppe | Cool semi-arid upland |
| Sahel/tropical dry | Hot subhumid lowland |
| Nordic fjord/coastal | Cold subhumid lowland |

### Religion Query (EA034)
- Added second accordion: "High gods (EA034)"
- 4 categories ordered by conceptual progression:
  - Absent (277 societies)
  - Otiose (258) - high god present but inactive
  - Active, but not supporting morality (42)
  - Active, supporting morality (198)
- Color gradient: light pink → dark red reflecting belief intensity
- Selecting religion filter resets subsistence filter (one query active at a time)
- Both "Ecoregions by realm" and "Basin clusters" display modes work

### Environmental-Religion Correlation Finding
- Societies with moralizing high gods have **half the precipitation** (677mm vs 1281mm) of societies without high gods
- Strong confound with subsistence: moralizing gods concentrated in intensive agriculture (95) and pastoralism (45)
- Possible causal chain: drier environment → pastoralism/intensive ag → moralizing high gods
- Aligns with anthropological literature on resource scarcity → cooperation → moral enforcement
