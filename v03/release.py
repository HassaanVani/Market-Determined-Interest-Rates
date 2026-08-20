from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path

from v03.provenance import sha256_file, utc_now

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "evidence" / "release" / "v0.3"
SOURCE_DIRS = ("v03", "engine", "models", "database", "configs", "calibration", "docs")
SOURCE_FILES = (
    "Makefile",
    "README.md",
    "requirements.txt",
    "requirements-v0.3.txt",
    "environment-v0.3.lock",
    ".gitignore",
)
PURGE_CANDIDATES = (
    "evidence/v0.3/confirmatory_shards",
    "evidence/v0.3/smoke_shards",
    "evidence/v0.3/pilot_shards",
    "evidence/v0.3/pilot-h7_shards",
    "evidence/v0.3/pilot-h7b_shards",
    "evidence/v0.3/pilot-h7c_shards",
    "evidence/v0.3/pilot-h7-accidental-main",
    "evidence/v0.3/pilot-h7-smoke",
    "evidence/v0.3/pilot-h7-smoke2",
    "evidence/v0.3/pilot_h7_parquet",
    "evidence/v0.3/pilot_h7b_parquet",
    "evidence/v0.4/concentration_shards",
    "evidence/v0.4/local_sensitivity_shards",
    "evidence/v0.4/local_sensitivity_v2_shards",
)


def archive_run_manifests(path: Path) -> dict:
    records = []
    for name in PURGE_CANDIDATES:
        source = ROOT / name / "run_manifest.json"
        if not source.is_file():
            continue
        records.append(
            {
                "source_path": source.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(source),
                "manifest": json.loads(source.read_text()),
            }
        )
    payload = {
        "created_at": utc_now(),
        "purpose": "Preserve run status and shard-path records before approved deletion of redundant SQLite directories.",
        "source_manifests": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {"path": path.relative_to(ROOT).as_posix(), "manifests": len(records)}


def _source_paths() -> list[Path]:
    paths = []
    for name in SOURCE_FILES:
        path = ROOT / name
        if path.is_file():
            paths.append(path)
    for name in SOURCE_DIRS:
        directory = ROOT / name
        if directory.is_dir():
            paths.extend(
                path
                for path in directory.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".sqlite", ".duckdb"}
            )
    return sorted(set(paths))


