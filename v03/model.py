from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from v03.config import (
    CalibrationBundle,
    ExperimentSpec,
    RateRegime,
    SeedBundle,
)
from v03.pricing import BankState, BorrowerState, price_loan
from v03.provenance import environment_record, git_commit, tree_fingerprint, utc_now
from v03.schema import LedgerV03, canonical_parameters


@dataclass
class Firm:
    firm_id: str
    deposit_bank_id: str
    deposits: float
    capital: float
    productivity: float
    debt: float = 0.0
    legacy_debt: float = 0.0
    working_capital: float = 0.0
    inventory: float = 0.0
    output: float = 0.0
    investment: float = 0.0
    labor: float = 0.0
    wages: float = 0.0
    sales: float = 0.0
    requested_credit: float = 0.0
    received_credit: float = 0.0
    debt_service: float = 0.0

    @property
    def equity(self) -> float:
        return self.deposits + self.capital - self.debt


@dataclass
class Bank:
    bank_id: str
    reserves: float
    deposits: float
    equity: float
    legacy_loans: float = 0.0
    legacy_ci_share: float = 0.0
    historical_loan_growth: float = 0.0
    historical_ci_loan_growth: float = 0.0
    other_assets: float = 0.0
    other_liabilities: float = 0.0
    reserve_funding_liability: float = 0.0
    interbank_assets: float = 0.0
    interbank_liabilities: float = 0.0
    emergency_borrowing: float = 0.0
    expected_inflation: float = 0.02
    status: str = "active"
    resolution_periods: int = 0
    profit: float = 0.0
    resolution_cost: float = 0.0
    liquidity_failed: bool = False


@dataclass
class Household:
    deposit_bank_id: str
    deposits: float
    lagged_deposits: float
    current_income: float = 0.0
    deposit_accounts: dict[str, float] = field(default_factory=dict)


@dataclass
class Loan:
    loan_id: str
    application_id: str
    offer_id: str
    borrower_id: str
    bank_id: str
    principal: float
    remaining: float
    rate: float
    maturity: int
    originated_period: int
    purpose: str
    age: int = 0


@dataclass(frozen=True)
class Offer:
    offer_id: str
    application_id: str
    bank_id: str
    quantity: float
    maturity: int
    rate: float | None
    rejection_code: str | None
    components: Any


