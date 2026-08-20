# Centralized Currency, Decentralized Credit

## Research design, version 0.2

### Working title

**Centralized Currency, Decentralized Credit: Market-Determined Interest Rates in an LLM-Augmented Agent-Based Economy**

## 1. Research objective

This paper studies a monetary economy in which the currency remains centralized but
the supply and price of bank credit are decentralized.

The simulated dollar is the common unit of account. A central monetary authority
issues the settlement asset, operates the payment system, and enforces prudential
rules. Commercial banks create dollar-denominated deposits when they originate
loans. Competing banks and borrowers determine loan quantities and nominal interest
rates through a credit market.

The institutional counterfactual is therefore not public money versus private
money. It is:

1. an **administered-rate regime**, in which a central policy rate anchors bank loan
   pricing; versus
2. a **market-discovery regime**, in which no policy-rate target anchors loan
   pricing and accepted bank quotes determine the distribution of nominal rates.

The central question is:

> How do decentralized interest-rate discovery and endogenous deposit creation
> affect credit allocation, monetary expansion, and financial stability when the
> unit of account and settlement infrastructure remain centralized?

## 2. Scope and claims

The model is a controlled computational experiment, not a forecast of the United
States economy. Its purpose is to identify mechanisms under explicit institutional
rules.

The paper will not claim that:

- the existing US system has no market-determined interest rates;
- an LLM is a validated representation of a human firm or banker;
- the simulation estimates a policy effect for the real US economy; or
- decentralized rate discovery is unconditionally superior.

Instead, it will report how outcomes change inside the model when the rate-setting
institution changes while the currency, agents, shocks, accounting rules, and
regulatory environment are held constant.

## 3. Primary hypotheses

### H2: Local-information sensitivity

> In the market-discovery regime, accepted nominal loan rates and credit approval
> respond more strongly to borrower risk, lender balance-sheet conditions, and
> expected inflation than in the administered-rate regime.

Operational tests:

- Estimate the response of offered rates, accepted rates, approved quantities, and
  rejection probabilities to:
  - borrower leverage and default risk;
  - bank capital and settlement liquidity;
  - borrower and bank expected inflation.
- Compare these marginal responses across rate regimes.
- Measure cross-sectional rate dispersion and the share of dispersion explained by
  observable local state.

The hypothesis is supported when the interaction between the market regime and
local state is economically and statistically meaningful in the predicted
direction.

### H3: Credit elasticity

> Following an ordinary positive demand or productivity shock, decentralized
> deposit creation under market rate discovery produces a larger short-run credit
> response than the administered-rate regime.

Operational tests:

- Apply identical, seeded shocks to matched simulation runs.
- Measure:
  - new credit issued;
  - deposit-money growth;
  - application approval rates;
  - investment and output response;
  - cumulative credit impulse over a fixed response window.
- Also report later defaults, write-offs, inflation, and output reversal. A larger
  initial response is not assumed to imply higher welfare or greater stability.

### H7: Institutional dependence

> The macroeconomic effects of market rate discovery depend on settlement
> liquidity, bank capital constraints, and lender-of-last-resort access.

Operational tests:

- Interact the rate regime with:
  - the initial supply and distribution of reserves;
  - the regulatory capital requirement;
  - the availability and price of emergency central liquidity.
- Measure whether these institutions alter credit expansion, rate dispersion,
  payment failures, defaults, output volatility, and bank failures.

This is the paper's principal boundary-condition hypothesis: "market determined"
does not mean institution free.

## 4. Experimental design

### 4.1 Core factorial design

Rate formation and agent behavior must be varied independently.

| Rate regime | Rule-based decisions | LLM-based decisions |
| --- | --- | --- |
| Administered-rate anchor | AR-Rule | AR-LLM |
| Market rate discovery | MR-Rule | MR-LLM |

The primary institutional comparison is AR versus MR. The LLM comparison is a
behavioral specification and robustness exercise. It must not be confounded with
the rate regime.

Primary estimands:

1. the average effect of MR relative to AR within rule-based agents;
2. the average effect of MR relative to AR within LLM agents; and
3. the interaction between the MR regime and LLM behavior.

Rule-based agents provide the reproducible baseline. LLM agents test whether richer,
heterogeneous bounded decisions change the institutional result.

### 4.2 Institutional scenarios for H7

Each core cell is evaluated under a limited scenario grid:

- settlement liquidity: scarce, baseline, abundant;
- capital requirement: low, baseline, high;
- lender of last resort:
  - unavailable;
  - available at a fixed penalty spread;
  - available against eligible assets with a borrowing limit.

The initial study should vary one institutional dimension at a time around the
baseline. A full factorial grid is reserved for robustness analysis because it can
be computationally expensive and difficult to interpret.

### 4.3 Shocks

Shocks are generated outside the LLM and shared across matched runs.

