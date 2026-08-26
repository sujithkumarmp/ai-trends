"""Tests for :mod:`option_analyzer`."""

from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from option_analyzer import (  # noqa: E402
    analyze_option_opportunity,
    atr,
    black_scholes,
    bollinger,
    ema,
    format_report,
    macd,
    realized_volatility,
    rsi,
    sma,
)


def trending(days: int = 120, start: float = 100.0, daily: float = 0.004):
    """A clean trend: ``daily`` compounded, with a small alternating wobble."""
    closes = []
    price = start
    for i in range(days):
        price *= 1 + daily
        closes.append(round(price * (1 + (0.002 if i % 2 else -0.002)), 4))
    return closes


def choppy(days: int = 120, start: float = 100.0, amplitude: float = 0.03):
    """Range-bound: a 7-day sine wave around ``start`` with no net drift.

    The period divides both the 21-day momentum lookback and the sample
    length, so the series ends flat on every horizon the analyzer measures.
    """
    return [
        round(start * (1 + amplitude * math.sin(i * 2 * math.pi / 7)), 4)
        for i in range(days)
    ]


class IndicatorTests(unittest.TestCase):
    def test_sma_is_the_mean_of_the_window(self):
        self.assertAlmostEqual(sma([1, 2, 3, 4, 5], 3), 4.0)

    def test_ema_of_a_constant_series_is_that_constant(self):
        self.assertAlmostEqual(ema([7.0] * 30, 9), 7.0)

    def test_ema_tracks_a_rising_series_below_the_last_price(self):
        closes = trending()
        self.assertLess(ema(closes, 21), closes[-1])
        self.assertGreater(ema(closes, 9), ema(closes, 21))

    def test_rsi_is_100_when_every_bar_gains(self):
        self.assertAlmostEqual(rsi([100 + i for i in range(30)]), 100.0)

    def test_rsi_is_0_when_every_bar_loses(self):
        self.assertAlmostEqual(rsi([100 - i for i in range(30)]), 0.0)

    def test_rsi_of_an_uptrend_is_above_that_of_a_downtrend(self):
        up = rsi(trending(daily=0.004))
        down = rsi(trending(daily=-0.004))
        self.assertGreater(up, 50)
        self.assertLess(down, 50)
        self.assertGreater(up, down)

    def test_macd_histogram_is_the_line_minus_the_signal(self):
        line, signal, histogram = macd(trending())
        self.assertAlmostEqual(histogram, line - signal)

    def test_macd_is_positive_in_an_uptrend(self):
        line, _, _ = macd(trending(daily=0.004))
        self.assertGreater(line, 0)

    def test_bollinger_bands_bracket_the_middle(self):
        low, mid, high = bollinger(trending())
        self.assertLess(low, mid)
        self.assertLess(mid, high)
        self.assertAlmostEqual(high - mid, mid - low)

    def test_atr_uses_the_full_high_low_range_when_available(self):
        closes = trending(60)
        highs = [c * 1.02 for c in closes]
        lows = [c * 0.98 for c in closes]
        self.assertGreater(atr(closes, highs, lows), atr(closes))

    def test_realized_vol_is_higher_for_a_noisier_series(self):
        calm = trending(60, daily=0.001)
        wild = [c * (1 + 0.05 * (-1) ** i) for i, c in enumerate(calm)]
        self.assertGreater(realized_volatility(wild), realized_volatility(calm))

    def test_indicators_reject_series_that_are_too_short(self):
        with self.assertRaises(ValueError):
            sma([1, 2], 5)
        with self.assertRaises(ValueError):
            rsi([1, 2, 3])


