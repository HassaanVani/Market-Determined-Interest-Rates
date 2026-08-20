# Calibration and validation chronology

This record is based on preserved artifacts and filesystem timestamps. It is
written to prevent the manuscript from overstating the independence of the
2025 validation exercise.

## 16 August 2026

1. The 2022Q1–2024Q4 estimation sample and 2025Q1–Q4 validation sample were
   processed through the immutable data pipeline.
2. At 13:46 EDT, `rejected_six_of_eight_candidate.json` recorded normalized
   RMSE 0.161 and six of eight validation groups inside their bootstrap
   intervals. This candidate did not satisfy the declared seven-of-eight gate
   used by the final pipeline.
3. At 13:53 EDT, the final candidate and report were written. They retained
   normalized RMSE 0.161 and moved to seven of eight groups inside the
   intervals, with no group over two empirical standard errors away.
4. Relative to the preserved rejected candidate, the final bundle slightly
   changed the administered spread and added fitted transition parameters for
   the loan/deposit target and deposit reallocation mechanism. The 2025 results
   were therefore observed before the final accepted bundle was written.
5. Pilot summaries were generated beginning at 13:55 EDT. Power analysis was
   written at 14:17 EDT, before the final confirmatory seed namespace was run.

## Required manuscript wording

The 2025 period must be called an **out-of-sample validation period used with a
predeclared acceptance gate**, not a pristine untouched holdout. Because one
failed candidate was revised after inspecting the validation result, the 2025
exercise provides guarded validation evidence but not a fully independent final
test. This limitation must be disclosed.

For a stronger JEDC submission, add a genuinely untouched later release (for
example, a frozen 2026 vintage when enough quarters are available) without
changing the existing model. JEIC or Computational Economics may accept the
current design if the chronology is explicit and the remaining calibration and
sensitivity evidence is strong.
