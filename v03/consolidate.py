from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from v03.schema import SCHEMA_VERSION

EVENT_TABLES = (
    "experiment_runs",
    "parameter_sets",
    "calibration_targets",
    "credit_applications",
    "bank_offers",
    "loan_contracts",
    "loan_events",
    "incumbent_portfolio_events",
    "authority_money_events",
    "deposit_funding_events",
    "firm_states",
    "bank_states",
    "period_macro",
    "liquidity_events",
    "bank_resolution_events",
    "llm_calls",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_shard(path: str | Path) -> dict:
    path = Path(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    version = conn.execute("SELECT schema_version FROM schema_metadata").fetchone()
    if version is None or version[0] != SCHEMA_VERSION:
        raise ValueError(f"{path}: incompatible schema")
    fk = list(conn.execute("PRAGMA foreign_key_check"))
    if fk:
        raise ValueError(f"{path}: {len(fk)} foreign-key violations")
    runs = [dict(row) for row in conn.execute("SELECT * FROM experiment_runs")]
    if len(runs) != 1:
        raise ValueError(f"{path}: expected exactly one run, found {len(runs)}")
    run = runs[0]
    if run["status"] != "completed":
        raise ValueError(f"{path}: run status is {run['status']}")
    horizon = json.loads(run["config_json"])["parameters"]["horizon"]
    periods = conn.execute(
        "SELECT COUNT(*) FROM period_macro WHERE run_id=?", (run["run_id"],)
    ).fetchone()[0]
    if periods != horizon:
        raise ValueError(f"{path}: incomplete horizon {periods}/{horizon}")
    conn.close()
    return run


def _arrow_schema(conn: sqlite3.Connection, table: str, pa):
    sqlite_types = {
        "INTEGER": pa.int64(),
        "REAL": pa.float64(),
        "TEXT": pa.string(),
        "BLOB": pa.binary(),
    }
    fields = []
    for row in conn.execute(f"PRAGMA table_info({table})"):
        declared = str(row[2]).upper().split("(", 1)[0]
        fields.append(pa.field(row[1], sqlite_types.get(declared, pa.string())))
    names = {field.name for field in fields}
    if "run_id" in names:
        fields.extend(
            (
                pa.field("specification", pa.string()),
                pa.field("scenario", pa.string()),
                pa.field("regime", pa.string()),
                pa.field("seed", pa.int64()),
            )
        )
    return pa.schema(fields)


def _batch_manifest(path: Path) -> dict:
    manifest = path / "batch_manifest.json"
    if not manifest.is_file():
        raise ValueError(f"completed batch lacks manifest: {path}")
    return json.loads(manifest.read_text())


def consolidate_shards(
    shard_dir: str | Path,
    output_dir: str | Path,
    catalog_path: str | Path,
    batch_size: int = 5,
    max_shards: int | None = None,
) -> dict:
    try:
        import pyarrow as pa
        import pyarrow.dataset as ds
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "pyarrow and duckdb are required for evidence consolidation"
        ) from exc
    shard_paths = sorted(Path(shard_dir).glob("*.sqlite"))
    if max_shards is not None:
        if max_shards < 1:
            raise ValueError("max_shards must be positive")
        shard_paths = shard_paths[:max_shards]
    if not shard_paths:
        raise FileNotFoundError(f"no SQLite shards in {shard_dir}")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    batches_dir = output / "batches"
    staging_dir = output / "_staging"
    batches_dir.mkdir(exist_ok=True)
    staging_dir.mkdir(exist_ok=True)
    seen_run_ids = set()
    shard_manifest = []
    parquet_format = ds.ParquetFileFormat()
    write_options = parquet_format.make_write_options(
        compression="zstd", compression_level=6, use_dictionary=True
    )
    total_batches = (len(shard_paths) + batch_size - 1) // batch_size
    for batch_index, start in enumerate(range(0, len(shard_paths), batch_size)):
        batch_paths = shard_paths[start : start + batch_size]
        final_batch = batches_dir / f"batch-{batch_index:05d}"
        expected_sources = [path.as_posix() for path in batch_paths]
        if final_batch.is_dir():
            existing = _batch_manifest(final_batch)
            if existing["source_paths"] != expected_sources:
                raise ValueError(f"resume mismatch in {final_batch}")
            for item in existing["shards"]:
                if item["run_id"] in seen_run_ids:
                    raise ValueError(f"duplicate run_id: {item['run_id']}")
                seen_run_ids.add(item["run_id"])
                shard_manifest.append(item)
            print(f"resumed batch {batch_index + 1:,}/{total_batches:,}", flush=True)
            continue

        stage = staging_dir / f"batch-{batch_index:05d}.partial"
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        table_frames = {table: [] for table in EVENT_TABLES}
        table_schemas = {}
        batch_shards = []
        for shard in batch_paths:
            run = validate_shard(shard)
            if run["run_id"] in seen_run_ids:
                raise ValueError(f"duplicate run_id across shards: {run['run_id']}")
            seen_run_ids.add(run["run_id"])
            item = {
                "path": shard.as_posix(),
                "sha256": _sha256(shard),
                "run_id": run["run_id"],
            }
            batch_shards.append(item)
            conn = sqlite3.connect(shard)
            for table in EVENT_TABLES:
                table_schemas.setdefault(table, _arrow_schema(conn, table, pa))
                frame = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                if frame.empty:
                    continue
                if "run_id" in frame:
                    frame["specification"] = run["specification_id"]
                    frame["scenario"] = run["scenario_id"]
                    frame["regime"] = run["rate_regime"]
                    frame["seed"] = run["environment_seed"]
                table_frames[table].append(frame)
            conn.close()
        for table, frames in table_frames.items():
            if not frames:
                continue
            frame = pd.concat(frames, ignore_index=True)
            schema = table_schemas[table]
            arrow_table = pa.Table.from_pandas(
                frame, schema=schema, preserve_index=False, safe=False
            )
            partition_fields = [
                schema.field(name)
                for name in ("specification", "scenario", "regime", "seed")
                if name in schema.names
            ]
            ds.write_dataset(
                arrow_table,
                stage / table,
                format=parquet_format,
                file_options=write_options,
                partitioning=ds.partitioning(
                    pa.schema(partition_fields), flavor="hive"
                ),
                max_open_files=32,
                existing_data_behavior="error",
            )
        batch_payload = {
            "batch_index": batch_index,
            "source_paths": expected_sources,
            "shards": batch_shards,
        }
        (stage / "batch_manifest.json").write_text(
            json.dumps(batch_payload, indent=2, sort_keys=True) + "\n"
        )
        stage.replace(final_batch)
        shard_manifest.extend(batch_shards)
        print(f"completed batch {batch_index + 1:,}/{total_batches:,}", flush=True)
    catalog = Path(catalog_path)
    catalog.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(catalog))
    for table in EVENT_TABLES:
        if any(batches_dir.glob(f"*/{table}/**/*.parquet")):
            glob = (batches_dir / "*" / table / "**" / "*.parquet").as_posix()
            connection.execute(
                f"CREATE OR REPLACE VIEW {table} AS "
                f"SELECT * FROM read_parquet('{glob}', "
                "hive_partitioning=true, union_by_name=true)"
            )
    connection.close()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_size": batch_size,
        "compression": "zstd-6",
        "shards": shard_manifest,
        "run_count": len(seen_run_ids),
    }
    manifest_path = output / "consolidation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def validate_consolidation(
    shard_dir: str | Path, output_dir: str | Path, catalog_path: str | Path
) -> dict:
    import duckdb

    shard_paths = sorted(Path(shard_dir).glob("*.sqlite"))
    output = Path(output_dir)
    manifest = json.loads((output / "consolidation_manifest.json").read_text())
    manifest_paths = [item["path"] for item in manifest["shards"]]
    expected_paths = [path.as_posix() for path in shard_paths]
    if manifest_paths != expected_paths:
        raise ValueError("consolidation manifest does not match source shard set")
    run_ids = [item["run_id"] for item in manifest["shards"]]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("duplicate run IDs in consolidation manifest")

    source_counts = {table: 0 for table in EVENT_TABLES}
    for index, shard in enumerate(shard_paths, start=1):
        conn = sqlite3.connect(shard)
        for table in EVENT_TABLES:
            source_counts[table] += conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        conn.close()
        if index % 500 == 0 or index == len(shard_paths):
            print(f"counted {index:,}/{len(shard_paths):,} source shards", flush=True)

    catalog = duckdb.connect(str(catalog_path), read_only=True)
    available = {
        row[0]
        for row in catalog.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' AND table_type='VIEW'"
        ).fetchall()
    }
    parquet_counts = {
        table: (
            catalog.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if table in available
            else 0
        )
        for table in EVENT_TABLES
    }
    incomplete_horizons = catalog.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT e.run_id, "
        "CAST(json_extract(e.config_json, '$.parameters.horizon') AS INTEGER) AS horizon, "
        "COUNT(p.period) AS periods "
        "FROM experiment_runs e LEFT JOIN period_macro p USING(run_id) "
        "GROUP BY e.run_id, e.config_json HAVING periods != horizon)"
    ).fetchone()[0]
    catalog.close()
    mismatches = {
        table: {"source": source_counts[table], "parquet": parquet_counts[table]}
        for table in EVENT_TABLES
        if source_counts[table] != parquet_counts[table]
    }
    if mismatches:
        raise ValueError(f"source/Parquet row-count mismatch: {mismatches}")
    if incomplete_horizons:
        raise ValueError(
            f"{incomplete_horizons} consolidated runs have incomplete horizons"
        )
    report = {
        "status": "ok",
        "run_count": len(run_ids),
        "batch_count": len(list((output / "batches").glob("batch-*"))),
        "incomplete_horizons": incomplete_horizons,
        "source_counts": source_counts,
        "parquet_counts": parquet_counts,
    }
    (output / "consolidation_validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report
