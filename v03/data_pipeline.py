from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

REQUIRED_QUARTERS = tuple(
    f"{year}Q{quarter}" for year in range(2022, 2026) for quarter in range(1, 5)
)
CALIBRATION_QUARTERS = REQUIRED_QUARTERS[:12]
VALIDATION_QUARTERS = REQUIRED_QUARTERS[12:]
REQUIRED_BANK_COLUMNS = (
    "bank_id",
    "quarter",
    "active",
    "domestic_charter",
    "fdic_insured",
    "commercial_bank",
    "assets",
    "deposits",
    "gross_loans",
    "liquid_assets",
    "equity",
    "ci_loans",
    "ci_chargeoffs",
)


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    url: str
    release_date: str
    local_path: str
    bytes: int
    sha256: str
    retrieved_at: str


def sha256_path(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_immutable(
    source_id: str, url: str, destination: str | Path, release_date: str = "unknown"
) -> SourceRecord:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"immutable raw file already exists: {destination}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "market-rates-v0.3-replication/1.0",
            "Accept": "text/csv,application/zip,application/octet-stream",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    destination.write_bytes(content)
    return SourceRecord(
        source_id=source_id,
        url=url,
        release_date=release_date,
        local_path=destination.as_posix(),
        bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )


def verify_source_manifest(
    manifest_path: str | Path, root: str | Path = "."
) -> list[SourceRecord]:
    root = Path(root)
    payload = json.loads(Path(manifest_path).read_text())
    records = [SourceRecord(**item) for item in payload["sources"]]
    for record in records:
        path = root / record.local_path
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size != record.bytes or sha256_path(path) != record.sha256:
            raise ValueError(f"checksum/size mismatch for {record.source_id}")
    return records


def write_source_manifest(records: Iterable[SourceRecord], path: str | Path) -> None:
    payload = {
        "schema_version": "0.3",
        "sources": [asdict(record) for record in records],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def quarter_from_date(value) -> str:
    timestamp = pd.Timestamp(value)
    return f"{timestamp.year}Q{timestamp.quarter}"


def load_dictionary(path: str | Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for the quarter-aware data dictionary"
        ) from exc
    payload = yaml.safe_load(Path(path).read_text())
    if payload.get("schema_version") != "0.3":
        raise ValueError("unrecognized data dictionary version")
    return payload


def standardize_call_report(frame: pd.DataFrame, dictionary: dict) -> pd.DataFrame:
    aliases = dictionary["call_report_aliases"]
    rename: dict[str, str] = {}
    missing = []
    for canonical in REQUIRED_BANK_COLUMNS:
        candidates = aliases.get(canonical, [canonical])
        match = next((name for name in candidates if name in frame.columns), None)
        if match is None:
            missing.append(canonical)
        else:
            rename[match] = canonical
    if missing:
        raise ValueError(f"unrecognized Call Report schema drift; missing {missing}")
    result = frame.rename(columns=rename)[list(REQUIRED_BANK_COLUMNS)].copy()
    if not result["quarter"].astype(str).str.match(r"^\d{4}Q[1-4]$").all():
        result["quarter"] = result["quarter"].map(quarter_from_date)
    numeric = (
        "assets",
        "deposits",
        "gross_loans",
        "liquid_assets",
        "equity",
        "ci_loans",
        "ci_chargeoffs",
    )
    for column in numeric:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in ("active", "domestic_charter", "fdic_insured", "commercial_bank"):
        result[column] = (
            result[column].astype(str).str.lower().isin(("1", "true", "yes", "y"))
        )
    return result


def clean_bank_panel(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    exclusions = []
    for _, row in frame.iterrows():
        reasons = []
        if not row["active"]:
            reasons.append("inactive")
        if not row["domestic_charter"]:
            reasons.append("not_domestic_charter")
        if not row["fdic_insured"]:
            reasons.append("not_fdic_insured")
        if not row["commercial_bank"]:
            reasons.append("not_commercial_bank")
        for column in ("assets", "deposits", "gross_loans", "equity"):
            if pd.isna(row[column]) or row[column] <= 0:
                reasons.append(f"nonpositive_{column}")
        # Net charge-offs may be negative when recoveries exceed gross
        # charge-offs. Liquid assets and loan stocks may not be negative.
        if row["liquid_assets"] < 0 or row["ci_loans"] < 0:
            reasons.append("impossible_negative_value")
        if (
            row["deposits"] > row["assets"] * 2
            or row["gross_loans"] > row["assets"] * 2
            or row["equity"] > row["assets"]
        ):
            reasons.append("impossible_accounting_ratio")
        if reasons:
            exclusions.append(
                {
                    "bank_id": row["bank_id"],
                    "quarter": row["quarter"],
                    "reasons": ";".join(sorted(set(reasons))),
                }
            )
        else:
            rows.append(row)
    clean = pd.DataFrame(rows, columns=frame.columns).copy()
    if clean.duplicated(["bank_id", "quarter"]).any():
        duplicates = clean.loc[
            clean.duplicated(["bank_id", "quarter"], keep=False), ["bank_id", "quarter"]
        ]
        raise ValueError(
            f"duplicate bank-quarter keys: {duplicates.head().to_dict('records')}"
        )
    found = set(clean["quarter"])
    missing_quarters = sorted(set(REQUIRED_QUARTERS) - found)
    if missing_quarters:
        raise ValueError(f"missing required quarters: {missing_quarters}")
    clean["size_stratum"] = pd.qcut(
        clean.groupby("quarter")["assets"].rank(method="first"),
        3,
        labels=("small", "medium", "large"),
    )
    level_columns = (
        "assets",
        "deposits",
        "gross_loans",
        "liquid_assets",
        "equity",
        "ci_loans",
        "ci_chargeoffs",
    )
    for column in level_columns:
        clean[column] = clean.groupby(["quarter", "size_stratum"], observed=True)[
            column
        ].transform(_winsorize)
    clean = clean.sort_values(["bank_id", "quarter"])
    clean["capital_assets"] = clean["equity"] / clean["assets"]
    clean["loans_deposits"] = clean["gross_loans"] / clean["deposits"]
    clean["liquid_deposits"] = clean["liquid_assets"] / clean["deposits"]
    clean["ci_share"] = clean["ci_loans"] / clean["gross_loans"]
    clean["ci_chargeoff_rate"] = clean["ci_chargeoffs"] / clean["ci_loans"].replace(
        0, np.nan
    )
    clean["deposit_growth"] = clean.groupby("bank_id")["deposits"].pct_change()
    clean["loan_growth"] = clean.groupby("bank_id")["gross_loans"].pct_change()
    clean["ci_loan_growth"] = clean.groupby("bank_id")["ci_loans"].pct_change()
    clean[["deposit_growth", "loan_growth", "ci_loan_growth"]] = clean[
        ["deposit_growth", "loan_growth", "ci_loan_growth"]
    ].replace([np.inf, -np.inf], np.nan)
    derived_columns = (
        "capital_assets",
        "loans_deposits",
        "liquid_deposits",
        "ci_share",
        "ci_chargeoff_rate",
        "deposit_growth",
        "loan_growth",
        "ci_loan_growth",
    )
    for column in derived_columns:
        clean[column] = clean.groupby(["quarter", "size_stratum"], observed=True)[
            column
        ].transform(_winsorize)
    missingness = pd.DataFrame(
        {
            "column": clean.columns,
            "missing_count": clean.isna().sum().values,
            "missing_share": clean.isna().mean().values,
        }
    )
    return clean, pd.DataFrame(exclusions), missingness


def _winsorize(series: pd.Series) -> pd.Series:
    lower, upper = series.quantile([0.01, 0.99])
    return series.clip(lower, upper)


def _weighted_quantile(
    values: np.ndarray, weights: np.ndarray, quantile: float
) -> float:
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cumulative = np.cumsum(weights) / weights.sum()
    return float(values[np.searchsorted(cumulative, quantile, side="left")])


def moment_table(frame: pd.DataFrame) -> pd.DataFrame:
    variables = (
        "capital_assets",
        "loans_deposits",
        "liquid_deposits",
        "ci_share",
        "deposit_growth",
        "loan_growth",
        "ci_loan_growth",
        "ci_chargeoff_rate",
    )
    records = []
    for period, subset in (
        ("calibration", frame[frame.quarter.isin(CALIBRATION_QUARTERS)]),
        ("validation", frame[frame.quarter.isin(VALIDATION_QUARTERS)]),
    ):
        for variable in variables:
            valid = subset[[variable, "assets"]].dropna()
            for weighting in ("equal_bank", "asset_weighted"):
                weights = (
                    np.ones(len(valid))
                    if weighting == "equal_bank"
                    else valid["assets"].to_numpy(float)
                )
                values = valid[variable].to_numpy(float)
                if not len(values):
                    continue
                for statistic, quantile in (
                    ("p25", 0.25),
                    ("median", 0.5),
                    ("p75", 0.75),
                ):
                    value = _weighted_quantile(values, weights, quantile)
                    records.append(
                        {
                            "period": period,
                            "variable": variable,
                            "statistic": statistic,
                            "weighting": weighting,
                            "value": value,
                            "n": len(values),
                        }
                    )
    return pd.DataFrame(records)


def cluster_bootstrap_moments(
    frame: pd.DataFrame, draws: int = 200, seed: int = 202503
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    bank_ids = frame["bank_id"].unique()
    cluster_indices = {
        bank_id: indices.to_numpy()
        for bank_id, indices in frame.groupby("bank_id", sort=False).groups.items()
    }
    records = []
    for draw in range(draws):
        sampled = rng.choice(bank_ids, size=len(bank_ids), replace=True)
        sampled_indices = np.concatenate(
            [cluster_indices[bank_id] for bank_id in sampled]
        )
        boot = frame.loc[sampled_indices]
        table = moment_table(boot)
        table["draw"] = draw
        records.append(table)
    return pd.concat(records, ignore_index=True)


def write_panel_outputs(
    clean: pd.DataFrame,
    exclusions: pd.DataFrame,
    missingness: pd.DataFrame,
    output_dir: str | Path,
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    calibration = clean[clean.quarter.isin(CALIBRATION_QUARTERS)]
    validation = clean[clean.quarter.isin(VALIDATION_QUARTERS)]
    calibration.to_parquet(
        output / "bank_calibration_2022q1_2024q4.parquet", index=False
    )
    validation.to_parquet(output / "bank_validation_2025q1_2025q4.parquet", index=False)
    exclusions.to_csv(output / "exclusions.csv", index=False)
    missingness.to_csv(output / "missingness.csv", index=False)
    moment_table(clean).to_csv(output / "bank_moments.csv", index=False)
    cluster_bootstrap_moments(clean).to_parquet(
        output / "bank_bootstrap_moments.parquet", index=False
    )


def data_fingerprint(paths: Iterable[str | Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(item) for item in paths):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_path(path)))
    return digest.hexdigest()


def clean_business_loan_panel(
    frame: pd.DataFrame, cpi: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Standardize an extracted FR 2028D aggregate panel without hand edits.

    The extractor must provide one row per quarter/loan category. Dollar
    amounts are converted to 2025Q4 dollars with CPI-U.
    """
    required = {
        "quarter",
        "loan_category",
        "loan_amount",
        "maturity_months",
        "effective_rate",
        "prime_spread",
    }
    missing = required - set(frame)
    if missing:
        raise ValueError(f"FR 2028D schema drift; missing {sorted(missing)}")
    if frame.duplicated(["quarter", "loan_category"]).any():
        raise ValueError("duplicate FR 2028D quarter/category keys")
    missing_quarters = sorted(set(REQUIRED_QUARTERS) - set(frame.quarter))
    if missing_quarters:
        raise ValueError(f"FR 2028D missing required quarters: {missing_quarters}")
    cpi_required = {"quarter", "cpi"}
    if cpi_required - set(cpi):
        raise ValueError("CPI input requires quarter and cpi columns")
    result = frame.copy()
    numeric = ("loan_amount", "maturity_months", "effective_rate", "prime_spread")
    for column in numeric:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    invalid = (
        result[list(numeric)].isna().any(axis=1)
        | (result["loan_amount"] <= 0)
        | (result["maturity_months"] <= 0)
        | (result["effective_rate"] < 0)
    )
    exclusions = result.loc[invalid, ["quarter", "loan_category"]].copy()
    exclusions["reasons"] = "missing_or_impossible_loan_term"
    result = result.loc[~invalid].merge(
        cpi[["quarter", "cpi"]], on="quarter", how="left", validate="many_to_one"
    )
    if result["cpi"].isna().any() or "2025Q4" not in set(cpi.quarter):
        raise ValueError("CPI coverage is incomplete through 2025Q4")
    base_cpi = float(cpi.loc[cpi.quarter == "2025Q4", "cpi"].iloc[0])
    result["loan_amount_2025q4"] = result["loan_amount"] * base_cpi / result["cpi"]
    return result, exclusions


def business_loan_moments(frame: pd.DataFrame) -> dict[str, float]:
    calibration = frame[frame.quarter.isin(CALIBRATION_QUARTERS)]
    return {
        "business_loan_amount": float(calibration.loan_amount_2025q4.mean()),
        "business_loan_maturity": float(calibration.maturity_months.mean()),
        "loan_rate_mean": float(calibration.effective_rate.mean()),
        "loan_rate_dispersion": float(calibration.effective_rate.std(ddof=1)),
        "prime_spread_mean": float(calibration.prime_spread.mean()),
    }
