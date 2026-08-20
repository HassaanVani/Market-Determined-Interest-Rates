from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from v03.config import (
    CalibrationBundle,
    ExperimentSpec,
    RateRegime,
    SeedBundle,
)
from v03.model import InstitutionalCreditModel
from v03.schema import LedgerV03


def run_one(
    spec_payload: dict,
    regime: str,
    seed_payload: dict,
    replication: int,
    shard_path: str,
    calibration_payload: dict | None = None,
) -> dict:
    spec = ExperimentSpec.model_validate(spec_payload)
    seeds = SeedBundle.model_validate(seed_payload)
    calibration = (
        CalibrationBundle.model_validate(calibration_payload)
        if calibration_payload
        else None
    )
    # The caller constructs the final cell parameters before dispatch. Merging
    # calibration here would overwrite H7 and sensitivity treatments.
    path = Path(shard_path)
    if path.exists():
        ledger = LedgerV03(path)
        existing = ledger.conn.execute(
            "SELECT run_id,status FROM experiment_runs"
        ).fetchone()
        if existing:
            return {
                "run_id": existing[0],
                "status": existing[1],
                "shard": str(path),
                "resumed": True,
            }
    ledger = LedgerV03(path)
    model = InstitutionalCreditModel(
        spec=spec,
        regime=RateRegime(regime),
        seeds=seeds,
        ledger=ledger,
        calibration=calibration,
        replication=replication,
        shard_id=path.stem,
    )
    status = model.run()
    errors = ledger.validate(spec.parameters.horizon)
    if errors:
        ledger.update_run(
            model.run_id, status="invalid", failure_reason="; ".join(errors)
        )
        status = "invalid"
    ledger.close()
    return {
        "run_id": model.run_id,
        "status": status,
        "shard": str(path),
        "resumed": False,
    }


def run_cells(
    cells,
    output_dir: str | Path,
    calibration: CalibrationBundle | None = None,
    workers: int | None = None,
) -> list[dict]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    tasks = []
    for index, cell in enumerate(cells):
        shard = (
            output
            / f"{cell.family}-{index:05d}-{cell.regime.value}-r{cell.replication:04d}.sqlite"
        )
        tasks.append(
            (
                cell.spec.model_dump(mode="json"),
                cell.regime.value,
                cell.seeds.model_dump(),
                cell.replication,
                str(shard),
                calibration.model_dump(mode="json") if calibration else None,
            )
        )
    workers = workers or max(1, min(os.cpu_count() or 1, 8))
    if workers == 1:
        return [run_one(*task) for task in tasks]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, *task) for task in tasks]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def write_run_manifest(results: list[dict], path: str | Path) -> None:
    payload = {"runs": sorted(results, key=lambda x: x["shard"])}
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
