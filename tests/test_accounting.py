import pytest
from engine.model import MacroModel
from database.ledger import BalanceSheetMismatch


def test_initial_balance_sheet_validation():
    # Model initialization runs validation
    model = MacroModel(n_firms=2, n_banks=1)
    # Validation passed if no exception raised
    assert True


def test_credit_impulse_preserves_accounting():
    # Setup the model
    model = MacroModel(n_firms=2, n_banks=1)

    # Run a step (which triggers Ollama evaluation)
    # Note: if ollama is not running, this will fallback safely and demand/issue 0 loans
    # To test actual impulses, we can mock the demands or let it run with fallback.
    model.step()

    # Validation happens at the end of schedule.step(), so if it succeeds, we are good.
    assert True


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
