"""Conservative future trade-outcome labels, purely for supervised training.

NOT FEATURES. A signal on candle i is assumed known at its CLOSE.
Entry is the NEXT candle's OPEN. This helper is also used by the research runner.
Intrabar collision is assumed to hit STOP before target.
"""
import numpy as np
from trading_costs import load_settings, quantity_for_quote_budget, settle_trade

# All research/paper simulations load the SAME fee settings as the decision gate.
DEFAULT_FEES = load_settings()
MODEL_QUOTE_BUDGET = 50.0
STOP_FRACTION = 0.045  # 4.5% below reference entry price
TARGET_FRACTION = 0.075  # 7.5% above reference entry price
HOLD_BARS = 72         # 12 days in 4h candles


def net_return(entry_price: float, exit_price: float, *,
               volatility_frac: float = 0.0, settings=None,
               quote_budget: float = MODEL_QUOTE_BUDGET) -> float:
    """P&L after the shared fee model, relative to actual total entry cost."""
    cfg = DEFAULT_FEES if settings is None else settings
    qty = quantity_for_quote_budget(entry_price, quote_budget, cfg,
                                    volatility_frac=volatility_frac)
    ledger = settle_trade(entry_price, exit_price, qty, cfg,
                          volatility_frac=volatility_frac)
    return ledger.net_return_on_outlay


def future_net_trade_labels(opens, highs, lows, closes, hold=HOLD_BARS,
                            volatility_fracs=None, settings=None):
    """Return net P&L label for EACH closed-candle signal, or np.nan near end.

    An entry uses OPEN[i+1]. On later bars: gap-through stop exits at open;
    low<=stop has priority over high>=target; otherwise exit after holding
    `hold` bars at the last close. Fails closed for incomplete future windows.
    """
    o, h, l, c = [np.asarray(a, dtype='float64') for a in (opens, highs, lows, closes)]
    if not (len(o) == len(h) == len(l) == len(c)):
        raise ValueError('OHLC array lengths must match')
    if hold < 1:
        raise ValueError('hold must be positive')
    n = len(o)
    v = np.zeros(n, dtype='float64') if volatility_fracs is None else np.asarray(volatility_fracs, dtype='float64')
    if len(v) != n: raise ValueError('volatility_fracs length mismatch')
    ans = np.full(n, np.nan, dtype='float64')
    for i in range(n - hold):
        entry = o[i + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        stop, take = entry * (1 - STOP_FRACTION), entry * (1 + TARGET_FRACTION)
        sell = np.nan
        for j in range(i + 1, i + hold + 1):
            if not (np.isfinite(o[j]) and np.isfinite(h[j]) and np.isfinite(l[j]) and np.isfinite(c[j])):
                break
            if o[j] <= stop:          # opening gap against trade
                sell = o[j]
                break
            if l[j] <= stop:          # pessimistic: stop before target if both hit
                sell = stop
                break
            if o[j] >= take:          # opening gap up
                sell = o[j]
                break
            if h[j] >= take:
                sell = take
                break
            if j == i + hold:        # expiry only after full future window
                sell = c[j]
        if np.isfinite(sell) and sell > 0:
            vol = float(v[i])
            if np.isfinite(vol) and vol >= 0:
                ans[i] = net_return(entry, sell, volatility_frac=vol, settings=settings)
    return ans
