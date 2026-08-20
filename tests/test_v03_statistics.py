import numpy as np
import pandas as pd

from v03.statistics import (
    holm_adjust,
    matched_difference_in_differences,
    matched_regime_effects,
    percentile_paired_bootstrap,
)


def test_paired_bootstrap_recovers_known_positive_effect():
    result = percentile_paired_bootstrap(np.repeat(2.0, 20), draws=1000, seed=1)
    assert result["estimate"] == 2.0
    assert result["lower_95"] == 2.0
    assert result["p_value"] < 0.01


def test_holm_is_monotone_in_sorted_p_values():
    adjusted = holm_adjust([0.01, 0.04])
    assert np.allclose(adjusted, [0.02, 0.04])


def test_matched_regime_and_did_use_replication_level_pairs():
    rows = []
    for replication in range(10):
        for regime in ("administered", "market"):
            for shock in (False, True):
                outcome = (
                    replication + (1 if regime == "market" else 0) + (3 if shock else 0)
                )
                if regime == "market" and shock:
                    outcome += 2
                rows.append(
                    {
                        "replication": replication,
                        "scenario_id": "shock" if shock else "baseline",
                        "rate_regime": regime,
                        "shock": shock,
                        "outcome": outcome,
                    }
                )
    frame = pd.DataFrame(rows)
    baseline = matched_regime_effects(frame[~frame.shock], ("outcome",))
    did = matched_difference_in_differences(frame, ("outcome",))
    assert baseline.iloc[0].estimate == 1
    assert did.iloc[0].estimate == 2
