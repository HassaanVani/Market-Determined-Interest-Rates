import math

import pandas as pd

from v03.config import CalibrationBundle, ExperimentSpec, ModelParameters, RateRegime
from v03.design import seeds_for
from v03.model import InstitutionalCreditModel
from v03.schema import LedgerV03


def make_model(regime=RateRegime.MARKET, **parameter_updates):
    params = ModelParameters(n_firms=3, n_banks=2, horizon=3, **parameter_updates)
    spec = ExperimentSpec(
        calibration_id="test",
        parameter_set_id="test",
        scenario_id="smoke",
        seed_namespace="test",
        parameters=params,
    )
    ledger = LedgerV03(":memory:")
    return InstitutionalCreditModel(spec, regime, seeds_for("test", 0), ledger), ledger


def test_complete_run_has_full_horizon_and_accounting():
    model, ledger = make_model()
    assert model.run() == "completed"
    assert not ledger.validate(3)
    assert len(ledger.rows("period_macro", model.run_id)) == 3
    model._validate_accounting()


def test_credit_market_records_partial_quantities_and_pricing_components():
    model, ledger = make_model(max_lender_share=0.30)
    model.step()
    applications = ledger.rows("credit_applications", model.run_id)
    offers = ledger.rows("bank_offers", model.run_id)
    assert applications and offers
    assert all(
        row["accepted_principal"] <= row["requested_principal"] + 1e-9
        for row in applications
    )
    assert any(row["unfunded_principal"] > 0 for row in applications)
    assert all("borrower_risk_component" in row for row in offers)


def test_investment_is_asset_swap_and_depreciation_reduces_capital():
    model, _ = make_model(investment_share=0.5)
    initial = sum(f.capital for f in model.firms)
    model.step()
    invested = sum(f.investment for f in model.firms)
    expected_pre_investment = initial * (1 - model.p.capital_depreciation)
    assert math.isclose(
        sum(f.capital for f in model.firms),
        expected_pre_investment + invested,
        abs_tol=1e-7,
    )


def test_negative_equity_bank_enters_resolution_then_gets_explicit_injection():
    model, ledger = make_model(resolution_delay=1)
    bank = model.banks[0]
    bank.other_assets -= bank.equity + 5
    model._mark_insolvent()
    assert bank.status == "resolution"
    before = model.base_money_issued
    model.period = 1
    cost = model._resolve_pending_banks()
    assert bank.status == "resolved"
    assert cost > 0
    assert model.base_money_issued > before
    assert (
        ledger.rows("bank_resolution_events", model.run_id)[0]["capital_injection"]
        == cost
    )


def test_identical_seed_and_spec_are_deterministic_for_economic_tables():
    first, first_ledger = make_model()
    second, second_ledger = make_model()
    first.run()
    second.run()
    for table in (
        "period_macro",
        "firm_states",
        "bank_states",
        "credit_applications",
        "bank_offers",
    ):
        assert first_ledger.rows(table, first.run_id) == second_ledger.rows(
            table, second.run_id
        )


def test_empirical_incumbent_book_has_borrower_liability_and_balanced_growth():
    model, ledger = make_model()
    # Install a compact empirical opening book without relying on external data.
    model.calibration = type(
        "Bundle",
        (),
        {
            "sampling_distributions": {
                "assets": [125.0, 125.0],
                "deposits": [100.0, 100.0],
                "gross_loans": [80.0, 80.0],
                "liquid_assets": [10.0, 10.0],
                "equity": [12.0, 12.0],
                "ci_share": [0.10, 0.10],
            }
        },
    )()
    model._initialize_agents()
    assert math.isclose(sum(f.legacy_debt for f in model.firms), 160.0)
    assert math.isclose(sum(f.debt for f in model.firms), 160.0)
    deposits_before = sum(f.deposits for f in model.firms) + model.household.deposits
    debt_before = sum(f.debt for f in model.firms)
    model.period = 1
    flows = model._service_incumbent_portfolios()
    model._validate_accounting()
    assert math.isclose(
        sum(f.debt for f in model.firms) - debt_before,
        flows["net_originations"],
        abs_tol=1e-7,
    )
    deposits_after = sum(f.deposits for f in model.firms) + model.household.deposits
    retained = sum(
        row["retained_bank_income"]
        for row in ledger.rows("incumbent_portfolio_events", model.run_id)
    )
    assert math.isclose(
        deposits_after - deposits_before,
        flows["net_originations"] - retained,
        abs_tol=1e-7,
    )


def test_loan_interest_rate_is_converted_from_annual_to_quarterly():
    model, ledger = make_model(periods_per_year=4)
    model.step()
    event = ledger.rows("loan_events", model.run_id)[0]
    contract = ledger.rows("loan_contracts", model.run_id)[0]
    expected_interest = contract["principal"] * contract["nominal_rate"] / 4
    assert event["interest_paid"] <= expected_interest + 1e-9


def test_reserve_remuneration_is_explicit_base_money_and_bank_income():
    model, ledger = make_model(reserve_remuneration_rate=0.04)
    before = model.base_money_issued
    model.period = 1
    income = model._pay_reserve_interest()
    assert income > 0
    assert math.isclose(model.base_money_issued - before, income)
    events = ledger.rows("authority_money_events", model.run_id)
    assert math.isclose(sum(row["amount"] for row in events), income)
    model._validate_accounting()


