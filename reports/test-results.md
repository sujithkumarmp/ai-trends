# Unit Test Results

**Status:** ✅ PASSED  
**Generated:** 2026-08-26 03:14:48 UTC  
**Duration:** 0.06s

| Total | Passed | Failed | Errors | Skipped |
| ----: | -----: | -----: | -----: | ------: |
| 41 | 41 | 0 | 0 | 0 |

## Tests

| Result | Test | Time |
| ------ | ---- | ---: |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_atr_uses_the_full_high_low_range_when_available` | 0.001s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_bollinger_bands_bracket_the_middle` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_ema_of_a_constant_series_is_that_constant` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_ema_tracks_a_rising_series_below_the_last_price` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_indicators_reject_series_that_are_too_short` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_macd_histogram_is_the_line_minus_the_signal` | 0.001s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_macd_is_positive_in_an_uptrend` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_realized_vol_is_higher_for_a_noisier_series` | 0.001s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_rsi_is_0_when_every_bar_loses` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_rsi_is_100_when_every_bar_gains` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_rsi_of_an_uptrend_is_above_that_of_a_downtrend` | 0.001s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_sma_is_the_mean_of_the_window` | 0.000s |
| ✅ | `tests.test_option_analyzer.BlackScholesTests.test_at_expiry_the_price_is_intrinsic` | 0.000s |
| ✅ | `tests.test_option_analyzer.BlackScholesTests.test_deltas_have_the_right_sign_and_range` | 0.000s |
| ✅ | `tests.test_option_analyzer.BlackScholesTests.test_higher_vol_is_worth_more` | 0.000s |
| ✅ | `tests.test_option_analyzer.BlackScholesTests.test_long_options_lose_value_to_time` | 0.000s |
| ✅ | `tests.test_option_analyzer.BlackScholesTests.test_put_call_parity_holds` | 0.000s |
| ✅ | `tests.test_option_analyzer.BlackScholesTests.test_rejects_a_bad_right` | 0.000s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_a_wider_expiry_widens_the_expected_move` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_cheap_premium_into_earnings_buys_a_straddle` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_confidence_is_a_probability` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_contracts_scale_the_money_fields_linearly` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_credit_spread_risk_and_reward_add_up_to_the_spread_width` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_debit_spread_risk_and_reward_add_up_to_the_spread_width` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_downtrend_produces_a_bearish_directional_plan` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_earnings_inside_the_expiry_is_flagged_as_a_risk` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_implied_vol_is_inferred_and_flagged_when_omitted` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_iv_rank_is_derived_from_the_supplied_history` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_probability_of_profit_stays_between_0_and_1` | 0.002s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_range_bound_stock_with_no_catalyst_stands_aside` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_range_bound_stock_with_rich_premium_sells_an_iron_condor` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_report_mentions_the_ticker_and_the_strategy` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_report_renders_for_a_no_trade_verdict` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_short_history_still_analyzes_but_flags_the_gap` | 0.000s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_uptrend_produces_a_bullish_directional_plan` | 0.001s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_a_non_positive_expiry` | 0.000s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_a_non_positive_implied_vol` | 0.000s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_a_non_positive_size` | 0.001s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_misaligned_highs_or_lows` | 0.000s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_non_positive_prices` | 0.000s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_too_little_history` | 0.000s |
