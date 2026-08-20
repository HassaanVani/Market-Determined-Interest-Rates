import argparse
from pathlib import Path

from engine.experiment import BehaviorMode, RateRegime, SeedBundle
from engine.model import MacroModel
from engine.provenance import source_fingerprint
from engine.shocks import Shock

CONDITIONS = [
    {
        "scenario_name": "h2_baseline",
        "initial_reserves_per_bank": 300.0,
        "reserve_requirement": 0.10,
        "lender_of_last_resort": "penalty",
        "shocks": [],
    },
    {
        "scenario_name": "h3_baseline",
        "initial_reserves_per_bank": 300.0,
        "reserve_requirement": 0.10,
        "lender_of_last_resort": "penalty",
        "shocks": [],
    },
    {
        "scenario_name": "h3_demand",
        "initial_reserves_per_bank": 300.0,
        "reserve_requirement": 0.10,
        "lender_of_last_resort": "penalty",
        "shocks": [
            Shock(
                shock_id="h3_demand_shock",
                shock_type="demand",
                start_period=4,
                duration=2,
                magnitude=0.25,
            )
        ],
    },
    {
        "scenario_name": "h7_abundant_unavailable",
        "initial_reserves_per_bank": 500.0,
        "reserve_requirement": 0.30,
        "lender_of_last_resort": "unavailable",
        "shocks": [],
    },
    {
        "scenario_name": "h7_scarce_unavailable",
        "initial_reserves_per_bank": 80.0,
        "reserve_requirement": 0.30,
        "lender_of_last_resort": "unavailable",
        "shocks": [],
    },
    {
        "scenario_name": "h7_scarce_penalty",
        "initial_reserves_per_bank": 80.0,
        "reserve_requirement": 0.30,
        "lender_of_last_resort": "penalty",
        "shocks": [],
    },
    {
        "scenario_name": "h7_scarce_limited",
        "initial_reserves_per_bank": 80.0,
        "reserve_requirement": 0.30,
        "lender_of_last_resort": "limited",
        "emergency_borrowing_limit_ratio": 0.50,
        "shocks": [],
    },
]


def run_suite(output_path, replications=30, horizon=12):
    output_path = Path(output_path).resolve()
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to append to existing evidence database: {output_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    code_fingerprint = source_fingerprint()

    results = []
    for condition in CONDITIONS:
        for regime in (RateRegime.ADMINISTERED, RateRegime.MARKET):
            completed = 0
            for replication in range(replications):
                seed = 10_000 + replication
                seeds = SeedBundle(
                    environment=seed,
                    matching=seed + 100_000,
                    shocks=seed + 200_000,
                    behavior=seed + 300_000,
                )
                model = MacroModel(
                    n_firms=9,
                    n_banks=3,
                    db_path=str(output_path),
                    rate_regime=regime,
                    behavior_mode=BehaviorMode.RULE,
                    scenario_name=condition["scenario_name"],
                    source_fingerprint=code_fingerprint,
                    experiment_horizon=horizon,
                    seeds=seeds,
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
                except Exception:
                    status = "failed"

                results.append(
                    {
                        "scenario": condition["scenario_name"],
                        "regime": regime.value,
                        "replication": replication,
                        "run_id": model.run_id,
                        "status": status,
                    }
                )
                if status == "completed":
                    completed += 1

            print(
                f"{condition['scenario_name']:<26} {regime.value:<13} "
                f"{completed}/{replications} completed"
            )

    return output_path, results


def main():
    parser = argparse.ArgumentParser(
        description="Generate the preregistered rule-based paper pilot suite."
    )
    parser.add_argument("--db", default="evidence/paper_pilot_v0_1.sqlite")
    parser.add_argument("--replications", type=int, default=30)
    parser.add_argument("--horizon", type=int, default=12)
    args = parser.parse_args()

    output_path, results = run_suite(
        args.db, replications=args.replications, horizon=args.horizon
    )
    failed = [row for row in results if row["status"] != "completed"]
    print(f"Evidence database: {output_path}")
    print(f"Completed runs: {len(results) - len(failed)}/{len(results)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
