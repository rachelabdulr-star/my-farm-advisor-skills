#!/usr/bin/env python3
"""Field-level EDA: boundaries, CDL, and weather comparisons.

Generates 9 static outputs (6 PNG + 3 CSV) comparing field boundaries,
CDL cropland data (2024–2025), and weather across three growers.

Typical usage::

    export DATA_PIPELINE_DATA_ROOT=/home/coder/my-farm-advisor-runtime
    cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
    ../.venv/bin/python scripts/field-level-eda/run_field_level_eda.py
"""

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from scipy import stats

# ──────────────────────────────────────────────────────────────────
# Path helpers
# ──────────────────────────────────────────────────────────────────

def _data_root() -> Path:
    raw = os.environ.get("DATA_PIPELINE_DATA_ROOT", "")
    if not raw:
        sys.exit("DATA_PIPELINE_DATA_ROOT is not set")
    root = Path(raw)
    if not root.is_absolute():
        sys.exit(f"DATA_PIPELINE_DATA_ROOT must be absolute: {raw}")
    return root

def _runtime_base() -> Path:
    return _data_root() / "data-pipeline"

def _growers_dir() -> Path:
    return _runtime_base() / "growers"

def discover_growers(grower_slug: str | None = None) -> list[Path]:
    base = _growers_dir()
    if not base.is_dir():
        sys.exit(f"growers directory not found: {base}")
    if grower_slug:
        candidate = base / grower_slug
        if not candidate.is_dir():
            sys.exit(f"grower not found: {candidate}")
        return [candidate]
    return sorted(base / d.name for d in base.iterdir() if d.is_dir() and not d.name.startswith("."))

# ──────────────────────────────────────────────────────────────────
# Data loaders
# ──────────────────────────────────────────────────────────────────

def load_boundaries(grower_path: Path, farm_filter: str | None = None) -> pd.DataFrame:
    rows = []
    farms_dir = grower_path / "farms"
    if not farms_dir.is_dir():
        return pd.DataFrame()
    for farm_entry in sorted(farms_dir.iterdir()):
        if not farm_entry.is_dir():
            continue
        if farm_filter and farm_entry.name != farm_filter:
            continue
        geo_file = farm_entry / "boundary" / "field_boundaries.geojson"
        if not geo_file.is_file():
            continue
        with open(geo_file) as f:
            geo = json.load(f)
        for feat in geo["features"]:
            props = feat["properties"]
            geom = feat.get("geometry", {})
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates", [])
            lon = lat = None
            try:
                if geom_type == "Polygon" and coords:
                    outer = coords[0]
                    lons = [pt[0] for pt in outer]
                    lats = [pt[1] for pt in outer]
                elif geom_type == "MultiPolygon" and coords:
                    outer = coords[0][0]
                    lons = [pt[0] for pt in outer]
                    lats = [pt[1] for pt in outer]
                else:
                    continue
                if lons and lats:
                    lon, lat = np.mean(lons), np.mean(lats)
            except (IndexError, TypeError):
                pass
            rows.append({
                "grower": grower_path.name,
                "farm": farm_entry.name,
                "field_id": props.get("field_id", ""),
                "acres": float(props.get("area_acres", 0)),
                "lon": lon,
                "lat": lat,
            })
    return pd.DataFrame(rows)

def load_cdl(grower_path: Path, farm_filter: str | None = None) -> pd.DataFrame:
    rows = []
    farms_dir = grower_path / "farms"
    if not farms_dir.is_dir():
        return pd.DataFrame()
    for farm_entry in sorted(farms_dir.iterdir()):
        if not farm_entry.is_dir():
            continue
        if farm_filter and farm_entry.name != farm_filter:
            continue
        cdl_file = farm_entry / "derived" / "tables" / f"{farm_entry.name.replace('-','_')}_cdl_2021_2025_full_composition.csv"
        if not cdl_file.is_file():
            continue
        df = pd.read_csv(cdl_file)
        df["grower"] = grower_path.name
        df["farm"] = farm_entry.name
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)

