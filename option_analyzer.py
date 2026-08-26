"""Analyze a stock for option-trading opportunities.

The entry point is :func:`analyze_option_opportunity`. Give it a ticker and a
series of daily closes (plus, optionally, highs/lows and an implied
volatility) and it returns an :class:`OptionOpportunity` describing:

* the directional read (trend + a score in ``[-1, 1]``) from a blend of
  moving averages, MACD, RSI and momentum,
* the volatility regime (is option premium cheap or rich right now?),
* a concrete trade plan - strategy, strikes, theoretical prices and Greeks,
  net debit/credit, max profit/loss, breakevens and probability of profit,
* a confidence score with the rationale and risk flags behind it.

Everything is pure standard library: prices go in, an analysis comes out.
Fetching quotes and chains is left to the caller, so the same function works
against a broker API, a CSV of history or a backtest loop.

Typical use::

    from option_analyzer import analyze_option_opportunity, format_report

    result = analyze_option_opportunity(
        "NVDA",
        closes,                 # daily closes, oldest first
        highs=highs,
        lows=lows,
        implied_vol=0.47,       # ATM IV off the chain, as a decimal
        days_to_expiry=30,
        earnings_in_days=8,
    )
    if result.actionable:
        print(format_report(result))

Run the module directly for a worked example on generated data::

    python option_analyzer.py

This is analysis tooling, not financial advice. Theoretical prices come from
Black-Scholes on a single implied volatility, so they ignore the skew, the
bid/ask spread and early assignment on American options - always check the
live chain before trading.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

__all__ = [
    "Greeks",
    "Indicators",
    "OptionLeg",
    "OptionOpportunity",
    "TradePlan",
    "analyze_option_opportunity",
    "black_scholes",
    "format_report",
]

TRADING_DAYS = 252
DAYS_PER_YEAR = 365.0
CONTRACT_MULTIPLIER = 100

# Below this many closes there is not enough history to say anything useful.
MIN_CLOSES = 30
# Below this, MACD (12/26/9) cannot be computed and the score is re-weighted.
MACD_MIN_CLOSES = 34

# |score| at or beyond this is a directional call; inside it, neutral.
TREND_THRESHOLD = 0.25


# --------------------------------------------------------------------------
# Indicators
# --------------------------------------------------------------------------


def sma(values: Sequence[float], period: int) -> float:
    """Simple moving average of the last ``period`` values."""
    if len(values) < period:
        raise ValueError(f"need {period} values for SMA, got {len(values)}")
    window = values[-period:]
    return sum(window) / period


def ema_series(values: Sequence[float], period: int) -> list[float]:
    """EMA of ``values``, seeded with the SMA of the first ``period`` points.

    The result has ``len(values) - period + 1`` entries; entry ``i``
    corresponds to ``values[i + period - 1]``.
    """
    if len(values) < period:
        raise ValueError(f"need {period} values for EMA, got {len(values)}")
    k = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    out = [current]
    for value in values[period:]:
        current = value * k + current * (1 - k)
        out.append(current)
    return out


def ema(values: Sequence[float], period: int) -> float:
    """Latest exponential moving average."""
    return ema_series(values, period)[-1]


def rsi(values: Sequence[float], period: int = 14) -> float:
    """Wilder's Relative Strength Index over the last ``period`` bars."""
    if len(values) < period + 1:
        raise ValueError(f"need {period + 1} values for RSI, got {len(values)}")
    gains, losses = [], []
    for prev, curr in zip(values, values[1:]):
        change = curr - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1 + rs)


def macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[float, float, float]:
    """Return ``(macd_line, signal_line, histogram)``."""
    if len(values) < slow + signal - 1:
        raise ValueError(
            f"need {slow + signal - 1} values for MACD, got {len(values)}"
        )
    fast_ema = ema_series(values, fast)
    slow_ema = ema_series(values, slow)
    # Align: the fast series starts (slow - fast) entries earlier.
    offset = slow - fast
    line = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
    signal_line = ema_series(line, signal)[-1]
    return line[-1], signal_line, line[-1] - signal_line


