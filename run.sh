#!/bin/bash

# Set PYTHONPATH to current directory
export PYTHONPATH=.

# Virtual environment executables
VENV_PYTHON="venv/bin/python"
VENV_STREAMLIT="venv/bin/streamlit"
VENV_PYTEST="venv/bin/pytest"

# Verify virtual environment existence
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not detected."
    exit 1
fi

print_usage() {
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Available commands:"
    echo "  dashboard          Launch the interactive Streamlit UI dashboard"
    echo "  tui [args]         Launch the real-time Terminal User Interface dashboard (e.g., --control)"
    echo "  sweep [steps] [s]  Run parameter sensitivity sweep (optional: steps, seeds)"
    echo "  sim [args]         Run default treatment/control comparison simulation"
    echo "  test               Run the unit test suite"
    echo ""
}

case "$1" in
    dashboard)
        echo "Launching Streamlit dashboard..."
        $VENV_STREAMLIT run dashboard.py
        ;;
    tui)
        echo "Launching Terminal User Interface..."
        $VENV_PYTHON tui.py "${@:2}"
        ;;
    sweep)
        echo "Launching reserve requirement sensitivity sweep..."
        $VENV_PYTHON run_simulation.py sweep "${@:2}"
        ;;
    sim)
        echo "Launching default simulation..."
        $VENV_PYTHON run_simulation.py "${@:2}"
        ;;
    test)
        echo "Running automated verification tests..."
        $VENV_PYTEST tests/test_accounting.py
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
