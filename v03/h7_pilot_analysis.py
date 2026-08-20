from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

from v03.power import required_paired_seeds
from v03.statistics import percentile_paired_bootstrap, run_summaries

OUTCOMES = ("cumulative_new_credit", "unresolved_liquidity_shortfall")


def _load(catalog: str | Path) -> pd.DataFrame:
    conn = duckdb.connect(str(catalog), read_only=True)
    runs = conn.execute(
        "SELECT run_id,scenario_id,rate_regime,replication FROM experiment_runs"
    ).df()
    macro = conn.execute("SELECT * FROM period_macro").df()
    firms = conn.execute("SELECT * FROM firm_states").df()
    conn.close()
    return run_summaries(macro, firms).merge(runs, on="run_id", validate="one_to_one")


def _regime_difference(frame: pd.DataFrame, outcome: str) -> pd.Series:
    wide = frame.pivot(index="replication", columns="rate_regime", values=outcome)
    return wide["market"] - wide["administered"]


def analyze(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    anchors = []
    for scenario, group in frame.groupby("scenario_id"):
        for outcome in OUTCOMES:
            differences = _regime_difference(group, outcome)
            result = percentile_paired_bootstrap(differences)
            anchors.append(
                {
                    "scenario_id": scenario,
                    "outcome": outcome,
                    **result,
                    "required_matched_seeds": required_paired_seeds(
                        result["standardized_effect"]
                    ),
                    "structural_zero": bool(differences.abs().max() <= 1e-12),
                }
            )
    interactions = []
    comparisons = {
        "reserve_low_vs_high_unavailable": (
            "h7_reserve_0.05_unavailable_0.0",
            "h7_reserve_0.50_unavailable_0.0",
        ),
        "facility_unavailable_vs_penalty_low_reserve": (
            "h7_reserve_0.05_unavailable_0.0",
            "h7_reserve_0.05_penalty_1.0",
        ),
    }
    for comparison, (first, second) in comparisons.items():
        for outcome in OUTCOMES:
            first_diff = _regime_difference(frame[frame.scenario_id == first], outcome)
            second_diff = _regime_difference(
                frame[frame.scenario_id == second], outcome
            )
            result = percentile_paired_bootstrap(first_diff - second_diff)
            interactions.append(
                {
                    "comparison": comparison,
                    "outcome": outcome,
                    **result,
                    "required_matched_seeds": required_paired_seeds(
                        result["standardized_effect"]
                    ),
                }
            )
    return pd.DataFrame(anchors), pd.DataFrame(interactions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the v0.3 H7 pilot")
    parser.add_argument("--catalog", default="evidence/v0.3/pilot_h7c.duckdb")
    parser.add_argument("--output", default="evidence/v0.3/pilot_h7c_analysis")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    anchors, interactions = analyze(_load(args.catalog))
    anchors.to_csv(output / "h7_anchor_effects.csv", index=False)
    interactions.to_csv(output / "h7_interaction_effects.csv", index=False)
    interaction_counts = interactions.required_matched_seeds.dropna()
    required = int(interaction_counts.max()) if len(interaction_counts) else None
    anchor_counts = anchors.loc[
        ~anchors.structural_zero, "required_matched_seeds"
    ].dropna()
    report = {
        "pilot_seed_namespace": "pilot-h7-v0.3",
        "pilot_pairs_per_cell": 20,
        "target_power": 0.90,
        "planned_h7_pairs_per_cell": 40,
        "required_h7_pairs_per_cell": required,
        "planned_h7_design_is_adequate": bool(required and required <= 40),
        "maximum_nonzero_anchor_count": (
            int(anchor_counts.max()) if len(anchor_counts) else None
        ),
        "anchor_power_scope": (
            "Anchor contrasts are distributional/descriptive; replication is "
            "powered for the two predeclared reserve/facility interactions."
        ),
        "structural_zero_anchor_outcomes": int(anchors.structural_zero.sum()),
        "anchor_table": (output / "h7_anchor_effects.csv").as_posix(),
        "interaction_table": (output / "h7_interaction_effects.csv").as_posix(),
    }
    (output / "h7_power_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