class BlackScholesTests(unittest.TestCase):
    def test_put_call_parity_holds(self):
        spot, strike, days, vol, rate = 100.0, 105.0, 45, 0.30, 0.04
        call = black_scholes(spot, strike, days, vol, rate, "CALL")
        put = black_scholes(spot, strike, days, vol, rate, "PUT")
        discounted = strike * math.exp(-rate * days / 365.0)
        self.assertAlmostEqual(call.price - put.price, spot - discounted, places=8)

    def test_deltas_have_the_right_sign_and_range(self):
        call = black_scholes(100, 100, 30, 0.3)
        put = black_scholes(100, 100, 30, 0.3, right="PUT")
        self.assertTrue(0 < call.delta < 1)
        self.assertTrue(-1 < put.delta < 0)
        self.assertAlmostEqual(call.delta - put.delta, 1.0, places=8)

    def test_long_options_lose_value_to_time(self):
        self.assertLess(black_scholes(100, 100, 30, 0.3).theta, 0)
        self.assertLess(black_scholes(100, 100, 30, 0.3, right="PUT").theta, 0)

    def test_higher_vol_is_worth_more(self):
        cheap = black_scholes(100, 100, 30, 0.20).price
        rich = black_scholes(100, 100, 30, 0.60).price
        self.assertGreater(rich, cheap)

    def test_at_expiry_the_price_is_intrinsic(self):
        self.assertAlmostEqual(black_scholes(110, 100, 0, 0.3).price, 10.0)
        self.assertAlmostEqual(black_scholes(90, 100, 0, 0.3).price, 0.0)

    def test_rejects_a_bad_right(self):
        with self.assertRaises(ValueError):
            black_scholes(100, 100, 30, 0.3, right="STRADDLE")


