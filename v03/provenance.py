from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_fingerprint(
    root: str | Path, paths=("v03", "configs/v0.3", "requirements.txt", "Makefile")
) -> str:
    root = Path(root).resolve()
    files: list[Path] = []
    for relative in paths:
        path = root / relative
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file()
                and "__pycache__" not in p.parts
                and p.suffix not in {".pyc", ".pyo"}
            )
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def package_fingerprint() -> str:
    packages = sorted(
        (dist.metadata["Name"].lower(), dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name")
    )
    payload = json.dumps(packages, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def git_commit(root: str | Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def environment_record() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages_sha256": package_fingerprint(),
    }
