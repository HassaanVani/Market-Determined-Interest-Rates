from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from v03.config import (
    ExperimentSpec,
    ModelParameters,
    load_calibration_bundle,
    load_experiment_spec,
)
from v03.calibration import assert_calibration_gate
from v03.consolidate import (
    consolidate_shards,
    validate_consolidation,
    validate_shard,
)
from v03.data_pipeline import (
    clean_bank_panel,
    load_dictionary,
    standardize_call_report,
    verify_source_manifest,
    write_panel_outputs,
)
from v03.download_sources import build_call_report_input
from v03.survey_extract import extract_fr2028d_business_panel
from v03.design import confirmatory_design, h7_cells, main_cells, smoke_design
from v03.runner import run_cells, write_run_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "configs/v0.3/main.yaml"


def command_data(args) -> None:
    if args.input:
        raw = pd.read_csv(args.input)
        dictionary = load_dictionary(args.dictionary)
        standardized = standardize_call_report(raw, dictionary)
    else:
        standardized = build_call_report_input(args.raw_dir)
    clean, exclusions, missingness = clean_bank_panel(standardized)
    write_panel_outputs(clean, exclusions, missingness, args.output)
    business, business_exclusions = extract_fr2028d_business_panel(
        Path(args.raw_dir) / "fr2028d/aggregate_2026q1.xlsx",
        Path(args.raw_dir) / "fred/CPIAUCSL_2022_2025.csv",
        Path(args.raw_dir) / "fred/DPRIME_2022_2025.csv",
    )
    output = Path(args.output)
    business.to_parquet(output / "business_loans.parquet", index=False)
    business_exclusions.to_csv(output / "business_loan_exclusions.csv", index=False)
    print(f"Wrote calibration/validation data to {Path(args.output).resolve()}")


def _calibration(path: str | None):
    return load_calibration_bundle(path) if path else None


def _calibrated_spec(spec: ExperimentSpec, calibration: CalibrationBundle | None):
    if calibration is None:
        return spec
    values = spec.parameters.model_dump()
    values.update(
        {
            key: value
            for key, value in calibration.fitted_parameters.items()
            if key in ModelParameters.model_fields
        }
    )
    return spec.model_copy(
        update={"parameters": ModelParameters.model_validate(values)}
    )


def command_pilot(args) -> None:
    calibration = _calibration(args.calibration)
    spec = _calibrated_spec(load_experiment_spec(args.spec), calibration).model_copy(
        update={"seed_namespace": "pilot-v0.3", "frozen": False}
    )
    cells = main_cells(spec, replications=args.replications)
    results = run_cells(cells, args.output, calibration, args.workers)
    write_run_manifest(results, Path(args.output) / "run_manifest.json")
    print(
        json.dumps(
            {
                "planned": len(cells),
                "completed": sum(r["status"] == "completed" for r in results),
            },
            indent=2,
        )
    )


def command_h7_pilot(args) -> None:
    calibration = _calibration(args.calibration)
    spec = _calibrated_spec(load_experiment_spec(args.spec), calibration).model_copy(
        update={"seed_namespace": "pilot-h7-v0.3", "frozen": False}
    )
    cells = h7_cells(spec, replications=args.replications)
    results = run_cells(cells, args.output, calibration, args.workers)
    write_run_manifest(results, Path(args.output) / "run_manifest.json")
    print(
        json.dumps(
            {
                "planned": len(cells),
                "completed": sum(r["status"] == "completed" for r in results),
            },
            indent=2,
        )
    )


def command_smoke(args) -> None:
    calibration = _calibration(args.calibration)
    spec = _calibrated_spec(load_experiment_spec(args.spec), calibration).model_copy(
        update={"seed_namespace": "smoke-v0.3", "frozen": False}
    )
    cells = smoke_design(spec)
    results = run_cells(cells, args.output, calibration, args.workers)
    write_run_manifest(results, Path(args.output) / "run_manifest.json")
    print(
        json.dumps(
            {
                "planned": len(cells),
                "completed": sum(r["status"] == "completed" for r in results),
            },
            indent=2,
        )
    )


