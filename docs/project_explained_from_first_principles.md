# Market-Determined Interest Rates: from first principles to use

## What this project is asking

The project asks: if the dollar, banks, central-bank settlement, prudential
rules, and emergency liquidity all remain in place, what changes when business
loan quotes respond much more strongly to the particular condition of the
borrower and the bank?

It runs two otherwise identical simulated economies. One uses a policy-anchored
loan-price benchmark with muted local pass-through. The other uses full local
pass-through. It then measures allocation, credit rationing, output after a
shock, and the role of reserve liquidity. This is a controlled computational
laboratory, not a proposal to abolish the dollar, a description of literal US
retail loan pricing, or a forecast of US output.

## Level 1: money, banks, settlement, and interest rates

### Deposits and reserves

Most money firms and households use is a commercial-bank deposit: the bank's
promise to pay its customer on demand. Reserves are bank balances at the central
bank. Deposits are everyday payment money; reserves are the settlement asset
used between banks.

| Liability | Issuer | Main role |
| --- | --- | --- |
| Currency and reserves | Central bank | Final settlement asset |
| Deposits | Commercial banks | Everyday firm/household payments |

When Bank X lends a firm $100, it records a $100 loan asset and credits the
firm's deposit by $100. The loan and deposit are created together. This is not
the story that a bank takes a pre-existing saver deposit and hands it over.
It does *not* mean banks can lend without limit: viable borrowers, expected
losses, capital, liquidity, funding costs, regulation, and competition matter.

If the borrower uses the deposit to buy from a customer at Bank Y, Bank X sends
reserves to Bank Y. The banking system still has the deposit, but Bank X may
need interbank funding or central-bank liquidity to settle. Therefore, reserves
matter chiefly to settlement and funding conditions—not as a simplistic,
dollar-for-dollar reserve requirement that must come before a loan.

There is no one economy-wide interest rate. A policy rate is a central-bank
operating target. An interbank rate prices bank liquidity. A facility rate prices
emergency liquidity. A particular loan rate also includes borrower risk, lender
funding, capital, liquidity, expected inflation, maturity, relationship
information, costs, and competition. Nominal is the dollar rate; expected real
is approximately nominal minus expected inflation.

## Level 2: why credit quantity matters as much as the rate

A loan is a promise, not an ordinary commodity. Raising a rate can change who
still applies and can make riskier projects more attractive. A bank can
rationally refuse an applicant even when that applicant says it will pay a
higher rate. This is credit rationing.

The model thus tracks four distinct quantities:

1. requested credit;
2. bank-approved credit;
3. credit actually accepted by the borrower; and
4. unfunded demand.

That matters because an information-sensitive rate can direct funds toward
stronger projects yet cause more total credit requests to go unfunded. Better
selection among the borrowers who receive loans is not, by itself, a welfare
result; it must be weighed against the lost activity of excluded borrowers.

## Level 3: the exact institutional treatment

The project does not compare central money with private money. Both regimes
retain one dollar unit of account, central-bank reserves, deposit creation by
commercial banks, reserve settlement, capital/liquidity limits, a possible
emergency facility, and resolution of insolvent banks. It changes *only* the
loan-pricing map.

The quote by bank `b` to firm `i` at time `t` is:

\[
r_{ibt}=q_j+s_j+\lambda_j z_{ibt}+\eta_{ib}.
\]

`q` is a shared benchmark, `s` a calibrated intercept/spread, `z` local state,
`lambda` the weight applied to local state, and `eta` a stable bank–firm
relationship effect. Local state includes borrower leverage/default risk, bank
funding pressure, liquidity shortfall, capital shortfall, and expected
inflation.

| Regime | Benchmark | Pass-through of local state |
| --- | --- | --- |
| Policy-anchored, attenuated | Policy rate + calibrated spread | 25% |
| Market discovery, full | Required return + calibrated intercept | 100% |

The intercepts are aligned before experimentation to avoid simply forcing one
regime to have a higher average rate. The intended change is the **slope**: how
much a worsening borrower/bank condition changes a specific quote.

For example, if a common benchmark is 5% and local penalties total 4 points,
the attenuated quote is 6% while the full-pass-through quote is 9%. A project
expected to return 7% can finance at 6% but not 9%. Thus the two systems select
different borrowers even though banks observe the same underlying facts.

The careful name for the first condition is a **policy-anchored,
attenuated-pass-through benchmark**, not a claim that US business-loan rates are
literally administered by a central bank.

## Level 4: how a simulated quarter works

The confirmatory economy contains 30 heterogeneous firms, 5 banks, an aggregate
household/capital-goods supplier, and a monetary authority over 24 quarters.
Firms produce, hire, borrow, invest, sell, repay, and can default. Banks quote
partial contracts, create deposits, settle payments, obtain liquidity, bear
losses, and are resolved when insolvent.