class AnalyzerTests(unittest.TestCase):
    def test_uptrend_produces_a_bullish_directional_plan(self):
        result = analyze_option_opportunity(
            "UP", trending(daily=0.005), implied_vol=0.30
        )
        self.assertEqual(result.trend, "BULLISH")
        self.assertGreater(result.directional_score, 0.25)
        self.assertEqual(result.plan.direction, "BULLISH")
        self.assertIn(
            result.plan.strategy,
            {"Long Call", "Bull Call Spread", "Bull Put Spread"},
        )

    def test_downtrend_produces_a_bearish_directional_plan(self):
        result = analyze_option_opportunity(
            "DOWN", trending(daily=-0.005), implied_vol=0.30
        )
        self.assertEqual(result.trend, "BEARISH")
        self.assertLess(result.directional_score, -0.25)
        self.assertEqual(result.plan.direction, "BEARISH")
        self.assertIn(
            result.plan.strategy,
            {"Long Put", "Bear Put Spread", "Bear Call Spread"},
        )

    def test_range_bound_stock_with_rich_premium_sells_an_iron_condor(self):
        result = analyze_option_opportunity(
            "FLAT",
            choppy(),
            implied_vol=0.60,
            iv_history=[0.20, 0.30, 0.40, 0.55, 0.62],
        )
        self.assertEqual(result.trend, "NEUTRAL")
        self.assertEqual(result.volatility_regime, "RICH")
        self.assertEqual(result.plan.strategy, "Iron Condor")
        self.assertEqual(len(result.plan.legs), 4)
        self.assertEqual(len(result.plan.breakevens), 2)

    def test_range_bound_stock_with_no_catalyst_stands_aside(self):
        result = analyze_option_opportunity("FLAT", choppy(), implied_vol=0.20)
        self.assertEqual(result.trend, "NEUTRAL")
        self.assertEqual(result.plan.strategy, "No Trade")
        self.assertFalse(result.actionable)
        self.assertEqual(result.plan.legs, ())

    def test_cheap_premium_into_earnings_buys_a_straddle(self):
        result = analyze_option_opportunity(
            "EVENT",
            choppy(),
            implied_vol=0.20,
            days_to_expiry=30,
            earnings_in_days=10,
        )
        self.assertEqual(result.plan.strategy, "Long Straddle")
        self.assertEqual(len(result.plan.legs), 2)
        self.assertIsNone(result.plan.max_profit)

    def test_credit_spread_risk_and_reward_add_up_to_the_spread_width(self):
        result = analyze_option_opportunity(
            "UP",
            trending(daily=0.005),
            implied_vol=0.55,
            iv_history=[0.20, 0.35, 0.50, 0.58],
        )
        plan = result.plan
        self.assertEqual(plan.flow, "credit")
        self.assertLess(plan.net_premium, 0)
        short_leg, long_leg = plan.legs
        width = abs(short_leg.strike - long_leg.strike) * 100
        self.assertAlmostEqual(plan.max_profit + plan.max_loss, width, places=6)
        self.assertAlmostEqual(plan.max_profit, -plan.net_premium, places=6)

    def test_debit_spread_risk_and_reward_add_up_to_the_spread_width(self):
        result = analyze_option_opportunity(
            "UP",
            trending(daily=0.005),
            implied_vol=0.30,
            iv_history=[0.20, 0.28, 0.32, 0.45],
        )
        plan = result.plan
        self.assertEqual(plan.strategy, "Bull Call Spread")
        self.assertEqual(plan.flow, "debit")
        long_leg, short_leg = plan.legs
        width = abs(short_leg.strike - long_leg.strike) * 100
        self.assertAlmostEqual(plan.max_profit + plan.max_loss, width, places=6)

    def test_contracts_scale_the_money_fields_linearly(self):
        kwargs = dict(implied_vol=0.55, iv_history=[0.2, 0.35, 0.5, 0.58])
        one = analyze_option_opportunity("UP", trending(daily=0.005), **kwargs)
        five = analyze_option_opportunity(
            "UP", trending(daily=0.005), contracts=5, **kwargs
        )
        self.assertAlmostEqual(five.plan.max_loss, one.plan.max_loss * 5, places=6)
        self.assertAlmostEqual(
            five.plan.net_premium, one.plan.net_premium * 5, places=6
        )
        self.assertEqual(five.plan.breakevens, one.plan.breakevens)

    def test_probability_of_profit_stays_between_0_and_1(self):
        for closes, iv in (
            (trending(daily=0.005), 0.30),
            (trending(daily=-0.005), 0.30),
            (trending(daily=0.005), 0.70),
            (choppy(), 0.60),
        ):
            with self.subTest(iv=iv):
                result = analyze_option_opportunity("X", closes, implied_vol=iv)
                self.assertGreaterEqual(result.plan.probability_of_profit, 0.0)
                self.assertLessEqual(result.plan.probability_of_profit, 1.0)

    def test_a_wider_expiry_widens_the_expected_move(self):
        closes = trending()
        near = analyze_option_opportunity(
            "X", closes, implied_vol=0.4, days_to_expiry=7
        )
        far = analyze_option_opportunity(
            "X", closes, implied_vol=0.4, days_to_expiry=60
        )
        self.assertLess(near.expected_move, far.expected_move)

    def test_iv_rank_is_derived_from_the_supplied_history(self):
        result = analyze_option_opportunity(
            "X", trending(), implied_vol=0.50, iv_history=[0.30, 0.40, 0.50]
        )
        self.assertAlmostEqual(result.iv_rank, 100.0)
        self.assertEqual(result.volatility_regime, "RICH")

    def test_implied_vol_is_inferred_and_flagged_when_omitted(self):
        result = analyze_option_opportunity("X", trending())
        self.assertGreater(result.implied_vol, 0)
        self.assertTrue(any("inferred" in risk for risk in result.risks))

    def test_earnings_inside_the_expiry_is_flagged_as_a_risk(self):
        result = analyze_option_opportunity(
            "UP",
            trending(daily=0.005),
            implied_vol=0.30,
            days_to_expiry=30,
            earnings_in_days=5,
        )
        self.assertTrue(any("earnings" in risk.lower() for risk in result.risks))

    def test_short_history_still_analyzes_but_flags_the_gap(self):
        result = analyze_option_opportunity(
            "X", trending(days=32), implied_vol=0.30
        )
        self.assertTrue(any("history" in risk for risk in result.risks))
        self.assertLessEqual(result.confidence, 0.9)

    def test_confidence_is_a_probability(self):
        result = analyze_option_opportunity(
            "UP", trending(daily=0.005), implied_vol=0.30
        )
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_report_mentions_the_ticker_and_the_strategy(self):
        result = analyze_option_opportunity(
            "NVDA", trending(daily=0.005), implied_vol=0.30
        )
        report = format_report(result)
        self.assertIn("NVDA", report)
        self.assertIn(result.plan.strategy, report)
        self.assertIn("not financial advice", report)

    def test_report_renders_for_a_no_trade_verdict(self):
        result = analyze_option_opportunity("FLAT", choppy(), implied_vol=0.20)
        self.assertIn("Stand aside", format_report(result))


class ValidationTests(unittest.TestCase):
    def test_rejects_too_little_history(self):
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", [100.0] * 10)

    def test_rejects_non_positive_prices(self):
        closes = trending()
        closes[5] = 0.0
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", closes)

    def test_rejects_misaligned_highs_or_lows(self):
        closes = trending()
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", closes, highs=closes[:-1])
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", closes, lows=closes[:-1])

    def test_rejects_a_non_positive_expiry(self):
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", trending(), days_to_expiry=0)

    def test_rejects_a_non_positive_size(self):
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", trending(), contracts=0)

    def test_rejects_a_non_positive_implied_vol(self):
        with self.assertRaises(ValueError):
            analyze_option_opportunity("X", trending(), implied_vol=0.0)


if __name__ == "__main__":
    unittest.main()
