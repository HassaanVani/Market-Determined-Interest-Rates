from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

from v03.config import CalibrationBundle
from v03.data_pipeline import data_fingerprint

PRIMARY_GROUPS = (
    "capital_assets",
    "loans_deposits",
    "liquid_deposits",
    "ci_share",
    "deposit_growth",
    "loan_growth",
    "ci_chargeoff_rate",
    "business_loan_terms",
)


@dataclass(frozen=True)
class CalibrationResult:
    parameters: dict[str, float]
    objective: float
    normalized_rmse: float
    start_seed: int
    evaluations: int


class MinimumDistanceCalibrator:
    def __init__(
        self,
        target_moments: dict[str, float],
        bootstrap_variances: dict[str, float],
        bounds: dict[str, tuple[float, float]],
        simulator: Callable[[dict[str, float], int], dict[str, float]],
    ):
        self.targets = target_moments
        self.variances = bootstrap_variances
        self.bounds = bounds
        self.simulator = simulator
        if set(target_moments) - set(bootstrap_variances):
            raise ValueError("every target needs an empirical bootstrap variance")
        if any(
            value <= 0 or not np.isfinite(value)
            for value in bootstrap_variances.values()
        ):
            raise ValueError("bootstrap variances must be finite and positive")

    def objective(self, vector: np.ndarray, seed: int) -> float:
        parameters = dict(zip(self.bounds, map(float, vector)))
        simulated = self.simulator(parameters, seed)
        missing = set(self.targets) - set(simulated)
        if missing:
            raise ValueError(f"simulator omitted target moments: {sorted(missing)}")
        errors = [
            (simulated[name] - target) ** 2 / self.variances[name]
            for name, target in self.targets.items()
        ]
        return float(np.mean(errors))

    def fit(
        self, starts: tuple[int, ...] = tuple(range(34000, 34010)), maxiter: int = 100
    ) -> tuple[CalibrationResult, list[CalibrationResult]]:
        results = []
        bounds = list(self.bounds.values())
        for seed in starts:
            fit = differential_evolution(
                lambda vector: self.objective(vector, seed),
                bounds=bounds,
                seed=seed,
                polish=True,
                workers=1,
                updating="immediate",
                maxiter=maxiter,
            )
            results.append(
                CalibrationResult(
                    parameters=dict(zip(self.bounds, map(float, fit.x))),
                    objective=float(fit.fun),
                    normalized_rmse=float(np.sqrt(fit.fun)),
                    start_seed=seed,
                    evaluations=int(fit.nfev),
                )
            )
        return min(results, key=lambda result: result.objective), results


def targets_from_outputs(
    moment_csv: str | Path, bootstrap_parquet: str | Path
) -> tuple[dict[str, float], dict[str, float]]:
    moments = pd.read_csv(moment_csv)
    selected = moments[
        (moments.period == "calibration")
        & (moments.weighting == "equal_bank")
        & (moments.statistic == "median")
    ]
    targets = dict(zip(selected.variable, selected.value))
    bootstrap = pd.read_parquet(bootstrap_parquet)
    selected_boot = bootstrap[
        (bootstrap.period == "calibration")
        & (bootstrap.weighting == "equal_bank")
        & (bootstrap.statistic == "median")
    ]
    variances = selected_boot.groupby("variable").value.var(ddof=1).to_dict()
    return targets, variances


def holdout_gate(
    simulated: dict[str, float],
    validation_intervals: dict[str, tuple[float, float, float, float]],
) -> dict:
    inside = 0
    failures = []
    for group, (mean, se, lower, upper) in validation_intervals.items():
        value = simulated[group]
        if lower <= value <= upper:
            inside += 1
        if abs(value - mean) > 2 * se:
            failures.append(group)
    return {
        "groups_inside": inside,
        "total_groups": len(validation_intervals),
        "outside_two_se": failures,
        "passed": inside >= 6 and not failures,
    }


def make_calibration_bundle(
    calibration_id: str,
    best: CalibrationResult,
    targets: dict[str, float],
    sampling_frame: pd.DataFrame,
    source_paths,
    transformation_fingerprint: str,
    optimizer_starts: tuple[int, ...],
    holdout_groups_inside: int | None = None,
) -> CalibrationBundle:
    columns = (
        "assets",
        "deposits",
        "gross_loans",
        "liquid_assets",
        "equity",
        "ci_share",
        "deposit_growth",
        "loan_growth",
        "ci_loan_growth",
        "ci_chargeoff_rate",
    )
    available = [column for column in columns if column in sampling_frame]
    # Initial populations are drawn from the final calibration quarter. This
    # preserves a clean temporal boundary before the 2025 forecast validation.
    if "quarter" in sampling_frame:
        sampling_frame = sampling_frame[
            sampling_frame.quarter == sampling_frame.quarter.max()
        ]
    complete = sampling_frame[available].dropna()
    distributions = {
        column: [float(value) for value in complete[column]] for column in available
    }
    return CalibrationBundle(
        calibration_id=calibration_id,
        target_moments=targets,
        fitted_parameters=best.parameters,
        sampling_distributions=distributions,
        source_data_fingerprint=data_fingerprint(source_paths),
        transformation_fingerprint=transformation_fingerprint,
        optimizer_starts=optimizer_starts,
        normalized_rmse=best.normalized_rmse,
        holdout_groups_inside=holdout_groups_inside,
    )


def assert_calibration_gate(bundle: CalibrationBundle) -> None:
    if bundle.normalized_rmse is None or bundle.normalized_rmse > 0.25:
        raise ValueError(
            f"calibration failed normalized RMSE gate: {bundle.normalized_rmse}"
        )
    if bundle.holdout_groups_inside is not None and bundle.holdout_groups_inside < 6:
        raise ValueError("held-out validation failed six-of-eight group gate")
    if bundle.holdout_outside_two_se:
        raise ValueError(
            "held-out validation has groups outside two standard errors: "
            + ", ".join(bundle.holdout_outside_two_se)
        )


def write_calibration_report(
    best: CalibrationResult, starts: list[CalibrationResult], path: str | Path
) -> None:
    payload = {
        "best": best.__dict__,
        "starts": [result.__dict__ for result in starts],
        "success_threshold": {"normalized_rmse_lte": 0.25},
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
