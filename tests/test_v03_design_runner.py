import json
import sqlite3

from v03.config import CalibrationBundle, ExperimentSpec, ModelParameters
from v03.concentration_addendum import addendum_cells
from v03.local_sensitivity import local_cells
from v03.design import confirmatory_design, main_cells, smoke_design
from v03.runner import run_one
from v03.consolidate import consolidate_shards, validate_consolidation


def base():
    return ExperimentSpec(
        calibration_id="test",
        parameter_set_id="test",
        scenario_id="test",
        seed_namespace="test",
        parameters=ModelParameters(n_firms=2, n_banks=2, horizon=2),
    )


def test_confirmatory_design_has_exact_predeclared_count():
    cells = confirmatory_design(base())
    assert len(cells) == 8096
    h7 = next(cell for cell in cells if cell.family == "h7")
    assert (
        h7.spec.parameters.reserve_requirement
        == h7.spec.parameters.liquidity_target_ratio
    )


def test_concentration_addendum_is_narrow_and_uses_disjoint_seeds():
    cells = addendum_cells(base())
    assert len(cells) == 150
    assert {cell.spec.parameters.deposit_concentration for cell in cells} == {
        "low",
        "high",
    }
    assert all(
        cell.spec.seed_namespace == "confirmatory-v0.4-concentration-addendum-1"
        for cell in cells
    )
    assert all(cell.spec.frozen for cell in cells)


def test_local_sensitivity_is_one_at_a_time_and_narrow():
    cells = local_cells(base())
    assert len(cells) == 1040
    assert len({cell.spec.parameter_set_id for cell in cells}) == 13
    assert all(
        cell.spec.seed_namespace == "robustness-v0.4-local-sensitivity-2"
        for cell in cells
    )
    assert all(cell.spec.frozen for cell in cells)
    seed_by_parameter = {}
    for cell in cells:
        if cell.regime.value == "administered" and cell.spec.scenario_id.endswith("baseline"):
            seed_by_parameter.setdefault(cell.spec.parameter_set_id, {})[
                cell.replication
            ] = cell.seeds
    assert len(seed_by_parameter) == 13
    assert len(
        {
            values[0].environment
            for values in seed_by_parameter.values()
        }
    ) == 1


def test_smoke_design_covers_every_scenario_regime_cell_once():
    cells = smoke_design(base())
    assert len(cells) == 488
    assert {cell.replication for cell in cells} == {0}
    assert {cell.family for cell in cells} == {
        "main",
        "h7",
        "ablation",
        "topology",
        "sensitivity",
    }


def test_runner_uses_isolated_shard_and_prevents_duplicate(tmp_path):
    cell = main_cells(base(), replications=1)[0]
    shard = tmp_path / "run.sqlite"
    args = (
        cell.spec.model_dump(mode="json"),
        cell.regime.value,
        cell.seeds.model_dump(),
        0,
        str(shard),
        None,
    )
    first = run_one(*args)
    second = run_one(*args)
    assert first["status"] == "completed"
    assert second["resumed"]
    assert first["run_id"] == second["run_id"]


def test_runner_preserves_final_cell_parameters_when_calibration_is_supplied(tmp_path):
    cell = main_cells(base(), replications=1)[0]
    treated = cell.spec.model_copy(
        update={
            "parameters": cell.spec.parameters.model_copy(
                update={"reserve_requirement": 0.08}
            )
        }
    )
    calibration = CalibrationBundle(
        calibration_id="test",
        target_moments={},
        fitted_parameters={"reserve_requirement": 0.0},
        source_data_fingerprint="data",
        transformation_fingerprint="transform",
    )
    shard = tmp_path / "treatment.sqlite"
    run_one(
        treated.model_dump(mode="json"),
        cell.regime.value,
        cell.seeds.model_dump(),
        0,
        str(shard),
        calibration.model_dump(mode="json"),
    )
    with sqlite3.connect(shard) as conn:
        payload = json.loads(
            conn.execute("SELECT config_json FROM experiment_runs").fetchone()[0]
        )
    assert payload["parameters"]["reserve_requirement"] == 0.08


def test_consolidation_builds_partitioned_parquet_and_duckdb(tmp_path):
    cells = main_cells(base(), replications=1)
    shards = tmp_path / "shards"
    shards.mkdir()
    for index, cell in enumerate(cells):
        run_one(
            cell.spec.model_dump(mode="json"),
            cell.regime.value,
            cell.seeds.model_dump(),
            0,
            str(shards / f"{index}.sqlite"),
            None,
        )
    result = consolidate_shards(
        shards,
        tmp_path / "parquet",
        tmp_path / "evidence.duckdb",
        batch_size=2,
    )
    assert result["run_count"] == 4
    resumed = consolidate_shards(
        shards,
        tmp_path / "parquet",
        tmp_path / "evidence.duckdb",
        batch_size=2,
    )
    assert resumed["run_count"] == 4
    assert (tmp_path / "evidence.duckdb").is_file()
    assert list((tmp_path / "parquet/batches").rglob("*.parquet"))
    validation = validate_consolidation(
        shards, tmp_path / "parquet", tmp_path / "evidence.duckdb"
    )
    assert validation["status"] == "ok"
