from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, Tuple

import matplotlib
matplotlib.use("Agg")

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree


EARTH_RADIUS_M = 6371000.0
FEET_TO_METERS = 0.3048
WS1_FINAL_CSV_TOTAL_ROWS = 2455221
WS1_ZERO_READINGS_PCT = 23.12
WS1_CUTOFF_LUX = 0.5567
WS1_CAP_LUX = 24.7667
WS1_BASELINE_NON_ZERO_UNDERPERFORMING_PCT = 20.33
WS1_FINAL_CSV_LOW_PERFORMANCE_PCT = 38.75

REQUIRED_LUX_COLUMNS = {
    "Latitude",
    "Longitude",
    "Lux_mean",
    "Lux_mean_capped",
    "low_performance",
}

STREETLIGHT_REQUIRED_COLUMNS = {"FACILITYID", "lat_", "long_"}
TRAFFIC_REQUIRED_COLUMNS = {"ASSETID", "lat_", "long_"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WS2 asset-level aggregation and prioritization for LumiTracker."
    )
    parser.add_argument("--input-lux", required=True, help="Path to workstream1_clean_lux.csv")
    parser.add_argument("--streetlights", required=True, help="Path to city streetlight xlsx")
    parser.add_argument("--traffic-lights", required=True, help="Path to traffic roadway lights xlsx")
    parser.add_argument("--avalon-pdf", required=False, default="", help="Path to Avalon PDF reference")
    parser.add_argument("--output-dir", required=True, help="Output directory for WS2 results")
    parser.add_argument("--max-distance-ft", type=float, default=100.0, help="Nearest-neighbor tolerance in feet")
    parser.add_argument("--min-observations", type=int, default=20, help="Minimum observations for reliable asset classification")
    parser.add_argument("--asset-flag-threshold", type=float, default=0.30, help="Operational asset flag threshold")
    parser.add_argument("--chunksize", type=int, default=250000, help="CSV chunk size for processing")
    return parser.parse_args()


