# Hostile-referee audit: v0.3 evidence package

Status labels: **closed**, **open before submission**, or **disclose as a
limitation**. This audit is intentionally stricter than the manuscript.

| Referee objection | Current evidence | Status / required response |
|---|---|---|
| The regimes merely impose different average rates. | Intercepts are calibrated for comparable baseline means; pricing components are separately logged. | **Closed.** Show regime levels and decomposition. |
| Agent-period observations inflate the sample size. | Estimation and bootstrap operate on matched independent seeds. | **Closed.** State the seed as the sampling unit everywhere. |
| H2 is only a tautological pricing-coefficient result. | Primary H2 outcomes are credit-weighted productivity and unfunded-demand share; pass-through is mechanism validation. | **Closed.** Lead with allocation/quantity results. |
| The model was tuned after seeing final results. | v0.2 is exploratory; v0.3 estimands, exclusions, seeds, and run counts were frozen before final collection. | **Closed**, subject to including both protocols and fingerprints. |
| The concentration robustness cells are fake duplicates. | The defect was discovered and disclosed after v0.3 confirmation. | **Open before submission.** Use only the frozen v0.4 correction and preserve the invalid v0.3 cells in the archive. |
| H3 is presented as a universal property of market pricing. | The global stress map reverses the credit sign in 84/100 sets and the output sign in 15/100. | **Disclose as a limitation.** Claim only the recent-US calibrated result and map its boundary. |
| The sensitivity grid is implausibly far from calibration. | The original grid is labeled global stress testing. Frozen local-sensitivity v2 uses common random numbers and ±10% one-at-a-time changes around calibration; 12/13 sets preserve each H3 sign. | **Closed with boundary disclosure.** Report the lower-risk-price reversal and exclude invalidated v1. |
| Zero defaults make credit-performance claims uninformative. | Principal baseline cells have zero defaults/write-offs. | **Disclose as a limitation.** Do not imply improved realized default performance; treat it as an uninformative secondary outcome. |
| Output per credit is mechanically explosive near zero credit. | Five market baseline seeds originate no credit. | **Closed by disclosure.** Keep the ratio secondary and report denominator failures. |
| Calibration validates too few structural mechanisms. | Bank-side moments are empirical; several real-side parameters are normalized/literature-motivated. | **Disclose as a limitation.** Separate fitted and nonidentified parameters and rely on sensitivity for the latter. |
| The 2025 holdout was used for revision and is no longer a pure holdout. | The chronology preserves a rejected six-of-eight candidate and the later accepted seven-of-eight bundle. | **Disclose as a limitation.** Call 2025 out-of-sample validation with model-selection leakage; add an untouched later vintage for the strongest JEDC case. |
| Balance-sheet or settlement identities may fail silently. | Unit/property tests, double-entry checks, shard validation, and exact Parquet/source row-count validation pass. | **Closed**, after final release verification. |
| The LLM section is unreplicable or prompt-driven. | Model/prompt/schema hashes, temperature zero, bounded actions, call diagnostics, and a three-template audit are stored. | **Closed for infrastructure**, but **disclose** that one small local model is not behavioral external validity. |
| Multiple testing was ignored. | Holm correction is applied within each two-outcome primary family. | **Closed.** Keep secondary outcomes explicitly secondary. |
| The sample is called US dollars although it is normalized. | Median sampled bank deposits equal 100 model units. | **Closed.** Never label model magnitudes as dollars. |
| The study answers optimal US monetary policy. | Design is a controlled institutional mechanism comparison. | **Closed only if wording stays disciplined.** Remove optimality and forecast language. |
| Replication requires retaining 30+ GB of SQLite shards. | Immutable Parquet, DuckDB, source hashes, and a source snapshot form the compact release. | **Open before purge.** Verify the final release hash chain, then delete shards only with explicit approval. |

## Submission gates

1. Corrected concentration addendum completes and validates.
2. Local-neighborhood sensitivity v2 and its risk-price boundary are reported;
   invalidated v1 is excluded.
3. Final release manifest verifies after regenerating every paper asset.
4. Calibration revision chronology is included and its holdout limitation is
   reflected in the manuscript.
5. Manuscript claims are cross-checked against generated tables.
6. A clean environment reproduces at least one smoke cell and all analysis.
7. Archive location and DOI plan are selected before submission.
