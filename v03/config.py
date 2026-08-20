from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RateRegime(str, Enum):
    ADMINISTERED = "administered"
    MARKET = "market"


class BehaviorMode(str, Enum):
    RULE = "rule"
    LLM = "llm"


class SeedBundle(StrictModel):
    environment: int = Field(ge=0)
    matching: int = Field(ge=0)
    shocks: int = Field(ge=0)
    behavior: int = Field(ge=0)

    @model_validator(mode="after")
    def independent(self):
        if len(set(self.model_dump().values())) != 4:
            raise ValueError("seed streams must be independent")
        return self


class ShockSpec(StrictModel):
    shock_id: str
    shock_type: Literal["demand", "productivity", "inflation_expectation"]
    start_period: int = Field(ge=1)
    duration: int = Field(ge=1)
    magnitude: float = Field(gt=-1)


class ModelParameters(StrictModel):
    n_firms: int = Field(default=30, ge=1)
    n_banks: int = Field(default=5, ge=1)
    horizon: int = Field(default=24, ge=1)
    deposit_concentration: Literal["low", "empirical", "high"] = "empirical"

    initial_firm_deposits: float = Field(default=20.0, gt=0)
    initial_firm_capital: float = Field(default=20.0, ge=0)
    initial_household_deposits: float = Field(default=100.0, ge=0)
    initial_bank_deposits: float = Field(default=100.0, gt=0)
    initial_bank_reserves: float = Field(default=25.0, ge=0)
    initial_bank_equity: float = Field(default=12.0, gt=0)

    wage: float = Field(default=1.0, gt=0)
    goods_price: float = Field(default=1.0, gt=0)
    production_alpha: float = Field(default=0.35, gt=0, lt=1)
    capital_depreciation: float = Field(default=0.025, ge=0, lt=1)
    investment_share: float = Field(default=0.35, ge=0, le=1)
    baseline_labor_demand: float = Field(default=4.0, ge=0)
    marginal_propensity_consume_income: float = Field(default=0.80, ge=0, le=1)
    marginal_propensity_consume_wealth: float = Field(default=0.03, ge=0, le=1)

    base_credit_demand: float = Field(default=12.0, ge=0)
    demand_return_sensitivity: float = Field(default=25.0, ge=0)
    expected_project_return: float = Field(default=0.10, ge=0)
    loan_maturity: int = Field(default=8, ge=1)
    periods_per_year: int = Field(default=4, ge=1)
    max_lender_share: float = Field(default=0.60, gt=0, le=1)
    borrower_leverage_limit: float = Field(default=3.0, gt=0)

    # The empirical opening loan stock is a revolving incumbent portfolio.
    # These transition parameters are quarterly except for the quoted book rate.
    legacy_loan_growth_rate: float = Field(default=0.011, gt=-1, lt=1)
    legacy_ci_loan_growth_rate: float = Field(default=0.005, gt=-1, lt=1)
    legacy_book_rate: float = Field(default=0.075, ge=0, le=1)
    bank_income_retention_rate: float = Field(default=0.15, ge=0, le=1)

    policy_rate: float = Field(default=0.04, ge=0, le=1)
    required_real_return: float = Field(default=0.015, ge=0, le=1)
    administered_spread: float = Field(default=0.025, ge=0, le=1)
    administered_pass_through: float = Field(default=0.25, ge=0, le=1)
    market_intercept: float = Field(default=0.035, ge=-0.25, le=1)
    risk_price: float = Field(default=0.020, ge=0)
    liquidity_price: float = Field(default=0.015, ge=0)
    liquidity_target_ratio: float = Field(default=0.08, ge=0, lt=1)
    liquidity_adjustment_speed: float = Field(default=0.13, ge=0, le=1)
    loan_deposit_target: float = Field(default=0.80, gt=0)
    deposit_reallocation_speed: float = Field(default=0.25, ge=0, le=1)
    deposit_funding_price: float = Field(default=0.03, ge=0)
    capital_price: float = Field(default=0.010, ge=0)
    inflation_pass_through: float = Field(default=1.0, ge=0, le=2)
    quote_dispersion: float = Field(default=0.002, ge=0)

    reserve_requirement: float = Field(default=0.0, ge=0, lt=1)
    reserve_remuneration_rate: float = Field(default=0.04, ge=0, le=1)
    capital_requirement: float = Field(default=0.08, gt=0, lt=1)
    risk_weight: float = Field(default=1.0, gt=0)
    emergency_facility: Literal["unavailable", "limited", "penalty"] = "penalty"
    emergency_limit_equity: float = Field(default=1.0, ge=0)
    emergency_penalty_spread: float = Field(default=0.02, ge=0)
    interbank_maturity: int = Field(default=1, ge=1)
    resolution_delay: int = Field(default=1, ge=1)
    collateral_recovery_rate: float = Field(default=0.25, ge=0, le=1)
    deposit_recovery_rate: float = Field(default=1.0, ge=0, le=1)
    default_equity_threshold: float = 0.0

    @model_validator(mode="after")
    def normalized_prices(self):
        if abs(self.wage - 1.0) > 1e-12 or abs(self.goods_price - 1.0) > 1e-12:
            raise ValueError("v0.3 normalizes wage and goods price to one")
        return self


class MechanismSwitches(StrictModel):
    borrower_risk_pricing: bool = True
    liquidity_pricing: bool = True
    capital_pricing: bool = True
    inflation_pass_through: bool = True
    interbank_market: bool = True
    emergency_facility: bool = True
    bank_competition: bool = True
    credit_to_production: bool = True


class ExperimentSpec(StrictModel):
    specification_id: str = "v0.3"
    calibration_id: str
    parameter_set_id: str
    scenario_id: str
    rate_regimes: tuple[RateRegime, ...] = (
        RateRegime.ADMINISTERED,
        RateRegime.MARKET,
    )
    behavior_mode: BehaviorMode = BehaviorMode.RULE
    parameters: ModelParameters = ModelParameters()
    mechanisms: MechanismSwitches = MechanismSwitches()
    shocks: tuple[ShockSpec, ...] = ()
    replications: int = Field(default=1, ge=1)
    seed_namespace: str
    required_outcomes: tuple[str, ...] = ()
    failure_policy: Literal["fail_fast", "record_and_continue"] = "fail_fast"
    frozen: bool = False

    @model_validator(mode="after")
    def valid_specification(self):
        if self.specification_id != "v0.3":
            raise ValueError("v0.3 runner accepts specification_id='v0.3' only")
        if len(set(self.rate_regimes)) != len(self.rate_regimes):
            raise ValueError("rate_regimes contains duplicates")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class CalibrationBundle(StrictModel):
    calibration_id: str
    specification_id: str = "v0.3"
    sample_start: str = "2022Q1"
    sample_end: str = "2024Q4"
    holdout_start: str = "2025Q1"
    holdout_end: str = "2025Q4"
    target_moments: dict[str, float]
    fitted_parameters: dict[str, float]
    sampling_distributions: dict[str, list[float]] = {}
    source_data_fingerprint: str
    transformation_fingerprint: str
    optimizer_starts: tuple[int, ...] = ()
    normalized_rmse: float | None = None
    holdout_groups_inside: int | None = None
    holdout_outside_two_se: tuple[str, ...] = ()

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read v0.3 specifications") from exc
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    return ExperimentSpec.model_validate(_read_yaml(Path(path)))


def load_calibration_bundle(path: str | Path) -> CalibrationBundle:
    return CalibrationBundle.model_validate_json(Path(path).read_text())
