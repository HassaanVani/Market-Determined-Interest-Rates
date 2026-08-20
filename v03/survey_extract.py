from __future__ import annotations

from pathlib import Path

import pandas as pd

from v03.data_pipeline import clean_business_loan_panel


def quarterly_fred(path: str | Path, value_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "observation_date" not in frame or value_column not in frame:
        raise ValueError(f"unrecognized FRED schema for {value_column}")
    frame["observation_date"] = pd.to_datetime(frame["observation_date"])
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    frame["quarter"] = frame.observation_date.dt.to_period("Q").astype(str)
    return frame.groupby("quarter", as_index=False)[value_column].mean()


def extract_fr2028d_business_panel(
    workbook: str | Path,
    cpi_csv: str | Path,
    prime_csv: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(workbook, sheet_name="Aggregate Data")
    expected = {"Tab", "Period", "Attribute", "Value"}
    if expected - set(raw):
        raise ValueError("FR 2028D workbook schema drift")
    raw["Tab"] = raw["Tab"].astype(str).str.strip()
    raw["Attribute"] = raw["Attribute"].astype(str).str.strip()
    selected = raw[
        raw.Tab.isin(("A16", "A19"))
        & raw.Period.str.replace(":", "", regex=False).isin(
            [
                f"{year}Q{quarter}"
                for year in range(2022, 2026)
                for quarter in range(1, 5)
            ]
        )
    ].copy()
    selected["quarter"] = selected.Period.str.replace(":", "", regex=False)
    selected["loan_category"] = selected.Tab.map(
        {"A16": "new_fixed_term", "A19": "new_variable_term"}
    )
    pivot = selected.pivot(
        index=["quarter", "loan_category"], columns="Attribute", values="Value"
    ).reset_index()
    required = {
        "Number",
        "Outstanding dollar amount",
        "Weighted average interest rate",
        "Weighted average maturity",
    }
    if required - set(pivot):
        raise ValueError(
            f"FR 2028D attributes changed: missing {sorted(required - set(pivot))}"
        )
    # The workbook footnote defines reported dollar amounts as thousands.
    pivot["loan_amount"] = pivot["Outstanding dollar amount"] * 1000.0 / pivot["Number"]
    pivot["maturity_months"] = pivot["Weighted average maturity"]
    pivot["effective_rate"] = pivot["Weighted average interest rate"] / 100.0
    prime = quarterly_fred(prime_csv, "DPRIME").rename(columns={"DPRIME": "prime_rate"})
    prime["prime_rate"] /= 100.0
    pivot = pivot.merge(prime, on="quarter", how="left", validate="many_to_one")
    if pivot.prime_rate.isna().any():
        raise ValueError("prime-rate coverage is incomplete")
    pivot["prime_spread"] = pivot.effective_rate - pivot.prime_rate
    cpi = quarterly_fred(cpi_csv, "CPIAUCSL").rename(columns={"CPIAUCSL": "cpi"})
    return clean_business_loan_panel(
        pivot[
            [
                "quarter",
                "loan_category",
                "loan_amount",
                "maturity_months",
                "effective_rate",
                "prime_spread",
            ]
        ],
        cpi,
    )
