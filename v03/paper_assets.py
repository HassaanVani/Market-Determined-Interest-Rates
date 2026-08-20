from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

from v03.statistics import (
    matched_difference_in_differences,
    matched_regime_effects,
    holm_adjust,
    percentile_paired_bootstrap,
    write_analysis_manifest,
)

H7_OUTCOMES = ("cumulative_new_credit", "unresolved_liquidity_shortfall")


def load_run_summaries(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("""
        WITH macro AS (
            SELECT run_id,
                   sum(new_credit) AS cumulative_new_credit,
                   sum(aggregate_output) AS cumulative_output,
                   sum(CASE WHEN period BETWEEN 8 AND 23 THEN new_credit ELSE 0 END)
                       AS response_window_new_credit,
                   sum(CASE WHEN period BETWEEN 8 AND 23 THEN aggregate_output ELSE 0 END)
                       AS response_window_output,
                   sum(unresolved_liquidity_shortfall)
                       AS unresolved_liquidity_shortfall,
                   avg(unfunded_demand_share) AS mean_unfunded_share,
                   sum(actual_consumption) AS cumulative_consumption,
                   sum(defaults) AS defaults,
                   sum(write_offs) AS write_offs,
                   sum(resolution_cost) AS resolution_cost
            FROM period_macro GROUP BY run_id
        ), allocation AS (
            SELECT run_id,
                   sum(productivity * received_credit)
                       / nullif(sum(received_credit), 0)
                       AS credit_weighted_productivity
            FROM firm_states
            WHERE received_credit > 0
            GROUP BY run_id
        )
        SELECT r.run_id, r.scenario_id, r.rate_regime, r.replication,
               m.*, a.credit_weighted_productivity
        FROM experiment_runs r
        JOIN macro m USING(run_id)
        LEFT JOIN allocation a USING(run_id)
        ORDER BY r.scenario_id, r.rate_regime, r.replication
        """).df()


def load_h2_mechanisms(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("""
        WITH applications AS (
            SELECT run_id,
                   regr_slope(
                       unfunded_principal / nullif(requested_principal, 0),
                       borrower_leverage
                   ) AS risk_rationing_slope
            FROM credit_applications
            WHERE scenario='h2_h3_baseline'
            GROUP BY run_id
        ), offers AS (
            SELECT o.run_id,
                   avg(o.local_pass_through) AS mean_local_pass_through,
                   regr_slope(o.offered_nominal_rate, a.borrower_leverage)
                       AS borrower_leverage_rate_slope,
                   stddev_samp(o.offered_nominal_rate) AS quoted_rate_dispersion
            FROM bank_offers o
            JOIN credit_applications a
              ON o.run_id=a.run_id AND o.application_id=a.application_id
            WHERE o.scenario='h2_h3_baseline'
              AND o.offered_nominal_rate IS NOT NULL
            GROUP BY o.run_id
        )
        SELECT a.run_id, o.mean_local_pass_through,
               o.borrower_leverage_rate_slope, o.quoted_rate_dispersion,
               a.risk_rationing_slope
        FROM applications a LEFT JOIN offers o USING(run_id)
        ORDER BY a.run_id
        """).df()


def _regime_difference(frame: pd.DataFrame, outcome: str) -> pd.Series:
    wide = frame.pivot(index="replication", columns="rate_regime", values=outcome)
    return wide["market"] - wide["administered"]


def h7_interaction_effects(frame: pd.DataFrame) -> pd.DataFrame:
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
    records = []
    for comparison, (first, second) in comparisons.items():
        comparison_rows = []
        for outcome in H7_OUTCOMES:
            first_difference = _regime_difference(
                frame[frame.scenario_id == first], outcome
            )
            second_difference = _regime_difference(
                frame[frame.scenario_id == second], outcome
            )
            comparison_rows.append(
                {
                    "comparison": comparison,
                    "outcome": outcome,
                    **percentile_paired_bootstrap(first_difference - second_difference),
                }
            )
        adjusted = holm_adjust([row["p_value"] for row in comparison_rows])
        for row, p_value_holm in zip(comparison_rows, adjusted):
            row["p_value_holm"] = p_value_holm
            records.append(row)
    return pd.DataFrame(records)


def save_figure(frame: pd.DataFrame, outcome: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    grouped = frame.groupby(["scenario_id", "rate_regime"])[outcome].mean().unstack()
    grouped.plot(kind="bar", ax=ax)
    ax.set_ylabel(outcome.replace("_", " ").title())
    ax.set_xlabel("")
    ax.legend(title="Rate regime", frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate publication assets from the immutable DuckDB catalog"
    )
    parser.add_argument("--catalog", default="evidence/v0.3/evidence.duckdb")
    parser.add_argument("--output", default="paper/v0.3/generated")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(args.catalog, read_only=True)
    conn.execute("SET memory_limit='1GB'")
    # Regression aggregates are order-sensitive at the final floating-point
    # digits.  A single analysis thread makes CSV and manifest bytes reproducible.
    conn.execute("SET threads=1")
    summaries = load_run_summaries(conn)
    mechanism_runs = load_h2_mechanisms(conn)
    conn.close()
    summary_path = output / "run_summaries.csv"
    summaries.to_csv(summary_path, index=False)
    outputs = [summary_path]
    h2 = summaries[summaries.scenario_id == "h2_h3_baseline"]
    h2_levels = (
        h2.groupby("rate_regime")
        .agg(
            runs=("run_id", "size"),
            mean_credit_weighted_productivity=(
                "credit_weighted_productivity",
                "mean",
            ),
            undefined_productivity_runs=(
                "credit_weighted_productivity",
                lambda values: int(values.isna().sum()),
            ),
            zero_credit_runs=(
                "cumulative_new_credit",
                lambda values: int((values == 0).sum()),
            ),
            mean_unfunded_share=("mean_unfunded_share", "mean"),
        )
        .reset_index()
    )
    h2_levels_path = output / "h2_regime_levels.csv"
    h2_levels.to_csv(h2_levels_path, index=False)
    outputs.append(h2_levels_path)
    effects = matched_regime_effects(
        h2, ("credit_weighted_productivity", "mean_unfunded_share")
    )
    effects_path = output / "h2_primary_effects.csv"
    effects.to_csv(effects_path, index=False)
    outputs.append(effects_path)

    mechanism_runs = mechanism_runs.merge(
        summaries[
            [
                "run_id",
                "scenario_id",
                "rate_regime",
                "replication",
                "cumulative_output",
                "cumulative_new_credit",
                "defaults",
                "write_offs",
            ]
        ],
        on="run_id",
        validate="one_to_one",
    )
    mechanism_runs["output_per_unit_credit"] = (
        mechanism_runs.cumulative_output / mechanism_runs.cumulative_new_credit
    ).where(mechanism_runs.cumulative_new_credit.ne(0))
    mechanism_runs_path = output / "h2_mechanism_run_summaries.csv"
    mechanism_runs.to_csv(mechanism_runs_path, index=False)
    outputs.append(mechanism_runs_path)
    mechanism_effects = matched_regime_effects(
        mechanism_runs,
        ("mean_local_pass_through", "borrower_leverage_rate_slope"),
    )
    mechanism_effects_path = output / "h2_mechanism_effects.csv"
    mechanism_effects.to_csv(mechanism_effects_path, index=False)
    outputs.append(mechanism_effects_path)
    h2_secondary = matched_regime_effects(
        mechanism_runs,
        (
            "quoted_rate_dispersion",
            "risk_rationing_slope",
            "defaults",
            "write_offs",
            "output_per_unit_credit",
        ),
    )
    h2_secondary_path = output / "h2_secondary_effects.csv"
    h2_secondary.to_csv(h2_secondary_path, index=False)
    outputs.append(h2_secondary_path)

    completeness_records = []
    for outcome in (
        "credit_weighted_productivity",
        "mean_unfunded_share",
        "mean_local_pass_through",
        "borrower_leverage_rate_slope",
        "quoted_rate_dispersion",
        "risk_rationing_slope",
    ):
        source = h2 if outcome in h2 else mechanism_runs
        wide = source.pivot(index="replication", columns="rate_regime", values=outcome)
        completeness_records.append(
            {
                "outcome": outcome,
                "planned_pairs": 809,
                "complete_pairs": int(wide.dropna().shape[0]),
                "administered_undefined": int(wide["administered"].isna().sum()),
                "market_undefined": int(wide["market"].isna().sum()),
            }
        )
    completeness_path = output / "estimand_completeness.csv"
    pd.DataFrame(completeness_records).to_csv(completeness_path, index=False)
    outputs.append(completeness_path)

    h3 = summaries[
        summaries.scenario_id.isin(("h2_h3_baseline", "h3_positive_demand"))
    ].copy()
    h3["cumulative_new_credit"] = h3.response_window_new_credit
    h3["cumulative_output"] = h3.response_window_output
    h3["shock"] = h3.scenario_id.eq("h3_positive_demand")
    h3_effects = matched_difference_in_differences(
        h3, ("cumulative_new_credit", "cumulative_output")
    )
    h3_path = output / "h3_difference_in_differences.csv"
    h3_effects.to_csv(h3_path, index=False)
    outputs.append(h3_path)
    h3_impulses = (
        h3.groupby(["rate_regime", "shock"])[
            ["cumulative_new_credit", "cumulative_output"]
        ]
        .mean()
        .unstack("shock")
    )
    h3_impulses.columns = [
        f"{outcome}_{'shock' if shocked else 'baseline'}"
        for outcome, shocked in h3_impulses.columns
    ]
    for outcome in ("cumulative_new_credit", "cumulative_output"):
        h3_impulses[f"{outcome}_impulse"] = (
            h3_impulses[f"{outcome}_shock"] - h3_impulses[f"{outcome}_baseline"]
        )
    h3_impulses_path = output / "h3_regime_impulses.csv"
    h3_impulses.reset_index().to_csv(h3_impulses_path, index=False)
    outputs.append(h3_impulses_path)

    h7_records = []
    h7 = summaries[summaries.scenario_id.str.startswith("h7_")]
    for scenario, group in h7.groupby("scenario_id"):
        result = matched_regime_effects(
            group,
            ("cumulative_new_credit", "unresolved_liquidity_shortfall"),
        )
        result.insert(0, "scenario_id", scenario)
        h7_records.append(result)
    h7_path = output / "h7_anchor_effects.csv"
    (pd.concat(h7_records, ignore_index=True) if h7_records else pd.DataFrame()).to_csv(
        h7_path, index=False
    )
    outputs.append(h7_path)

    h7_interactions_path = output / "h7_interaction_effects.csv"
    h7_interaction_effects(h7).to_csv(h7_interactions_path, index=False)
    outputs.append(h7_interactions_path)

    secondary_path = output / "secondary_outcomes.csv"
    summaries[
        [
            "run_id",
            "scenario_id",
            "rate_regime",
            "cumulative_consumption",
            "defaults",
            "write_offs",
            "resolution_cost",
        ]
    ].to_csv(secondary_path, index=False)
    outputs.append(secondary_path)
    figure_path = output / "main_credit_by_scenario.png"
    save_figure(h3, "cumulative_new_credit", figure_path)
    outputs.append(figure_path)
    manifest_path = output / "analysis_manifest.json"
    write_analysis_manifest(outputs, manifest_path)
    print(
        json.dumps(
            {"outputs": len(outputs) + 1, "manifest": str(manifest_path)}, indent=2
        )
    )


if __name__ == "__main__":
    main()
