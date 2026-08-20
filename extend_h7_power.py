"""Add prespecified matched H7 replications after pilot power analysis."""

import argparse
import json
import sqlite3
from pathlib import Path

from engine.experiment import BehaviorMode, RateRegime, SeedBundle
from engine.model import MacroModel
from engine.provenance import source_fingerprint
from run_paper_suite import CONDITIONS

EXTENDED_SCENARIOS = {
    "h7_scarce_unavailable",
    "h7_scarce_penalty",
    "h7_scarce_limited",
}


def validate_existing_database(path, expected_fingerprint, start, stop):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT config_json, status FROM experiment_runs"
    ).fetchall()
    if not rows:
        raise ValueError("Evidence database contains no registered runs")
    configs = [json.loads(row["config_json"]) for row in rows]
    fingerprints = {config["source_fingerprint"] for config in configs}
    if fingerprints != {expected_fingerprint}:
        raise ValueError(
            "Current DGP fingerprint does not match the existing evidence database"
        )
    if any(row["status"] != "completed" for row in rows):
        raise ValueError("Existing evidence database has non-completed runs")

    target_seeds = {10_000 + replication for replication in range(start, stop)}
    for config in configs:
        if (
            config["scenario_name"] in EXTENDED_SCENARIOS
            and config["seeds"]["environment"] in target_seeds
        ):
            raise ValueError("Requested H7 extension overlaps existing replications")
    connection.close()


def extend(path, start=30, stop=40, horizon=12):
    path = Path(path).resolve()
    if start < 0 or stop <= start:
        raise ValueError("Require 0 <= start < stop")
    code_fingerprint = source_fingerprint()
    validate_existing_database(path, code_fingerprint, start, stop)
    conditions = [
        condition
        for condition in CONDITIONS
        if condition["scenario_name"] in EXTENDED_SCENARIOS
    ]

    completed = 0
    total = len(conditions) * 2 * (stop - start)
    for condition in conditions:
        for regime in (RateRegime.ADMINISTERED, RateRegime.MARKET):
            for replication in range(start, stop):
                seed = 10_000 + replication
                model = MacroModel(
                    n_firms=9,
                    n_banks=3,
                    db_path=str(path),
                    rate_regime=regime,
                    behavior_mode=BehaviorMode.RULE,
                    scenario_name=condition["scenario_name"],
                    source_fingerprint=code_fingerprint,
                    experiment_horizon=horizon,
                    seeds=SeedBundle(
                        environment=seed,
                        matching=seed + 100_000,
                        shocks=seed + 200_000,
                        behavior=seed + 300_000,
                    ),
                    heterogeneity_scale=0.15,
                    reserve_requirement=condition["reserve_requirement"],
                    capital_requirement=0.08,
                    leverage_limit=1.5,
                    initial_reserves_per_bank=condition["initial_reserves_per_bank"],
                    initial_bank_equity=100.0,
                    lender_of_last_resort=condition["lender_of_last_resort"],
                    emergency_penalty_spread=0.02,
                    emergency_borrowing_limit_ratio=condition.get(
                        "emergency_borrowing_limit_ratio", 1.0
                    ),
                    shocks=condition["shocks"],
                )
                try:
                    for _ in range(horizon):
                        model.step()
                    status = model.complete_run()
                except Exception as exc:
                    model.ledger.update_run_status(
                        model.run_id, "failed", str(exc)[:1000]
                    )
                    status = "failed"
                if status != "completed":
                    raise RuntimeError(f"Extension run failed: {model.run_id}")
                completed += 1
    print(f"Completed H7 extension runs: {completed}/{total}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("--start", type=int, default=30)
    parser.add_argument("--stop", type=int, default=40)
    parser.add_argument("--horizon", type=int, default=12)
    args = parser.parse_args()
    extend(args.database, args.start, args.stop, args.horizon)


if __name__ == "__main__":
    main()
