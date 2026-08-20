import math

from engine.experiment import BehaviorMode, RateRegime
from engine.model import MacroModel


def test_interbank_market_moves_existing_reserves_and_records_overnight_loan():
    model = MacroModel(
        n_firms=2,
        n_banks=2,
        initial_reserves_per_bank=30.0,
        reserve_requirement=0.10,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
        policy_rate=0.03,
    )
    bank_0, bank_1 = model.schedule.banks
    bank_0.current_balance = 5.0
    bank_1.current_balance = 55.0

    model.liquidity.clear_market(period=1)

    loans = model.ledger.get_liquidity_loans(model.run_id)
    assert len(loans) == 1
    assert loans[0]["facility_type"] == "interbank"
    assert loans[0]["lender_id"] == "bank_1"
    assert loans[0]["borrower_id"] == "bank_0"
    assert math.isclose(loans[0]["principal"], 15.0)
    assert math.isclose(loans[0]["interest_rate"], 0.03)
    assert math.isclose(model.liquidity.interbank_volume, 15.0)
    assert math.isclose(sum(bank.current_balance for bank in [bank_0, bank_1]), 60.0)
    model.validate_monetary_system()


def test_market_interbank_rate_responds_to_reserve_scarcity():
    model = MacroModel(
        n_firms=2,
        n_banks=2,
        initial_reserves_per_bank=30.0,
        reserve_requirement=0.10,
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
    )
    bank_0, bank_1 = model.schedule.banks
    bank_0.current_balance = 5.0
    bank_1.current_balance = 55.0

    model.liquidity.clear_market(period=1)

    expected_rate = 0.01 + 0.02 * (15.0 / 45.0)
    assert math.isclose(model.liquidity.interbank_rate, expected_rate)
    assert not math.isclose(model.liquidity.interbank_rate, model.policy_rate)


def test_penalty_facility_creates_and_later_destroys_reserves():
    model = MacroModel(
        n_firms=1,
        n_banks=1,
        initial_reserves_per_bank=5.0,
        reserve_requirement=0.10,
        lender_of_last_resort="penalty",
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
        policy_rate=0.03,
        emergency_penalty_spread=0.02,
    )
    bank = model.schedule.banks[0]

    model.liquidity.clear_market(period=1)

    assert math.isclose(bank.emergency_borrowing, 15.0)
    assert math.isclose(bank.current_balance, 20.0)
    assert math.isclose(model.base_money_issued, 20.0)
    assert not bank.liquidity_failed
    model.validate_monetary_system()

    model.liquidity.begin_period(period=2)
    assert math.isclose(bank.emergency_borrowing, 0.0)
    assert math.isclose(bank.current_balance, 4.25)
    assert math.isclose(model.base_money_issued, 4.25)
    assert model.ledger.get_liquidity_loans(model.run_id)[0]["status"] == "repaid"
    model.validate_monetary_system()


def test_unavailable_facility_records_unresolved_shortfall():
    model = MacroModel(
        n_firms=1,
        n_banks=1,
        initial_reserves_per_bank=5.0,
        reserve_requirement=0.10,
        lender_of_last_resort="unavailable",
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
    )
    bank = model.schedule.banks[0]

    model.liquidity.clear_market(period=1)

    assert bank.liquidity_failed
    assert math.isclose(model.liquidity.unresolved_shortfall, 15.0)
    assert not model.ledger.get_liquidity_loans(model.run_id)
    state = model.ledger.get_bank_liquidity(model.run_id)[0]
    assert math.isclose(state["unresolved_shortfall"], 15.0)
    assert state["liquidity_failed"] == 1


def test_limited_facility_respects_equity_based_borrowing_limit():
    model = MacroModel(
        n_firms=1,
        n_banks=1,
        initial_reserves_per_bank=250.0,
        initial_bank_equity=50.0,
        reserve_requirement=2.0,
        lender_of_last_resort="limited",
        emergency_borrowing_limit_ratio=1.0,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )
    bank = model.schedule.banks[0]

    model.liquidity.clear_market(period=1)

    assert math.isclose(bank.emergency_borrowing, 50.0)
    assert math.isclose(model.liquidity.unresolved_shortfall, 100.0)
    assert bank.liquidity_failed
    model.validate_monetary_system()