Required shocks:

- positive aggregate demand shock;
- positive firm productivity shock;
- borrower-risk shock;
- bank-capital loss;
- uneven reserve outflow or liquidity shock;
- expected-inflation information shock.

Each shock record contains a shock type, target, magnitude, period, duration, and
random seed. Baseline runs without shocks establish endogenous dynamics.

### 4.4 Replication

- Use matched seeds across institutional regimes.
- Separate the environment seed, matching seed, shock seed, and behavioral seed.
- Begin with at least 30 completed replications per experimental cell for pilot
  analysis.
- Determine final replication counts using pilot variance and a simulation-based
  power analysis.
- Treat an LLM infrastructure or schema failure as a failed observation, never as
  an economic rejection or zero-demand decision.

The frozen specification uses 30 matched replications for H2, H3, and abundant
H7 cells. The scarce H7 cells use 40 replications following the documented
pilot-variance extension in `docs/evidence_protocol_v0.2.md`.

## 5. Institutional model

### 5.1 Agents

**Firms**

- produce goods;
- pay wages;
- form inflation and demand expectations;
- choose desired borrowing and a reservation rate;
- solicit offers from multiple banks;
- accept compatible offers;
- invest loan proceeds and service debt;
- default under an explicit insolvency or illiquidity rule.

**Banks**

- hold reserves and loan assets;
- issue deposits as liabilities when loans originate;
- assess applications and quote rate-quantity pairs;
- settle outgoing payments using reserves;
- borrow or lend in the interbank market;
- use emergency liquidity when eligible;
- absorb credit losses through income and equity.

**Households**

- supply labor;
- receive wages and bank deposits;
- consume using an explicit income/wealth rule;
- hold deposits at heterogeneous banks.

**Central monetary authority**

- issues the common settlement asset;
- operates reserve accounts and payment settlement;
- sets prudential parameters;
- supplies emergency liquidity according to the experimental rule;
- sets a policy-rate anchor only in the administered-rate regime.

The authority does not choose individual loan approvals or loan spreads.

### 5.2 Credit-market sequence

For each period:

1. Firms observe their state and common information.
2. Firms submit credit applications with a requested amount, maturity, and maximum
   acceptable rate.
3. Multiple eligible banks observe each application.
4. Banks independently submit an approved amount and nominal rate or reject.
5. Firms rank compatible offers and accept the cheapest available funding, subject
   to quantity and concentration constraints.
6. Accepted contracts create a bank loan asset and a matching borrower deposit.
7. Spending transfers deposits and creates reserve-settlement obligations.
8. Banks resolve reserve shortfalls through the interbank market or the specified
   central liquidity facility.
9. Firms produce, receive revenue, repay debt, or default.
10. Accounting identities, market outcomes, and expectations update.

### 5.3 Rate definitions

The model must not use one scalar for every meaning of "the interest rate."

- `offered_nominal_rate`: a bank's quote on an application.
- `contract_nominal_rate`: the accepted contractual rate.
- `market_nominal_rate`: principal-weighted mean rate on newly accepted loans.
- `outstanding_book_rate`: remaining-principal-weighted mean rate on active loans.
- `interbank_rate`: rate on settlement-liquidity loans.
- `emergency_rate`: rate charged by the central liquidity facility.
- `expected_real_rate`: contract nominal rate minus expected inflation over the
  contract horizon.
- `realized_real_rate`: contract nominal rate minus subsequently realized inflation
  over a defined horizon.

If no new loan is made, `market_nominal_rate` is missing for that period; it is not
zero. The outstanding-book rate remains observable when active loans exist.

### 5.4 Money definitions

- `base_money`: currency plus reserves issued by the central authority.
- `deposit_money`: household and firm bank deposits.
- `broad_money`: currency held outside banks plus deposit money.
- `new_credit`: principal originated during the period.
- `outstanding_credit`: remaining principal on all active loans.

Loan origination expands loan assets and deposit liabilities by the same principal.
Principal repayment reduces both outstanding loans and deposits. Interest payments
transfer deposits and affect income/equity but do not destroy principal twice.

## 6. Behavioral specifications

### 6.1 Rule-based agents

Rule-based behavior should be economically transparent and use the same observable
information supplied to LLM agents.

Firm demand should depend on expected sales or productivity, existing leverage,
cash, expected inflation, and the expected borrowing rate.

Bank quotes should depend on expected funding cost, expected inflation, borrower
risk, maturity, concentration, capital scarcity, and liquidity scarcity.

### 6.2 LLM-based agents

LLMs choose bounded economic actions from a strictly defined state. They do not
perform accounting or override feasibility constraints.

Every LLM invocation records:

- provider and exact model identifier;
- decoding parameters;
- prompt-template version and prompt hash;
- observable state supplied to the agent;
- structured response;
- brief decision rationale;
- request latency and retry count;
- parse, timeout, or provider failure status.