def bollinger(
    values: Sequence[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float]:
    """Return ``(lower, middle, upper)`` Bollinger bands."""
    if len(values) < period:
        raise ValueError(f"need {period} values for Bollinger, got {len(values)}")
    window = values[-period:]
    middle = sum(window) / period
    variance = sum((v - middle) ** 2 for v in window) / period
    spread = num_std * math.sqrt(variance)
    return middle - spread, middle, middle + spread


def atr(
    closes: Sequence[float],
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    period: int = 14,
) -> float:
    """Average True Range.

    Without ``highs``/``lows`` this degrades to the average absolute close-to-
    close move, which is a usable stand-in when only closes are available.
    """
    if len(closes) < period + 1:
        raise ValueError(f"need {period + 1} closes for ATR, got {len(closes)}")

    ranges: list[float] = []
    for i in range(1, len(closes)):
        prev_close = closes[i - 1]
        if highs is not None and lows is not None:
            ranges.append(
                max(
                    highs[i] - lows[i],
                    abs(highs[i] - prev_close),
                    abs(lows[i] - prev_close),
                )
            )
        else:
            ranges.append(abs(closes[i] - prev_close))

    # Wilder smoothing over the true-range series.
    value = sum(ranges[:period]) / period
    for true_range in ranges[period:]:
        value = (value * (period - 1) + true_range) / period
    return value


def realized_volatility(closes: Sequence[float], period: int = 20) -> float:
    """Annualized standard deviation of log returns over ``period`` bars."""
    if len(closes) < period + 1:
        raise ValueError(
            f"need {period + 1} closes for realized vol, got {len(closes)}"
        )
    window = closes[-(period + 1) :]
    returns = [math.log(b / a) for a, b in zip(window, window[1:])]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS)


# --------------------------------------------------------------------------
# Option pricing
# --------------------------------------------------------------------------


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class Greeks:
    """Theoretical price and Greeks for a single option."""

    price: float
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float  # per 1 volatility point (0.01)


def black_scholes(
    spot: float,
    strike: float,
    days_to_expiry: float,
    vol: float,
    rate: float = 0.04,
    right: str = "CALL",
) -> Greeks:
    """Black-Scholes price and Greeks for a European option on a stock."""
    right = right.upper()
    if right not in ("CALL", "PUT"):
        raise ValueError(f"right must be CALL or PUT, got {right!r}")
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")

    t = days_to_expiry / DAYS_PER_YEAR
    if t <= 0 or vol <= 0:
        intrinsic = (
            max(spot - strike, 0.0) if right == "CALL" else max(strike - spot, 0.0)
        )
        delta = 0.0 if intrinsic == 0 else (1.0 if right == "CALL" else -1.0)
        return Greeks(price=intrinsic, delta=delta, gamma=0.0, theta=0.0, vega=0.0)

    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    discount = math.exp(-rate * t)

    gamma = norm_pdf(d1) / (spot * vol * sqrt_t)
    vega = spot * norm_pdf(d1) * sqrt_t * 0.01

    if right == "CALL":
        price = spot * norm_cdf(d1) - strike * discount * norm_cdf(d2)
        delta = norm_cdf(d1)
        theta = (
            -spot * norm_pdf(d1) * vol / (2 * sqrt_t)
            - rate * strike * discount * norm_cdf(d2)
        ) / DAYS_PER_YEAR
    else:
        price = strike * discount * norm_cdf(-d2) - spot * norm_cdf(-d1)
        delta = norm_cdf(d1) - 1.0
        theta = (
            -spot * norm_pdf(d1) * vol / (2 * sqrt_t)
            + rate * strike * discount * norm_cdf(-d2)
        ) / DAYS_PER_YEAR

    return Greeks(price=price, delta=delta, gamma=gamma, theta=theta, vega=vega)


def _prob_above(
    spot: float, level: float, vol: float, days: float, rate: float
) -> float:
    """Lognormal probability that the stock finishes above ``level``."""
    t = days / DAYS_PER_YEAR
    if t <= 0 or vol <= 0:
        return 1.0 if spot > level else 0.0
    d2 = (math.log(spot / level) + (rate - 0.5 * vol * vol) * t) / (
        vol * math.sqrt(t)
    )
    return norm_cdf(d2)


def _strike_increment(price: float) -> float:
    """Typical listed strike spacing for a stock at ``price``."""
    if price < 25:
        return 0.5
    if price < 100:
        return 1.0
    if price < 250:
        return 2.5
    return 5.0


def _round_strike(price: float, increment: float) -> float:
    return round(round(price / increment) * increment, 2)


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Indicators:
    """Technical snapshot the directional score is built from."""

    spot: float
    ema9: float
    ema21: float
    ema50: float | None
    rsi14: float
    macd_line: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bollinger_low: float
    bollinger_mid: float
    bollinger_high: float
    percent_b: float
    atr14: float
    momentum_20d: float


