from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def percentile_paired_bootstrap(
    differences, draws: int = 10_000, seed: int = 903
) -> dict[str, float]:
    values = np.asarray(differences, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return {
            "estimate": float("nan"),
            "lower_95": float("nan"),
            "upper_95": float("nan"),
            "n": 0,
            "standardized_effect": float("nan"),
            "p_value": float("nan"),
        }
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(draws, len(values)), replace=True).mean(axis=1)
    signs = rng.choice((-1.0, 1.0), size=(draws, len(values)))
    null = (signs * values).mean(axis=1)
    p_value = (np.sum(np.abs(null) >= abs(values.mean())) + 1) / (draws + 1)
    return {
        "estimate": float(values.mean()),
        "lower_95": float(np.quantile(samples, 0.025)),
        "upper_95": float(np.quantile(samples, 0.975)),
        "n": int(len(values)),
        "standardized_effect": (
            float(values.mean() / values.std(ddof=1))
            if len(values) > 1 and values.std(ddof=1) > 0
            else float("nan")
        ),
        "p_value": float(p_value),
    }


def holm_adjust(p_values) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    count = len(p)
    for rank, index in enumerate(order):
        running = max(running, (count - rank) * p[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def run_summaries(macro: pd.DataFrame, firms: pd.DataFrame) -> pd.DataFrame:
    aggregates = (
        macro.groupby("run_id")
        .agg(
            cumulative_new_credit=("new_credit", "sum"),
            cumulative_output=("aggregate_output", "sum"),
            unresolved_liquidity_shortfall=("unresolved_liquidity_shortfall", "sum"),
            mean_unfunded_share=("unfunded_demand_share", "mean"),
            cumulative_consumption=("actual_consumption", "sum"),
            defaults=("defaults", "sum"),
            write_offs=("write_offs", "sum"),
            resolution_cost=("resolution_cost", "sum"),
        )
        .reset_index()
    )
    funded = firms[firms.received_credit > 0].copy()
    funded["weighted_productivity"] = funded.productivity * funded.received_credit
    allocation = funded.groupby("run_id").agg(
        weighted=("weighted_productivity", "sum"), credit=("received_credit", "sum")
    )
    allocation["credit_weighted_productivity"] = allocation.weighted / allocation.credit
    return aggregates.merge(
        allocation[["credit_weighted_productivity"]], on="run_id", how="left"
    )


def matched_regime_effects(
    run_table: pd.DataFrame, outcomes: tuple[str, ...], seed_column: str = "replication"
) -> pd.DataFrame:
    identifiers = [seed_column, "scenario_id"]
    wide = run_table.pivot(
        index=identifiers, columns="rate_regime", values=list(outcomes)
    )
    records = []
    for outcome in outcomes:
        difference = wide[(outcome, "market")] - wide[(outcome, "administered")]
        result = percentile_paired_bootstrap(difference)
        records.append({"outcome": outcome, **result})
    frame = pd.DataFrame(records)
    frame["p_value_holm"] = holm_adjust(frame.p_value)
    return frame


def matched_difference_in_differences(
    run_table: pd.DataFrame, outcomes: tuple[str, ...]
) -> pd.DataFrame:
    wide = run_table.pivot(
        index="replication", columns=["rate_regime", "shock"], values=list(outcomes)
    )
    records = []
    for outcome in outcomes:
        market_irf = wide[(outcome, "market", True)] - wide[(outcome, "market", False)]
        administered_irf = (
            wide[(outcome, "administered", True)]
            - wide[(outcome, "administered", False)]
        )
        result = percentile_paired_bootstrap(market_irf - administered_irf)
        records.append({"outcome": outcome, **result})
    frame = pd.DataFrame(records)
    frame["p_value_holm"] = holm_adjust(frame.p_value)
    return frame


def write_analysis_manifest(outputs: list[str | Path], path: str | Path) -> None:
    import hashlib

    records = []
    for output in sorted(Path(item) for item in outputs):
        records.append(
            {
                "path": output.as_posix(),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "bytes": output.stat().st_size,
            }
        )
    Path(path).write_text(
        json.dumps({"outputs": records}, indent=2, sort_keys=True) + "\n"
    )