Each period it:

1. completes pending bank resolution;
2. depreciates capital, pays wages, and produces;
3. creates firm applications with amount, maturity, purpose, expected return,
   and maximum acceptable rate;
4. lets banks reject or submit a recorded rate–quantity offer;
5. lets firms accept their cheapest compatible offers, subject to lender
   concentration limits;
6. creates loans and matching deposits, then uses the funds for working capital
   and investment;
7. clears goods sales, inventories, and unmet demand;
8. services loans, records defaults and recoveries;
9. clears interbank then emergency liquidity; and
10. verifies accounting identities and records all events.

The accounting discipline requires firm/household deposits to equal bank deposit
liabilities and firm debt to equal bank loan assets. This does not prove the
model true, but it eliminates results that arise from an unrecorded balance-sheet
error.

## Level 5: empirical discipline and experiment design

FDIC Call Reports and the FR 2028D small-business-lending survey from
2022Q1–2024Q4 discipline selected bank balance-sheet and loan-term moments;
FRED supplies price/rate transformations. The median sampled bank deposits are
normalized to 100, so all output magnitudes are **model units**, not dollars.

Calibration makes selected initial moments more realistic. It does not identify
every household, production, or behavioral parameter, and cannot turn the model
into a causal estimate for the United States. The 2025 validation period has a
documented limitation: a rejected candidate was revised after its result was
seen. It is therefore out-of-sample validation with disclosed model-selection
leakage—not a pristine holdout.

Randomness is handled with matched seeds: the same environment, matching, and
shock are used under both regimes, and the paired difference is the experiment's
estimand. A whole simulation seed is the independent observation, not every
firm-period row. The frozen main study uses 809 matched seeds, and H7 anchors
use 40 matched seeds per cell.

## Level 6: hypotheses and current results

**H2** asks whether full pass-through yields more local-state-sensitive pricing
and changes allocation. Market minus benchmark raises credit-weighted borrower
productivity by 0.0751 model units but raises unfunded demand by 0.4932. That is
a selection–quantity trade-off: funded firms are more productive on average,
yet substantially more requested credit goes unfilled. It is not a welfare
ranking. Five market runs make no new credit, so credit-weighted productivity is
undefined for them and must be disclosed.

**H3** asks how a positive demand shock transmits. Near the calibration, market
minus benchmark cumulative new credit is −0.1445 and output is −0.3512 model
units: fuller pricing pass-through dampens the simulated positive impulse.
The result is conditional, not universal. Local sensitivity retains the signs in
12 of 13 nearby sets, but a broad global stress map reverses the credit sign in
84 of 100 sets and the output sign in 15 of 100.

**H7** asks whether liquidity institutions change the comparison. With low
reserves and no facility, the market regime can leave settlement shortfalls.
Abundant reserves or a penalty facility removes the shortfall at declared anchor
cells, while the relative credit effect remains. The lesson is institutional
complementarity: pricing rules cannot be judged independently of settlement and
backstop design. Liquidity lending and insolvency resolution are separate.

Removing borrower-risk pricing nearly removes the H2/H3 contrast. This confirms
the mechanism inside the model: the results principally come from how borrower
risk enters pricing, rather than a hidden mean-rate level difference. It is not
external empirical proof that the same mechanism quantitatively dominates US
lending.

The DeepSeek R1 8B exercise is a separate, fully audited behavioral robustness
check. It can show what this one bounded language-model decision component does
under fixed prompts and states. It does not validate language models as human
firms or bankers; the paper's core conclusions rely on transparent rule agents.

## Level 7: what the project is useful for

It is useful as a mechanism laboratory. It teaches the distinction between
centralized money/settlement and decentralized loan pricing; it lets researchers
study allocation, rate dispersion, approvals, and rationing jointly; and it
supports controlled ablations and sensitivity tests involving bank balance
sheets, reserves, and emergency liquidity. It can generate hypotheses for later
loan-level or credit-registry empirical research.

It must not be used to forecast US GDP, recommend a real-world reform by itself,
claim an optimal interest-rate regime, convert model units into dollars, or use
the LLM exercise as evidence about human behavior.

The final mental model is simple:

```text
Hold money, settlement, agents, shocks, and regulation fixed
                         │
                         ▼
Change only local-state pass-through in business-loan prices
                         │
        allocation ── quantity rationing ── shock propagation
                         │
                         ▼
          all conditional on reserves and backstop design
```

Its value is precision: it turns a vague debate about “market-determined rates”
into a transparent, reproducible proposition about a specific pricing mechanism
and its institutional dependencies.
