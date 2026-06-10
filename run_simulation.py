import csv
import sys
import numpy as np
from engine.model import MacroModel

def run_single_simulation(steps, control_mode, output_csv):
    print(f"Starting simulation (Control Mode = {control_mode}) for {steps} steps...")
    
    # Initialize the model
    # To write to a DB file instead of memory, you can specify db_path="simulation.db"
    model = MacroModel(n_firms=3, n_banks=1, control_mode=control_mode)
    
    # Header for the CSV
    headers = [
        "step",
        "total_money_supply",
        "total_outstanding_debt",
        "nominal_interest_rate",
        "realized_inflation",
        "real_interest_rate"
    ]
    
    records = []
    
    # Record initial state (step 0)
    total_money = sum(f.current_balance for f in model.schedule.firms)
    total_debt = sum(f.current_debt for f in model.schedule.firms)
    records.append({
        "step": 0,
        "total_money_supply": total_money,
        "total_outstanding_debt": total_debt,
        "nominal_interest_rate": model.nominal_rate,
        "realized_inflation": model.realized_inflation,
        "real_interest_rate": model.real_interest_rate
    })

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
        
        records.append({
            "step": s,
            "total_money_supply": total_money,
            "total_outstanding_debt": total_debt,
            "nominal_interest_rate": model.nominal_rate,
            "realized_inflation": model.realized_inflation,
            "real_interest_rate": model.real_interest_rate
        })
        
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
    print(f"{'Metric':<25} | {'Treatment (LLM Agent Negotiation)':<35} | {'Control (Deterministic Heuristics)':<35}")
    print("-" * 105)
    
    metrics = [
        ("total_money_supply", "Total Money Supply"),
        ("total_outstanding_debt", "Total Outstanding Debt"),
        ("nominal_interest_rate", "Nominal Interest Rate"),
        ("realized_inflation", "Realized Inflation"),
        ("real_interest_rate", "Real Interest Rate")
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

if __name__ == "__main__":
    steps = 5
    if len(sys.argv) > 1:
        try:
            steps = int(sys.argv[1])
        except ValueError:
            pass
            
    # Run Treatment (LLM Negotiation)
    treatment_records = run_single_simulation(steps, control_mode=False, output_csv="treatment_results.csv")
    
    # Run Control (Deterministic Rules)
    control_records = run_single_simulation(steps, control_mode=True, output_csv="control_results.csv")
    
    # Output Paper-ready Summary Table
    print_summary_statistics(treatment_records, control_records)
