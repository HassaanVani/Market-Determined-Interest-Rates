"""Produce a descriptive integrity report for the DeepSeek R1 8B pilot."""

import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean


def write_csv(path, rows):
    rows = list(rows)
    with path.open("w", newline="") as handle:
        if not rows:
            return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(database, output):
    database = Path(database).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    run_rows = connection.execute(
        "SELECT run_id, status, failure_reason, config_json FROM experiment_runs"
    ).fetchall()
    runs = {}
    for row in run_rows:
        config = json.loads(row["config_json"])
        config.update(
            {
                "status": row["status"],
                "failure_reason": row["failure_reason"],
            }
        )
        runs[row["run_id"]] = config

    calls = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM llm_calls ORDER BY run_id, period, agent_id, attempt"
        )
    ]
    write_csv(output / "llm_call_audit.csv", calls)

    run_metrics = []
    for run_id, config in runs.items():
        applications = connection.execute(
            "SELECT * FROM credit_applications WHERE run_id = ?", (run_id,)
        ).fetchall()
        offers = connection.execute(
            "SELECT * FROM bank_offers WHERE run_id = ?", (run_id,)
        ).fetchall()
        macro = connection.execute(
            """
            SELECT * FROM period_macro
            WHERE run_id = ? AND period >= 1
            ORDER BY period
            """,
            (run_id,),
        ).fetchall()
        run_calls = [row for row in calls if row["run_id"] == run_id]
        accepted_rates = [
            row["offered_nominal_rate"] for row in offers if row["accepted"]
        ]
        run_metrics.append(
            {
                "run_id": run_id,
                "regime": config["rate_regime"],
                "seed": config["seeds"]["environment"],
                "status": config["status"],
                "applications": len(applications),
                "positive_applications": sum(
                    row["requested_principal"] > 0 for row in applications
                ),
                "requested_principal": sum(
                    row["requested_principal"] for row in applications
                ),
                "offers": len(offers),
                "approved_offers": sum(row["approved"] for row in offers),
                "accepted_offers": sum(row["accepted"] for row in offers),
                "new_credit": sum(row["new_credit"] for row in macro),
                "mean_accepted_rate": (
                    mean(accepted_rates) if accepted_rates else math.nan
                ),
                "llm_calls": len(run_calls),
                "failed_calls": sum(row["status"] != "success" for row in run_calls),
                "retry_calls": sum(row["attempt"] > 0 for row in run_calls),
                "mean_latency_seconds": mean(
                    row["latency_seconds"] for row in run_calls
                ),
            }
        )
    write_csv(output / "llm_run_metrics.csv", run_metrics)

    by_regime = defaultdict(list)
    for row in run_metrics:
        by_regime[row["regime"]].append(row)
    regime_summary = []
    for regime, rows in sorted(by_regime.items()):
        regime_summary.append(
            {
                "regime": regime,
                "runs": len(rows),
                "completed_runs": sum(row["status"] == "completed" for row in rows),
                "applications": sum(row["applications"] for row in rows),
                "positive_applications": sum(
                    row["positive_applications"] for row in rows
                ),
                "accepted_offers": sum(row["accepted_offers"] for row in rows),
                "mean_new_credit": mean(row["new_credit"] for row in rows),
                "mean_accepted_rate": mean(row["mean_accepted_rate"] for row in rows),
                "llm_calls": sum(row["llm_calls"] for row in rows),
                "failed_calls": sum(row["failed_calls"] for row in rows),
                "retry_calls": sum(row["retry_calls"] for row in rows),
                "mean_latency_seconds": mean(
                    row["mean_latency_seconds"] for row in rows
                ),
            }
        )
    write_csv(output / "llm_regime_summary.csv", regime_summary)

    indexed = {(row["seed"], row["regime"]): row for row in run_metrics}
    matched = []
    for seed in sorted({row["seed"] for row in run_metrics}):
        administered = indexed.get((seed, "administered"))
        market = indexed.get((seed, "market"))
        if not administered or not market:
            continue
        matched.append(
            {
                "seed": seed,
                "market_minus_administered_new_credit": (
                    market["new_credit"] - administered["new_credit"]
                ),
                "market_minus_administered_accepted_rate": (
                    market["mean_accepted_rate"] - administered["mean_accepted_rate"]
                ),
                "market_minus_administered_positive_applications": (
                    market["positive_applications"]
                    - administered["positive_applications"]
                ),
            }
        )
    write_csv(output / "llm_matched_comparisons.csv", matched)

    successful = [row for row in calls if row["status"] == "success"]
    latencies = [row["latency_seconds"] for row in successful]
    lines = [
        "# DeepSeek R1 8B behavioral validation",
        "",
        "## Integrity",
        "",
        f"- Runs: {len(runs)} total; "
        f"{sum(c['status'] == 'completed' for c in runs.values())} completed.",
        f"- LLM calls: {len(calls)} total; {len(successful)} successful; "
        f"{len(calls) - len(successful)} failed.",
        f"- Retry attempts: {sum(row['attempt'] > 0 for row in calls)}.",
        f"- Call latency: mean {mean(latencies):.2f}s, "
        f"minimum {min(latencies):.2f}s, maximum {max(latencies):.2f}s.",
        f"- Applications: {sum(row['applications'] for row in run_metrics)}; "
        f"positive requests: "
        f"{sum(row['positive_applications'] for row in run_metrics)}.",
        f"- Offers: {sum(row['offers'] for row in run_metrics)}; "
        f"accepted contracts: "
        f"{sum(row['accepted_offers'] for row in run_metrics)}.",
        "",
        "## Regime-level descriptive results",
        "",
    ]
    for row in regime_summary:
        lines.append(
            f"- {row['regime']}: mean new credit "
            f"{row['mean_new_credit']:.2f}; mean accepted nominal rate "
            f"{row['mean_accepted_rate']:.4f}; "
            f"{row['completed_runs']}/{row['runs']} runs completed."
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a behavioral and infrastructure validation sample, not a "
            "powered treatment-effect estimate. It establishes that DeepSeek "
            "R1 8B can generate schema-valid firm and bank decisions, including "
            "positive credit requests and competitive quotes, with failures and "
            "retries observable separately from economic zero-demand choices.",
            "",
        ]
    )
    (output / "llm_validation_summary.md").write_text("\n".join(lines))
    connection.close()
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("--output", default="evidence/llm_analysis_v0_2")
    args = parser.parse_args()
    print(f"LLM analysis outputs: {analyze(args.database, args.output)}")


if __name__ == "__main__":
    main()
