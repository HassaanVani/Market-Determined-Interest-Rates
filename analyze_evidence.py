import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import numpy as np


def summarize(values):
    values = list(values)
    if not values:
        return {
            "n": 0,
            "mean": float("nan"),
            "std": float("nan"),
            "se": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
        }
    average = mean(values)
    standard_deviation = stdev(values) if len(values) > 1 else 0.0
    standard_error = standard_deviation / math.sqrt(len(values))
    return {
        "n": len(values),
        "mean": average,
        "std": standard_deviation,
        "se": standard_error,
        "ci_low": average - 1.96 * standard_error,
        "ci_high": average + 1.96 * standard_error,
    }


def required_replications(values):
    values = list(values)
    if len(values) < 2:
        return None
    effect = abs(mean(values))
    variability = stdev(values)
    if effect < 1e-12:
        return None
    return math.ceil(((1.96 + 0.84) * variability / effect) ** 2)


def required_replications_from_stats(effect, variability):
    if abs(effect) < 1e-12:
        return None
    return math.ceil(((1.96 + 0.84) * variability / abs(effect)) ** 2)


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_runs(connection):
    rows = connection.execute("""
        SELECT run_id, config_json, status, failure_reason
        FROM experiment_runs
        """).fetchall()
    runs = {}
    for row in rows:
        config = json.loads(row["config_json"])
        config["run_id"] = row["run_id"]
        config["status"] = row["status"]
        config["failure_reason"] = row["failure_reason"]
        runs[row["run_id"]] = config
    return runs


def h2_analysis(connection, runs):
    offers = connection.execute("""
        SELECT *
        FROM bank_offers
        WHERE approved = 1
          AND offered_nominal_rate IS NOT NULL
          AND decision_status = 'economic'
        """).fetchall()
    by_run = defaultdict(list)
    risk_scores = {
        "risk-averse": 0.0,
        "neutral": 1.0,
        "risk-seeking": 2.0,
    }
    for offer in offers:
        config = runs[offer["run_id"]]
        if config["scenario_name"] != "h2_baseline":
            continue
        deposits = max(offer["bank_deposit_liabilities"], 1e-9)
        reserve_buffer = (
            offer["bank_reserves"] / deposits - config["reserve_requirement"]
        )
        capital_buffer = offer["bank_equity"] / max(
            offer["bank_customer_loans"] + offer["bank_equity"], 1e-9
        )
        by_run[offer["run_id"]].append(
            (
                offer["offered_nominal_rate"],
                offer["borrower_leverage"],
                risk_scores[offer["borrower_risk_profile"]],
                reserve_buffer,
                capital_buffer,
                offer["bank_expected_inflation"],
            )
        )

    coefficient_names = [
        "borrower_leverage",
        "borrower_risk",
        "reserve_buffer",
        "capital_buffer",
        "expected_inflation",
    ]
    run_slopes = []
    for run_id, observations in by_run.items():
        if len(observations) < 6:
            continue
        values = np.asarray(observations, dtype=float)
        y = values[:, 0]
        x = np.column_stack([np.ones(len(values)), values[:, 1:]])
        coefficients, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
        if rank < x.shape[1]:
            continue
        for name, coefficient in zip(coefficient_names, coefficients[1:]):
            run_slopes.append(
                {
                    "run_id": run_id,
                    "regime": runs[run_id]["rate_regime"],
                    "seed": runs[run_id]["seeds"]["environment"],
                    "coefficient": name,
                    "value": float(coefficient),
                }
            )

    grouped = defaultdict(list)
    for row in run_slopes:
        grouped[(row["regime"], row["coefficient"])].append(row["value"])

    summary_rows = []
    for (regime, coefficient), values in sorted(grouped.items()):
        stats = summarize(values)
        summary_rows.append(
            {
                "regime": regime,
                "coefficient": coefficient,
                **stats,
            }
        )

    comparisons = []
    indexed = {
        (row["seed"], row["regime"], row["coefficient"]): row["value"]
        for row in run_slopes
    }
    seeds = sorted({row["seed"] for row in run_slopes})
    for coefficient in coefficient_names:
        differences = []
        for seed in seeds:
            administered = indexed.get((seed, "administered", coefficient))
            market = indexed.get((seed, "market", coefficient))
            if administered is not None and market is not None:
                differences.append(market - administered)
        stats = summarize(differences)
        comparisons.append(
            {
                "comparison": "market_minus_administered",
                "coefficient": coefficient,
                **stats,
            }
        )
    return summary_rows, comparisons, run_slopes


