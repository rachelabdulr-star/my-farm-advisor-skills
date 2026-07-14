# Field-Level EDA

Generates static statistical visualizations and comparison tables from the
data-pipeline runtime, organized into three categories across three comparison
levels (within-field, across-fields, across-growers).

## Categories & Outputs

| Category | V1 (PNG) | V2 (PNG) | C1 (CSV) |
|---|---|---|---|
| **Field Boundaries** | KDE density of field sizes per grower | Attribute clustering heatmap | Size summary + skewness table |
| **CDL / Cropland** | Grouped bar: crop acres by grower × year | Transition heatmap 2024→2025 | Per-field rotation stability table |
| **Weather** | Dual-axis T2M + precip for one field | Grower-level box plots (T2M, precip) | GDD accumulation curves per grower |

## Data scope

- Years: 2024–2025 only
- 3 categories × 3 outputs = 9 total outputs per run

## Output location

```
growers/<g>/farms/<f>/derived/eda/
```

## Dependencies

Already in the runtime venv: `pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`, `geopandas`

## See also

- [SKILL.md](SKILL.md) — subskill router
- [GUIDE.md](GUIDE.md) — usage guide
- [AGENTS.md](AGENTS.md) — agent instructions
- [PROVENANCE.md](PROVENANCE.md) — source provenance

## Report artifact

After running the subskill, a self-contained single-page HTML report can be
generated from the outputs. The report embeds all PNG visualizations as base64
and renders CSV data as interactive tables. No server or external dependencies
required — open the `.html` file in any browser.

The report generator is a one-time artifact, not part of the reusable subskill.
It reads from the `derived/eda/` directory and writes `field_level_eda_report.html`
to the same location.

## Assignment 3 — Field Dashboard (2025)

Generated a single-field dashboard for osm-1360386537 (ia-grower, 148.1 acres,
Kossuth County, Iowa) covering the 2025 soybean growing season.

### Input files
| Source | Path |
|---|---|
| Daily weather | `fields/osm-1360386537/weather/daily_weather.csv` (NASA POWER, 2021–2025) |
| Sentinel-2 NDVI scenes | `fields/osm-1360386537/satellite/sentinel/2025/` (8 scenes, Apr–Nov) |
| NDVI annual composite | `fields/osm-1360386537/derived/features/ndvi_year_2025_composite.tif` |
| Management zones | `fields/osm-1360386537/derived/zones/management_zones_2025.tif` |
| CDL crop data | `derived/tables/ia_grower_iowa_cdl_2021_2025_full_composition.csv` |
| Field boundary | `fields/osm-1360386537/boundary/field_boundary.geojson` |

### Weather metrics calculated
- Daily T2M (mean/max/min), precipitation, relative humidity, wind speed, solar radiation
- Monthly aggregates (May–Sep): mean T2M, total precipitation, cumulative GDD (base 10°C), wet day count (>5mm)
- Growing Degree Day accumulation curve with soybean stage thresholds (R5, R7)
- 3-day and 7-day antecedent precipitation per NDVI scene date

### Dashboard output path
```
growers/ia-grower/farms/ia-grower-iowa/fields/osm-1360386537/derived/dashboards/field_dashboard_2025.html
```
Full-dashboard preview: [field_dashboard_2025_full.png](field_dashboard_2025_full.png)

### How to re-run
```bash
export DATA_PIPELINE_DATA_ROOT=/home/coder/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py
```
The dashboard HTML is a one-time artifact generated separately after the EDA
outputs are produced. Run the dashboard generation from the runtime venv using
the parent EDA outputs and per-field Sentinel/weather data.

### Known data limitations
- Weather data for IA and IL growers is limited to farm-level aggregated CSVs (3 of 10 fields per grower). NE grower has full per-field data.
- The Aug 28, 2025 Sentinel scene is 73.6% cloud-obscured — the exact peak NDVI value is uncertain.
- NDVI scene valid pixel percentages cluster at 87.1% due to shared raster extent; field-edge pixels are consistently NaN.
- CDL data is annual only — intra-season crop condition must be inferred from NDVI trajectory.
