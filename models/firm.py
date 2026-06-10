from pydantic import BaseModel, Field
import mesa
import instructor
from openai import AsyncOpenAI


# Pydantic schema for Firm's credit demand
class FirmCreditDemand(BaseModel):
    chain_of_thought: str = Field(
        ..., description="The reasoning behind the credit request"
    )
    loan_principal_requested: float = Field(
        ..., description="The amount of money requested as a loan"
    )
    max_acceptable_nominal_rate: float = Field(
        ...,
        description="The maximum nominal interest rate the firm is willing to accept (as a decimal, e.g. 0.05 for 5%)",
    )


class FirmAgent(mesa.Agent):
    def __init__(self, unique_id, model, client: AsyncOpenAI):
        super().__init__(model)
        self.unique_id = unique_id
        # Using instructor to patch the AsyncOpenAI client
        self.client = instructor.from_openai(client, mode=instructor.Mode.MD_JSON)

        # State variables
        self.current_balance: float = 100.0  # Initial equity
        self.current_debt: float = 0.0
        self.equity: float = 100.0  # Assumes current_balance is purely equity initially

        # Temporary storage for current step's demand
        self.current_demand: FirmCreditDemand | None = None

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

    async def strategize_credit_demand(self):
        """
        Asynchronously generates a credit demand using the local Ollama LLM.
        """
        if getattr(self.model, "control_mode", False):
            # Rule-based credit demand for control group
            self.current_demand = FirmCreditDemand(
                chain_of_thought="Control group: deterministic rule-based credit demand.",
                loan_principal_requested=20.0 if self.current_debt == 0 else 5.0,
                max_acceptable_nominal_rate=0.08
            )
            return self.current_demand

        memory_state = self.get_compact_memory()

        prompt = f"""
You are a Firm deciding how much credit to request and the maximum interest rate you will accept.
Your current state:
Balance: {memory_state['current_balance']}
Debt: {memory_state['current_debt']}
Realized Inflation: {memory_state['realized_inflation']}
Three Step Yield Trend: {memory_state['three_step_yield_trend']}

Based on the macroeconomic conditions, formulate a strategy.
        """

        # We wrap in a try-except to handle potential LLM parsing errors
        try:
            demand = await self.client.chat.completions.create(
                model=self.model.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Firm agent in a macroeconomic simulation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=FirmCreditDemand,
            )
            self.current_demand = demand
        except Exception as e:
            print(f"Firm {self.unique_id} failed to generate demand: {e}")
            # Fallback demand
            self.current_demand = FirmCreditDemand(
                chain_of_thought="Fallback due to generation error.",
                loan_principal_requested=0.0,
                max_acceptable_nominal_rate=0.0,
            )

        return self.current_demand