def aggregate_macro(connection, run_id, start_period=1, end_period=None):
    parameters = [run_id, start_period]
    end_clause = ""
    if end_period is not None:
        end_clause = "AND period <= ?"
        parameters.append(end_period)
    rows = connection.execute(
        f"""
        SELECT *
        FROM period_macro
        WHERE run_id = ? AND period >= ? {end_clause}
        ORDER BY period
        """,
        parameters,
    ).fetchall()
    if not rows:
        return {}
    return {
        "new_credit": sum(row["new_credit"] for row in rows),
        "output": sum(row["aggregate_output"] for row in rows),
        "consumption": sum(row["total_consumption"] for row in rows),
        "mean_inflation": mean(row["realized_inflation"] for row in rows),
        "inflation_volatility": (
            stdev(row["realized_inflation"] for row in rows) if len(rows) > 1 else 0.0
        ),
        "defaults": sum(row["defaults"] for row in rows),
        "write_offs": sum(row["write_offs"] for row in rows),
        "interbank_volume": sum(row["interbank_volume"] for row in rows),
        "emergency_borrowing": sum(row["emergency_borrowing"] for row in rows),
        "liquidity_shortfall": sum(row["liquidity_shortfall"] for row in rows),
        "final_deposit_money": rows[-1]["deposit_money"],
        "final_credit": rows[-1]["outstanding_credit"],
    }


def h3_analysis(connection, runs):
    indexed = {}
    for run_id, config in runs.items():
        if config["status"] != "completed":
            continue
        if config["scenario_name"] not in {"h3_baseline", "h3_demand"}:
            continue
        key = (
            config["rate_regime"],
            config["seeds"]["environment"],
            config["scenario_name"],
        )
        indexed[key] = aggregate_macro(connection, run_id, 4, 7)

    outcomes = [
        "new_credit",
        "output",
        "consumption",
        "mean_inflation",
        "defaults",
        "write_offs",
        "final_deposit_money",
        "final_credit",
    ]
    differences_by_regime = defaultdict(lambda: defaultdict(list))
    for regime in ("administered", "market"):
        seeds = {key[1] for key in indexed if key[0] == regime}
        for seed in seeds:
            baseline = indexed.get((regime, seed, "h3_baseline"))
            treatment = indexed.get((regime, seed, "h3_demand"))
            if not baseline or not treatment:
                continue
            for outcome in outcomes:
                differences_by_regime[regime][outcome].append(
                    treatment[outcome] - baseline[outcome]
                )

    rows = []
    power_rows = []
    for regime, outcome_values in differences_by_regime.items():
        for outcome, values in outcome_values.items():
            stats = summarize(values)
            rows.append(
                {
                    "regime": regime,
                    "estimand": "demand_shock_minus_baseline",
                    "outcome": outcome,
                    **stats,
                }
            )
            power_rows.append(
                {
                    "hypothesis": "H3",
                    "regime": regime,
                    "outcome": outcome,
                    "pilot_n": stats["n"],
                    "observed_effect": stats["mean"],
                    "pilot_std": stats["std"],
                    "required_n_80pct": required_replications(values),
                }
            )

    for outcome in outcomes:
        differences_in_differences = []
        seeds = sorted({key[1] for key in indexed})
        for seed in seeds:
            administered_baseline = indexed.get(("administered", seed, "h3_baseline"))
            administered_treatment = indexed.get(("administered", seed, "h3_demand"))
            market_baseline = indexed.get(("market", seed, "h3_baseline"))
            market_treatment = indexed.get(("market", seed, "h3_demand"))
            if all(
                (
                    administered_baseline,
                    administered_treatment,
                    market_baseline,
                    market_treatment,
                )
            ):
                administered_response = (
                    administered_treatment[outcome] - administered_baseline[outcome]
                )
                market_response = market_treatment[outcome] - market_baseline[outcome]
                differences_in_differences.append(
                    market_response - administered_response
                )
        stats = summarize(differences_in_differences)
        rows.append(
            {
                "regime": "market_minus_administered",
                "estimand": "difference_in_differences",
                "outcome": outcome,
                **stats,
            }
        )
        power_rows.append(
            {
                "hypothesis": "H3",
                "regime": "market_minus_administered",
                "outcome": outcome,
                "pilot_n": stats["n"],
                "observed_effect": stats["mean"],
                "pilot_std": stats["std"],
                "required_n_80pct": required_replications(differences_in_differences),
            }
        )
    return rows, power_rows


