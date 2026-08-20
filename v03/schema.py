from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "0.3"

DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_metadata (
    schema_version TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parameter_sets (
    parameter_set_id TEXT PRIMARY KEY,
    canonical_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS calibration_targets (
    calibration_id TEXT NOT NULL,
    moment_name TEXT NOT NULL,
    target_value REAL NOT NULL,
    bootstrap_se REAL,
    lower_95 REAL,
    upper_95 REAL,
    weight_type TEXT NOT NULL,
    PRIMARY KEY (calibration_id, moment_name, weight_type)
);
CREATE TABLE IF NOT EXISTS experiment_runs (
    run_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL CHECK(specification_id = 'v0.3'),
    calibration_id TEXT NOT NULL,
    parameter_set_id TEXT NOT NULL REFERENCES parameter_sets(parameter_set_id),
    scenario_id TEXT NOT NULL,
    rate_regime TEXT NOT NULL CHECK(rate_regime IN ('administered','market')),
    behavior_mode TEXT NOT NULL CHECK(behavior_mode IN ('rule','llm')),
    replication INTEGER NOT NULL,
    seed_namespace TEXT NOT NULL,
    environment_seed INTEGER NOT NULL,
    matching_seed INTEGER NOT NULL,
    shock_seed INTEGER NOT NULL,
    behavior_seed INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    code_fingerprint TEXT NOT NULL,
    calibration_fingerprint TEXT NOT NULL,
    data_fingerprint TEXT NOT NULL,
    package_fingerprint TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    shard_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    runtime_seconds REAL,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed','invalid')),
    failure_reason TEXT,
    UNIQUE(config_fingerprint, rate_regime, replication, seed_namespace)
);
CREATE TABLE IF NOT EXISTS credit_applications (
    application_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    firm_id TEXT NOT NULL,
    requested_principal REAL NOT NULL CHECK(requested_principal >= 0),
    requested_maturity INTEGER NOT NULL CHECK(requested_maturity > 0),
    loan_purpose TEXT NOT NULL CHECK(loan_purpose IN ('working_capital','investment','mixed')),
    expected_return REAL NOT NULL,
    max_acceptable_rate REAL NOT NULL,
    borrower_leverage REAL NOT NULL,
    borrower_productivity REAL NOT NULL,
    approved_principal REAL NOT NULL DEFAULT 0,
    accepted_principal REAL NOT NULL DEFAULT 0,
    unfunded_principal REAL NOT NULL DEFAULT 0,
    decision_source TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    rationale TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bank_offers (
    offer_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES credit_applications(application_id),
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    bank_id TEXT NOT NULL,
    approved_principal REAL NOT NULL CHECK(approved_principal >= 0),
    maturity INTEGER NOT NULL CHECK(maturity > 0),
    offered_nominal_rate REAL,
    rejection_code TEXT,
    benchmark_component REAL NOT NULL,
    fixed_spread_component REAL NOT NULL,
    funding_component REAL NOT NULL,
    borrower_risk_component REAL NOT NULL,
    liquidity_component REAL NOT NULL,
    capital_component REAL NOT NULL,
    inflation_component REAL NOT NULL,
    bank_effect_component REAL NOT NULL,
    local_pass_through REAL NOT NULL,
    accepted_principal REAL NOT NULL DEFAULT 0,
    clearing_status TEXT NOT NULL DEFAULT 'not_selected',
    bank_reserves REAL NOT NULL,
    bank_equity REAL NOT NULL,
    bank_deposits REAL NOT NULL,
    bank_customer_loans REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS loan_contracts (
    loan_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    application_id TEXT NOT NULL REFERENCES credit_applications(application_id),
    offer_id TEXT NOT NULL REFERENCES bank_offers(offer_id),
    borrower_id TEXT NOT NULL,
    bank_id TEXT NOT NULL,
    principal REAL NOT NULL,
    remaining_principal REAL NOT NULL,
    nominal_rate REAL NOT NULL,
    maturity INTEGER NOT NULL,
    originated_period INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    terminated_period INTEGER,
    termination_reason TEXT
);
CREATE TABLE IF NOT EXISTS loan_events (
    loan_event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    loan_id TEXT NOT NULL REFERENCES loan_contracts(loan_id),
    event_type TEXT NOT NULL,
    scheduled_amount REAL NOT NULL,
    principal_paid REAL NOT NULL,
    interest_paid REAL NOT NULL,
    deposit_recovery REAL NOT NULL,
    collateral_recovery REAL NOT NULL,
    principal_written_off REAL NOT NULL,
    remaining_principal_before REAL NOT NULL,
    remaining_principal_after REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS incumbent_portfolio_events (
    incumbent_event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    bank_id TEXT NOT NULL,
    opening_principal REAL NOT NULL,
    scheduled_rollover REAL NOT NULL,
    net_originations REAL NOT NULL,
    closing_principal REAL NOT NULL,
    opening_ci_principal REAL NOT NULL,
    closing_ci_principal REAL NOT NULL,
    interest_paid REAL NOT NULL,
    household_funding_income REAL NOT NULL,
    retained_bank_income REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS authority_money_events (
    authority_event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    bank_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('reserve_remuneration','open_market_asset_swap','initial_reserve_configuration')),
    rate REAL NOT NULL,
    amount REAL NOT NULL,
    base_money_issuance REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deposit_funding_events (
    funding_event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    source_bank_id TEXT NOT NULL,
    target_bank_id TEXT NOT NULL,
    amount REAL NOT NULL,
    target_loans_deposits_before REAL NOT NULL,
    target_loans_deposits_after REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS firm_states (
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    firm_id TEXT NOT NULL,
    deposit_bank_id TEXT NOT NULL,
    deposits REAL NOT NULL,
    debt REAL NOT NULL,
    incumbent_debt REAL NOT NULL,
    experimental_debt REAL NOT NULL,
    real_capital REAL NOT NULL,
    equity REAL NOT NULL,
    productivity REAL NOT NULL,
    investment REAL NOT NULL,
    labor REAL NOT NULL,
    wages REAL NOT NULL,
    output REAL NOT NULL,
    inventory REAL NOT NULL,
    sales REAL NOT NULL,
    requested_credit REAL NOT NULL,
    received_credit REAL NOT NULL,
    debt_service_burden REAL NOT NULL,
    PRIMARY KEY(run_id, period, firm_id)
);
CREATE TABLE IF NOT EXISTS bank_states (
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    bank_id TEXT NOT NULL,
    reserves REAL NOT NULL,
    deposits REAL NOT NULL,
    customer_loans REAL NOT NULL,
    incumbent_loans REAL NOT NULL,
    incumbent_ci_share REAL NOT NULL,
    interbank_assets REAL NOT NULL,
    interbank_liabilities REAL NOT NULL,
    emergency_borrowing REAL NOT NULL,
    reserve_funding_liability REAL NOT NULL,
    equity REAL NOT NULL,
    risk_weighted_assets REAL NOT NULL,
    capital_ratio REAL,
    liquidity_ratio REAL,
    profit REAL NOT NULL,
    market_share REAL NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','resolution','resolved')),
    resolution_cost REAL NOT NULL,
    liquidity_failed INTEGER NOT NULL,
    PRIMARY KEY(run_id, period, bank_id)
);
CREATE TABLE IF NOT EXISTS period_macro (
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    base_money REAL NOT NULL,
    deposit_money REAL NOT NULL,
    new_credit REAL NOT NULL,
    incumbent_net_originations REAL NOT NULL,
    incumbent_interest_paid REAL NOT NULL,
    household_funding_income REAL NOT NULL,
    reserve_interest_income REAL NOT NULL,
    reserve_asset_swaps REAL NOT NULL,
    deposit_funding_reallocation REAL NOT NULL,
    outstanding_credit REAL NOT NULL,
    aggregate_output REAL NOT NULL,
    aggregate_investment REAL NOT NULL,
    planned_consumption REAL NOT NULL,
    actual_consumption REAL NOT NULL,
    inventory REAL NOT NULL,
    unmet_consumption REAL NOT NULL,
    requested_credit REAL NOT NULL,
    approved_credit REAL NOT NULL,
    accepted_credit REAL NOT NULL,
    unfunded_credit REAL NOT NULL,
    unfunded_demand_share REAL NOT NULL,
    mean_new_loan_rate REAL,
    rate_dispersion REAL,
    defaults INTEGER NOT NULL,
    write_offs REAL NOT NULL,
    unresolved_liquidity_shortfall REAL NOT NULL,
    active_banks INTEGER NOT NULL,
    failed_banks INTEGER NOT NULL,
    resolution_cost REAL NOT NULL,
    realized_inflation REAL NOT NULL,
    PRIMARY KEY(run_id, period)
);
CREATE TABLE IF NOT EXISTS liquidity_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    facility_type TEXT NOT NULL,
    lender_id TEXT NOT NULL,
    borrower_id TEXT NOT NULL,
    principal REAL NOT NULL,
    rate REAL NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bank_resolution_events (
    resolution_event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    bank_id TEXT NOT NULL,
    prior_equity REAL NOT NULL,
    risk_weighted_assets REAL NOT NULL,
    required_equity REAL NOT NULL,
    capital_injection REAL NOT NULL,
    reserves_created REAL NOT NULL,
    base_money_issuance REAL NOT NULL,
    resolution_cost REAL NOT NULL,
    status_before TEXT NOT NULL,
    status_after TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
    period INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    temperature REAL NOT NULL,
    reasoning_effort TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    latency_seconds REAL NOT NULL,
    status TEXT NOT NULL,
    failure_type TEXT
);
CREATE INDEX IF NOT EXISTS idx_macro_scenario ON experiment_runs(scenario_id, rate_regime);
CREATE INDEX IF NOT EXISTS idx_app_run_period ON credit_applications(run_id, period);
CREATE INDEX IF NOT EXISTS idx_offer_app ON bank_offers(application_id);
"""


class LedgerV03:
    def __init__(self, path: str | Path = ":memory:", created_at: str = "unknown"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(DDL)
        versions = [
            r[0]
            for r in self.conn.execute("SELECT schema_version FROM schema_metadata")
        ]
        if versions and versions != [SCHEMA_VERSION]:
            raise ValueError(f"refusing incompatible database schema: {versions}")
        self.conn.execute(
            "INSERT OR IGNORE INTO schema_metadata VALUES (?, ?)",
            (SCHEMA_VERSION, created_at),
        )
        self.conn.commit()

    def insert(self, table: str, row: dict[str, Any], *, replace: bool = False) -> None:
        if not table.replace("_", "").isalnum():
            raise ValueError("invalid table name")
        columns = tuple(row)
        operation = "INSERT OR REPLACE" if replace else "INSERT"
        sql = f"{operation} INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
        self.conn.execute(sql, tuple(row[c] for c in columns))

    def insert_many(self, table: str, rows: Iterable[dict[str, Any]]) -> None:
        for row in rows:
            self.insert(table, row)
        self.conn.commit()

    def register_parameter_set(
        self, parameter_set_id: str, canonical_json: str, fingerprint: str
    ) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO parameter_sets VALUES (?, ?, ?)",
            (parameter_set_id, canonical_json, fingerprint),
        )
        self.conn.commit()

    def update_run(self, run_id: str, **values: Any) -> None:
        allowed = {"completed_at", "runtime_seconds", "status", "failure_reason"}
        if not values or set(values) - allowed:
            raise ValueError("unsupported experiment_runs update")
        sql = (
            "UPDATE experiment_runs SET "
            + ",".join(f"{k}=?" for k in values)
            + " WHERE run_id=?"
        )
        self.conn.execute(sql, (*values.values(), run_id))
        self.conn.commit()

    def rows(self, table: str, run_id: str | None = None) -> list[dict[str, Any]]:
        if not table.replace("_", "").isalnum():
            raise ValueError("invalid table name")
        if run_id is None:
            cursor = self.conn.execute(f"SELECT * FROM {table}")
        else:
            cursor = self.conn.execute(
                f"SELECT * FROM {table} WHERE run_id=?", (run_id,)
            )
        return [dict(row) for row in cursor]

    def validate(self, expected_horizon: int | None = None) -> list[str]:
        errors: list[str] = []
        violations = list(self.conn.execute("PRAGMA foreign_key_check"))
        if violations:
            errors.append(f"{len(violations)} foreign-key violations")
        for row in self.conn.execute("SELECT run_id,status FROM experiment_runs"):
            if row["status"] == "completed" and expected_horizon is not None:
                count = self.conn.execute(
                    "SELECT COUNT(*) FROM period_macro WHERE run_id=? AND period>0",
                    (row["run_id"],),
                ).fetchone()[0]
                if count != expected_horizon:
                    errors.append(
                        f"{row['run_id']}: expected {expected_horizon} periods, found {count}"
                    )
        return errors

    def dump_schema(self) -> str:
        rows = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
        )
        return "\n\n".join(row[0] for row in rows)

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()


def canonical_parameters(parameters: Any) -> tuple[str, str]:
    payload = json.dumps(
        parameters.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    import hashlib

    return payload, hashlib.sha256(payload.encode()).hexdigest()
