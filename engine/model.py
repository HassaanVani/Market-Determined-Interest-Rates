import mesa
import random
from engine.schedule import AsyncMacroScheduler
from engine.liquidity import LiquidityManager
from engine.shocks import ShockEngine
from models.firm import FirmAgent
from models.bank import BankAgent
from models.household import HouseholdAgent
from database.ledger import Ledger
from engine.experiment import (
    BehaviorMode,
    ExperimentConfig,
    RateRegime,
    SeedBundle,
    new_run_id,
)
from openai import AsyncOpenAI


class MacroModel(mesa.Model):
    def __init__(
        self,
        n_firms=5,
        n_banks=2,
        db_path=":memory:",
        control_mode=False,
        llm_model="deepseek-r1:8b",
        agent_sentiment="neutral",
        llm_temperature=0.7,
        llm_timeout_seconds=60.0,
        llm_max_retries=2,
        llm_max_tokens=256,
        llm_reasoning_effort="none",
        prompt_version="0.1",
        reserve_requirement=0.10,
        capital_requirement=0.08,
        leverage_limit=1.5,
        rate_regime=None,
        behavior_mode=None,
        policy_rate=0.03,
        experiment_horizon=0,
        seeds=None,
        initial_reserves_per_bank=1000.0,
        initial_bank_equity=100.0,
        lender_of_last_resort="unavailable",
        emergency_penalty_spread=0.02,
        emergency_borrowing_limit_ratio=1.0,
        shocks=None,
        heterogeneity_scale=0.0,
        scenario_name="baseline",
        source_fingerprint="unrecorded",
    ):
        super().__init__()
        if n_banks < 1:
            raise ValueError("MacroModel requires at least one bank")
        self.num_firms = n_firms
        self.num_banks = n_banks
        self.control_mode = control_mode
        self.llm_model = llm_model
        self.agent_sentiment = agent_sentiment
        self.llm_temperature = llm_temperature
        self.llm_timeout_seconds = llm_timeout_seconds
        self.llm_max_retries = llm_max_retries
        self.llm_max_tokens = llm_max_tokens
        self.llm_reasoning_effort = llm_reasoning_effort
        self.prompt_version = prompt_version
        self.reserve_requirement = reserve_requirement
        self.capital_requirement = capital_requirement
        self.leverage_limit = leverage_limit
        self.policy_rate = policy_rate
        self.initial_reserves_per_bank = initial_reserves_per_bank
        self.initial_bank_equity = initial_bank_equity
        self.lender_of_last_resort = lender_of_last_resort
        self.emergency_penalty_spread = emergency_penalty_spread
        self.emergency_borrowing_limit_ratio = emergency_borrowing_limit_ratio
        self.heterogeneity_scale = heterogeneity_scale
        shock_list = list(shocks or [])

        # `control_mode` remains as a compatibility alias for the original two
        # bundled treatments. New experiments must set the institutional rate
        # regime and behavioral specification independently.
        if rate_regime is None:
            rate_regime = RateRegime.ADMINISTERED if control_mode else RateRegime.MARKET
        self.rate_regime = RateRegime(rate_regime)

        if behavior_mode is None:
            behavior_mode = BehaviorMode.RULE if control_mode else BehaviorMode.LLM
        self.behavior_mode = BehaviorMode(behavior_mode)
        self.control_mode = self.behavior_mode == BehaviorMode.RULE

        self.ledger = Ledger(db_path)
        self.schedule = AsyncMacroScheduler(self)

        seed_bundle = seeds or SeedBundle()
        self.experiment_config = ExperimentConfig(
            scenario_name=scenario_name,
            source_fingerprint=source_fingerprint,
            rate_regime=self.rate_regime,
            behavior_mode=self.behavior_mode,
            n_firms=n_firms,
            n_banks=n_banks,
            horizon=experiment_horizon,
            llm_model=llm_model,
            llm_temperature=llm_temperature,
            llm_timeout_seconds=llm_timeout_seconds,
            llm_max_retries=llm_max_retries,
            llm_max_tokens=llm_max_tokens,
            llm_reasoning_effort=llm_reasoning_effort,
            prompt_version=prompt_version,
            agent_sentiment=agent_sentiment,
            reserve_requirement=reserve_requirement,
            capital_requirement=capital_requirement,
            leverage_limit=leverage_limit,
            policy_rate=policy_rate,
            initial_reserves_per_bank=initial_reserves_per_bank,
            initial_bank_equity=initial_bank_equity,
            lender_of_last_resort=lender_of_last_resort,
            emergency_penalty_spread=emergency_penalty_spread,
            emergency_borrowing_limit_ratio=emergency_borrowing_limit_ratio,
            heterogeneity_scale=heterogeneity_scale,
            shocks=tuple(shock.to_dict() for shock in shock_list),
            seeds=seed_bundle,
        )
        self.run_id = new_run_id(self.experiment_config)
        self.ledger.register_run(self.run_id, self.experiment_config)
        self.matching_random = random.Random(seed_bundle.matching)
        self.environment_random = random.Random(seed_bundle.environment)

        # Loan registry: tracks all outstanding loans
        self.active_loans = []
        self.active_interbank_loans = []
        self.active_emergency_loans = []

        # The client is created inside the scheduler's active event loop.
        self.client = None

        # Macroeconomic variables & Expectation trackers
        self.nominal_rate = 0.0
        self.real_interest_rate = 0.0
        self.realized_inflation = 0.0
        self.three_step_yield_trend = 0.0
        self.exp_inflation = 0.0
        self.exp_nominal_rate = 0.05
        self.write_offs_in_step = 0.0
        self.defaults_in_step = 0
        self.new_credit_in_step = 0.0
        self.market_nominal_rate = None
        self.aggregate_output = 0.0
        self.total_consumption = 0.0
        self.llm_failure_count = 0
        self.base_money_issued = float(n_banks * initial_reserves_per_bank)
        self.liquidity = LiquidityManager(self)
        self.shocks = ShockEngine(self, shock_list)
        self.current_shock_effects = self.shocks.effects(0)
        for shock in shock_list:
            self.ledger.record_shock(self.run_id, shock)

        # Create Households (starts with 100.0 deposits)
        self.household = HouseholdAgent("household", self)
        self.household.current_balance = 100.0
        self.household.update_equity()

        # Initialize Banks
        for i in range(self.num_banks):
            b = BankAgent(f"bank_{i}", self, self.client)
            self.schedule.add(b)

        # Every non-bank agent has a specific deposit bank. Initial deposit
        # liabilities are assigned to those banks rather than divided equally.
        self.household.deposit_bank_id = self.schedule.banks[0].unique_id
        self.schedule.banks[0].current_debt += self.household.current_balance

        # Initialize Firms with heterogeneous risk profiles (round-robin)
        profiles = ["risk-averse", "neutral", "risk-seeking"]
        for i in range(self.num_firms):
            risk_profile = profiles[i % len(profiles)]
            f = FirmAgent(f"firm_{i}", self, self.client, risk_profile=risk_profile)
            if heterogeneity_scale > 0:
                f.current_balance *= 1.0 + self.environment_random.uniform(
                    -heterogeneity_scale, heterogeneity_scale
                )
                f.productivity = 1.0 + self.environment_random.uniform(
                    -heterogeneity_scale, heterogeneity_scale
                )
                f.update_equity()
            deposit_bank = self.schedule.banks[i % self.num_banks]
            f.deposit_bank_id = deposit_bank.unique_id
            deposit_bank.current_debt += f.current_balance
            self.schedule.add(f)
            self.ledger.update_balance_sheet(
                f.unique_id, "Firm", f.current_balance, f.current_debt, f.equity
            )

        self.ledger.update_balance_sheet(
            self.household.unique_id,
            "Household",
            self.household.current_balance,
            self.household.current_debt,
            self.household.equity,
        )
        for bank in self.schedule.banks:
            bank.other_assets = max(
                0.0,
                bank.current_debt + initial_bank_equity - bank.current_balance,
            )
            bank.equity = bank.current_balance + bank.other_assets - bank.current_debt
            self.ledger.update_balance_sheet(
                bank.unique_id,
                "Bank",
                bank.current_balance + bank.other_assets,
                bank.current_debt,
                bank.equity,
            )

        self.ledger.validate_balance_sheets()
        self.validate_monetary_system()
        self.record_current_period()

    def step(self):
        try:
            self.schedule.step()
            self.record_current_period()
        except Exception as exc:
            self.ledger.update_run_status(self.run_id, "failed", str(exc))
            raise

    def collect_macro_snapshot(self):
        """Return consistently named monetary and credit aggregates.

        The legacy model has no currency held outside banks, so broad money equals
        deposit money. A nullable new-loan rate distinguishes no market observation
        from a genuine zero-percent contract.
        """
        base_money = sum(bank.current_balance for bank in self.schedule.banks)
        deposit_money = (
            sum(firm.current_balance for firm in self.schedule.firms)
            + self.household.current_balance
        )
        outstanding_credit = sum(
            loan["remaining_principal"] for loan in self.active_loans
        )
        if outstanding_credit > 0:
            outstanding_book_rate = (
                sum(
                    loan["remaining_principal"] * loan["interest_rate"]
                    for loan in self.active_loans
                )
                / outstanding_credit
            )
        else:
            outstanding_book_rate = None

        return {
            "base_money": base_money,
            "deposit_money": deposit_money,
            "broad_money": deposit_money,
            "new_credit": self.new_credit_in_step,
            "outstanding_credit": outstanding_credit,
            "market_nominal_rate": self.market_nominal_rate,
            "outstanding_book_rate": outstanding_book_rate,
            "realized_inflation": self.realized_inflation,
            "defaults": self.defaults_in_step,
            "write_offs": self.write_offs_in_step,
            "interbank_rate": self.liquidity.interbank_rate,
            "interbank_volume": self.liquidity.interbank_volume,
            "emergency_borrowing": self.liquidity.emergency_volume,
            "liquidity_shortfall": self.liquidity.unresolved_shortfall,
            "aggregate_output": self.aggregate_output,
            "total_consumption": self.total_consumption,
        }

    def record_current_period(self):
        self.ledger.record_period_macro(
            self.run_id, self.schedule.steps, self.collect_macro_snapshot()
        )
        self.record_agent_states()

    def create_llm_client(self):
        return AsyncOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",  # required by the SDK but ignored by Ollama
        )

    def record_agent_states(self):
        period = self.schedule.steps
        for firm in self.schedule.firms:
            self.ledger.record_agent_state(
                (
                    self.run_id,
                    period,
                    firm.unique_id,
                    "Firm",
                    firm.deposit_bank_id,
                    firm.current_balance,
                    firm.current_debt,
                    firm.current_balance,
                    firm.current_debt,
                    firm.equity,
                    firm.exp_inflation,
                    firm.exp_nominal_rate,
                    getattr(firm, "output", 0.0),
                    firm.working_capital_budget,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
            )

        household = self.household
        self.ledger.record_agent_state(
            (
                self.run_id,
                period,
                household.unique_id,
                "Household",
                household.deposit_bank_id,
                household.current_balance,
                household.current_debt,
                household.current_balance,
                household.current_debt,
                household.equity,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )

        for bank in self.schedule.banks:
            customer_loans = sum(
                loan["remaining_principal"]
                for loan in self.active_loans
                if loan["bank_id"] == bank.unique_id
            )
            assets = (
                bank.current_balance
                + bank.other_assets
                + customer_loans
                + bank.interbank_assets
            )
            liabilities = (
                bank.current_debt
                + bank.interbank_liabilities
                + bank.emergency_borrowing
            )
            self.ledger.record_agent_state(
                (
                    self.run_id,
                    period,
                    bank.unique_id,
                    "Bank",
                    None,
                    0.0,
                    bank.interbank_liabilities + bank.emergency_borrowing,
                    assets,
                    liabilities,
                    bank.equity,
                    bank.exp_inflation,
                    bank.exp_nominal_rate,
                    None,
                    None,
                    bank.current_balance,
                    bank.current_debt,
                    bank.interbank_assets,
                    bank.interbank_liabilities,
                    bank.emergency_borrowing,
                    int(bank.liquidity_failed),
                )
            )

    def validate_monetary_system(self):
        deposit_assets = (
            sum(firm.current_balance for firm in self.schedule.firms)
            + self.household.current_balance
        )
        deposit_liabilities = sum(bank.current_debt for bank in self.schedule.banks)
        total_reserves = sum(bank.current_balance for bank in self.schedule.banks)
        self.ledger.validate_monetary_totals(
            deposit_assets=deposit_assets,
            deposit_liabilities=deposit_liabilities,
            total_reserves=total_reserves,
            expected_base_money=self.base_money_issued,
        )
        self.ledger.validate_credit_totals(
            borrower_debt=sum(firm.current_debt for firm in self.schedule.firms),
            outstanding_loans=sum(
                loan["remaining_principal"] for loan in self.active_loans
            ),
        )
        self.ledger.validate_liquidity_totals(
            interbank_assets=sum(bank.interbank_assets for bank in self.schedule.banks),
            interbank_liabilities=sum(
                bank.interbank_liabilities for bank in self.schedule.banks
            ),
            emergency_liabilities=sum(
                bank.emergency_borrowing for bank in self.schedule.banks
            ),
            emergency_loans=sum(
                loan["principal"] for loan in self.active_emergency_loans
            ),
        )

    def complete_run(self):
        if self.llm_failure_count:
            self.ledger.update_run_status(
                self.run_id,
                "invalid",
                f"{self.llm_failure_count} LLM decision calls failed",
            )
            return "invalid"
        self.ledger.update_run_status(self.run_id, "completed")
        return "completed"
