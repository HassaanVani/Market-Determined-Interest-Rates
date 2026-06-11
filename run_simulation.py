import csv
import sys
import numpy as np
from engine.model import MacroModel


def run_single_simulation(
    steps,
    control_mode,
    output_csv,
    llm_model="deepseek-r1:8b",
    agent_sentiment="neutral",
    llm_temperature=0.7,
):
    print(
        f"Starting simulation (Control Mode = {control_mode}) for {steps} steps using {llm_model} (sentiment: {agent_sentiment}, temp: {llm_temperature})..."
    )

    # Initialize the model
    # To write to a DB file instead of memory, you can specify db_path="simulation.db"
    model = MacroModel(
        n_firms=3,
        n_banks=1,
        control_mode=control_mode,
        llm_model=llm_model,
        agent_sentiment=agent_sentiment,
        llm_temperature=llm_temperature,
    )

    # Header for the CSV
    headers = [
        "step",
        "total_money_supply",
        "total_outstanding_debt",
        "nominal_interest_rate",
        "realized_inflation",
        "real_interest_rate",
    ]

    records = []

    # Record initial state (step 0)
    total_money = sum(f.current_balance for f in model.schedule.firms)
    total_debt = sum(f.current_debt for f in model.schedule.firms)
    records.append(
        {
            "step": 0,
            "total_money_supply": total_money,
            "total_outstanding_debt": total_debt,
            "nominal_interest_rate": model.nominal_rate,
            "realized_inflation": model.realized_inflation,
            "real_interest_rate": model.real_interest_rate,
        }
    )

    # Run steps
    for s in range(1, steps + 1):
        print(f"Executing step {s}/{steps}...")
        try:
            model.step()
        except Exception as e:
            print(f"Simulation halted due to exception: {e}")
            break

        total_money = sum(f.current_balance for f in model.schedule.firms)
        total_debt = sum(f.current_debt for f in model.schedule.firms)

        records.append(
            {
                "step": s,
                "total_money_supply": total_money,
                "total_outstanding_debt": total_debt,
                "nominal_interest_rate": model.nominal_rate,
                "realized_inflation": model.realized_inflation,
                "real_interest_rate": model.real_interest_rate,
            }
        )

    # Write to CSV
    with open(output_csv, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)

    print(f"Simulation completed. Data saved to {output_csv}\n")
    return records


def print_summary_statistics(treatment_data, control_data):
    print("==========================================================================")
    print("                  MACROECONOMIC SUMMARY STATISTICS TABLE                  ")
    print("==========================================================================")
    print(
        f"{'Metric':<25} | {'Treatment (LLM Agent Negotiation)':<35} | {'Control (Deterministic Heuristics)':<35}"
    )
    print("-" * 105)

    metrics = [
        ("total_money_supply", "Total Money Supply"),
        ("total_outstanding_debt", "Total Outstanding Debt"),
        ("nominal_interest_rate", "Nominal Interest Rate"),
        ("realized_inflation", "Realized Inflation"),
        ("real_interest_rate", "Real Interest Rate"),
    ]

    for key, label in metrics:
        t_values = [r[key] for r in treatment_data]
        c_values = [r[key] for r in control_data]

        t_mean, t_std = np.mean(t_values), np.std(t_values)
        c_mean, c_std = np.mean(c_values), np.std(c_values)

        # Format like LaTeX tables in Econ papers: Mean (Std Dev)
        t_str = f"{t_mean:.4f} ({t_std:.4f})"
        c_str = f"{c_mean:.4f} ({c_std:.4f})"

        print(f"{label:<25} | {t_str:<35} | {c_str:<35}")

    print("==========================================================================")


