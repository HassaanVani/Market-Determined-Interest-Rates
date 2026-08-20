from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import duckdb
import pandas as pd

from v03.config import load_calibration_bundle, load_experiment_spec
from v03.consolidate import consolidate_shards, validate_consolidation
from v03.design import RunCell, clone_spec, seeds_for
from v03.provenance import sha256_file, tree_fingerprint, utc_now
from v03.runner import run_cells, write_run_manifest
from v03.statistics import matched_regime_effects, write_analysis_manifest

ADDENDUM_ID = "v0.4-concentration-addendum-1"
SEED_NAMESPACE = "confirmatory-v0.4-concentration-addendum-1"
SETTINGS = ((30, 5, "low"), (30, 5, "high"), (100, 5, "high"))
REPLICATIONS = 25


def load_run_summaries(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("""
        WITH macro AS (
            SELECT run_id,
                   sum(new_credit) AS cumulative_new_credit,
                   sum(aggregate_output) AS cumulative_output,
                   sum(unresolved_liquidity_shortfall) AS unresolved_liquidity_shortfall,
                   avg(unfunded_demand_share) AS mean_unfunded_share
            FROM period_macro GROUP BY run_id
        ), allocation AS (
            SELECT run_id,
                   sum(productivity * received_credit) / nullif(sum(received_credit), 0)
                       AS credit_weighted_productivity
            FROM firm_states WHERE received_credit > 0 GROUP BY run_id
        )
        SELECT r.run_id, r.scenario_id, r.rate_regime, r.replication,
               m.*, a.credit_weighted_productivity
        FROM experiment_runs r
        JOIN macro m USING(run_id)
        LEFT JOIN allocation a USING(run_id)
        ORDER BY r.scenario_id, r.rate_regime, r.replication
        """).df()


def addendum_cells(base, replications: int = REPLICATIONS) -> list[RunCell]:
    cells = []
    for firms, banks, concentration in SETTINGS:
        parameters = base.parameters.model_copy(
            update={
                "n_firms": firms,
                "n_banks": banks,
                "deposit_concentration": concentration,
            }
        )
        scenario = f"addendum_concentration_{firms}_{banks}_{concentration}"
        spec = clone_spec(
            base,
            scenario_id=scenario,
            parameter_set_id=f"{ADDENDUM_ID}-{firms}-{banks}-{concentration}",
            parameters=parameters,
            replications=replications,
            seed_namespace=SEED_NAMESPACE,
            frozen=True,
        )
        for regime, replication in product(spec.rate_regimes, range(replications)):
            cells.append(
                RunCell(
                    "concentration_addendum",
                    spec,
                    regime,
                    replication,
                    seeds_for(SEED_NAMESPACE, replication),
                )
            )
    return cells


def freeze_protocol(spec_path: Path, calibration_path: Path, output: Path) -> dict:
    base = load_experiment_spec(spec_path)
    calibration = load_calibration_bundle(calibration_path)
    cells = addendum_cells(base)
    payload = {
        "addendum_id": ADDENDUM_ID,
        "status": "frozen",
        "frozen_at": utc_now(),
        "purpose": "Correct the no-op low/high deposit-concentration robustness cells; do not alter v0.3 confirmatory inference.",
        "classification": "post-confirmatory_design_correction",
        "base_specification": "v0.3",
        "base_spec_sha256": sha256_file(spec_path),
        "calibration_sha256": sha256_file(calibration_path),
        "calibration_fingerprint": calibration.fingerprint(),
        "code_fingerprint": tree_fingerprint(spec_path.resolve().parents[2]),
        "seed_namespace": SEED_NAMESPACE,
        "settings": [list(item) for item in SETTINGS],
        "replications_per_regime_cell": REPLICATIONS,
        "planned_runs": len(cells),
        "estimands": ["credit_weighted_productivity", "mean_unfunded_share"],
        "transformation": {
            "low": "equal deposit shares",
            "high": "largest sampled bank receives weight n_banks-1; other banks receive weight 1",
            "invariants": [
                "aggregate deposits",
                "each sampled bank's balance-sheet ratios",
                "all non-size rate and growth variables",
            ],
        },
        "interpretation": "Robustness of the within-cell market-minus-administered effect; not a causal estimate of concentration itself.",
    }
    if output.exists():
        existing = json.loads(output.read_text())
        stable = {k: v for k, v in payload.items() if k != "frozen_at"}
        old_stable = {k: v for k, v in existing.items() if k != "frozen_at"}
        if stable != old_stable:
            raise ValueError("existing concentration addendum protocol differs")
        return existing
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def run_addendum(protocol_path, spec_path, calibration_path, output, workers) -> dict:
    protocol = json.loads(Path(protocol_path).read_text())
    if protocol.get("status") != "frozen" or protocol.get("addendum_id") != ADDENDUM_ID:
        raise ValueError("a matching frozen concentration addendum is required")
    if protocol["code_fingerprint"] != tree_fingerprint(Path.cwd()):
        raise ValueError("code fingerprint differs from the frozen addendum")
    base = load_experiment_spec(spec_path)
    calibration = load_calibration_bundle(calibration_path)
    cells = addendum_cells(base)
    if len(cells) != protocol["planned_runs"]:
        raise ValueError("addendum run count differs from frozen protocol")
    results = run_cells(cells, output, calibration, workers)
    write_run_manifest(results, Path(output) / "run_manifest.json")
    result = {
        "planned": len(cells),
        "completed": sum(row["status"] == "completed" for row in results),
        "failed": sum(row["status"] != "completed" for row in results),
    }
    if result["failed"]:
        raise RuntimeError(json.dumps(result))
    return result


def analyze(catalog: Path, output: Path) -> dict:
    conn = duckdb.connect(str(catalog), read_only=True)
    conn.execute("SET memory_limit='1GB'")
    conn.execute("SET threads=2")
    summaries = load_run_summaries(conn)
    concentration = conn.execute("""
        WITH initial AS (
            SELECT run_id, bank_id, deposits,
                   row_number() OVER (PARTITION BY run_id, bank_id ORDER BY period) AS rn
            FROM bank_states
        ), totals AS (
            SELECT run_id,
                   sum(deposits) AS deposits,
                   sum(deposits * deposits) / (sum(deposits) * sum(deposits)) AS deposit_hhi
            FROM initial WHERE rn=1 GROUP BY run_id
        )
        SELECT r.run_id, r.scenario_id, r.rate_regime, r.replication,
               t.deposits AS opening_deposits, t.deposit_hhi
        FROM experiment_runs r JOIN totals t USING(run_id)
        ORDER BY r.scenario_id, r.rate_regime, r.replication
        """).df()
    conn.close()
    summaries = summaries.merge(concentration, on=["run_id", "scenario_id", "rate_regime", "replication"], validate="one_to_one")
    records = []
    for scenario, group in summaries.groupby("scenario_id"):
        effects = matched_regime_effects(
            group, ("credit_weighted_productivity", "mean_unfunded_share")
        )
        effects.insert(0, "scenario_id", scenario)
        effects.insert(1, "mean_opening_deposit_hhi", group.deposit_hhi.mean())
        records.append(effects)
    effects = pd.concat(records, ignore_index=True)
    output.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, frame in (
        ("concentration_run_summaries.csv", summaries),
        ("concentration_effects.csv", effects),
    ):
        path = output / name
        frame.to_csv(path, index=False)
        outputs.append(path)
    report = {
        "addendum_id": ADDENDUM_ID,
        "runs": len(summaries),
        "scenarios": int(summaries.scenario_id.nunique()),
        "deposit_hhi_by_scenario": {
            key: float(value)
            for key, value in summaries.groupby("scenario_id").deposit_hhi.mean().items()
        },
        "interpretation": "Within-cell regime robustness only; concentration is not assigned a causal coefficient.",
    }
    report_path = output / "concentration_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    outputs.append(report_path)
    manifest = output / "concentration_manifest.json"
    write_analysis_manifest(outputs, manifest)
    return {**report, "manifest": manifest.as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen concentration robustness addendum")
    parser.add_argument("command", choices=("freeze", "run", "consolidate", "analyze", "verify"))
    parser.add_argument("--spec", default="configs/v0.3/main.yaml")
    parser.add_argument("--calibration", default="calibration/v0.3/recent_us.json")
    parser.add_argument("--protocol", default="evidence/v0.4/concentration_protocol.json")
    parser.add_argument("--shards", default="evidence/v0.4/concentration_shards")
    parser.add_argument("--parquet", default="evidence/v0.4/parquet")
    parser.add_argument("--catalog", default="evidence/v0.4/evidence.duckdb")
    parser.add_argument("--output", default="paper/v0.3/generated/concentration_addendum")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze_protocol(Path(args.spec), Path(args.calibration), Path(args.protocol))
    elif args.command == "run":
        result = run_addendum(args.protocol, args.spec, args.calibration, args.shards, args.workers)
    elif args.command == "consolidate":
        result = consolidate_shards(args.shards, args.parquet, args.catalog, batch_size=5)
    elif args.command == "verify":
        result = validate_consolidation(args.shards, args.parquet, args.catalog)
    else:
        result = analyze(Path(args.catalog), Path(args.output))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
