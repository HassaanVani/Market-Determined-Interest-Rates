from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import time
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from v03.design import seeds_for

PROMPT_VERSION = "deepseek-v0.3-bounded-share-2"


class FirmDecision(BaseModel):
    requested_fraction: float = Field(ge=0, le=1)
    maturity: int = Field(ge=1, le=24)
    purpose: Literal["working_capital", "investment", "mixed"]
    expected_return: float = Field(ge=0, le=1)
    max_rate: float = Field(ge=0, le=1)
    rationale: str


class BankDecision(BaseModel):
    approval_fraction: float = Field(ge=0, le=1)
    maturity: int = Field(ge=1, le=24)
    nominal_rate: float = Field(ge=0, le=1)
    rejection_code: str | None = None
    rationale: str


def freeze_llm_protocol(
    output: Path, model: str, pairs: int, audit_states: int
) -> dict:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "temperature": 0.0,
        "reasoning": "disabled",
        "pairs": pairs,
        "periods": 3,
        "firms": 3,
        "banks": 2,
        "audit_states": audit_states,
        "audit_templates": 3,
        "retries": 2,
        "hard_call_timeout_seconds": 30.0,
        "firm_schema": FirmDecision.model_json_schema(),
        "bank_schema": BankDecision.model_json_schema(),
        "prompt_function_sha256": hashlib.sha256(
            inspect.getsource(prompt_for).encode()
        ).hexdigest(),
        "state_generator_sha256": hashlib.sha256(
            inspect.getsource(institutional_state).encode()
        ).hexdigest(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["protocol_fingerprint"] = hashlib.sha256(canonical.encode()).hexdigest()
    path = output.parent / "llm_protocol.json"
    if path.is_file():
        existing = json.loads(path.read_text())
        if existing != payload:
            raise ValueError(f"LLM protocol mismatch: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def institutional_state(pair: int, period: int, agent: int) -> dict:
    seed = seeds_for("llm-robustness-v0.3", pair).environment + period * 100 + agent
    import random

    rng = random.Random(seed)
    return {
        "period": period,
        "deposits": round(rng.uniform(15, 80), 4),
        "debt": round(rng.uniform(0, 60), 4),
        "capital": round(rng.uniform(10, 75), 4),
        "productivity": round(rng.uniform(0.8, 1.2), 4),
        "expected_inflation": round(rng.uniform(0.015, 0.04), 4),
        "reserves": round(rng.uniform(10, 40), 4),
        "bank_equity": round(rng.uniform(8, 20), 4),
    }


def prompt_for(role: str, regime: str, state: dict, template: int = 0) -> str:
    regime_text = (
        "The loan-rate benchmark is an administered policy rate of 0.04; local-state pass-through is attenuated."
        if regime == "administered"
        else "There is no administered loan-rate anchor; form the rate from funding cost and local borrower/bank state."
    )
    introductions = (
        "Make one bounded economic decision.",
        "Given the identical institutional state, choose the economically feasible action.",
        "Evaluate this state and return a concise decision.",
    )
    schema = (
        "requested_fraction, maturity, purpose, expected_return, max_rate, rationale"
        if role == "firm"
        else "approval_fraction, maturity, nominal_rate, rejection_code, rationale"
    )
    if role == "firm":
        feasible = state["deposits"] + state["capital"]
        bounds = (
            f"Choose requested_fraction from 0 to 1; it is the share of the feasible "
            f"principal bound {feasible:.4f}. Maturity must be "
            "1-24; expected_return and max_rate must be 0-1; purpose must be "
            "working_capital, investment, or mixed."
        )
    else:
        requested = sum(
            item["requested_principal"] for item in state.get("applications", [])
        )
        capacity = min(requested, state["reserves"] * 0.5)
        bounds = (
            f"Choose approval_fraction from 0 to 1; it is the share of lending "
            f"capacity {capacity:.4f}. Maturity must be "
            "1-24; nominal_rate must be 0-1."
        )
    return (
        f"{introductions[template]} You are a {role}. {regime_text}\n"
        f"State: {json.dumps(state, sort_keys=True)}\n"
        f"{bounds}\nReturn JSON only with fields: {schema}."
    )


def _validate_economic_bounds(schema, decision: dict, state: dict) -> None:
    if schema is FirmDecision:
        maximum = state["deposits"] + state["capital"]
        decision["requested_principal"] = decision.pop("requested_fraction") * maximum
        if decision["requested_principal"] > maximum + 1e-9:
            raise ValueError("requested principal exceeds firm feasibility bound")
    else:
        requested = sum(
            item["requested_principal"] for item in state.get("applications", [])
        )
        maximum = min(requested, state["reserves"] * 0.5)
        decision["approved_principal"] = decision.pop("approval_fraction") * maximum
        if decision["approved_principal"] > maximum + 1e-9:
            raise ValueError("approved principal exceeds bank feasibility bound")


def rule_decision(role: str, regime: str, state: dict) -> dict:
    if role == "firm":
        leverage = state["debt"] / max(
            state["deposits"] + state["capital"] - state["debt"], 1e-9
        )
        expected_return = max(0.01, 0.10 * state["productivity"])
        requested = max(0.0, 12.0 * state["productivity"] - 2.0 * max(0.0, leverage))
        return {
            "requested_principal": requested,
            "maturity": 8,
            "purpose": "mixed",
            "expected_return": expected_return,
            "max_rate": expected_return,
            "rationale": "Frozen v0.3 rule benchmark.",
        }
    local = 0.02 * max(
        0.0, state.get("debt", 0.0) / max(state.get("capital", 1.0), 1e-9)
    )
    benchmark = 0.04 if regime == "administered" else 0.015
    pass_through = 0.25 if regime == "administered" else 1.0
    rate = (
        benchmark
        + (0.029 if regime == "administered" else 0.034)
        + pass_through * local
    )
    applications = state.get("applications", [])
    requested = sum(item["requested_principal"] for item in applications)
    return {
        "approved_principal": min(requested, state["reserves"] * 0.5),
        "maturity": 8,
        "nominal_rate": rate,
        "rejection_code": None if requested > 0 else "no_demand",
        "rationale": "Frozen v0.3 rule benchmark.",
    }


async def _call(
    client: httpx.AsyncClient,
    model: str,
    prompt: str,
    schema,
    state: dict,
    retries: int = 2,
) -> tuple[dict | None, list[dict]]:
    calls = []
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    for attempt in range(1, retries + 2):
        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                client.post(
                    "/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Return valid JSON only. Do not expose private "
                                    "reasoning."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "think": False,
                        "format": schema.model_json_schema(),
                        "options": {"temperature": 0.0, "num_predict": 256},
                    },
                ),
                timeout=30.0,
            )
            response.raise_for_status()
            raw = response.json().get("message", {}).get("content") or "{}"
            decision = schema.model_validate_json(raw).model_dump()
            _validate_economic_bounds(schema, decision, state)
            calls.append(
                {
                    "prompt_hash": prompt_hash,
                    "attempt": attempt,
                    "latency_seconds": time.perf_counter() - started,
                    "status": "valid",
                    "failure_type": None,
                }
            )
            return decision, calls
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            failure = "schema_invalid"
            calls.append(
                {
                    "prompt_hash": prompt_hash,
                    "attempt": attempt,
                    "latency_seconds": time.perf_counter() - started,
                    "status": "invalid",
                    "failure_type": failure,
                    "message": str(exc)[:300],
                }
            )
        except Exception as exc:
            calls.append(
                {
                    "prompt_hash": prompt_hash,
                    "attempt": attempt,
                    "latency_seconds": time.perf_counter() - started,
                    "status": "error",
                    "failure_type": type(exc).__name__,
                    "message": str(exc)[:300],
                }
            )
    return None, calls


