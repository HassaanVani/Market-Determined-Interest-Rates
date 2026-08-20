import math

from engine.experiment import (
    BehaviorMode,
    ExperimentConfig,
    RateRegime,
    SeedBundle,
)
from engine.model import MacroModel


def test_experiment_fingerprint_is_stable_and_treatment_fields_are_independent():
    seeds = SeedBundle(environment=10, matching=11, shocks=12, behavior=13)
    market_rule = ExperimentConfig(
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
        seeds=seeds,
    )
    same = ExperimentConfig(
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.RULE,
        seeds=seeds,
    )
    market_llm = ExperimentConfig(
        rate_regime=RateRegime.MARKET,
        behavior_mode=BehaviorMode.LLM,
        seeds=seeds,
    )

    assert market_rule.fingerprint() == same.fingerprint()
    assert market_rule.fingerprint() != market_llm.fingerprint()
    assert market_rule.to_dict()["rate_regime"] == "market"
    assert market_rule.to_dict()["behavior_mode"] == "rule"


def test_initial_period_records_explicit_money_definitions_and_missing_rate():
    model = MacroModel(n_firms=2, n_banks=1, control_mode=True)

    rows = model.ledger.get_period_macro(model.run_id)
    assert len(rows) == 1
    initial = rows[0]

    assert initial["period"] == 0
    assert math.isclose(initial["deposit_money"], 300.0)
    assert math.isclose(initial["broad_money"], 300.0)
    assert math.isclose(initial["base_money"], 1000.0)
    assert initial["market_nominal_rate"] is None
    assert initial["outstanding_book_rate"] is None


def test_period_record_distinguishes_new_credit_and_outstanding_credit():
    model = MacroModel(n_firms=1, n_banks=1, control_mode=True)
    model.step()
    model.complete_run()

    rows = model.ledger.get_period_macro(model.run_id)
    run = model.ledger.get_run(model.run_id)

    assert len(rows) == 2
    assert rows[1]["new_credit"] > 0
    assert rows[1]["outstanding_credit"] > 0
    assert rows[1]["market_nominal_rate"] is not None
    assert run["status"] == "completed"
    assert run["config"]["rate_regime"] == "administered"
    assert run["config"]["behavior_mode"] == "rule"


def test_llm_infrastructure_failures_invalidate_a_completed_run():
    model = MacroModel(n_firms=1, n_banks=1, control_mode=True)
    model.llm_failure_count = 2

    status = model.complete_run()
    run = model.ledger.get_run(model.run_id)

    assert status == "invalid"
    assert run["status"] == "invalid"
    assert "2 LLM decision calls failed" in run["failure_reason"]
