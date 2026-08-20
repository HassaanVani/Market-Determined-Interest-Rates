import asyncio
import hashlib
import json
import time


async def call_structured_llm(
    model,
    agent_id,
    task_type,
    client,
    messages,
    response_model,
):
    """Call the local LLM with bounded retries and complete attempt metadata."""
    example_values = {
        "decision_rationale": "Brief economic rationale.",
        "loan_principal_requested": 10.0,
        "max_acceptable_nominal_rate": 0.05,
        "decision_status": "economic",
        "approved": True,
        "offered_nominal_rate": 0.04,
    }
    example = {
        field_name: example_values[field_name]
        for field_name in response_model.model_fields
    }
    schema_instruction = {
        "role": "system",
        "content": (
            "Return only one JSON object with concrete decision values. "
            "Do not return a schema, properties, descriptions, markdown, or "
            "explanatory text. Use exactly these keys and value types, replacing "
            "the example values with your decision: "
            f"{json.dumps(example, separators=(',', ':'))}"
        ),
    }
    request_messages = [*messages, schema_instruction]
    prompt_payload = json.dumps(
        request_messages,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    prompt_hash = hashlib.sha256(prompt_payload.encode("utf-8")).hexdigest()
    period = model.schedule.steps + 1
    last_error = None

    for attempt in range(model.llm_max_retries + 1):
        started = time.perf_counter()
        try:
            completion = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model.llm_model,
                    messages=request_messages,
                    response_format={"type": "json_object"},
                    temperature=model.llm_temperature,
                    max_tokens=model.llm_max_tokens,
                    reasoning_effort=model.llm_reasoning_effort,
                ),
                timeout=model.llm_timeout_seconds,
            )
            content = completion.choices[0].message.content or ""
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                content = content.rsplit("```", 1)[0].strip()
            first_brace = content.find("{")
            last_brace = content.rfind("}")
            if first_brace < 0 or last_brace < first_brace:
                excerpt = content[:500].replace("\n", " ")
                raise ValueError(
                    "LLM response did not contain a JSON object; "
                    f"response excerpt: {excerpt!r}"
                )
            payload = json.loads(content[first_brace : last_brace + 1])
            result = response_model.model_validate(payload)
            latency = time.perf_counter() - started
            call_id = f"{model.run_id}-p{period}-{agent_id}-" f"{task_type}-a{attempt}"
            model.ledger.record_llm_call(
                call_id=call_id,
                run_id=model.run_id,
                period=period,
                agent_id=agent_id,
                task_type=task_type,
                provider="ollama",
                model_id=model.llm_model,
                prompt_version=model.prompt_version,
                prompt_hash=prompt_hash,
                temperature=model.llm_temperature,
                attempt=attempt,
                latency_seconds=latency,
                status="success",
            )
            return result, None
        except Exception as exc:
            latency = time.perf_counter() - started
            last_error = exc
            call_id = f"{model.run_id}-p{period}-{agent_id}-" f"{task_type}-a{attempt}"
            model.ledger.record_llm_call(
                call_id=call_id,
                run_id=model.run_id,
                period=period,
                agent_id=agent_id,
                task_type=task_type,
                provider="ollama",
                model_id=model.llm_model,
                prompt_version=model.prompt_version,
                prompt_hash=prompt_hash,
                temperature=model.llm_temperature,
                attempt=attempt,
                latency_seconds=latency,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc)[:1000],
            )

    return None, last_error
