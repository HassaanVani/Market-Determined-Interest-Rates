# Computational evidence summary

## Run integrity

- Total registered runs: 420
- completed: 420

## H2: local-information sensitivity

- Market-minus-administered slope for `borrower_leverage`: 0.0119 (95% CI 0.0116, 0.0121; n=30).
- Market-minus-administered slope for `borrower_risk`: 0.0031 (95% CI 0.0030, 0.0032; n=30).
- Market-minus-administered slope for `reserve_buffer`: -0.0010 (95% CI -0.0011, -0.0009; n=30).
- Market-minus-administered slope for `expected_inflation`: 0.9696 (95% CI 0.9585, 0.9806; n=30).

## H3: demand-shock response

- administered `new_credit` demand_shock_minus_baseline: 35.8700 (95% CI 35.8700, 35.8700; n=30).
- administered `output` demand_shock_minus_baseline: 26.8235 (95% CI 26.5810, 27.0660; n=30).
- administered `mean_inflation` demand_shock_minus_baseline: -0.0007 (95% CI -0.0007, -0.0007; n=30).
- market `new_credit` demand_shock_minus_baseline: -68.6085 (95% CI -91.3974, -45.8196; n=30).
- market `output` demand_shock_minus_baseline: 26.8235 (95% CI 26.5810, 27.0660; n=30).
- market `mean_inflation` demand_shock_minus_baseline: -0.0007 (95% CI -0.0007, -0.0007; n=30).
- market_minus_administered `new_credit` difference_in_differences: -104.4785 (95% CI -127.2674, -81.6896; n=30).
- market_minus_administered `output` difference_in_differences: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- market_minus_administered `mean_inflation` difference_in_differences: 0.0000 (95% CI 0.0000, 0.0000; n=30).

## H7: institutional dependence

- h7_abundant_unavailable (market_minus_administered) `new_credit`: -382.5330 (95% CI -427.3410, -337.7250; n=30).
- h7_abundant_unavailable (market_minus_administered) `emergency_borrowing`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- h7_abundant_unavailable (market_minus_administered) `liquidity_shortfall`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_administered) `new_credit`: 1578.5904 (95% CI 1578.5904, 1578.5904; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_administered) `emergency_borrowing`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_administered) `liquidity_shortfall`: -1408.1998 (95% CI -1485.8010, -1330.5985; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_market) `new_credit`: 1196.0575 (95% CI 1151.2495, 1240.8655; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_market) `emergency_borrowing`: 0.0000 (95% CI 0.0000, 0.0000; n=30).
- abundant_minus_scarce_unavailable (institutional_contrast_market) `liquidity_shortfall`: -1408.1998 (95% CI -1485.8010, -1330.5985; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_administered) `new_credit`: 355.5385 (95% CI 355.5385, 355.5385; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_administered) `emergency_borrowing`: 1136.3517 (95% CI 1084.8740, 1187.8294; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_administered) `liquidity_shortfall`: -1408.1998 (95% CI -1485.8010, -1330.5985; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_market) `new_credit`: 303.1815 (95% CI 285.3769, 320.9861; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_market) `emergency_borrowing`: 1435.7476 (95% CI 1334.6855, 1536.8097; n=30).
- scarce_penalty_minus_unavailable (institutional_contrast_market) `liquidity_shortfall`: -1408.1998 (95% CI -1485.8010, -1330.5985; n=30).
- scarce_limited_minus_unavailable (institutional_contrast_administered) `new_credit`: 30.0000 (95% CI 30.0000, 30.0000; n=30).
- scarce_limited_minus_unavailable (institutional_contrast_administered) `emergency_borrowing`: 533.3682 (95% CI 528.3538, 538.3826; n=30).
- scarce_limited_minus_unavailable (institutional_contrast_administered) `liquidity_shortfall`: -709.7203 (95% CI -716.0888, -703.3518; n=30).
- scarce_limited_minus_unavailable (institutional_contrast_market) `new_credit`: 30.0000 (95% CI 30.0000, 30.0000; n=30).
- scarce_limited_minus_unavailable (institutional_contrast_market) `emergency_borrowing`: 412.0928 (95% CI 405.9637, 418.2219; n=30).
- scarce_limited_minus_unavailable (institutional_contrast_market) `liquidity_shortfall`: -124.8414 (95% CI -171.1868, -78.4961; n=30).
- scarce_penalty_minus_limited (institutional_contrast_administered) `new_credit`: 325.5385 (95% CI 325.5385, 325.5385; n=30).
- scarce_penalty_minus_limited (institutional_contrast_administered) `emergency_borrowing`: 602.9835 (95% CI 556.2462, 649.7208; n=30).
- scarce_penalty_minus_limited (institutional_contrast_administered) `liquidity_shortfall`: -698.4794 (95% CI -770.1681, -626.7907; n=30).
- scarce_penalty_minus_limited (institutional_contrast_market) `new_credit`: 273.1815 (95% CI 255.3769, 290.9861; n=30).
- scarce_penalty_minus_limited (institutional_contrast_market) `emergency_borrowing`: 1023.6548 (95% CI 918.2853, 1129.0244; n=30).
- scarce_penalty_minus_limited (institutional_contrast_market) `liquidity_shortfall`: -1283.3583 (95% CI -1403.3869, -1163.3298; n=30).

## Interpretation boundary

These are computational treatment effects inside the specified agent-based model. They are not estimates of causal effects in the United States economy. Rule-based powered results establish the institutional mechanisms; DeepSeek R1 8B runs are reported as a separate behavioral robustness layer.
