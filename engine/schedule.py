import mesa
import asyncio
import random
from models.firm import FirmAgent
from models.bank import BankAgent


class AsyncMacroScheduler:
    def __init__(self, model):
        self.model = model
        self.steps = 0
        self.time = 0
        self.firms = []
        self.banks = []

    def add(self, agent):
        if isinstance(agent, FirmAgent):
            self.firms.append(agent)
        elif isinstance(agent, BankAgent):
            self.banks.append(agent)

    def remove(self, agent):
        if isinstance(agent, FirmAgent):
            self.firms.remove(agent)
        elif isinstance(agent, BankAgent):
            self.banks.remove(agent)

    def step(self):
        """
        Mesa's step method, which we hijack to run our async loop.
        """
        asyncio.run(self.async_step())
        self.steps += 1
        self.time += 1

    async def async_step(self):
        """
        The three distinct computational sub-steps per tick:
        1. Production Strategy (Firm Request)
        2. Credit Clearing (Bank Negotiation)
        3. Macro-Accounting (Deterministic system update)
        """
        # --- 1. Production Strategy ---
        # Asynchronous Batching: Wrap the agent query loops inside an asyncio.gather pipeline
        firm_tasks = [firm.strategize_credit_demand() for firm in self.firms]
        demands = await asyncio.gather(*firm_tasks)

        # --- 2. Credit Clearing ---
        # For simplicity in clearing, each firm with a >0 demand applies to a random bank
        bank_tasks = []
        loan_applications = []  # Keep track of (firm, bank) pairs

        for firm in self.firms:
            demand = firm.current_demand
            if demand and demand.loan_principal_requested > 0 and self.banks:
                bank = random.choice(self.banks)
                task = bank.evaluate_loan(
                    firm_id=firm.unique_id,
                    principal=demand.loan_principal_requested,
                    max_rate=demand.max_acceptable_nominal_rate,
                )
                bank_tasks.append(task)
                loan_applications.append((firm, bank, demand))

        if bank_tasks:
            decisions = await asyncio.gather(*bank_tasks)
        else:
            decisions = []

        total_nominal_rates = 0.0
        approved_loans_count = 0

        # Process the outcomes
        for (firm, bank, demand), decision in zip(loan_applications, decisions):
            if (
                decision.approved
                and decision.offered_nominal_rate <= demand.max_acceptable_nominal_rate
            ):
                principal = demand.loan_principal_requested
                # Endogenous money creation: Bank creates deposit (liability) and loan (asset)
                # Firm gets deposit (asset) and loan (liability)

                # Bank ledger update
                bank.current_balance += principal  # Asset: Loan to firm (simplification, using current_balance to sum up total size, but correctly it's just total assets)
                bank.current_debt += principal  # Liability: Deposit created for firm

                # Firm ledger update
                firm.current_balance += principal  # Asset: Deposit at bank
                firm.current_debt += principal  # Liability: Loan from bank

                total_nominal_rates += decision.offered_nominal_rate
                approved_loans_count += 1

        # --- 3. Macro-Accounting ---
        # Update Ledger and Validate
        ledger = self.model.ledger
        for bank in self.banks:
            # For Bank, Equity = Assets - Liabilities
            ledger.update_balance_sheet(
                bank.unique_id,
                "Bank",
                bank.current_balance,
                bank.current_debt,
                bank.equity,
            )

        for firm in self.firms:
            # For Firm, Equity = Assets - Liabilities
            ledger.update_balance_sheet(
                firm.unique_id,
                "Firm",
                firm.current_balance,
                firm.current_debt,
                firm.equity,
            )

        # Strict state-check method inside ledger.py that verifies Total Assets == Total Liabilities + Total Equity
        ledger.validate_balance_sheets()

        # Compute the Real Interest Rate deterministically using the Fisher Equation: I_r = I_n - \pi
        # Calculate average nominal rate for this step
        if approved_loans_count > 0:
            avg_nominal_rate = total_nominal_rates / approved_loans_count
        else:
            avg_nominal_rate = 0.0

        self.model.nominal_rate = avg_nominal_rate

        # Fisher Equation
        self.model.real_interest_rate = (
            self.model.nominal_rate - self.model.realized_inflation
        )

        # Update trends
        self.model.three_step_yield_trend = (
            self.model.real_interest_rate
        )  # Naive current rate as trend for now

        # Simple inflation model for demonstration (inflation goes up if money supply goes up)
        total_money_supply = sum(f.current_balance for f in self.firms)
        self.model.realized_inflation = min(
            0.1, max(0.0, (total_money_supply - 100 * len(self.firms)) / 10000.0)
        )
