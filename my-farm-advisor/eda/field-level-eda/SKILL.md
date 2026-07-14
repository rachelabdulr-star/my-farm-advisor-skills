---
name: field-level-eda
description: Generate statistical visualizations comparing field boundaries, CDL crop data, and weather across growers, farms, and fields.
version: 1.0.0
tags: [eda, field-boundaries, cdl, weather, visualization, comparison]
---

# Skill: field-level-eda

Generate static PNG visualizations and CSV comparison tables from the
data-pipeline runtime, comparing field boundaries, cropland data, and
weather across within-field, across-field, and across-grower levels.

## Routing

- [GUIDE.md](GUIDE.md) — usage, options, and output descriptions
- [AGENTS.md](AGENTS.md) — agent instructions
- [run_field_level_eda.py](src/run_field_level_eda.py) — the generator script

## When to use

- The user wants statistical visualizations of field sizes, crop rotations, or weather.
- The data pipeline has populated boundaries, CDL, and weather for at least one grower.
- The user needs static outputs (PNG, CSV) for review or downstream report assembly.

## Quick start

```bash
export DATA_PIPELINE_DATA_ROOT=/home/coder/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py
```
