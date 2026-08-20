from engine.experiment import BehaviorMode, RateRegime
from engine.model import MacroModel


def build_model():
    return MacroModel(
        n_firms=2,
        n_banks=2,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )


def test_agent_state_panel_records_every_agent_at_every_period():
    model = build_model()
    model.step()

    states = model.ledger.get_agent_states(model.run_id)
    agents_per_period = 2 + 2 + 1

    assert len(states) == agents_per_period * 2
    assert {row["period"] for row in states} == {0, 1}
    assert {row["agent_type"] for row in states} == {
        "Firm",
        "Bank",
        "Household",
    }
    bank_states = [
        row for row in states if row["period"] == 1 and row["agent_type"] == "Bank"
    ]
    assert all(row["reserves"] is not None for row in bank_states)
    assert all(row["deposit_liabilities"] is not None for row in bank_states)


def test_accepted_offers_link_to_contracts_and_payment_events():
    model = build_model()
    model.step()

    offers = model.ledger.get_bank_offers(model.run_id)
    accepted_offer_ids = {row["offer_id"] for row in offers if row["accepted"]}
    contracts = model.ledger.get_loan_contracts(model.run_id)
    events = model.ledger.get_loan_events(model.run_id)

    assert len(contracts) == 2
    assert {row["offer_id"] for row in contracts} == accepted_offer_ids
    assert {row["loan_id"] for row in events} == {row["loan_id"] for row in contracts}
    assert {row["event_type"] for row in events} == {"payment"}
    assert all(row["remaining_principal_after"] >= 0 for row in events)


def test_period_macro_contains_output_consumption_and_liquidity_measures():
    model = build_model()
    model.step()

    period = model.ledger.get_period_macro(model.run_id)[1]

    assert period["aggregate_output"] > 0
    assert period["total_consumption"] > 0
    assert period["interbank_volume"] >= 0
    assert period["emergency_borrowing"] >= 0
    assert period["liquidity_shortfall"] >= 0
