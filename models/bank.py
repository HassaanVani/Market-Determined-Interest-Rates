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
        if getattr(self.model, "control_mode", False):
            # Control group: deterministic central bank rule (e.g. Taylor rule style or simple fixed rate)
            # Say, a fixed nominal rate of 5% (0.05)
            fixed_rate = 0.05
            approved = (principal <= self.current_balance * 0.5) and (fixed_rate <= max_rate)
            return BankCreditDecision(
                chain_of_thought="Control group: deterministic approval rule with fixed interest rate of 5%.",
                approved=approved,
                offered_nominal_rate=fixed_rate if approved else 0.0
            )

        memory_state = self.get_compact_memory()

        prompt = f"""
You are a Bank evaluating a loan request from Firm {firm_id}.
Firm requests: Principal: {principal}, Maximum Acceptable Nominal Rate: {max_rate}

Your current state:
Balance (Reserves): {memory_state['current_balance']}
Debt (Deposits): {memory_state['current_debt']}
Realized Inflation: {memory_state['realized_inflation']}
Three Step Yield Trend: {memory_state['three_step_yield_trend']}

Decide whether to approve this loan and what nominal rate to offer. 
Do not exceed the firm's maximum acceptable rate if you want them to accept.
        """

        try:
            decision = await self.client.chat.completions.create(
                model=self.model.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Bank agent in a macroeconomic simulation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=BankCreditDecision,
            )
            return decision
        except Exception as e:
            print(f"Bank {self.unique_id} failed to evaluate loan: {e}")
            return BankCreditDecision(
                chain_of_thought="Fallback rejection.",
                approved=False,
                offered_nominal_rate=0.0,
            )
