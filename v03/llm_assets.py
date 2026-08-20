from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from v03.statistics import percentile_paired_bootstrap, write_analysis_manifest


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_llm_assets(source: str | Path, output: str | Path) -> dict:
    source = Path(source)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = _records(source)
    decisions = [
        row
        for row in records
        if row.get("record_type") == "decision" and row.get("decision") is not None
    ]
    completed = {
        row["pair"]
        for row in records
        if row.get("record_type") == "pair_status" and row.get("completed")
    }
    decisions = [row for row in decisions if row["pair"] in completed]

    decision_rows = []
    call_rows = []
    for row in decisions:
        decision = row["decision"]
        rule = row["rule_decision"]
        value_name = (
            "requested_principal" if row["role"] == "firm" else "approved_principal"
        )
        item = {
            "pair": row["pair"],
            "regime": row["regime"],
            "period": row["period"],
            "agent_id": row["agent_id"],
            "role": row["role"],
            "quantity": decision[value_name],
            "rule_quantity": rule[value_name],
            "quantity_difference_llm_minus_rule": decision[value_name] - rule[value_name],
            "maturity": decision["maturity"],
            "rule_maturity": rule["maturity"],
            "nominal_rate": decision.get("nominal_rate"),
            "rule_nominal_rate": rule.get("nominal_rate"),
        }
        decision_rows.append(item)
        for call in row["calls"]:
            call_rows.append(
                {
                    "pair": row["pair"],
                    "regime": row["regime"],
                    "period": row["period"],
                    "agent_id": row["agent_id"],
                    "role": row["role"],
                    **call,
                }
            )
    decisions_frame = pd.DataFrame(decision_rows)
    calls_frame = pd.DataFrame(call_rows)

    pair_means = (
        decisions_frame.groupby(["pair", "regime", "role"], as_index=False)
        .agg(
            quantity=("quantity", "mean"),
            rule_quantity=("rule_quantity", "mean"),
            nominal_rate=("nominal_rate", "mean"),
            rule_nominal_rate=("rule_nominal_rate", "mean"),
        )
    )
    paired_records = []
    for role, outcome in (
        ("firm", "requested_principal"),
        ("bank", "approved_principal"),
        ("bank", "nominal_rate"),
    ):
        column = "nominal_rate" if outcome == "nominal_rate" else "quantity"
        subset = pair_means[pair_means.role == role]
        wide = subset.pivot(index="pair", columns="regime", values=column)
        paired_records.append(
            {
                "outcome": outcome,
                "contrast": "market_minus_administered",
                **percentile_paired_bootstrap(wide["market"] - wide["administered"]),
            }
        )
    paired_frame = pd.DataFrame(paired_records)

    rule_records = []
    for (regime, role), group in pair_means.groupby(["regime", "role"]):
        for outcome, actual, rule in (
            ("quantity", "quantity", "rule_quantity"),
            ("nominal_rate", "nominal_rate", "rule_nominal_rate"),
        ):
            differences = group[actual] - group[rule]
            if differences.notna().any():
                rule_records.append(
                    {
                        "regime": regime,
                        "role": role,
                        "outcome": outcome,
                        "contrast": "llm_minus_rule",
                        **percentile_paired_bootstrap(differences),
                    }
                )
    rule_frame = pd.DataFrame(rule_records)

    audit_rows = []
    for row in records:
        if row.get("record_type") != "prompt_audit" or row.get("decision") is None:
            continue
        audit_rows.append(
            {
                "state_index": row["state_index"],
                "template": row["template"],
                "nominal_rate": row["decision"]["nominal_rate"],
                "approved_principal": row["decision"]["approved_principal"],
            }
        )
    audit_frame = pd.DataFrame(audit_rows)
    audit_ranges = (
        audit_frame.groupby("state_index", as_index=False)
        .agg(
            rate_min=("nominal_rate", "min"),
            rate_max=("nominal_rate", "max"),
            approval_min=("approved_principal", "min"),
            approval_max=("approved_principal", "max"),
        )
    )
    audit_ranges["rate_range"] = audit_ranges.rate_max - audit_ranges.rate_min
    audit_ranges["approval_range"] = (
        audit_ranges.approval_max - audit_ranges.approval_min
    )

    diagnostics = {
        "completed_pairs": len(completed),
        "decision_records": len(decisions_frame),
        "calls": len(calls_frame),
        "valid_calls": int(calls_frame.status.eq("valid").sum()),
        "valid_call_rate": float(calls_frame.status.eq("valid").mean()),
        "retry_calls": int(calls_frame.attempt.gt(1).sum()),
        "mean_latency_seconds": float(calls_frame.latency_seconds.mean()),
        "failure_types": {
            str(key): int(value)
            for key, value in calls_frame.failure_type.dropna().value_counts().items()
        },
    }
    outputs = []
    for name, frame in (
        ("llm_decisions.csv", decisions_frame),
        ("llm_call_diagnostics.csv", calls_frame),
        ("llm_paired_regime_effects.csv", paired_frame),
        ("llm_rule_comparisons.csv", rule_frame),
        ("llm_prompt_audit.csv", audit_ranges),
    ):
        path = output / name
        frame.to_csv(path, index=False)
        outputs.append(path)
    diagnostics_path = output / "llm_diagnostics.json"
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n")
    outputs.append(diagnostics_path)
    manifest = output / "llm_assets_manifest.json"
    write_analysis_manifest(outputs, manifest)
    return {**diagnostics, "manifest": manifest.as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate manuscript-ready LLM assets")
    parser.add_argument("--source", default="evidence/v0.3/llm/deepseek_r1_8b.jsonl")
    parser.add_argument("--output", default="paper/v0.3/generated/llm")
    args = parser.parse_args()
    print(json.dumps(build_llm_assets(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
