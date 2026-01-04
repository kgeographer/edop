# PCA Results Summary

Analysis of 20 World Heritage Sites across 1565 environmental dimensions.

## Variance Explained

- **No dominant component** - variance is spread across many dimensions (PC1=11.8%, PC2=10.6%)
- Need **13 components for 80%** variance, **16 for 90%**
- This is expected: the 20 diverse sites span many independent environmental gradients

| Component | Individual | Cumulative |
|-----------|------------|------------|
| PC1 | 11.8% | 11.8% |
| PC2 | 10.6% | 22.4% |
| PC3 | 8.7% | 31.1% |
| PC4 | 7.2% | 38.3% |
| PC5 | 6.8% | 45.0% |

## Interpretable Gradients

| Component | Explains | Interpretation |
|-----------|----------|----------------|
| **PC1** (11.8%) | **Temperature/terrain** - warm flat → cool mountainous |
| **PC2** (10.6%) | **Hydrology/development** - dry remote → wet/urbanized river basins |
| **PC3** (8.7%) | **Wetland/runoff** - dry → wet floodplains |

### Top Feature Loadings

**PC1 (Temperature/Terrain):**
- temp_yr (+0.228)
- temp_max (+0.221)
- temp_min (+0.202)
- slope_upstream (-0.202)
- slope_avg (-0.176)

**PC2 (Hydrology/Development):**
- human_footprint_09 (+0.223)
- discharge_min (+0.219)
- discharge_yr (+0.216)
- discharge_max (+0.214)
- river_area_upstream (+0.208)

**PC3 (Wetland/Runoff):**
- river_area (+0.247)
- pnv_01 (+0.223)
- wet_3 (+0.195)
- runoff (+0.187)

## Site Positions in PCA Space

Sites ordered by PC1 (cool/mountainous → hot/flat):

| Site | PC1 | PC2 | PC3 |
|------|-----|-----|-----|
| Historic Sanctuary of Machu Picchu | -7.23 | -6.92 | +7.63 |
| Taos Pueblo | -4.64 | -4.58 | -2.51 |
| Cahokia Mounds State Historic Site | -4.43 | +10.63 | +4.06 |
| Head-Smashed-In Buffalo Jump | -3.98 | -1.17 | -1.86 |
| Old Town of Lijiang | -2.63 | -3.36 | -0.48 |
| Historic Centre of Vienna | -2.61 | +3.09 | -2.02 |
| Historic Monuments of Ancient Kyoto | -2.60 | +1.22 | -0.75 |
| Kyiv: Saint-Sophia Cathedral | -1.28 | +3.65 | -2.62 |
| Samarkand – Crossroad of Cultures | -1.13 | -1.32 | -1.51 |
| Historic Centre (Old Town) of Tallinn | -0.55 | +0.81 | -3.04 |
| Summer Palace, Beijing | -0.30 | +1.49 | -2.23 |
| Historic City of Toledo | +0.41 | -0.93 | -2.23 |
| Venice and its Lagoon | +1.10 | +2.81 | -3.41 |
| Göbekli Tepe | +1.77 | -0.41 | -1.39 |
| Iguazu National Park | +2.04 | +2.33 | +8.30 |
| Petra | +3.34 | -2.99 | -0.82 |
| Uluru-Kata Tjuta National Park | +3.57 | -2.89 | +0.22 |
| Timbuktu | +6.19 | -1.82 | +0.14 |
| Ellora Caves | +6.34 | +0.19 | +1.82 |
| Angkor | +6.63 | +0.18 | +2.71 |

## Cluster Labels (K-means, k=5)

| Label | Sites | Key Characteristics |
|-------|-------|---------------------|
| **Temperate Lowland Heritage** | Vienna, Kyiv, Venice, Kyoto, Tallinn, Beijing, Angkor, Head-Smashed-In | Moderate temps, low elevation, highest human footprint |
| **Subtropical/Arid Wilderness** | Iguazu, Uluru, Petra | Hot, remote, low human impact |
| **High Altitude Continental** | Machu Picchu, Lijiang, Taos | Cool, highest elevation, low discharge |
| **Arid Heritage Crossroads** | Timbuktu, Ellora, Toledo, Göbekli Tepe, Samarkand | Hot, driest, most arid |
| **Major River Floodplain** | Cahokia | Outlier: highest discharge, highest human footprint |

## Notable Observations

- **Machu Picchu** is the most distinct site (high altitude Andes, unique environment)
- **Cahokia** is an outlier on PC2 (major river confluence on Mississippi)
- **Timbuktu, Uluru, Petra** cluster together (arid environments)
- **European cities** (Vienna, Kyiv, Tallinn, Venice) cluster in center-top

## Generated Plots

- `pca_variance.png` - Explained variance by component
- `pca_sites_2d.png` - Sites in PC1-PC2 space
- `pca_sites_3d.png` - Sites in PC1-PC2-PC3 space
