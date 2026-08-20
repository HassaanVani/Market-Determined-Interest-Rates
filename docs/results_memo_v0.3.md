# Confirmatory results memo — specification 0.3

## Status and interpretation rule

This memo translates the frozen rule-agent evidence into manuscript language. It
does not turn the model into a US policy forecast. Effects are market-regime
minus administered-regime differences in model units unless stated otherwise.
Unfavorable outcomes, undefined estimands, inactive mechanisms, and robustness
failures remain part of the reported evidence.

## H2 — pricing, allocation, and rationing

The market regime implements stronger local-state pricing. Among runs with
valid quotes, its local pass-through parameter is 0.75 higher by construction,
and the estimated loan-rate slope on borrower leverage is 0.02145 higher (95%
bootstrap interval 0.02128 to 0.02163). This is a treatment/manipulation check,
not an independent welfare result.

For the two primary allocation outcomes:

- Credit-weighted borrower productivity is 0.07511 higher in the market regime
  among 804 matched pairs with positive credit in both regimes (95% interval
  0.07206 to 0.07821; Holm-adjusted p approximately 0.0002).
- The mean unfunded-demand share is 0.49318 higher across all 809 matched pairs
  (95% interval 0.48349 to 0.50281; Holm-adjusted p approximately 0.0002).

The corresponding regime levels are informative. Mean credit-weighted
productivity is 1.07546 under administered pricing and 1.15104 under market
pricing, while mean unfunded demand rises from 0.03812 to 0.53130. Thus, the
market regime directs the credit it supplies toward more productive borrowers,
but does so alongside much more severe aggregate rationing. This is a
selection-versus-quantity tradeoff, not an unambiguous efficiency improvement.

Five of 809 market-regime baseline runs generate zero new credit. Their
credit-weighted productivity and quote-based mechanism slopes are structurally
undefined; no administered run has this outcome. The conditional productivity
estimate therefore uses 804 complete pairs, and the five zero-credit outcomes
must be reported separately rather than assigned an invented value.

Secondary H2 diagnostics reinforce the mechanism:

- Quoted-rate dispersion is 0.00496 higher.
- The leverage gradient of the unfunded-demand share is 0.39114 higher.
- Output per unit of new credit is higher conditional on positive credit, but
  this ratio is mechanically sensitive to the market regime's much smaller
  credit denominator and is not a welfare measure.
- Baseline defaults and write-offs are zero in both regimes. The calibrated
  baseline therefore cannot identify comparative default-loss effects.

## H3 — positive demand-shock transmission

The preregistered cumulative response window is periods 8 through 23. The
positive demand shock raises cumulative new credit by 4.00691 under administered
pricing and 3.86237 under market pricing. The market-minus-administered
difference in impulse responses is -0.14454 (95% interval -0.21664 to -0.07107;
Holm-adjusted p approximately 0.0003), about 3.6% of the administered credit
impulse.

The corresponding output impulse is 30.86338 under administered pricing and
30.51219 under market pricing. The difference is -0.35119 (95% interval
-0.45484 to -0.24840; Holm-adjusted p approximately 0.0002), about 1.1% of the
administered output impulse.

H3 is therefore supported in the recent-US calibration: market pricing modestly
dampens both credit and output responses. The effect is precisely estimated
because of 809 matched seeds, but economically small relative to the total
shock response.

The ablation results locate the mechanism. Disabling borrower-risk pricing
reduces both H3 interactions essentially to zero. Disabling inflation
pass-through also produces small, statistically uncertain positive estimates.
Other ablations retain negative output interactions, although many 30-seed
credit intervals cross zero. Borrower-risk pricing is therefore central to the
main H3 result.

## H7 — reserve abundance and backstop design

At the low-reserve, unavailable-facility anchor, the market regime produces
8.59854 less cumulative credit than the administered regime and 0.73728 less
unresolved liquidity shortfall. At high reserves with no facility, unresolved
shortfalls are structurally zero in both regimes and the market credit gap is
-12.25852. At low reserves with a penalty facility, unresolved shortfalls are
also zero and the market credit gap is -11.73893.

The two preregistered interactions are nonzero:

- Moving from high to low reserves when the facility is unavailable changes
  the market-versus-administered credit contrast by +3.65998 and the liquidity
  contrast by -0.73728.
- Replacing a penalty facility with no facility at low reserves changes the
  credit contrast by +3.14039 and the liquidity contrast by -0.73728.

All four 95% intervals exclude zero after within-comparison Holm correction.
The signs require care: reserve scarcity and facility design alter the relative
credit contraction under market pricing, while the market regime reduces
unresolved shortfalls only in the cell where shortfalls actually occur. H7
supports institutional dependence, not the claim that less liquidity support
is universally desirable.

## Robustness map

Population/bank-count checks at 30 firms/3 banks, 30/5, and 100/5 preserve the
positive productivity-selection and higher-rationing results.

The original low/high deposit-concentration cells are invalid because empirical
initialization bypassed the switch. They remain archived and excluded. A
separately frozen post-confirmatory addendum corrected the initialization path
without changing v0.3. All 150 addendum runs completed and validated. In the
30-firm/five-bank cells, opening deposit HHI rises from 0.2012 to 0.2906, while
the H2 productivity-selection and rationing effects retain their signs. These
are within-cell regime robustness results, not causal concentration estimates.

The 100-set Latin-hypercube analysis is a global stress map, not a local
calibrated sensitivity. In particular, calibrated base credit demand is about
0.078, whereas the stress grid spans approximately 6.06 to 19.93. Within this
extreme region, the H3 credit interaction is negative in 16 sets and reverses
positive in 84; the output interaction is negative in 85 and reverses in 15.
The main calibrated result is therefore conditional and should not be described
as a general theorem.

A separately frozen local-neighborhood addendum varies six parameters one at a
time by plus/minus 10 percent using common random numbers. The corrected v2
design contains 1,040 validated runs. Both H3 signs remain negative in 12 of 13
parameter sets. Reducing borrower-risk pricing by 10 percent produces small,
statistically uncertain positive signs; raising it strengthens dampening. This
local boundary agrees with the borrower-risk ablation. The earlier v1 local
design used different seed streams across parameter sets and is archived but
excluded from interpretation.

Defaults and write-offs occur in some extreme stress-grid runs, but not in the
main calibrated baseline. Those stress outcomes may illustrate nonlinear
regions; they cannot substitute for a calibrated baseline default comparison.

## LLM robustness status

DeepSeek R1 8B is secondary. The final action representation uses bounded 0-1
request and approval shares that the environment maps into feasible principal.
All 30 matched pairs completed. All 900 main calls were valid, with no retries,
so the predeclared comparative gate passed. Market-state prompts raise mean LLM
offered rates by 0.00552 and lower approved principal by 0.42967 model units;
requested principal differs by -0.43347 with an interval spanning zero. The
three-template audit shows a median within-state rate range near zero but some
nontrivial prompt sensitivity, which must be disclosed.

## Defensible paper conclusion if remaining audits pass

In this model, decentralized local-state pricing creates a robust intensive-
margin allocation effect: scarce credit moves toward more productive firms and
rates become more sensitive to borrower risk. That selection gain is paired
with substantially greater credit rationing. Under the recent-US calibration,
market pricing slightly dampens a positive demand shock, and the magnitude of
credit and liquidity effects depends on reserve abundance and backstop design.
These are conditional institutional mechanisms, not evidence of universal
market-rate superiority or an optimal policy prescription for the United
States.
