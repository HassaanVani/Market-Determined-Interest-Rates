from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import product

from v03.config import (
    ExperimentSpec,
    MechanismSwitches,
    ModelParameters,
    RateRegime,
    SeedBundle,
    ShockSpec,
)

MAIN_CONFIRMATORY_REPLICATIONS = 809
CONFIRMATORY_RUN_COUNT = 8_096


@dataclass(frozen=True)
class RunCell:
    family: str
    spec: ExperimentSpec
    regime: RateRegime
    replication: int
    seeds: SeedBundle


def seeds_for(namespace: str, replication: int, parameter_index: int = 0) -> SeedBundle:
    raw = hashlib.sha256(
        f"v0.3:{namespace}:{parameter_index}:{replication}".encode()
    ).digest()
    base = int.from_bytes(raw[:8], "big") % 1_000_000_000
    return SeedBundle(
        environment=base,
        matching=base + 1_000_000_000,
        shocks=base + 2_000_000_000,
        behavior=base + 3_000_000_000,
    )


def clone_spec(spec: ExperimentSpec, **updates) -> ExperimentSpec:
    return spec.model_copy(update=updates)


def main_cells(base: ExperimentSpec, replications: int = 100) -> list[RunCell]:
    cells = []
    scenarios = {
        "h2_h3_baseline": (),
        "h3_positive_demand": (
            ShockSpec(
                shock_id="h3_demand",
                shock_type="demand",
                start_period=8,
                duration=4,
                magnitude=0.25,
            ),
        ),
    }
    for scenario, shocks in scenarios.items():
        spec = clone_spec(
            base, scenario_id=scenario, shocks=shocks, replications=replications
        )
        for regime, replication in product(spec.rate_regimes, range(replications)):
            cells.append(
                RunCell(
                    "main",
                    spec,
                    regime,
                    replication,
                    seeds_for(spec.seed_namespace, replication),
                )
            )
    return cells


def h7_cells(base: ExperimentSpec, replications: int = 40) -> list[RunCell]:
    cells = []
    reserve_levels = (0.05, 0.10, 0.20, 0.35, 0.50)
    facilities = (
        ("unavailable", 0.0, False),
        ("limited", 0.5, True),
        ("limited", 1.0, True),
        ("penalty", 1.0, True),
    )
    for reserve, (facility, limit, enabled) in product(reserve_levels, facilities):
        params = base.parameters.model_copy(
            update={
                "initial_bank_reserves": reserve
                * base.parameters.initial_bank_deposits,
                # H7 fixes a common operational settlement floor while reserve
                # abundance and backstop generosity vary across cells.
                "reserve_requirement": base.parameters.liquidity_target_ratio,
                "emergency_facility": facility,
                "emergency_limit_equity": limit,
            }
        )
        switches = base.mechanisms.model_copy(update={"emergency_facility": enabled})
        scenario = f"h7_reserve_{reserve:.2f}_{facility}_{limit:.1f}"
        spec = clone_spec(
            base,
            scenario_id=scenario,
            parameters=params,
            mechanisms=switches,
            replications=replications,
        )
        for regime, replication in product(spec.rate_regimes, range(replications)):
            cells.append(
                RunCell(
                    "h7",
                    spec,
                    regime,
                    replication,
                    seeds_for(spec.seed_namespace, replication),
                )
            )
    return cells


def ablation_cells(base: ExperimentSpec, replications: int = 30) -> list[RunCell]:
    cells = []
    names = tuple(MechanismSwitches.model_fields)
    for mechanism in names:
        switches = base.mechanisms.model_copy(update={mechanism: False})
        for shocked in (False, True):
            shocks = (
                (
                    ShockSpec(
                        shock_id="demand",
                        shock_type="demand",
                        start_period=8,
                        duration=4,
                        magnitude=0.25,
                    ),
                )
                if shocked
                else ()
            )
            scenario = f"ablation_{mechanism}_{'shock' if shocked else 'baseline'}"
            spec = clone_spec(
                base,
                scenario_id=scenario,
                mechanisms=switches,
                shocks=shocks,
                replications=replications,
            )
            for regime, replication in product(spec.rate_regimes, range(replications)):
                cells.append(
                    RunCell(
                        "ablation",
                        spec,
                        regime,
                        replication,
                        seeds_for(spec.seed_namespace, replication),
                    )
                )
    return cells