def load_weather_for_field(field_dir: Path, field_id: str, grower: str, farm: str,
                           farm_weather_df: pd.DataFrame | None = None) -> pd.DataFrame:
    wcsv = field_dir / "weather" / "daily_weather.csv"
    if wcsv.is_file():
        df = pd.read_csv(wcsv)
        if "field_id" not in df.columns:
            return pd.DataFrame()
        df = df[df["field_id"] == field_id].copy()
        if len(df) > 0 and df["date"].str.contains("2024|2025").any():
            df["grower"] = grower
            df["farm"] = farm
            return df

    if farm_weather_df is not None and not farm_weather_df.empty:
        fwf = farm_weather_df[farm_weather_df["field_id"] == field_id].copy()
        if len(fwf) > 0:
            fwf["grower"] = grower
            fwf["farm"] = farm
            return fwf

    return pd.DataFrame()

def load_all_weather(grower_path: Path, farm_filter: str | None = None) -> pd.DataFrame:
    frames = []
    farms_dir = grower_path / "farms"
    if not farms_dir.is_dir():
        return pd.DataFrame()
    for farm_entry in sorted(farms_dir.iterdir()):
        if not farm_entry.is_dir():
            continue
        if farm_filter and farm_entry.name != farm_filter:
            continue
        farm_weather = farm_entry / "derived" / "tables" / f"{farm_entry.name.replace('-','_')}_weather_2021_2025.csv"
        fw_df = pd.read_csv(farm_weather) if farm_weather.is_file() else pd.DataFrame()
        fields_dir = farm_entry / "fields"
        if not fields_dir.is_dir():
            continue
        for field_entry in sorted(fields_dir.iterdir()):
            if not field_entry.is_dir():
                continue
            wdf = load_weather_for_field(field_entry, field_entry.name, grower_path.name, farm_entry.name, fw_df)
            if not wdf.empty:
                frames.append(wdf)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# ──────────────────────────────────────────────────────────────────
# Category 1: Field Boundaries
# ──────────────────────────────────────────────────────────────────

def viz_boundaries_density(boundaries_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = {"ne-grower": "#e74c3c", "ia-grower": "#2980b9", "il-grower": "#27ae60"}
    labels = {"ne-grower": "Nebraska (NE)", "ia-grower": "Iowa (IA)", "il-grower": "Illinois (IL)"}

    for grower in ["ia-grower", "il-grower", "ne-grower"]:
        gdf = boundaries_df[boundaries_df["grower"] == grower]
        if gdf.empty:
            continue
        sns.kdeplot(data=gdf, x="acres", ax=ax, color=colors.get(grower, "#333"),
                    fill=True, alpha=0.18, linewidth=2.2, label=labels.get(grower, grower))
        ax.plot(gdf["acres"].values, [-0.0002] * len(gdf), "|", color=colors.get(grower, "#333"),
                markersize=10, markeredgewidth=1.5, alpha=0.7)

    ax.set_xlabel("Field Size (acres)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.set_title("Field Size Distribution by Grower\n(10 fields per grower, 3 distinct distribution shapes)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, framealpha=0.9)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=-0.001, top=None)
    ax.grid(axis="y", alpha=0.3)
    sns.despine()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"  -> {out_path}")

