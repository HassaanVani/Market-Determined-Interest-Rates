from __future__ import annotations

import numpy as np

from v03.config import CalibrationBundle, ExperimentSpec, ModelParameters, RateRegime
from v03.design import seeds_for
from v03.model import InstitutionalCreditModel
from v03.schema import LedgerV03


def dynamic_validation_moments(
    bundle: CalibrationBundle,
    base_parameters: ModelParameters,
    replications: int = 100,
    parameter_overrides: dict | None = None,
) -> dict[str, float]:
    parameter_values = base_parameters.model_dump()
    parameter_values.update(
        {
            name: value
            for name, value in bundle.fitted_parameters.items()
            if name in ModelParameters.model_fields
        }
    )
    parameter_values.update({"horizon": 4, "n_firms": 30, "n_banks": 5})
    parameter_values.update(parameter_overrides or {})
    parameters = ModelParameters.model_validate(parameter_values)
    observations = {
        name: []
        for name in (
            "capital_assets",
            "loans_deposits",
            "liquid_deposits",
            "ci_share",
            "deposit_growth",
            "loan_growth",
            "ci_chargeoff_rate",
            "loan_rate",
            "loan_amount",
            "loan_maturity",
        )
    }
    for replication in range(replications):
        spec = ExperimentSpec(
            calibration_id=bundle.calibration_id,
            parameter_set_id="validation",
            scenario_id="2025_holdout_forecast",
            rate_regimes=(RateRegime.ADMINISTERED,),
            parameters=parameters,
            replications=1,
            seed_namespace="validation-v0.3",
            failure_policy="fail_fast",
        )
        ledger = LedgerV03(":memory:")
        model = InstitutionalCreditModel(
            spec,
            RateRegime.ADMINISTERED,
            seeds_for("validation-v0.3", replication),
            ledger,
            calibration=bundle,
            replication=replication,
        )
        model.run()
        bank_rows = ledger.rows("bank_states", model.run_id)
        previous = {row["bank_id"]: row for row in bank_rows if row["period"] == 3}
        final = [row for row in bank_rows if row["period"] == 4]
        for row in final:
            bank = model.bank(row["bank_id"])
            assets = (
                bank.reserves
                + bank.other_assets
                + model.bank_loans(bank.bank_id)
                + bank.interbank_assets
            )
            observations["capital_assets"].append(
                row["equity"] / assets if assets else np.nan
            )
            observations["loans_deposits"].append(
                row["customer_loans"] / row["deposits"] if row["deposits"] else np.nan
            )
            observations["liquid_deposits"].append(
                row["reserves"] / row["deposits"] if row["deposits"] else np.nan
            )
            prior = previous[row["bank_id"]]
            observations["deposit_growth"].append(
                row["deposits"] / prior["deposits"] - 1 if prior["deposits"] else np.nan
            )
            observations["loan_growth"].append(
                row["customer_loans"] / prior["customer_loans"] - 1
                if prior["customer_loans"]
                else np.nan
            )
        for bank in model.banks:
            experimental = sum(
                loan.remaining for loan in model.loans if loan.bank_id == bank.bank_id
            )
            total = bank.legacy_loans + experimental
            observations["ci_share"].append(
                (bank.legacy_loans * bank.legacy_ci_share + experimental) / total
                if total
                else np.nan
            )
        macros = ledger.rows("period_macro", model.run_id)
        total_writeoffs = sum(row["write_offs"] for row in macros)
        ci_loans = sum(
            model.bank_loans(bank.bank_id) * max(bank.legacy_ci_share, 1e-9)
            for bank in model.banks
        )
        observations["ci_chargeoff_rate"].append(
            total_writeoffs / ci_loans if ci_loans else 0.0
        )
        contracts = ledger.rows("loan_contracts", model.run_id)
        observations["loan_rate"].extend(row["nominal_rate"] for row in contracts)
        observations["loan_amount"].extend(row["principal"] for row in contracts)
        observations["loan_maturity"].extend(row["maturity"] for row in contracts)
        ledger.close()
    return {
        name: float(np.nanmedian(values)) if values else float("nan")
        for name, values in observations.items()
    }
