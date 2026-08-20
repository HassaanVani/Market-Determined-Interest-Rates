from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import duckdb
import pandas as pd

from v03.config import ExperimentSpec, ShockSpec, load_calibration_bundle
from v03.consolidate import consolidate_shards, validate_consolidation
from v03.design import RunCell, clone_spec, seeds_for
from v03.provenance import sha256_file, tree_fingerprint, utc_now
from v03.runner import run_cells, write_run_manifest
from v03.statistics import matched_difference_in_differences, write_analysis_manifest

ADDENDUM_ID = "v0.4-local-sensitivity-2"
SEED_NAMESPACE = "robustness-v0.4-local-sensitivity-2"
PARAMETERS = (
    "production_alpha",
    "investment_share",
    "base_credit_demand",
    "risk_price",
    "liquidity_price",
    "capital_price",
)
MULTIPLIERS = (0.90, 1.10)
REPLICATIONS = 20


def _base_spec(protocol_path: str | Path) -> ExperimentSpec:
    payload = json.loads(Path(protocol_path).read_text())
    allowed = set(ExperimentSpec.model_fields)
    return ExperimentSpec.model_validate(
        {key: value for key, value in payload.items() if key in allowed}
    )


def parameter_sets(base: ExperimentSpec) -> list[tuple[str, ExperimentSpec]]:
    result = [("calibrated", base)]
    for name, multiplier in product(PARAMETERS, MULTIPLIERS):
        value = getattr(base.parameters, name) * multiplier
        parameters = base.parameters.model_copy(update={name: value})
        label = f"{name}_{'minus10' if multiplier < 1 else 'plus10'}"
        result.append(
            (
                label,
                clone_spec(
                    base,
                    parameters=parameters,
                    parameter_set_id=f"{ADDENDUM_ID}-{label}",
                ),
            )
        )
    return result


def local_cells(base: ExperimentSpec) -> list[RunCell]:
    cells = []
    demand_shock = (
        ShockSpec(
            shock_id="local_sensitivity_demand",
            shock_type="demand",
            start_period=8,
            duration=4,
            magnitude=0.25,
        ),
    )
    for label, parameter_spec in parameter_sets(base):
        for shocked in (False, True):
            scenario = f"local_{label}_{'shock' if shocked else 'baseline'}"
            spec = clone_spec(
                parameter_spec,
                scenario_id=scenario,
                shocks=demand_shock if shocked else (),
                seed_namespace=SEED_NAMESPACE,
                replications=REPLICATIONS,
                frozen=True,
            )
            for regime, replication in product(spec.rate_regimes, range(REPLICATIONS)):
                cells.append(
                    RunCell(
                        "local_sensitivity",
                        spec,
                        regime,
                        replication,
                        # Common random numbers across every parameter set make
                        # the one-at-a-time comparison a genuine local contrast.
                        seeds_for(SEED_NAMESPACE, replication),
                    )
                )
    return cells


def freeze_protocol(base_protocol: Path, calibration: Path, output: Path) -> dict:
    base = _base_spec(base_protocol)
    cells = local_cells(base)
    payload = {
        "addendum_id": ADDENDUM_ID,
        "status": "frozen",
        "frozen_at": utc_now(),
        "classification": "post-confirmatory_local_robustness_mapping",
        "supersedes": "v0.4-local-sensitivity-1",
        "supersession_reason": "v1 used different seed streams across parameter sets and is retained as an invalidated audit artifact",
        "purpose": "Map H3 in a compact one-at-a-time plus/minus 10 percent neighborhood of the frozen calibrated parameters.",
        "base_protocol_sha256": sha256_file(base_protocol),
        "calibration_sha256": sha256_file(calibration),
        "code_fingerprint": tree_fingerprint(Path.cwd()),
        "parameters": list(PARAMETERS),
        "multipliers": list(MULTIPLIERS),
        "design": "calibrated base plus one-at-a-time perturbations",
        "replications_per_regime_scenario_cell": REPLICATIONS,
        "parameter_sets": len(parameter_sets(base)),
        "planned_runs": len(cells),
        "seed_namespace": SEED_NAMESPACE,
        "outcomes": ["cumulative_new_credit", "cumulative_output"],
        "inference": "descriptive robustness mapping; not additional confirmatory tests",
    }
    if output.exists():
        existing = json.loads(output.read_text())
        stable = {k: v for k, v in payload.items() if k != "frozen_at"}
        old = {k: v for k, v in existing.items() if k != "frozen_at"}
        if stable != old:
            raise ValueError("existing local-sensitivity protocol differs")
        return existing
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def run(protocol_path, base_protocol, calibration_path, shards, workers) -> dict:
    protocol = json.loads(Path(protocol_path).read_text())
    if protocol.get("status") != "frozen" or protocol.get("addendum_id") != ADDENDUM_ID:
        raise ValueError("matching frozen local-sensitivity protocol required")
    if protocol["code_fingerprint"] != tree_fingerprint(Path.cwd()):
        raise ValueError("code fingerprint differs from frozen local sensitivity")
    cells = local_cells(_base_spec(base_protocol))
    if len(cells) != protocol["planned_runs"]:
        raise ValueError("local-sensitivity run count differs from protocol")
    results = run_cells(cells, shards, load_calibration_bundle(calibration_path), workers)
    write_run_manifest(results, Path(shards) / "run_manifest.json")
    summary = {
        "planned": len(cells),
        "completed": sum(row["status"] == "completed" for row in results),
        "failed": sum(row["status"] != "completed" for row in results),
    }
    if summary["failed"]:
        raise RuntimeError(json.dumps(summary))
    return summary