def command_freeze(args) -> None:
    spec = load_experiment_spec(args.spec)
    calibration = load_calibration_bundle(args.calibration)
    assert_calibration_gate(calibration)
    values = spec.parameters.model_dump()
    values.update(
        {
            key: value
            for key, value in calibration.fitted_parameters.items()
            if key in ModelParameters.model_fields
        }
    )
    spec = spec.model_copy(
        update={"parameters": ModelParameters.model_validate(values)}
    )
    frozen = spec.model_copy(update={"frozen": True})
    destination = Path(args.output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite frozen protocol: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = frozen.model_dump(mode="json")
    payload["config_fingerprint"] = frozen.fingerprint()
    payload["planned_rule_runs"] = len(confirmatory_design(frozen))
    payload["calibration_fingerprint"] = calibration.fingerprint()
    payload["data_fingerprint"] = calibration.source_data_fingerprint
    pilot_power_path = ROOT / "evidence/v0.3/pilot_analysis/power_report.json"
    h7_power_path = ROOT / "evidence/v0.3/pilot_h7c_analysis/h7_power_report.json"
    if not pilot_power_path.is_file() or not h7_power_path.is_file():
        raise FileNotFoundError(
            "pilot power reports must exist before specification freeze"
        )
    pilot_power = json.loads(pilot_power_path.read_text())
    h7_power = json.loads(h7_power_path.read_text())
    if pilot_power.get("required_main_matched_seeds") != 809:
        raise ValueError(
            "main replication count does not match the frozen pilot power result"
        )
    if not h7_power.get("planned_h7_design_is_adequate"):
        raise ValueError("H7 pilot power gate failed")
    payload["power_design"] = {
        "target_power": 0.90,
        "main_matched_seeds": 809,
        "main_required_by_pilot": pilot_power["required_main_matched_seeds"],
        "h7_matched_seeds": 40,
        "h7_required_by_pilot": h7_power["required_h7_pairs_per_cell"],
        "planning_multiplicity": "Bonferroni 0.025 per outcome; final inference uses Holm",
    }
    payload["timing"] = {
        "horizon": frozen.parameters.horizon,
        "demand_shock_start_period": 8,
        "demand_shock_duration": 4,
        "cumulative_response_window": [8, frozen.parameters.horizon - 1],
    }
    payload["seed_namespaces"] = {
        "pilot_main": "pilot-v0.3",
        "pilot_h7": "pilot-h7-v0.3",
        "smoke": "smoke-v0.3",
        "confirmatory": frozen.seed_namespace,
    }
    payload["estimands"] = {
        "H2": ["credit_weighted_productivity", "unfunded_demand_share"],
        "H3": ["cumulative_new_credit", "cumulative_output"],
        "H7": ["cumulative_new_credit", "unresolved_liquidity_shortfall"],
    }
    payload["exclusions"] = [
        "failed or incomplete horizons",
        "fingerprint mismatch",
        "foreign-key violation",
    ]
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Frozen protocol: {destination.resolve()}")


def command_confirm(args) -> None:
    protocol = json.loads(Path(args.protocol).read_text())
    if not protocol.get("frozen"):
        raise ValueError("confirmatory runs require a frozen v0.3 protocol")
    allowed = set(ExperimentSpec.model_fields)
    spec = ExperimentSpec.model_validate(
        {key: value for key, value in protocol.items() if key in allowed}
    )
    if spec.fingerprint() != protocol["config_fingerprint"]:
        raise ValueError("frozen protocol fingerprint mismatch")
    cells = confirmatory_design(spec)
    if protocol.get("planned_rule_runs") != len(cells):
        raise ValueError("frozen protocol run count does not match the design")
    results = run_cells(
        cells, args.output, _calibration(args.calibration), args.workers
    )
    write_run_manifest(results, Path(args.output) / "run_manifest.json")
    print(
        json.dumps(
            {
                "planned": len(cells),
                "completed": sum(r["status"] == "completed" for r in results),
            },
            indent=2,
        )
    )


def command_consolidate(args) -> None:
    result = consolidate_shards(
        args.shards,
        args.output,
        args.catalog,
        batch_size=args.batch_size,
        max_shards=args.max_shards,
    )
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "run_count": result["run_count"],
                "batch_size": result["batch_size"],
                "compression": result["compression"],
            },
            indent=2,
        )
    )


