# Field-Level EDA — Local Instructions

## Purpose

Generate static statistical visualizations and comparison tables from
field boundaries, CDL cropland data, and weather in the data-pipeline runtime.

## Safe edit scope

Edits should stay in this folder and its children unless the user explicitly
asks for a broader skill change. Do not change parent `SKILL.md`, sibling
EDA workflows, or root policy from a subskill task unless explicitly requested.

## Read nearby docs first

Read `GUIDE.md` for usage, options, and output descriptions. Read `../INDEX.md`
and `../../AGENTS.md` for EDA routing and data-pipeline conventions.

## Runtime contract

- Requires `DATA_PIPELINE_DATA_ROOT` set to the absolute runtime root.
- Reads boundaries from `growers/<g>/farms/<f>/boundary/field_boundaries.geojson`.
- Reads CDL from `growers/<g>/farms/<f>/derived/tables/<f>_cdl_2021_2025_full_composition.csv`.
- Reads weather from `growers/<g>/farms/<f>/fields/<slug>/weather/daily_weather.csv`.
- If per-field weather is empty, falls back to `growers/<g>/farms/<f>/derived/tables/<f>_weather_2021_2025.csv`.
- Writes outputs to `growers/<g>/farms/<f>/derived/eda/`.
- Runs from the runtime source copy `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src`.

## Command runbook

```bash
export DATA_PIPELINE_DATA_ROOT=/home/coder/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py
```

Single grower:
```bash
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py \
  --grower-slug ia-grower
```

## Output manifest

9 files per run:
1. `01_boundaries_density.png` — KDE + rug plot, all growers
2. `02_field_attribute_heatmap.png` — hierarchical clustering heatmap
3. `03_boundaries_summary.csv` — size stats per grower
4. `04_cdl_crop_by_grower.png` — grouped bar 2024–2025
5. `05_cdl_transition_heatmap.png` — 2024→2025 crop transitions
6. `06_cdl_stability.csv` — per-field rotation stability
7. `07_weather_single_field.png` — T2M + precip for osm-1360386537
8. `08_weather_grower_boxplot.png` — grower-level T2M + precip boxes
9. `09_weather_gdd_curves.png` — GDD accumulation curves

## Data scope

- Years: 2024–2025 only
- Weather: only fields with actual data (NE=10, IA=3, IL=3)
- Representative single-field analyses use osm-1360386537 (IA-grower)

## Dependencies

`pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`, `geopandas` — all in runtime venv.

## Local validation

Run the script against the existing growers and verify all 9 output files
are generated with valid content.

## Local-delta-only reminder

This nested AGENTS.md only records instructions that differ from the parent
or root files. Do not duplicate root-wide asset, vendor, or validation policy
here except this pointer to `../../../AGENTS.md`.
