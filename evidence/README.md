# Frozen evidence package, version 0.2

## Included in inference

- `paper_evidence_v0_2.sqlite`: 480 completed rule-based runs
- `analysis_v0_2/`: H2 slopes, H3 impulse responses, H7 contrasts, power table,
  and human-readable summary
- `deepseek8b_pilot_v0_2_final.sqlite`: six completed DeepSeek R1 8B validation
  runs with 42 successful calls
- `llm_analysis_v0_2/`: call audit and descriptive LLM results
- `dgp_source_b15fc02ecf92a7e3.tar.gz`: exact rule DGP source
- `dgp_source_c89b0b80fef6e979.tar.gz`: exact final LLM DGP source
- `test_report_v0_2.txt`: 38 passing tests
- `manifest_v0_2.json`: validation results and SHA-256 hashes

## Excluded

`diagnostics/` contains calibration data, superseded specification-0.1 results,
two deliberately preserved invalid DeepSeek token-budget tests, a minimal
structured-output check, and the pilot that exposed the pre-fix async client
lifecycle warning. These artifacts are retained for transparency and are
excluded from all reported estimands.

## Interpretation

H2 and H7 are supported. H3's mechanism is identified, but its proposed
direction is rejected: market pricing dampens credit and output responses to the
positive demand shock in specification 0.2. The DeepSeek sample validates actor
execution and logging but is not powered for treatment-effect inference.
