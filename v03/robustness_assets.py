from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize, TwoSlopeNorm

from v03.statistics import (
    matched_difference_in_differences,
    matched_regime_effects,
    write_analysis_manifest,
)

PARAMETERS = (
    "production_alpha",
    "investment_share",
    "base_credit_demand",
    "risk_price",
    "liquidity_price",
    "capital_price",
)
H3_OUTCOMES = ("cumulative_new_credit", "cumulative_output")


def load_parameter_metadata(catalog: str | Path) -> pd.DataFrame:
    expressions = ",\n".join(
        f"cast(json_extract(config_json, '$.parameters.{name}') as double) AS {name}"
        for name in PARAMETERS
    )
    conn = duckdb.connect(str(catalog), read_only=True)
    frame = conn.execute(f"""
        SELECT run_id, parameter_set_id, {expressions}
        FROM experiment_runs
        """).df()
    conn.close()
    return frame


def analyze_ablations(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ablations = frame[frame.scenario_id.str.startswith("ablation_")].copy()
    ablations["shock"] = ablations.scenario_id.str.endswith("_shock")
    ablations["mechanism"] = (
        ablations.scenario_id.str.removeprefix("ablation_")
        .str.removesuffix("_shock")
        .str.removesuffix("_baseline")
    )
    h2_records = []
    h3_records = []
    for mechanism, group in ablations.groupby("mechanism"):
        baseline = group[~group.shock]
        h2 = matched_regime_effects(
            baseline, ("credit_weighted_productivity", "mean_unfunded_share")
        )
        h2.insert(0, "mechanism_disabled", mechanism)
        h2_records.append(h2)
        h3_input = group.copy()
        h3_input["cumulative_new_credit"] = h3_input.response_window_new_credit
        h3_input["cumulative_output"] = h3_input.response_window_output
        h3 = matched_difference_in_differences(h3_input, H3_OUTCOMES)
        h3.insert(0, "mechanism_disabled", mechanism)
        h3_records.append(h3)
    return pd.concat(h2_records, ignore_index=True), pd.concat(
        h3_records, ignore_index=True
    )


def analyze_topologies(frame: pd.DataFrame) -> pd.DataFrame:
    topology = frame[frame.scenario_id.str.startswith("topology_")]
    records = []
    for scenario, group in topology.groupby("scenario_id"):
        effects = matched_regime_effects(
            group, ("credit_weighted_productivity", "mean_unfunded_share")
        )
        effects.insert(0, "scenario_id", scenario)
        records.append(effects)
    return pd.concat(records, ignore_index=True)


def analyze_sensitivity(
    frame: pd.DataFrame, metadata: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    sensitivity = frame[frame.scenario_id.str.startswith("sensitivity_")].copy()
    sensitivity["shock"] = sensitivity.scenario_id.str.endswith("_shock")
    sensitivity = sensitivity.merge(metadata, on="run_id", validate="one_to_one")
    wide = sensitivity.pivot(
        index=["parameter_set_id", "replication"],
        columns=["rate_regime", "shock"],
        values=["response_window_new_credit", "response_window_output"],
    )
    records = []
    parameter_values = sensitivity.groupby("parameter_set_id")[list(PARAMETERS)].first()
    for outcome, source in (
        ("cumulative_new_credit", "response_window_new_credit"),
        ("cumulative_output", "response_window_output"),
    ):
        differences = (
            wide[(source, "market", True)]
            - wide[(source, "market", False)]
            - wide[(source, "administered", True)]
            + wide[(source, "administered", False)]
        )
        for parameter_set_id, values in differences.groupby(level=0):
            clean = values.dropna().to_numpy(dtype=float)
            records.append(
                {
                    "parameter_set_id": parameter_set_id,
                    "outcome": outcome,
                    "matched_seeds": len(clean),
                    "mean_effect": float(clean.mean()),
                    "standard_deviation": float(clean.std(ddof=1)),
                    "minimum_effect": float(clean.min()),
                    "maximum_effect": float(clean.max()),
                    "positive_seed_share": float((clean > 0).mean()),
                }
            )
    effects = pd.DataFrame(records).merge(
        parameter_values.reset_index(), on="parameter_set_id", validate="many_to_one"
    )
    summary = {
        "interpretation": "global_stress_map_not_local_calibration_neighborhood",
        "parameter_sets": int(effects.parameter_set_id.nunique()),
        "matched_seeds_per_set": 5,
        "sign_counts": {
            outcome: {
                "negative": int((group.mean_effect < 0).sum()),
                "zero": int((group.mean_effect == 0).sum()),
                "positive_sign_reversal": int((group.mean_effect > 0).sum()),
            }
            for outcome, group in effects.groupby("outcome")
        },
    }
    return effects, summary


def save_phase_map(frame: pd.DataFrame, outcome: str, path: Path) -> None:
    data = frame[frame.outcome == outcome]
    values = data.mean_effect.to_numpy()
    norm = (
        TwoSlopeNorm(vmin=values.min(), vcenter=0, vmax=values.max())
        if values.min() < 0 < values.max()
        else Normalize(vmin=values.min(), vmax=values.max())
    )
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    scatter = ax.scatter(
        data.base_credit_demand,
        data.risk_price,
        c=values,
        cmap="coolwarm",
        norm=norm,
        s=38,
        edgecolor="black",
        linewidth=0.25,
    )
    ax.set_xlabel("Base credit demand (global stress range)")
    ax.set_ylabel("Risk-price coefficient")
    ax.set_title(outcome.replace("_", " ").title() + " H3 interaction")
    fig.colorbar(scatter, ax=ax, label="Market minus administered impulse")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate v0.3 robustness assets")
    parser.add_argument("--catalog", default="evidence/v0.3/evidence.duckdb")
    parser.add_argument("--summaries", default="paper/v0.3/generated/run_summaries.csv")
    parser.add_argument("--output", default="paper/v0.3/generated/robustness")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    summaries = pd.read_csv(args.summaries)
    metadata = load_parameter_metadata(args.catalog)
    h2_ablations, h3_ablations = analyze_ablations(summaries)
    topology = analyze_topologies(summaries)
    sensitivity, sensitivity_report = analyze_sensitivity(summaries, metadata)
    outputs = []
    for name, frame in (
        ("h2_ablation_effects.csv", h2_ablations),
        ("h3_ablation_effects.csv", h3_ablations),
        ("topology_effects.csv", topology),
        ("sensitivity_parameter_effects.csv", sensitivity),
    ):
        path = output / name
        frame.to_csv(path, index=False)
        outputs.append(path)
    report_path = output / "sensitivity_report.json"
    report_path.write_text(
        json.dumps(sensitivity_report, indent=2, sort_keys=True) + "\n"
    )
    outputs.append(report_path)
    for outcome in H3_OUTCOMES:
        path = output / f"{outcome}_phase_map.png"
        save_phase_map(sensitivity, outcome, path)
        outputs.append(path)
    manifest_path = output / "robustness_manifest.json"
    write_analysis_manifest(outputs, manifest_path)
    print(
        json.dumps(
            {
                "outputs": len(outputs) + 1,
                "manifest": manifest_path.as_posix(),
                **sensitivity_report,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
