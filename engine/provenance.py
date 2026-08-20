"""Deterministic fingerprints for executable experiment sources."""

from hashlib import sha256
from pathlib import Path

SOURCE_DIRECTORIES = ("engine", "models", "database")
SOURCE_FILES = (
    "requirements.txt",
    "run_experiments.py",
    "run_paper_suite.py",
    "run.sh",
)


def source_fingerprint(project_root=None):
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    paths = [root / name for name in SOURCE_FILES]
    for directory in SOURCE_DIRECTORIES:
        paths.extend((root / directory).rglob("*.py"))

    digest = sha256()
    for path in sorted({path.resolve() for path in paths}):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
