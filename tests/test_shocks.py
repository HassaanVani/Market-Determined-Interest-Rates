import math

from engine.experiment import BehaviorMode, RateRegime, SeedBundle
from engine.model import MacroModel
from engine.shocks import Shock


def build_rule_model(shocks=None):
    return MacroModel(
        n_firms=2,
        n_banks=2,
        rate_regime=RateRegime.ADMINISTERED,
        behavior_mode=BehaviorMode.RULE,
        seeds=SeedBundle(environment=7, matching=8, shocks=9, behavior=10),
        shocks=shocks,
    )


def test_demand_shock_is_recorded_and_increases_credit_demand_and_output():
    shock = Shock(
        shock_id="demand_test",
        shock_type="demand",
        start_period=2,
        duration=1,
        magnitude=0.20,
    )
    treatment = build_rule_model([shock])
    control = build_rule_model()

    for _ in range(2):
        treatment.step()
        control.step()

    treatment_apps = treatment.ledger.get_credit_applications(treatment.run_id)
    control_apps = control.ledger.get_credit_applications(control.run_id)
    treatment_period_2 = sum(
        row["requested_principal"] for row in treatment_apps if row["period"] == 2
    )
    control_period_2 = sum(
        row["requested_principal"] for row in control_apps if row["period"] == 2
    )
    treatment_macro = treatment.ledger.get_period_macro(treatment.run_id)[2]
    control_macro = control.ledger.get_period_macro(control.run_id)[2]

    assert treatment.ledger.get_shocks(treatment.run_id)[0]["shock_type"] == "demand"
    assert treatment_period_2 > control_period_2
    assert treatment_macro["aggregate_output"] > control_macro["aggregate_output"]
    assert treatment_macro["total_consumption"] > control_macro["total_consumption"]


def test_productivity_shock_raises_output_for_the_same_wage_bill():
    shock = Shock(
        shock_id="productivity_test",
        shock_type="productivity",
        start_period=1,
        duration=1,
        magnitude=0.25,
    )
    treatment = build_rule_model([shock])
    control = build_rule_model()

    treatment.step()
    control.step()

    treatment_macro = treatment.ledger.get_period_macro(treatment.run_id)[1]
    control_macro = control.ledger.get_period_macro(control.run_id)[1]
    assert math.isclose(
        treatment_macro["aggregate_output"],
        control_macro["aggregate_output"] * 1.25,
    )


def test_shock_schedule_is_inactive_outside_its_registered_window():
    shock = Shock(
        shock_id="one_period",
        shock_type="demand",
        start_period=2,
        duration=1,
        magnitude=0.50,
    )
    model = build_rule_model([shock])

    assert model.shocks.effects(1)["demand_multiplier"] == 1.0
    assert model.shocks.effects(2)["demand_multiplier"] == 1.5
    assert model.shocks.effects(3)["demand_multiplier"] == 1.0
