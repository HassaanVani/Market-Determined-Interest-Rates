import mesa
from engine.schedule import AsyncMacroScheduler
from models.firm import FirmAgent
from models.bank import BankAgent
from models.household import HouseholdAgent
from database.ledger import Ledger
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
        reserve_requirement=0.10,
        capital_requirement=0.08,
    ):
        super().__init__()
        self.num_firms = n_firms
        self.num_banks = n_banks
        self.control_mode = control_mode
        self.llm_model = llm_model
        self.agent_sentiment = agent_sentiment
        self.llm_temperature = llm_temperature
        self.reserve_requirement = reserve_requirement
        self.capital_requirement = capital_requirement

        self.ledger = Ledger(db_path)
        self.schedule = AsyncMacroScheduler(self)

        # Loan registry: tracks all outstanding loans
        self.active_loans = []

        # Point AsyncOpenAI to local Ollama instance
        self.client = AsyncOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",  # api_key is required by the SDK but ignored by Ollama
        )

        # Macroeconomic variables
        self.nominal_rate = 0.0
        self.real_interest_rate = 0.0
        self.realized_inflation = 0.0
        self.three_step_yield_trend = 0.0

        # Create Households (starts with 100.0 deposits)
        self.household = HouseholdAgent("household", self)
        self.household.current_balance = 100.0
        self.household.update_equity()
        self.ledger.update_balance_sheet(
            self.household.unique_id,
            "Household",
            self.household.current_balance,
            self.household.current_debt,
            self.household.equity,
        )

        # Distribute initial deposits (from firms and households) as liabilities to the banks
        total_initial_deposits = (n_firms * 100.0) + 100.0
        initial_debt_per_bank = total_initial_deposits / n_banks

        # Initialize Banks
        for i in range(self.num_banks):
            b = BankAgent(f"bank_{i}", self, self.client)
            # Adjust bank balance sheet to accommodate deposits
            b.current_debt = initial_debt_per_bank
            b.equity = b.current_balance - b.current_debt

            self.schedule.add(b)
            self.ledger.update_balance_sheet(
                b.unique_id, "Bank", b.current_balance, b.current_debt, b.equity
            )

        # Initialize Firms
        for i in range(self.num_firms):
            f = FirmAgent(f"firm_{i}", self, self.client)
            self.schedule.add(f)
            self.ledger.update_balance_sheet(
                f.unique_id, "Firm", f.current_balance, f.current_debt, f.equity
            )

        self.ledger.validate_balance_sheets()

    def step(self):
        self.schedule.step()