def viz_field_attribute_heatmap(boundaries_df: pd.DataFrame, cdl_df: pd.DataFrame, out_path: Path) -> None:
    if boundaries_df.empty:
        return

    # Build crop columns from CDL
    crop_map = {}
    if not cdl_df.empty:
        for yr in [2024, 2025]:
            yr_df = cdl_df[cdl_df["year"] == yr].groupby(["grower", "field_id"])["crop_name"].first().reset_index()
            for _, r in yr_df.iterrows():
                key = (r["grower"], r["field_id"])
                crop_map.setdefault(key, {})[f"crop_{yr}"] = r["crop_name"]

    # Build merged dataset
    rows = []
    for _, b in boundaries_df.iterrows():
        key = (b["grower"], b["field_id"])
        rows.append({
            "field_id": b["field_id"],
            "grower": b["grower"],
            "acres": b["acres"],
            "crop_2024": crop_map.get(key, {}).get("crop_2024", "Unknown"),
            "crop_2025": crop_map.get(key, {}).get("crop_2025", "Unknown"),
        })
    mdf = pd.DataFrame(rows)
    mdf["changed"] = (mdf["crop_2024"] != mdf["crop_2025"]).astype(int)

    # Encode categoricals
    grower_map = {"ne-grower": 0, "ia-grower": 1, "il-grower": 2}
    all_crops = sorted(set(mdf["crop_2024"].unique()) | set(mdf["crop_2025"].unique()))
    crop_enc = {c: i for i, c in enumerate(all_crops)}
    mdf["grower_code"] = mdf["grower"].map(grower_map).fillna(-1).astype(int)
    mdf["crop24_code"] = mdf["crop_2024"].map(crop_enc).fillna(-1).astype(int)
    mdf["crop25_code"] = mdf["crop_2025"].map(crop_enc).fillna(-1).astype(int)

    # Clustering matrix
    matrix = mdf[["acres", "crop24_code", "crop25_code", "changed", "grower_code"]].copy()
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    matrix_scaled = pd.DataFrame(scaled, index=mdf["field_id"], columns=matrix.columns)

    # Row labels
    row_labels = mdf.apply(
        lambda r: f"{r['field_id'][:12]} ({r['grower'][:2]})", axis=1
    ).values

    # Grower colors for row sidebar
    grower_colors = {"ne-grower": "#e74c3c", "ia-grower": "#2980b9", "il-grower": "#27ae60"}
    row_colors = mdf["grower"].map(grower_colors).values

    # Column display names
    col_display = ["Acres", "Crop 2024", "Crop 2025", "Changed", "Grower"]

    g = sns.clustermap(
        matrix_scaled,
        method="ward",
        metric="euclidean",
        cmap="RdBu_r",
        center=0,
        row_cluster=True, col_cluster=False,
        row_colors=row_colors,
        xticklabels=col_display,
        yticklabels=row_labels,
        figsize=(10, 12),
        dendrogram_ratio=(0.12, 0.05),
        cbar_pos=(0.02, 0.82, 0.02, 0.12),
        linewidths=0.5,
        annot=False,
    )
    g.ax_heatmap.set_xticklabels(g.ax_heatmap.get_xticklabels(), rotation=30, ha="right", fontsize=9)
    g.ax_heatmap.set_yticklabels(g.ax_heatmap.get_yticklabels(), fontsize=7)
    g.ax_cbar.set_ylabel("Standardized Value", fontsize=8)

    gax = g.ax_heatmap
    gax.set_title(
        "Field Attribute Clustering\n"
        "acres · crop_2024 · crop_2025 · changed · grower\n"
        "Ward linkage, euclidean distance on standardized values",
        fontsize=13, fontweight="bold", pad=25
    )

    # Legend for row color bar
    from matplotlib.patches import Patch
    legend_els = [Patch(facecolor=c, label=g) for g, c in grower_colors.items()]
    g.ax_heatmap.legend(
        handles=legend_els, title="Grower", fontsize=7, title_fontsize=8,
        loc="upper left", bbox_to_anchor=(0.01, 1.02), ncol=3, framealpha=0.9
    )

    # Annotate crop encoding
    crop_note = "Crop codes: " + " | ".join(f"{i}={c}" for c, i in crop_enc.items())
    gax.annotate(crop_note, xy=(0.5, -0.06), xycoords="axes fraction",
                 ha="center", fontsize=7, color="#555")

    g.savefig(out_path, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(g.figure)
    print(f"  -> {out_path}")

def comparison_boundaries_summary(boundaries_df: pd.DataFrame, out_path: Path) -> None:
    rows = []
    for grower in sorted(boundaries_df["grower"].unique()):
        gdf = boundaries_df[boundaries_df["grower"] == grower]
        vals = gdf["acres"]
        rows.append({
            "grower": grower,
            "field_count": len(gdf),
            "total_acres": round(vals.sum(), 2),
            "mean_acres": round(vals.mean(), 2),
            "median_acres": round(vals.median(), 2),
            "std_acres": round(vals.std(ddof=1), 2),
            "min_acres": round(vals.min(), 2),
            "max_acres": round(vals.max(), 2),
            "skewness": round(float(stats.skew(vals)), 3),
        })

    gj = boundaries_df["grower"].unique()
    if len(gj) >= 2:
        groups = [boundaries_df[boundaries_df["grower"] == g]["acres"].values for g in gj]
        try:
            f_stat, p_val = stats.f_oneway(*groups)
            anova_verdict = f"F={f_stat:.3f}, p={p_val:.4f} -- {'significant' if p_val < 0.05 else 'not significant'} difference across growers"
        except Exception:
            anova_verdict = "ANOVA could not be computed"
    else:
        anova_verdict = "Need >= 2 growers for ANOVA"

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(out_path, index=False)
    with open(out_path, "a") as f:
        f.write(f"\n# ANOVA (one-way, mean field size across growers):\n# {anova_verdict}\n")
    print(f"  -> {out_path}")
    print(f"  ANOVA: {anova_verdict}")

# ──────────────────────────────────────────────────────────────────
# Category 2: CDL
# ──────────────────────────────────────────────────────────────────

def viz_cdl_crop_by_grower(cdl_df: pd.DataFrame, out_path: Path, years: list[int]) -> None:
    cdl_filt = cdl_df[cdl_df["year"].isin(years)].copy()
    if cdl_filt.empty:
        return
    cdl_filt["acres_est"] = cdl_filt["pixel_count"].astype(float) * 900 * 0.000247105  # 30m pixel to acres
    grower_yc = cdl_filt.groupby(["grower", "year", "crop_name"])["acres_est"].sum().reset_index()

    growers = sorted(grower_yc["grower"].unique())
    n = len(growers)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 5.5), sharey=True)
    if n == 1:
        axes = [axes]

    crop_colors = {"Corn": "#f1c40f", "Soybeans": "#27ae60", "Winter Wheat": "#e67e22",
                   "Fallow/Idle Cropland": "#95a5a6", "Grass/Pasture": "#2ecc71",
                   "Alfalfa": "#9b59b6", "Forest": "#1abc9c"}
    color_map = {c: crop_colors.get(c, "#bbb") for c in grower_yc["crop_name"].unique()}

    for ax, grower in zip(axes, growers):
        gdf = grower_yc[grower_yc["grower"] == grower]
        pivot = gdf.pivot_table(index="year", columns="crop_name", values="acres_est", fill_value=0)
        pivot = pivot[sorted(pivot.columns, key=lambda c: gdf[gdf["crop_name"] == c]["acres_est"].sum(), reverse=True)]
        bar_colors = [color_map.get(c, "#bbb") for c in pivot.columns]
        pivot.plot(kind="bar", stacked=False, ax=ax, color=bar_colors, edgecolor="white", linewidth=0.5, legend=False)
        label = {"ne-grower": "Nebraska", "ia-grower": "Iowa", "il-grower": "Illinois"}.get(grower, grower)
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.set_xlabel("")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Crop Acres (CDL-derived)", fontsize=11)
    handles, labels_ax = axes[-1].get_legend_handles_labels()
    fig.legend(handles, [c for c in pivot.columns], title="Crop Type", fontsize=9, title_fontsize=10,
               loc="lower center", ncol=min(6, len(pivot.columns)), bbox_to_anchor=(0.5, -0.08))
    fig.suptitle("Crop Acreage by Grower and Year (CDL)", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    fig.savefig(out_path, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {out_path}")

def viz_cdl_transition_heatmap(cdl_df: pd.DataFrame, cdl_rot_df: pd.DataFrame, out_path: Path) -> None:
    cdl2024 = cdl_df[cdl_df["year"] == 2024].groupby(["grower", "field_id"])["crop_name"].apply(
        lambda x: x.iloc[0] if len(x) > 0 else "Unknown"
    ).reset_index()
    cdl2025 = cdl_df[cdl_df["year"] == 2025].groupby(["grower", "field_id"])["crop_name"].apply(
        lambda x: x.iloc[0] if len(x) > 0 else "Unknown"
    ).reset_index()

    merged = cdl2024.merge(cdl2025, on=["grower", "field_id"], suffixes=("_2024", "_2025"))
    merged["transition"] = merged["crop_name_2024"] + " → " + merged["crop_name_2025"]

    growers = sorted(merged["grower"].unique())
    n = len(growers)
    fig, axes = plt.subplots(1, n, figsize=(7 * n, 5.5))
    if n == 1:
        axes = [axes]

    for ax, grower in zip(axes, growers):
        gdf = merged[merged["grower"] == grower]
        if gdf.empty:
            continue
        pivot = gdf.groupby(["crop_name_2024", "crop_name_2025"]).size().unstack(fill_value=0)
        sns.heatmap(pivot, annot=True, fmt="d", cmap="YlOrRd", ax=ax, linewidths=0.5,
                    cbar_kws={"label": "Field Count", "shrink": 0.75})
        label = {"ne-grower": "Nebraska", "ia-grower": "Iowa", "il-grower": "Illinois"}.get(grower, grower)
        ax.set_title(f"{label}\n2024 → 2025", fontsize=12, fontweight="bold")
        ax.set_xlabel("2025 Crop", fontsize=10)
        ax.set_ylabel("2024 Crop", fontsize=10)
        ax.tick_params(axis="both", labelsize=9)

    fig.suptitle("Crop Transition Matrix by Grower (2024 → 2025)", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {out_path}")

def comparison_cdl_stability(cdl_df: pd.DataFrame, out_path: Path) -> None:
    cdl2024 = cdl_df[cdl_df["year"] == 2024].groupby(["grower", "farm", "field_id"])["crop_name"].first().reset_index()
    cdl2024.columns = ["grower", "farm", "field_id", "crop_2024"]
    cdl2025 = cdl_df[cdl_df["year"] == 2025].groupby(["grower", "farm", "field_id"])["crop_name"].first().reset_index()
    cdl2025.columns = ["grower", "farm", "field_id", "crop_2025"]

    merged = cdl2024.merge(cdl2025, on=["grower", "farm", "field_id"])
    merged["changed"] = merged["crop_2024"] != merged["crop_2025"]

    merged.to_csv(out_path, index=False)

    print(f"  -> {out_path}")
    for grower in sorted(merged["grower"].unique()):
        gdf = merged[merged["grower"] == grower]
        stable = (~gdf["changed"]).sum()
        rate = stable / len(gdf) * 100
        changed = gdf[gdf["changed"]]
        pattern = "; ".join(f"{r['crop_2024']}→{r['crop_2025']}" for _, r in changed.iterrows())
        print(f"  {grower}: {stable}/{len(gdf)} stable ({rate:.0f}%) — changes: {pattern}")

# ──────────────────────────────────────────────────────────────────
# Category 3: Weather
# ──────────────────────────────────────────────────────────────────

REP_FIELD = "osm-1360386537"

def _prepare_weather_df(weather_df: pd.DataFrame) -> pd.DataFrame:
    df = weather_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year
    for c in ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "RH2M", "WS10M"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _compute_gdd(df: pd.DataFrame, base: float = 10.0) -> pd.DataFrame:
    gdd_df = df.copy()
    gdd_df["T2M_mean"] = (gdd_df["T2M_MAX"] + gdd_df["T2M_MIN"]) / 2
    gdd_df["GDD"] = (gdd_df["T2M_mean"] - base).clip(lower=0)
    return gdd_df

def viz_weather_single_field(weather_df: pd.DataFrame, out_path: Path) -> None:
    wdf = _prepare_weather_df(weather_df)
    rep = wdf[(wdf["field_id"] == REP_FIELD) & (wdf["year"] == 2025) & (wdf["month"] >= 5) & (wdf["month"] <= 9)]
    if rep.empty:
        print(f"  SKIP V1: {REP_FIELD} has no 2025 May–Sep weather data")
        return
    rep = rep.sort_values("date")

    fig, ax1 = plt.subplots(figsize=(13, 5.5))
    ax1.fill_between(rep["date"], rep["T2M_MIN"], rep["T2M_MAX"], alpha=0.2, color="#e74c3c", label="T2M min–max range")
    ax1.plot(rep["date"], rep["T2M"], color="#c0392b", linewidth=2, label="T2M (mean °C)")
    ax1.set_ylabel("Temperature (°C)", fontsize=11, color="#c0392b")
    ax1.tick_params(axis="y", labelcolor="#c0392b")
    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9)

    ax2 = ax1.twinx()
    bars = ax2.bar(rep["date"], rep["PRECTOTCORR"], width=1.0, color="#2980b9", alpha=0.55, label="Precipitation (mm)")
    ax2.set_ylabel("Precipitation (mm)", fontsize=11, color="#2980b9")
    ax2.tick_params(axis="y", labelcolor="#2980b9")
    ax2.legend(loc="upper right", fontsize=9)

    grower_name = rep["grower"].iloc[0] if "grower" in rep.columns else "ia-grower"
    ax1.set_title(f"Weather for {REP_FIELD} ({grower_name})\nMay–September 2025", fontsize=13, fontweight="bold")
    ax1.set_xlabel("")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"  -> {out_path}")

def viz_weather_grower_boxplot(weather_df: pd.DataFrame, out_path: Path) -> None:
    wdf = _prepare_weather_df(weather_df)
    growing = wdf[(wdf["month"] >= 5) & (wdf["month"] <= 9) & (wdf["year"].isin([2024, 2025]))]
    if growing.empty:
        return

    season_stats = growing.groupby(["grower", "field_id", "year"]).agg(
        mean_T2M=("T2M", "mean"),
        total_precip=("PRECTOTCORR", "sum"),
    ).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    sns.boxplot(data=season_stats, x="grower", y="mean_T2M", hue="grower", ax=axes[0],
                palette={"ne-grower": "#e74c3c", "ia-grower": "#2980b9", "il-grower": "#27ae60"}, legend=False)
    sns.stripplot(data=season_stats, x="grower", y="mean_T2M", ax=axes[0], color="black", size=5, alpha=0.5, jitter=True)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Mean T2M (°C) May–Sep", fontsize=11)
    axes[0].set_title("Growing Season Temperature", fontsize=12, fontweight="bold")
    axes[0].grid(axis="y", alpha=0.3)

    sns.boxplot(data=season_stats, x="grower", y="total_precip", hue="grower", ax=axes[1],
                palette={"ne-grower": "#e74c3c", "ia-grower": "#2980b9", "il-grower": "#27ae60"}, legend=False)
    sns.stripplot(data=season_stats, x="grower", y="total_precip", ax=axes[1], color="black", size=5, alpha=0.5, jitter=True)
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Total Precipitation (mm) May–Sep", fontsize=11)
    axes[1].set_title("Growing Season Precipitation", fontsize=12, fontweight="bold")
    axes[1].grid(axis="y", alpha=0.3)

    n_fields = season_stats.groupby("grower")["field_id"].nunique()
    subtitle = " | ".join(f"{g}: {n_fields.get(g, 0)} fields" for g in ["ne-grower", "ia-grower", "il-grower"])
    fig.suptitle(f"Growing Season Weather by Grower (May–Sep 2024–2025)\n{subtitle}",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {out_path}")

def comparison_weather_gdd(weather_df: pd.DataFrame, out_path: Path) -> None:
    wdf = _prepare_weather_df(weather_df)
    gdd_df = _compute_gdd(wdf)
    gdd_2025 = gdd_df[(gdd_df["year"] == 2025) & (gdd_df["month"] >= 5) & (gdd_df["month"] <= 9)].copy()
    if gdd_2025.empty:
        print("  SKIP GDD: no 2025 May–Sep weather data")
        return

    gdd_2025["doy"] = gdd_2025["date"].dt.dayofyear
    gdd_2025["GDD_cum"] = gdd_2025.groupby(["grower", "field_id"])["GDD"].cumsum()

    growers = sorted(gdd_2025["grower"].unique())
    colors = {"ne-grower": "#e74c3c", "ia-grower": "#2980b9", "il-grower": "#27ae60"}

    fig, ax = plt.subplots(figsize=(10, 5.5))

    for grower in growers:
        gdf = gdd_2025[gdd_2025["grower"] == grower]
        if gdf.empty:
            continue
        for fid in gdf["field_id"].unique():
            fdf = gdf[gdf["field_id"] == fid].sort_values("doy")
            ax.plot(fdf["doy"], fdf["GDD_cum"], color=colors.get(grower, "#999"), alpha=0.25, linewidth=0.8)
        mean_curve = gdf.groupby("doy")["GDD_cum"].mean().sort_index()
        label = {"ne-grower": "Nebraska", "ia-grower": "Iowa", "il-grower": "Illinois"}.get(grower, grower)
        ax.plot(mean_curve.index, mean_curve.values, color=colors.get(grower, "#333"), linewidth=3, label=label)

    ax.set_xlabel("Day of Year (2025)", fontsize=11)
    ax.set_ylabel("Cumulative GDD (base 10°C)", fontsize=11)
    ax.set_title("Growing Degree Day Accumulation by Grower\n(May–Sep 2025, base 10°C)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, framealpha=0.9)
    ax.grid(alpha=0.3)
    ax.set_xlim(121, 273)  # May 1 – Sep 30

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"  -> {out_path}")

# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Field-level EDA: boundaries, CDL, weather")
    parser.add_argument("--grower-slug", help="Limit to a single grower")
    parser.add_argument("--output-dir", help="Override output directory")
    args = parser.parse_args()

    growers = discover_growers(args.grower_slug)
    print(f"Field-Level EDA: {len(growers)} grower(s)")

    # ── Collect all data ──────────────────────────────────────────
    boundaries_list, cdl_list, weather_list = [], [], []
    for gpath in growers:
        boundaries_list.append(load_boundaries(gpath))
        cdl_list.append(load_cdl(gpath))
        weather_list.append(load_all_weather(gpath))

    boundaries_df = pd.concat(boundaries_list, ignore_index=True) if boundaries_list else pd.DataFrame()
    cdl_df = pd.concat(cdl_list, ignore_index=True) if cdl_list else pd.DataFrame()
    weather_df = pd.concat(weather_list, ignore_index=True) if weather_list else pd.DataFrame()

    print(f"  Boundaries: {len(boundaries_df)} fields")
    print(f"  CDL rows: {len(cdl_df)}")
    print(f"  Weather rows: {len(weather_df)} — {weather_df['field_id'].nunique() if not weather_df.empty else 0} fields with data")

    # ── Determine output directory ────────────────────────────────
    if args.output_dir:
        out_base = Path(args.output_dir)
    else:
        first_grower = growers[0].name
        farms_dir = growers[0] / "farms"
        first_farm = next((f for f in farms_dir.iterdir() if f.is_dir()), None)
        if first_farm:
            out_base = first_farm / "derived" / "eda"
        else:
            out_base = Path("derived/eda")
    out_base.mkdir(parents=True, exist_ok=True)

    # ── Category 1: Boundaries ────────────────────────────────────
    print("\n=== Category 1: Field Boundaries ===")
    if not boundaries_df.empty:
        viz_boundaries_density(boundaries_df, out_base / "01_boundaries_density.png")
        viz_field_attribute_heatmap(boundaries_df, cdl_df, out_base / "02_field_attribute_heatmap.png")
        comparison_boundaries_summary(boundaries_df, out_base / "03_boundaries_summary.csv")
    else:
        print("  SKIP: no boundary data")

    # ── Category 2: CDL ───────────────────────────────────────────
    print("\n=== Category 2: CDL / Cropland ===")
    if not cdl_df.empty:
        cdl_df["pixel_count"] = pd.to_numeric(cdl_df["pixel_count"], errors="coerce")
        cdl_df["year"] = pd.to_numeric(cdl_df["year"], errors="coerce")
        viz_cdl_crop_by_grower(cdl_df, out_base / "04_cdl_crop_by_grower.png", [2024, 2025])
        viz_cdl_transition_heatmap(cdl_df, cdl_df, out_base / "05_cdl_transition_heatmap.png")
        comparison_cdl_stability(cdl_df, out_base / "06_cdl_stability.csv")
    else:
        print("  SKIP: no CDL data")

    # ── Category 3: Weather ───────────────────────────────────────
    print("\n=== Category 3: Weather ===")
    if not weather_df.empty:
        viz_weather_single_field(weather_df, out_base / "07_weather_single_field.png")
        viz_weather_grower_boxplot(weather_df, out_base / "08_weather_grower_boxplot.png")
        comparison_weather_gdd(weather_df, out_base / "09_weather_gdd_curves.png")
    else:
        print("  SKIP: no weather data with 2024–2025 coverage")

    print(f"\nDone. Outputs in {out_base}/")

if __name__ == "__main__":
    main()