def topology_cells(base: ExperimentSpec, replications: int = 25) -> list[RunCell]:
    settings = (
        (30, 3, "empirical"),
        (30, 5, "empirical"),
        (100, 5, "empirical"),
        (30, 5, "low"),
        (30, 5, "high"),
        (100, 5, "high"),
    )
    cells = []
    for firms, banks, concentration in settings:
        params = base.parameters.model_copy(
            update={
                "n_firms": firms,
                "n_banks": banks,
                "deposit_concentration": concentration,
            }
        )
        scenario = f"topology_{firms}_{banks}_{concentration}"
        spec = clone_spec(
            base, scenario_id=scenario, parameters=params, replications=replications
        )
        for regime, replication in product(spec.rate_regimes, range(replications)):
            cells.append(
                RunCell(
                    "topology",
                    spec,
                    regime,
                    replication,
                    seeds_for(spec.seed_namespace, replication),
                )
            )
    return cells


def latin_hypercube_parameters(
    base: ModelParameters, count: int = 100, seed: int = 30303
) -> list[ModelParameters]:
    import numpy as np
    from scipy.stats import qmc

    names = (
        "production_alpha",
        "investment_share",
        "base_credit_demand",
        "risk_price",
        "liquidity_price",
        "capital_price",
    )
    bounds = (
        (0.20, 0.50),
        (0.15, 0.60),
        (6.0, 20.0),
        (0.005, 0.05),
        (0.003, 0.04),
        (0.002, 0.03),
    )
    sample = qmc.LatinHypercube(d=len(names), seed=seed).random(count)
    values = qmc.scale(
        sample, np.array([x[0] for x in bounds]), np.array([x[1] for x in bounds])
    )
    return [base.model_copy(update=dict(zip(names, row))) for row in values]


def sensitivity_cells(
    base: ExperimentSpec, sets: int = 100, replications: int = 5
) -> list[RunCell]:
    cells = []
    for index, params in enumerate(latin_hypercube_parameters(base.parameters, sets)):
        for shocked in (False, True):
            shocks = (
                (
                    ShockSpec(
                        shock_id="demand",
                        shock_type="demand",
                        start_period=8,
                        duration=4,
                        magnitude=0.25,
                    ),
                )
                if shocked
                else ()
            )
            scenario = f"sensitivity_{index:03d}_{'shock' if shocked else 'baseline'}"
            spec = clone_spec(
                base,
                scenario_id=scenario,
                parameter_set_id=f"lhs-{index:03d}",
                parameters=params,
                shocks=shocks,
                replications=replications,
            )
            for regime, replication in product(spec.rate_regimes, range(replications)):
                cells.append(
                    RunCell(
                        "sensitivity",
                        spec,
                        regime,
                        replication,
                        seeds_for(spec.seed_namespace, replication, index),
                    )
                )
    return cells


def confirmatory_design(base: ExperimentSpec) -> list[RunCell]:
    cells = (
        main_cells(base, replications=MAIN_CONFIRMATORY_REPLICATIONS)
        + h7_cells(base)
        + ablation_cells(base)
        + topology_cells(base)
        + sensitivity_cells(base)
    )
    if len(cells) != CONFIRMATORY_RUN_COUNT:
        raise AssertionError(
            f"expected {CONFIRMATORY_RUN_COUNT:,} rule runs, constructed {len(cells)}"
        )
    return cells


def smoke_design(base: ExperimentSpec) -> list[RunCell]:
    """One replication of every distinct confirmatory scenario/regime cell."""
    cells = (
        main_cells(base, replications=1)
        + h7_cells(base, replications=1)
        + ablation_cells(base, replications=1)
        + topology_cells(base, replications=1)
        + sensitivity_cells(base, replications=1)
    )
    if len(cells) != 488:
        raise AssertionError(f"expected 488 smoke runs, constructed {len(cells)}")
    return cells
