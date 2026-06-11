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
        Mesa's step method, which runs our async closed-loop macroeconomic cycle.
        """
        asyncio.run(self.async_step())
        self.steps += 1
        self.time += 1

    async def async_step(self):
        """
        Closed-loop macroeconomic sub-steps:
        1. Production & Wage Payments (Firms pay Households)
        2. Production Strategy (Firm Request Credit demands)
        3. Credit Clearing (Banks evaluate credit subject to reserve & Basel ratios)
        4. Goods Market Clearing (Households spend consumption revenue on Firms)
        5. Debt Service & Amortization (Firms pay Bank; default resolution if Firm insolvent)
        6. Macro-Accounting & Synchronization (Fisher calculation, double-entry validation)
        """
        # --- 1. Production & Wage Payments ---
        payroll_per_firm = 5.0
        total_payroll = 0.0
        aggregate_output = 0.0

        for firm in self.firms:
            # Pay wages to household
            wages = min(payroll_per_firm, firm.current_balance)
            firm.current_balance -= wages
            self.model.household.current_balance += wages

            # Simple production: Output = beta * wages (Beta = 1.2)
            firm.output = wages * 1.2
            aggregate_output += firm.output
            total_payroll += wages

        # --- 2. Production Strategy ---
        # Asynchronous Batching: Gather firm credit demands
        firm_tasks = [firm.strategize_credit_demand() for firm in self.firms]
        demands = await asyncio.gather(*firm_tasks)

        # --- 3. Credit Clearing ---
        bank_tasks = []
        loan_applications = []

        for firm in self.firms:
            demand = firm.current_demand
            if demand and demand.loan_principal_requested > 0 and self.banks:
                bank = random.choice(self.banks)
                # evaluate_loan contains Reserve requirement and Basel Capital check programmatically
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

        # Process approved loans and create endogenous money
        for (firm, bank, demand), decision in zip(loan_applications, decisions):
            if (
                decision.approved
                and decision.offered_nominal_rate <= demand.max_acceptable_nominal_rate
            ):
                principal = demand.loan_principal_requested

                # Symmetrical balance sheet expansion (loan creation)
                firm.current_balance += principal
                firm.current_debt += principal

                # Register the loan in the model's active loan book
                loan = {
                    "loan_id": f"loan_{self.steps}_{firm.unique_id}",
                    "borrower_id": firm.unique_id,
                    "bank_id": bank.unique_id,
                    "principal": principal,
                    "remaining_principal": principal,
                    "interest_rate": decision.offered_nominal_rate,
                    "duration": 5,
                    "age": 0,
                }
                self.model.active_loans.append(loan)

                total_nominal_rates += decision.offered_nominal_rate
                approved_loans_count += 1

        # --- 4. Goods Market Clearing (Consumption) ---
        # Households consume a fraction (80%) of their accumulated wealth
        total_consumption = self.model.household.current_balance * 0.8
        self.model.household.current_balance -= total_consumption

        # Consumption revenue is distributed equally across firms
        if self.firms:
            revenue_per_firm = total_consumption / len(self.firms)
            for firm in self.firms:
                firm.current_balance += revenue_per_firm

        # --- 5. Debt Service, Amortization & Defaults ---
        still_active_loans = []
        for loan in self.model.active_loans:
            # Find borrower (Firm) and bank
            firm = next(
                (f for f in self.firms if f.unique_id == loan["borrower_id"]), None
            )
            bank = next((b for b in self.banks if b.unique_id == loan["bank_id"]), None)

            if not firm or not bank:
                continue

            # Amortization payment (linear principal payment + interest)
            amortization = loan["principal"] / loan["duration"]
            interest = loan["remaining_principal"] * loan["interest_rate"]
            total_due = amortization + interest

            if firm.current_balance >= total_due:
                # Fully service debt
                firm.current_balance -= total_due
                firm.current_debt -= amortization

                # Bank updates reserves with interest income (reserves is balance)
                # reserves increase by interest, deposits liability decreases by amortization + interest
                bank.current_balance += interest

                loan["remaining_principal"] -= amortization
                loan["age"] += 1

                if loan["remaining_principal"] > 0 and loan["age"] < loan["duration"]:
                    still_active_loans.append(loan)
            else:
                # DEFAULT! Firm cannot afford total debt service.
                # Wipes out all remaining deposits to service what is possible
                paid = firm.current_balance
                firm.current_balance = 0.0

                interest_paid = min(interest, paid)
                amort_paid = max(0.0, paid - interest_paid)

                # Firm updates
                firm.current_debt -= amort_paid
                bank.current_balance += interest_paid

                # Write off the rest of the loan
                write_off_principal = loan["remaining_principal"] - amort_paid
                firm.current_debt -= write_off_principal  # Debt canceled for firm

                # Bank takes the hit to equity (losses written off, reducing outstanding loans asset)
                loan["remaining_principal"] = 0.0

        self.model.active_loans = still_active_loans

        # --- 6. Macro-Accounting & Synchronization ---
        # Synchronize Bank Deposit Liabilities (current_debt) with actual deposits of firms and household
        total_deposits = (
            sum(f.current_balance for f in self.firms)
            + self.model.household.current_balance
        )
        if self.banks:
            deposit_share_per_bank = total_deposits / len(self.banks)
            for bank in self.banks:
                bank.current_debt = deposit_share_per_bank

                # Outstanding loans for this bank
                loans_outstanding = sum(
                    l["remaining_principal"]
                    for l in self.model.active_loans
                    if l["bank_id"] == bank.unique_id
                )
                # Bank Equity = Reserves (current_balance) + Outstanding Loans - Deposit Liabilities
                bank.equity = (
                    bank.current_balance + loans_outstanding - bank.current_debt
                )

        # Synchronize Firm and Household Equities
        for firm in self.firms:
            firm.equity = firm.current_balance - firm.current_debt

        self.model.household.update_equity()

        # Update SQLite database balance sheets
        ledger = self.model.ledger
        for bank in self.banks:
            # Bank Total Assets = Reserves (current_balance) + Outstanding Loans
            loans_outstanding = sum(
                l["remaining_principal"]
                for l in self.model.active_loans
                if l["bank_id"] == bank.unique_id
            )
            bank_total_assets = bank.current_balance + loans_outstanding
            ledger.update_balance_sheet(
                bank.unique_id,
                "Bank",
                bank_total_assets,
                bank.current_debt,
                bank.equity,
            )

        for firm in self.firms:
            ledger.update_balance_sheet(
                firm.unique_id,
                "Firm",
                firm.current_balance,
                firm.current_debt,
                firm.equity,
            )

        ledger.update_balance_sheet(
            self.model.household.unique_id,
            "Household",
            self.model.household.current_balance,
            self.model.household.current_debt,
            self.model.household.equity,
        )

        # Strict balance sheet checks
        ledger.validate_balance_sheets()

        # Dynamic Demand-Pull Inflation level: pi_t = alpha * (C_t / Y_t - 1)
        # alpha = 0.1
        if aggregate_output > 0:
            inflation_rate = 0.1 * ((total_consumption / aggregate_output) - 1.0)
        else:
            # If no output produced, inflation jumps
            inflation_rate = 0.10 if total_consumption > 0 else 0.0

        # Clamp realized inflation between -0.05 (deflation) and 0.10 (max inflation)
        self.model.realized_inflation = min(0.10, max(-0.05, inflation_rate))

        # Compute the average nominal rate for new loans or outstanding loans
        if approved_loans_count > 0:
            avg_nominal_rate = total_nominal_rates / approved_loans_count
        else:
            avg_nominal_rate = 0.0
        self.model.nominal_rate = avg_nominal_rate

        # Deterministic Real Interest Rate
        self.model.real_interest_rate = (
            self.model.nominal_rate - self.model.realized_inflation
        )
        self.model.three_step_yield_trend = self.model.real_interest_rate
