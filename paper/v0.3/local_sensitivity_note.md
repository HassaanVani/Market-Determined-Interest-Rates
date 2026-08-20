# Local H3 sensitivity addendum

The preregistered global Latin-hypercube design is a broad stress map and lies
far from the calibrated neighborhood on some dimensions. A separate
post-confirmatory addendum therefore varies six parameters one at a time by
minus/plus 10 percent around the frozen calibration:

- production elasticity;
- investment share;
- base credit demand;
- borrower-risk price;
- liquidity price; and
- capital price.

Version 1 of this addendum used different random-number streams across parameter
sets. It remains archived but is invalid for cross-parameter comparisons and is
not used. Frozen version 2 uses the same 20 matched seeds for all 13 parameter
sets. It contains 1,040 runs. Every run completed, and consolidation has exact
source/Parquet counts with zero incomplete horizons.

The calibrated-base estimate in this smaller independent namespace closely
matches the main H3 point estimate: -0.1435 model units for cumulative new
credit. The 20-seed interval includes zero, as expected from its much lower
power than the 809-seed confirmatory design.

For both cumulative credit and cumulative output, the dampening sign remains
negative in 12 of 13 parameter sets. The only reversal occurs when the
borrower-risk-pricing coefficient is reduced by 10 percent:

- cumulative credit: +0.0623, 95% interval [-0.2105, 0.3503];
- cumulative output: +0.0271, 95% interval [-0.4597, 0.5241].

Both reversals are small and statistically indistinguishable from zero. Raising
the risk-price coefficient by 10 percent strengthens the credit dampening effect
to -0.4853, with a 95% interval [-0.8859, -0.1015].

The defensible conclusion is therefore conditional but locally informative:
H3 is stable to modest changes in five of the six examined dimensions and to a
higher risk-price coefficient, but it approaches zero and can reverse under a
modest weakening of borrower-risk pricing. This complements the borrower-risk
ablation, which independently identifies the same mechanism.
