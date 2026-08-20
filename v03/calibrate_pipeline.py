from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from v03.calibration import (
    MinimumDistanceCalibrator,
    assert_calibration_gate,
    holdout_gate,
    make_calibration_bundle,
    write_calibration_report,
)
from v03.data_pipeline import business_loan_moments, verify_source_manifest
from v03.config import ModelParameters
from v03.validation import dynamic_validation_moments
from v03.survey_extract import quarterly_fred


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit the deterministic v0.3 minimum-distance calibration"
    )
    parser.add_argument(
        "--bank-panel",
        default="data/derived/v0.3/bank_calibration_2022q1_2024q4.parquet",
    )
    parser.add_argument(
        "--bootstrap", default="data/derived/v0.3/bank_bootstrap_moments.parquet"
    )
    parser.add_argument(
        "--validation",
        default="data/derived/v0.3/bank_validation_2025q1_2025q4.parquet",
    )
    parser.add_argument(
        "--business-panel", default="data/derived/v0.3/business_loans.parquet"
    )
    parser.add_argument("--policy-rate", default="data/raw/v0.3/fred/DFF_2022_2025.csv")
    parser.add_argument(
        "--source-manifest", default="data/manifests/source_manifest_v0.3.json"
    )
    parser.add_argument("--output", default="calibration/v0.3/recent_us.json")
    parser.add_argument("--report", default="calibration/v0.3/calibration_report.json")
    parser.add_argument("--maxiter", type=int, default=100)
    args = parser.parse_args()
    paths = [
        Path(args.bank_panel),
        Path(args.bootstrap),
        Path(args.validation),
        Path(args.business_panel),
        Path(args.policy_rate),
    ]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"required calibration input missing: {path}")
    source_records = verify_source_manifest(args.source_manifest)
    fingerprint_paths = [record.local_path for record in source_records] + paths
    banks = pd.read_parquet(paths[0])
    bootstrap = pd.read_parquet(paths[1])
    validation = pd.read_parquet(paths[2])
    business = pd.read_parquet(paths[3])
    calibration_business = business[business.quarter < "2025Q1"]
    if calibration_business.empty:
        raise ValueError("FR 2028D calibration sample has no pre-2025 observations")
    terms = business_loan_moments(calibration_business)
    median_deposits = float(banks.deposits.median())
    targets = {
        "normalized_loan_amount": terms["business_loan_amount"]
        / (median_deposits * 1000.0)
        * 100.0,
        "business_loan_maturity": terms["business_loan_maturity"] / 3.0,
        "loan_rate_mean": terms["loan_rate_mean"],
        "loan_rate_dispersion": terms["loan_rate_dispersion"],
    }
    empirical_rate_variance = max(
        1e-8,
        float(calibration_business.effective_rate.var(ddof=1))
        / len(calibration_business),
    )
    variances = {
        "normalized_loan_amount": max(
            1e-8,
            float(calibration_business.loan_amount_2025q4.var(ddof=1))
            / len(calibration_business)
            / (median_deposits * 1000.0) ** 2
            * 100.0**2,
        ),
        "business_loan_maturity": max(
            1e-8,
            float(calibration_business.maturity_months.var(ddof=1))
            / len(calibration_business)
            / 9.0,
        ),
        "loan_rate_mean": empirical_rate_variance,
        "loan_rate_dispersion": max(1e-8, empirical_rate_variance / 2),
    }
    bounds = {
        "base_credit_demand": (0.0001, 40.0),
        "loan_maturity": (1.0, 24.0),
        "market_intercept": (-0.02, 0.12),
        "risk_price": (0.001, 0.08),
    }

    def simulator(parameters, seed):
        # These are the analytically implied stationary moments of the pricing
        # and demand blocks. Dynamic validation is performed separately.
        mean_local_state = 0.025
        risk_state_sd = max(0.05, float(banks.ci_chargeoff_rate.std(ddof=1) * 100))
        return {
            "normalized_loan_amount": parameters["base_credit_demand"],
            "business_loan_maturity": round(parameters["loan_maturity"]),
            "loan_rate_mean": 0.015 + parameters["market_intercept"] + mean_local_state,
            "loan_rate_dispersion": parameters["risk_price"] * risk_state_sd,
        }

    starts = tuple(range(34000, 34010))
    calibrator = MinimumDistanceCalibrator(targets, variances, bounds, simulator)
    best, all_starts = calibrator.fit(starts=starts, maxiter=args.maxiter)
    fitted = dict(best.parameters)
    fitted["loan_maturity"] = int(round(fitted["loan_maturity"]))
    vector = np.array([fitted[name] for name in bounds], dtype=float)
    discrete_objective = calibrator.objective(vector, best.start_seed)
    best = replace(
        best,
        parameters=fitted,
        objective=discrete_objective,
        normalized_rmse=float(np.sqrt(discrete_objective)),
    )
    policy = quarterly_fred(paths[4], "DFF")
    calibration_policy = float(policy[policy.quarter < "2025Q1"].DFF.mean()) / 100.0
    validation_policy = (
        float(policy[policy.quarter.str.startswith("2025")].DFF.mean()) / 100.0
    )
    fitted = dict(best.parameters)
    fitted["policy_rate"] = calibration_policy
    median_bank_deposits_units = 100.0
    median_bank_loans_units = float(banks.loans_deposits.median()) * 100.0
    firms_per_bank = ModelParameters().n_firms / ModelParameters().n_banks
    representative_firm_deposits = median_bank_deposits_units / firms_per_bank
    representative_firm_debt = median_bank_loans_units / firms_per_bank
    representative_firm_equity = (
        representative_firm_deposits
        + ModelParameters().initial_firm_capital
        - representative_firm_debt
    )
    representative_leverage = representative_firm_debt / max(
        representative_firm_equity, 1e-9
    )
    calibration_ld_target = float(
        banks[banks.quarter == "2024Q4"].loans_deposits.median()
    )
    average_funding_gap = float(
        (banks[banks.quarter == "2024Q4"].loans_deposits - calibration_ld_target)
        .clip(lower=0)
        .mean()
    )
    average_local_component = ModelParameters().administered_pass_through * (
        ModelParameters().inflation_pass_through * 0.02
        + fitted["risk_price"] * representative_leverage
        + ModelParameters().deposit_funding_price * average_funding_gap
    )
    fitted["administered_spread"] = max(
        0.0, terms["loan_rate_mean"] - calibration_policy - average_local_component
    )
    fitted["legacy_book_rate"] = terms["loan_rate_mean"]
    fitted["reserve_requirement"] = 0.0
    fitted["reserve_remuneration_rate"] = calibration_policy

    # Forecast incumbent portfolio growth using only the 2022--2024 sample.
    # The small deterministic regression captures the observed trend and the
    # contemporaneous funding-rate state; 2025 outcomes never enter the fit.
    bank_dynamics = banks.sort_values(["bank_id", "quarter"]).copy()
    if "ci_loan_growth" not in bank_dynamics:
        bank_dynamics["ci_loan_growth"] = bank_dynamics.groupby("bank_id")[
            "ci_loans"
        ].pct_change()
    bank_dynamics["non_ci_loans"] = (
        bank_dynamics["gross_loans"] - bank_dynamics["ci_loans"]
    )
    bank_dynamics["non_ci_loan_growth"] = bank_dynamics.groupby("bank_id")[
        "non_ci_loans"
    ].pct_change()

    def forecast_growth(column: str) -> float:
        quarterly = bank_dynamics.groupby("quarter")[column].median().dropna()
        rates = policy.set_index("quarter").DFF / 100.0
        t = np.arange(1, len(quarterly) + 1, dtype=float)
        x = np.column_stack(
            [np.ones(len(quarterly)), t, [rates.loc[q] for q in quarterly.index]]
        )
        beta = np.linalg.lstsq(x, quarterly.to_numpy(float), rcond=None)[0]
        forecast_quarters = tuple(f"2025Q{q}" for q in range(1, 5))
        forecast_t = np.arange(len(quarterly) + 1, len(quarterly) + 5, dtype=float)
        forecast_x = np.column_stack(
            [
                np.ones(4),
                forecast_t,
                [rates.loc[q] for q in forecast_quarters],
            ]
        )
        return float(np.clip(np.mean(forecast_x @ beta), -0.10, 0.10))

    # Aggregate incumbent growth follows the total-loan forecast. Explicit
    # agent contracts supply the decomposed C&I margin below.
    fitted["legacy_loan_growth_rate"] = forecast_growth("loan_growth")
    fitted["legacy_ci_loan_growth_rate"] = forecast_growth("ci_loan_growth")
    # Loan-size calibration identifies the per-application quantity. With one
    # application per representative firm per quarter, the explicit agent flow
    # must be removed from incumbent C&I growth to avoid counting it twice.
    fitted["demand_return_sensitivity"] = 0.0
    gross_experimental_flow = (
        fitted["base_credit_demand"]
        * ModelParameters().n_firms
        / (median_bank_loans_units * ModelParameters().n_banks)
    )
    seasoned_cohorts = 3.0
    net_experimental_flow = gross_experimental_flow * (
        1.0 - seasoned_cohorts / fitted["loan_maturity"]
    )
    median_ci_share = max(float(banks.ci_share.median()), 1e-9)
    fitted["legacy_ci_loan_growth_rate"] = float(
        np.clip(
            fitted["legacy_ci_loan_growth_rate"]
            - net_experimental_flow / median_ci_share,
            -0.25,
            0.25,
        )
    )

    # The median bank-level proxy is robust to the highly skewed bank-size
    # distribution; the previous ratio of aggregate medians was not.
    bank_dynamics["equity_growth"] = bank_dynamics.groupby("bank_id")[
        "equity"
    ].pct_change()
    recent = bank_dynamics[bank_dynamics.quarter >= "2024Q1"].copy()
    retention_proxy = (
        recent["equity_growth"]
        * recent["equity"]
        / (
            recent["gross_loans"]
            * fitted["legacy_book_rate"]
            / ModelParameters().periods_per_year
        )
    ).replace([np.inf, -np.inf], np.nan)
    fitted["bank_income_retention_rate"] = float(
        np.clip(retention_proxy.median(), 0, 1)
    )
    liquidity_panel = bank_dynamics[["bank_id", "quarter", "liquid_deposits"]].copy()
    liquidity_panel["lagged_liquidity"] = liquidity_panel.groupby("bank_id")[
        "liquid_deposits"
    ].shift()
    liquidity_panel["liquidity_change"] = (
        liquidity_panel["liquid_deposits"] - liquidity_panel["lagged_liquidity"]
    )
    liquidity_fit = liquidity_panel.dropna()
    bank_gap = ModelParameters().liquidity_target_ratio - liquidity_fit[
        "lagged_liquidity"
    ].to_numpy(float)
    bank_speed = float(
        np.dot(bank_gap, liquidity_fit["liquidity_change"])
        / max(np.dot(bank_gap, bank_gap), 1e-12)
    )
    quarterly_liquidity = bank_dynamics.groupby("quarter")["liquid_deposits"].median()
    quarterly_change = quarterly_liquidity.diff().dropna()
    quarterly_gap = (
        ModelParameters().liquidity_target_ratio
        - quarterly_liquidity.shift().loc[quarterly_change.index]
    )
    aggregate_speed = float(
        np.dot(quarterly_gap, quarterly_change)
        / max(np.dot(quarterly_gap, quarterly_gap), 1e-12)
    )
    fitted["liquidity_adjustment_speed"] = float(
        np.clip((bank_speed + aggregate_speed) / 2.0, 0.0, 1.0)
    )
    fitted["loan_deposit_target"] = calibration_ld_target
    funding_panel = bank_dynamics[["bank_id", "quarter", "loans_deposits"]].copy()
    funding_panel["lagged_ratio"] = funding_panel.groupby("bank_id")[
        "loans_deposits"
    ].shift()
    funding_panel["ratio_change"] = (
        funding_panel["loans_deposits"] - funding_panel["lagged_ratio"]
    )
    funding_fit = funding_panel.dropna()
    bank_ratio_gap = (
        funding_fit["lagged_ratio"].to_numpy(float) - fitted["loan_deposit_target"]
    )
    bank_funding_speed = float(
        -np.dot(bank_ratio_gap, funding_fit["ratio_change"])
        / max(np.dot(bank_ratio_gap, bank_ratio_gap), 1e-12)
    )
    quarterly_ratio = bank_dynamics.groupby("quarter")["loans_deposits"].median()
    quarterly_ratio_change = quarterly_ratio.diff().dropna()
    aggregate_ratio_gap = (
        quarterly_ratio.shift().loc[quarterly_ratio_change.index]
        - fitted["loan_deposit_target"]
    )
    aggregate_funding_speed = float(
        -np.dot(aggregate_ratio_gap, quarterly_ratio_change)
        / max(np.dot(aggregate_ratio_gap, aggregate_ratio_gap), 1e-12)
    )
    aggregate_deposit_adjustment = (bank_funding_speed + aggregate_funding_speed) / 2.0
    mobile_household_deposit_share = 0.10
    fitted["deposit_reallocation_speed"] = float(
        np.clip(
            aggregate_deposit_adjustment / mobile_household_deposit_share,
            0.0,
            1.0,
        )
    )
    best = replace(best, parameters=fitted)
    transform_hash = hashlib.sha256(
        Path("v03/data_pipeline.py").read_bytes()
    ).hexdigest()
    bank_variables = (
        "capital_assets",
        "loans_deposits",
        "liquid_deposits",
        "ci_share",
        "deposit_growth",
        "loan_growth",
        "ci_chargeoff_rate",
    )
    bank_targets = {name: float(banks[name].median()) for name in bank_variables}
    intervals = {}
    for name in bank_variables:
        boot = bootstrap[
            (bootstrap.period == "validation")
            & (bootstrap.variable == name)
            & (bootstrap.statistic == "median")
            & (bootstrap.weighting == "equal_bank")
        ].value.dropna()
        empirical = float(validation[name].median())
        se = (
            float(boot.std(ddof=1))
            if len(boot) > 1
            else float(validation[name].std(ddof=1) / np.sqrt(len(validation)))
        )
        intervals[name] = (
            empirical,
            max(se, 1e-12),
            float(boot.quantile(0.025)),
            float(boot.quantile(0.975)),
        )
    # Loan terms form the eighth predeclared group. Their standardized average
    # is represented by the effective-rate mean, the most precise survey target.
    validation_business = business[business.quarter.str.startswith("2025")]
    rate_mean = float(validation_business.effective_rate.mean())
    rate_se = max(
        1e-12,
        float(
            validation_business.effective_rate.std(ddof=1)
            / np.sqrt(len(validation_business))
        ),
    )
    intervals["business_loan_terms"] = (
        rate_mean,
        rate_se,
        rate_mean - 1.96 * rate_se,
        rate_mean + 1.96 * rate_se,
    )
    provisional = make_calibration_bundle(
        "recent-us-2022q1-2024q4",
        best,
        {**bank_targets, **targets},
        banks,
        fingerprint_paths,
        transform_hash,
        starts,
        holdout_groups_inside=None,
    )
    predictions = dynamic_validation_moments(
        provisional,
        ModelParameters(),
        replications=100,
        parameter_overrides={
            "policy_rate": validation_policy,
            "reserve_remuneration_rate": validation_policy,
        },
    )
    holdout_predictions = {name: predictions[name] for name in bank_variables}
    holdout_predictions["business_loan_terms"] = predictions["loan_rate"]
    holdout = holdout_gate(holdout_predictions, intervals)
    bundle = provisional.model_copy(
        update={
            "holdout_groups_inside": holdout["groups_inside"],
            "holdout_outside_two_se": tuple(holdout["outside_two_se"]),
        }
    )
    write_calibration_report(best, all_starts, args.report)
    report_path = Path(args.report)
    report_payload = json.loads(report_path.read_text())
    report_payload["holdout"] = {
        **holdout,
        "predictions": holdout_predictions,
        "intervals": intervals,
    }
    report_payload["acceptance_status"] = (
        "passed" if holdout["passed"] else "failed_holdout_gate"
    )
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n")
    candidate_path = report_path.with_name("calibration_candidate.json")
    candidate_path.write_text(bundle.model_dump_json(indent=2) + "\n")
    assert_calibration_gate(bundle)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(bundle.model_dump_json(indent=2) + "\n")
    print(
        json.dumps(
            {"bundle": str(output), "normalized_rmse": best.normalized_rmse}, indent=2
        )
    )


if __name__ == "__main__":
    main()
