# Computational evidence summary

## Run integrity

- Total registered runs: 480
- completed: 480

## H2: local-information sensitivity

- Market-minus-administered slope for `borrower_leverage`: 0.0118 (95% CI 0.0117, 0.0120; n=30).
- Market-minus-administered slope for `borrower_risk`: 0.0030 (95% CI 0.0029, 0.0031; n=30).
- Market-minus-administered slope for `reserve_buffer`: -0.0014 (95% CI -0.0018, -0.0011; n=30).
- Market-minus-administered slope for `capital_buffer`: -0.0044 (95% CI -0.0048, -0.0041; n=30).
- Market-minus-administered slope for `expected_inflation`: 0.9785 (95% CI 0.9691, 0.9879; n=30).

## H3: demand-shock response

- administered `new_credit` demand_shock_minus_baseline: 31.4774 (95% CI 27.8932, 35.0616; n=30).
- administered `output` demand_shock_minus_baseline: 54.4410 (95% CI 53.9378, 54.9442; n=30).
- administered `mean_inflation` demand_shock_minus_baseline: 0.0001 (95% CI 0.0001, 0.0001; n=30).
- market `new_credit` demand_shock_minus_baseline: -38.0879 (95% CI -62.6392, -13.5366; n=30).
- market `output` demand_shock_minus_baseline: 18.1417 (95% CI 5.9776, 30.3059; n=30).
- market `mean_inflation` demand_shock_minus_baseline: 0.0008 (95% CI 0.0006, 0.0010; n=30).
- market_minus_administered `new_credit` difference_in_differences: -69.5653 (95% CI -94.8214, -44.3092; n=30).
- market_minus_administered `output` difference_in_differences: -36.2992 (95% CI -48.0976, -24.5008; n=30).
- market_minus_administered `mean_inflation` difference_in_differences: 0.0007 (95% CI 0.0004, 0.0009; n=30).

## H7: institutional dependence

- h7_abundant_unavailable (market_minus_administered) `new_credit`: -66.7516 (95% CI -115.5796, -17.9236; n=30).
- h7_abundant_unavailable (market_minus_administered) `emergency_borrowing`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- h7_abundant_unavailable (market_minus_administered) `liquidity_shortfall`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_administered) `new_credit`: 1243.3587 (95% CI 1233.6747, 1253.0428; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_administered) `emergency_borrowing`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_administered) `liquidity_shortfall`: -1408.1998 (95% CI -1485.8010, -1330.5985; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_market) `new_credit`: 1176.6071 (95% CI 1126.4792, 1226.7351; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_market) `emergency_borrowing`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_market) `liquidity_shortfall`: -1408.1998 (95% CI -1485.8010, -1330.5985; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_administered) `new_credit`: 576.1015 (95% CI 574.0153, 578.1877; n=40).
- scarce_penalty_minus_unavailable (institutional_contrast_administered) `emergency_borrowing`: 1229.3858 (95% CI 1185.4345, 1273.3370; n=40).
- scarce_penalty_minus_unavailable (institutional_contrast_administered) `liquidity_shortfall`: -1395.3789 (95% CI -1461.2654, -1329.4924; n=40).
- scarce_penalty_minus_unavailable (institutional_contrast_market) `new_credit`: 63.6311 (95% CI 45.4118, 81.8504; n=40).
- scarce_penalty_minus_unavailable (institutional_contrast_market) `emergency_borrowing`: 1438.5100 (95% CI 1276.4015, 1600.6184; n=40).
- scarce_penalty_minus_unavailable (institutional_contrast_market) `liquidity_shortfall`: -1395.3789 (95% CI -1461.2654, -1329.4924; n=40).
- scarce_limited_minus_unavailable (institutional_contrast_administered) `new_credit`: 30.0000 (95% CI 30.0000, 30.0000; n=40).
- scarce_limited_minus_unavailable (institutional_contrast_administered) `emergency_borrowing`: 546.4545 (95% CI 538.8024, 554.1065; n=40).
- scarce_limited_minus_unavailable (institutional_contrast_administered) `liquidity_shortfall`: -723.7340 (95% CI -735.2300, -712.2380; n=40).
- scarce_limited_minus_unavailable (institutional_contrast_market) `new_credit`: 30.0000 (95% CI 30.0000, 30.0000; n=40).
- scarce_limited_minus_unavailable (institutional_contrast_market) `emergency_borrowing`: 436.0267 (95% CI 425.4841, 446.5694; n=40).
- scarce_limited_minus_unavailable (institutional_contrast_market) `liquidity_shortfall`: -162.8500 (95% CI -200.8399, -124.8601; n=40).
- scarce_penalty_minus_limited (institutional_contrast_administered) `new_credit`: 546.1015 (95% CI 544.0153, 548.1877; n=40).
- scarce_penalty_minus_limited (institutional_contrast_administered) `emergency_borrowing`: 682.9313 (95% CI 645.2087, 720.6539; n=40).
- scarce_penalty_minus_limited (institutional_contrast_administered) `liquidity_shortfall`: -671.6449 (95% CI -728.9500, -614.3397; n=40).
- scarce_penalty_minus_limited (institutional_contrast_market) `new_credit`: 33.6311 (95% CI 15.4118, 51.8504; n=40).
- scarce_penalty_minus_limited (institutional_contrast_market) `emergency_borrowing`: 1002.4832 (95% CI 843.0515, 1161.9149; n=40).
- scarce_penalty_minus_limited (institutional_contrast_market) `liquidity_shortfall`: -1232.5288 (95% CI -1330.9006, -1134.1571; n=40).

## Interpretation boundary

These are computational treatment effects inside the specified agent-based model. They are not estimates of causal effects in the United States economy. Rule-based powered results establish the institutional mechanisms; DeepSeek R1 8B runs are reported as a separate behavioral robustness layer.