@dataclass(frozen=True)
class OptionLeg:
    """One leg of a trade plan, priced off the model."""

    action: str  # BUY | SELL
    right: str  # CALL | PUT
    strike: float
    days_to_expiry: int
    price: float  # theoretical, per share
    delta: float
    gamma: float
    theta: float
    vega: float

    def __str__(self) -> str:
        return (
            f"{self.action} {self.strike:g} {self.right} "
            f"@ ~${self.price:.2f} (delta {self.delta:+.2f})"
        )


@dataclass(frozen=True)
class TradePlan:
    """A concrete, defined-risk structure with its payoff arithmetic.

    Money fields are per contract (already multiplied by 100), for
    ``contracts`` contracts.
    """

    strategy: str
    direction: str  # BULLISH | BEARISH | NEUTRAL
    flow: str  # debit | credit
    legs: tuple[OptionLeg, ...]
    contracts: int
    net_premium: float  # > 0 paid (debit), < 0 received (credit)
    max_profit: float | None  # None means theoretically unlimited
    max_loss: float
    breakevens: tuple[float, ...]
    probability_of_profit: float

    @property
    def reward_risk(self) -> float | None:
        """Max profit divided by max loss; ``None`` when profit is unbounded."""
        if self.max_profit is None:
            return None
        if self.max_loss <= 0:
            return None
        return self.max_profit / self.max_loss


@dataclass(frozen=True)
class OptionOpportunity:
    """Full analysis of one stock for option-trading purposes."""

    ticker: str
    as_of: date
    spot: float
    trend: str  # BULLISH | BEARISH | NEUTRAL
    directional_score: float  # -1 (max bearish) .. +1 (max bullish)
    implied_vol: float
    realized_vol: float
    iv_rank: float | None  # 0..100 when iv_history is supplied
    volatility_regime: str  # CHEAP | NORMAL | RICH
    expected_move: float  # one standard deviation, in dollars, over the DTE
    days_to_expiry: int
    indicators: Indicators
    plan: TradePlan
    confidence: float  # 0..1
    rationale: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def actionable(self) -> bool:
        """True when the setup clears a basic conviction bar."""
        return self.confidence >= 0.5 and self.plan.strategy != "No Trade"


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _build_indicators(
    closes: Sequence[float],
    highs: Sequence[float] | None,
    lows: Sequence[float] | None,
) -> Indicators:
    spot = closes[-1]
    have_macd = len(closes) >= MACD_MIN_CLOSES
    macd_line = macd_signal = macd_hist = None
    if have_macd:
        macd_line, macd_signal, macd_hist = macd(closes)

    low_band, mid_band, high_band = bollinger(closes)
    band_width = high_band - low_band
    percent_b = 0.5 if band_width == 0 else (spot - low_band) / band_width

    lookback = min(21, len(closes) - 1)
    momentum = spot / closes[-1 - lookback] - 1.0

    return Indicators(
        spot=spot,
        ema9=ema(closes, 9),
        ema21=ema(closes, 21),
        ema50=ema(closes, 50) if len(closes) >= 50 else None,
        rsi14=rsi(closes),
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_hist,
        bollinger_low=low_band,
        bollinger_mid=mid_band,
        bollinger_high=high_band,
        percent_b=percent_b,
        atr14=atr(closes, highs, lows),
        momentum_20d=momentum,
    )


