# Session Log: 14 January 2026

## Objective
GUI refinements, "Similar WH Cities" feature for WHG API, and Ecoregions hierarchy drill-down UI.

---

## 1. Bug Fixes

### WH Cities Dropdown Filter
Cities with `basin_id = NULL` (islands without basin coverage) were appearing in dropdown but causing errors.

**Fix:** Added filter to `/api/whc-cities` endpoint:
```sql
WHERE c.basin_id IS NOT NULL
```

---

## 2. GUI Improvements

### Environmental Profile Heading Visibility
"Environmental profile" heading now only appears after resolving a place.

**Changes:**
- Added `id="profile-heading"` with initial `style="display:none"`
- `renderSignature()` shows/hides based on data presence

### WHG Place Record Popover
Replaced "Resolved place" div with a compact link that shows WHG API payload in a popover.

**Implementation:**
- Added "WHG place record" link flush-right on profile heading line
- Bootstrap popover displays formatted JSON
- Close button in popover header

### Header Click to Restore Main Tab
Clicking site title in header now returns to Main tab.

**Changes:**
- Made title clickable with `id="site-title"` in `base.html`
- Click handler triggers Main tab and resets UI state

---

## 3. Similar WH Cities for WHG API

Added ability to find similar World Heritage cities for any location resolved via WHG API.

### New Endpoint: `/api/whc-similar-env-by-coord`
Returns 5 most similar WH cities based on PCA vector distance from the basin containing the input coordinates.

**Features:**
- Uses pgvector `<->` operator for cosine distance
- Includes percentile context (how similar compared to all 254 cities)
- Returns distance, percentile, city name, country, coordinates

**SQL approach:**
```sql
WITH input_basin AS (
    SELECT hybas_id FROM basin08 WHERE ST_Covers(geom, ST_SetSRID(ST_Point(%s, %s), 4326))
),
input_vector AS (
    SELECT pca_vector FROM basin08_pca WHERE hybas_id = (SELECT hybas_id FROM input_basin)
)
SELECT c.id, c.city, c.country_en, c.lat, c.lon,
       bp.pca_vector <-> (SELECT pca_vector FROM input_vector) as distance
FROM gaz.wh_cities c
JOIN basin08_pca bp ON bp.hybas_id = c.basin_id
ORDER BY distance LIMIT 5
```

### Frontend
- Added "Similar WH Cities" button to WHG input section
- Results display with distance percentile context
- Click city name to see location on map

---

## 4. Ecoregions Hierarchy (OneEarth Data)

Integrated OneEarth's biogeographic hierarchy for drill-down exploration.

### Data Import
Four shapefiles imported to `gaz` schema:
- `Realm2023` (14 rows) - highest level
- `Subrealm2023` (53 rows)
- `Bioregions2023` (185 rows)
- `Ecoregions2017` (847 rows) - lowest level

### Foreign Key Relationships
Created FK columns via spatial joins using centroids:
```sql
-- Ecoregions → Bioregions
ALTER TABLE gaz."Ecoregions2017" ADD COLUMN bioregion_fk TEXT;
UPDATE gaz."Ecoregions2017" e SET bioregion_fk = b.bioregion_
FROM gaz."Bioregions2023" b
WHERE ST_Within(ST_Centroid(e.geom), b.geom);

-- Similar pattern for Bioregions → Subrealms and Subrealms → Realms
```

**Coverage:** 842/847 ecoregions, 181/185 bioregions linked (small islands missed due to centroid placement).

### API Endpoints
Created hierarchy navigation endpoints:
- `GET /api/eco/realms` - list realms with subrealm counts
- `GET /api/eco/subrealms?realm=X` - list subrealms with bioregion counts
- `GET /api/eco/bioregions?subrealm_id=X` - list bioregions with ecoregion counts
- `GET /api/eco/ecoregions?bioregion=X` - list ecoregions with biome info
- `GET /api/eco/geom?level=X&id=Y` - get GeoJSON geometry for any level item
- `GET /api/eco/realms/geom` - get FeatureCollection of all realm geometries

### Frontend UI
New Ecoregions tab with:
- Breadcrumb navigation (Realms → Subrealm → Bioregion → Ecoregion)
- Drill-down list showing child counts at each level
- Map displays polygon geometry at each level
- Selected item info panel with OneEarth link (for ecoregions)

### Tab Initialization Fix
Realms now load automatically when navigating to Ecoregions tab.

**Issue:** Separate event listener wasn't firing.

**Fix:** Consolidated eco tab handling into main tab event handler:
```javascript
// In main tab handler
if (targetSel === '#panel-eco') {
  ecoSetStatus('');
  if (!ecoTabInitialized) {
    ecoTabInitialized = true;
    loadEcoLevel(ecoBreadcrumbState[0]);
  }
}
```

---

## 5. Explainer System

Added context-sensitive explainer text that appears on page load and hides when signature data is displayed.

### Main Explainer
Two-paragraph EDOP introduction appears in Main tab when WHG API pill is active:
- Explains environmental signatures based on HydroBasins level 8
- Describes similarity comparisons (environmental + text-based)
- Mentions ecoregion hierarchy integration

### Pill-Specific Explainers
Each input method pill has its own explainer div:
- `main-explainer` - shows when WHG API pill active
- `explainer-edop` - shows when EDOP Gazetteer pill active
- `explainer-coords` - shows when Coordinates pill active

**Implementation:**
```javascript
function showActiveExplainer() {
  // Hide all explainers first
  ['main-explainer', 'explainer-edop', 'explainer-coords'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  // Show explainer for active pill based on data-bs-target
  const activePill = document.querySelector('#main-input-pills .nav-link.active');
  // ... show matching explainer
}
```

### About Modal
Added "About" link in header that opens a 75%-width modal with sections:
- **Technical** - placeholder for technical documentation
- **Project Mission** - placeholder for project goals

Header layout updated: `About | API docs | [v0.1 badge]`

---

## 6. Production Deployment

### Ecoregion Tables Export
```bash
pg_dump -h localhost -p 5435 -U postgres -d edop \
  --clean --if-exists \
  -t 'gaz."Realm2023"' \
  -t 'gaz."Subrealm2023"' \
  -t 'gaz."Bioregions2023"' \
  -t 'gaz."Ecoregions2017"' \
  > /tmp/edop_dumps/06_ecoregion_tables.sql
```

### Server Restore
```bash
psql -h localhost -p 5432 -U postgres -d edop < 06_ecoregion_tables.sql
sudo systemctl restart edop
```

---

## Files Modified

```
app/api/routes.py           # New endpoints: whc-similar-env-by-coord, eco/* hierarchy
app/templates/index.html    # GUI fixes, Similar WH Cities, Ecoregions tab, explainers
app/templates/base.html     # Clickable header title, About modal, header layout
```

---

## Notes

- Ecoregion polygons appear "blob-ey" due to simplified geometries in OneEarth data
- 5 orphan ecoregions and 4 orphan bioregions exist (islands where centroid falls outside parent polygon)
- Percentile context helps users understand if "similar" cities are actually similar or just least-dissimilar
