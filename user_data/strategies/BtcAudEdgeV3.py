"""Research candidate: FreqAI LightGBM predicts *net hypothetical trade P&L*.

No live activation from this file. Kraken BTC/AUD spot, 4h, long-only.
Model can adapt its estimates, not the exposure cap, protective exits, or keys.
"""
from datetime import datetime
import json
import math
import time
from pathlib import Path

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from v3_outcomes import future_net_trade_labels

GUARD_HEARTBEAT = Path('/freqtrade/user_data/risk_guard_heartbeat.json')


class BtcAudEdgeV3(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = '4h'
    startup_candle_count = 230
    process_only_new_candles = True
    max_open_trades = 1
    position_adjustment_enable = False

    # Strategy price stop ~= -4.5%; actual after-fee loss is larger.
    stoploss = -0.045
    # +5.5% net trade profit as reported by Freqtrade. Approx +7.5% gross
    # assuming tier-1 taker fees + spread/slippage, but not precisely equal.
    minimal_roi = {'0': 0.055}
    use_exit_signal = False
    exit_profit_only = False

    # Prediction is NET return incl assumed fees/slippage, not gross movement.
    MIN_EXPECTED_NET_RETURN = 0.012  # +1.2% predicted EV margin; research candidate
    MAX_MODEL_PREDICTION = 0.20      # reject implausible / outlier predictions

    order_types = {
        'entry': 'market', 'exit': 'market', 'emergency_exit': 'market',
        'force_entry': 'market', 'force_exit': 'market', 'stoploss': 'market',
        'stoploss_on_exchange': True, 'stoploss_on_exchange_interval': 60,
    }

    @property
    def protections(self):
        return [
            {'method': 'CooldownPeriod', 'stop_duration_candles': 12},
            {'method': 'StoplossGuard', 'lookback_period_candles': 72,
             'trade_limit': 2, 'stop_duration_candles': 48, 'only_per_pair': False},
            {'method': 'MaxDrawdown', 'lookback_period_candles': 180,
             'trade_limit': 2, 'stop_duration_candles': 48,
             'max_allowed_drawdown': 0.05},
        ]

    def feature_engineering_expand_all(self, df: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        df['%-rsi-period'] = ta.RSI(df, timeperiod=period)
        df['%-adx-period'] = ta.ADX(df, timeperiod=period)
        df['%-ema-distance-period'] = df['close'] / ta.EMA(df, timeperiod=period) - 1
        df['%-atr-ratio-period'] = ta.ATR(df, timeperiod=period) / df['close']
        df['%-volume-relative-period'] = df['volume'] / df['volume'].rolling(period).mean().replace(0, float('nan'))
        return df

    def feature_engineering_expand_basic(self, df: DataFrame,
                                         metadata: dict, **kwargs) -> DataFrame:
        for p in (1, 3, 6, 12, 42):
            df[f'%-return-{p}'] = df['close'].pct_change(p)
        df['%-high-low-range'] = (df['high'] - df['low']) / df['close']
        return df

    def feature_engineering_standard(self, df: DataFrame,
                                     metadata: dict, **kwargs) -> DataFrame:
        df['%-weekday'] = df['date'].dt.dayofweek / 7.0
        df['%-hour'] = df['date'].dt.hour / 24.0
        return df

    def set_freqai_targets(self, df: DataFrame, metadata: dict,
                           **kwargs) -> DataFrame:
        hold = int(self.freqai_info['feature_parameters']['label_period_candles'])
        if hold != 72:
            raise ValueError('V3 training labels require exactly 72 4h candles')
        # Forward data here is REQUIRED for training TARGETS only; it is never
        # part of %-prefixed live features or used by inference.
        df['&-net-trade-return'] = future_net_trade_labels(
            df['open'], df['high'], df['low'], df['close'], hold=hold,
            volatility_fracs=df['atr_frac'].fillna(0).clip(lower=0))
        return df

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df['ema20'] = ta.EMA(df, timeperiod=20)
        df['ema50'] = ta.EMA(df, timeperiod=50)
        df['ema200'] = ta.EMA(df, timeperiod=200)
        df['rsi14'] = ta.RSI(df, timeperiod=14)
        df['adx14'] = ta.ADX(df, timeperiod=14)
        df['atr14'] = ta.ATR(df, timeperiod=14)
        df['atr_frac'] = df['atr14'] / df['close']
        df['vol_avg20'] = df['volume'].rolling(20).mean()
        df = self.freqai.start(df, metadata, self)
        return df

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df['enter_long'] = 0
        df['enter_tag'] = ''
        # Price filters gate for liquidity / bullish regimes; AI compares net
        # hypothetical trade results, not 48h gross percentage movements.
        setup = (
            (df['close'] > df['ema200']) & (df['ema50'] > df['ema200']) &
            (df['ema200'] > df['ema200'].shift(12)) &
            (df['adx14'] >= 14) & (df['close'] > df['ema20']) &
            (df['low'].rolling(4).min() <= df['ema20'] * 1.005) &
            (df['close'] <= df['ema20'] + 1.25 * df['atr14']) &
            df['rsi14'].between(40, 68) &
            df['atr_frac'].between(0.005, 0.07) &
            (df['volume'] >= 0.5 * df['vol_avg20']) & (df['volume'] > 0)
        )
        model = (
            (df['do_predict'] == 1) &
            (df['&-net-trade-return'] >= self.MIN_EXPECTED_NET_RETURN) &
            (df['&-net-trade-return'] <= self.MAX_MODEL_PREDICTION)
        )
        df.loc[setup & model, ['enter_long', 'enter_tag']] = (1, 'v3_net_ev_swing')
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        # No early AI exits: matching time/target/stop rules to training labels
        # reduces mismatch between trained outcome and live trade path.
        df['exit_long'] = 0
        return df

    def custom_exit(self, pair: str, trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        age_hours = (current_time - trade.open_date_utc).total_seconds() / 3600
        if age_hours >= 288:  # 72 * 4 hours
            return '12day_timeout'
        return None

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None,
                            side: str, **kwargs) -> float:
        try:
            equity = float(self.wallets.get_total_stake_amount())
            desired = min(float(proposed_stake), float(max_stake), .05 * equity)
            if not math.isfinite(desired) or desired <= 0:
                return 0
            if min_stake is not None and desired < min_stake:
                return 0
            return desired
        except (ValueError, TypeError, OverflowError, AttributeError):
            return 0

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: str | None, side: str, **kwargs) -> bool:
        mode = getattr(self.config.get('runmode'), 'value', '')
        if mode in {'backtest', 'hyperopt'}:
            return True
        if pair != 'BTC/AUD' or side != 'long' or not math.isfinite(rate) or rate <= 0:
            return False
        # Hard security boundary: no real orders from this project under any file flag.
        if not self.config.get('dry_run', False):
            return False
        try:
            hb = json.loads(GUARD_HEARTBEAT.read_text())
            age = time.time() - float(hb['timestamp'])
            if hb['status'] != 'ok' or not 0 <= age <= 120:
                return False
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False
        if self.dp is None:
            return False
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty or rate > float(dataframe.iloc[-1]['close']) * 1.0025:
            return False
        return True
