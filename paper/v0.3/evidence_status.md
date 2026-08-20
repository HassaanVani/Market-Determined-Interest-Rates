# Evidence status at manuscript handoff

- Empirical sources verified: 20.
- Calibration normalized RMSE: 0.161; holdout groups inside intervals: 7/8;
  groups beyond two standard errors: 0.
- Frozen v0.3 rule runs: 8,096/8,096 complete.
- Full v0.3 consolidation: exact row-count equality across 16 tables; zero
  incomplete horizons.
- DeepSeek R1 8B: 30/30 matched pairs, 900/900 valid main calls, zero retries.
- Frozen concentration addendum: 150/150 complete; exact consolidation; zero
  incomplete horizons.
- Local sensitivity v1: preserved but invalidated because parameter sets did not
  use common random numbers; excluded from interpretation.
- Frozen local sensitivity v2: 1,040/1,040 runs complete; exact consolidation;
  H3's credit and output signs remain negative in 12/13 local parameter sets.
- Tests: 72 passed before final addendum collection.
- Main, robustness, LLM, and concentration analysis assets regenerate
  byte-identically after pinning DuckDB analysis to one thread.
- Destructive storage cleanup has not been performed.

Remaining submission gates are manuscript drafting, an untouched future-vintage
validation if targeting JEDC, clean-environment replication, archive/DOI
selection, and final claim-to-table audit.
