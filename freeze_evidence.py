"""Validate and hash the specification-0.2 evidence package."""

import csv
import hashlib
import json
import sqlite3
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from engine.provenance import SOURCE_DIRECTORIES, SOURCE_FILES, source_fingerprint

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
RULE_DATABASE = EVIDENCE / "paper_evidence_v0_2.sqlite"
LLM_DATABASE = EVIDENCE / "deepseek8b_pilot_v0_2_final.sqlite"
RULE_SOURCE_ARCHIVE = EVIDENCE / "dgp_source_b15fc02ecf92a7e3.tar.gz"
LLM_SOURCE_ARCHIVE = EVIDENCE / "dgp_source_c89b0b80fef6e979.tar.gz"
RULE_FINGERPRINT = "b15fc02ecf92a7e33e998f309e41ca44dd7aac0ef46a55bf531c23862e234898"
LLM_FINGERPRINT = "c89b0b80fef6e97996cc36a16b6babf2cf9afb0e8a2a12aab375ea514ca3d62a"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_archived_dgp(path):
    explicit = set(SOURCE_FILES)
    directory_prefixes = tuple(f"{name}/" for name in SOURCE_DIRECTORIES)
    members = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            name = member.name.removeprefix("./")
            if Path(name).name.startswith("._"):
                continue
            included = name in explicit or (
                name.endswith(".py") and name.startswith(directory_prefixes)
            )
            if included and member.isfile():
                members[name] = archive.extractfile(member).read()
    digest = hashlib.sha256()
    for name in sorted(members):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(members[name])
        digest.update(b"\0")
    return digest.hexdigest()


def load_configs(connection):
    rows = connection.execute(
        "SELECT run_id, status, failure_reason, config_json FROM experiment_runs"
    ).fetchall()
    return [
        {
            "run_id": row[0],
            "status": row[1],
            "failure_reason": row[2],
            "config": json.loads(row[3]),
        }
        for row in rows
    ]


def audit_periods(connection, rows):
    for row in rows:
        run_id = row["run_id"]
        horizon = row["config"]["horizon"]
        periods = [
            value[0]
            for value in connection.execute(
                "SELECT period FROM period_macro WHERE run_id = ? ORDER BY period",
                (run_id,),
            )
        ]
        if periods != list(range(horizon + 1)):
            raise ValueError(f"Incomplete period sequence for {run_id}: {periods}")


def audit_rule_database():
    connection = sqlite3.connect(RULE_DATABASE)
    rows = load_configs(connection)
    if len(rows) != 480 or any(row["status"] != "completed" for row in rows):
        raise ValueError("Rule database must contain 480 completed runs")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Rule database has foreign-key violations")
    if connection.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] != 0:
        raise ValueError("Rule database unexpectedly contains LLM calls")
    if {row["config"]["source_fingerprint"] for row in rows} != {RULE_FINGERPRINT}:
        raise ValueError("Rule DGP fingerprint mismatch")
    if {row["config"]["specification_version"] for row in rows} != {"0.2"}:
        raise ValueError("Rule specification version mismatch")
    if {row["config"]["behavior_mode"] for row in rows} != {"rule"}:
        raise ValueError("Rule database contains a non-rule behavior cell")

    expected = {
        ("h2_baseline", "administered"): 30,
        ("h2_baseline", "market"): 30,
        ("h3_baseline", "administered"): 30,
        ("h3_baseline", "market"): 30,
        ("h3_demand", "administered"): 30,
        ("h3_demand", "market"): 30,
        ("h7_abundant_unavailable", "administered"): 30,
        ("h7_abundant_unavailable", "market"): 30,
        ("h7_scarce_unavailable", "administered"): 40,
        ("h7_scarce_unavailable", "market"): 40,
        ("h7_scarce_penalty", "administered"): 40,
        ("h7_scarce_penalty", "market"): 40,
        ("h7_scarce_limited", "administered"): 40,
        ("h7_scarce_limited", "market"): 40,
    }
    observed = Counter(
        (
            row["config"]["scenario_name"],
            row["config"]["rate_regime"],
        )
        for row in rows
    )
    if observed != Counter(expected):
        raise ValueError(f"Unexpected rule cell counts: {observed}")
    audit_periods(connection, rows)
    period_rows = connection.execute("SELECT COUNT(*) FROM period_macro").fetchone()[0]
    connection.close()
    cells = {
        f"{scenario}:{regime}": count for (scenario, regime), count in expected.items()
    }
    return {"runs": len(rows), "period_rows": period_rows, "cells": cells}