class InstitutionalCreditModel:
    """Deterministic v0.3 institutional-credit simulation.

    Prices and behavioral rules are explicit. Randomness enters only through the
    named seed streams, allowing matched treatment comparisons.
    """

    def __init__(
        self,
        spec: ExperimentSpec,
        regime: RateRegime,
        seeds: SeedBundle,
        ledger: LedgerV03,
        calibration: CalibrationBundle | None = None,
        replication: int = 0,
        shard_id: str = "single",
        project_root: str | Path | None = None,
    ):
        if regime not in spec.rate_regimes:
            raise ValueError(f"{regime} is not enabled by the experiment specification")
        self.spec = spec
        self.p = spec.parameters
        self.switches = spec.mechanisms
        self.regime = RateRegime(regime)
        self.seeds = seeds
        self.ledger = ledger
        self.calibration = calibration
        self.replication = replication
        self.shard_id = shard_id
        self.root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
        self.environment_random = random.Random(seeds.environment)
        self.matching_random = random.Random(seeds.matching)
        self.shock_random = random.Random(seeds.shocks)
        self.period = 0
        self.loans: list[Loan] = []
        self.base_money_issued = self.p.n_banks * self.p.initial_bank_reserves
        self.cumulative_resolution_cost = 0.0
        self._event_sequence = 0
        self.started_clock = time.perf_counter()

        parameter_json, parameter_fingerprint = canonical_parameters(self.p)
        self.ledger.register_parameter_set(
            spec.parameter_set_id, parameter_json, parameter_fingerprint
        )
        run_key = json.dumps(
            [
                spec.fingerprint(),
                self.regime.value,
                replication,
                spec.seed_namespace,
                seeds.model_dump(),
            ],
            sort_keys=True,
        )
        self.run_id = hashlib.sha256(run_key.encode()).hexdigest()[:24]
        env = environment_record()
        calibration_fingerprint = (
            calibration.fingerprint() if calibration else "uncalibrated"
        )
        data_fingerprint = (
            calibration.source_data_fingerprint if calibration else "unavailable"
        )
        self.ledger.insert(
            "experiment_runs",
            {
                "run_id": self.run_id,
                "specification_id": spec.specification_id,
                "calibration_id": spec.calibration_id,
                "parameter_set_id": spec.parameter_set_id,
                "scenario_id": spec.scenario_id,
                "rate_regime": self.regime.value,
                "behavior_mode": spec.behavior_mode.value,
                "replication": replication,
                "seed_namespace": spec.seed_namespace,
                "environment_seed": seeds.environment,
                "matching_seed": seeds.matching,
                "shock_seed": seeds.shocks,
                "behavior_seed": seeds.behavior,
                "config_json": spec.canonical_json(),
                "config_fingerprint": spec.fingerprint(),
                "code_fingerprint": tree_fingerprint(self.root),
                "calibration_fingerprint": calibration_fingerprint,
                "data_fingerprint": data_fingerprint,
                "package_fingerprint": env["packages_sha256"],
                "git_commit": git_commit(self.root),
                "shard_id": shard_id,
                "started_at": utc_now(),
                "completed_at": None,
                "runtime_seconds": None,
                "status": "running",
                "failure_reason": None,
            },
        )
        self.ledger.conn.commit()
        self._initialize_agents()
        self.base_money_issued = sum(bank.reserves for bank in self.banks)

    def _initialize_agents(self) -> None:
        empirical = self._empirical_bank_draws()
        if empirical is not None:
            self._initialize_empirical_agents(empirical)
            self._validate_accounting()
            return
        self.banks = [
            Bank(
                bank_id=f"bank_{i}",
                reserves=self.p.initial_bank_reserves,
                deposits=0.0,
                equity=self.p.initial_bank_equity,
            )
            for i in range(self.p.n_banks)
        ]
        weights = self._deposit_weights()
        bank_assignments = self.matching_random.choices(
            [b.bank_id for b in self.banks], weights=weights, k=self.p.n_firms
        )
        self.firms = []
        for i, bank_id in enumerate(bank_assignments):
            productivity = math.exp(self.environment_random.gauss(0.0, 0.15))
            firm = Firm(
                firm_id=f"firm_{i}",
                deposit_bank_id=bank_id,
                deposits=self.p.initial_firm_deposits,
                capital=self.p.initial_firm_capital,
                productivity=productivity,
            )
            self.firms.append(firm)
            self.bank(bank_id).deposits += firm.deposits
        self.household = Household(
            deposit_bank_id=self.banks[0].bank_id,
            deposits=self.p.initial_household_deposits,
            lagged_deposits=self.p.initial_household_deposits,
            deposit_accounts={self.banks[0].bank_id: self.p.initial_household_deposits},
        )
        self.banks[0].deposits += self.household.deposits
        for bank in self.banks:
            bank.other_assets = bank.deposits + bank.equity - bank.reserves
        self._validate_accounting()

    def _empirical_bank_draws(self) -> list[dict[str, float]] | None:
        if self.calibration is None:
            return None
        distributions = self.calibration.sampling_distributions
        required = ("assets", "deposits", "gross_loans", "liquid_assets", "equity")
        if not all(name in distributions and distributions[name] for name in required):
            return None
        length = len(distributions["deposits"])
        if any(len(distributions[name]) != length for name in required):
            raise ValueError(
                "empirical joint-distribution columns must have equal length"
            )
        indices = [
            self.environment_random.randrange(length) for _ in range(self.p.n_banks)
        ]
        median_deposits = statistics.median(
            float(distributions["deposits"][i]) for i in indices
        )
        scale = 100.0 / median_deposits
        draws = []
        for i in indices:
            draw = {name: float(distributions[name][i]) * scale for name in required}
            for name in (
                "ci_share",
                "deposit_growth",
                "loan_growth",
                "ci_loan_growth",
                "ci_chargeoff_rate",
            ):
                if name in distributions:
                    draw[name] = float(distributions[name][i])
            draws.append(draw)
        return self._apply_empirical_concentration(draws)

    def _apply_empirical_concentration(
        self, draws: list[dict[str, float]]
    ) -> list[dict[str, float]]:
        """Apply the topology concentration switch to empirical bank draws.

        The confirmatory ``empirical`` path is unchanged.  For the explicitly
        labelled low/high robustness cells, bank balance sheets are rescaled so
        that each bank's internally sampled ratios remain fixed while aggregate
        deposits remain fixed.  Low concentration assigns equal deposit shares;
        high concentration assigns half of deposits to the empirically largest
        sampled bank and equal shares to the remainder (for the main five-bank
        design).  Rate and growth variables are not rescaled.
        """
        if self.p.deposit_concentration == "empirical" or not draws:
            return draws
        total_deposits = sum(draw["deposits"] for draw in draws)
        if self.p.deposit_concentration == "low":
            weights = [1.0] * len(draws)
        else:
            largest = max(range(len(draws)), key=lambda i: draws[i]["deposits"])
            weights = [1.0] * len(draws)
            weights[largest] = float(len(draws) - 1)
        weight_total = sum(weights)
        nominal_fields = ("assets", "deposits", "gross_loans", "liquid_assets", "equity")
        transformed = []
        for draw, weight in zip(draws, weights):
            target_deposits = total_deposits * weight / weight_total
            factor = target_deposits / draw["deposits"]
            item = dict(draw)
            for field in nominal_fields:
                item[field] = draw[field] * factor
            transformed.append(item)
        return transformed

    def _initialize_empirical_agents(self, draws: list[dict[str, float]]) -> None:
        self.banks = []
        for i, draw in enumerate(draws):
            loans = draw["gross_loans"]
            other_assets = draw["assets"] - draw["liquid_assets"] - loans
            reserves = draw["liquid_assets"]
            reserve_funding = 0.0
            reserve_delta = 0.0
            if self.spec.scenario_id.startswith("h7_"):
                reserve_ratio = (
                    self.p.initial_bank_reserves / self.p.initial_bank_deposits
                )
                desired_reserves = reserve_ratio * draw["deposits"]
                reserve_delta = desired_reserves - reserves
                if reserve_delta >= 0:
                    asset_swap = min(reserve_delta, max(0.0, other_assets))
                    other_assets -= asset_swap
                    reserve_funding = reserve_delta - asset_swap
                else:
                    other_assets += -reserve_delta
                reserves = desired_reserves
            bank = Bank(
                bank_id=f"bank_{i}",
                reserves=reserves,
                deposits=draw["deposits"],
                equity=draw["equity"],
                legacy_loans=loans,
                legacy_ci_share=draw.get("ci_share", 0.0),
                historical_loan_growth=draw.get("loan_growth", 0.0),
                historical_ci_loan_growth=draw.get("ci_loan_growth", 0.0),
                other_assets=other_assets,
                other_liabilities=max(
                    0.0, draw["assets"] - draw["deposits"] - draw["equity"]
                ),
                reserve_funding_liability=reserve_funding,
            )
            self.banks.append(bank)
            if self.spec.scenario_id.startswith("h7_"):
                self._event_sequence += 1
                self.ledger.insert(
                    "authority_money_events",
                    {
                        "authority_event_id": f"{self.run_id}-authority-{self._event_sequence}",
                        "run_id": self.run_id,
                        "period": 0,
                        "bank_id": bank.bank_id,
                        "event_type": "initial_reserve_configuration",
                        "rate": reserve_ratio,
                        "amount": reserve_delta,
                        "base_money_issuance": reserve_delta,
                    },
                )
        total_deposits = sum(bank.deposits for bank in self.banks)
        household_bank = max(self.banks, key=lambda bank: bank.deposits)
        household_share = min(
            0.10 * total_deposits,
            0.25 * household_bank.deposits,
            self.p.initial_household_deposits,
        )
        self.household = Household(
            deposit_bank_id=household_bank.bank_id,
            deposits=household_share,
            lagged_deposits=household_share,
            deposit_accounts={household_bank.bank_id: household_share},
        )
        remaining_by_bank = {b.bank_id: b.deposits for b in self.banks}
        remaining_by_bank[household_bank.bank_id] -= household_share
        assignments = self._empirical_firm_assignments(remaining_by_bank)
        counts = {b.bank_id: assignments.count(b.bank_id) for b in self.banks}
        self.firms = []
        for i, bank_id in enumerate(assignments):
            deposits = remaining_by_bank[bank_id] / max(counts[bank_id], 1)
            legacy_debt = self.bank(bank_id).legacy_loans / max(counts[bank_id], 1)
            self.firms.append(
                Firm(
                    firm_id=f"firm_{i}",
                    deposit_bank_id=bank_id,
                    deposits=deposits,
                    capital=self.p.initial_firm_capital,
                    productivity=math.exp(self.environment_random.gauss(0.0, 0.15)),
                    debt=legacy_debt,
                    legacy_debt=legacy_debt,
                )
            )

    def _empirical_firm_assignments(
        self, deposits_by_bank: dict[str, float]
    ) -> list[str]:
        """Allocate firms by deposit scale while retaining every sampled bank."""
        bank_ids = [bank.bank_id for bank in self.banks]
        if self.p.n_firms < len(bank_ids):
            raise ValueError(
                "empirical initialization requires at least one firm per bank"
            )
        counts = {bank_id: 1 for bank_id in bank_ids}
        remaining = self.p.n_firms - len(bank_ids)
        total = sum(max(0.0, deposits_by_bank[bank_id]) for bank_id in bank_ids)
        quotas = {
            bank_id: (
                remaining * max(0.0, deposits_by_bank[bank_id]) / total
                if total
                else remaining / len(bank_ids)
            )
            for bank_id in bank_ids
        }
        for bank_id in bank_ids:
            counts[bank_id] += math.floor(quotas[bank_id])
        unallocated = self.p.n_firms - sum(counts.values())
        order = sorted(
            bank_ids,
            key=lambda bank_id: (-(quotas[bank_id] % 1), bank_id),
        )
        for bank_id in order[:unallocated]:
            counts[bank_id] += 1
        return [bank_id for bank_id in bank_ids for _ in range(counts[bank_id])]

    def _deposit_weights(self) -> list[float]:
        if self.p.deposit_concentration == "low":
            return [1.0] * self.p.n_banks
        if self.p.deposit_concentration == "high":
            return [4.0] + [1.0] * (self.p.n_banks - 1)
        return [float(self.p.n_banks - i) for i in range(self.p.n_banks)]

    def bank(self, bank_id: str) -> Bank:
        return next(bank for bank in self.banks if bank.bank_id == bank_id)

    def firm(self, firm_id: str) -> Firm:
        return next(firm for firm in self.firms if firm.firm_id == firm_id)

    def bank_loans(self, bank_id: str) -> float:
        bank = next(bank for bank in self.banks if bank.bank_id == bank_id)
        return bank.legacy_loans + sum(
            loan.remaining for loan in self.loans if loan.bank_id == bank_id
        )

    def _bank_equity_residual(self, bank: Bank) -> float:
        assets = (
            bank.reserves
            + bank.other_assets
            + self.bank_loans(bank.bank_id)
            + bank.interbank_assets
        )
        liabilities = (
            bank.deposits
            + bank.other_liabilities
            + bank.interbank_liabilities
            + bank.emergency_borrowing
            + bank.reserve_funding_liability
        )
        return assets - liabilities

    def _sync_bank_equity(self) -> None:
        for bank in self.banks:
            bank.equity = self._bank_equity_residual(bank)

    def _transfer(self, payer: Any, payee: Any, amount: float) -> float:
        if isinstance(payer, Household):
            return self._pay_from_household(payee, amount)
        if isinstance(payee, Household):
            amount = min(max(0.0, amount), payer.deposits)
            if amount <= 0:
                return 0.0
            bank = self.bank(payer.deposit_bank_id)
            payer.deposits -= amount
            payee.deposits += amount
            payee.deposit_accounts[bank.bank_id] = (
                payee.deposit_accounts.get(bank.bank_id, 0.0) + amount
            )
            # This is an ownership transfer between two customers of the same
            # bank, so the bank's aggregate deposit liability is unchanged.
            return amount
        amount = min(max(0.0, amount), payer.deposits)
        if amount <= 0:
            return 0.0
        payer_bank = self.bank(payer.deposit_bank_id)
        payee_bank = self.bank(payee.deposit_bank_id)
        payer.deposits -= amount
        payer_bank.deposits -= amount
        payee.deposits += amount
        payee_bank.deposits += amount
        if payer_bank is not payee_bank:
            payer_bank.reserves -= amount
            payee_bank.reserves += amount
        return amount

    def _pay_from_household(self, payee: Firm, amount: float) -> float:
        amount = min(max(0.0, amount), self.household.deposits)
        if amount <= 0:
            return 0.0
        payee_bank = self.bank(payee.deposit_bank_id)
        remaining = amount
        paid = 0.0
        # Spend local deposits first, then draw other accounts in stable order.
        account_order = [payee_bank.bank_id] + sorted(
            bank_id
            for bank_id in self.household.deposit_accounts
            if bank_id != payee_bank.bank_id
        )
        for bank_id in account_order:
            available = self.household.deposit_accounts.get(bank_id, 0.0)
            draw = min(remaining, available)
            if draw <= 0:
                continue
            source_bank = self.bank(bank_id)
            self.household.deposit_accounts[bank_id] = available - draw
            self.household.deposits -= draw
            source_bank.deposits -= draw
            payee.deposits += draw
            payee_bank.deposits += draw
            if source_bank is not payee_bank:
                source_bank.reserves -= draw
                payee_bank.reserves += draw
            remaining -= draw
            paid += draw
            if remaining <= 1e-12:
                break
        return paid

    def _shock_multiplier(self, shock_type: str) -> float:
        effect = 1.0
        for shock in self.spec.shocks:
            if (
                shock.shock_type == shock_type
                and shock.start_period
                <= self.period
                < shock.start_period + shock.duration
            ):
                effect *= 1.0 + shock.magnitude
        return effect

    def _resolve_pending_banks(self) -> float:
        cost = 0.0
        for bank in self.banks:
            if bank.status != "resolution":
                continue
            bank.resolution_periods += 1
            if bank.resolution_periods < self.p.resolution_delay:
                continue
            rwa = self.p.risk_weight * self.bank_loans(bank.bank_id)
            required = self.p.capital_requirement * rwa
            prior_equity = self._bank_equity_residual(bank)
            injection = max(0.0, required - prior_equity)
            bank.reserves += injection
            bank.equity += injection
            bank.resolution_cost += injection
            self.base_money_issued += injection
            self.cumulative_resolution_cost += injection
            self._event_sequence += 1
            self.ledger.insert(
                "bank_resolution_events",
                {
                    "resolution_event_id": f"{self.run_id}-resolution-{self._event_sequence}",
                    "run_id": self.run_id,
                    "period": self.period,
                    "bank_id": bank.bank_id,
                    "prior_equity": prior_equity,
                    "risk_weighted_assets": rwa,
                    "required_equity": required,
                    "capital_injection": injection,
                    "reserves_created": injection,
                    "base_money_issuance": injection,
                    "resolution_cost": injection,
                    "status_before": "resolution",
                    "status_after": "resolved",
                },
            )
            bank.status = "resolved"
            cost += injection
        return cost

    def _production(self) -> tuple[float, float, float]:
        aggregate_output = 0.0
        investment = 0.0
        wages = 0.0
        productivity_shock = self._shock_multiplier("productivity")
        for firm in self.firms:
            depreciation = self.p.capital_depreciation * firm.capital
            firm.capital -= depreciation
            labor_budget = self.p.baseline_labor_demand
            if self.switches.credit_to_production:
                labor_budget += firm.working_capital
            payroll = min(firm.deposits, labor_budget * self.p.wage)
            firm.wages = self._transfer(firm, self.household, payroll)
            firm.labor = firm.wages / self.p.wage
            firm.working_capital = max(0.0, firm.working_capital - firm.wages)
            capital_input = max(firm.capital, 1e-9)
            labor_input = max(firm.labor, 0.0)
            firm.output = (
                firm.productivity
                * productivity_shock
                * capital_input**self.p.production_alpha
                * labor_input ** (1.0 - self.p.production_alpha)
                if labor_input > 0
                else 0.0
            )
            firm.inventory += firm.output
            firm.sales = 0.0
            firm.investment = 0.0
            firm.requested_credit = 0.0
            firm.received_credit = 0.0
            firm.debt_service = 0.0
            aggregate_output += firm.output
            wages += firm.wages
        self.household.current_income = wages
        return aggregate_output, investment, wages

    def _credit_demand(self, firm: Firm) -> tuple[float, float, int, str]:
        expected_return = (
            self.p.expected_project_return
            * self._shock_multiplier("demand")
            * firm.productivity
        )
        expected_rate = self.p.policy_rate + self.p.administered_spread
        gap = max(0.0, expected_return - expected_rate)
        requested = (
            self.p.base_credit_demand + self.p.demand_return_sensitivity * gap
        ) * self._shock_multiplier("demand")
        leverage_capacity = max(
            0.0, self.p.borrower_leverage_limit * max(firm.equity, 0.0) - firm.debt
        )
        requested = min(requested, leverage_capacity)
        purpose = (
            "mixed"
            if 0 < self.p.investment_share < 1
            else ("investment" if self.p.investment_share else "working_capital")
        )
        return requested, expected_return, self.p.loan_maturity, purpose

    def _offer(
        self,
        bank: Bank,
        firm: Firm,
        application_id: str,
        requested: float,
        expected_return: float,
        maturity: int,
    ) -> Offer:
        loans = self.bank_loans(bank.bank_id)
        reserve_ratio = (
            bank.reserves / bank.deposits if bank.deposits > 0 else float("inf")
        )
        rwa = loans * self.p.risk_weight
        capital_ratio = bank.equity / rwa if rwa > 0 else float("inf")
        funding_rate = self.p.required_real_return
        funding_rate += self.p.deposit_funding_price * max(
            0.0, loans / max(bank.deposits, 1e-9) - self.p.loan_deposit_target
        )
        if bank.reserve_funding_liability > 0:
            funding_rate += (
                self.p.required_real_return
                * bank.reserve_funding_liability
                / max(bank.equity, 1e-9)
            )
        if bank.interbank_liabilities > 0:
            funding_rate += (
                self.p.emergency_penalty_spread
                * bank.interbank_liabilities
                / max(bank.equity, 1e-9)
            )
        components = price_loan(
            self.regime,
            BorrowerState(
                leverage=max(0.0, firm.debt / max(firm.equity, 1e-9)),
                expected_return=expected_return,
                productivity=firm.productivity,
            ),
            BankState(
                reserve_ratio, capital_ratio, bank.expected_inflation, funding_rate
            ),
            self.p,
            self.switches,
            bank_effect=self._relationship_effect(firm.firm_id, bank.bank_id),
        )
        rejection = None
        capacity = requested
        if bank.status != "active":
            rejection, capacity = "bank_not_active", 0.0
        elif bank.liquidity_failed:
            rejection, capacity = "unresolved_liquidity", 0.0
        else:
            capital_capacity = max(
                0.0,
                bank.equity / (self.p.capital_requirement * self.p.risk_weight) - loans,
            )
            # Liquidity affects the quote and is settled after final payments;
            # it is not a second static quantity constraint at application time.
            # Applying the reserve floor here would make a bank exactly at its
            # requirement unable to lend even when interbank/backstop funding is
            # available, mechanically disabling the H7 institutions.
            capacity = min(requested, capital_capacity)
            if capacity <= 1e-12:
                rejection = "regulatory_capacity"
            elif components.nominal_rate > expected_return:
                rejection, capacity = "price_above_expected_return", 0.0
        offer_id = f"{application_id}-{bank.bank_id}"
        return Offer(
            offer_id,
            application_id,
            bank.bank_id,
            capacity,
            maturity,
            components.nominal_rate if capacity > 0 else None,
            rejection,
            components,
        )

    def _relationship_effect(self, firm_id: str, bank_id: str) -> float:
        digest = hashlib.sha256(
            f"{self.seeds.matching}:{firm_id}:{bank_id}".encode()
        ).digest()
        uniform = int.from_bytes(digest[:8], "big") / (2**64 - 1)
        return (2.0 * uniform - 1.0) * self.p.quote_dispersion

    def _record_offer(self, offer: Offer, bank: Bank, period: int) -> None:
        c = offer.components
        self.ledger.insert(
            "bank_offers",
            {
                "offer_id": offer.offer_id,
                "application_id": offer.application_id,
                "run_id": self.run_id,
                "period": period,
                "bank_id": bank.bank_id,
                "approved_principal": offer.quantity,
                "maturity": offer.maturity,
                "offered_nominal_rate": offer.rate,
                "rejection_code": offer.rejection_code,
                "benchmark_component": c.benchmark,
                "fixed_spread_component": c.fixed_spread,
                "funding_component": c.funding,
                "borrower_risk_component": c.borrower_risk,
                "liquidity_component": c.liquidity,
                "capital_component": c.capital,
                "inflation_component": c.inflation,
                "bank_effect_component": c.bank_effect,
                "local_pass_through": c.pass_through,
                "accepted_principal": 0.0,
                "clearing_status": (
                    "rejected" if offer.quantity <= 0 else "not_selected"
                ),
                "bank_reserves": bank.reserves,
                "bank_equity": bank.equity,
                "bank_deposits": bank.deposits,
                "bank_customer_loans": self.bank_loans(bank.bank_id),
            },
        )

    def _originate(
        self, firm: Firm, offer: Offer, amount: float, maturity: int, purpose: str
    ) -> Loan:
        lender = self.bank(offer.bank_id)
        deposit_bank = self.bank(firm.deposit_bank_id)
        firm.deposits += amount
        firm.debt += amount
        deposit_bank.deposits += amount
        if lender is not deposit_bank:
            lender.reserves -= amount
            deposit_bank.reserves += amount
        loan_id = f"{self.run_id}-loan-{self.period}-{firm.firm_id}-{offer.bank_id}-{len(self.loans)}"
        loan = Loan(
            loan_id,
            offer.application_id,
            offer.offer_id,
            firm.firm_id,
            offer.bank_id,
            amount,
            amount,
            float(offer.rate),
            maturity,
            self.period,
            purpose,
        )
        self.loans.append(loan)
        self.ledger.insert(
            "loan_contracts",
            {
                "loan_id": loan_id,
                "run_id": self.run_id,
                "application_id": offer.application_id,
                "offer_id": offer.offer_id,
                "borrower_id": firm.firm_id,
                "bank_id": offer.bank_id,
                "principal": amount,
                "remaining_principal": amount,
                "nominal_rate": offer.rate,
                "maturity": maturity,
                "originated_period": self.period,
                "purpose": purpose,
                "status": "active",
                "terminated_period": None,
                "termination_reason": None,
            },
        )
        investment = (
            amount * self.p.investment_share
            if self.switches.credit_to_production
            else 0.0
        )
        invested = self._transfer(firm, self.household, investment)
        firm.capital += invested
        firm.investment += invested
        firm.working_capital += max(0.0, amount - invested)
        firm.received_credit += amount
        return loan

    def _credit_market(self) -> dict[str, Any]:
        requested_total = approved_total = accepted_total = 0.0
        rates: list[tuple[float, float]] = []
        for firm in self.firms:
            requested, expected_return, maturity, purpose = self._credit_demand(firm)
            firm.requested_credit = requested
            requested_total += requested
            application_id = f"{self.run_id}-app-{self.period}-{firm.firm_id}"
            self.ledger.insert(
                "credit_applications",
                {
                    "application_id": application_id,
                    "run_id": self.run_id,
                    "period": self.period,
                    "firm_id": firm.firm_id,
                    "requested_principal": requested,
                    "requested_maturity": maturity,
                    "loan_purpose": purpose,
                    "expected_return": expected_return,
                    "max_acceptable_rate": expected_return,
                    "borrower_leverage": max(0.0, firm.debt / max(firm.equity, 1e-9)),
                    "borrower_productivity": firm.productivity,
                    "approved_principal": 0.0,
                    "accepted_principal": 0.0,
                    "unfunded_principal": requested,
                    "decision_source": self.spec.behavior_mode.value,
                    "decision_status": "economic",
                    "rationale": "Rule demand from expected project return and leverage capacity.",
                },
            )
            offers = [
                self._offer(
                    bank, firm, application_id, requested, expected_return, maturity
                )
                for bank in self.banks
            ]
            for offer in offers:
                self._record_offer(offer, self.bank(offer.bank_id), self.period)
            approved = sum(offer.quantity for offer in offers)
            approved_total += approved
            remaining = requested
            accepted_by_bank: dict[str, float] = {}
            candidates = [
                offer
                for offer in offers
                if offer.quantity > 0 and offer.rate is not None
            ]
            if not self.switches.bank_competition and candidates:
                candidates = [
                    next(
                        (o for o in candidates if o.bank_id == firm.deposit_bank_id),
                        candidates[0],
                    )
                ]
            candidates.sort(
                key=lambda offer: (offer.rate, self.matching_random.random())
            )
            for offer in candidates:
                if remaining <= 1e-12:
                    break
                concentration_room = (
                    self.p.max_lender_share * requested
                    - accepted_by_bank.get(offer.bank_id, 0.0)
                )
                amount = min(remaining, offer.quantity, max(0.0, concentration_room))
                if amount <= 1e-12:
                    continue
                self._originate(firm, offer, amount, maturity, purpose)
                accepted_by_bank[offer.bank_id] = (
                    accepted_by_bank.get(offer.bank_id, 0.0) + amount
                )
                remaining -= amount
                accepted_total += amount
                rates.append((float(offer.rate), amount))
                self.ledger.conn.execute(
                    "UPDATE bank_offers SET accepted_principal=?, clearing_status='accepted' WHERE offer_id=?",
                    (amount, offer.offer_id),
                )
            self.ledger.conn.execute(
                """UPDATE credit_applications
                   SET approved_principal=?, accepted_principal=?, unfunded_principal=?
                   WHERE application_id=?""",
                (approved, requested - remaining, remaining, application_id),
            )
        weighted_rate = (
            sum(rate * amount for rate, amount in rates) / accepted_total
            if accepted_total
            else None
        )
        dispersion = (
            statistics.pstdev([rate for rate, _ in rates])
            if len(rates) > 1
            else (0.0 if rates else None)
        )
        return {
            "requested": requested_total,
            "approved": approved_total,
            "accepted": accepted_total,
            "unfunded": max(0.0, requested_total - accepted_total),
            "mean_rate": weighted_rate,
            "rate_dispersion": dispersion,
        }

    def _goods_market(self) -> tuple[float, float, float]:
        planned = min(
            self.household.deposits,
            self.p.marginal_propensity_consume_income * self.household.current_income
            + self.p.marginal_propensity_consume_wealth
            * self.household.lagged_deposits,
        ) * self._shock_multiplier("demand")
        supply = sum(f.inventory for f in self.firms) * self.p.goods_price
        actual = min(planned, supply, self.household.deposits)
        total_inventory = sum(f.inventory for f in self.firms)
        if actual > 0 and total_inventory > 0:
            for firm in self.firms:
                sale = actual * firm.inventory / total_inventory
                paid = self._transfer(self.household, firm, sale)
                units = paid / self.p.goods_price
                firm.inventory = max(0.0, firm.inventory - units)
                firm.sales += paid
        return planned, actual, max(0.0, planned - actual)

    def _service_loans(self) -> tuple[int, float]:
        defaults = 0
        write_offs = 0.0
        survivors: list[Loan] = []
        for loan in self.loans:
            firm = self.firm(loan.borrower_id)
            bank = self.bank(loan.bank_id)
            scheduled_principal = min(loan.remaining, loan.principal / loan.maturity)
            interest = loan.remaining * loan.rate / self.p.periods_per_year
            due = scheduled_principal + interest
            before = loan.remaining
            cash_paid = self._pay_bank(firm, bank, min(due, firm.deposits))
            interest_paid = min(interest, cash_paid)
            principal_paid = min(
                scheduled_principal, max(0.0, cash_paid - interest_paid)
            )
            bank.profit += interest_paid
            firm.debt = max(0.0, firm.debt - principal_paid)
            firm.debt_service += cash_paid
            loan.remaining -= principal_paid
            collateral = deposit_recovery = written = 0.0
            event_type = "payment"
            if cash_paid + 1e-9 < due:
                defaults += 1
                event_type = "default"
                deposit_recovery = principal_paid
                collateral = min(
                    loan.remaining, self.p.collateral_recovery_rate * firm.capital
                )
                firm.capital -= collateral
                bank.other_assets += collateral
                firm.debt = max(0.0, firm.debt - collateral)
                loan.remaining -= collateral
                written = max(0.0, loan.remaining)
                firm.debt = max(0.0, firm.debt - written)
                loan.remaining = 0.0
                write_offs += written
                bank.profit -= written
            loan.age += 1
            if loan.remaining > 1e-9 and loan.age < loan.maturity:
                survivors.append(loan)
                status = "active"
            else:
                status = "defaulted" if event_type == "default" else "repaid"
                self.ledger.conn.execute(
                    "UPDATE loan_contracts SET remaining_principal=0,status=?,terminated_period=?,termination_reason=? WHERE loan_id=?",
                    (status, self.period, status, loan.loan_id),
                )
            self.ledger.insert(
                "loan_events",
                {
                    "loan_event_id": f"{loan.loan_id}-event-{self.period}",
                    "run_id": self.run_id,
                    "period": self.period,
                    "loan_id": loan.loan_id,
                    "event_type": event_type,
                    "scheduled_amount": due,
                    "principal_paid": principal_paid,
                    "interest_paid": interest_paid,
                    "deposit_recovery": deposit_recovery,
                    "collateral_recovery": collateral,
                    "principal_written_off": written,
                    "remaining_principal_before": before,
                    "remaining_principal_after": loan.remaining,
                },
            )
        self.loans = survivors
        self._sync_bank_equity()
        return defaults, write_offs

    def _service_incumbent_portfolios(self) -> dict[str, float]:
        """Roll and expand the empirically initialized loan book.

        The opening stock is not an unbacked bank asset: every unit is assigned
        to an existing firm as an incumbent liability. Scheduled principal is
        rolled over, while only net expansion creates deposits. Borrowers pay
        periodic interest; the non-retained share is paid to the household as
        funding/capital income. All three flows therefore preserve double entry.
        """
        totals = {
            "net_originations": 0.0,
            "interest_paid": 0.0,
            "household_funding_income": 0.0,
        }
        for bank in self.banks:
            borrowers = [
                firm for firm in self.firms if firm.deposit_bank_id == bank.bank_id
            ]
            if not borrowers or bank.legacy_loans <= 0:
                continue
            opening = bank.legacy_loans
            opening_ci = opening * bank.legacy_ci_share
            scheduled_rollover = opening / max(self.p.loan_maturity, 1)

            interest_due = opening * self.p.legacy_book_rate / self.p.periods_per_year
            interest_paid = 0.0
            for firm in borrowers:
                share = firm.legacy_debt / opening if opening else 0.0
                paid = self._pay_bank(firm, bank, interest_due * share)
                firm.debt_service += paid
                interest_paid += paid

            retained = interest_paid * self.p.bank_income_retention_rate
            household_income = self._pay_household_from_bank(
                bank, interest_paid - retained
            )
            bank.profit += interest_paid - household_income
            self.household.current_income += household_income

            target = max(0.0, opening * (1.0 + self.p.legacy_loan_growth_rate))
            net_originations = target - opening
            if net_originations >= 0:
                for firm in borrowers:
                    share = (
                        firm.legacy_debt / opening if opening else 1.0 / len(borrowers)
                    )
                    amount = net_originations * share
                    firm.deposits += amount
                    firm.debt += amount
                    firm.legacy_debt += amount
                    bank.deposits += amount
            else:
                repayment_needed = -net_originations
                repaid = 0.0
                for firm in borrowers:
                    share = firm.legacy_debt / opening if opening else 0.0
                    amount = self._pay_bank(
                        firm, bank, min(repayment_needed * share, firm.legacy_debt)
                    )
                    firm.debt -= amount
                    firm.legacy_debt -= amount
                    repaid += amount
                net_originations = -repaid
                target = opening - repaid
            bank.legacy_loans = target

            closing_ci = min(
                target,
                max(0.0, opening_ci * (1.0 + self.p.legacy_ci_loan_growth_rate)),
            )
            bank.legacy_ci_share = closing_ci / target if target else 0.0
            self._event_sequence += 1
            self.ledger.insert(
                "incumbent_portfolio_events",
                {
                    "incumbent_event_id": f"{self.run_id}-incumbent-{self._event_sequence}",
                    "run_id": self.run_id,
                    "period": self.period,
                    "bank_id": bank.bank_id,
                    "opening_principal": opening,
                    "scheduled_rollover": scheduled_rollover,
                    "net_originations": net_originations,
                    "closing_principal": target,
                    "opening_ci_principal": opening_ci,
                    "closing_ci_principal": closing_ci,
                    "interest_paid": interest_paid,
                    "household_funding_income": household_income,
                    "retained_bank_income": retained,
                },
            )
            totals["net_originations"] += net_originations
            totals["interest_paid"] += interest_paid
            totals["household_funding_income"] += household_income
        self._sync_bank_equity()
        return totals

    def _pay_reserve_interest(self) -> float:
        """Credit remuneration on central-bank reserves as new base money."""
        total = 0.0
        for bank in self.banks:
            amount = (
                max(0.0, bank.reserves)
                * self.p.reserve_remuneration_rate
                / self.p.periods_per_year
            )
            if amount <= 0:
                continue
            bank.reserves += amount
            bank.profit += amount
            self.base_money_issued += amount
            total += amount
            self._event_sequence += 1
            self.ledger.insert(
                "authority_money_events",
                {
                    "authority_event_id": f"{self.run_id}-authority-{self._event_sequence}",
                    "run_id": self.run_id,
                    "period": self.period,
                    "bank_id": bank.bank_id,
                    "event_type": "reserve_remuneration",
                    "rate": self.p.reserve_remuneration_rate,
                    "amount": amount,
                    "base_money_issuance": amount,
                },
            )
        self._sync_bank_equity()
        return total

    def _manage_liquidity_buffers(self) -> float:
        """Partially close reserve-buffer gaps through central-bank asset swaps."""
        total = 0.0
        for bank in self.banks:
            target = self.p.liquidity_target_ratio * bank.deposits
            desired = self.p.liquidity_adjustment_speed * max(
                0.0, target - bank.reserves
            )
            amount = min(desired, max(0.0, bank.other_assets))
            if amount <= 0:
                continue
            bank.other_assets -= amount
            bank.reserves += amount
            self.base_money_issued += amount
            total += amount
            self._event_sequence += 1
            self.ledger.insert(
                "authority_money_events",
                {
                    "authority_event_id": f"{self.run_id}-authority-{self._event_sequence}",
                    "run_id": self.run_id,
                    "period": self.period,
                    "bank_id": bank.bank_id,
                    "event_type": "open_market_asset_swap",
                    "rate": 0.0,
                    "amount": amount,
                    "base_money_issuance": amount,
                },
            )
        self._sync_bank_equity()
        return total

    def _rebalance_deposit_funding(self) -> float:
        """Let high-loan banks attract household deposits from low-loan banks."""
        total = 0.0
        target_ratio = self.p.loan_deposit_target
        recipients = sorted(
            self.banks,
            key=lambda bank: self.bank_loans(bank.bank_id) / max(bank.deposits, 1e-9),
            reverse=True,
        )
        for recipient in recipients:
            loans = self.bank_loans(recipient.bank_id)
            ratio_before = loans / max(recipient.deposits, 1e-9)
            funding_gap = max(0.0, loans / target_ratio - recipient.deposits)
            need = self.p.deposit_reallocation_speed * funding_gap
            if need <= 1e-12:
                continue
            donors = sorted(
                (
                    bank
                    for bank in self.banks
                    if bank.bank_id != recipient.bank_id
                    and self.household.deposit_accounts.get(bank.bank_id, 0.0) > 0
                ),
                key=lambda bank: self.bank_loans(bank.bank_id)
                / max(bank.deposits, 1e-9),
            )
            moved = 0.0
            for donor in donors:
                available = self.household.deposit_accounts.get(donor.bank_id, 0.0)
                # Keep the donor on the low-funding side of the same target;
                # otherwise the transaction merely transfers the imbalance.
                donor_surplus = max(
                    0.0,
                    donor.deposits - self.bank_loans(donor.bank_id) / target_ratio,
                )
                amount = min(need - moved, available, donor_surplus)
                if amount <= 0:
                    continue
                self.household.deposit_accounts[donor.bank_id] -= amount
                self.household.deposit_accounts[recipient.bank_id] = (
                    self.household.deposit_accounts.get(recipient.bank_id, 0.0) + amount
                )
                donor.deposits -= amount
                donor.reserves -= amount
                recipient.deposits += amount
                recipient.reserves += amount
                moved += amount
                self._event_sequence += 1
                self.ledger.insert(
                    "deposit_funding_events",
                    {
                        "funding_event_id": f"{self.run_id}-funding-{self._event_sequence}",
                        "run_id": self.run_id,
                        "period": self.period,
                        "source_bank_id": donor.bank_id,
                        "target_bank_id": recipient.bank_id,
                        "amount": amount,
                        "target_loans_deposits_before": ratio_before,
                        "target_loans_deposits_after": loans
                        / max(recipient.deposits, 1e-9),
                    },
                )
                if moved + 1e-12 >= need:
                    break
            if moved <= 0:
                continue
            total += moved
        self._sync_bank_equity()
        return total

    def _pay_household_from_bank(self, payer_bank: Bank, amount: float) -> float:
        amount = max(0.0, amount)
        if amount <= 0:
            return 0.0
        self.household.deposits += amount
        self.household.deposit_accounts[payer_bank.bank_id] = (
            self.household.deposit_accounts.get(payer_bank.bank_id, 0.0) + amount
        )
        payer_bank.deposits += amount
        return amount

    def _pay_bank(self, firm: Firm, lender: Bank, amount: float) -> float:
        amount = min(max(0.0, amount), firm.deposits)
        deposit_bank = self.bank(firm.deposit_bank_id)
        firm.deposits -= amount
        deposit_bank.deposits -= amount
        if deposit_bank is not lender:
            deposit_bank.reserves -= amount
            lender.reserves += amount
        return amount

    def _clear_liquidity(self) -> float:
        for bank in self.banks:
            bank.liquidity_failed = False
        deficits = {
            b.bank_id: max(0.0, self.p.reserve_requirement * b.deposits - b.reserves)
            for b in self.banks
        }
        if self.switches.interbank_market:
            lenders = [
                b
                for b in self.banks
                if b.reserves > self.p.reserve_requirement * b.deposits
            ]
            for borrower in self.banks:
                need = deficits[borrower.bank_id]
                for lender in lenders:
                    if need <= 1e-12 or lender is borrower:
                        break
                    surplus = max(
                        0.0,
                        lender.reserves - self.p.reserve_requirement * lender.deposits,
                    )
                    amount = min(need, surplus)
                    if amount <= 0:
                        continue
                    lender.reserves -= amount
                    lender.interbank_assets += amount
                    borrower.reserves += amount
                    borrower.interbank_liabilities += amount
                    need -= amount
                    self._record_liquidity(
                        "interbank",
                        lender.bank_id,
                        borrower.bank_id,
                        amount,
                        self.p.required_real_return,
                    )
                deficits[borrower.bank_id] = need
        unresolved = 0.0
        for bank in self.banks:
            need = max(0.0, self.p.reserve_requirement * bank.deposits - bank.reserves)
            facility_allowed = (
                self.switches.emergency_facility
                and self.p.emergency_facility != "unavailable"
            )
            if need > 0 and facility_allowed:
                limit = max(
                    0.0,
                    self.p.emergency_limit_equity * max(0.0, bank.equity)
                    - bank.emergency_borrowing,
                )
                amount = (
                    min(need, limit) if self.p.emergency_facility == "limited" else need
                )
                bank.reserves += amount
                bank.emergency_borrowing += amount
                self.base_money_issued += amount
                need -= amount
                self._record_liquidity(
                    "emergency",
                    "authority",
                    bank.bank_id,
                    amount,
                    self.p.policy_rate + self.p.emergency_penalty_spread,
                )
            bank.liquidity_failed = need > 1e-9
            unresolved += max(0.0, need)
        return unresolved

    def _record_liquidity(
        self, facility_type: str, lender: str, borrower: str, amount: float, rate: float
    ) -> None:
        self._event_sequence += 1
        self.ledger.insert(
            "liquidity_events",
            {
                "event_id": f"{self.run_id}-liquidity-{self._event_sequence}",
                "run_id": self.run_id,
                "period": self.period,
                "facility_type": facility_type,
                "lender_id": lender,
                "borrower_id": borrower,
                "principal": amount,
                "rate": rate,
                "status": "active",
            },
        )

    def _mark_insolvent(self) -> None:
        self._sync_bank_equity()
        for bank in self.banks:
            if bank.equity < 0 and bank.status == "active":
                bank.status = "resolution"
                bank.resolution_periods = 0
            elif bank.status == "resolved":
                bank.status = "active"

    def step(self) -> None:
        self.period += 1
        for bank in self.banks:
            bank.profit = 0.0
            bank.resolution_cost = 0.0
        resolution_cost = self._resolve_pending_banks()
        aggregate_output, _, _ = self._production()
        incumbent = self._service_incumbent_portfolios()
        credit = self._credit_market()
        planned, actual, unmet = self._goods_market()
        defaults, write_offs = self._service_loans()
        deposit_reallocation = self._rebalance_deposit_funding()
        unresolved = self._clear_liquidity()
        reserve_asset_swaps = self._manage_liquidity_buffers()
        # Reserve remuneration is an end-of-period central-bank payment on the
        # settled reserve balance. Paying it before settlement would let the
        # liquidity floor mechanically absorb the income in the same period.
        reserve_interest = self._pay_reserve_interest()
        self._mark_insolvent()
        self._record_period(
            aggregate_output,
            credit,
            planned,
            actual,
            unmet,
            defaults,
            write_offs,
            unresolved,
            resolution_cost,
            incumbent,
            reserve_interest,
            reserve_asset_swaps,
            deposit_reallocation,
        )
        self._validate_accounting()
        self.ledger.conn.commit()

    def _record_period(
        self,
        output: float,
        credit: dict[str, Any],
        planned: float,
        actual: float,
        unmet: float,
        defaults: int,
        write_offs: float,
        unresolved: float,
        resolution_cost: float,
        incumbent: dict[str, float],
        reserve_interest: float,
        reserve_asset_swaps: float,
        deposit_reallocation: float,
    ) -> None:
        rates = credit["mean_rate"]
        macro = {
            "run_id": self.run_id,
            "period": self.period,
            "base_money": sum(bank.reserves for bank in self.banks),
            "deposit_money": sum(firm.deposits for firm in self.firms)
            + self.household.deposits,
            "new_credit": credit["accepted"],
            "incumbent_net_originations": incumbent["net_originations"],
            "incumbent_interest_paid": incumbent["interest_paid"],
            "household_funding_income": incumbent["household_funding_income"],
            "reserve_interest_income": reserve_interest,
            "reserve_asset_swaps": reserve_asset_swaps,
            "deposit_funding_reallocation": deposit_reallocation,
            "outstanding_credit": sum(
                self.bank_loans(bank.bank_id) for bank in self.banks
            ),
            "aggregate_output": output,
            "aggregate_investment": sum(firm.investment for firm in self.firms),
            "planned_consumption": planned,
            "actual_consumption": actual,
            "inventory": sum(firm.inventory for firm in self.firms),
            "unmet_consumption": unmet,
            "requested_credit": credit["requested"],
            "approved_credit": credit["approved"],
            "accepted_credit": credit["accepted"],
            "unfunded_credit": credit["unfunded"],
            "unfunded_demand_share": (
                credit["unfunded"] / credit["requested"] if credit["requested"] else 0.0
            ),
            "mean_new_loan_rate": rates,
            "rate_dispersion": credit["rate_dispersion"],
            "defaults": defaults,
            "write_offs": write_offs,
            "unresolved_liquidity_shortfall": unresolved,
            "active_banks": sum(b.status == "active" for b in self.banks),
            "failed_banks": sum(b.status != "active" for b in self.banks),
            "resolution_cost": resolution_cost,
            "realized_inflation": 0.0,
        }
        self.ledger.insert("period_macro", macro)
        total_credit = sum(self.bank_loans(b.bank_id) for b in self.banks)
        for firm in self.firms:
            self.ledger.insert(
                "firm_states",
                {
                    "run_id": self.run_id,
                    "period": self.period,
                    "firm_id": firm.firm_id,
                    "deposit_bank_id": firm.deposit_bank_id,
                    "deposits": firm.deposits,
                    "debt": firm.debt,
                    "incumbent_debt": firm.legacy_debt,
                    "experimental_debt": firm.debt - firm.legacy_debt,
                    "real_capital": firm.capital,
                    "equity": firm.equity,
                    "productivity": firm.productivity,
                    "investment": firm.investment,
                    "labor": firm.labor,
                    "wages": firm.wages,
                    "output": firm.output,
                    "inventory": firm.inventory,
                    "sales": firm.sales,
                    "requested_credit": firm.requested_credit,
                    "received_credit": firm.received_credit,
                    "debt_service_burden": firm.debt_service / max(firm.sales, 1e-9),
                },
            )
        self._sync_bank_equity()
        for bank in self.banks:
            loans = self.bank_loans(bank.bank_id)
            rwa = self.p.risk_weight * loans
            self.ledger.insert(
                "bank_states",
                {
                    "run_id": self.run_id,
                    "period": self.period,
                    "bank_id": bank.bank_id,
                    "reserves": bank.reserves,
                    "deposits": bank.deposits,
                    "customer_loans": loans,
                    "incumbent_loans": bank.legacy_loans,
                    "incumbent_ci_share": bank.legacy_ci_share,
                    "interbank_assets": bank.interbank_assets,
                    "interbank_liabilities": bank.interbank_liabilities,
                    "emergency_borrowing": bank.emergency_borrowing,
                    "reserve_funding_liability": bank.reserve_funding_liability,
                    "equity": bank.equity,
                    "risk_weighted_assets": rwa,
                    "capital_ratio": bank.equity / rwa if rwa else None,
                    "liquidity_ratio": (
                        bank.reserves / bank.deposits if bank.deposits else None
                    ),
                    "profit": bank.profit,
                    "market_share": loans / total_credit if total_credit else 0.0,
                    "status": bank.status,
                    "resolution_cost": bank.resolution_cost,
                    "liquidity_failed": int(bank.liquidity_failed),
                },
            )
        self.household.lagged_deposits = self.household.deposits

    def _validate_accounting(self) -> None:
        deposits_assets = (
            sum(firm.deposits for firm in self.firms) + self.household.deposits
        )
        deposits_liabilities = sum(bank.deposits for bank in self.banks)
        if not math.isclose(deposits_assets, deposits_liabilities, abs_tol=1e-7):
            raise AssertionError(
                f"deposit mismatch: {deposits_assets} != {deposits_liabilities}"
            )
        if not math.isclose(
            self.household.deposits,
            sum(self.household.deposit_accounts.values()),
            abs_tol=1e-7,
        ):
            raise AssertionError("household deposit-account mismatch")
        borrower_debt = sum(firm.debt for firm in self.firms)
        loans = sum(self.bank_loans(bank.bank_id) for bank in self.banks)
        if not math.isclose(borrower_debt, loans, abs_tol=1e-7):
            raise AssertionError(f"credit mismatch: {borrower_debt} != {loans}")
        for value in [deposits_assets, loans, *(firm.capital for firm in self.firms)]:
            if not math.isfinite(value) or value < -1e-8:
                raise AssertionError(f"inadmissible accounting value: {value}")

    def run(self) -> str:
        try:
            while self.period < self.p.horizon:
                self.step()
            runtime = time.perf_counter() - self.started_clock
            self.ledger.update_run(
                self.run_id,
                completed_at=utc_now(),
                runtime_seconds=runtime,
                status="completed",
                failure_reason=None,
            )
            return "completed"
        except Exception as exc:
            runtime = time.perf_counter() - self.started_clock
            self.ledger.update_run(
                self.run_id,
                completed_at=utc_now(),
                runtime_seconds=runtime,
                status="failed",
                failure_reason=f"{type(exc).__name__}: {exc}",
            )
            if self.spec.failure_policy == "fail_fast":
                raise
            return "failed"
