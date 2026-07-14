---
name: field-level-eda
description: Generate field-level EDA visualizations comparing boundaries, CDL, and weather.
version: 1.0.0
tags: [eda, boundaries, cdl, weather, visualization]
---

# Guide: field-level-eda

## Description

Generates 9 static outputs (6 PNG visualizations + 3 CSV comparison tables)
comparing field boundaries, CDL cropland data, and weather across three
growers (Nebraska, Iowa, Illinois) with 30 total fields.

## Prerequisites

The data-pipeline runtime must be initialized with growers, field boundaries,
CDL composition data, and weather data.

## Usage

### Full analysis (all growers)

```bash
export DATA_PIPELINE_DATA_ROOT=/home/coder/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py
```

### Single grower

```bash
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py \
  --grower-slug ia-grower
```

### Custom year (2024–2025 supported)

```bash
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py \
  --year 2024
```

### Options

| Option | Default | Description |
|---|---|---|
| `--grower-slug` | (all growers) | Limit to a single grower |
| `--output-dir` | `derived/eda/` | Override output directory |

## Output files

```
growers/<g>/farms/<f>/derived/eda/
├── 01_boundaries_density.png
├── 02_field_attribute_heatmap.png
├── 03_boundaries_summary.csv
├── 04_cdl_crop_by_grower.png
├── 05_cdl_transition_heatmap.png
├── 06_cdl_stability.csv
├── 07_weather_single_field.png
├── 08_weather_grower_boxplot.png
└── 09_weather_gdd_curves.png
```

## Category details

### Boundaries
- **V1**: KDE density overlaid for all 3 growers (10 fields each) with rug ticks — shows distribution shape differences (NE bimodal, IA symmetric, IL right-skewed)
- **V2**: Hierarchical clustering heatmap of all 30 fields by acres + crop_2024 + crop_2025 + changed + grower — groups similar fields together using Ward linkage on standardized attributes
- **C1**: Per-grower summary (count, mean, median, std, min, max, skewness)

### CDL (2024–2025)
- **V1**: Grouped bar chart of crop acreage stacked by crop type, faceted by grower
- **V2**: 2024→2025 crop transition heatmap per grower — "rotation speed" via stability rate
- **C1**: Per-field rotation stability: changed boolean + grower-level stability %

### Weather (2024–2025, growing season May–Sep)
- **V1**: Dual-axis daily T2M + precipitation for osm-1360386537 (IA, full data)
- **V2**: Faceted box plots of May–Sep mean T2M and cumulative precipitation per grower
- **C1**: GDD (base 10°C) accumulation curves May–Sep 2025 per grower

## Data limitations

Only fields with actual weather data are included in Category 3 (NE: 10 fields,
IA: 3 fields, IL: 3 fields). Fields without weather data are silently excluded
from weather analyses.
