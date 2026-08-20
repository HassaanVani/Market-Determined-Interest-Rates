from __future__ import annotations

import argparse
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from v03.data_pipeline import (
    SourceRecord,
    download_immutable,
    sha256_path,
    write_source_manifest,
)

FDIC_API = "https://api.fdic.gov/banks/financials"
FDIC_FIELDS = "CERT,REPDTE,ACTIVE,CB,BKCLASS,ASSET,DEP,LNLSGR,CHBAL,EQ,LNCI,NTCI"
SBL_XLSX = "https://www.kansascityfed.org/documents/16893/Small-Business-Lending-Survey-Aggregate-Data-Kansas-City-Fed-First-Quarter-2026-Excel.xlsx"
CPI_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL&cosd=2022-01-01&coed=2025-12-31"
PRIME_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DPRIME&cosd=2022-01-01&coed=2025-12-31"
POLICY_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF&cosd=2022-01-01&coed=2025-12-31"


def quarter_dates():
    for year in range(2022, 2026):
        for month_day in ("0331", "0630", "0930", "1231"):
            yield f"{year}{month_day}"


def fdic_url(report_date: str) -> str:
    query = urllib.parse.urlencode(
        {
            "filters": f"REPDTE:{report_date} AND ACTIVE:1 AND CB:1",
            "fields": FDIC_FIELDS,
            "limit": 10000,
            "format": "json",
        }
    )
    return f"{FDIC_API}?{query}"


def download_all(raw_dir: str | Path, manifest_path: str | Path) -> list[SourceRecord]:
    raw = Path(raw_dir)
    records = []

    def fetch(source_id, url, path, release_date):
        path = Path(path)
        if path.exists():
            return SourceRecord(
                source_id=source_id,
                url=url,
                release_date=release_date,
                local_path=path.as_posix(),
                bytes=path.stat().st_size,
                sha256=sha256_path(path),
                retrieved_at=datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat(),
            )
        return download_immutable(source_id, url, path, release_date)

    for report_date in quarter_dates():
        records.append(
            fetch(
                f"fdic-financials-{report_date}",
                fdic_url(report_date),
                raw / "fdic" / f"financials_{report_date}.json",
                release_date=report_date,
            )
        )
    records.append(
        fetch(
            "fr2028d-aggregate",
            SBL_XLSX,
            raw / "fr2028d" / "aggregate_2026q1.xlsx",
            "2026-06-25",
        )
    )
    records.append(
        fetch("cpi-u", CPI_CSV, raw / "fred" / "CPIAUCSL_2022_2025.csv", "2026-01")
    )
    records.append(
        fetch(
            "bank-prime-rate",
            PRIME_CSV,
            raw / "fred" / "DPRIME_2022_2025.csv",
            "2026-01",
        )
    )
    records.append(
        fetch(
            "effective-federal-funds-rate",
            POLICY_CSV,
            raw / "fred" / "DFF_2022_2025.csv",
            "2026-01",
        )
    )
    write_source_manifest(records, manifest_path)
    return records


def build_call_report_input(raw_dir: str | Path) -> pd.DataFrame:
    frames = []
    for path in sorted((Path(raw_dir) / "fdic").glob("financials_*.json")):
        payload = json.loads(path.read_text())
        records = [item["data"] for item in payload["data"]]
        frame = pd.DataFrame(records)
        quarter = pd.Period(pd.Timestamp(str(frame.REPDTE.iloc[0])), freq="Q")
        frame = frame.assign(
            bank_id=frame.CERT.astype(str),
            quarter=str(quarter),
            active=frame.ACTIVE.eq(1),
            domestic_charter=~frame.BKCLASS.eq("OI"),
            fdic_insured=True,
            commercial_bank=frame.CB.astype(str).eq("1"),
            assets=frame.ASSET,
            deposits=frame.DEP,
            gross_loans=frame.LNLSGR,
            liquid_assets=frame.CHBAL,
            equity=frame.EQ,
            ci_loans=frame.LNCI,
            ci_chargeoffs=frame.NTCI,
        )
        frames.append(
            frame[
                [
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
                ]
            ]
        )
    if len(frames) != 16:
        raise ValueError(f"expected 16 FDIC quarterly releases, found {len(frames)}")
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download immutable official v0.3 source releases"
    )
    parser.add_argument("--raw-dir", default="data/raw/v0.3")
    parser.add_argument(
        "--manifest", default="data/manifests/source_manifest_v0.3.json"
    )
    args = parser.parse_args()
    records = download_all(args.raw_dir, args.manifest)
    print(json.dumps({"downloaded": len(records), "manifest": args.manifest}, indent=2))


if __name__ == "__main__":
    main()