The schema must not request private chain-of-thought. A short economic rationale is
sufficient for analysis.

Fallback behavior must be explicit. Failed LLM calls are either retried or mark the
run incomplete according to a preregistered rule. They are never silently converted
to zero loan demand or loan rejection.

## 7. Outcome variables

### Primary outcomes

- new credit and credit growth;
- deposit-money growth;
- offered and accepted nominal rates;
- rate dispersion;
- expected and realized real rates;
- approval probability and quantity rationing;
- output and output volatility;
- inflation and inflation volatility;
- default rate and principal write-offs;
- bank equity, capital ratios, and bank failures;
- interbank borrowing and emergency-liquidity use.

### Secondary outcomes

- consumption and investment;
- firm leverage distribution;
- bank market concentration;
- application search intensity;
- unmatched credit demand;
- payment-settlement failures;
- interest income and borrower debt-service burden.

No aggregate called "money supply" should be reported without identifying which
money definition it represents.

## 8. Data model

The final data product consists of normalized tables joined by `experiment_id`,
`run_id`, and explicit entity identifiers.

### `experiments`

- experiment and specification version;
- code commit;
- rate regime and behavior mode;
- institutional parameters;
- population sizes and horizon;
- model and prompt versions;
- seed bundle;
- start time, completion status, and failure reason.

### `period_macro`

- period;
- base, deposit, and broad money;
- new and outstanding credit;
- each aggregate rate definition;
- output, consumption, investment, and inflation;
- defaults, write-offs, bank failures;
- interbank volume and emergency borrowing.

### `agent_states`

- period and agent identifier/type;
- cash/deposits, debt, assets, liabilities, and equity;
- expectations;
- firm production and risk measures;
- bank reserves, capital ratio, liquidity ratio, and loan exposure.

### `credit_applications`

- application and firm identifiers;
- requested principal and maturity;
- reservation rate;
- observed borrower state;
- decision source, rationale, and LLM status metadata.

### `bank_offers`

- application, bank, and offer identifiers;
- approved quantity and offered rate;
- rejection reason;
- bank and borrower state visible at decision time;
- decision source, rationale, and LLM status metadata.

### `loan_contracts`

- accepted offer and loan identifiers;
- lender, borrower, principal, rate, maturity, and origination period;
- repayment schedule;
- status and termination reason.

### `loan_events`

- payment, interest, principal, delinquency, default, recovery, or write-off;
- scheduled and actual amounts;
- pre-event and post-event remaining principal.

### `settlement_events`

- payer bank, receiver bank, and reserve amount;
- resulting reserve positions;
- interbank borrowing or emergency-facility use;
- payment completion or failure status.

### `shocks`

- type, target, magnitude, start, duration, and seed.

Raw decision-level data should be retained. Paper tables are derived outputs and
must be reproducible from these tables.

## 9. Identification and analysis

Matched simulations use identical initial populations and exogenous shocks. Only
the assigned institutional or behavioral treatment changes.

A baseline panel specification is:

`Y[r,t] = a + b1*Market[r] + b2*LLM[r] + b3*Market[r]*LLM[r]`
`         + period effects + shock controls + error[r,t]`

H2 additionally uses decision-level models with interactions between the market
regime and borrower risk, bank state, or expected inflation.

H3 uses impulse responses and cumulative responses following matched positive
demand and productivity shocks.

H7 uses interactions between the market regime and capital, reserve-liquidity, and
lender-of-last-resort treatments.

Uncertainty should be calculated across independent simulation runs, not by
treating agent-period observations from one run as independent.

## 10. Validation criteria before final data collection

Final collection cannot begin until:

1. all individual and system-level stock-flow identities pass each period;
2. seeded rule-based runs reproduce exactly;
3. regime assignment changes only the intended mechanisms;
4. LLM failures are observable and do not become economic choices;
5. missing rates are distinguished from zero rates;
6. each headline metric can be reconstructed from event-level records;
7. matched shock experiments pass recovery and direction sanity checks;
8. pilot results are robust to longer horizons and alternative seeds;
9. the experiment configuration and prompt templates are version frozen; and
10. the final dataset is generated from a clean, recorded code commit.

## 11. Immediate implementation sequence

1. Add versioned experiment configuration and separated random seeds.
2. Add structured event-level storage and explicit run-status tracking.
3. correct money and interest-rate definitions.
4. Separate the rate regime from the actor decision mode.
5. Implement multi-bank applications, offers, and firm selection.
6. Add bank-specific deposits and reserve settlement.
7. Add the interbank and emergency-liquidity mechanisms.
8. Implement external seeded shocks.
9. Add system-wide stock-flow and determinism tests.
10. Run the four-cell pilot and simulation-based power analysis.
