import math

import pytest

from database.ledger import BalanceSheetMismatch
from engine.experiment import BehaviorMode, RateRegime
from engine.model import MacroModel


def test_initial_deposit_liabilities_follow_agent_bank_assignments():
    model = MacroModel(
        n_firms=3,
        n_banks=2,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )

    bank_0, bank_1 = model.schedule.banks
    assert model.household.deposit_bank_id == "bank_0"
    assert [firm.deposit_bank_id for firm in model.schedule.firms] == [
        "bank_0",
        "bank_1",
        "bank_0",
    ]
    assert math.isclose(bank_0.current_debt, 300.0)
    assert math.isclose(bank_1.current_debt, 100.0)
    model.validate_monetary_system()


def test_cross_bank_payments_create_reserve_settlement_events():
    model = MacroModel(
        n_firms=2,
        n_banks=2,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )
    model.step()

    events = model.ledger.get_settlement_events(model.run_id)
    event_types = {event["event_type"] for event in events}
    cross_bank = [
        event for event in events if event["payer_bank_id"] != event["payee_bank_id"]
    ]

    assert {"wage", "loan_disbursement", "consumption", "debt_service"} <= (event_types)
    assert cross_bank
    assert all(
        math.isclose(event["reserve_transfer"], event["amount"]) for event in cross_bank
    )
    assert math.isclose(
        sum(bank.current_balance for bank in model.schedule.banks), 2000.0
    )
    model.validate_monetary_system()


def test_loan_disbursement_to_another_bank_moves_reserves_and_creates_deposit():
    model = MacroModel(
        n_firms=2,
        n_banks=2,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )
    model.step()

    events = model.ledger.get_settlement_events(model.run_id)
    disbursements = [
        event
        for event in events
        if event["event_type"] == "loan_disbursement"
        and event["payer_bank_id"] != event["payee_bank_id"]
    ]

    assert len(disbursements) == 1
    event = disbursements[0]
    assert event["payer_bank_id"] == "bank_0"
    assert event["payee_bank_id"] == "bank_1"
    assert event["payee_id"] == "firm_1"
    assert event["reserve_transfer"] > 0


def test_system_validation_detects_unbacked_agent_deposit_mutation():
    model = MacroModel(n_firms=1, n_banks=1, control_mode=True)
    model.schedule.firms[0].current_balance += 1.0

    with pytest.raises(BalanceSheetMismatch, match="System deposit mismatch"):
        model.validate_monetary_system()


def test_system_validation_detects_unmatched_borrower_debt():
    model = MacroModel(n_firms=1, n_banks=1, control_mode=True)
    model.schedule.firms[0].current_debt += 1.0

    with pytest.raises(BalanceSheetMismatch, match="System credit mismatch"):
        model.validate_monetary_system()
