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
    def __init__(
        self, unique_id, model, client: AsyncOpenAI, risk_profile: str = "neutral"
    ):
        super().__init__(model)
        self.unique_id = unique_id
        self.risk_profile = risk_profile
        # Using instructor to patch the AsyncOpenAI client
        self.client = instructor.from_openai(client, mode=instructor.Mode.MD_JSON)

        # State variables
        self.current_balance: float = 100.0  # Initial equity
        self.current_debt: float = 0.0
        self.equity: float = 100.0  # Assumes current_balance is purely equity initially

        # Expectation trackers (adaptive expectations)
        self.exp_inflation: float = 0.0
        self.exp_nominal_rate: float = 0.05

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
            "sentiment": getattr(self.model, "agent_sentiment", "neutral"),
            "risk_profile": self.risk_profile,
            "exp_inflation": self.exp_inflation,
            "exp_nominal_rate": self.exp_nominal_rate,
        }

    async def strategize_credit_demand(self):
        """
        Asynchronously generates a credit demand using the local Ollama LLM or rules.
        """
        if getattr(self.model, "control_mode", False):
            # Rule-based credit demand based on risk profile and expectations
            if self.risk_profile == "risk-averse":
                principal = max(0.0, 10.0 - 0.1 * self.current_debt)
                max_rate = max(0.01, self.exp_nominal_rate - 0.01)
            elif self.risk_profile == "risk-seeking":
                principal = max(0.0, 40.0 - 0.3 * self.current_debt)
                max_rate = max(0.01, self.exp_nominal_rate + 0.02)
            else:  # neutral
                principal = max(0.0, 20.0 - 0.2 * self.current_debt)
                max_rate = max(0.01, self.exp_nominal_rate)

            self.current_demand = FirmCreditDemand(
                chain_of_thought=f"Control group: deterministic rule-based credit demand for {self.risk_profile} profile.",
                loan_principal_requested=principal,
                max_acceptable_nominal_rate=max_rate,
            )
            return self.current_demand

        memory_state = self.get_compact_memory()
        sentiment_context = ""
        sentiment = memory_state["sentiment"]
        if sentiment == "optimistic":
            sentiment_context = "\nMacroeconomic Outlook: Highly Favorable. High demand expected. Animal spirits are strong. Plan for aggressive growth and higher credit capacity."
        elif sentiment == "pessimistic":
            sentiment_context = "\nMacroeconomic Outlook: Elevated Risk. Downward trends expected. Conserve capital, minimize credit/debt requests, and hold cash reserves."

        # Risk profile prompts
        risk_context = ""
        if self.risk_profile == "risk-averse":
            risk_context = "\nRisk Profile: Risk-Averse. Minimize your debt burden. Only request credit if absolutely necessary, and demand low maximum interest rates."
        elif self.risk_profile == "risk-seeking":
            risk_context = "\nRisk Profile: Risk-Seeking. Maximize growth and expand production aggressively. Request large loan amounts and be willing to accept higher interest rates."
        else:
            risk_context = "\nRisk Profile: Neutral. Balance growth opportunities with credit cost, requesting moderate loan amounts at market-average interest rates."

        prompt = f"""
You are a Firm deciding how much credit to request and the maximum interest rate you will accept.
Your current state:
Balance: {memory_state['current_balance']}
Debt: {memory_state['current_debt']}
Realized Inflation: {memory_state['realized_inflation']}
Three Step Yield Trend: {memory_state['three_step_yield_trend']}
Expected Inflation: {memory_state['exp_inflation']}
Expected Nominal Interest Rate: {memory_state['exp_nominal_rate']}{sentiment_context}{risk_context}

Based on the macroeconomic conditions, formulate a strategy.
        """

        # We wrap in a try-except to handle potential LLM parsing errors
        try:
            demand = await self.client.chat.completions.create(
                model=self.model.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Firm agent in a macroeconomic simulation. Output valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=FirmCreditDemand,
                temperature=getattr(self.model, "llm_temperature", 0.7),
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
