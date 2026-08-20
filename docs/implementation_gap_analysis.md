# Implementation readiness audit

This audit supersedes the prototype-era gap analysis.

| Requirement | Status | Evidence |
| --- | --- | --- |
| Independent rate and behavior treatments | Complete | `RateRegime` and `BehaviorMode`; 38 tests |
| Competitive applications and bank quotes | Complete | application, offer, acceptance, and contract tables |
| Central settlement and decentralized deposit creation | Complete | bank-specific accounts and settlement-event ledger |
| Interbank and lender-of-last-resort mechanisms | Complete | liquidity loans, bank liquidity states, H7 scenarios |
| Seeded exogenous shocks | Complete | versioned shock records and independent seed streams |
| Credit-to-real-output channel | Complete | logged working-capital budgets and lagged wage spending |
| H2 local-state instrumentation | Complete | borrower, reserve, capital, and inflation state on offers |
| LLM failure integrity | Complete | bounded retry/timeout, call metadata, invalid-run policy |
| DGP provenance | Complete | embedded source fingerprint and verified source archive |
| Powered H2/H3/H7 pilot | Complete | 480 completed rule runs and power analysis |
| DeepSeek R1 8B validation | Complete | 6 runs, 42 successful calls, no retries/failures |
| Frozen evidence package | Complete | protocol, results, analysis CSVs, hashes, manifest |

## Remaining work outside evidence readiness

The following are paper-development tasks rather than missing evidence
infrastructure:

- write the literature review and formal institutional comparison;
- decide whether to rename H3 after its directional rejection;
- add robustness grids for alternative pricing coefficients, shock sizes, and
  horizons if required by reviewers;
- run a powered LLM treatment comparison only if the paper intends to make
  inferential claims about LLM behavior; and
- prepare publication tables, figures, and manuscript prose.
