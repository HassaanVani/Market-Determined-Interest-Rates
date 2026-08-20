# Post-confirmatory concentration addendum

The original v0.3 low/high deposit-concentration topology cells were invalid as
treatment checks because empirical bank initialization bypassed the switch. The
defect was discovered after confirmation and disclosed before the correction.
No v0.3 primary result was changed or rerun.

The separately frozen `v0.4-concentration-addendum-1` rescales empirical bank
balance-sheet sizes while preserving aggregate deposits, within-bank sampled
ratios, and non-size rate/growth variables. It uses a disjoint seed namespace
and 25 matched seeds for each of three settings, totaling 150 runs.

All 150 runs completed. Source-to-Parquet validation passed with zero incomplete
horizons. In the comparable 30-firm/five-bank cells, mean opening deposit HHI is
0.2012 under low concentration and 0.2906 under high concentration.

The market-minus-administered H2 effects remain positive:

| Setting | Credit-weighted productivity | 95% CI | Unfunded-demand share | 95% CI |
|---|---:|---:|---:|---:|
| 30 firms, 5 banks, low | 0.0659 | [0.0555, 0.0762] | 0.6166 | [0.5765, 0.6588] |
| 30 firms, 5 banks, high | 0.0647 | [0.0529, 0.0772] | 0.5970 | [0.5527, 0.6395] |
| 100 firms, 5 banks, high | 0.0681 | [0.0594, 0.0771] | 0.5034 | [0.4742, 0.5356] |

These are within-cell regime robustness estimates. They are not interpreted as
causal effects of changing concentration itself.
