# Results, specification 0.2

## Evidence status

The final institutional dataset contains 480 completed runs and 6,240
run-period states (including period zero). H2 and H3 use 30 matched replications
per cell. The scarce-reserve H7 cells use 40 after the documented adaptive power
extension.

## H2: supported

Market pricing is more sensitive to every modeled local-state signal than
administered pricing. Market-minus-administered slope differences are:

- borrower leverage: 0.0118 (95% CI 0.0117, 0.0120);
- borrower risk: 0.0030 (0.0029, 0.0031);
- reserve buffer: -0.0014 (-0.0018, -0.0011);
- capital buffer: -0.0044 (-0.0048, -0.0041); and
- expected inflation: 0.9785 (0.9691, 0.9879).

The signs are economically coherent: risk and inflation raise market quotes,
while stronger reserve and capital buffers lower them.

## H3: mechanism present, proposed direction rejected

The positive demand shock increases administered-regime new credit by 31.48
(95% CI 27.89, 35.06) and output by 54.44 (53.94, 54.94). In the market regime,
new credit falls by 38.09 (-62.64, -13.54), while output still rises by 18.14
(5.98, 30.31).

The matched market-minus-administered difference-in-differences is:

- new credit: -69.57 (-94.82, -44.31);
- output: -36.30 (-48.10, -24.50); and
- mean inflation: 0.0007 (0.0004, 0.0009).

Thus H3 is not supported in its proposed “larger market credit response”
direction. In this calibration, decentralized risk/liquidity pricing makes
credit supply more elastic in the contractionary direction and dampens the real
response to a positive demand shock. This negative result is a paper result,
not a failed simulation.

## H7: supported

Institutional support materially changes outcomes under reserve scarcity.
Relative to no backstop, a penalty facility changes cumulative new credit by:

- +576.10 (95% CI 574.02, 578.19) in the administered regime; and
- +63.63 (45.41, 81.85) in the market regime.

It reduces cumulative unresolved liquidity shortfall by 1,395.38 in both
regimes (95% CI -1,461.27, -1,329.49).

Relative to the limited facility, the penalty facility changes cumulative new
credit by +546.10 (544.02, 548.19) under administered pricing and +33.63
(15.41, 51.85) under market pricing. It also reduces unresolved shortfall by
671.64 and 1,232.53, respectively.

The evidence supports the boundary-condition claim: decentralized rate
formation does not remove dependence on settlement liquidity and central
backstop design.

## DeepSeek R1 8B robustness layer

The final LLM validation contains 6 completed runs and 42 successful calls with
zero failures and zero retries. Eighteen firm applications produced 12 positive
requests, 24 approved bank offers, and 12 accepted contracts. Mean call latency
was 11.49 seconds.

Mean one-period new credit was 88.33 in both regimes. Mean accepted nominal
rates were 0.0408 under administered pricing and 0.0400 under market pricing.
With only three matched replications per regime, these are behavioral validation
statistics, not powered treatment-effect estimates.

## Claim boundary

These are causal treatment effects inside the specified computational economy.
They are not estimates for the United States economy and do not establish that
LLM decisions represent human firms or bankers. The paper can claim mechanism
identification, reproducible comparative statics, and explicit institutional
boundary conditions.