def _directional_score(ind: Indicators) -> tuple[float, list[str]]:
    """Blend the indicators into a score in ``[-1, 1]`` plus its rationale."""
    signals: list[tuple[float, float, str]] = []  # (weight, value, note)

    trend_pull = _clamp((ind.spot / ind.ema21 - 1.0) / 0.03)
    signals.append(
        (
            0.25,
            trend_pull,
            f"price ${ind.spot:.2f} is "
            f"{'above' if ind.spot >= ind.ema21 else 'below'} the 21-EMA "
            f"(${ind.ema21:.2f})",
        )
    )

    cross = _clamp((ind.ema9 / ind.ema21 - 1.0) / 0.02)
    signals.append(
        (
            0.20,
            cross,
            f"9-EMA (${ind.ema9:.2f}) is "
            f"{'over' if ind.ema9 >= ind.ema21 else 'under'} the 21-EMA",
        )
    )

    if ind.macd_histogram is not None:
        hist = _clamp(ind.macd_histogram / (0.005 * ind.spot))
        signals.append(
            (
                0.20,
                hist,
                f"MACD histogram {ind.macd_histogram:+.2f} "
                f"({'expanding bullish' if hist >= 0 else 'expanding bearish'})",
            )
        )

    rsi_signal = _clamp((ind.rsi14 - 50.0) / 25.0)
    signals.append((0.20, rsi_signal, f"RSI(14) at {ind.rsi14:.1f}"))

    momentum_signal = _clamp(ind.momentum_20d / 0.06)
    signals.append(
        (0.15, momentum_signal, f"20-day momentum {ind.momentum_20d * 100:+.1f}%")
    )

    total_weight = sum(weight for weight, _, _ in signals)
    score = sum(weight * value for weight, value, _ in signals) / total_weight
    notes = [note for _, _, note in signals]
    return _clamp(score), notes


def _volatility_regime(
    implied: float, realized: float, iv_rank: float | None
) -> tuple[str, str]:
    """Classify premium as CHEAP / NORMAL / RICH, with the reason."""
    if iv_rank is not None:
        if iv_rank >= 60:
            return "RICH", f"IV rank {iv_rank:.0f}/100 - premium is expensive"
        if iv_rank <= 30:
            return "CHEAP", f"IV rank {iv_rank:.0f}/100 - premium is cheap"
        return "NORMAL", f"IV rank {iv_rank:.0f}/100 - premium is middling"

    ratio = implied / realized if realized > 0 else 1.0
    detail = (
        f"IV {implied * 100:.0f}% vs realized {realized * 100:.0f}% "
        f"(ratio {ratio:.2f})"
    )
    if ratio >= 1.25:
        return "RICH", f"{detail} - options carry a fat variance premium"
    if ratio <= 0.90:
        return "CHEAP", f"{detail} - options underprice recent movement"
    return "NORMAL", f"{detail} - premium is in line with movement"


# --------------------------------------------------------------------------
# Strategy construction
# --------------------------------------------------------------------------


def _leg(
    action: str,
    right: str,
    strike: float,
    spot: float,
    dte: int,
    vol: float,
    rate: float,
) -> OptionLeg:
    greeks = black_scholes(spot, strike, dte, vol, rate, right)
    return OptionLeg(
        action=action,
        right=right,
        strike=strike,
        days_to_expiry=dte,
        price=round(greeks.price, 2),
        delta=greeks.delta,
        gamma=greeks.gamma,
        theta=greeks.theta,
        vega=greeks.vega,
    )


def _select_strategy(trend: str, regime: str, event_risk: bool) -> str:
    """Pick a structure from the direction x volatility matrix."""
    if trend == "BULLISH":
        return {
            "CHEAP": "Long Call",
            "NORMAL": "Bull Call Spread",
            "RICH": "Bull Put Spread",
        }[regime]
    if trend == "BEARISH":
        return {
            "CHEAP": "Long Put",
            "NORMAL": "Bear Put Spread",
            "RICH": "Bear Call Spread",
        }[regime]
    # Neutral: sell the range when premium is fat, buy the move when it is
    # cheap and a catalyst is coming, otherwise stand aside.
    if regime == "RICH":
        return "Iron Condor"
    if regime == "CHEAP" and event_risk:
        return "Long Straddle"
    return "No Trade"


