# Web research dossier: Central Money, Decentralized Credit Prices

Research completed 20 August 2026. This dossier maps the economic concepts,
empirical inputs, and scholarly literature needed to write the manuscript in
`paper/v0.3/manuscript_draft.md`. It is a literature and source plan, not
evidence that the model has identified an effect in the United States.

## 1. The project in one precise paragraph

The project is a controlled agent-based computational experiment. It keeps a
centralized unit of account, central-bank settlement asset, commercial-bank
deposit creation, prudential constraints, and a liquidity backstop fixed. Its
treatment is **the pass-through of observable local borrower and bank state to
retail loan quotes**: attenuated around a policy-rate benchmark versus full
pass-through around an endogenous funding/required-return benchmark. It then
measures allocation, quantity rationing, shock propagation, and dependence on
reserves and emergency liquidity. It does **not** estimate the effect of a
real-world abolition of policy rates, establish an optimal monetary rule, or
test a decentralized currency.

## 2. Knowledge ladder for the manuscript

| Level | What a reader needs to understand | Where it belongs | Essential sources |
| --- | --- | --- | --- |
| Introductory macro | Nominal versus real rates; expected inflation; output, investment, and demand shocks; a policy rate is an operating target, not every retail loan rate. | Intro and model notation | [Taylor (1993)](https://web.stanford.edu/~johntayl/Onlinepaperscombinedbyyear/1993/Discretion_versus_Policy_Rules_in_Practice.pdf); [Bernanke & Gertler (1995)](https://doi.org/10.3386/w5146) |
| Monetary institutions | Central-bank liabilities (currency/reserves) differ from bank deposits; bank lending simultaneously creates a loan and a deposit, while capital, funding, regulation, and borrower demand constrain it. Cross-bank payments create reserve-settlement needs. | Intro; model balance sheets | [McLeay, Radia & Thomas (2014)](https://www.bankofengland.co.uk/quarterly-bulletin/2014/q1/money-creation-in-the-modern-economy); [BIS Annual Economic Report (2026), Ch. III](https://www.bis.org/publ/arpdf/ar2026e3.htm) |
| Credit microeconomics | Lending price and quantity are jointly chosen. Higher rates can change the risk composition of applicants; quantity rationing can remain even when prices move. Relationship information can affect price and collateral. | Related literature; H2 | [Stiglitz & Weiss (1981)](https://ideas.repec.org/a/aea/aecrev/v71y1981i3p393-410.html); [Berger & Udell (1995)](https://scholarcommons.sc.edu/fin_facpub/10/) |
| Financial-intermediation macro | Monetary policy can affect borrower balance sheets and the bank supply of loans; policy-rate pass-through is conditional, not mechanical. Bank capital and liquidity affect capacity, funding cost, and lending. | Related literature; H3/H7 | [Kashyap & Stein (1993)](https://doi.org/10.3386/w4317); [Bernanke & Gertler (1995)](https://doi.org/10.3386/w5146); [Vo (2021)](https://www.bankofengland.co.uk/working-paper/2021/interactions-of-capital-and-liquidity-requirements-a-review-of-the-literature) |
| Liquidity and backstops | Liquidity assistance and insolvency resolution are distinct. Reserve abundance/scarcity and standing lending facilities shape settlement outcomes. Classical LOLR ideas require adaptation to modern balance sheets. | H7 and institutional model | [Tucker (2014)](https://www.bis.org/publ/bppdf/bispap79b_rh.pdf); [Abad, Nuño & Thomas (2023)](https://www.bis.org/publ/work1126.htm) |
| Computational macro | ABMs are useful for heterogeneous, networked, non-linear interactions but require explicit validation, sensitivity analysis, transparent timing, and reproducible computation. | Method, calibration, limitations | [Dosi & Roventini (2017)](https://jasss.soc.surrey.ac.uk/20/1/1.html); [Hendry et al. (2025)](https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/agent-based-modeling-at-central-banks-recent-developments-and-new-challenges.pdf); [Windrum, Fagiolo & Moneta (2007)](https://jasss.soc.surrey.ac.uk/10/2/8.html) |
| Closest model class | Multi-bank, bank-firm matching ABMs combine credit constraints, firm investment/production, balance sheets, defaults, and sometimes interbank networks. | Related literature and contribution matrix | [Ashraf, Gershman & Howitt (2017)](https://doi.org/10.1016/j.jebo.2016.09.019); [Zhang et al. (2018)](https://doi.org/10.1007/s10614-017-9726-0); [Neuner et al. (2025)](https://doi.org/10.1007/s11403-025-00454-2) |
| LLM agents | A language model’s choices are an implementation-specific behavioral robustness exercise, not human behavioral evidence or an identification strategy. Fixed prompts, model versions, parsing, failure rules, and seed/call audits matter. | Bounded LLM section and limitations | [STEER (2024)](https://arxiv.org/abs/2402.09552); [Gao et al. (2025)](https://arxiv.org/abs/2505.21371) |

## 3. Claims that should be made—and claims that should not

### Defensible manuscript language

- “The experiment varies the local-state sensitivity of bank loan quotes while
  maintaining centralized money and settlement.”
- “Within this calibrated computational economy, stronger local pass-through
  changes the allocation/quantity trade-off and interacts with liquidity
  institutions.”
- “The recent-US bank data discipline selected bank-side moments; normalized
  production and household parameters are not separately identified from those
  data.”
- “The LLM exercise tests whether this particular bounded decision component
  preserves selected qualitative patterns under the audited prompt and model
  configuration.”

### Claims to avoid

- “The U.S. has administered retail loan rates.” US loan prices already include
  market, bank, and borrower-specific components. Call the comparator a
  **policy-anchored, attenuated-pass-through benchmark**, not a literal
  description of U.S. retail lending.
- “Market rates clear credit markets efficiently.” The Stiglitz–Weiss result is
  the reason the manuscript must treat prices and quantity rationing jointly;
  the project has no welfare objective or welfare calibration.
- “Loans are constrained by a reserve multiplier.” Lending creates deposits,
  but individual banks face settlement, capital, funding, risk, regulation, and
  demand constraints. Use the balance-sheet sequence, not a multiplier story.
- “Liquidity support solves insolvency.” It cannot; retain the distinction
  between collateralized liquidity lending and equity/resolution transfers.
- “The 2025 validation is an untouched holdout.” The repository’s own
  chronology records model-selection leakage. Use its required guarded wording.

## 4. Recommended references for the main manuscript

Use this as the tight 18–22 item reference spine. Verify issue/page metadata
against the publisher or DOI landing page during final BibTeX preparation.

### Money, monetary implementation, and policy transmission

1. McLeay, M., Radia, A., & Thomas, R. (2014). “Money creation in the modern
   economy.” *Bank of England Quarterly Bulletin*, Q1. Explains the loan–deposit
   balance-sheet entry and its constraints. [Official source](https://www.bankofengland.co.uk/quarterly-bulletin/2014/q1/money-creation-in-the-modern-economy).
2. Taylor, J. B. (1993). “Discretion versus policy rules in practice.”
   *Carnegie-Rochester Conference Series on Public Policy*, 39, 195–214.
   [Author-hosted paper](https://web.stanford.edu/~johntayl/Onlinepaperscombinedbyyear/1993/Discretion_versus_Policy_Rules_in_Practice.pdf).
3. Kashyap, A. K., & Stein, J. C. (1993). “Monetary policy and bank lending.”
   NBER Working Paper 4317. [NBER](https://doi.org/10.3386/w4317).
4. Bernanke, B. S., & Gertler, M. (1995). “Inside the black box: The credit
   channel of monetary policy transmission.” *Journal of Economic Perspectives*,
   9(4), 27–48. [NBER version](https://doi.org/10.3386/w5146).
5. Eggertsson, G. B., Juelsrud, R. E., Summers, L. H., & Wold, E. G. (2021).
   “Negative nominal interest rates and the bank lending channel.” *Review of
   Economic Studies*, 88(5), 2111–2139. Conditional pass-through anchor.
   [NBER version](https://doi.org/10.3386/w25416).
6. Abad, J., Nuño, G., & Thomas, C. (2023). “CBDC and the operational framework
   of monetary policy.” BIS Working Papers 1126. Particularly relevant to the
   reserve-scarcity/interbank/standing-facility architecture.
   [BIS](https://www.bis.org/publ/work1126.htm).

### Credit pricing, rationing, information, and relationships

7. Stiglitz, J. E., & Weiss, A. (1981). “Credit rationing in markets with
   imperfect information.” *American Economic Review*, 71(3), 393–410.
   [Record](https://ideas.repec.org/a/aea/aecrev/v71y1981i3p393-410.html).
8. Berger, A. N., & Udell, G. F. (1995). “Relationship lending and lines of
   credit in small firm finance.” *Journal of Business*, 68(3), 351–381.
   [Open record](https://scholarcommons.sc.edu/fin_facpub/10/).
9. Yannelis, C., & Zhang, A. L. (2023). “Competition and selection in credit
   markets.” *Journal of Financial Economics*, 150(2). Useful corrective to
   simplistic ‘more competition means lower rates’ language.
   [NBER version](https://doi.org/10.3386/w29169).
10. Aiyar, S., Calomiris, C. W., & Wieladek, T. (2014). “Does macro-prudential
    regulation leak? Evidence from a UK policy experiment.” *Journal of Money,
    Credit and Banking*, 46(s1), 181–214. For capital-rule/lending context.
    [Working-paper summary](https://www.bankofengland.co.uk/working-paper/2014/how-does-credit-supply-respond-to-monetary-policy-and-bank-minimum-capital-requirements).
11. Vo, Q.-A. (2021). “Interactions of capital and liquidity requirements: A
    review of the literature.” Bank of England Staff Working Paper 916.
    [Official source](https://www.bankofengland.co.uk/working-paper/2021/interactions-of-capital-and-liquidity-requirements-a-review-of-the-literature).
12. Tucker, P. (2014). “The lender of last resort and modern central banking:
    principles and reconstruction.” BIS Papers 79. Cite for the conceptual
    liquidity/solvency distinction—not as a direct validation of the model’s
    facility rule. [BIS](https://www.bis.org/publ/bppdf/bispap79b_rh.pdf).

### Agent-based macro-finance and closest computational comparators

13. Ashraf, Q., Gershman, B., & Howitt, P. (2017). “Banks, market organization,
    and macroeconomic performance: An agent-based computational analysis.”
    *Journal of Economic Behavior & Organization*, 135, 143–180.
    [NBER version](https://www.nber.org/papers/w17102).
14. Cincotti, S., Raberto, M., & Teglio, A. (2010). “Credit money and
    macroeconomic instability in the agent-based model and simulator Eurace.”
    *Economics: The Open-Access, Open-Assessment E-Journal*, 4.
    [Open record](https://doi.org/10.5018/economics-ejournal.ja.2010-26).
15. Zhang, Y., Xiong, X., Zhang, W., & Liu, X. (2018). “Credit rationing and
    the simulation of multi-bank credit market model: A computational economics
    approach.” *Computational Economics*, 52, 1233–1256.
    [DOI](https://doi.org/10.1007/s10614-017-9726-0).
16. Neuner, A., et al. (2025). “Agent-based modeling of long-term bank credit:
    buffer policies vs. selective lending in stochastic growth and decline.”
    *Journal of Economic Interaction and Coordination*. [DOI](https://doi.org/10.1007/s11403-025-00454-2).
17. Dosi, G., & Roventini, A. (2017). “Macroeconomic policy in DSGE and
    agent-based models redux: New developments and challenges ahead.” *Journal
    of Artificial Societies and Social Simulation*, 20(1), 1.
    [Open paper](https://jasss.soc.surrey.ac.uk/20/1/1.html).
18. Hendry, C., et al. (2025). “Agent-based modeling at central banks: Recent
    developments and new challenges.” Bank of England Staff Working Paper.
    [Official PDF](https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/agent-based-modeling-at-central-banks-recent-developments-and-new-challenges.pdf).

### Calibration, validation, reproducibility, and LLM boundary

19. Windrum, P., Fagiolo, G., & Moneta, A. (2007). “Empirical validation of
    agent-based models: Alternatives and prospects.” *JASSS*, 10(2), 8.
    [Open paper](https://jasss.soc.surrey.ac.uk/10/2/8.html).
20. Grimm, V., et al. (2020). “The ODD protocol for describing agent-based and
    other simulation models: A second update to improve clarity, replication,
    and structural realism.” *JASSS*, 23(2), 7.
    [DOI](https://doi.org/10.18564/jasss.4259).
21. Li, Y., et al. (2024). “STEER: Assessing the economic rationality of large
    language models.” arXiv:2402.09552. This motivates evaluation, but does not
    validate DeepSeek behavior as human behavior. [arXiv](https://arxiv.org/abs/2402.09552).
22. Gao, J., et al. (2025). “When experimental economics meets large language
    models: Tactics with evidence.” arXiv:2505.21371. Use in the LLM methods
    appendix for controls and failure reporting. [arXiv](https://arxiv.org/abs/2505.21371).

## 5. Official empirical-source citations and construction controls

| Repository input | What it can support | Non-negotiable caveat |
| --- | --- | --- |
| [FDIC BankFind Suite](https://banks.data.fdic.gov/bankfind-suite/bulkData) | Quarterly insured-bank Call Report balance-sheet and income inputs. | The manuscript must retain field definitions, vintages, filters, bank universe, and hashes; a bulk download is a source, not a causal design. |
| [FR 2028D / SSBFL](https://www.federalreserve.gov/apps/reportingforms/Report/Index/FR_2028D) | Small-business loan terms/amounts/rates and survey series used in calibration. | Explain aggregation and weights; do not represent survey aggregates as loan-level microdata. |
| [FRED CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) | Deflation to the stated price basis. | State quarter aggregation and the target-quarter index. |
| [FRED DPRIME](https://fred.stlouisfed.org/series/DPRIME) and [DFF](https://fred.stlouisfed.org/series/DFF) | Prime-policy spread and administered benchmark construction. | These are different rates with different economic roles; never call either *the* market rate. |
| [H.8](https://www.federalreserve.gov/releases/H8/about.htm) | Aggregate banking-sector cross-checks. | H.8 is an estimated weekly aggregate, not a substitute for bank-level FDIC calibration. |

## 6. Section-by-section writing map

1. **Introduction.** Start with the institutional decomposition. Cite McLeay et
   al. and BIS only for the descriptive monetary architecture. Then say the
   paper changes a pricing rule inside a model—not the actual institutional
   status of the dollar system. End with the model-specific H2/H3/H7 results.
2. **Related literature.** Use three compact streams: (i) credit
   rationing/relationships (Stiglitz–Weiss; Berger–Udell; Yannelis–Zhang), (ii)
   credit channels, capital, and liquidity (Kashyap–Stein; Bernanke–Gertler;
   Vo; Tucker), and (iii) ABM credit economies (Ashraf et al.; Eurace; Zhang et
   al.; Neuner et al.). State the delta precisely: pricing pass-through is
   isolated while money and settlement remain centralized.
3. **Model.** Use primary equations and full timing. Cite sources only when a
   design choice is borrowed; do not cite a paper as if it proves a simulated
   identity. Include all balance-sheet entries and clarify that reserve need
   arises at settlement, not mechanically before a loan can originate.
4. **Data and calibration.** Cite all five official data pages in the table
   above. Identify which parameters are fitted, normalized, and
   literature-motivated. Include the documented 2025 validation limitation.
5. **Experiment and inference.** Treat the independent matched seed as the
   sampling unit. Cite ODD/Windrum et al. for reporting/validation norms, but
   describe the project’s actual frozen protocol rather than claiming a generic
   standard guarantees validity.
6. **Results/discussion.** Lead with the allocation-versus-rationing trade-off.
   Use the credit-rationing literature to explain why higher selection is not a
   welfare conclusion. Use capital/liquidity literature only as external
   motivation for the H7 boundary condition.
7. **LLM subsection.** Keep it short, after core results. Cite STEER and Gao et
   al. for the measurement problem; report model, prompt, output schema,
   temperature, invalid-call rule, and complete audit.

## 7. Remaining research work before submission

- Build a final `.bib` from the publisher/DOI records above and check author,
  year, issue, page, and DOI metadata one by one.
- Add a data-vintage table with retrieval date, exact FDIC release/quarter,
  SSBFL release, FRED transformation, SHA-256, and repository path.
- Cite a genuine production-function / investment source only if the manuscript
  claims those coefficients are empirically grounded; otherwise call them
  normalized or literature-motivated and report sensitivity.
- Obtain an untouched later vintage before asserting strong out-of-sample
  validation, consistent with `docs/calibration_chronology_v0.3.md`.
- Replace the LLM citations with peer-reviewed sources if the target journal
  requires that; the current papers are methods context, not validation.
