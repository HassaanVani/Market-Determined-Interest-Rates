import os
import sys
import time
import argparse
from engine.model import MacroModel


def clear_screen():
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def draw_header(current_step, total_steps, control_mode, model_name):
    mode_str = (
        "Control Mode (Deterministic)" if control_mode else f"LLM Mode ({model_name})"
    )
    print("=" * 100)
    print(
        f"  MACROECONOMIC SIMULATION ENGINE (TUI)  |  Step: {current_step}/{total_steps}  |  Mode: {mode_str}"
    )
    print("=" * 100)


def draw_macro_state(model):
    tot_money = (
        sum(f.current_balance for f in model.schedule.firms)
        + model.household.current_balance
    )
    tot_debt = sum(f.current_debt for f in model.schedule.firms)
    print("\n[MACROECONOMIC STATE]")
    print(
        f"  Money Supply (M1)  : ${tot_money:<15.2f} Outstanding Debt    : ${tot_debt:<15.2f}"
    )
    print(
        f"  Nominal Interest   : {model.nominal_rate*100:<15.2f}% Real Interest Rate   : {model.real_interest_rate*100:<15.2f}%"
    )
    print(f"  Realized Inflation : {model.realized_inflation*100:<15.2f}%")
    print(
        f"  Expected Inflation : {model.exp_inflation*100:<15.2f}% Expected Nom Rate   : {model.exp_nominal_rate*100:<15.2f}%"
    )
    print(
        f"  Defaults in Step   : {model.defaults_in_step:<15d} Write-offs in Step  : ${model.write_offs_in_step:<15.2f}"
    )
    print("-" * 100)


def draw_firms(model):
    print("\n[FIRMS BALANCE SHEETS]")
    print(
        f"  {'Firm ID':<10} | {'Risk Profile':<15} | {'Cash (Assets)':<15} | {'Debt (Liab)':<15} | {'Equity':<12} | {'Exp Nom':<8} | {'Exp Inf':<8}"
    )
    print("  " + "-" * 96)
    for f in model.schedule.firms:
        print(
            f"  {f.unique_id:<10} | {f.risk_profile:<15} | ${f.current_balance:<14.2f} | ${f.current_debt:<14.2f} | ${f.equity:<11.2f} | {f.exp_nominal_rate*100:.1f}%   | {f.exp_inflation*100:.1f}%"
        )
    print("-" * 100)


def draw_banks(model):
    print("\n[BANKS BALANCE SHEETS]")
    print(
        f"  {'Bank ID':<10} | {'Reserves':<12} | {'Deposits':<12} | {'Outstanding Loans':<18} | {'Total Assets':<14} | {'Equity':<10}"
    )
    print("  " + "-" * 96)
    for b in model.schedule.banks:
        loans_outstanding = sum(
            l["remaining_principal"]
            for l in model.active_loans
            if l["bank_id"] == b.unique_id
        )
        total_assets = b.current_balance + loans_outstanding
        print(
            f"  {b.unique_id:<10} | ${b.current_balance:<11.2f} | ${b.current_debt:<11.2f} | ${loans_outstanding:<17.2f} | ${total_assets:<13.2f} | ${b.equity:<10.2f}"
        )
    print("-" * 100)


def draw_household(model):
    h = model.household
    print("\n[HOUSEHOLD BALANCE SHEET]")
    print(
        f"  {'Household':<10} | {'Cash (Assets)':<15} | {'Debt (Liab)':<15} | {'Equity':<15}"
    )
    print("  " + "-" * 96)
    print(
        f"  {'household':<10} | ${h.current_balance:<14.2f} | ${h.current_debt:<14.2f} | ${h.equity:<14.2f}"
    )
    print("-" * 100)


def draw_loans(model):
    print("\n[ACTIVE LOANS BOOK]")
    if not model.active_loans:
        print("  No active loans outstanding.")
    else:
        print(
            f"  {'Loan ID':<20} | {'Borrower':<10} | {'Lender':<10} | {'Remaining Principal':<20} | {'Age/Duration':<12} | {'Interest Rate':<10}"
        )
        print("  " + "-" * 96)
        for l in model.active_loans:
            print(
                f"  {l['loan_id']:<20} | {l['borrower_id']:<10} | {l['bank_id']:<10} | ${l['remaining_principal']:<19.2f} | {l['age']}/{l['duration']:<10} | {l['interest_rate']*100:.2f}%"
            )
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(
        description="Terminal interface for Macroeconomic Simulation."
    )
    parser.add_argument(
        "--steps", type=int, default=15, help="Number of simulation steps"
    )
    parser.add_argument(
        "--control", action="store_true", help="Run in control mode (deterministic)"
    )
    parser.add_argument(
        "--llm", type=str, default="deepseek-r1:1.5b", help="LLM model to use"
    )
    parser.add_argument(
        "--sentiment", type=str, default="neutral", help="Agent sentiment context"
    )
    parser.add_argument("--temp", type=float, default=0.7, help="LLM temperature")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Refresh delay between steps in seconds",
    )
    args = parser.parse_args()

    # Initialize model
    model = MacroModel(
        n_firms=5,
        n_banks=2,
        db_path=":memory:",
        control_mode=args.control,
        llm_model=args.llm,
        agent_sentiment=args.sentiment,
        llm_temperature=args.temp,
    )

    # Clean starting screen
    clear_screen()
    draw_header(0, args.steps, args.control, args.llm)
    draw_macro_state(model)
    draw_firms(model)
    draw_banks(model)
    draw_household(model)
    draw_loans(model)

    print("\nPress ENTER to start the simulation simulation run...")
    input()

    # Run loop
    for s in range(1, args.steps + 1):
        clear_screen()
        draw_header(s, args.steps, args.control, args.llm)
        print(
            f"\nSimulating step {s}... executing credit discovery and clearing cycle..."
        )

        try:
            model.step()
        except Exception as e:
            print(f"\n[FATAL ERROR] Simulation halted: {e}")
            break

        # Redraw dashboard
        clear_screen()
        draw_header(s, args.steps, args.control, args.llm)
        draw_macro_state(model)
        draw_firms(model)
        draw_banks(model)
        draw_household(model)
        draw_loans(model)

        if s < args.steps:
            time.sleep(args.delay)

    print("\nSimulation Run Complete. Press ENTER to exit.")
    input()


if __name__ == "__main__":
    main()