def _build_plan(
    strategy: str,
    trend: str,
    spot: float,
    dte: int,
    vol: float,
    rate: float,
    expected_move: float,
    contracts: int,
) -> TradePlan:
    """Turn a chosen strategy into priced legs and payoff arithmetic."""
    increment = _strike_increment(spot)
    atm = _round_strike(spot, increment)
    # Short legs sit one expected move out; wings are a quarter of a move
    # beyond them, and never narrower than two strikes.
    width = max(2 * increment, _round_strike(expected_move * 0.25, increment))
    scale = CONTRACT_MULTIPLIER * contracts

    def priced(action: str, right: str, strike: float) -> OptionLeg:
        return _leg(action, right, strike, spot, dte, vol, rate)

    if strategy == "No Trade":
        return TradePlan(
            strategy="No Trade",
            direction="NEUTRAL",
            flow="none",
            legs=(),
            contracts=0,
            net_premium=0.0,
            max_profit=0.0,
            max_loss=0.0,
            breakevens=(),
            probability_of_profit=0.0,
        )

    if strategy in ("Long Call", "Long Put"):
        right = "CALL" if strategy == "Long Call" else "PUT"
        leg = priced("BUY", right, atm)
        debit = leg.price * scale
        breakeven = atm + leg.price if right == "CALL" else atm - leg.price
        pop = _prob_above(spot, breakeven, vol, dte, rate)
        if right == "PUT":
            pop = 1.0 - pop
        return TradePlan(
            strategy=strategy,
            direction=trend,
            flow="debit",
            legs=(leg,),
            contracts=contracts,
            net_premium=debit,
            max_profit=None,
            max_loss=debit,
            breakevens=(round(breakeven, 2),),
            probability_of_profit=pop,
        )

    if strategy == "Long Straddle":
        call = priced("BUY", "CALL", atm)
        put = priced("BUY", "PUT", atm)
        debit = (call.price + put.price) * scale
        cost = call.price + put.price
        upper, lower = atm + cost, atm - cost
        pop = _prob_above(spot, upper, vol, dte, rate) + (
            1.0 - _prob_above(spot, lower, vol, dte, rate)
        )
        return TradePlan(
            strategy=strategy,
            direction="NEUTRAL",
            flow="debit",
            legs=(call, put),
            contracts=contracts,
            net_premium=debit,
            max_profit=None,
            max_loss=debit,
            breakevens=(round(lower, 2), round(upper, 2)),
            probability_of_profit=pop,
        )

    if strategy == "Bull Call Spread":
        long_strike = atm
        short_strike = _round_strike(spot + expected_move, increment)
        short_strike = max(short_strike, long_strike + increment)
        long_leg = priced("BUY", "CALL", long_strike)
        short_leg = priced("SELL", "CALL", short_strike)
        debit = (long_leg.price - short_leg.price) * scale
        spread = (short_strike - long_strike) * scale
        breakeven = long_strike + (long_leg.price - short_leg.price)
        return TradePlan(
            strategy=strategy,
            direction="BULLISH",
            flow="debit",
            legs=(long_leg, short_leg),
            contracts=contracts,
            net_premium=debit,
            max_profit=spread - debit,
            max_loss=debit,
            breakevens=(round(breakeven, 2),),
            probability_of_profit=_prob_above(spot, breakeven, vol, dte, rate),
        )

    if strategy == "Bear Put Spread":
        long_strike = atm
        short_strike = _round_strike(spot - expected_move, increment)
        short_strike = min(short_strike, long_strike - increment)
        long_leg = priced("BUY", "PUT", long_strike)
        short_leg = priced("SELL", "PUT", short_strike)
        debit = (long_leg.price - short_leg.price) * scale
        spread = (long_strike - short_strike) * scale
        breakeven = long_strike - (long_leg.price - short_leg.price)
        return TradePlan(
            strategy=strategy,
            direction="BEARISH",
            flow="debit",
            legs=(long_leg, short_leg),
            contracts=contracts,
            net_premium=debit,
            max_profit=spread - debit,
            max_loss=debit,
            breakevens=(round(breakeven, 2),),
            probability_of_profit=1.0
            - _prob_above(spot, breakeven, vol, dte, rate),
        )

    if strategy == "Bull Put Spread":
        short_strike = _round_strike(spot - expected_move, increment)
        short_strike = min(short_strike, atm - increment)
        long_strike = short_strike - width
        short_leg = priced("SELL", "PUT", short_strike)
        long_leg = priced("BUY", "PUT", long_strike)
        credit = (short_leg.price - long_leg.price) * scale
        spread = (short_strike - long_strike) * scale
        breakeven = short_strike - (short_leg.price - long_leg.price)
        return TradePlan(
            strategy=strategy,
            direction="BULLISH",
            flow="credit",
            legs=(short_leg, long_leg),
            contracts=contracts,
            net_premium=-credit,
            max_profit=credit,
            max_loss=spread - credit,
            breakevens=(round(breakeven, 2),),
            probability_of_profit=_prob_above(spot, breakeven, vol, dte, rate),
        )

    if strategy == "Bear Call Spread":
        short_strike = _round_strike(spot + expected_move, increment)
        short_strike = max(short_strike, atm + increment)
        long_strike = short_strike + width
        short_leg = priced("SELL", "CALL", short_strike)
        long_leg = priced("BUY", "CALL", long_strike)
        credit = (short_leg.price - long_leg.price) * scale
        spread = (long_strike - short_strike) * scale
        breakeven = short_strike + (short_leg.price - long_leg.price)
        return TradePlan(
            strategy=strategy,
            direction="BEARISH",
            flow="credit",
            legs=(short_leg, long_leg),
            contracts=contracts,
            net_premium=-credit,
            max_profit=credit,
            max_loss=spread - credit,
            breakevens=(round(breakeven, 2),),
            probability_of_profit=1.0
            - _prob_above(spot, breakeven, vol, dte, rate),
        )

    if strategy == "Iron Condor":
        short_call_strike = max(
            _round_strike(spot + expected_move, increment), atm + increment
        )
        short_put_strike = min(
            _round_strike(spot - expected_move, increment), atm - increment
        )
        long_call_strike = short_call_strike + width
        long_put_strike = short_put_strike - width
        short_call = priced("SELL", "CALL", short_call_strike)
        long_call = priced("BUY", "CALL", long_call_strike)
        short_put = priced("SELL", "PUT", short_put_strike)
        long_put = priced("BUY", "PUT", long_put_strike)

        credit_per_share = (
            short_call.price + short_put.price - long_call.price - long_put.price
        )
        credit = credit_per_share * scale
        spread = max(
            long_call_strike - short_call_strike,
            short_put_strike - long_put_strike,
        ) * scale
        upper_be = short_call_strike + credit_per_share
        lower_be = short_put_strike - credit_per_share
        pop = _prob_above(spot, lower_be, vol, dte, rate) - _prob_above(
            spot, upper_be, vol, dte, rate
        )
        return TradePlan(
            strategy=strategy,
            direction="NEUTRAL",
            flow="credit",
            legs=(long_put, short_put, short_call, long_call),
            contracts=contracts,
            net_premium=-credit,
            max_profit=credit,
            max_loss=spread - credit,
            breakevens=(round(lower_be, 2), round(upper_be, 2)),
            probability_of_profit=pop,
        )

    raise ValueError(f"unknown strategy {strategy!r}")


