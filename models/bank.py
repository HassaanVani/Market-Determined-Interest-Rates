from pydantic import BaseModel, Field
import mesa
from openai import AsyncOpenAI
from engine.experiment import BehaviorMode, RateRegime
from engine.llm_runtime import call_structured_llm


class BankCreditDecision(BaseModel):
    decision_rationale: str = Field(
        ...,
        description="A concise economic rationale for the credit decision",
    )
    approved: bool = Field(..., description="Whether the bank approves the loan")
    offered_nominal_rate: float = Field(
        ..., description="The nominal interest rate offered (as a decimal, e.g. 0.05)"
    )
    decision_status: str = Field(
        default="economic",
        description="Whether this is an economic decision or an LLM infrastructure failure",
    )

    @property
    def chain_of_thought(self):
        return self.decision_rationale


class BankAgent(mesa.Agent):
    def __init__(self, unique_id, model, client: AsyncOpenAI):
        super().__init__(model)
        self.unique_id = unique_id
        self.client = client

        self.current_balance: float = (
            model.initial_reserves_per_bank
        )  # settlement reserves
        self.current_debt: float = 0.0  # Liabilities (e.g. deposits)
        self.equity: float = self.current_balance
        self.other_assets: float = 0.0
        self.interbank_assets: float = 0.0
        self.interbank_liabilities: float = 0.0
        self.emergency_borrowing: float = 0.0
        self.liquidity_failed: bool = False
        try:
            bank_index = int(str(unique_id).rsplit("_", 1)[1])
        except (IndexError, ValueError):
            bank_index = 0
        self.pricing_spread = (((bank_index + 1) % 3) - 1) * 0.001

        # Expectation trackers (adaptive expectations)
        self.exp_inflation: float = 0.0
        self.exp_nominal_rate: float = 0.05

    def get_compact_memory(self):
        """
        Compresses active memory into a lean dictionary avoiding raw transaction strings.
        """
        return {
            "current_balance": self.current_balance,
            "current_debt": self.current_debt,
            "other_assets": self.other_assets,
            "interbank_assets": self.interbank_assets,
            "interbank_liabilities": self.interbank_liabilities,
            "emergency_borrowing": self.emergency_borrowing,
            "realized_inflation": self.model.realized_inflation,
            "three_step_yield_trend": self.model.three_step_yield_trend,
            "exp_inflation": self.exp_inflation,
            "exp_nominal_rate": self.exp_nominal_rate,
            "shock_effects": self.model.current_shock_effects,
        }

    def regulatory_feasibility(self, firm_id: str, principal: float):
        """Return whether a loan is feasible under hard balance-sheet rules."""
        if self.liquidity_failed:
            return (
                False,
                "Liquidity Rejection: Bank has an unresolved reserve shortfall.",
            )
        firm = next(
            (f for f in self.model.schedule.firms if f.unique_id == firm_id), None
        )
        if firm:
            equity = firm.equity
            post_loan_debt = firm.current_debt + principal
            leverage_limit = getattr(self.model, "leverage_limit", 1.5)
            if equity <= 0 or (post_loan_debt / equity) > leverage_limit:
                ratio = post_loan_debt / equity if equity > 0 else float("inf")
                return (
                    False,
                    f"Leverage Rejection: Post-loan firm debt-to-equity ratio "
                    f"({ratio:.4f}) exceeds leverage limit ({leverage_limit}).",
                )

        reserve_requirement = getattr(self.model, "reserve_requirement", 0.10)
        capital_requirement = getattr(self.model, "capital_requirement", 0.08)

        loans_outstanding = sum(
            loan["remaining_principal"]
            for loan in self.model.active_loans
            if loan["bank_id"] == self.unique_id
        )

        post_loan_deposits = self.current_debt + principal
        if post_loan_deposits > 0:
            post_loan_reserve_ratio = self.current_balance / post_loan_deposits
            if post_loan_reserve_ratio < reserve_requirement:
                return (
                    False,
                    f"Regulatory Rejection: Post-loan reserve ratio "
                    f"({post_loan_reserve_ratio:.4f}) falls below requirement "
                    f"({reserve_requirement}).",
                )

        post_loan_loans = loans_outstanding + principal
        if post_loan_loans > 0:
            post_loan_capital_ratio = self.equity / post_loan_loans
            if post_loan_capital_ratio < capital_requirement:
                return (
                    False,
                    f"Regulatory Rejection: Post-loan Basel capital ratio "
                    f"({post_loan_capital_ratio:.4f}) falls below requirement "
                    f"({capital_requirement}).",
                )
        return True, ""

    async def evaluate_loan(
        self, firm_id: str, principal: float, max_rate: float
    ) -> BankCreditDecision:
        # Hard feasibility constraints apply to both behavioral specifications.
        feasible, rejection_reason = self.regulatory_feasibility(firm_id, principal)
        if not feasible:
            return BankCreditDecision(
                decision_rationale=rejection_reason,
                approved=False,
                offered_nominal_rate=0.0,
            )

        firm = next(
            (f for f in self.model.schedule.firms if f.unique_id == firm_id), None
        )
        reserve_requirement = getattr(self.model, "reserve_requirement", 0.10)
        capital_requirement = getattr(self.model, "capital_requirement", 0.08)
        loans_outstanding = sum(
            loan["remaining_principal"]
            for loan in self.model.active_loans
            if loan["bank_id"] == self.unique_id
        )

        if self.model.behavior_mode == BehaviorMode.RULE:
            leverage = 0.0
            risk_profile = "neutral"
            if firm:
                leverage = max(0.0, firm.current_debt / max(firm.equity, 1e-9))
                risk_profile = firm.risk_profile

            profile_premium = {
                "risk-averse": 0.002,
                "neutral": 0.006,
                "risk-seeking": 0.012,
            }.get(risk_profile, 0.006)
            borrower_risk_premium = max(0.0, profile_premium - 0.002) + 0.015 * leverage

            reserve_ratio = (
                self.current_balance / self.current_debt
                if self.current_debt > 0
                else float("inf")
            )
            target_reserve_ratio = reserve_requirement + 0.65
            liquidity_premium = max(0.0, target_reserve_ratio - reserve_ratio) * 0.010
            capital_ratio = (
                self.equity / loans_outstanding
                if loans_outstanding > 0
                else float("inf")
            )
            # The hard capital requirement is enforced above. Pricing also
            # responds smoothly to how much of the bank's loan book is funded
            # by equity, rather than activating only at the regulatory cliff.
            capital_premium = (
                0.005
                * loans_outstanding
                / max(loans_outstanding + self.equity, 1e-9)
            )

            if self.model.rate_regime == RateRegime.ADMINISTERED:
                # The policy rate is the anchor; local information has an
                # attenuated effect on the final retail quote.
                offered_rate = (
                    self.model.policy_rate
                    + 0.25
                    * (borrower_risk_premium + liquidity_premium + capital_premium)
                    + self.pricing_spread
                )
                regime_description = "administered policy-rate anchor"
            else:
                # With no policy-rate anchor, the quote is built from the bank's
                # required real return, expectations, and local balance-sheet risk.
                offered_rate = (
                    0.02
                    + self.exp_inflation
                    + self.model.current_shock_effects["expected_inflation_shift"]
                    + borrower_risk_premium
                    + liquidity_premium
                    + capital_premium
                    + self.pricing_spread
                )
                regime_description = "decentralized market pricing"

            offered_rate = max(0.01, offered_rate)
            approved = (principal <= self.current_balance * 0.5) and (
                offered_rate <= max_rate
            )
            return BankCreditDecision(
                decision_rationale=(
                    f"Rule-based {regime_description}; quoted {offered_rate:.4f} "
                    f"after borrower, capital, and liquidity adjustments."
                ),
                approved=approved,
                offered_nominal_rate=offered_rate if approved else 0.0,
            )

        memory_state = self.get_compact_memory()
        sentiment_context = ""
        sentiment = getattr(self.model, "agent_sentiment", "neutral")
        if sentiment == "optimistic":
            sentiment_context = "\nMacroeconomic Outlook: Highly Favorable. Low defaults expected. Animal spirits are strong. Focus on expanding lending and support credit demands."
        elif sentiment == "pessimistic":
            sentiment_context = "\nMacroeconomic Outlook: Elevated Risk. Defaults are likely to rise. Conserve capital, restrict lending to high-interest offers, or reject riskier loans."

        if self.model.rate_regime == RateRegime.ADMINISTERED:
            regime_context = f"""
Rate Regime: Administered-rate anchor.
The central policy rate is {self.model.policy_rate}. Price the loan relative to
that anchor, adding a transparent premium for borrower and balance-sheet risk."""
        else:
            regime_context = """
Rate Regime: Decentralized market discovery.
There is no administered policy-rate anchor. Form your quote from expected
inflation, required real return, borrower risk, and your balance-sheet condition."""

        prompt = f"""
You are a Bank evaluating a loan request from Firm {firm_id}.
Firm requests: Principal: {principal}, Maximum Acceptable Nominal Rate: {max_rate}

Your current state:
Balance (Reserves): {memory_state['current_balance']}
Debt (Deposits): {memory_state['current_debt']}
Realized Inflation: {memory_state['realized_inflation']}
Three Step Yield Trend: {memory_state['three_step_yield_trend']}
Expected Inflation: {memory_state['exp_inflation']}
Expected Nominal Interest Rate: {memory_state['exp_nominal_rate']}{sentiment_context}{regime_context}
Current Exogenous Shock Effects: {memory_state['shock_effects']}

Decide whether to approve this loan and what nominal rate to offer. 
Do not exceed the firm's maximum acceptable rate if you want them to accept.
        """

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a Bank agent in a macroeconomic simulation. "
                    "Output valid JSON and provide only a concise economic "
                    "decision rationale."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        decision, error = await call_structured_llm(
            model=self.model,
            agent_id=self.unique_id,
            task_type=f"loan_evaluation_{firm_id}",
            client=self.client,
            messages=messages,
            response_model=BankCreditDecision,
        )
        if decision is not None:
            return decision
        print(f"Bank {self.unique_id} failed to evaluate loan: {error}")
        return BankCreditDecision(
            decision_rationale=(
                "LLM infrastructure failure; no economic credit decision."
            ),
            approved=False,
            offered_nominal_rate=0.0,
            decision_status="llm_failure",
        )
