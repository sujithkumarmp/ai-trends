# Unit Test Results

**Status:** ✅ PASSED  
**Generated:** 2026-08-26 03:28:44 UTC  
**Duration:** 0.49s

| Total | Passed | Failed | Errors | Skipped |
| ----: | -----: | -----: | -----: | ------: |
| 79 | 79 | 0 | 0 | 0 |

## Tests

| Result | Test | Time |
| ------ | ---- | ---: |
| ✅ | `tests.test_langgraph_triage.NormalizeCategoryTests.test_empty_output_falls_back` | 0.001s |
| ✅ | `tests.test_langgraph_triage.NormalizeCategoryTests.test_exact_label_passes_through` | 0.000s |
| ✅ | `tests.test_langgraph_triage.NormalizeCategoryTests.test_matching_is_case_insensitive_and_ignores_surrounding_prose` | 0.000s |
| ✅ | `tests.test_langgraph_triage.NormalizeCategoryTests.test_unknown_label_falls_back` | 0.000s |
| ✅ | `tests.test_langgraph_triage.NormalizeCategoryTests.test_whitespace_is_stripped` | 0.000s |
| ✅ | `tests.test_langgraph_triage.IsApprovedTests.test_a_critique_does_not_approve` | 0.000s |
| ✅ | `tests.test_langgraph_triage.IsApprovedTests.test_bare_token_approves` | 0.000s |
| ✅ | `tests.test_langgraph_triage.IsApprovedTests.test_token_is_matched_case_insensitively_with_padding` | 0.000s |
| ✅ | `tests.test_langgraph_triage.IsApprovedTests.test_token_must_lead_the_verdict` | 0.000s |
| ✅ | `tests.test_langgraph_triage.ClassifyNodeTests.test_normalizes_a_chatty_answer` | 0.002s |
| ✅ | `tests.test_langgraph_triage.ClassifyNodeTests.test_passes_the_ticket_text_to_the_chain` | 0.001s |
| ✅ | `tests.test_langgraph_triage.ClassifyNodeTests.test_returns_only_the_keys_it_owns` | 0.001s |
| ✅ | `tests.test_langgraph_triage.DraftNodeTests.test_forwards_category_and_critique_to_the_chain` | 0.001s |
| ✅ | `tests.test_langgraph_triage.DraftNodeTests.test_records_the_draft_and_spends_a_revision` | 0.001s |
| ✅ | `tests.test_langgraph_triage.DraftNodeTests.test_revision_counter_builds_on_the_current_state` | 0.001s |
| ✅ | `tests.test_langgraph_triage.ReviewNodeTests.test_approval_clears_the_critique` | 0.001s |
| ✅ | `tests.test_langgraph_triage.ReviewNodeTests.test_passes_the_ticket_and_current_draft_to_the_chain` | 0.001s |
| ✅ | `tests.test_langgraph_triage.ReviewNodeTests.test_rejection_stores_the_critique` | 0.001s |
| ✅ | `tests.test_langgraph_triage.TerminalNodeTests.test_escalate_hands_over` | 0.000s |
| ✅ | `tests.test_langgraph_triage.TerminalNodeTests.test_finalize_resolves` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterClassificationTests.test_billing_gets_a_draft` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterClassificationTests.test_fallback_category_still_gets_a_draft` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterClassificationTests.test_outage_skips_drafting` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterReviewTests.test_a_zero_budget_escalates_immediately` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterReviewTests.test_approval_wins_over_an_exhausted_budget` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterReviewTests.test_approved_draft_is_finalized` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterReviewTests.test_budget_exhausted_escalates` | 0.000s |
| ✅ | `tests.test_langgraph_triage.RouteAfterReviewTests.test_rejected_draft_within_budget_loops_back` | 0.000s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_a_larger_budget_allows_more_passes_before_escalating` | 0.011s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_first_draft_approved_runs_straight_through` | 0.006s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_graph_runs_against_fake_chat_models` | 0.010s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_loop_terminates_and_escalates_when_the_budget_runs_out` | 0.007s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_outage_escalates_without_drafting` | 0.006s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_rejected_draft_loops_back_and_carries_the_critique` | 0.008s |
| ✅ | `tests.test_langgraph_triage.GraphTests.test_the_critique_reaches_the_next_draft` | 0.008s |
| ✅ | `tests.test_langgraph_triage.PromptTests.test_classifier_prompt_lists_every_allowed_category` | 0.001s |
| ✅ | `tests.test_langgraph_triage.PromptTests.test_drafter_prompt_carries_the_critique` | 0.001s |
| ✅ | `tests.test_langgraph_triage.PromptTests.test_reviewer_prompt_names_the_approval_token` | 0.001s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_atr_uses_the_full_high_low_range_when_available` | 0.001s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_bollinger_bands_bracket_the_middle` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_ema_of_a_constant_series_is_that_constant` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_ema_tracks_a_rising_series_below_the_last_price` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_indicators_reject_series_that_are_too_short` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_macd_histogram_is_the_line_minus_the_signal` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_macd_is_positive_in_an_uptrend` | 0.000s |
| ✅ | `tests.test_option_analyzer.IndicatorTests.test_realized_vol_is_higher_for_a_noisier_series` | 0.000s |
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
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_short_history_still_analyzes_but_flags_the_gap` | 0.001s |
| ✅ | `tests.test_option_analyzer.AnalyzerTests.test_uptrend_produces_a_bullish_directional_plan` | 0.001s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_a_non_positive_expiry` | 0.001s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_a_non_positive_implied_vol` | 0.001s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_a_non_positive_size` | 0.000s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_misaligned_highs_or_lows` | 0.001s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_non_positive_prices` | 0.000s |
| ✅ | `tests.test_option_analyzer.ValidationTests.test_rejects_too_little_history` | 0.001s |
