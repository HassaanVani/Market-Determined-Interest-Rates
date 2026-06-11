from pydantic import BaseModel, Field
import mesa
import instructor
from openai import AsyncOpenAI
from typing import List


class BankCreditDecision(BaseModel):
    chain_of_thought: str = Field(
        ...,
        description="Reasoning for approving or rejecting the loan and setting the rate",
    )
    approved: bool = Field(..., description="Whether the bank approves the loan")
    offered_nominal_rate: float = Field(
        ..., description="The nominal interest rate offered (as a decimal, e.g. 0.05)"
    )


class BankAgent(mesa.Agent):
    def __init__(self, unique_id, model, client: AsyncOpenAI):
        super().__init__(model)
        self.unique_id = unique_id
        self.client = instructor.from_openai(client, mode=instructor.Mode.MD_JSON)

        self.current_balance: float = 1000.0  # Initial assets (e.g. reserves)
        self.current_debt: float = 0.0  # Liabilities (e.g. deposits)
        self.equity: float = 1000.0

    def get_compact_memory(self):
        """
        Compresses active memory into a lean dictionary avoiding raw transaction strings.
        """
        return {
            "current_balance": self.current_balance,
            "current_debt": self.current_debt,
            "realized_inflation": self.model.realized_inflation,
            "three_step_yield_trend": self.model.three_step_yield_trend,
        }

    async def evaluate_loan(
        self, firm_id: str, principal: float, max_rate: float
    ) -> BankCreditDecision:
        # Programmatic Regulatory Constraints Check (Basel & Reserves)
        reserve_requirement = getattr(self.model, "reserve_requirement", 0.10)
        capital_requirement = getattr(self.model, "capital_requirement", 0.08)

        # Calculate outstanding loans for this bank
        loans_outstanding = sum(
            loan["remaining_principal"]
            for loan in self.model.active_loans
            if loan["bank_id"] == self.unique_id
        )

        # 1. Check Reserve Ratio constraint post-loan: Reserves / (Deposits + principal) >= reserve_requirement
        # Bank reserves are self.current_balance; Bank deposits are self.current_debt
        post_loan_deposits = self.current_debt + principal
        if post_loan_deposits > 0:
            post_loan_reserve_ratio = self.current_balance / post_loan_deposits
            if post_loan_reserve_ratio < reserve_requirement:
                return BankCreditDecision(
                    chain_of_thought=f"Regulatory Rejection: Post-loan reserve ratio ({post_loan_reserve_ratio:.4f}) falls below requirement ({reserve_requirement}).",
                    approved=False,
                    offered_nominal_rate=0.0,
                )

        # 2. Check Basel Capital Adequacy post-loan: Equity / (Loans Outstanding + principal) >= capital_requirement
        post_loan_loans = loans_outstanding + principal
        if post_loan_loans > 0:
            post_loan_capital_ratio = self.equity / post_loan_loans
            if post_loan_capital_ratio < capital_requirement:
                return BankCreditDecision(
                    chain_of_thought=f"Regulatory Rejection: Post-loan Basel capital ratio ({post_loan_capital_ratio:.4f}) falls below requirement ({capital_requirement}).",
                    approved=False,
                    offered_nominal_rate=0.0,
                )

        if getattr(self.model, "control_mode", False):
            # Control group: deterministic central bank rule (e.g. Taylor rule style or simple fixed rate)
            # Say, a fixed nominal rate of 5% (0.05)
            fixed_rate = 0.05
            approved = (principal <= self.current_balance * 0.5) and (
                fixed_rate <= max_rate
            )
            return BankCreditDecision(
                chain_of_thought="Control group: deterministic approval rule with fixed interest rate of 5%.",
                approved=approved,
                offered_nominal_rate=fixed_rate if approved else 0.0,
            )

        memory_state = self.get_compact_memory()
        sentiment_context = ""
        sentiment = getattr(self.model, "agent_sentiment", "neutral")
        if sentiment == "optimistic":
            sentiment_context = "\nMacroeconomic Outlook: Highly Favorable. Low defaults expected. Animal spirits are strong. Focus on expanding lending and support credit demands."
        elif sentiment == "pessimistic":
            sentiment_context = "\nMacroeconomic Outlook: Elevated Risk. Defaults are likely to rise. Conserve capital, restrict lending to high-interest offers, or reject riskier loans."

        prompt = f"""
You are a Bank evaluating a loan request from Firm {firm_id}.
Firm requests: Principal: {principal}, Maximum Acceptable Nominal Rate: {max_rate}

Your current state:
Balance (Reserves): {memory_state['current_balance']}
Debt (Deposits): {memory_state['current_debt']}
Realized Inflation: {memory_state['realized_inflation']}
Three Step Yield Trend: {memory_state['three_step_yield_trend']}{sentiment_context}

Decide whether to approve this loan and what nominal rate to offer. 
Do not exceed the firm's maximum acceptable rate if you want them to accept.
        """

        try:
            decision = await self.client.chat.completions.create(
                model=self.model.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Bank agent in a macroeconomic simulation. Output valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=BankCreditDecision,
                temperature=getattr(self.model, "llm_temperature", 0.7),
            )
            return decision
        except Exception as e:
            print(f"Bank {self.unique_id} failed to evaluate loan: {e}")
            return BankCreditDecision(
                chain_of_thought="Fallback rejection.",
                approved=False,
                offered_nominal_rate=0.0,
            )