async def run_robustness(
    output: str | Path,
    pairs: int = 30,
    model: str = "deepseek-r1:8b",
    base_url: str = "http://localhost:11434/v1",
    audit_states: int = 10,
) -> dict:
    if model != "deepseek-r1:8b":
        raise ValueError("the frozen v0.3 robustness model is deepseek-r1:8b")
    native_base_url = base_url.removesuffix("/v1").rstrip("/")
    client = httpx.AsyncClient(base_url=native_base_url, timeout=30.0)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    protocol = freeze_llm_protocol(output, model, pairs, audit_states)
    records = []
    if output.is_file():
        records = [json.loads(line) for line in output.read_text().splitlines() if line]
    completed_pairs = {
        record["pair"] for record in records if record["record_type"] == "pair_status"
    }

    def checkpoint() -> None:
        output.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n"
        )

    try:
        for pair in range(pairs):
            if pair in completed_pairs:
                print(f"resumed pair {pair + 1}/{pairs}", flush=True)
                continue
            pair_valid = True
            for regime in ("administered", "market"):
                for period in range(1, 4):
                    firm_decisions = []
                    for agent in range(3):
                        state = institutional_state(pair, period, agent)
                        decision, calls = await _call(
                            client,
                            model,
                            prompt_for("firm", regime, state),
                            FirmDecision,
                            state,
                        )
                        records.append(
                            {
                                "record_type": "decision",
                                "pair": pair,
                                "regime": regime,
                                "period": period,
                                "agent_id": f"firm_{agent}",
                                "role": "firm",
                                "state": state,
                                "decision": decision,
                                "rule_decision": rule_decision("firm", regime, state),
                                "calls": calls,
                            }
                        )
                        pair_valid &= decision is not None
                        if decision:
                            firm_decisions.append(decision)
                        print(
                            f"pair {pair + 1}/{pairs} {regime} period {period} "
                            f"firm {agent}: {'valid' if decision else 'failed'}",
                            flush=True,
                        )
                    for agent in range(2):
                        state = institutional_state(pair, period, agent + 3)
                        state["applications"] = firm_decisions
                        decision, calls = await _call(
                            client,
                            model,
                            prompt_for("bank", regime, state),
                            BankDecision,
                            state,
                        )
                        records.append(
                            {
                                "record_type": "decision",
                                "pair": pair,
                                "regime": regime,
                                "period": period,
                                "agent_id": f"bank_{agent}",
                                "role": "bank",
                                "state": state,
                                "decision": decision,
                                "rule_decision": rule_decision("bank", regime, state),
                                "calls": calls,
                            }
                        )
                        pair_valid &= decision is not None
                        print(
                            f"pair {pair + 1}/{pairs} {regime} period {period} "
                            f"bank {agent}: {'valid' if decision else 'failed'}",
                            flush=True,
                        )
            records.append(
                {"record_type": "pair_status", "pair": pair, "completed": pair_valid}
            )
            checkpoint()
            print(f"checkpointed pair {pair + 1}/{pairs}", flush=True)
        # Non-inferential sensitivity audit: ten fixed bank states, three
        # semantically equivalent templates, no resampling or hypothesis tests.
        completed_audit_states = {
            record["state_index"]
            for record in records
            if record["record_type"] == "prompt_audit"
        }
        for state_index in range(audit_states):
            if state_index in completed_audit_states:
                continue
            state = institutional_state(1000, 1, state_index)
            state["applications"] = [rule_decision("firm", "market", state)]
            for template in range(3):
                decision, calls = await _call(
                    client,
                    model,
                    prompt_for("bank", "market", state, template),
                    BankDecision,
                    state,
                )
                records.append(
                    {
                        "record_type": "prompt_audit",
                        "state_index": state_index,
                        "template": template,
                        "state": state,
                        "decision": decision,
                        "calls": calls,
                    }
                )
                print(
                    f"prompt audit state {state_index + 1}/{audit_states} "
                    f"template {template + 1}/3: "
                    f"{'valid' if decision else 'failed'}",
                    flush=True,
                )
            checkpoint()
    finally:
        await client.aclose()
    checkpoint()
    calls = [
        call
        for record in records
        if record["record_type"] == "decision"
        for call in record["calls"]
    ]
    completed = sum(
        record["completed"]
        for record in records
        if record["record_type"] == "pair_status"
    )
    valid_calls = sum(call["status"] == "valid" for call in calls)
    decisions = [
        record
        for record in records
        if record["record_type"] == "decision" and record["decision"] is not None
    ]

    def distribution(values):
        import numpy as np

        values = np.asarray(values, dtype=float)
        if not len(values):
            return {"n": 0}
        return {
            "n": int(len(values)),
            "mean": float(values.mean()),
            "std": float(values.std()),
            "p25": float(np.quantile(values, 0.25)),
            "median": float(np.quantile(values, 0.5)),
            "p75": float(np.quantile(values, 0.75)),
        }

    economic = {}
    for regime in ("administered", "market"):
        firm_rows = [
            row
            for row in decisions
            if row["regime"] == regime and row["role"] == "firm"
        ]
        bank_rows = [
            row
            for row in decisions
            if row["regime"] == regime and row["role"] == "bank"
        ]
        economic[regime] = {
            "requested_principal": distribution(
                [row["decision"]["requested_principal"] for row in firm_rows]
            ),
            "approved_principal": distribution(
                [row["decision"]["approved_principal"] for row in bank_rows]
            ),
            "nominal_rate": distribution(
                [row["decision"]["nominal_rate"] for row in bank_rows]
            ),
            "rule_minus_llm_rate": distribution(
                [
                    row["rule_decision"]["nominal_rate"]
                    - row["decision"]["nominal_rate"]
                    for row in bank_rows
                ]
            ),
        }
    audit_rows = [
        row
        for row in records
        if row["record_type"] == "prompt_audit" and row["decision"]
    ]
    audit_ranges = []
    for state_index in range(audit_states):
        rates = [
            row["decision"]["nominal_rate"]
            for row in audit_rows
            if row["state_index"] == state_index
        ]
        if rates:
            audit_ranges.append(max(rates) - min(rates))
    summary = {
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "protocol_fingerprint": protocol["protocol_fingerprint"],
        "temperature": 0.0,
        "reasoning": "disabled",
        "pairs_requested": pairs,
        "pairs_completed": completed,
        "completed_pair_threshold_met": completed >= 27,
        "valid_call_rate": valid_calls / len(calls) if calls else 0.0,
        "valid_call_threshold_met": (
            valid_calls / len(calls) >= 0.95 if calls else False
        ),
        "comparative_inference_allowed": (
            completed >= 27 and valid_calls / len(calls) >= 0.95 if calls else False
        ),
        "economic_distributions": economic,
        "prompt_sensitivity_rate_range": distribution(audit_ranges),
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/v0.3/llm/deepseek_r1_8b.jsonl")
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--model", default="deepseek-r1:8b")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--audit-states", type=int, default=10)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                run_robustness(
                    args.output,
                    args.pairs,
                    args.model,
                    args.base_url,
                    args.audit_states,
                )
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
