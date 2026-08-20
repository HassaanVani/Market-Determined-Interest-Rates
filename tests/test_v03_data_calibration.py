import pandas as pd
import pytest

from v03.calibration import MinimumDistanceCalibrator, holdout_gate
from v03.data_pipeline import REQUIRED_QUARTERS, clean_bank_panel


def panel():
    rows = []
    for q_index, quarter in enumerate(REQUIRED_QUARTERS):
        for bank in range(4):
            assets = 100 + bank * 20 + q_index
            rows.append(
                {
                    "bank_id": str(bank),
                    "quarter": quarter,
                    "active": True,
                    "domestic_charter": True,
                    "fdic_insured": True,
                    "commercial_bank": True,
                    "assets": assets,
                    "deposits": assets * 0.8,
                    "gross_loans": assets * 0.6,
                    "liquid_assets": assets * 0.15,
                    "equity": assets * 0.1,
                    "ci_loans": assets * 0.2,
                    "ci_chargeoffs": assets * 0.001,
                }
            )
    return pd.DataFrame(rows)


def test_clean_panel_has_holdout_and_unique_keys():
    data = panel()
    data.loc[data.index[0], "ci_chargeoffs"] = -0.1
    clean, exclusions, missingness = clean_bank_panel(data)
    assert set(clean.quarter) == set(REQUIRED_QUARTERS)
    assert exclusions.empty
    assert not clean.duplicated(["bank_id", "quarter"]).any()
    assert "capital_assets" in clean
    assert "ci_loan_growth" in clean
    assert (clean.ci_chargeoffs < 0).any()


def test_duplicate_keys_and_missing_quarters_fail():
    data = panel()
    with pytest.raises(ValueError, match="duplicate"):
        clean_bank_panel(pd.concat([data, data.iloc[[0]]]))
    with pytest.raises(ValueError, match="missing required quarters"):
        clean_bank_panel(data[data.quarter != "2025Q4"])


def test_minimum_distance_recovers_synthetic_parameter():
    calibrator = MinimumDistanceCalibrator(
        target_moments={"moment": 4.0},
        bootstrap_variances={"moment": 1.0},
        bounds={"theta": (0.0, 5.0)},
        simulator=lambda p, seed: {"moment": 2 * p["theta"]},
    )
    best, starts = calibrator.fit(starts=(1, 2), maxiter=20)
    assert abs(best.parameters["theta"] - 2) < 1e-4
    assert len(starts) == 2


def test_holdout_gate_requires_six_groups_and_no_two_se_failure():
    intervals = {f"g{i}": (1.0, 0.1, 0.8, 1.2) for i in range(8)}
    assert holdout_gate({name: 1.0 for name in intervals}, intervals)["passed"]
    bad = {name: 1.0 for name in intervals}
    bad["g0"] = 2.0
    assert not holdout_gate(bad, intervals)["passed"]
