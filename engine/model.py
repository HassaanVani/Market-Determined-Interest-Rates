import mesa
from engine.schedule import AsyncMacroScheduler
from models.firm import FirmAgent
from models.bank import BankAgent
from database.ledger import Ledger
from openai import AsyncOpenAI


class MacroModel(mesa.Model):
    def __init__(self, n_firms=5, n_banks=2, db_path=":memory:", control_mode=False):
        super().__init__()
        self.num_firms = n_firms
        self.num_banks = n_banks
        self.control_mode = control_mode

        self.ledger = Ledger(db_path)
        self.schedule = AsyncMacroScheduler(self)

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

        # Initialize Banks
        for i in range(self.num_banks):
            b = BankAgent(f"bank_{i}", self, self.client)
            self.schedule.add(b)
            # Initial ledger state
            self.ledger.update_balance_sheet(
                b.unique_id, "Bank", b.current_balance, b.current_debt, b.equity
            )

        # Initialize Firms
        for i in range(self.num_firms):
            f = FirmAgent(f"firm_{i}", self, self.client)
            self.schedule.add(f)
            # Initial ledger state
            self.ledger.update_balance_sheet(
                f.unique_id, "Firm", f.current_balance, f.current_debt, f.equity
            )

        self.ledger.validate_balance_sheets()

    def step(self):
        self.schedule.step()
