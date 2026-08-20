# Market-Determined Interest Rates

This repository is a computational economics model of a centralized dollar with
decentralized bank credit creation and loan-rate discovery. It compares an
administered policy-rate anchor with competitive market pricing while holding
the unit of account, settlement system, prudential rules, agents, and shocks
fixed.

The frozen specification studies:

- **H2:** whether market loan quotes respond more strongly to borrower risk,
  lender reserves/capital, and expected inflation;
- **H3:** whether a positive demand shock generates a larger credit and output
  response under market pricing; and
- **H7:** how reserve scarcity and lender-of-last-resort design condition both
  regimes.

Rule-based agents provide the powered institutional evidence. Local
`deepseek-r1:8b` actors provide a separate descriptive behavioral validation.

## Key artifacts

- Research design: `docs/research_design.md`
- Frozen protocol: `docs/evidence_protocol_v0.2.md`
- Results and interpretation: `docs/results_v0.2.md`
- Evidence inventory: `evidence/README.md`
- Cryptographic manifest: `evidence/manifest_v0_2.json`

## Verification

```bash
./run.sh test
venv/bin/python analyze_evidence.py \
  evidence/paper_evidence_v0_2.sqlite \
  --output evidence/analysis_v0_2
venv/bin/python analyze_llm_pilot.py \
  evidence/deepseek8b_pilot_v0_2_final.sqlite \
  --output evidence/llm_analysis_v0_2
venv/bin/python freeze_evidence.py
```

The freeze verifier audits run statuses, cell counts, period completeness,
foreign keys, model identities recorded during generation, LLM-call integrity,
power thresholds, DGP fingerprints, and artifact hashes.

## Journal-ready v0.3 workstream

Specification 0.3 is a separate pre-confirmatory architecture under `v03/` and
`configs/v0.3/`. It does not mutate or reuse v0.2 evidence databases. See:

- `docs/v0.3_architecture.md`
- `docs/v0.3_data_dictionary.md`
- `docs/replication_v0.3.md`
- `docs/journal_strategy_v0.3.md`

The executable workflow is exposed through `make download-data`, `make data`,
`make calibrate`, `make pilot`, `make pilot-h7`, `make pilot-power`, `make smoke`,
`make freeze-spec`, `make confirm`,
`make llm-robustness`, `make paper-assets`, and `make verify`. The calibration
command currently enforces a hard held-out gate; confirmatory execution cannot
start while that gate is failing.