def _score_confidence(
    score: float,
    trend: str,
    strategy: str,
    ind: Indicators,
    have_macd: bool,
    event_inside_expiry: bool,
) -> tuple[float, list[str]]:
    """Grade the setup and collect the risk flags that moved the grade."""
    risks: list[str] = []

    if strategy == "No Trade":
        return 0.0, ["No directional edge and premium is not rich enough to sell."]

    if trend == "NEUTRAL":
        # Premium-selling and event trades do not need a directional read.
        confidence = 0.55
    else:
        confidence = 0.45 + 0.40 * min(abs(score) / 0.6, 1.0)

    if not have_macd:
        confidence -= 0.07
        risks.append("Not enough history for MACD; the score is re-weighted.")

    if event_inside_expiry:
        if strategy == "Long Straddle":
            confidence += 0.05
        else:
            confidence -= 0.08
            risks.append(
                "An earnings event lands before expiry - expect an IV crush "
                "and a gap the model does not price."
            )

    if trend == "BULLISH" and ind.rsi14 > 75:
        confidence -= 0.06
        risks.append(f"RSI(14) at {ind.rsi14:.1f} is overbought; entries chase.")
    if trend == "BEARISH" and ind.rsi14 < 25:
        confidence -= 0.06
        risks.append(f"RSI(14) at {ind.rsi14:.1f} is oversold; bounce risk.")

    if trend == "BULLISH" and ind.percent_b > 1.0:
        risks.append("Price is outside the upper Bollinger band - extended.")
    if trend == "BEARISH" and ind.percent_b < 0.0:
        risks.append("Price is outside the lower Bollinger band - extended.")

    if ind.ema50 is not None:
        if trend == "BULLISH" and ind.spot < ind.ema50:
            confidence -= 0.05
            risks.append(
                f"Bullish read but price is under the 50-EMA "
                f"(${ind.ema50:.2f}) - counter to the larger trend."
            )
        if trend == "BEARISH" and ind.spot > ind.ema50:
            confidence -= 0.05
            risks.append(
                f"Bearish read but price is over the 50-EMA "
                f"(${ind.ema50:.2f}) - counter to the larger trend."
            )

    return _clamp(confidence, 0.2, 0.9), risks


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def analyze_option_opportunity(
    ticker: str,
    closes: Sequence[float],
    *,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    implied_vol: float | None = None,
    iv_history: Sequence[float] | None = None,
    days_to_expiry: int = 30,
    risk_free_rate: float = 0.04,
    earnings_in_days: int | None = None,
    contracts: int = 1,
    as_of: date | None = None,
) -> OptionOpportunity:
    """Analyze ``ticker`` and return the option trade its setup argues for.

    Args:
        ticker: Symbol being analyzed, used for labelling only.
        closes: Daily closing prices, oldest first. At least
            :data:`MIN_CLOSES` are required; 60+ gives every indicator.
        highs: Daily highs aligned with ``closes``. Improves the ATR.
        lows: Daily lows aligned with ``closes``.
        implied_vol: At-the-money implied volatility as a decimal (``0.35``
            for 35%). Defaults to realized volatility plus a 10% variance
            premium, which is a rough stand-in only.
        iv_history: Past implied volatilities, oldest first. When supplied,
            the volatility regime is graded by IV rank instead of by the
            IV/realized ratio.
        days_to_expiry: Calendar days to the expiry being traded.
        risk_free_rate: Annualized risk-free rate as a decimal.
        earnings_in_days: Calendar days to the next earnings report, if known.
        contracts: Position size; scales the money fields of the trade plan.
        as_of: Date of the last close. Defaults to today.

    Returns:
        An :class:`OptionOpportunity` with the directional read, the
        volatility regime, a priced trade plan and a confidence score.

    Raises:
        ValueError: If the inputs are too short, misaligned or out of range.
    """
    closes = [float(c) for c in closes]
    if len(closes) < MIN_CLOSES:
        raise ValueError(
            f"need at least {MIN_CLOSES} closes to analyze, got {len(closes)}"
        )
    if any(c <= 0 for c in closes):
        raise ValueError("closes must be positive")
    for name, series in (("highs", highs), ("lows", lows)):
        if series is not None and len(series) != len(closes):
            raise ValueError(f"{name} must align with closes")
    if days_to_expiry <= 0:
        raise ValueError("days_to_expiry must be positive")
    if contracts <= 0:
        raise ValueError("contracts must be positive")
    if implied_vol is not None and implied_vol <= 0:
        raise ValueError("implied_vol must be positive")

    spot = closes[-1]
    ind = _build_indicators(closes, highs, lows)
    have_macd = ind.macd_histogram is not None

    realized = realized_volatility(closes)
    if implied_vol is None:
        # No chain supplied: assume the usual small variance premium.
        implied = max(realized * 1.10, 0.05)
        iv_note = (
            f"No implied vol supplied - assuming {implied * 100:.0f}% from "
            f"realized volatility."
        )
    else:
        implied = float(implied_vol)
        iv_note = None

    iv_rank: float | None = None
    if iv_history:
        lo, hi = min(iv_history), max(iv_history)
        iv_rank = 50.0 if hi == lo else _clamp((implied - lo) / (hi - lo), 0, 1) * 100

    score, score_notes = _directional_score(ind)
    if score >= TREND_THRESHOLD:
        trend = "BULLISH"
    elif score <= -TREND_THRESHOLD:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    regime, regime_note = _volatility_regime(implied, realized, iv_rank)
    expected_move = spot * implied * math.sqrt(days_to_expiry / DAYS_PER_YEAR)

    event_inside_expiry = (
        earnings_in_days is not None and 0 <= earnings_in_days <= days_to_expiry
    )
    strategy = _select_strategy(trend, regime, event_inside_expiry)
    plan = _build_plan(
        strategy,
        trend,
        spot,
        days_to_expiry,
        implied,
        risk_free_rate,
        expected_move,
        contracts,
    )
    confidence, risks = _score_confidence(
        score, trend, strategy, ind, have_macd, event_inside_expiry
    )

    rationale = [
        f"Directional score {score:+.2f} -> {trend}.",
        *score_notes,
        regime_note,
        f"A {days_to_expiry}-day expected move of ${expected_move:.2f} "
        f"({expected_move / spot * 100:.1f}%) sets the strikes.",
    ]
    if iv_note:
        rationale.append(iv_note)
        risks.append("Implied volatility was inferred, not read off a chain.")
    if strategy != "No Trade":
        rationale.append(
            f"{trend} bias with {regime} premium argues for a {strategy.lower()}."
        )

    if len(closes) < 50:
        risks.append(
            f"Only {len(closes)} closes of history - longer-term trend is unknown."
        )

    return OptionOpportunity(
        ticker=ticker.upper(),
        as_of=as_of or date.today(),
        spot=spot,
        trend=trend,
        directional_score=score,
        implied_vol=implied,
        realized_vol=realized,
        iv_rank=iv_rank,
        volatility_regime=regime,
        expected_move=expected_move,
        days_to_expiry=days_to_expiry,
        indicators=ind,
        plan=plan,
        confidence=confidence,
        rationale=tuple(rationale),
        risks=tuple(risks),
    )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def format_report(opportunity: OptionOpportunity) -> str:
    """Render an :class:`OptionOpportunity` as a Markdown trade note."""
    op = opportunity
    ind = op.indicators
    plan = op.plan
    lines = [
        f"# {op.ticker} Options Analysis",
        f"**Date:** {op.as_of.isoformat()}  **Spot:** ${op.spot:.2f}",
        "",
        "### Pre-Trade Analysis",
        "| Factor | Details |",
        "|---|---|",
        f"| Trend | {op.trend} (score {op.directional_score:+.2f}) |",
        f"| Technical | RSI: {ind.rsi14:.1f}  EMA9: ${ind.ema9:.2f}  "
        f"EMA21: ${ind.ema21:.2f}  "
        f"BB: ${ind.bollinger_low:.2f}-${ind.bollinger_high:.2f} |",
        f"| Volatility | IV: {op.implied_vol * 100:.0f}% ({op.volatility_regime})"
        f"  Realized: {op.realized_vol * 100:.0f}%  ATR(14): ${ind.atr14:.2f} |",
        f"| Expected Move ({op.days_to_expiry}d) | "
        f"+/-${op.expected_move:.2f} ({op.expected_move / op.spot * 100:.1f}%) |",
        f"| Confidence | {op.confidence * 100:.0f}% |",
        "",
        "### Trade Plan",
        "| Field | Value |",
        "|---|---|",
        f"| Strategy | {plan.strategy} |",
    ]

    if plan.strategy == "No Trade":
        lines.append("| Action | Stand aside - no edge worth the risk |")
    else:
        for i, leg in enumerate(plan.legs, start=1):
            lines.append(f"| Leg {i} | {leg} |")
        lines += [
            f"| DTE | {op.days_to_expiry} |",
            f"| Contracts | {plan.contracts} |",
            f"| Net {plan.flow.title()} | ${abs(plan.net_premium):.2f} |",
            "| Max Profit | "
            + (
                "unlimited |"
                if plan.max_profit is None
                else f"${plan.max_profit:.2f} |"
            ),
            f"| Max Loss | ${plan.max_loss:.2f} |",
            "| Breakeven | "
            + " / ".join(f"${b:.2f}" for b in plan.breakevens)
            + " |",
            f"| Chance of Profit | ~{plan.probability_of_profit * 100:.0f}% |",
            "| Reward/Risk | "
            + (
                "unbounded |"
                if plan.reward_risk is None
                else f"{plan.reward_risk:.2f} : 1 |"
            ),
        ]

    lines += ["", "### Rationale"]
    lines += [f"- {note}" for note in op.rationale]

    if op.risks:
        lines += ["", "### Risks"]
        lines += [f"- {risk}" for risk in op.risks]

    lines += [
        "",
        "_Model output for research only - not financial advice. Theoretical "
        "prices ignore skew, spreads and early assignment._",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------


def _sample_history(
    days: int = 120, start: float = 180.0, drift: float = 0.0012, seed: int = 7
) -> tuple[list[float], list[float], list[float]]:
    """Deterministic OHLC-ish history so the demo runs without a data feed."""
    rng = random.Random(seed)
    closes, highs, lows = [], [], []
    price = start
    for _ in range(days):
        price *= math.exp(drift + rng.gauss(0, 0.016))
        wiggle = price * abs(rng.gauss(0, 0.008))
        closes.append(round(price, 2))
        highs.append(round(price + wiggle, 2))
        lows.append(round(price - wiggle, 2))
    return closes, highs, lows


def main() -> None:
    closes, highs, lows = _sample_history()
    opportunity = analyze_option_opportunity(
        "DEMO",
        closes,
        highs=highs,
        lows=lows,
        implied_vol=0.42,
        iv_history=[0.28, 0.31, 0.35, 0.39, 0.44, 0.47],
        days_to_expiry=30,
        earnings_in_days=12,
    )
    print(format_report(opportunity))


if __name__ == "__main__":
    main()