def h7_analysis(connection, runs):
    scenarios = [
        "h7_abundant_unavailable",
        "h7_scarce_unavailable",
        "h7_scarce_penalty",
        "h7_scarce_limited",
    ]
    outcomes = [
        "new_credit",
        "output",
        "inflation_volatility",
        "defaults",
        "write_offs",
        "interbank_volume",
        "emergency_borrowing",
        "liquidity_shortfall",
        "final_credit",
    ]
    run_values = {}
    grouped = defaultdict(lambda: defaultdict(list))
    for run_id, config in runs.items():
        scenario = config["scenario_name"]
        if config["status"] != "completed" or scenario not in scenarios:
            continue
        values = aggregate_macro(connection, run_id)
        key = (
            scenario,
            config["rate_regime"],
            config["seeds"]["environment"],
        )
        run_values[key] = values
        for outcome in outcomes:
            grouped[(scenario, config["rate_regime"])][outcome].append(values[outcome])

    rows = []
    for (scenario, regime), outcome_values in sorted(grouped.items()):
        for outcome, values in outcome_values.items():
            rows.append(
                {
                    "scenario": scenario,
                    "regime": regime,
                    "outcome": outcome,
                    **summarize(values),
                }
            )

    comparisons = []
    power_rows = []
    seeds = sorted({key[2] for key in run_values})
    for scenario in scenarios:
        for outcome in outcomes:
            differences = []
            for seed in seeds:
                administered = run_values.get((scenario, "administered", seed))
                market = run_values.get((scenario, "market", seed))
                if administered and market:
                    differences.append(market[outcome] - administered[outcome])
            stats = summarize(differences)
            comparisons.append(
                {
                    "scenario": scenario,
                    "comparison": "market_minus_administered",
                    "outcome": outcome,
                    **stats,
                }
            )
            power_rows.append(
                {
                    "hypothesis": "H7",
                    "regime": scenario,
                    "outcome": outcome,
                    "pilot_n": stats["n"],
                    "observed_effect": stats["mean"],
                    "pilot_std": stats["std"],
                    "required_n_80pct": required_replications(differences),
                }
            )

    institutional_contrasts = [
        (
            "h7_abundant_unavailable",
            "h7_scarce_unavailable",
            "abundant_minus_scarce_unavailable",
        ),
        (
            "h7_scarce_penalty",
            "h7_scarce_unavailable",
            "scarce_penalty_minus_unavailable",
        ),
        (
            "h7_scarce_limited",
            "h7_scarce_unavailable",
            "scarce_limited_minus_unavailable",
        ),
        (
            "h7_scarce_penalty",
            "h7_scarce_limited",
            "scarce_penalty_minus_limited",
        ),
    ]
    for treatment_scenario, reference_scenario, label in institutional_contrasts:
        for regime in ("administered", "market"):
            for outcome in outcomes:
                differences = []
                for seed in seeds:
                    treatment = run_values.get((treatment_scenario, regime, seed))
                    reference = run_values.get((reference_scenario, regime, seed))
                    if treatment and reference:
                        differences.append(treatment[outcome] - reference[outcome])
                stats = summarize(differences)
                comparisons.append(
                    {
                        "scenario": label,
                        "comparison": f"institutional_contrast_{regime}",
                        "outcome": outcome,
                        **stats,
                    }
                )
                power_rows.append(
                    {
                        "hypothesis": "H7",
                        "regime": f"{label}:{regime}",
                        "outcome": outcome,
                        "pilot_n": stats["n"],
                        "observed_effect": stats["mean"],
                        "pilot_std": stats["std"],
                        "required_n_80pct": required_replications(differences),
                    }
                )
    return rows, comparisons, power_rows


