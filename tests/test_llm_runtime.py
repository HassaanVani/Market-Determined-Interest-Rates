from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from database.ledger import Ledger
from engine.experiment import ExperimentConfig
from engine.llm_runtime import call_structured_llm


class Decision(BaseModel):
    decision_rationale: str
    loan_principal_requested: float
    max_acceptable_nominal_rate: float
    decision_status: str


class FakeCompletions:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def create(self, **kwargs):
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response))]
        )


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


def fake_model():
    ledger = Ledger()
    config = ExperimentConfig()
    ledger.register_run("test-run", config)
    return SimpleNamespace(
        schedule=SimpleNamespace(steps=0),
        llm_max_retries=1,
        llm_timeout_seconds=1.0,
        llm_model="deepseek-r1:8b",
        llm_temperature=0.0,
        llm_max_tokens=128,
        llm_reasoning_effort="none",
        prompt_version="test",
        run_id="test-run",
        ledger=ledger,
    )


@pytest.mark.asyncio
async def test_structured_llm_retries_and_records_each_attempt():
    model = fake_model()
    client = FakeClient(
        [
            ValueError("temporary failure"),
            (
                '{"decision_rationale":"cash buffer","loan_principal_requested":'
                '0,"max_acceptable_nominal_rate":0.05,'
                '"decision_status":"economic"}'
            ),
        ]
    )

    result, error = await call_structured_llm(
        model=model,
        agent_id="Firm_0",
        task_type="credit_demand",
        client=client,
        messages=[{"role": "user", "content": "Decide."}],
        response_model=Decision,
    )

    assert error is None
    assert result.decision_status == "economic"
    rows = model.ledger.get_llm_calls("test-run")
    assert [row["status"] for row in rows] == ["failed", "success"]
    assert rows[0]["error_type"] == "ValueError"
    assert rows[0]["prompt_hash"] == rows[1]["prompt_hash"]


@pytest.mark.asyncio
async def test_structured_llm_returns_error_after_bounded_failures():
    model = fake_model()
    client = FakeClient(["not json", "still not json"])

    result, error = await call_structured_llm(
        model=model,
        agent_id="Firm_0",
        task_type="credit_demand",
        client=client,
        messages=[{"role": "user", "content": "Decide."}],
        response_model=Decision,
    )

    assert result is None
    assert isinstance(error, ValueError)
    rows = model.ledger.get_llm_calls("test-run")
    assert len(rows) == 2
    assert all(row["status"] == "failed" for row in rows)