def source_snapshot(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as archive:
                for source in _source_paths():
                    info = archive.gettarinfo(str(source), source.relative_to(ROOT).as_posix())
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    with source.open("rb") as handle:
                        archive.addfile(info, handle)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "files": len(_source_paths()),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _release_artifacts(snapshot: Path) -> list[Path]:
    fixed = [
        ROOT / "environment-v0.3.lock",
        ROOT / "data/manifests/source_manifest_v0.3.json",
        ROOT / "evidence/v0.3/evidence_protocol_v0.3.json",
        ROOT / "evidence/v0.3/parquet/consolidation_manifest.json",
        ROOT / "evidence/v0.3/parquet/consolidation_validation.json",
        ROOT / "evidence/v0.3/evidence.duckdb",
        ROOT / "evidence/v0.3/pilot.duckdb",
        ROOT / "evidence/v0.3/pilot_h7c.duckdb",
        ROOT / "evidence/v0.3/llm/llm_protocol.json",
        ROOT / "evidence/v0.3/llm/deepseek_r1_8b.jsonl",
        ROOT / "evidence/v0.3/llm/deepseek_r1_8b.summary.json",
        ROOT / "evidence/v0.4/concentration_protocol.json",
        ROOT / "evidence/v0.4/parquet/consolidation_manifest.json",
        ROOT / "evidence/v0.4/parquet/consolidation_validation.json",
        ROOT / "evidence/v0.4/evidence.duckdb",
        ROOT / "evidence/v0.4/local_sensitivity_protocol.json",
        ROOT / "evidence/v0.4/local_sensitivity_parquet/consolidation_manifest.json",
        ROOT / "evidence/v0.4/local_sensitivity_parquet/consolidation_validation.json",
        ROOT / "evidence/v0.4/local_sensitivity.duckdb",
        ROOT / "evidence/v0.4/local_sensitivity_v2_protocol.json",
        ROOT / "evidence/v0.4/local_sensitivity_v2_parquet/consolidation_manifest.json",
        ROOT / "evidence/v0.4/local_sensitivity_v2_parquet/consolidation_validation.json",
        ROOT / "evidence/v0.4/local_sensitivity_v2.duckdb",
        ROOT / "paper/v0.3/manuscript_draft.md",
        ROOT / "paper/v0.3/manuscript_outline.md",
        ROOT / "paper/v0.3/evidence_status.md",
        ROOT / "paper/v0.3/concentration_addendum_note.md",
        ROOT / "paper/v0.3/local_sensitivity_note.md",
        ROOT / "evidence/release/v0.3/archived_run_manifests.json",
        ROOT / "evidence/release/v0.3/purge_inventory.json",
        snapshot,
    ]
    recursive = (
        ROOT / "data/derived/v0.3",
        ROOT / "calibration/v0.3",
        ROOT / "paper/v0.3/generated",
        ROOT / "evidence/v0.3/pilot_analysis",
        ROOT / "evidence/v0.3/pilot_h7c_analysis",
        ROOT / "evidence/v0.3/pilot_parquet",
        ROOT / "evidence/v0.3/pilot_h7c_parquet",
        ROOT / "evidence/v0.3/parquet/batches",
        ROOT / "evidence/v0.4/parquet/batches",
        ROOT / "evidence/v0.4/local_sensitivity_parquet/batches",
        ROOT / "evidence/v0.4/local_sensitivity_v2_parquet/batches",
    )
    files = [path for path in fixed if path.is_file()]
    for directory in recursive:
        if directory.is_dir():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(set(files))


def write_release_manifest(path: Path, snapshot: Path) -> dict:
    records = []
    for artifact in _release_artifacts(snapshot):
        records.append(
            {
                "path": artifact.relative_to(ROOT).as_posix(),
                "bytes": artifact.stat().st_size,
                "sha256": sha256_file(artifact),
            }
        )
    payload = {
        "release": "journal-evidence-v0.3-with-v0.4-concentration-addendum",
        "created_at": utc_now(),
        "hash_algorithm": "sha256",
        "notes": [
            "Confirmatory SQLite shard hashes are chained through the v0.3 consolidation manifest.",
            "Raw empirical source hashes are chained through the source manifest.",
            "The v0.4 concentration addendum is robustness-only and does not alter v0.3 confirmatory inference.",
        ],
        "artifacts": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {"artifacts": len(records), "bytes": sum(row["bytes"] for row in records)}


def _directory_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    files = [item for item in path.rglob("*") if item.is_file()]
    return len(files), sum(item.stat().st_size for item in files)


def write_purge_inventory(path: Path) -> dict:
    candidates = []
    for name in PURGE_CANDIDATES:
        files, size = _directory_size(ROOT / name)
        if files:
            candidates.append({"path": name, "files": files, "bytes": size})
    payload = {
        "status": "inventory_only_no_files_deleted",
        "approval_required": True,
        "prerequisites": [
            "release_manifest verification passes",
            "v0.3 consolidation validation passes",
            "v0.4 addendum consolidation validation passes",
            "user explicitly approves deletion",
        ],
        "retain": [
            "evidence/v0.3/parquet",
            "evidence/v0.3/evidence.duckdb",
            "evidence/v0.3/llm",
            "evidence/v0.4/parquet",
            "evidence/v0.4/evidence.duckdb",
            "evidence/v0.4/local_sensitivity_parquet",
            "evidence/v0.4/local_sensitivity.duckdb",
            "evidence/v0.4/local_sensitivity_v2_parquet",
            "evidence/v0.4/local_sensitivity_v2.duckdb",
            "evidence/release/v0.3",
            "paper/v0.3/generated",
            "evidence/v0.3/pilot_analysis",
            "evidence/v0.3/pilot.duckdb",
            "evidence/v0.3/pilot_parquet",
            "evidence/v0.3/pilot_h7c_analysis",
            "evidence/v0.3/pilot_h7c.duckdb",
            "evidence/v0.3/pilot_h7c_parquet",
        ],
        "candidates": candidates,
        "reclaimable_bytes": sum(item["bytes"] for item in candidates),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def verify_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text())
    errors = []
    for record in payload["artifacts"]:
        artifact = ROOT / record["path"]
        if not artifact.is_file():
            errors.append(f"missing: {record['path']}")
        elif artifact.stat().st_size != record["bytes"]:
            errors.append(f"size mismatch: {record['path']}")
        elif sha256_file(artifact) != record["sha256"]:
            errors.append(f"hash mismatch: {record['path']}")
    if errors:
        raise ValueError("\n".join(errors))
    return {"status": "ok", "artifacts": len(payload["artifacts"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and verify journal evidence release")
    parser.add_argument("command", choices=("build", "verify", "inventory"))
    args = parser.parse_args()
    snapshot = RELEASE / "source_snapshot.tar.gz"
    manifest = RELEASE / "sha256_manifest.json"
    inventory = RELEASE / "purge_inventory.json"
    if args.command == "build":
        archived_manifests = archive_run_manifests(
            RELEASE / "archived_run_manifests.json"
        )
        result = {
            "archived_run_manifests": archived_manifests,
            "snapshot": source_snapshot(snapshot),
            "manifest": write_release_manifest(manifest, snapshot),
            "purge_inventory": write_purge_inventory(inventory),
        }
    elif args.command == "verify":
        result = verify_manifest(manifest)
    else:
        result = write_purge_inventory(inventory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