def format_number(value):
    if value is None:
        return "NA"
    if isinstance(value, float) and math.isnan(value):
        return "NA"
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def write_summary(path, runs, h2_comparisons, h3_rows, h7_comparisons):
    statuses = defaultdict(int)
    for config in runs.values():
        statuses[config["status"]] += 1
    lines = [
        "# Computational evidence summary",
        "",
        "## Run integrity",
        "",
        f"- Total registered runs: {len(runs)}",
        *[f"- {status}: {count}" for status, count in sorted(statuses.items())],
        "",
        "## H2: local-information sensitivity",
        "",
    ]
    for row in h2_comparisons:
        lines.append(
            f"- Market-minus-administered slope for "
            f"`{row['coefficient']}`: {format_number(row['mean'])} "
            f"(95% CI {format_number(row['ci_low'])}, "
            f"{format_number(row['ci_high'])}; n={row['n']})."
        )
    lines.extend(["", "## H3: demand-shock response", ""])
    for row in h3_rows:
        if row["outcome"] in {"new_credit", "output", "mean_inflation"}:
            lines.append(
                f"- {row['regime']} `{row['outcome']}` "
                f"{row['estimand']}: "
                f"{format_number(row['mean'])} "
                f"(95% CI {format_number(row['ci_low'])}, "
                f"{format_number(row['ci_high'])}; n={row['n']})."
            )
    lines.extend(["", "## H7: institutional dependence", ""])
    for row in h7_comparisons:
        if row["outcome"] in {
            "new_credit",
            "emergency_borrowing",
            "liquidity_shortfall",
        } and (
            row["comparison"].startswith("institutional_contrast")
            or row["scenario"] == "h7_abundant_unavailable"
        ):
            lines.append(
                f"- {row['scenario']} ({row['comparison']}) "
                f"`{row['outcome']}`: {format_number(row['mean'])} "
                f"(95% CI {format_number(row['ci_low'])}, "
                f"{format_number(row['ci_high'])}; n={row['n']})."
            )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "These are computational treatment effects inside the specified "
            "agent-based model. They are not estimates of causal effects in the "
            "United States economy. Rule-based powered results establish the "
            "institutional mechanisms; DeepSeek R1 8B runs are reported as a "
            "separate behavioral robustness layer.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def analyze(database_path, output_directory):
    database_path = Path(database_path).resolve()
    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    runs = load_runs(connection)
    h2_summary, h2_comparisons, h2_run_slopes = h2_analysis(connection, runs)
    h3_rows, h3_power = h3_analysis(connection, runs)
    h7_rows, h7_comparisons, h7_power = h7_analysis(connection, runs)

    write_csv(output_directory / "h2_coefficients.csv", h2_summary)
    write_csv(output_directory / "h2_comparisons.csv", h2_comparisons)
    write_csv(output_directory / "h2_run_slopes.csv", h2_run_slopes)
    write_csv(output_directory / "h3_impulse_responses.csv", h3_rows)
    write_csv(output_directory / "h7_scenario_outcomes.csv", h7_rows)
    write_csv(output_directory / "h7_comparisons.csv", h7_comparisons)
    h2_power = [
        {
            "hypothesis": "H2",
            "regime": row["comparison"],
            "outcome": row["coefficient"],
            "pilot_n": row["n"],
            "observed_effect": row["mean"],
            "pilot_std": row["std"],
            "required_n_80pct": required_replications_from_stats(
                row["mean"], row["std"]
            ),
        }
        for row in h2_comparisons
    ]
    write_csv(
        output_directory / "power_analysis.csv",
        [*h2_power, *h3_power, *h7_power],
    )
    write_summary(
        output_directory / "evidence_summary.md",
        runs,
        h2_comparisons,
        h3_rows,
        h7_comparisons,
    )
    connection.close()
    return output_directory


def main():
    parser = argparse.ArgumentParser(
        description="Estimate H2, H3, and H7 from an evidence database."
    )
    parser.add_argument("database")
    parser.add_argument("--output", default="evidence/analysis_v0_1")
    args = parser.parse_args()
    output = analyze(args.database, args.output)
    print(f"Analysis outputs: {output}")


if __name__ == "__main__":
    main()