def run_sweep(steps=10, num_seeds=10):
    print(
        f"Running parameter sensitivity sweep across reserve requirements (0.05 to 0.20) with {num_seeds} seeds..."
    )
    reserve_rates = [0.05, 0.10, 0.15, 0.20]
    sweep_results = {}

    for req in reserve_rates:
        print(f"Testing reserve requirement: {req:.2f}")
        all_money_supplies = []
        all_debts = []
        all_nominal_rates = []
        all_inflations = []
        all_defaults = []

        for seed in range(num_seeds):
            # Use distinct seeds where possible (random behavior depends on python random seed)
            import random

            random.seed(seed)
            np.random.seed(seed)

            model = MacroModel(
                n_firms=5,
                n_banks=2,
                db_path=":memory:",
                control_mode=True,  # deterministic rules for sweep reproducibility
                reserve_requirement=req,
            )

            for s in range(1, steps + 1):
                try:
                    model.step()
                except Exception as e:
                    print(f"Sweep simulation halted at step {s} due to: {e}")
                    break

                total_money = sum(f.current_balance for f in model.schedule.firms)
                total_debt = sum(f.current_debt for f in model.schedule.firms)

                all_money_supplies.append(total_money)
                all_debts.append(total_debt)
                all_nominal_rates.append(model.nominal_rate)
                all_inflations.append(model.realized_inflation)
                all_defaults.append(model.defaults_in_step)

        sweep_results[req] = {
            "money_supply_mean": (
                np.mean(all_money_supplies) if all_money_supplies else 0.0
            ),
            "money_supply_std": (
                np.std(all_money_supplies) if all_money_supplies else 0.0
            ),
            "debt_mean": np.mean(all_debts) if all_debts else 0.0,
            "debt_std": np.std(all_debts) if all_debts else 0.0,
            "nominal_rate_mean": (
                np.mean(all_nominal_rates) if all_nominal_rates else 0.0
            ),
            "nominal_rate_std": np.std(all_nominal_rates) if all_nominal_rates else 0.0,
            "inflation_mean": np.mean(all_inflations) if all_inflations else 0.0,
            "inflation_std": np.std(all_inflations) if all_inflations else 0.0,
            "defaults_mean": np.mean(all_defaults) if all_defaults else 0.0,
            "defaults_std": np.std(all_defaults) if all_defaults else 0.0,
        }

    print(
        "\n=========================================================================================================="
    )
    print(
        "                              SENSITIVITY ANALYSIS: RESERVE REQUIREMENT SWEEP                             "
    )
    print(
        "=========================================================================================================="
    )
    print(
        f"{'Reserve Req':<12} | {'Money Supply':<20} | {'Outstanding Debt':<20} | {'Nominal Rate':<16} | {'Inflation':<16} | {'Defaults/Step':<16}"
    )
    print("-" * 110)
    for req in reserve_rates:
        res = sweep_results[req]
        m_str = f"{res['money_supply_mean']:.2f} ({res['money_supply_std']:.2f})"
        d_str = f"{res['debt_mean']:.2f} ({res['debt_std']:.2f})"
        r_str = f"{res['nominal_rate_mean']:.4f} ({res['nominal_rate_std']:.4f})"
        i_str = f"{res['inflation_mean']:.4f} ({res['inflation_std']:.4f})"
        df_str = f"{res['defaults_mean']:.2f} ({res['defaults_std']:.2f})"
        print(
            f"{req:<12.2f} | {m_str:<20} | {d_str:<20} | {r_str:<16} | {i_str:<16} | {df_str:<16}"
        )
    print(
        "==========================================================================================================\n"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        steps = 10
        seeds = 10
        if len(sys.argv) > 2:
            try:
                steps = int(sys.argv[2])
            except ValueError:
                pass
        if len(sys.argv) > 3:
            try:
                seeds = int(sys.argv[3])
            except ValueError:
                pass
        run_sweep(steps=steps, num_seeds=seeds)
    else:
        steps = 5
        llm_model = "deepseek-r1:8b"
        agent_sentiment = "neutral"
        llm_temperature = 0.7

        if len(sys.argv) > 1:
            try:
                steps = int(sys.argv[1])
            except ValueError:
                pass
        if len(sys.argv) > 2:
            llm_model = sys.argv[2]
        if len(sys.argv) > 3:
            agent_sentiment = sys.argv[3]
        if len(sys.argv) > 4:
            try:
                llm_temperature = float(sys.argv[4])
            except ValueError:
                pass

        # Run Treatment (LLM Negotiation)
        treatment_records = run_single_simulation(
            steps,
            control_mode=False,
            output_csv="treatment_results.csv",
            llm_model=llm_model,
            agent_sentiment=agent_sentiment,
            llm_temperature=llm_temperature,
        )

        # Run Control (Deterministic Rules)
        control_records = run_single_simulation(
            steps,
            control_mode=True,
            output_csv="control_results.csv",
            llm_model=llm_model,
            agent_sentiment=agent_sentiment,
            llm_temperature=llm_temperature,
        )

        # Output Paper-ready Summary Table
        print_summary_statistics(treatment_records, control_records)