def test_deposit_funding_market_reallocates_without_creating_deposits():
    model, ledger = make_model(loan_deposit_target=0.8, deposit_reallocation_speed=0.5)
    borrower = model.firms[0]
    recipient = model.bank(borrower.deposit_bank_id)
    donor = next(bank for bank in model.banks if bank is not recipient)
    if model.household.deposit_accounts.get(donor.bank_id, 0.0) == 0:
        source = model.bank(model.household.deposit_bank_id)
        amount = min(50.0, model.household.deposit_accounts[source.bank_id])
        model.household.deposit_accounts[source.bank_id] -= amount
        model.household.deposit_accounts[donor.bank_id] = amount
        source.deposits -= amount
        source.reserves -= amount
        donor.deposits += amount
        donor.reserves += amount
    recipient.legacy_loans = 200.0
    borrower.debt += 200.0
    borrower.legacy_debt += 200.0
    model._sync_bank_equity()
    deposits_before = sum(bank.deposits for bank in model.banks)
    household_before = model.household.deposits
    moved = model._rebalance_deposit_funding()
    assert moved > 0
    assert math.isclose(sum(bank.deposits for bank in model.banks), deposits_before)
    assert math.isclose(model.household.deposits, household_before)
    assert ledger.rows("deposit_funding_events", model.run_id)
    model._validate_accounting()


def test_h7_empirical_reserve_anchor_changes_asset_mix_not_equity():
    parameters = ModelParameters(
        n_firms=4,
        n_banks=2,
        horizon=1,
        initial_bank_reserves=20.0,
        initial_bank_deposits=100.0,
    )
    spec = ExperimentSpec(
        calibration_id="test",
        parameter_set_id="h7-test",
        scenario_id="h7_reserve_0.20_penalty_1.0",
        seed_namespace="h7-test",
        parameters=parameters,
    )
    calibration = CalibrationBundle(
        calibration_id="test",
        target_moments={},
        fitted_parameters={},
        sampling_distributions={
            "assets": [130.0, 260.0],
            "deposits": [100.0, 200.0],
            "gross_loans": [80.0, 160.0],
            "liquid_assets": [10.0, 20.0],
            "equity": [10.0, 20.0],
            "ci_share": [0.1, 0.1],
        },
        source_data_fingerprint="test-data",
        transformation_fingerprint="test-transform",
    )
    ledger = LedgerV03(":memory:")
    model = InstitutionalCreditModel(
        spec,
        RateRegime.MARKET,
        seeds_for("h7-test", 0),
        ledger,
        calibration,
    )
    assert all(
        math.isclose(bank.reserves / bank.deposits, 0.20) for bank in model.banks
    )
    assert len(ledger.rows("authority_money_events", model.run_id)) == 2
    model._validate_accounting()


def test_empirical_concentration_switch_changes_hhi_and_preserves_bank_ratios():
    calibration = CalibrationBundle(
        calibration_id="test",
        target_moments={},
        fitted_parameters={},
        sampling_distributions={
            "assets": [130.0, 260.0, 390.0, 520.0, 650.0],
            "deposits": [100.0, 200.0, 300.0, 400.0, 500.0],
            "gross_loans": [80.0, 160.0, 240.0, 320.0, 400.0],
            "liquid_assets": [10.0, 20.0, 30.0, 40.0, 50.0],
            "equity": [10.0, 20.0, 30.0, 40.0, 50.0],
        },
        source_data_fingerprint="test-data",
        transformation_fingerprint="test-transform",
    )

    def initialized(concentration):
        params = ModelParameters(
            n_firms=30,
            n_banks=5,
            horizon=1,
            deposit_concentration=concentration,
        )
        spec = ExperimentSpec(
            calibration_id="test",
            parameter_set_id=f"concentration-{concentration}",
            scenario_id=f"topology_30_5_{concentration}",
            seed_namespace="concentration-test",
            parameters=params,
        )
        return InstitutionalCreditModel(
            spec,
            RateRegime.MARKET,
            seeds_for("concentration-test", 0),
            LedgerV03(":memory:"),
            calibration,
        )

    low = initialized("low")
    high = initialized("high")

    def hhi(model):
        total = sum(bank.deposits for bank in model.banks)
        return sum((bank.deposits / total) ** 2 for bank in model.banks)

    assert math.isclose(hhi(low), 0.20)
    assert math.isclose(hhi(high), 0.3125)
    assert hhi(high) > hhi(low)
    for model in (low, high):
        assert all(
            math.isclose(bank.legacy_loans / bank.deposits, 0.8)
            for bank in model.banks
        )
        model._validate_accounting()


def test_limited_facility_cap_applies_to_total_outstanding_exposure():
    model, _ = make_model(
        reserve_requirement=0.5,
        emergency_facility="limited",
        emergency_limit_equity=0.5,
    )
    for bank in model.banks:
        bank.reserves = -10.0
    model._clear_liquidity()
    first = sum(bank.emergency_borrowing for bank in model.banks)
    for bank in model.banks:
        bank.reserves = -10.0
    model._clear_liquidity()
    second = sum(bank.emergency_borrowing for bank in model.banks)
    assert first > 0
    assert math.isclose(second, first)
