import argparse
from itertools import product
from pathlib import Path

from engine.experiment import BehaviorMode, RateRegime, SeedBundle
from engine.model import MacroModel
from engine.provenance import source_fingerprint
from engine.shocks import Shock


def selected_values(selection, enum_type):
    if selection == "all":
        return list(enum_type)
    return [enum_type(selection)]


def run_experiments(args):
    output_path = Path(args.db).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    regimes = selected_values(args.regime, RateRegime)
    behaviors = selected_values(args.behavior, BehaviorMode)
    summaries = []
    code_fingerprint = source_fingerprint()

    for rate_regime, behavior_mode in product(regimes, behaviors):
        for replication in range(args.replications):
            seed = args.seed_start + replication
            seed_bundle = SeedBundle(
                environment=seed,
                matching=seed + 10_000,
                shocks=seed + 20_000,
                behavior=seed + 30_000,
            )
            shocks = []
            if args.shock_type != "none":
                shocks.append(
                    Shock(
                        shock_id=f"{args.shock_type}_shock",
                        shock_type=args.shock_type,
                        start_period=args.shock_start,
                        duration=args.shock_duration,
                        magnitude=args.shock_magnitude,
                    )
                )
            model = MacroModel(
                n_firms=args.firms,
                n_banks=args.banks,
                db_path=str(output_path),
                rate_regime=rate_regime,
                behavior_mode=behavior_mode,
                policy_rate=args.policy_rate,
                experiment_horizon=args.steps,
                llm_model=args.llm_model,
                llm_temperature=args.temperature,
                llm_timeout_seconds=args.llm_timeout_seconds,
                llm_max_retries=args.llm_max_retries,
                llm_max_tokens=args.llm_max_tokens,
                llm_reasoning_effort=args.llm_reasoning_effort,
                prompt_version=args.prompt_version,
                reserve_requirement=args.reserve_requirement,
                capital_requirement=args.capital_requirement,
                leverage_limit=args.leverage_limit,
                initial_reserves_per_bank=args.initial_reserves_per_bank,
                initial_bank_equity=args.initial_bank_equity,
                lender_of_last_resort=args.lender_of_last_resort,
                emergency_penalty_spread=args.emergency_penalty_spread,
                emergency_borrowing_limit_ratio=(args.emergency_borrowing_limit_ratio),
                shocks=shocks,
                heterogeneity_scale=args.heterogeneity_scale,
                scenario_name=args.scenario_name,
                source_fingerprint=code_fingerprint,
                seeds=seed_bundle,
            )

            try:
                for _ in range(args.steps):
                    model.step()
                status = model.complete_run()
            except Exception:
                status = "failed"

            macro = model.ledger.get_period_macro(model.run_id)
            final = macro[-1]
            summaries.append(
                {
                    "run_id": model.run_id,
                    "regime": rate_regime.value,
                    "behavior": behavior_mode.value,
                    "replication": replication,
                    "status": status,
                    "deposit_money": final["deposit_money"],
                    "outstanding_credit": final["outstanding_credit"],
                    "defaults": sum(row["defaults"] for row in macro),
                }
            )

    return output_path, summaries


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run versioned factorial pilot experiments."
    )
    parser.add_argument(
        "--regime",
        choices=["administered", "market", "all"],
        default="all",
    )
    parser.add_argument("--behavior", choices=["rule", "llm", "all"], default="rule")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--replications", type=int, default=1)
    parser.add_argument("--firms", type=int, default=5)
    parser.add_argument("--banks", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--db", default="pilot_results.sqlite")
    parser.add_argument("--policy-rate", type=float, default=0.03)
    parser.add_argument("--reserve-requirement", type=float, default=0.10)
    parser.add_argument("--capital-requirement", type=float, default=0.08)
    parser.add_argument("--leverage-limit", type=float, default=1.5)
    parser.add_argument("--initial-reserves-per-bank", type=float, default=1000.0)
    parser.add_argument("--initial-bank-equity", type=float, default=100.0)
    parser.add_argument(
        "--lender-of-last-resort",
        choices=["unavailable", "penalty", "limited"],
        default="unavailable",
    )
    parser.add_argument("--emergency-penalty-spread", type=float, default=0.02)
    parser.add_argument("--emergency-borrowing-limit-ratio", type=float, default=1.0)
    parser.add_argument(
        "--shock-type",
        choices=["none", "demand", "productivity", "inflation_expectation"],
        default="none",
    )
    parser.add_argument("--shock-start", type=int, default=3)
    parser.add_argument("--shock-duration", type=int, default=1)
    parser.add_argument("--shock-magnitude", type=float, default=0.20)
    parser.add_argument("--heterogeneity-scale", type=float, default=0.0)
    parser.add_argument("--scenario-name", default="pilot")
    parser.add_argument("--llm-model", default="deepseek-r1:8b")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--llm-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--llm-max-retries", type=int, default=2)
    parser.add_argument("--llm-max-tokens", type=int, default=256)
    parser.add_argument(
        "--llm-reasoning-effort",
        choices=["none", "low", "medium", "high"],
        default="none",
    )
    parser.add_argument("--prompt-version", default="0.1")
    return parser


def main():
    output_path, summaries = run_experiments(build_parser().parse_args())
    print(f"Results database: {output_path}")
    for row in summaries:
        print(
            f"{row['regime']:<13} {row['behavior']:<4} "
            f"rep={row['replication']:<3} status={row['status']:<9} "
            f"deposits={row['deposit_money']:.2f} "
            f"credit={row['outstanding_credit']:.2f} "
            f"defaults={row['defaults']}"
        )


if __name__ == "__main__":
    main()
