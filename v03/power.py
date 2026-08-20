from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import norm


def required_paired_seeds(
    standardized_effect: float,
    power: float = 0.90,
    family_alpha: float = 0.05,
    family_outcomes: int = 2,
) -> int | None:
    """Conservative normal-approximation count for a paired contrast.

    Bonferroni alpha is used for planning; final inference still uses Holm.
    Returning ``None`` for a zero/nonfinite pilot effect makes the lack of an
    identified replication count explicit rather than silently capping it.
    """
    effect = abs(float(standardized_effect))
    if not math.isfinite(effect) or effect <= 0:
        return None
    alpha = family_alpha / family_outcomes
    count = ((norm.ppf(1 - alpha / 2) + norm.ppf(power)) / effect) ** 2
    return max(2, int(math.ceil(count)))


def build_power_table(h2_path: str | Path, h3_path: str | Path) -> pd.DataFrame:
    records = []
    for family, path in (("H2", h2_path), ("H3", h3_path)):
        frame = pd.read_csv(path)
        for row in frame.to_dict("records"):
            required = required_paired_seeds(row["standardized_effect"])
            records.append(
                {
                    "family": family,
                    "outcome": row["outcome"],
                    "pilot_pairs": int(row["n"]),
                    "pilot_effect": float(row["estimate"]),
                    "pilot_standardized_effect": float(row["standardized_effect"]),
                    "planning_power": 0.90,
                    "family_alpha": 0.05,
                    "planning_alpha_per_outcome": 0.025,
                    "required_matched_seeds": required,
                }
            )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.3 pilot power calculation")
    parser.add_argument("--analysis", default="evidence/v0.3/pilot_analysis")
    parser.add_argument(
        "--output", default="evidence/v0.3/pilot_analysis/power_analysis.csv"
    )
    parser.add_argument(
        "--report", default="evidence/v0.3/pilot_analysis/power_report.json"
    )
    args = parser.parse_args()
    analysis = Path(args.analysis)
    table = build_power_table(
        analysis / "h2_primary_effects.csv",
        analysis / "h3_difference_in_differences.csv",
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    finite = table.required_matched_seeds.dropna()
    report = {
        "pilot_seed_namespace": "pilot-v0.3",
        "pilot_pairs_per_cell": 20,
        "target_power": 0.90,
        "multiplicity_planning": "Bonferroni 0.025 per outcome; final Holm",
        "required_main_matched_seeds": int(finite.max()) if len(finite) else None,
        "original_main_matched_seeds": 100,
        "original_main_design_is_adequate": bool(len(finite) and finite.max() <= 100),
        "h7_power_status": "pending dedicated institutional-grid pilot",
        "table": output.as_posix(),
    }
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