def command_verify_consolidation(args) -> None:
    report = validate_consolidation(args.shards, args.output, args.catalog)
    print(json.dumps(report, indent=2))


def command_verify(args) -> None:
    sources_verified = 0
    if Path(args.source_manifest).is_file():
        sources_verified = len(verify_source_manifest(args.source_manifest))
    shards = sorted(Path(args.shards).glob("*.sqlite")) if args.shards else []
    errors = []
    for shard in shards:
        try:
            validate_shard(shard)
        except Exception as exc:
            errors.append(f"{shard}: {exc}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        json.dumps(
            {
                "verified_sources": sources_verified,
                "verified_shards": len(shards),
                "status": "ok",
            }
        )
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Specification 0.3 research pipeline")
    sub = result.add_subparsers(dest="command", required=True)
    data = sub.add_parser("data")
    data.add_argument("--input")
    data.add_argument("--raw-dir", default="data/raw/v0.3")
    data.add_argument(
        "--dictionary", default=str(ROOT / "configs/v0.3/data_dictionary.yaml")
    )
    data.add_argument("--output", default="data/derived/v0.3")
    data.set_defaults(func=command_data)
    for name, func in (
        ("pilot", command_pilot),
        ("pilot-h7", command_h7_pilot),
    ):
        item = sub.add_parser(name)
        item.add_argument("--spec", default=str(DEFAULT_SPEC))
        item.add_argument("--output", default=f"evidence/v0.3/{name}_shards")
        item.add_argument("--calibration")
        item.add_argument("--workers", type=int, default=1)
        item.add_argument("--replications", type=int, default=20)
        item.set_defaults(func=func)
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--spec", default=str(DEFAULT_SPEC))
    smoke.add_argument("--output", default="evidence/v0.3/smoke_shards")
    smoke.add_argument("--calibration", default="calibration/v0.3/recent_us.json")
    smoke.add_argument("--workers", type=int, default=1)
    smoke.set_defaults(func=command_smoke)
    freeze = sub.add_parser("freeze-spec")
    freeze.add_argument("--spec", default=str(DEFAULT_SPEC))
    freeze.add_argument("--calibration", default="calibration/v0.3/recent_us.json")
    freeze.add_argument("--output", default="evidence/v0.3/evidence_protocol_v0.3.json")
    freeze.set_defaults(func=command_freeze)
    confirm = sub.add_parser("confirm")
    confirm.add_argument(
        "--protocol", default="evidence/v0.3/evidence_protocol_v0.3.json"
    )
    confirm.add_argument("--output", default="evidence/v0.3/confirmatory_shards")
    confirm.add_argument("--calibration")
    confirm.add_argument("--workers", type=int, default=1)
    confirm.set_defaults(func=command_confirm)
    consolidate = sub.add_parser("consolidate")
    consolidate.add_argument("--shards", default="evidence/v0.3/confirmatory_shards")
    consolidate.add_argument("--output", default="evidence/v0.3/parquet")
    consolidate.add_argument("--catalog", default="evidence/v0.3/evidence.duckdb")
    consolidate.add_argument("--batch-size", type=int, default=5)
    consolidate.add_argument("--max-shards", type=int)
    consolidate.set_defaults(func=command_consolidate)
    verify_consolidation = sub.add_parser("verify-consolidation")
    verify_consolidation.add_argument(
        "--shards", default="evidence/v0.3/confirmatory_shards"
    )
    verify_consolidation.add_argument("--output", default="evidence/v0.3/parquet")
    verify_consolidation.add_argument(
        "--catalog", default="evidence/v0.3/evidence.duckdb"
    )
    verify_consolidation.set_defaults(func=command_verify_consolidation)
    verify = sub.add_parser("verify")
    verify.add_argument("--shards")
    verify.add_argument(
        "--source-manifest", default="data/manifests/source_manifest_v0.3.json"
    )
    verify.set_defaults(func=command_verify)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
