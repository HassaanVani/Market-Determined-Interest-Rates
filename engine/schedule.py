import asyncio
from engine.experiment import BehaviorMode
from models.firm import FirmAgent
from models.bank import BankAgent


class AsyncMacroScheduler:
    def __init__(self, model):
        self.model = model
        self.steps = 0
        self.time = 0
        self.firms = []
        self.banks = []
        self.settlement_sequence = 0

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

    def get_bank(self, bank_id):
        return next((bank for bank in self.banks if bank.unique_id == bank_id), None)

    def _record_settlement(
        self,
        period,
        event_type,
        payer_id,
        payee_id,
        payer_bank,
        payee_bank,
        amount,
        reserve_transfer,
        loan_id=None,
    ):
        self.settlement_sequence += 1
        event_id = f"{self.model.run_id}-p{period}-s{self.settlement_sequence}"
        self.model.ledger.record_settlement_event(
            event_id=event_id,
            run_id=self.model.run_id,
            period=period,
            event_type=event_type,
            payer_id=payer_id,
            payee_id=payee_id,
            payer_bank_id=payer_bank.unique_id,
            payee_bank_id=payee_bank.unique_id,
            amount=amount,
            reserve_transfer=reserve_transfer,
            loan_id=loan_id,
        )

    def transfer_deposit(self, payer, payee, amount, event_type, period, loan_id=None):
        """Transfer an existing deposit and settle across reserve accounts."""
        if amount < 0 or amount > payer.current_balance + 1e-9:
            raise ValueError(
                f"Invalid deposit transfer of {amount} from {payer.unique_id}"
            )
        if amount == 0:
            return

        payer_bank = self.get_bank(payer.deposit_bank_id)
        payee_bank = self.get_bank(payee.deposit_bank_id)
        if payer_bank is None or payee_bank is None:
            raise ValueError("Deposit account references an unknown bank")

        payer.current_balance -= amount
        payer_bank.current_debt -= amount
        payee.current_balance += amount
        payee_bank.current_debt += amount

        reserve_transfer = 0.0
        if payer_bank is not payee_bank:
            payer_bank.current_balance -= amount
            payee_bank.current_balance += amount
            reserve_transfer = amount

        self._record_settlement(
            period,
            event_type,
            payer.unique_id,
            payee.unique_id,
            payer_bank,
            payee_bank,
            amount,
            reserve_transfer,
            loan_id,
        )

    def create_loan_deposit(self, firm, lender, amount, period, loan_id):
        """Create a loan deposit and transfer it to the firm's deposit bank."""
        deposit_bank = self.get_bank(firm.deposit_bank_id)
        if deposit_bank is None:
            raise ValueError("Firm deposit account references an unknown bank")

        firm.current_balance += amount
        deposit_bank.current_debt += amount

        reserve_transfer = 0.0
        if lender is not deposit_bank:
            lender.current_balance -= amount
            deposit_bank.current_balance += amount
            reserve_transfer = amount

        self._record_settlement(
            period,
            "loan_disbursement",
            lender.unique_id,
            firm.unique_id,
            lender,
            deposit_bank,
            amount,
            reserve_transfer,
            loan_id,
        )

    def settle_loan_payment(self, firm, lender, amount, period, loan_id, event_type):
        """Destroy the payer's deposit while settling with the lender."""
        if amount < 0 or amount > firm.current_balance + 1e-9:
            raise ValueError(f"Invalid loan payment of {amount} from {firm.unique_id}")
        if amount == 0:
            return

        deposit_bank = self.get_bank(firm.deposit_bank_id)
        if deposit_bank is None:
            raise ValueError("Firm deposit account references an unknown bank")

        firm.current_balance -= amount
        deposit_bank.current_debt -= amount

        reserve_transfer = 0.0
        if deposit_bank is not lender:
            deposit_bank.current_balance -= amount
            lender.current_balance += amount
            reserve_transfer = amount

        self._record_settlement(
            period,
            event_type,
            firm.unique_id,
            lender.unique_id,
            deposit_bank,
            lender,
            amount,
            reserve_transfer,
            loan_id,
        )

    def step(self):
        """
        Mesa's step method, which runs our async closed-loop macroeconomic cycle.
        """
        asyncio.run(self.managed_async_step())
        self.steps += 1
        self.time += 1

    async def managed_async_step(self):
        if self.model.behavior_mode != BehaviorMode.LLM:
            await self.async_step()
            return

        client = self.model.create_llm_client()
        self.model.client = client
        for agent in [*self.firms, *self.banks]:
            agent.client = client
        try:
            await self.async_step()
        finally:
            await client.close()
            self.model.client = None

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
        self.model.write_offs_in_step = 0.0
        self.model.defaults_in_step = 0
        self.model.new_credit_in_step = 0.0
        self.model.market_nominal_rate = None
        period = self.steps + 1
        self.model.liquidity.begin_period(period)
        self.model.liquidity.clear_market(period)
        self.model.current_shock_effects = self.model.shocks.effects(period)
        shock_effects = self.model.current_shock_effects

        # --- 1. Production & Wage Payments ---
        base_payroll_per_firm = 5.0 * shock_effects["demand_multiplier"]
        total_payroll = 0.0
        aggregate_output = 0.0

        for firm in self.firms:
            # Credit originated in earlier periods is spent gradually as working
            # capital. This gives financing a transparent, lagged real channel:
            # deposits fund additional wages, which produce additional output.
            expansion_payroll = 0.25 * firm.working_capital_budget
            target_payroll = base_payroll_per_firm + expansion_payroll

            # Pay wages to household
            wages = min(target_payroll, firm.current_balance)
            self.transfer_deposit(
                payer=firm,
                payee=self.model.household,
                amount=wages,
                event_type="wage",
                period=self.steps + 1,
            )
            expansion_spent = max(0.0, wages - base_payroll_per_firm)
            firm.working_capital_budget = max(
                0.0, firm.working_capital_budget - expansion_spent
            )

            # Simple production: Output = beta * wages (Beta = 1.2)
            firm.output = (
                wages
                * 1.2
                * firm.productivity
                * shock_effects["productivity_multiplier"]
            )
            aggregate_output += firm.output
            total_payroll += wages

        # --- 2. Production Strategy ---
        # Asynchronous Batching: Gather firm credit demands
        firm_tasks = [firm.strategize_credit_demand() for firm in self.firms]
        await asyncio.gather(*firm_tasks)

        # --- 3. Competitive Credit-Market Clearing ---
        bank_tasks = []
        pending_offers = []
        applications = {}
        decision_source = self.model.behavior_mode.value

        for firm in self.firms:
            demand = firm.current_demand
            if not demand:
                continue

            application_id = f"{self.model.run_id}-p{period}-{firm.unique_id}"
            applications[application_id] = (firm, demand)
            if demand.decision_status == "llm_failure":
                self.model.llm_failure_count += 1
            self.model.ledger.record_credit_application(
                application_id=application_id,
                run_id=self.model.run_id,
                period=period,
                firm_id=firm.unique_id,
                requested_principal=demand.loan_principal_requested,
                max_acceptable_rate=demand.max_acceptable_nominal_rate,
                decision_source=decision_source,
                decision_status=demand.decision_status,
                rationale=demand.chain_of_thought,
            )

            if demand and demand.loan_principal_requested > 0 and self.banks:
                # Every eligible bank can quote. Regulatory feasibility remains a
                # deterministic constraint inside `evaluate_loan`.
                for bank in self.banks:
                    offer_id = f"{application_id}-{bank.unique_id}"
                    bank_tasks.append(
                        bank.evaluate_loan(
                            firm_id=firm.unique_id,
                            principal=demand.loan_principal_requested,
                            max_rate=demand.max_acceptable_nominal_rate,
                        )
                    )
                    pending_offers.append(
                        (offer_id, application_id, firm, bank, demand)
                    )

        if bank_tasks:
            decisions = await asyncio.gather(*bank_tasks)
        else:
            decisions = []

        offers_by_application = {}
        for pending, decision in zip(pending_offers, decisions):
            offer_id, application_id, firm, bank, demand = pending
            if decision.decision_status == "llm_failure":
                self.model.llm_failure_count += 1
            borrower_leverage = (
                firm.current_debt / firm.equity if firm.equity > 0 else float("inf")
            )
            bank_customer_loans = sum(
                loan["remaining_principal"]
                for loan in self.model.active_loans
                if loan["bank_id"] == bank.unique_id
            )
            self.model.ledger.record_bank_offer(
                offer_id=offer_id,
                application_id=application_id,
                run_id=self.model.run_id,
                period=period,
                bank_id=bank.unique_id,
                approved=decision.approved,
                offered_nominal_rate=(
                    decision.offered_nominal_rate if decision.approved else None
                ),
                decision_source=decision_source,
                decision_status=decision.decision_status,
                rationale=decision.chain_of_thought,
                borrower_leverage=borrower_leverage,
                borrower_risk_profile=firm.risk_profile,
                bank_reserves=bank.current_balance,
                bank_equity=bank.equity,
                bank_deposit_liabilities=bank.current_debt,
                bank_customer_loans=bank_customer_loans,
                bank_expected_inflation=bank.exp_inflation,
            )
            offers_by_application.setdefault(application_id, []).append(
                (offer_id, bank, decision)
            )

        total_nominal_rate_volume = 0.0
        total_approved_principal = 0.0
        approved_loans_count = 0

        # Firms accept the cheapest compatible offer. A seeded random stream only
        # resolves exact price ties.
        for application_id, (firm, demand) in applications.items():
            compatible = [
                (offer_id, bank, decision)
                for offer_id, bank, decision in offers_by_application.get(
                    application_id, []
                )
                if decision.decision_status == "economic"
                and decision.approved
                and decision.offered_nominal_rate <= demand.max_acceptable_nominal_rate
            ]
            if not compatible:
                continue

            selected_offer = None
            remaining = list(compatible)
            while remaining and selected_offer is None:
                best_rate = min(
                    decision.offered_nominal_rate for _, _, decision in remaining
                )
                best_offers = [
                    offer
                    for offer in remaining
                    if abs(offer[2].offered_nominal_rate - best_rate) < 1e-12
                ]
                self.model.matching_random.shuffle(best_offers)
                for candidate in best_offers:
                    candidate_offer_id, candidate_bank, _ = candidate
                    feasible, _ = candidate_bank.regulatory_feasibility(
                        firm.unique_id, demand.loan_principal_requested
                    )
                    if feasible:
                        selected_offer = candidate
                        break
                    self.model.ledger.mark_offer_capacity_constrained(
                        candidate_offer_id
                    )
                remaining = [offer for offer in remaining if offer not in best_offers]

            if selected_offer is None:
                continue

            offer_id, bank, decision = selected_offer
            self.model.ledger.accept_bank_offer(offer_id)
            principal = demand.loan_principal_requested

            # Symmetrical balance sheet expansion (loan creation)
            firm.current_debt += principal

            # Register the loan in the model's active loan book
            loan_id = (
                f"{self.model.run_id}-loan-p{period}-"
                f"{firm.unique_id}-{bank.unique_id}"
            )
            loan = {
                "loan_id": loan_id,
                "application_id": application_id,
                "offer_id": offer_id,
                "borrower_id": firm.unique_id,
                "bank_id": bank.unique_id,
                "principal": principal,
                "remaining_principal": principal,
                "interest_rate": decision.offered_nominal_rate,
                "duration": 5,
                "age": 0,
            }
            self.model.active_loans.append(loan)
            self.model.ledger.record_loan_contract(
                loan_id=loan_id,
                run_id=self.model.run_id,
                application_id=application_id,
                offer_id=offer_id,
                borrower_id=firm.unique_id,
                bank_id=bank.unique_id,
                principal=principal,
                nominal_rate=decision.offered_nominal_rate,
                duration=loan["duration"],
                originated_period=period,
            )
            self.create_loan_deposit(
                firm=firm,
                lender=bank,
                amount=principal,
                period=period,
                loan_id=loan_id,
            )
            firm.working_capital_budget += principal

            total_nominal_rate_volume += decision.offered_nominal_rate * principal
            total_approved_principal += principal
            approved_loans_count += 1
            self.model.new_credit_in_step += principal

        # --- 4. Goods Market Clearing (Consumption) ---
        # Households consume a fraction (80%) of their accumulated wealth
        consumption_propensity = min(0.95, 0.8 * shock_effects["demand_multiplier"])
        total_consumption = (
            self.model.household.current_balance * consumption_propensity
        )

        # Consumption revenue is distributed equally across firms
        if self.firms:
            revenue_per_firm = total_consumption / len(self.firms)
            for firm in self.firms:
                self.transfer_deposit(
                    payer=self.model.household,
                    payee=firm,
                    amount=revenue_per_firm,
                    event_type="consumption",
                    period=period,
                )

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
            remaining_before = loan["remaining_principal"]

            if firm.current_balance >= total_due:
                # Fully service debt
                self.settle_loan_payment(
                    firm=firm,
                    lender=bank,
                    amount=total_due,
                    period=period,
                    loan_id=loan["loan_id"],
                    event_type="debt_service",
                )
                firm.current_debt -= amortization

                loan["remaining_principal"] -= amortization
                loan["age"] += 1
                self.model.ledger.record_loan_event(
                    loan_event_id=f"{loan['loan_id']}-p{period}",
                    run_id=self.model.run_id,
                    period=period,
                    loan_id=loan["loan_id"],
                    event_type="payment",
                    scheduled_amount=total_due,
                    principal_paid=amortization,
                    interest_paid=interest,
                    principal_written_off=0.0,
                    remaining_principal_before=remaining_before,
                    remaining_principal_after=loan["remaining_principal"],
                )

                if loan["remaining_principal"] > 0 and loan["age"] < loan["duration"]:
                    still_active_loans.append(loan)
                else:
                    self.model.ledger.terminate_loan_contract(
                        loan["loan_id"], period, "repaid"
                    )
            else:
                # DEFAULT! Firm cannot afford total debt service.
                self.model.defaults_in_step += 1
                # Wipes out all remaining deposits to service what is possible
                paid = firm.current_balance

                interest_paid = min(interest, paid)
                amort_paid = max(0.0, paid - interest_paid)

                # Firm updates
                self.settle_loan_payment(
                    firm=firm,
                    lender=bank,
                    amount=paid,
                    period=period,
                    loan_id=loan["loan_id"],
                    event_type="default_recovery",
                )
                firm.current_debt -= amort_paid

                # Write off the rest of the loan
                write_off_principal = loan["remaining_principal"] - amort_paid
                self.model.write_offs_in_step += write_off_principal
                firm.current_debt -= write_off_principal  # Debt canceled for firm

                # Bank takes the hit to equity (losses written off, reducing outstanding loans asset)
                loan["remaining_principal"] = 0.0
                self.model.ledger.record_loan_event(
                    loan_event_id=f"{loan['loan_id']}-p{period}",
                    run_id=self.model.run_id,
                    period=period,
                    loan_id=loan["loan_id"],
                    event_type="default",
                    scheduled_amount=total_due,
                    principal_paid=amort_paid,
                    interest_paid=interest_paid,
                    principal_written_off=write_off_principal,
                    remaining_principal_before=remaining_before,
                    remaining_principal_after=0.0,
                )
                self.model.ledger.terminate_loan_contract(
                    loan["loan_id"], period, "default"
                )

        self.model.active_loans = still_active_loans
        self.model.aggregate_output = aggregate_output
        self.model.total_consumption = total_consumption

        # --- 6. Macro-Accounting & Synchronization ---
        self.model.liquidity.clear_market(period, reset_metrics=False)
        for bank in self.banks:
            loans_outstanding = sum(
                loan["remaining_principal"]
                for loan in self.model.active_loans
                if loan["bank_id"] == bank.unique_id
            )
            bank.equity = (
                bank.current_balance
                + bank.other_assets
                + loans_outstanding
                + bank.interbank_assets
                - bank.current_debt
                - bank.interbank_liabilities
                - bank.emergency_borrowing
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
                loan["remaining_principal"]
                for loan in self.model.active_loans
                if loan["bank_id"] == bank.unique_id
            )
            bank_total_assets = (
                bank.current_balance
                + bank.other_assets
                + loans_outstanding
                + bank.interbank_assets
            )
            bank_total_liabilities = (
                bank.current_debt
                + bank.interbank_liabilities
                + bank.emergency_borrowing
            )
            ledger.update_balance_sheet(
                bank.unique_id,
                "Bank",
                bank_total_assets,
                bank_total_liabilities,
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
        self.model.validate_monetary_system()

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
            avg_nominal_rate = total_nominal_rate_volume / total_approved_principal
            self.model.market_nominal_rate = avg_nominal_rate
        else:
            avg_nominal_rate = 0.0
        self.model.nominal_rate = avg_nominal_rate

        # Deterministic Real Interest Rate
        self.model.real_interest_rate = (
            self.model.nominal_rate - self.model.realized_inflation
        )
        self.model.three_step_yield_trend = self.model.real_interest_rate

        # --- 7. Adaptive Expectations Update ---
        lambda_rate = 0.3
        realized_inf = self.model.realized_inflation
        realized_nom = self.model.nominal_rate

        self.model.exp_inflation += lambda_rate * (
            realized_inf - self.model.exp_inflation
        )
        self.model.exp_nominal_rate += lambda_rate * (
            realized_nom - self.model.exp_nominal_rate
        )

        for f in self.firms:
            f.exp_inflation += lambda_rate * (realized_inf - f.exp_inflation)
            f.exp_nominal_rate += lambda_rate * (realized_nom - f.exp_nominal_rate)

        for b in self.banks:
            b.exp_inflation += lambda_rate * (realized_inf - b.exp_inflation)
            b.exp_nominal_rate += lambda_rate * (realized_nom - b.exp_nominal_rate)
