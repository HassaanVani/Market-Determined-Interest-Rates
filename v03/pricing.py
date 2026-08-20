from __future__ import annotations

from dataclasses import dataclass

from v03.config import MechanismSwitches, ModelParameters, RateRegime


@dataclass(frozen=True)
class BorrowerState:
    leverage: float
    expected_return: float
    productivity: float


@dataclass(frozen=True)
class BankState:
    reserve_ratio: float
    capital_ratio: float
    expected_inflation: float
    funding_rate: float


@dataclass(frozen=True)
class PricingDecomposition:
    benchmark: float
    fixed_spread: float
    funding: float
    borrower_risk: float
    liquidity: float
    capital: float
    inflation: float
    bank_effect: float
    pass_through: float

    @property
    def nominal_rate(self) -> float:
        local = (
            self.funding
            + self.borrower_risk
            + self.liquidity
            + self.capital
            + self.inflation
        )
        return max(
            0.0,
            self.benchmark
            + self.fixed_spread
            + self.pass_through * local
            + self.bank_effect,
        )


def price_loan(
    regime: RateRegime,
    borrower: BorrowerState,
    bank: BankState,
    params: ModelParameters,
    switches: MechanismSwitches,
    bank_effect: float = 0.0,
) -> PricingDecomposition:
    risk = (
        params.risk_price * max(0.0, borrower.leverage)
        if switches.borrower_risk_pricing
        else 0.0
    )
    liquidity = (
        params.liquidity_price
        * max(0.0, params.liquidity_target_ratio - bank.reserve_ratio)
        if switches.liquidity_pricing
        else 0.0
    )
    capital = (
        params.capital_price * max(0.0, params.capital_requirement - bank.capital_ratio)
        if switches.capital_pricing
        else 0.0
    )
    inflation = (
        params.inflation_pass_through * max(0.0, bank.expected_inflation)
        if switches.inflation_pass_through
        else 0.0
    )
    funding = max(0.0, bank.funding_rate - params.required_real_return)
    if regime == RateRegime.ADMINISTERED:
        benchmark = params.policy_rate
        fixed_spread = params.administered_spread
        pass_through = params.administered_pass_through
    else:
        benchmark = params.required_real_return
        fixed_spread = params.market_intercept
        pass_through = 1.0
    return PricingDecomposition(
        benchmark=benchmark,
        fixed_spread=fixed_spread,
        funding=funding,
        borrower_risk=risk,
        liquidity=liquidity,
        capital=capital,
        inflation=inflation,
        bank_effect=bank_effect,
        pass_through=pass_through,
    )


def align_market_intercept(
    administered_mean: float,
    market_without_intercept_mean: float,
    lower: float = -0.25,
    upper: float = 1.0,
) -> float:
    """Choose the market intercept that equalizes baseline mean quotes."""
    return min(upper, max(lower, administered_mean - market_without_intercept_mean))