def audit_llm_database():
    connection = sqlite3.connect(LLM_DATABASE)
    rows = load_configs(connection)
    if len(rows) != 6 or any(row["status"] != "completed" for row in rows):
        raise ValueError("LLM database must contain six completed runs")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("LLM database has foreign-key violations")
    if {row["config"]["source_fingerprint"] for row in rows} != {LLM_FINGERPRINT}:
        raise ValueError("LLM DGP fingerprint mismatch")
    if {row["config"]["llm_model"] for row in rows} != {"deepseek-r1:8b"}:
        raise ValueError("Unexpected LLM model")
    if {row["config"]["llm_reasoning_effort"] for row in rows} != {"none"}:
        raise ValueError("Unexpected LLM reasoning configuration")
    call_statuses = connection.execute(
        "SELECT status, attempt, COUNT(*) FROM llm_calls GROUP BY status, attempt"
    ).fetchall()
    if call_statuses != [("success", 0, 42)]:
        raise ValueError(f"Unexpected LLM call audit: {call_statuses}")
    audit_periods(connection, rows)
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "period_macro",
            "credit_applications",
            "bank_offers",
            "loan_contracts",
            "llm_calls",
        )
    }
    connection.close()
    return {"runs": len(rows), **counts}


def audit_power():
    path = EVIDENCE / "analysis_v0_2" / "power_analysis.csv"
    rows = list(csv.DictReader(path.open()))
    selected = []
    for row in rows:
        is_primary = (
            row["hypothesis"] == "H2"
            or (
                row["hypothesis"] == "H3"
                and row["regime"] == "market_minus_administered"
                and row["outcome"] in {"new_credit", "output", "final_credit"}
            )
            or (
                row["hypothesis"] == "H7"
                and (
                    "penalty_minus_unavailable" in row["regime"]
                    or "penalty_minus_limited" in row["regime"]
                )
                and row["outcome"] in {"new_credit", "liquidity_shortfall"}
            )
        )
        if not is_primary:
            continue
        required = row["required_n_80pct"]
        if required and int(row["pilot_n"]) < int(required):
            raise ValueError(f"Underpowered primary estimand: {row}")
        selected.append(row)
    if len(selected) != 16:
        raise ValueError(f"Expected 16 primary power checks, found {len(selected)}")
    return selected


def package_files():
    paths = [
        RULE_DATABASE,
        LLM_DATABASE,
        RULE_SOURCE_ARCHIVE,
        LLM_SOURCE_ARCHIVE,
        ROOT / "analyze_evidence.py",
        ROOT / "analyze_llm_pilot.py",
        ROOT / "README.md",
        ROOT / "docs" / "research_design.md",
        ROOT / "docs" / "evidence_protocol_v0.2.md",
        ROOT / "docs" / "results_v0.2.md",
        EVIDENCE / "README.md",
    ]
    paths.extend(sorted((EVIDENCE / "analysis_v0_2").glob("*")))
    paths.extend(sorted((EVIDENCE / "llm_analysis_v0_2").glob("*")))
    test_report = EVIDENCE / "test_report_v0_2.txt"
    if test_report.exists():
        paths.append(test_report)
    return paths


def freeze():
    archived_fingerprint = fingerprint_archived_dgp(RULE_SOURCE_ARCHIVE)
    if archived_fingerprint != RULE_FINGERPRINT:
        raise ValueError("Archived rule source does not reproduce its fingerprint")
    archived_llm_fingerprint = fingerprint_archived_dgp(LLM_SOURCE_ARCHIVE)
    if archived_llm_fingerprint != LLM_FINGERPRINT:
        raise ValueError("Archived LLM source does not reproduce its fingerprint")
    if source_fingerprint() != LLM_FINGERPRINT:
        raise ValueError("Current source does not reproduce the final LLM fingerprint")

    rule_audit = audit_rule_database()
    llm_audit = audit_llm_database()
    power = audit_power()
    artifacts = {
        str(path.relative_to(ROOT)): {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in package_files()
    }
    manifest = {
        "manifest_version": "0.2",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "rule_dgp_fingerprint": RULE_FINGERPRINT,
        "llm_dgp_fingerprint": LLM_FINGERPRINT,
        "archived_rule_dgp_verified": True,
        "archived_llm_dgp_verified": True,
        "rule_audit": rule_audit,
        "llm_audit": llm_audit,
        "primary_power_checks": power,
        "artifacts": artifacts,
        "excluded_from_inference": [
            "evidence/diagnostics/",
        ],
    }
    output = EVIDENCE / "manifest_v0_2.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Frozen evidence manifest: {output}")
    return output


if __name__ == "__main__":
    freeze()
