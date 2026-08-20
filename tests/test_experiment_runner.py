from argparse import Namespace

from run_experiments import run_experiments


def test_factorial_runner_writes_both_rule_based_rate_regimes(tmp_path):
    args = Namespace(
        db=str(tmp_path / "pilot.sqlite"),
        regime="all",
        behavior="rule",
        steps=2,
        replications=1,
        firms=2,
        banks=2,
        seed_start=500,
        policy_rate=0.03,
        reserve_requirement=0.10,
        capital_requirement=0.08,
        leverage_limit=1.5,
        initial_reserves_per_bank=1000.0,
        initial_bank_equity=100.0,
        lender_of_last_resort="unavailable",
        emergency_penalty_spread=0.02,
        emergency_borrowing_limit_ratio=1.0,
        shock_type="none",
        shock_start=2,
        shock_duration=1,
        shock_magnitude=0.20,
        heterogeneity_scale=0.0,
        scenario_name="test",
        llm_model="unused",
        temperature=0.0,
        llm_timeout_seconds=1.0,
        llm_max_retries=0,
        llm_max_tokens=64,
        llm_reasoning_effort="none",
        prompt_version="test",
    )

    output_path, summaries = run_experiments(args)

    assert output_path.exists()
    assert len(summaries) == 2
    assert {row["regime"] for row in summaries} == {
        "administered",
        "market",
    }
    assert {row["behavior"] for row in summaries} == {"rule"}
    assert {row["status"] for row in summaries} == {"completed"}
