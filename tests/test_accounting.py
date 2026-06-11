import pytest
from engine.model import MacroModel
from database.ledger import BalanceSheetMismatch


def test_initial_balance_sheet_validation():
    # Model initialization runs validation and distributes initial deposits correctly
    model = MacroModel(n_firms=2, n_banks=1)
    # Validation passed if no exception raised
    assert True


def test_credit_impulse_preserves_accounting():
    # Setup model in control mode for fast deterministic steps
    model = MacroModel(n_firms=2, n_banks=1, control_mode=True)

    # Run steps to trigger circular loop (Wage payment -> credit clearing -> consumption -> repayments)
    model.step()
    model.step()

    # Validation occurs at the end of each step. If it reaches here, the invariants held.
    assert True


def test_bank_regulatory_rejection():
    # Reserve requirement = 0.01 (extremely low, so it won't trigger initially)
    # Capital requirement = 0.20 (high, so it triggers easily)
    model = MacroModel(
        n_firms=1, n_banks=1, reserve_requirement=0.01, capital_requirement=0.20
    )
    bank = model.schedule.banks[0]

    # 1. Test Reserve requirement rejection
    model.reserve_requirement = 0.50
    # Bank reserves are 1000. Deposits are 200.
    # Loan of 3000 -> post-loan reserve ratio = 1000 / 3200 = 0.3125 (violates 0.50)
    import asyncio

    decision = asyncio.run(
        bank.evaluate_loan(firm_id="firm_0", principal=3000.0, max_rate=0.10)
    )
    assert not decision.approved
    assert "reserve ratio" in decision.chain_of_thought.lower()

    # 2. Test Basel capital requirement violation
    model.reserve_requirement = 0.01
    # Bank equity = 1000 - 200 = 800.
    # A loan of 5000 -> post-loan outstanding loans = 5000.
    # Capital ratio = 800 / 5000 = 0.16 (below 0.20).
    decision = asyncio.run(
        bank.evaluate_loan(firm_id="firm_0", principal=5000.0, max_rate=0.10)
    )
    assert not decision.approved
    assert "basel capital" in decision.chain_of_thought.lower()


def test_loan_amortization_and_default_accounting():
    model = MacroModel(n_firms=1, n_banks=1, control_mode=True)

    # Manually insert a loan to simulate amortization
    loan = {
        "loan_id": "test_loan",
        "borrower_id": "firm_0",
        "bank_id": "bank_0",
        "principal": 50.0,
        "remaining_principal": 50.0,
        "interest_rate": 0.05,
        "duration": 5,
        "age": 0,
    }
    model.active_loans.append(loan)

    # Update firm and bank balance sheets manually to reflect loan issuance
    firm = model.schedule.firms[0]
    bank = model.schedule.banks[0]
    firm.current_balance += 50.0
    firm.current_debt += 50.0

    # Run a step (which will trigger wage payment, consumption, and amortization payment)
    # The firm balance sheet will change, but invariants must preserve.
    model.step()

    # Outstanding loans should shrink by amortization (50 / 5 = 10.0)
    # The firm also automatically requests a new loan of 5.0 in control mode (since current_debt > 0),
    # which is approved and amortizes by 1.0 in the same step.
    # Total debt = 50.0 (initial) + 5.0 (new) - 10.0 (amortization 1) - 1.0 (amortization 2) = 44.0
    assert loan["remaining_principal"] == 40.0
    assert firm.current_debt == 44.0


def test_balance_sheet_mismatch_raises_exception():
    model = MacroModel(n_firms=1, n_banks=1)

    # Manually cause a mismatch
    firm = model.schedule.firms[0]
    # Increase assets without increasing liabilities or equity
    model.ledger.update_balance_sheet(
        agent_id=firm.unique_id,
        agent_type="Firm",
        assets=firm.current_balance + 1000.0,
        liabilities=firm.current_debt,
        equity=firm.equity,
    )

    with pytest.raises(BalanceSheetMismatch):
        model.ledger.validate_balance_sheets()
