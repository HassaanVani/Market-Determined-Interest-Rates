# Market-Determined-Interest-Rates

## Project description

Agent-based economic simulation exploring market-determined interest rates.

## Architecture

`models/` defines household, firm, and bank agents; `engine/` schedules and evolves the model; `database/ledger.py` records accounts; CLI, dashboard, and tests sit at the boundary.

## Technology

Python • CSV • pytest

## Run locally

`./run.sh`

## Repository guide

The implementation is organized so that entry points remain thin and domain-specific logic stays in the modules named above. Configuration, assets, and deployment files are kept separate from application code. Review the source tree before changing behavior, and keep secrets in local environment files rather than committing them.
