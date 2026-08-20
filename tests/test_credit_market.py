import asyncio
import math

from engine.experiment import BehaviorMode, RateRegime, SeedBundle
from engine.model import MacroModel


def test_rate_regime_and_behavior_mode_are_independently_configurable():
    combinations = {
        (RateRegime.ADMINISTERED, BehaviorMode.RULE),
        (RateRegime.ADMINISTERED, BehaviorMode.LLM),
        (RateRegime.MARKET, BehaviorMode.RULE),
        (RateRegime.MARKET, BehaviorMode.LLM),
    }

    for rate_regime, behavior_mode in combinations:
        model = MacroModel(
            n_firms=1,
            n_banks=1,
            rate_regime=rate_regime,
            behavior_mode=behavior_mode,
        )
        assert model.rate_regime == rate_regime
        assert model.behavior_mode == behavior_mode
        assert (
            model.experiment_config.rate_regime,
            model.experiment_config.behavior_mode,
        ) == (rate_regime, behavior_mode)


def test_every_bank_quotes_and_firm_accepts_the_cheapest_offer():
    model = MacroModel(
        n_firms=1,
        n_banks=3,
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
        seeds=SeedBundle(matching=17),
    )
    model.step()

    applications = model.ledger.get_credit_applications(model.run_id)
    offers = model.ledger.get_bank_offers(model.run_id)
    accepted = [offer for offer in offers if offer["accepted"]]
    approved = [offer for offer in offers if offer["approved"]]

    assert len(applications) == 1
    assert len(offers) == 3
    assert len(accepted) == 1
    assert accepted[0]["offered_nominal_rate"] == min(
        offer["offered_nominal_rate"] for offer in approved
    )
    assert model.active_loans[0]["offer_id"] == accepted[0]["offer_id"]


def test_market_and_administered_rule_quotes_use_different_anchors():
    administered = MacroModel(
        n_firms=1,
        n_banks=1,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
        policy_rate=0.03,
    )
    market = MacroModel(
        n_firms=1,
        n_banks=1,
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
        policy_rate=0.20,
    )

    administered_bank = administered.schedule.banks[0]
    market_bank = market.schedule.banks[0]
    administered_quote = asyncio.run(
        administered_bank.evaluate_loan("firm_0", 10.0, 1.0)
    )
    market_quote = asyncio.run(market_bank.evaluate_loan("firm_0", 10.0, 1.0))

    assert math.isclose(administered_quote.offered_nominal_rate, 0.03)
    assert math.isclose(market_quote.offered_nominal_rate, 0.02)
    assert market_quote.offered_nominal_rate != market.policy_rate


def test_application_and_offer_records_identify_decision_source_and_status():
    model = MacroModel(
        n_firms=2,
        n_banks=2,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )
    model.step()

    applications = model.ledger.get_credit_applications(model.run_id)
    offers = model.ledger.get_bank_offers(model.run_id)

    assert len(applications) == 2
    assert len(offers) == 4
    assert {row["decision_source"] for row in applications} == {"rule"}
    assert {row["decision_status"] for row in applications} == {"economic"}
    assert {row["decision_source"] for row in offers} == {"rule"}
    assert {row["decision_status"] for row in offers} == {"economic"}


def test_clearing_rechecks_bank_capacity_after_earlier_acceptances():
    model = MacroModel(
        n_firms=2,
        n_banks=2,
        reserve_requirement=4.40,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
    )

    model.step()

    offers = model.ledger.get_bank_offers(model.run_id)
    constrained = [
        offer for offer in offers if offer["clearing_status"] == "capacity_constrained"
    ]
    accepted = [offer for offer in offers if offer["accepted"]]

    assert len(constrained) == 1
    assert constrained[0]["bank_id"] == "bank_0"
    assert len(accepted) == 2
    assert {offer["bank_id"] for offer in accepted} == {"bank_0", "bank_1"}


def test_market_quotes_price_reserve_and_capital_scarcity():
    model = MacroModel(
        n_firms=1,
        n_banks=2,
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
        initial_reserves_per_bank=300.0,
    )
    liquid, scarce = model.schedule.banks
    liquid.current_balance = 300.0
    scarce.current_balance = 100.0

    liquid_quote = asyncio.run(
        liquid.evaluate_loan("firm_0", principal=10.0, max_rate=1.0)
    )
    scarce_quote = asyncio.run(
        scarce.evaluate_loan("firm_0", principal=10.0, max_rate=1.0)
    )
    assert scarce_quote.offered_nominal_rate > liquid_quote.offered_nominal_rate

    model.active_loans = [
        {
            "bank_id": liquid.unique_id,
            "remaining_principal": 100.0,
        }
    ]
    liquid.equity = 20.0
    low_capital_quote = asyncio.run(
        liquid.evaluate_loan("firm_0", principal=10.0, max_rate=1.0)
    )
    liquid.equity = 100.0
    high_capital_quote = asyncio.run(
        liquid.evaluate_loan("firm_0", principal=10.0, max_rate=1.0)
    )
    assert (
        low_capital_quote.offered_nominal_rate > high_capital_quote.offered_nominal_rate
    )
