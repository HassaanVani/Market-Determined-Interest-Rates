# Contribution matrix and journal strategy

Updated 20 August 2026 against current journal scopes.

## Contribution matrix

| Literature | Closest existing object | What this paper adds | Evidence needed in manuscript |
|---|---|---|---|
| Credit rationing and relationship lending | Multi-bank artificial credit markets study quantities and firm-bank relationships | Competing partial offers with explicit requested, approved, accepted, and unfunded principal under two rate institutions | H2 allocation effects, pricing decomposition, and borrower-risk ablation |
| Macro-financial agent-based models | Heterogeneous firms/banks, credit-driven production, and bank balance-sheet constraints | Isolates local-state retail credit pricing from the centralized unit of account and settlement asset | Treatment-isolation tests, matched seeds, accounting appendix |
| Bank market organization | Endogenous credit networks affect macroeconomic performance | Holds the monetary unit centralized while varying the information sensitivity of credit prices | Population/topology checks and corrected concentration addendum |
| Monetary implementation and liquidity | Reserves, interbank markets, emergency liquidity, and orderly recapitalization | Separates liquidity assistance from insolvency resolution and estimates regime × reserve × facility dependence | H7 interactions, authority-money ledger, and resolution accounting |
| Empirical ABM calibration | Stylized-fact or microdata calibration | Recent-US joint bank resampling, deterministic minimum distance, explicit holdout gates, and source fingerprints | Calibration/validation table, exclusion log, fitted-versus-normalized parameter table |
| Reproducible computational experiments | Simulation moments and robustness exercises | Predeclared seed-level estimands, power-adjusted matched runs, immutable normalized events, and exact source/Parquet validation | Frozen protocol, 8,096 runs, bootstrap/Holm details, release manifest |
| LLM economic agents | Open-ended or prompt-conditioned decisions | Bounded actions in identical institutional states as secondary behavioral robustness only | 30 matched pairs, 900 valid calls, rule comparison, prompt-template audit |

## Literature anchors to read and cite

- Stiglitz and Weiss (1981), *Credit Rationing in Markets with Imperfect
  Information*, for the canonical distinction between interest-rate adjustment
  and quantity rationing.
- Ashraf, Gershman, and Howitt, *Banks, Market Organization, and Macroeconomic
  Performance*, for bank-mediated exchange networks, macro fluctuations, and
  empirical calibration: https://www.nber.org/papers/w17102
- Dosi and Roventini (2017), *Macroeconomic Policy in DSGE and Agent-Based
  Models Redux*, for the computational-laboratory framing and the methodological
  status of macro ABMs: https://jasss.soc.surrey.ac.uk/20/1/1.html
- Zhang et al. (2018), *Credit Rationing and the Simulation of Multi-bank Credit
  Market Model*, as a close artificial-credit-market comparison:
  https://doi.org/10.1007/s10614-017-9726-0
- Hendry et al. (2025), *Agent-based modeling at central banks*, for the modern
  central-bank ABM landscape across financial stability, payments, and monetary
  applications: https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/agent-based-modeling-at-central-banks-recent-developments-and-new-challenges.pdf
- The Bank of England's DeTail stock-flow-consistent ABM is a particularly close
  recent benchmark for credit-driven production and explicit central-bank
  recapitalization: https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2026/the-devil-in-the-detail-assessing-state-contingent-tail-effects.pdf
- Neuner et al. (2025), *Agent-based modeling of long-term bank credit*, for
  decentralized bank-firm matching and selective lending:
  https://doi.org/10.1007/s11403-025-00454-2

## Target ladder

1. **Journal of Economic Dynamics and Control — stretch.** Its scope explicitly
   includes economic dynamics and computational methods. Submit here only after
   the local sensitivity gap and calibration chronology are closed:
   https://www.sciencedirect.com/journal/journal-of-economic-dynamics-and-control
2. **Journal of Economic Interaction and Coordination — strongest substantive
   fit.** Its stated focus is heterogeneity, agent interaction, emergent
   phenomena, and agent-based methods:
   https://link.springer.com/journal/11403
3. **Computational Economics — strongest methods fit.** Its current scope
   expressly covers agent-based modeling, machine learning, and dynamic systems:
   https://link.springer.com/journal/10614
4. **Journal of Artificial Societies and Social Simulation — credible fallback.**
   Best if the manuscript foregrounds controlled simulation, verification, and
   reproducibility more than banking-policy contribution:
   https://jasss.soc.surrey.ac.uk/

Recommended submission order after the hostile audit: **JEDC once**, then
**JEIC**, then **Computational Economics**. Do not simultaneously submit.

The paper's defensible claim is institutional: decentralized local-state
pass-through changes credit allocation and interacts with settlement liquidity
and backstop design. It should not claim that the simulations estimate an
optimal US monetary regime.
