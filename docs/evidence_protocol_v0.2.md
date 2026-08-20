# Evidence protocol, specification 0.2

## Scope

This protocol freezes the computational evidence for H2, H3, and H7 in
`docs/research_design.md`. The common unit of account and settlement asset is a
centralized dollar. Commercial banks create dollar deposits by lending, while
borrowers and competing banks determine credit quantities and loan rates.

The powered institutional results use rule-based agents. DeepSeek R1 8B is a
separate behavioral and infrastructure validation layer, not a substitute for
the powered baseline.

## Data-generating process

- Specification: `0.2`
- Horizon: 12 periods, plus the recorded period-zero initial state
- Firms: 9
- Banks: 3
- Rate regimes: administered anchor and market discovery
- Rule-based replications: 30 matched replications in every cell
- H7 adaptive extension: scarce/unavailable, scarce/penalty, and scarce/limited
  cells extended to 40 matched replications after the n=30 variance analysis
- Seed mapping for replication `r`:
  - environment: `10000 + r`
  - matching: `110000 + r`
  - shocks: `210000 + r`
  - behavior: `310000 + r`
- Firm heterogeneity scale: 0.15
- Reserve requirement: 0.10 for H2/H3; 0.30 for H7
- Capital requirement: 0.08
- Firm post-loan leverage limit: 1.5

Credit originated in period `t` creates a deposit and an equal borrower
liability. The borrower assigns the proceeds to a logged working-capital budget.
Beginning in period `t+1`, one quarter of the remaining budget can fund additional
wages and production per period. This creates a transparent lagged credit-to-output
channel without creating an unbalanced financial asset.

## Experimental cells

| Scenario | Initial reserves per bank | Backstop | Replications per regime |
| --- | ---: | --- | ---: |
| H2 baseline | 300 | penalty | 30 |
| H3 baseline | 300 | penalty | 30 |
| H3 demand shock | 300 | penalty | 30 |
| H7 abundant | 500 | unavailable | 30 |
| H7 scarce | 80 | unavailable | 40 |
| H7 scarce | 80 | penalty | 40 |
| H7 scarce | 80 | limited to 0.5 × equity | 40 |

The H3 demand shock starts in period 4, lasts two periods, and has magnitude
0.25. Baseline and treatment runs use identical seeds.

## Estimands

### H2

Within each completed run, offered nominal rates are regressed on borrower
leverage, borrower risk category, lender reserve buffer, lender capital buffer,
and lender expected inflation. The reported estimand is the matched-seed
market-minus-administered difference in each run-level slope.

### H3

Outcomes are aggregated over periods 4–7. The treatment response is demand-shock
minus baseline within each regime and seed. The primary institutional estimand is
the matched difference-in-differences:

`(market shock − market baseline) − (administered shock − administered baseline)`.

### H7

The primary boundary-condition contrasts are matched differences between:

- abundant and scarce reserves without a backstop;
- penalty liquidity and no backstop under scarce reserves;
- limited liquidity and no backstop under scarce reserves; and
- penalty liquidity and limited liquidity under scarce reserves.

Outcomes include credit, output, inflation volatility, interbank volume,
emergency borrowing, unresolved liquidity shortfall, defaults, and write-offs.

## Power rule

The pilot replication requirement is

`ceil(((1.96 + 0.84) × paired standard deviation / |paired mean|)^2)`.

Thirty replications exceeded the estimated 80% requirement for every H2 and H3
primary estimand. The H7 market-regime credit contrast between penalty and
limited liquidity initially required 34 replications, so all matched scarce H7
cells were extended to 40. After extension its estimated requirement was 24.

## DeepSeek R1 8B validation

- Model: `deepseek-r1:8b` through local Ollama
- Firms: 3 heterogeneous risk profiles
- Banks: 2 competing banks
- Regimes: administered and market
- Matched replications: 3 per regime
- Horizon: 1 period
- Temperature: 0
- Maximum output: 256 tokens
- Reasoning effort: `none`
- Timeout: 300 seconds
- Maximum retries: 1

Ollama documents that DeepSeek R1 supports disabling thinking and that its
OpenAI-compatible chat endpoint accepts `reasoning_effort="none"`. This avoids
spending the structured-output budget on a reasoning trace while retaining the
requested DeepSeek R1 8B model.

The LLM sample is descriptive. Infrastructure/schema failures invalidate a run
and are never coded as an economic rejection or zero-credit decision.

## Integrity and exclusions

- Final rule dataset: 480/480 runs completed.
- Final DeepSeek dataset: 6/6 runs completed.
- Final DeepSeek calls: 42/42 successful on attempt zero.
- Every final run has its complete period-zero state and experimental horizon.
- SQLite foreign-key checks return no violations.
- Accounting, settlement, credit, interbank, and emergency-liquidity identities
  are checked during every model step.
- Earlier calibration databases and the 128/512-token invalid DeepSeek
  diagnostics are excluded from inference and retained under
  `evidence/diagnostics/`.

The manifest in `evidence/manifest_v0_2.json` contains SHA-256 hashes. The archived
rule and LLM DGP sources each reproduce the source fingerprint embedded in their
respective runs.
