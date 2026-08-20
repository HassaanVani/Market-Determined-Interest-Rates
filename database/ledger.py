import sqlite3
import math
import json


class BalanceSheetMismatch(Exception):
    pass


class Ledger:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_sheets (
                agent_id TEXT PRIMARY KEY,
                agent_type TEXT,
                assets REAL DEFAULT 0.0,
                liabilities REAL DEFAULT 0.0,
                equity REAL DEFAULT 0.0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiment_runs (
                run_id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                config_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                failure_reason TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS period_macro (
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                base_money REAL NOT NULL,
                deposit_money REAL NOT NULL,
                broad_money REAL NOT NULL,
                new_credit REAL NOT NULL,
                outstanding_credit REAL NOT NULL,
                market_nominal_rate REAL,
                outstanding_book_rate REAL,
                realized_inflation REAL NOT NULL,
                defaults INTEGER NOT NULL,
                write_offs REAL NOT NULL,
                interbank_rate REAL,
                interbank_volume REAL NOT NULL DEFAULT 0.0,
                emergency_borrowing REAL NOT NULL DEFAULT 0.0,
                liquidity_shortfall REAL NOT NULL DEFAULT 0.0,
                aggregate_output REAL NOT NULL DEFAULT 0.0,
                total_consumption REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (run_id, period),
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_applications (
                application_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                firm_id TEXT NOT NULL,
                requested_principal REAL NOT NULL,
                max_acceptable_rate REAL NOT NULL,
                decision_source TEXT NOT NULL,
                decision_status TEXT NOT NULL,
                rationale TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_offers (
                offer_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                bank_id TEXT NOT NULL,
                approved INTEGER NOT NULL,
                offered_nominal_rate REAL,
                decision_source TEXT NOT NULL,
                decision_status TEXT NOT NULL,
                rationale TEXT NOT NULL,
                accepted INTEGER NOT NULL DEFAULT 0,
                clearing_status TEXT NOT NULL DEFAULT 'not_selected',
                borrower_leverage REAL NOT NULL,
                borrower_risk_profile TEXT NOT NULL,
                bank_reserves REAL NOT NULL,
                bank_equity REAL NOT NULL,
                bank_deposit_liabilities REAL NOT NULL,
                bank_customer_loans REAL NOT NULL,
                bank_expected_inflation REAL NOT NULL,
                FOREIGN KEY (application_id)
                    REFERENCES credit_applications(application_id),
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settlement_events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payer_id TEXT NOT NULL,
                payee_id TEXT NOT NULL,
                payer_bank_id TEXT NOT NULL,
                payee_bank_id TEXT NOT NULL,
                amount REAL NOT NULL,
                reserve_transfer REAL NOT NULL,
                loan_id TEXT,
                status TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liquidity_loans (
                liquidity_loan_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                facility_type TEXT NOT NULL,
                lender_id TEXT NOT NULL,
                borrower_id TEXT NOT NULL,
                principal REAL NOT NULL,
                interest_rate REAL NOT NULL,
                originated_period INTEGER NOT NULL,
                due_period INTEGER NOT NULL,
                repaid_period INTEGER,
                interest_paid REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_liquidity (
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                bank_id TEXT NOT NULL,
                reserves_before REAL NOT NULL,
                required_reserves REAL NOT NULL,
                interbank_borrowed REAL NOT NULL,
                interbank_lent REAL NOT NULL,
                emergency_borrowed REAL NOT NULL,
                reserves_after REAL NOT NULL,
                unresolved_shortfall REAL NOT NULL,
                liquidity_failed INTEGER NOT NULL,
                PRIMARY KEY (run_id, period, bank_id),
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shocks (
                shock_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                shock_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                start_period INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                magnitude REAL NOT NULL,
                PRIMARY KEY (run_id, shock_id),
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_states (
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                deposit_bank_id TEXT,
                deposits REAL NOT NULL,
                debt REAL NOT NULL,
                assets REAL NOT NULL,
                liabilities REAL NOT NULL,
                equity REAL NOT NULL,
                expected_inflation REAL,
                expected_nominal_rate REAL,
                output REAL,
                working_capital_budget REAL,
                reserves REAL,
                deposit_liabilities REAL,
                interbank_assets REAL,
                interbank_liabilities REAL,
                emergency_borrowing REAL,
                liquidity_failed INTEGER,
                PRIMARY KEY (run_id, period, agent_id),
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loan_contracts (
                loan_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                offer_id TEXT NOT NULL,
                borrower_id TEXT NOT NULL,
                bank_id TEXT NOT NULL,
                principal REAL NOT NULL,
                nominal_rate REAL NOT NULL,
                duration INTEGER NOT NULL,
                originated_period INTEGER NOT NULL,
                status TEXT NOT NULL,
                terminated_period INTEGER,
                termination_reason TEXT,
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loan_events (
                loan_event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                loan_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                scheduled_amount REAL NOT NULL,
                principal_paid REAL NOT NULL,
                interest_paid REAL NOT NULL,
                principal_written_off REAL NOT NULL,
                remaining_principal_before REAL NOT NULL,
                remaining_principal_after REAL NOT NULL,
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id),
                FOREIGN KEY (loan_id) REFERENCES loan_contracts(loan_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                call_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_id TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                temperature REAL NOT NULL,
                attempt INTEGER NOT NULL,
                latency_seconds REAL NOT NULL,
                status TEXT NOT NULL,
                error_type TEXT,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id)
            )
        """)
        self.conn.commit()

    def register_run(self, run_id, config):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO experiment_runs (
                run_id, config_json, config_fingerprint, status, failure_reason
            ) VALUES (?, ?, ?, 'running', NULL)
            """,
            (run_id, config.canonical_json(), config.fingerprint()),
        )
        self.conn.commit()

    def update_run_status(self, run_id, status, failure_reason=None):
        if status not in {"running", "completed", "failed", "invalid"}:
            raise ValueError(f"Unsupported run status: {status}")
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE experiment_runs
            SET status = ?, failure_reason = ?
            WHERE run_id = ?
            """,
            (status, failure_reason, run_id),
        )
        self.conn.commit()

    def record_period_macro(self, run_id, period, snapshot):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO period_macro (
                run_id, period, base_money, deposit_money, broad_money,
                new_credit, outstanding_credit, market_nominal_rate,
                outstanding_book_rate, realized_inflation, defaults, write_offs
                , interbank_rate, interbank_volume, emergency_borrowing,
                liquidity_shortfall, aggregate_output, total_consumption
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, period) DO UPDATE SET
                base_money=excluded.base_money,
                deposit_money=excluded.deposit_money,
                broad_money=excluded.broad_money,
                new_credit=excluded.new_credit,
                outstanding_credit=excluded.outstanding_credit,
                market_nominal_rate=excluded.market_nominal_rate,
                outstanding_book_rate=excluded.outstanding_book_rate,
                realized_inflation=excluded.realized_inflation,
                defaults=excluded.defaults,
                write_offs=excluded.write_offs,
                interbank_rate=excluded.interbank_rate,
                interbank_volume=excluded.interbank_volume,
                emergency_borrowing=excluded.emergency_borrowing,
                liquidity_shortfall=excluded.liquidity_shortfall,
                aggregate_output=excluded.aggregate_output,
                total_consumption=excluded.total_consumption
            """,
            (
                run_id,
                int(period),
                float(snapshot["base_money"]),
                float(snapshot["deposit_money"]),
                float(snapshot["broad_money"]),
                float(snapshot["new_credit"]),
                float(snapshot["outstanding_credit"]),
                snapshot["market_nominal_rate"],
                snapshot["outstanding_book_rate"],
                float(snapshot["realized_inflation"]),
                int(snapshot["defaults"]),
                float(snapshot["write_offs"]),
                snapshot["interbank_rate"],
                float(snapshot["interbank_volume"]),
                float(snapshot["emergency_borrowing"]),
                float(snapshot["liquidity_shortfall"]),
                float(snapshot["aggregate_output"]),
                float(snapshot["total_consumption"]),
            ),
        )
        self.conn.commit()

    def get_run(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM experiment_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["config"] = json.loads(result.pop("config_json"))
        return result

    def get_period_macro(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM period_macro WHERE run_id = ? ORDER BY period", (run_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_credit_application(
        self,
        application_id,
        run_id,
        period,
        firm_id,
        requested_principal,
        max_acceptable_rate,
        decision_source,
        decision_status,
        rationale,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO credit_applications (
                application_id, run_id, period, firm_id, requested_principal,
                max_acceptable_rate, decision_source, decision_status, rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                run_id,
                int(period),
                str(firm_id),
                float(requested_principal),
                float(max_acceptable_rate),
                decision_source,
                decision_status,
                rationale,
            ),
        )
        self.conn.commit()

    def record_bank_offer(
        self,
        offer_id,
        application_id,
        run_id,
        period,
        bank_id,
        approved,
        offered_nominal_rate,
        decision_source,
        decision_status,
        rationale,
        borrower_leverage,
        borrower_risk_profile,
        bank_reserves,
        bank_equity,
        bank_deposit_liabilities,
        bank_customer_loans,
        bank_expected_inflation,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO bank_offers (
                offer_id, application_id, run_id, period, bank_id, approved,
                offered_nominal_rate, decision_source, decision_status,
                rationale, accepted, clearing_status, borrower_leverage,
                borrower_risk_profile, bank_reserves, bank_equity,
                bank_deposit_liabilities, bank_customer_loans,
                bank_expected_inflation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'not_selected',
                      ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer_id,
                application_id,
                run_id,
                int(period),
                str(bank_id),
                int(bool(approved)),
                (
                    float(offered_nominal_rate)
                    if offered_nominal_rate is not None
                    else None
                ),
                decision_source,
                decision_status,
                rationale,
                float(borrower_leverage),
                borrower_risk_profile,
                float(bank_reserves),
                float(bank_equity),
                float(bank_deposit_liabilities),
                float(bank_customer_loans),
                float(bank_expected_inflation),
            ),
        )
        self.conn.commit()

    def accept_bank_offer(self, offer_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE bank_offers
            SET accepted = 1, clearing_status = 'accepted'
            WHERE offer_id = ?
            """,
            (offer_id,),
        )
        self.conn.commit()

    def mark_offer_capacity_constrained(self, offer_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE bank_offers
            SET clearing_status = 'capacity_constrained'
            WHERE offer_id = ?
            """,
            (offer_id,),
        )
        self.conn.commit()

    def get_credit_applications(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM credit_applications
            WHERE run_id = ?
            ORDER BY period, application_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_bank_offers(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM bank_offers
            WHERE run_id = ?
            ORDER BY period, application_id, offer_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_settlement_event(
        self,
        event_id,
        run_id,
        period,
        event_type,
        payer_id,
        payee_id,
        payer_bank_id,
        payee_bank_id,
        amount,
        reserve_transfer,
        loan_id=None,
        status="settled",
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO settlement_events (
                event_id, run_id, period, event_type, payer_id, payee_id,
                payer_bank_id, payee_bank_id, amount, reserve_transfer,
                loan_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                run_id,
                int(period),
                event_type,
                str(payer_id),
                str(payee_id),
                str(payer_bank_id),
                str(payee_bank_id),
                float(amount),
                float(reserve_transfer),
                loan_id,
                status,
            ),
        )
        self.conn.commit()

    def get_settlement_events(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM settlement_events
            WHERE run_id = ?
            ORDER BY period, event_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_liquidity_loan(
        self,
        liquidity_loan_id,
        run_id,
        facility_type,
        lender_id,
        borrower_id,
        principal,
        interest_rate,
        originated_period,
        due_period,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO liquidity_loans (
                liquidity_loan_id, run_id, facility_type, lender_id,
                borrower_id, principal, interest_rate, originated_period,
                due_period, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                liquidity_loan_id,
                run_id,
                facility_type,
                lender_id,
                borrower_id,
                float(principal),
                float(interest_rate),
                int(originated_period),
                int(due_period),
            ),
        )
        self.conn.commit()

    def settle_liquidity_loan(self, liquidity_loan_id, repaid_period, interest_paid):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE liquidity_loans
            SET status = 'repaid', repaid_period = ?, interest_paid = ?
            WHERE liquidity_loan_id = ?
            """,
            (int(repaid_period), float(interest_paid), liquidity_loan_id),
        )
        self.conn.commit()

    def record_bank_liquidity(
        self,
        run_id,
        period,
        bank_id,
        reserves_before,
        required_reserves,
        interbank_borrowed,
        interbank_lent,
        emergency_borrowed,
        reserves_after,
        unresolved_shortfall,
        liquidity_failed,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO bank_liquidity (
                run_id, period, bank_id, reserves_before, required_reserves,
                interbank_borrowed, interbank_lent, emergency_borrowed,
                reserves_after, unresolved_shortfall, liquidity_failed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, period, bank_id) DO UPDATE SET
                reserves_before=excluded.reserves_before,
                required_reserves=excluded.required_reserves,
                interbank_borrowed=excluded.interbank_borrowed,
                interbank_lent=excluded.interbank_lent,
                emergency_borrowed=excluded.emergency_borrowed,
                reserves_after=excluded.reserves_after,
                unresolved_shortfall=excluded.unresolved_shortfall,
                liquidity_failed=excluded.liquidity_failed
            """,
            (
                run_id,
                int(period),
                bank_id,
                float(reserves_before),
                float(required_reserves),
                float(interbank_borrowed),
                float(interbank_lent),
                float(emergency_borrowed),
                float(reserves_after),
                float(unresolved_shortfall),
                int(bool(liquidity_failed)),
            ),
        )
        self.conn.commit()

    def get_liquidity_loans(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM liquidity_loans
            WHERE run_id = ?
            ORDER BY originated_period, liquidity_loan_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_bank_liquidity(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM bank_liquidity
            WHERE run_id = ?
            ORDER BY period, bank_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_shock(self, run_id, shock):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO shocks (
                shock_id, run_id, shock_type, target_id, start_period,
                duration, magnitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shock.shock_id,
                run_id,
                shock.shock_type,
                shock.target_id,
                int(shock.start_period),
                int(shock.duration),
                float(shock.magnitude),
            ),
        )
        self.conn.commit()

    def get_shocks(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM shocks
            WHERE run_id = ?
            ORDER BY start_period, shock_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_agent_state(self, values):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_states (
                run_id, period, agent_id, agent_type, deposit_bank_id,
                deposits, debt, assets, liabilities, equity,
                expected_inflation, expected_nominal_rate, output,
                working_capital_budget, reserves,
                deposit_liabilities, interbank_assets, interbank_liabilities,
                emergency_borrowing, liquidity_failed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, period, agent_id) DO UPDATE SET
                deposits=excluded.deposits,
                debt=excluded.debt,
                assets=excluded.assets,
                liabilities=excluded.liabilities,
                equity=excluded.equity,
                expected_inflation=excluded.expected_inflation,
                expected_nominal_rate=excluded.expected_nominal_rate,
                output=excluded.output,
                working_capital_budget=excluded.working_capital_budget,
                reserves=excluded.reserves,
                deposit_liabilities=excluded.deposit_liabilities,
                interbank_assets=excluded.interbank_assets,
                interbank_liabilities=excluded.interbank_liabilities,
                emergency_borrowing=excluded.emergency_borrowing,
                liquidity_failed=excluded.liquidity_failed
            """,
            values,
        )
        self.conn.commit()

    def get_agent_states(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM agent_states
            WHERE run_id = ?
            ORDER BY period, agent_type, agent_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_loan_contract(
        self,
        loan_id,
        run_id,
        application_id,
        offer_id,
        borrower_id,
        bank_id,
        principal,
        nominal_rate,
        duration,
        originated_period,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO loan_contracts (
                loan_id, run_id, application_id, offer_id, borrower_id,
                bank_id, principal, nominal_rate, duration,
                originated_period, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                loan_id,
                run_id,
                application_id,
                offer_id,
                borrower_id,
                bank_id,
                float(principal),
                float(nominal_rate),
                int(duration),
                int(originated_period),
            ),
        )
        self.conn.commit()

    def terminate_loan_contract(self, loan_id, period, reason):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE loan_contracts
            SET status = ?, terminated_period = ?, termination_reason = ?
            WHERE loan_id = ?
            """,
            (reason, int(period), reason, loan_id),
        )
        self.conn.commit()

    def record_loan_event(
        self,
        loan_event_id,
        run_id,
        period,
        loan_id,
        event_type,
        scheduled_amount,
        principal_paid,
        interest_paid,
        principal_written_off,
        remaining_principal_before,
        remaining_principal_after,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO loan_events (
                loan_event_id, run_id, period, loan_id, event_type,
                scheduled_amount, principal_paid, interest_paid,
                principal_written_off, remaining_principal_before,
                remaining_principal_after
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                loan_event_id,
                run_id,
                int(period),
                loan_id,
                event_type,
                float(scheduled_amount),
                float(principal_paid),
                float(interest_paid),
                float(principal_written_off),
                float(remaining_principal_before),
                float(remaining_principal_after),
            ),
        )
        self.conn.commit()

    def get_loan_contracts(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM loan_contracts
            WHERE run_id = ?
            ORDER BY originated_period, loan_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_loan_events(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM loan_events
            WHERE run_id = ?
            ORDER BY period, loan_event_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_llm_call(
        self,
        call_id,
        run_id,
        period,
        agent_id,
        task_type,
        provider,
        model_id,
        prompt_version,
        prompt_hash,
        temperature,
        attempt,
        latency_seconds,
        status,
        error_type=None,
        error_message=None,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO llm_calls (
                call_id, run_id, period, agent_id, task_type, provider,
                model_id, prompt_version, prompt_hash, temperature, attempt,
                latency_seconds, status, error_type, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                run_id,
                int(period),
                agent_id,
                task_type,
                provider,
                model_id,
                prompt_version,
                prompt_hash,
                float(temperature),
                int(attempt),
                float(latency_seconds),
                status,
                error_type,
                error_message,
            ),
        )
        self.conn.commit()

    def get_llm_calls(self, run_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM llm_calls
            WHERE run_id = ?
            ORDER BY period, agent_id, task_type, attempt
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_balance_sheet(
        self,
        agent_id: str,
        agent_type: str,
        assets: float,
        liabilities: float,
        equity: float,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO balance_sheets (agent_id, agent_type, assets, liabilities, equity)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                assets=excluded.assets,
                liabilities=excluded.liabilities,
                equity=excluded.equity
        """,
            (
                str(agent_id),
                agent_type,
                float(assets),
                float(liabilities),
                float(equity),
            ),
        )
        self.conn.commit()

    def get_balance_sheet(self, agent_id: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM balance_sheets WHERE agent_id = ?", (str(agent_id),)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            "agent_id": str(agent_id),
            "assets": 0.0,
            "liabilities": 0.0,
            "equity": 0.0,
        }

    def validate_balance_sheets(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM balance_sheets")
        rows = cursor.fetchall()

        for row in rows:
            assets = float(row["assets"])
            liabilities = float(row["liabilities"])
            equity = float(row["equity"])

            # Use math.isclose to handle floating point inaccuracies
            if not math.isclose(assets, liabilities + equity, abs_tol=1e-5):
                raise BalanceSheetMismatch(
                    f"Agent {row['agent_id']} ({row['agent_type']}) balance sheet mismatch: "
                    f"Assets ({assets}) != Liabilities ({liabilities}) + Equity ({equity})"
                )

        # Also validate global macro constraint if necessary, but checking all agents is sufficient
        # as long as each agent obeys it, the system obeys it.
        return True

    def validate_monetary_totals(
        self,
        deposit_assets,
        deposit_liabilities,
        total_reserves,
        expected_base_money,
    ):
        if not math.isclose(deposit_assets, deposit_liabilities, abs_tol=1e-5):
            raise BalanceSheetMismatch(
                "System deposit mismatch: "
                f"agent deposits ({deposit_assets}) != "
                f"bank deposit liabilities ({deposit_liabilities})"
            )
        if not math.isclose(total_reserves, expected_base_money, abs_tol=1e-5):
            raise BalanceSheetMismatch(
                "Base-money mismatch: "
                f"bank reserves ({total_reserves}) != "
                f"issued base money ({expected_base_money})"
            )
        return True

    def validate_credit_totals(self, borrower_debt, outstanding_loans):
        if not math.isclose(borrower_debt, outstanding_loans, abs_tol=1e-5):
            raise BalanceSheetMismatch(
                "System credit mismatch: "
                f"borrower debt ({borrower_debt}) != "
                f"outstanding bank loans ({outstanding_loans})"
            )
        return True

    def validate_liquidity_totals(
        self,
        interbank_assets,
        interbank_liabilities,
        emergency_liabilities,
        emergency_loans,
    ):
        if not math.isclose(interbank_assets, interbank_liabilities, abs_tol=1e-5):
            raise BalanceSheetMismatch(
                "Interbank mismatch: "
                f"assets ({interbank_assets}) != "
                f"liabilities ({interbank_liabilities})"
            )
        if not math.isclose(emergency_liabilities, emergency_loans, abs_tol=1e-5):
            raise BalanceSheetMismatch(
                "Emergency-liquidity mismatch: "
                f"bank liabilities ({emergency_liabilities}) != "
                f"central liquidity loans ({emergency_loans})"
            )
        return True
