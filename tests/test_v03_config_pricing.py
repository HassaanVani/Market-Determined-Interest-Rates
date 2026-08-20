import pytest
from pydantic import ValidationError

from v03.config import ExperimentSpec, ModelParameters, RateRegime, SeedBundle
from v03.pricing import BankState, BorrowerState, price_loan


def spec(**updates):
    values = dict(
        calibration_id="test",
        parameter_set_id="test",
        scenario_id="test",
        seed_namespace="test",
    )
    values.update(updates)
    return ExperimentSpec(**values)


def test_config_is_strict_canonical_and_serializable():
    first = spec()
    second = ExperimentSpec.model_validate_json(first.canonical_json())
    assert first == second
    assert first.fingerprint() == second.fingerprint()
    with pytest.raises(ValidationError):
        spec(unknown_field=True)


def test_seed_streams_must_be_distinct():
    with pytest.raises(ValidationError):
        SeedBundle(environment=1, matching=1, shocks=2, behavior=3)


def test_market_has_full_and_administered_attenuated_local_pass_through():
    parameters = ModelParameters()
    borrower = BorrowerState(leverage=1.0, expected_return=0.12, productivity=1.0)
    bank = BankState(
        reserve_ratio=0.05,
        capital_ratio=0.04,
        expected_inflation=0.02,
        funding_rate=0.015,
    )
    market = price_loan(
        RateRegime.MARKET, borrower, bank, parameters, spec().mechanisms
    )
    administered = price_loan(
        RateRegime.ADMINISTERED, borrower, bank, parameters, spec().mechanisms
    )
    assert market.pass_through == 1.0
    assert administered.pass_through == parameters.administered_pass_through
    assert market.borrower_risk == administered.borrower_risk


def test_pricing_switch_removes_only_named_component():
    baseline = spec()
    off = baseline.mechanisms.model_copy(update={"borrower_risk_pricing": False})
    state = BorrowerState(2.0, 0.12, 1.0)
    bank = BankState(0.2, 0.2, 0.02, 0.02)
    quote = price_loan(RateRegime.MARKET, state, bank, baseline.parameters, off)
    assert quote.borrower_risk == 0
    assert quote.inflation > 0


def test_funding_stress_is_common_but_pass_through_differs():
    parameters = ModelParameters()
    borrower = BorrowerState(0.5, 0.12, 1.0)
    bank = BankState(0.08, 0.10, 0.02, 0.03)
    market = price_loan(
        RateRegime.MARKET, borrower, bank, parameters, spec().mechanisms
    )
    administered = price_loan(
        RateRegime.ADMINISTERED, borrower, bank, parameters, spec().mechanisms
    )
    assert market.funding == administered.funding == 0.015
    assert market.pass_through == 1.0
    assert administered.pass_through < 1.0
