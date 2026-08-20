# Specification 0.3 replication guide

## Environment

```bash
venv/bin/python -m pip install -r requirements-v0.3.txt
make lock
```

The raw data directory is ignored by Git. The checksum manifest under
`data/manifests/` is version controlled.

## Data and calibration

```bash
make download-data
make data
make calibrate
```

`make data` fails on source schema drift, missing quarters, duplicate keys, or
impossible required values. `make calibrate` writes its report even when an
acceptance gate fails, but it writes the usable calibration bundle only after
normalized RMSE is at most 0.25 and the held-out validation passes.

## Evidence sequence

```bash
make pilot V03_WORKERS=4
make pilot-h7 V03_WORKERS=4
make pilot-power
make smoke V03_WORKERS=4
make verify
make freeze-spec
make confirm V03_WORKERS=8
make llm-robustness
make paper-assets
make concentration-freeze
make concentration-run V03_WORKERS=2
make concentration-assets
make release
make release-verify
make verify
```

The pilot power calculation raised the H2/H3 count from 100 to 809 matched
seeds. The H7 pilot requires 37 per cell and the frozen design retains 40.
`make smoke` executes every distinct scenario/regime cell once before freeze.

The confirmatory command refuses an absent/unfrozen protocol, a protocol with a
changed fingerprint, or a run count other than 8,096. Each run receives its own
SQLite shard. Consolidation validates the shard before writing partitioned
Parquet and a read-only DuckDB evidence catalog.

DeepSeek requires Ollama to expose an OpenAI-compatible endpoint at
`http://localhost:11434/v1` and the exact local model ID `deepseek-r1:8b`.
Comparative intervals are automatically disallowed below 95% valid calls or 27
completed matched pairs.

The deposit-concentration robustness correction is a separately frozen,
post-confirmatory addendum. It reruns only the three invalid low/high cells and
does not alter v0.3 primary inference. Source SQLite shards may be removed only
after `make release-verify` succeeds and the user approves the purge inventory.

## Reproduction standard

A release is complete only when all rule runs have full horizons, foreign-key
checks are clean, no rule failure is unexplained, analysis outputs regenerate
byte-identically, and SHA-256 manifests cover raw sources, shards, Parquet,
catalog, generated tables/figures, source snapshot, and environment lock.