def analyze(catalog: Path, output: Path) -> dict:
    conn = duckdb.connect(str(catalog), read_only=True)
    conn.execute("SET memory_limit='1GB'")
    conn.execute("SET threads=1")
    frame = conn.execute("""
        WITH macro AS (
            SELECT run_id,
                   sum(CASE WHEN period BETWEEN 8 AND 23 THEN new_credit ELSE 0 END)
                       AS cumulative_new_credit,
                   sum(CASE WHEN period BETWEEN 8 AND 23 THEN aggregate_output ELSE 0 END)
                       AS cumulative_output
            FROM period_macro GROUP BY run_id
        )
        SELECT r.run_id, r.scenario_id, r.rate_regime, r.replication,
               r.parameter_set_id, m.* EXCLUDE(run_id)
        FROM experiment_runs r JOIN macro m USING(run_id)
        ORDER BY r.parameter_set_id, r.scenario_id, r.rate_regime, r.replication
        """).df()
    conn.close()
    frame["shock"] = frame.scenario_id.str.endswith("_shock")
    records = []
    for parameter_set, group in frame.groupby("parameter_set_id"):
        effects = matched_difference_in_differences(
            group, ("cumulative_new_credit", "cumulative_output")
        )
        effects.insert(0, "parameter_set_id", parameter_set)
        records.append(effects)
    effects = pd.concat(records, ignore_index=True)
    signs = {
        outcome: {
            "negative": int((group.estimate < 0).sum()),
            "positive": int((group.estimate > 0).sum()),
        }
        for outcome, group in effects.groupby("outcome")
    }
    output.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, table in (
        ("local_run_summaries.csv", frame),
        ("local_h3_effects.csv", effects),
    ):
        path = output / name
        table.to_csv(path, index=False)
        outputs.append(path)
    report = {
        "addendum_id": ADDENDUM_ID,
        "runs": len(frame),
        "parameter_sets": int(frame.parameter_set_id.nunique()),
        "sign_counts": signs,
        "interpretation": "descriptive local robustness mapping, not confirmatory inference",
    }
    report_path = output / "local_sensitivity_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    outputs.append(report_path)
    manifest = output / "local_sensitivity_manifest.json"
    write_analysis_manifest(outputs, manifest)
    return {**report, "manifest": manifest.as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen local H3 sensitivity addendum")
    parser.add_argument("command", choices=("freeze", "run", "consolidate", "verify", "analyze"))
    parser.add_argument("--base-protocol", default="evidence/v0.3/evidence_protocol_v0.3.json")
    parser.add_argument("--calibration", default="calibration/v0.3/recent_us.json")
    parser.add_argument("--protocol", default="evidence/v0.4/local_sensitivity_v2_protocol.json")
    parser.add_argument("--shards", default="evidence/v0.4/local_sensitivity_v2_shards")
    parser.add_argument("--parquet", default="evidence/v0.4/local_sensitivity_v2_parquet")
    parser.add_argument("--catalog", default="evidence/v0.4/local_sensitivity_v2.duckdb")
    parser.add_argument("--output", default="paper/v0.3/generated/local_sensitivity_v2")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze_protocol(Path(args.base_protocol), Path(args.calibration), Path(args.protocol))
    elif args.command == "run":
        result = run(args.protocol, args.base_protocol, args.calibration, args.shards, args.workers)
    elif args.command == "consolidate":
        result = consolidate_shards(args.shards, args.parquet, args.catalog, batch_size=5)
    elif args.command == "verify":
        result = validate_consolidation(args.shards, args.parquet, args.catalog)
    else:
        result = analyze(Path(args.catalog), Path(args.output))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