def validate_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def load_excel_sheet(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1")
    if df.empty:
        raise ValueError(f"{path.name} Sheet1 is empty.")
    return df


def load_asset_layers(streetlights_path: Path, traffic_path: Path) -> pd.DataFrame:
    streetlights = load_excel_sheet(streetlights_path)
    traffic = load_excel_sheet(traffic_path)

    validate_columns(streetlights, STREETLIGHT_REQUIRED_COLUMNS, "Streetlight layer")
    validate_columns(traffic, TRAFFIC_REQUIRED_COLUMNS, "Traffic roadway layer")

    streetlights = streetlights.rename(
        columns={
            "FACILITYID": "asset_id",
            "lat_": "asset_latitude",
            "long_": "asset_longitude",
        }
    ).copy()
    streetlights["asset_source"] = "city_streetlight"

    traffic = traffic.rename(
        columns={
            "ASSETID": "asset_id",
            "lat_": "asset_latitude",
            "long_": "asset_longitude",
        }
    ).copy()
    traffic["asset_source"] = "traffic_roadway_light"

    streetlights["asset_id"] = streetlights["asset_id"].astype(str)
    traffic["asset_id"] = traffic["asset_id"].astype(str)

    traffic["SUBTYPE"] = traffic["SUBTYPE"].astype(str).str.strip()
    traffic = traffic[~traffic["SUBTYPE"].str.contains("Service Meter", case=False, na=False)].copy()

    keep_streetlight_cols = [c for c in streetlights.columns if c in {
        "asset_id", "asset_latitude", "asset_longitude", "asset_source", "FIXTUREWAT", "LASTUPDATE"
    }]
    keep_traffic_cols = [c for c in traffic.columns if c in {
        "asset_id", "asset_latitude", "asset_longitude", "asset_source",
        "Pole ID", "Roadway", "Fixture Type", "Power Wattage", "Life Cycle", "SUBTYPE"
    }]

    streetlights = streetlights[keep_streetlight_cols].copy()
    traffic = traffic[keep_traffic_cols].copy()

    assets = pd.concat([streetlights, traffic], ignore_index=True)

    assets["asset_latitude"] = pd.to_numeric(assets["asset_latitude"], errors="coerce")
    assets["asset_longitude"] = pd.to_numeric(assets["asset_longitude"], errors="coerce")
    assets = assets.dropna(subset=["asset_latitude", "asset_longitude"]).copy()

    assets = assets[
        assets["asset_latitude"].between(-90, 90) &
        assets["asset_longitude"].between(-180, 180)
    ].copy()

    assets = assets.drop_duplicates(subset=["asset_source", "asset_id"]).reset_index(drop=True)

    if assets.empty:
        raise ValueError("No valid asset coordinates were found after loading GIS layers.")

    assets["asset_index"] = np.arange(len(assets))
    return assets


def build_balltree(assets: pd.DataFrame) -> BallTree:
    asset_coords_rad = np.radians(assets[["asset_latitude", "asset_longitude"]].to_numpy())
    return BallTree(asset_coords_rad, metric="haversine")


def iter_lux_chunks(path: Path, chunksize: int) -> Iterable[pd.DataFrame]:
    return pd.read_csv(path, chunksize=chunksize)


def prepare_lux_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    validate_columns(chunk, REQUIRED_LUX_COLUMNS, "LumiTracker cleaned file")

    chunk = chunk.copy().reset_index(drop=True)

    for col in ["Latitude", "Longitude", "Lux_mean", "Lux_mean_capped", "low_performance"]:
        chunk[col] = pd.to_numeric(chunk[col], errors="coerce")

    chunk = chunk.dropna(subset=["Latitude", "Longitude", "Lux_mean", "Lux_mean_capped", "low_performance"]).copy()

    chunk = chunk[
        chunk["Latitude"].between(-90, 90) &
        chunk["Longitude"].between(-180, 180)
    ].copy()

    chunk["low_performance"] = chunk["low_performance"].astype(int)
    return chunk.reset_index(drop=True)


def match_chunk_to_assets(
    chunk: pd.DataFrame,
    tree: BallTree,
    max_distance_ft: float,
) -> pd.DataFrame:
    if chunk.empty:
        return pd.DataFrame(
            columns=["asset_index", "low_performance", "Lux_mean", "Lux_mean_capped", "matched_distance_ft"]
        )

    lux_coords_rad = np.radians(chunk[["Latitude", "Longitude"]].to_numpy())
    distances_rad, indices = tree.query(lux_coords_rad, k=1)

    distances_m = distances_rad[:, 0] * EARTH_RADIUS_M
    distances_ft = distances_m / FEET_TO_METERS
    asset_indices = indices[:, 0]

    within_tolerance = distances_ft <= max_distance_ft
    if not np.any(within_tolerance):
        return pd.DataFrame(
            columns=["asset_index", "low_performance", "Lux_mean", "Lux_mean_capped", "matched_distance_ft"]
        )

    matched = pd.DataFrame({
        "asset_index": asset_indices[within_tolerance],
        "low_performance": chunk.loc[within_tolerance, "low_performance"].to_numpy(),
        "Lux_mean": chunk.loc[within_tolerance, "Lux_mean"].to_numpy(),
        "Lux_mean_capped": chunk.loc[within_tolerance, "Lux_mean_capped"].to_numpy(),
        "matched_distance_ft": distances_ft[within_tolerance],
    })
    return matched


def update_stats(stats: Dict[int, Dict[str, float]], matched: pd.DataFrame) -> None:
    if matched.empty:
        return

    grouped = matched.groupby("asset_index", as_index=False).agg(
        observation_count=("asset_index", "size"),
        low_performance_count=("low_performance", "sum"),
        lux_mean_sum=("Lux_mean", "sum"),
        lux_mean_capped_sum=("Lux_mean_capped", "sum"),
        distance_ft_sum=("matched_distance_ft", "sum"),
    )

    for row in grouped.itertuples(index=False):
        idx = int(row.asset_index)
        current = stats.setdefault(
            idx,
            {
                "observation_count": 0.0,
                "low_performance_count": 0.0,
                "lux_mean_sum": 0.0,
                "lux_mean_capped_sum": 0.0,
                "distance_ft_sum": 0.0,
            },
        )
        current["observation_count"] += float(row.observation_count)
        current["low_performance_count"] += float(row.low_performance_count)
        current["lux_mean_sum"] += float(row.lux_mean_sum)
        current["lux_mean_capped_sum"] += float(row.lux_mean_capped_sum)
        current["distance_ft_sum"] += float(row.distance_ft_sum)


def finalize_asset_metrics(
    assets: pd.DataFrame,
    stats: Dict[int, Dict[str, float]],
    min_observations: int,
    asset_flag_threshold: float,
) -> pd.DataFrame:
    records = []
    for idx, values in stats.items():
        observation_count = int(values["observation_count"])
        low_count = int(values["low_performance_count"])
        pct_low = low_count / observation_count if observation_count > 0 else np.nan
        mean_lux = values["lux_mean_sum"] / observation_count if observation_count > 0 else np.nan
        mean_lux_capped = values["lux_mean_capped_sum"] / observation_count if observation_count > 0 else np.nan
        mean_distance_ft = values["distance_ft_sum"] / observation_count if observation_count > 0 else np.nan

        records.append({
            "asset_index": idx,
            "observation_count": observation_count,
            "low_performance_count": low_count,
            "pct_low_performance": pct_low,
            "mean_lux_mean": mean_lux,
            "mean_lux_mean_capped": mean_lux_capped,
            "mean_matched_distance_ft": mean_distance_ft,
        })

    metrics = pd.DataFrame(records)
    if metrics.empty:
        raise ValueError("No observations matched to assets within the specified tolerance.")

    asset_level = assets.merge(metrics, on="asset_index", how="inner").copy()

    asset_level["asset_flag"] = (
        (asset_level["observation_count"] >= min_observations) &
        (asset_level["pct_low_performance"] >= asset_flag_threshold)
    )

    conditions = [
        asset_level["observation_count"] < min_observations,
        asset_level["pct_low_performance"] >= 0.50,
        asset_level["pct_low_performance"] >= asset_flag_threshold,
        asset_level["pct_low_performance"] >= 0.15,
    ]
    choices = [
        "Insufficient data",
        "Critical",
        "High",
        "Moderate",
    ]
    asset_level["severity_tier"] = np.select(conditions, choices, default="Low")

    severity_rank = {
        "Critical": 1,
        "High": 2,
        "Moderate": 3,
        "Low": 4,
        "Insufficient data": 5,
    }
    asset_level["severity_rank"] = asset_level["severity_tier"].map(severity_rank).astype(int)

    asset_level = asset_level.sort_values(
        by=["severity_rank", "pct_low_performance", "mean_lux_mean_capped", "observation_count"],
        ascending=[True, False, True, False],
    ).reset_index(drop=True)

    asset_level["rank_overall"] = np.arange(1, len(asset_level) + 1)
    return asset_level


def get_critical_high_assets(asset_level: pd.DataFrame) -> pd.DataFrame:
    return asset_level[
        (asset_level["asset_flag"]) &
        (asset_level["severity_tier"].isin(["Critical", "High"]))
    ].copy()


def build_summary_tables(
    asset_level: pd.DataFrame,
    total_rows: int,
    eligible_rows: int,
    matched_rows: int,
    max_distance_ft: float,
    min_observations: int,
    asset_flag_threshold: float,
    avalon_pdf: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    unmatched_rows = eligible_rows - matched_rows
    match_rate = matched_rows / eligible_rows if eligible_rows > 0 else np.nan
    matched_rows_pct_of_total = matched_rows / total_rows if total_rows > 0 else np.nan

    assets_with_matches = int(asset_level["asset_id"].nunique())
    assets_meeting_min_observations = int((asset_level["observation_count"] >= min_observations).sum())
    flagged_assets_count = int(asset_level["asset_flag"].sum())
    flagged_assets_pct = flagged_assets_count / assets_with_matches if assets_with_matches > 0 else np.nan

    critical_count = int((asset_level["severity_tier"] == "Critical").sum())
    high_count = int((asset_level["severity_tier"] == "High").sum())
    moderate_count = int((asset_level["severity_tier"] == "Moderate").sum())
    low_count = int((asset_level["severity_tier"] == "Low").sum())
    insufficient_count = int((asset_level["severity_tier"] == "Insufficient data").sum())

    critical_high_map_assets_count = int(
        (
            asset_level["asset_flag"] &
            asset_level["severity_tier"].isin(["Critical", "High"])
        ).sum()
    )

    severity_counts = (
        asset_level["severity_tier"]
        .value_counts(dropna=False)
        .rename_axis("severity_tier")
        .reset_index(name="asset_count")
        .sort_values("severity_tier")
        .reset_index(drop=True)
    )

    summary_rows = [
        {"metric": "ws1_final_csv_total_rows", "value": WS1_FINAL_CSV_TOTAL_ROWS},
        {"metric": "ws1_final_csv_zero_readings_pct", "value": WS1_ZERO_READINGS_PCT},
        {"metric": "ws1_cutoff_lux", "value": WS1_CUTOFF_LUX},
        {"metric": "ws1_cap_lux", "value": WS1_CAP_LUX},
        {"metric": "ws1_baseline_non_zero_underperforming_pct", "value": WS1_BASELINE_NON_ZERO_UNDERPERFORMING_PCT},
        {"metric": "ws1_final_csv_low_performance_pct", "value": WS1_FINAL_CSV_LOW_PERFORMANCE_PCT},
        {"metric": "total_input_rows", "value": total_rows},
        {"metric": "eligible_rows_for_join", "value": eligible_rows},
        {"metric": "matched_rows_within_tolerance", "value": matched_rows},
        {"metric": "unmatched_rows_beyond_tolerance", "value": unmatched_rows},
        {"metric": "match_rate_of_eligible_rows", "value": round(float(match_rate), 6) if pd.notna(match_rate) else np.nan},
        {"metric": "matched_rows_pct_of_total_input", "value": round(float(matched_rows_pct_of_total) * 100, 4) if pd.notna(matched_rows_pct_of_total) else np.nan},
        {"metric": "total_assets_with_matches", "value": assets_with_matches},
        {"metric": "assets_meeting_min_observations", "value": assets_meeting_min_observations},
        {"metric": "flagged_assets_count", "value": flagged_assets_count},
        {"metric": "flagged_assets_pct_of_assets_with_matches", "value": round(float(flagged_assets_pct) * 100, 4) if pd.notna(flagged_assets_pct) else np.nan},
        {"metric": "critical_assets_count", "value": critical_count},
        {"metric": "high_assets_count", "value": high_count},
        {"metric": "moderate_assets_count", "value": moderate_count},
        {"metric": "low_assets_count", "value": low_count},
        {"metric": "insufficient_data_assets_count", "value": insufficient_count},
        {"metric": "critical_high_assets_shown_on_map", "value": critical_high_map_assets_count},
        {"metric": "join_method", "value": "nearest_neighbor_haversine_balltree"},
        {"metric": "distance_tolerance_ft", "value": max_distance_ft},
        {"metric": "min_observations", "value": min_observations},
        {"metric": "asset_flag_threshold", "value": asset_flag_threshold},
        {
            "metric": "asset_flag_rule",
            "value": "asset_flag = observation_count >= min_observations and pct_low_performance >= asset_flag_threshold",
        },
        {
            "metric": "severity_basis",
            "value": "severity is based on pct_low_performance from the final WS1 CSV, using the provided low_performance flag and the WS1 0.5567 lux cutoff",
        },
        {"metric": "avalon_used_in_automated_join", "value": "no"},
        {"metric": "avalon_reference_file_provided", "value": "yes" if avalon_pdf else "no"},
        {
            "metric": "notes",
            "value": "Traffic roadway Service Meter records were excluded before matching. Avalon PDF was not used in automated spatial join.",
        },
    ]

    risk_summary = pd.DataFrame(summary_rows)
    return risk_summary, severity_counts


def build_validation_template(
    total_rows: int,
    lux_zero_count: int,
    low_performance_count_total: int,
    cap_value_used: float,
    cutoff_value_used: float,
    max_distance_ft: float,
    min_observations: int,
    asset_flag_threshold: float,
) -> pd.DataFrame:
    zero_share = lux_zero_count / total_rows if total_rows > 0 else np.nan
    low_performance_share = low_performance_count_total / total_rows if total_rows > 0 else np.nan

    rows = [
        {"metric": "observed_total_rows_in_input", "value": total_rows},
        {"metric": "observed_zero_readings_count", "value": lux_zero_count},
        {"metric": "observed_zero_readings_pct", "value": round(float(zero_share) * 100, 4) if pd.notna(zero_share) else np.nan},
        {"metric": "observed_cap_value_used_lux", "value": round(float(cap_value_used), 6) if pd.notna(cap_value_used) else np.nan},
        {"metric": "observed_cutoff_value_used_lux", "value": round(float(cutoff_value_used), 6) if pd.notna(cutoff_value_used) else np.nan},
        {"metric": "observed_low_performance_count", "value": low_performance_count_total},
        {"metric": "observed_low_performance_share_pct", "value": round(float(low_performance_share) * 100, 4) if pd.notna(low_performance_share) else np.nan},
        {"metric": "ws1_final_csv_expected_total_rows", "value": WS1_FINAL_CSV_TOTAL_ROWS},
        {"metric": "ws1_final_csv_expected_zero_readings_pct", "value": WS1_ZERO_READINGS_PCT},
        {"metric": "ws1_expected_cap_lux", "value": WS1_CAP_LUX},
        {"metric": "ws1_expected_cutoff_lux", "value": WS1_CUTOFF_LUX},
        {"metric": "ws1_baseline_non_zero_underperforming_pct", "value": WS1_BASELINE_NON_ZERO_UNDERPERFORMING_PCT},
        {"metric": "ws1_final_csv_expected_low_performance_pct", "value": WS1_FINAL_CSV_LOW_PERFORMANCE_PCT},
        {"metric": "join_method", "value": "nearest_neighbor_haversine_balltree"},
        {"metric": "distance_tolerance_ft", "value": max_distance_ft},
        {"metric": "min_observations", "value": min_observations},
        {"metric": "asset_flag_threshold", "value": asset_flag_threshold},
    ]
    return pd.DataFrame(rows)


def build_asset_source_summary(asset_level: pd.DataFrame) -> pd.DataFrame:
    summary = (
        asset_level.groupby("asset_source", as_index=False)
        .agg(
            assets_with_matches=("asset_id", "count"),
            flagged_assets=("asset_flag", "sum"),
            critical_assets=("severity_tier", lambda s: (s == "Critical").sum()),
            high_assets=("severity_tier", lambda s: (s == "High").sum()),
            moderate_assets=("severity_tier", lambda s: (s == "Moderate").sum()),
            low_assets=("severity_tier", lambda s: (s == "Low").sum()),
            insufficient_data_assets=("severity_tier", lambda s: (s == "Insufficient data").sum()),
            avg_pct_low_performance=("pct_low_performance", "mean"),
            median_observation_count=("observation_count", "median"),
        )
    )

    summary["flag_rate_pct"] = (
        summary["flagged_assets"] / summary["assets_with_matches"] * 100
    ).round(2)
    summary["avg_pct_low_performance"] = (
        summary["avg_pct_low_performance"] * 100
    ).round(2)
    summary["median_observation_count"] = summary["median_observation_count"].round(1)

    return summary


def save_ranked_table(asset_level: pd.DataFrame, output_tables_dir: Path) -> None:
    ordered_cols = [
        "rank_overall",
        "asset_id",
        "asset_source",
        "asset_latitude",
        "asset_longitude",
        "observation_count",
        "low_performance_count",
        "pct_low_performance",
        "mean_lux_mean",
        "mean_lux_mean_capped",
        "mean_matched_distance_ft",
        "asset_flag",
        "severity_tier",
    ]
    extra_cols = [c for c in asset_level.columns if c not in ordered_cols and c not in {"asset_index", "severity_rank"}]
    asset_level[ordered_cols + extra_cols].to_csv(output_tables_dir / "asset_level_ranked.csv", index=False)


def save_top20_table(asset_level: pd.DataFrame, output_tables_dir: Path) -> None:
    top20 = asset_level[asset_level["asset_flag"]].copy().head(20)

    base_cols = [
        "rank_overall",
        "asset_id",
        "asset_source",
        "severity_tier",
        "asset_latitude",
        "asset_longitude",
        "observation_count",
        "low_performance_count",
        "pct_low_performance",
        "mean_lux_mean",
        "mean_lux_mean_capped",
        "mean_matched_distance_ft",
    ]

    optional_cols = [
        c for c in [
            "FIXTUREWAT",
            "LASTUPDATE",
            "Pole ID",
            "Roadway",
            "Fixture Type",
            "Power Wattage",
            "Life Cycle",
            "SUBTYPE",
        ]
        if c in top20.columns
    ]

    top20 = top20[base_cols + optional_cols].copy()

    top20["pct_low_performance"] = (top20["pct_low_performance"] * 100).round(2)
    top20["mean_lux_mean"] = top20["mean_lux_mean"].round(3)
    top20["mean_lux_mean_capped"] = top20["mean_lux_mean_capped"].round(3)
    top20["mean_matched_distance_ft"] = top20["mean_matched_distance_ft"].round(2)

    rename_map = {
        "rank_overall": "rank",
        "asset_latitude": "latitude",
        "asset_longitude": "longitude",
        "pct_low_performance": "pct_ws1_underperforming_pct",
        "mean_lux_mean": "mean_lux",
        "mean_lux_mean_capped": "mean_lux_capped",
        "mean_matched_distance_ft": "mean_match_distance_ft",
        "FIXTUREWAT": "fixture_wattage_type",
        "LASTUPDATE": "last_update",
        "Pole ID": "pole_id",
        "Roadway": "roadway",
        "Fixture Type": "fixture_type",
        "Power Wattage": "power_wattage",
        "Life Cycle": "life_cycle",
        "SUBTYPE": "subtype",
    }

    top20 = top20.rename(columns=rename_map)

    top20.to_csv(
        output_tables_dir / "top20_underperforming_assets.csv",
        index=False,
    )


def save_example_asset_table(asset_level: pd.DataFrame, output_tables_dir: Path) -> None:
    example_asset = asset_level[asset_level["asset_flag"]].copy().head(1)

    if example_asset.empty:
        example_asset = asset_level.head(1).copy()

    example_asset = example_asset[
        [
            "rank_overall",
            "asset_id",
            "asset_source",
            "severity_tier",
            "observation_count",
            "low_performance_count",
            "pct_low_performance",
            "mean_lux_mean",
            "mean_lux_mean_capped",
            "mean_matched_distance_ft",
            "asset_flag",
        ]
    ].copy()

    example_asset["pct_low_performance"] = (example_asset["pct_low_performance"] * 100).round(2)
    example_asset["mean_lux_mean"] = example_asset["mean_lux_mean"].round(3)
    example_asset["mean_lux_mean_capped"] = example_asset["mean_lux_mean_capped"].round(3)
    example_asset["mean_matched_distance_ft"] = example_asset["mean_matched_distance_ft"].round(2)

    example_asset = example_asset.rename(
        columns={
            "rank_overall": "rank",
            "pct_low_performance": "pct_ws1_underperforming_pct",
            "mean_lux_mean": "mean_lux",
            "mean_lux_mean_capped": "mean_lux_capped",
            "mean_matched_distance_ft": "mean_match_distance_ft",
        }
    )

    example_asset.to_csv(
        output_tables_dir / "example_asset_metrics.csv",
        index=False,
    )


def plot_top20(asset_level: pd.DataFrame, output_figures_dir: Path) -> None:
    plot_df = asset_level[
        (asset_level["asset_flag"]) &
        (asset_level["observation_count"] > 0)
    ].copy()

    if plot_df.empty:
        return

    plot_df = plot_df.head(20).copy()
    plot_df = plot_df.iloc[::-1]

    labels = [
        f"{row.asset_id} ({row.asset_source})"
        for row in plot_df.itertuples(index=False)
    ]

    plt.figure(figsize=(12, 9))
    plt.barh(labels, plot_df["pct_low_performance"] * 100)
    plt.xlabel("% WS1 underperforming readings")
    plt.ylabel("Asset")
    plt.title("Top 20 assets by WS1 underperforming share")
    plt.tight_layout()
    plt.savefig(output_figures_dir / "top20_underperforming_assets.png", dpi=200)
    plt.close()


def plot_flagged_assets_png(asset_level: pd.DataFrame, output_figures_dir: Path) -> None:
    flagged = get_critical_high_assets(asset_level)
    if flagged.empty:
        return

    color_map = {
        "Critical": "red",
        "High": "orange",
    }

    plt.figure(figsize=(10, 8))
    for tier, subset in flagged.groupby("severity_tier"):
        plt.scatter(
            subset["asset_longitude"],
            subset["asset_latitude"],
            s=12,
            label=tier,
            alpha=0.75,
            c=color_map.get(tier, "black"),
        )

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Critical and High flagged assets")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_figures_dir / "flagged_assets_map.png", dpi=220)
    plt.close()


def build_flagged_assets_html_map(asset_level: pd.DataFrame, output_figures_dir: Path) -> None:
    flagged = get_critical_high_assets(asset_level)
    if flagged.empty:
        return

    center_lat = float(flagged["asset_latitude"].mean())
    center_lon = float(flagged["asset_longitude"].mean())
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=12, control_scale=True)

    color_map = {
        "Critical": "red",
        "High": "orange",
    }

    for row in flagged.itertuples(index=False):
        popup = (
            f"Asset ID: {row.asset_id}<br>"
            f"Source: {row.asset_source}<br>"
            f"Severity: {row.severity_tier}<br>"
            f"Observation count: {row.observation_count}<br>"
            f"WS1 underperforming count: {row.low_performance_count}<br>"
            f"% WS1 underperforming: {row.pct_low_performance:.2%}<br>"
            f"Mean lux capped: {row.mean_lux_mean_capped:.3f}<br>"
            f"Mean match distance ft: {row.mean_matched_distance_ft:.2f}"
        )

        folium.CircleMarker(
            location=[row.asset_latitude, row.asset_longitude],
            radius=4,
            color=color_map.get(row.severity_tier, "black"),
            fill=True,
            fill_opacity=0.8,
            popup=folium.Popup(popup, max_width=350),
        ).add_to(fmap)

    fmap.save(output_figures_dir / "flagged_assets_map.html")


def main() -> None:
    args = parse_args()

    input_lux = Path(args.input_lux)
    streetlights = Path(args.streetlights)
    traffic_lights = Path(args.traffic_lights)
    output_dir = Path(args.output_dir)
    avalon_pdf = args.avalon_pdf.strip()

    output_tables_dir = output_dir / "tables"
    output_figures_dir = output_dir / "figures"
    output_tables_dir.mkdir(parents=True, exist_ok=True)
    output_figures_dir.mkdir(parents=True, exist_ok=True)

    assets = load_asset_layers(streetlights, traffic_lights)
    tree = build_balltree(assets)

    total_rows = 0
    eligible_rows = 0
    matched_rows = 0
    stats: Dict[int, Dict[str, float]] = {}
    lux_zero_count = 0
    low_performance_count_total = 0
    cap_value_used = float("-inf")
    cutoff_candidates = []

    for chunk in iter_lux_chunks(input_lux, chunksize=args.chunksize):
        total_rows += len(chunk)
        prepared = prepare_lux_chunk(chunk)
        eligible_rows += len(prepared)
        lux_zero_count += int((prepared["Lux_mean_capped"] == 0).sum())
        low_performance_count_total += int(prepared["low_performance"].sum())
        chunk_cap = pd.to_numeric(prepared["Lux_mean_capped"], errors="coerce").max()
        if pd.notna(chunk_cap):
            cap_value_used = max(cap_value_used, float(chunk_cap))

        non_zero_low = prepared[
            (prepared["low_performance"] == 1) &
            (prepared["Lux_mean_capped"] > 0)
        ]["Lux_mean_capped"]

        if not non_zero_low.empty:
            cutoff_candidates.append(float(non_zero_low.max()))

        matched = match_chunk_to_assets(
            chunk=prepared,
            tree=tree,
            max_distance_ft=args.max_distance_ft,
        )
        matched_rows += len(matched)
        update_stats(stats, matched)

    asset_level = finalize_asset_metrics(
        assets=assets,
        stats=stats,
        min_observations=args.min_observations,
        asset_flag_threshold=args.asset_flag_threshold,
    )

    risk_summary, severity_counts = build_summary_tables(
        asset_level=asset_level,
        total_rows=total_rows,
        eligible_rows=eligible_rows,
        matched_rows=matched_rows,
        max_distance_ft=args.max_distance_ft,
        min_observations=args.min_observations,
        asset_flag_threshold=args.asset_flag_threshold,
        avalon_pdf=avalon_pdf,
    )

    cutoff_value_used = max(cutoff_candidates) if cutoff_candidates else np.nan
    validation_template = build_validation_template(
        total_rows=total_rows,
        lux_zero_count=lux_zero_count,
        low_performance_count_total=low_performance_count_total,
        cap_value_used=cap_value_used if cap_value_used != float("-inf") else np.nan,
        cutoff_value_used=cutoff_value_used,
        max_distance_ft=args.max_distance_ft,
        min_observations=args.min_observations,
        asset_flag_threshold=args.asset_flag_threshold,
    )
    
    asset_source_summary = build_asset_source_summary(asset_level)

    save_ranked_table(asset_level, output_tables_dir)
    save_top20_table(asset_level, output_tables_dir)
    save_example_asset_table(asset_level, output_tables_dir)
    risk_summary.to_csv(output_tables_dir / "asset_risk_summary.csv", index=False)
    severity_counts.to_csv(output_tables_dir / "severity_tier_summary.csv", index=False)
    validation_template.to_csv(output_tables_dir / "ws2_validation_template.csv", index=False)
    asset_source_summary.to_csv(output_tables_dir / "asset_source_summary.csv", index=False)

    plot_top20(asset_level, output_figures_dir)
    plot_flagged_assets_png(asset_level, output_figures_dir)
    build_flagged_assets_html_map(asset_level, output_figures_dir)

    print("WS2 asset prioritization completed.")
    print(f"Total input rows: {total_rows}")
    print(f"Eligible rows for join: {eligible_rows}")
    print(f"Matched rows within {args.max_distance_ft} ft: {matched_rows}")
    print(f"Assets with matches: {asset_level['asset_id'].nunique()}")
    print(f"Flagged assets: {int(asset_level['asset_flag'].sum())}")
    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()