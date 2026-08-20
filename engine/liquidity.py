from engine.experiment import RateRegime


class LiquidityManager:
    """Clears overnight reserve imbalances and central liquidity."""

    def __init__(self, model):
        self.model = model
        self.interbank_rate = None
        self.interbank_volume = 0.0
        self.emergency_volume = 0.0
        self.unresolved_shortfall = 0.0
        self.sequence = 0

    def _bank(self, bank_id):
        return next(
            (bank for bank in self.model.schedule.banks if bank.unique_id == bank_id),
            None,
        )

    def _recompute_equity(self, bank):
        customer_loans = sum(
            loan["remaining_principal"]
            for loan in self.model.active_loans
            if loan["bank_id"] == bank.unique_id
        )
        assets = (
            bank.current_balance
            + bank.other_assets
            + customer_loans
            + bank.interbank_assets
        )
        liabilities = (
            bank.current_debt + bank.interbank_liabilities + bank.emergency_borrowing
        )
        bank.equity = assets - liabilities

    def begin_period(self, period):
        """Settle one-period liquidity loans before new economic activity."""
        remaining_interbank = []
        for loan in self.model.active_interbank_loans:
            if loan["due_period"] > period:
                remaining_interbank.append(loan)
                continue

            lender = self._bank(loan["lender_id"])
            borrower = self._bank(loan["borrower_id"])
            interest = loan["principal"] * loan["interest_rate"]
            total_due = loan["principal"] + interest

            borrower.current_balance -= total_due
            lender.current_balance += total_due
            borrower.interbank_liabilities -= loan["principal"]
            lender.interbank_assets -= loan["principal"]
            self.model.ledger.settle_liquidity_loan(
                loan["liquidity_loan_id"], period, interest
            )

        self.model.active_interbank_loans = remaining_interbank

        remaining_emergency = []
        for loan in self.model.active_emergency_loans:
            if loan["due_period"] > period:
                remaining_emergency.append(loan)
                continue

            borrower = self._bank(loan["borrower_id"])
            interest = loan["principal"] * loan["interest_rate"]
            total_due = loan["principal"] + interest

            borrower.current_balance -= total_due
            borrower.emergency_borrowing -= loan["principal"]
            self.model.base_money_issued -= total_due
            self.model.ledger.settle_liquidity_loan(
                loan["liquidity_loan_id"], period, interest
            )

        self.model.active_emergency_loans = remaining_emergency
        for bank in self.model.schedule.banks:
            self._recompute_equity(bank)

    def _market_rate(self, total_shortfall, total_surplus):
        if self.model.rate_regime == RateRegime.ADMINISTERED:
            return max(0.0, self.model.policy_rate)

        banks = self.model.schedule.banks
        expected_inflation = (
            sum(bank.exp_inflation for bank in banks) / len(banks) if banks else 0.0
        )
        expected_inflation += self.model.current_shock_effects[
            "expected_inflation_shift"
        ]
        scarcity = total_shortfall / max(total_surplus, 1e-9)
        return min(
            1.0,
            max(0.001, 0.01 + expected_inflation + 0.02 * scarcity),
        )

    def _new_liquidity_loan_id(self, period, facility_type):
        self.sequence += 1
        return f"{self.model.run_id}-p{period}-{facility_type}-{self.sequence}"

    def clear_market(self, period, reset_metrics=True):
        banks = self.model.schedule.banks
        if reset_metrics:
            self.interbank_rate = None
            self.interbank_volume = 0.0
            self.emergency_volume = 0.0
            self.unresolved_shortfall = 0.0

        states = {}
        for bank in banks:
            required = self.model.reserve_requirement * bank.current_debt
            states[bank.unique_id] = {
                "reserves_before": bank.current_balance,
                "required": required,
                "borrowed": 0.0,
                "lent": 0.0,
                "emergency": 0.0,
            }

        shortfalls = {
            bank.unique_id: max(
                0.0,
                states[bank.unique_id]["required"] - bank.current_balance,
            )
            for bank in banks
        }
        surpluses = {
            bank.unique_id: max(
                0.0,
                bank.current_balance - states[bank.unique_id]["required"],
            )
            for bank in banks
        }
        total_shortfall = sum(shortfalls.values())
        total_surplus = sum(surpluses.values())

        if total_shortfall > 1e-9 and total_surplus > 1e-9:
            self.interbank_rate = self._market_rate(total_shortfall, total_surplus)

            borrowers = sorted(
                banks,
                key=lambda bank: shortfalls[bank.unique_id],
                reverse=True,
            )
            lenders = sorted(
                banks,
                key=lambda bank: surpluses[bank.unique_id],
                reverse=True,
            )
            for borrower in borrowers:
                needed = shortfalls[borrower.unique_id]
                if needed <= 1e-9:
                    continue
                for lender in lenders:
                    available = surpluses[lender.unique_id]
                    if lender is borrower or available <= 1e-9:
                        continue
                    principal = min(needed, available)
                    lender.current_balance -= principal
                    borrower.current_balance += principal
                    lender.interbank_assets += principal
                    borrower.interbank_liabilities += principal

                    states[lender.unique_id]["lent"] += principal
                    states[borrower.unique_id]["borrowed"] += principal
                    surpluses[lender.unique_id] -= principal
                    needed -= principal
                    self.interbank_volume += principal

                    loan_id = self._new_liquidity_loan_id(period, "interbank")
                    loan = {
                        "liquidity_loan_id": loan_id,
                        "lender_id": lender.unique_id,
                        "borrower_id": borrower.unique_id,
                        "principal": principal,
                        "interest_rate": self.interbank_rate,
                        "originated_period": period,
                        "due_period": period + 1,
                    }
                    self.model.active_interbank_loans.append(loan)
                    self.model.ledger.record_liquidity_loan(
                        liquidity_loan_id=loan_id,
                        run_id=self.model.run_id,
                        facility_type="interbank",
                        lender_id=lender.unique_id,
                        borrower_id=borrower.unique_id,
                        principal=principal,
                        interest_rate=self.interbank_rate,
                        originated_period=period,
                        due_period=period + 1,
                    )
                    if needed <= 1e-9:
                        break
                shortfalls[borrower.unique_id] = needed

        reference_rate = (
            self.interbank_rate
            if self.interbank_rate is not None
            else (
                self.model.policy_rate
                if self.model.rate_regime == RateRegime.ADMINISTERED
                else 0.01 + self.model.exp_inflation
            )
        )

        for bank in banks:
            residual = max(
                0.0,
                states[bank.unique_id]["required"] - bank.current_balance,
            )
            if residual > 1e-9 and self.model.lender_of_last_resort in {
                "penalty",
                "limited",
            }:
                if self.model.lender_of_last_resort == "limited":
                    remaining_limit = max(
                        0.0,
                        max(bank.equity, 0.0)
                        * self.model.emergency_borrowing_limit_ratio
                        - bank.emergency_borrowing,
                    )
                else:
                    remaining_limit = residual
                principal = min(residual, remaining_limit)

                if principal > 1e-9:
                    emergency_rate = (
                        reference_rate + self.model.emergency_penalty_spread
                    )
                    bank.current_balance += principal
                    bank.emergency_borrowing += principal
                    self.model.base_money_issued += principal
                    states[bank.unique_id]["emergency"] += principal
                    self.emergency_volume += principal

                    loan_id = self._new_liquidity_loan_id(period, "emergency")
                    loan = {
                        "liquidity_loan_id": loan_id,
                        "lender_id": "central_bank",
                        "borrower_id": bank.unique_id,
                        "principal": principal,
                        "interest_rate": emergency_rate,
                        "originated_period": period,
                        "due_period": period + 1,
                    }
                    self.model.active_emergency_loans.append(loan)
                    self.model.ledger.record_liquidity_loan(
                        liquidity_loan_id=loan_id,
                        run_id=self.model.run_id,
                        facility_type="emergency",
                        lender_id="central_bank",
                        borrower_id=bank.unique_id,
                        principal=principal,
                        interest_rate=emergency_rate,
                        originated_period=period,
                        due_period=period + 1,
                    )

            unresolved = max(
                0.0,
                states[bank.unique_id]["required"] - bank.current_balance,
            )
            bank.liquidity_failed = unresolved > 1e-9
            self.unresolved_shortfall += unresolved
            self._recompute_equity(bank)
            self.model.ledger.record_bank_liquidity(
                run_id=self.model.run_id,
                period=period,
                bank_id=bank.unique_id,
                reserves_before=states[bank.unique_id]["reserves_before"],
                required_reserves=states[bank.unique_id]["required"],
                interbank_borrowed=states[bank.unique_id]["borrowed"],
                interbank_lent=states[bank.unique_id]["lent"],
                emergency_borrowed=states[bank.unique_id]["emergency"],
                reserves_after=bank.current_balance,
                unresolved_shortfall=unresolved,
                liquidity_failed=bank.liquidity_failed,
            )
