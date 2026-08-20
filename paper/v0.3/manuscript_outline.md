# Manuscript architecture: decentralized credit pricing with centralized money

Target main-text length: 10,000–12,000 words, excluding references and the
technical appendix. The paper is an institutional-mechanism study, not a
quantitative forecast of an alternative US monetary regime.

## Working title

**Central Money, Decentralized Credit Prices: Allocation, Shock Transmission,
and Liquidity Backstops in a Calibrated Agent-Based Economy**

## Abstract — 180–220 words

State the institutional contrast, model, recent-US calibration, preregistered
matched-seed design, principal H2/H3/H7 findings, and bounded DeepSeek exercise.
Do not introduce welfare optimality or claim external causal identification.

## 1. Introduction — 1,200–1,500 words

1. Motivate the distinction between centralized currency/settlement and
   decentralized retail credit pricing.
2. Ask how local-state-sensitive pricing changes allocation, demand-shock
   transmission, and dependence on reserves/backstops.
3. State the three contributions: institutional decomposition; measured
   quantity/allocation mechanism; reproducible calibrated simulation evidence.
4. Preview results with magnitudes and intervals.
5. Explain scope: mechanism evidence rather than an optimal-policy estimate.

## 2. Related literature and institutional framing — 1,000–1,300 words

Organize by credit rationing/bank lending, agent-based macro-finance,
market-based versus administered benchmarks, settlement liquidity/backstops,
and LLM economic agents. The contribution matrix belongs here or in the
appendix. Hayek is background motivation only; the paper's novelty is not a
broad claim about decentralized knowledge.

## 3. Model — 2,000–2,400 words

### 3.1 Timing and agents

Give the 24-period event order and identify firms, five banks, the aggregate
household/capital-goods supplier, and the monetary authority.

### 3.2 Firm demand, offer clearing, and partial fills

Define requested principal, expected return, maturity, purpose, offer ranking,
the lender concentration limit, accepted principal, and unfunded demand.

### 3.3 Rate institutions

Write both pricing equations term by term. Emphasize that the common intercepts
were calibrated to make baseline mean rates comparable; the intended treatment
is local-state pass-through, not an imposed level difference.

### 3.4 Production and household demand

Document the Cobb–Douglas block, working capital, investment, depreciation,
capital ownership, consumption plan, goods constraint, sales allocation,
inventory, and unmet demand.

### 3.5 Balance sheets, settlement, default, and resolution

Show stock-flow identities, loan amortization, recovery, provisional finality,
interbank borrowing, emergency liquidity, insolvency status, and explicit
authority recapitalization.

## 4. Data and calibration — 1,300–1,600 words

Describe the 2022Q1–2024Q4 calibration sample, 2025Q1–Q4 holdout, filters,
winsorization, equal-bank and asset-weighted moments, joint empirical bank
resampling, normalization to model units, bootstrap weighting, ten-start
minimum distance, and pass/fail gates. Report normalized RMSE 0.161, seven of
eight held-out groups inside the 95% intervals, and no group over two standard
errors away. Clearly separate empirically fitted parameters from normalized or
literature-motivated production parameters.

## 5. Experimental design and inference — 1,000–1,300 words

State H2a/H2b, H3, and H7 verbatim. Explain the pilot/final seed separation,
809 matched main seeds, 40 H7 seeds per cell, seed-level inference, paired
bootstrap, Holm correction, fixed response window (periods 8–23), ablations,
topology checks, and global stress mapping. Note the post-confirmatory v0.4
concentration addendum separately.

## 6. Results — 1,800–2,200 words

### 6.1 H2: mechanism and allocation

Lead with full versus attenuated local pass-through. Report the market-minus-
administered effects: credit-weighted productivity +0.0751 and unfunded-demand
share +0.4932, with frozen confidence intervals. Report five market runs with
zero new credit and explain why their credit-weighted productivity is undefined.

### 6.2 H3: demand-shock transmission

Report the credit DID of -0.1445 and output DID of -0.3512. Translate these as
approximately 3.6% and 1.1% smaller positive impulses relative to the
administered regime, while retaining model-unit results and intervals.

### 6.3 H7: reserve and facility dependence

Report the preregistered interactions and anchor contrasts. Explain that low
reserves generate unresolved shortfalls in the market regime when the facility
is unavailable, while high reserves or a penalty facility remove those
shortfalls in the tested anchors.

### 6.4 Robustness and boundaries

The borrower-risk-pricing ablation nearly eliminates the central H2/H3 contrast.
Population/bank-count checks preserve H2. The global Latin-hypercube exercise is
an intentionally broad stress map: H3's credit sign reverses in 84/100 parameter
sets and output reverses in 15/100, so the calibrated result is conditional, not
universal. Add the corrected concentration results from the frozen addendum.

### 6.5 DeepSeek R1 8B

Report 30/30 completed pairs, 900/900 valid main calls, zero retries, and the
prompt audit. The market-minus-administered LLM mean offered-rate effect is
+0.00552; requested principal is statistically indistinguishable across regimes,
while approved principal is -0.4297 model units. Treat this as bounded behavioral
robustness, not evidence replacing the rule-agent experiment.

## 7. Discussion and limitations — 800–1,000 words

Discuss the aggregate household, normalized goods/wage prices, short horizon,
recent-US banking calibration, zero baseline defaults in the principal cells,
conditional H3 sign, model-specific resolution authority, and limited external
validity of a small local LLM. Distinguish market pricing from decentralized
currency supply: the unit of account and settlement asset remain centralized.

## 8. Conclusion — 400–600 words

Restate the institutional result without policy optimality language. Identify
future work on household heterogeneity, endogenous bank entry, richer defaults,
and empirical identification of real-side parameters.

## Technical appendix

Include complete equations and timing, data dictionary, source/exclusion audit,
calibration objective and bootstrap, all parameter tables, power calculations,
secondary outcomes, ablations, topology/concentration addendum, global phase
maps, LLM prompts/schema/audit, accounting tests, and replication commands.
