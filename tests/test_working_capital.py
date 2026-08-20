from engine.experiment import BehaviorMode, RateRegime
from engine.model import MacroModel


def build_model(leverage_limit):
    return MacroModel(
        n_firms=1,
        n_banks=1,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
        leverage_limit=leverage_limit,
        initial_reserves_per_bank=300.0,
    )


def test_originated_credit_funds_next_period_working_capital_and_output():
    funded = build_model(leverage_limit=1.5)
    constrained = build_model(leverage_limit=0.0)

    funded.step()
    constrained.step()
    assert funded.schedule.firms[0].working_capital_budget > 0.0
    assert constrained.schedule.firms[0].working_capital_budget == 0.0

    funded.step()
    constrained.step()

    assert funded.aggregate_output > constrained.aggregate_output
    states = funded.ledger.get_agent_states(funded.run_id)
    firm_state = next(
        row for row in states if row["period"] == 2 and row["agent_type"] == "Firm"
    )
    assert firm_state["working_capital_budget"] > 0.0
