"""The project's single source of truth for assumed exchange trading costs.

All price inputs are *mid/reference* quotes. All fee/slippage values are
fractions (0.008 means 0.8%), except fields explicitly suffixed '_bps'.

No network, API keys, exchange clients or order submission exists here.
Trading volume for tiers is in USD, while quote amounts are in AUD for BTC/AUD.
Do not equate those currencies; pass the appropriate USD rolling volume.

The model intentionally estimates costs; live order-book depth, limit-order
fill probability and exchange asset-specific charges can differ materially.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
import json
import math
import os
from typing import Literal

Side = Literal['buy', 'sell']
Liquidity = Literal['maker', 'taker']


def _finite(value: float, label: str, minimum: float | None = 0.0) -> float:
    value = float(value)
    if not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f'{label} must be finite' + (f' and >= {minimum}' if minimum is not None else ''))
    return value


@dataclass(frozen=True)
class FeeTier:
    min_30day_volume_usd: float
    maker_rate: float
    taker_rate: float

    def __post_init__(self):
        _finite(self.min_30day_volume_usd, 'tier threshold')
        _finite(self.maker_rate, 'maker_rate', -0.01)  # supports configured maker rebates
        _finite(self.taker_rate, 'taker_rate')
        if self.maker_rate >= 1 or self.taker_rate >= 1:
            raise ValueError('Fee rates must be fractions, not percentages')


@dataclass(frozen=True)
class FeeSettings:
    exchange: str = 'kraken'
    instrument: Literal['spot', 'perpetual'] = 'spot'
    tiers: tuple[FeeTier, ...] = (FeeTier(0.0, 0.004, 0.008),)
    spread_bps: float = 8.0    # full bid/ask spread (split between sides)
    base_slippage_bps: float = 2.0
    volatility_slippage_multiplier: float = 0.04  # 2% ATR -> 8 bps
    size_slippage_bps: float = 3.0
    reference_liquidity_quote: float = 10_000.0  # assumed quote depth
    max_slippage_bps: float = 100.0
    funding_rate_per_8h: float = 0.0  # signed: positive means long pays
    withdrawal_fee_quote: float = 0.0
    network_fee_quote: float = 0.0

    def __post_init__(self):
        if self.instrument not in ('spot', 'perpetual'):
            raise ValueError('instrument must be spot or perpetual')
        if not self.exchange or not self.tiers or self.tiers[0].min_30day_volume_usd != 0:
            raise ValueError('Nonempty exchange and tier starting at USD 0 required')
        th=[tier.min_30day_volume_usd for tier in self.tiers]
        if any(a >= b for a,b in zip(th,th[1:])):
            raise ValueError('Tier volume thresholds must strictly increase')
        for name in ('spread_bps', 'base_slippage_bps', 'volatility_slippage_multiplier',
                     'size_slippage_bps', 'max_slippage_bps', 'withdrawal_fee_quote',
                     'network_fee_quote'):
            _finite(getattr(self, name), name)
        _finite(self.reference_liquidity_quote, 'reference_liquidity_quote')
        if self.reference_liquidity_quote <= 0:
            raise ValueError('reference_liquidity_quote must be positive')
        _finite(self.funding_rate_per_8h, 'funding rate', -1.)
        if self.instrument == 'spot' and self.funding_rate_per_8h != 0:
            raise ValueError('Spot trading has no perpetual funding')
        if self.max_slippage_bps >= 10_000 or self.spread_bps >= 20_000:
            raise ValueError('Spread/slippage assumptions out of range')

    def rate(self, liquidity: Liquidity, rolling_volume_usd: float = 0.0) -> float:
        if liquidity not in ('maker', 'taker'):
            raise ValueError('liquidity must be maker or taker')
        rolling_volume_usd = _finite(rolling_volume_usd, 'rolling 30-day USD volume')
        chosen = self.tiers[0]
        for tier in self.tiers:
            if tier.min_30day_volume_usd <= rolling_volume_usd:
                chosen = tier
            else:
                break
        return chosen.maker_rate if liquidity == 'maker' else chosen.taker_rate

    @staticmethod
    def zero() -> 'FeeSettings':
        """Fee-off comparison: also disables spread, slippage and funding."""
        return FeeSettings(exchange='simulation', tiers=(FeeTier(0, 0, 0),),
                           spread_bps=0, base_slippage_bps=0,
                           volatility_slippage_multiplier=0, size_slippage_bps=0,
                           max_slippage_bps=0, funding_rate_per_8h=0,
                           withdrawal_fee_quote=0, network_fee_quote=0)


@dataclass(frozen=True)
class Execution:
    side: Side
    liquidity: Liquidity
    mid_price: float
    execution_price: float
    quantity_base: float
    mid_notional_quote: float
    executed_notional_quote: float
    fee_rate: float
    fee_quote: float
    slippage_rate: float
    slippage_quote: float
    spread_quote: float  # signed; maker improves price if assumed filled


@dataclass(frozen=True)
class TradeLedger:
    entry: Execution
    exit: Execution
    gross_pnl_quote: float
    trading_fees_quote: float
    slippage_quote: float
    spread_quote: float
    funding_quote: float
    withdrawal_network_quote: float
    net_pnl_quote: float
    entry_total_outlay_quote: float
    exit_total_received_quote: float
    net_return_on_outlay: float

    @property
    def total_costs_quote(self) -> float:
        return (self.trading_fees_quote + self.slippage_quote + self.spread_quote
                + self.funding_quote + self.withdrawal_network_quote)


def load_settings(path: str | Path | None = None) -> FeeSettings:
    """Load one JSON profile; BOT_FEE_CONFIG overrides default only if set."""
    file = Path(path or os.environ.get('BOT_FEE_CONFIG')
                or Path(__file__).resolve().parents[1] / 'config' / 'fees.json')
    raw = json.loads(file.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError('Fee JSON must be an object')
    valid = set(FeeSettings.__dataclass_fields__)
    unknown = set(raw).difference(valid)
    if unknown:
        raise ValueError(f'Unrecognised fee settings: {sorted(unknown)}')
    raw['tiers'] = tuple(FeeTier(**obj) for obj in raw['tiers'])
    return FeeSettings(**raw)


def estimate_execution(mid_price: float, quantity_base: float, side: Side,
                       liquidity: Liquidity, settings: FeeSettings,
                       volatility_frac: float = 0.0,
                       rolling_volume_usd: float = 0.0) -> Execution:
    """Estimate one filled buy/sell order from the mid, without fills/market IO.

    Maker quote crosses *negative* half spread (bid buy / ask sell), assuming
    the passive order fills. This is NOT a maker fill-probability model.
    """
    mid_price = _finite(mid_price, 'mid_price')
    quantity_base = _finite(quantity_base, 'quantity_base')
    volatility_frac = _finite(volatility_frac, 'volatility_frac')
    if not mid_price or not quantity_base:
        raise ValueError('mid_price and quantity must be positive')
    if side not in ('buy', 'sell'):
        raise ValueError('side must be buy/sell')
    rate = settings.rate(liquidity, rolling_volume_usd)
    notional = mid_price * quantity_base
    size_ratio = notional / settings.reference_liquidity_quote
    slippage_bps = min(settings.max_slippage_bps,
        settings.base_slippage_bps +
        settings.volatility_slippage_multiplier * volatility_frac * 10_000 +
        settings.size_slippage_bps * math.sqrt(size_ratio))
    slip = slippage_bps / 10_000
    signed_half_spread = settings.spread_bps / 20_000 * (1 if liquidity == 'taker' else -1)
    impact = signed_half_spread + slip
    price = mid_price * (1 + impact if side == 'buy' else 1 - impact)
    if price <= 0:
        raise ValueError('Execution price is non-positive under cost assumptions')
    gross_fill = price * quantity_base
    return Execution(side=side, liquidity=liquidity, mid_price=mid_price,
        execution_price=price, quantity_base=quantity_base,
        mid_notional_quote=notional, executed_notional_quote=gross_fill,
        fee_rate=rate, fee_quote=gross_fill * rate,
        slippage_rate=slip, slippage_quote=notional * slip,
        spread_quote=notional * signed_half_spread)


def settle_trade(entry_mid: float, exit_mid: float, quantity_base: float,
                 settings: FeeSettings, *, entry_liquidity: Liquidity = 'taker',
                 exit_liquidity: Liquidity = 'taker',
                 volatility_frac: float = 0.0,
                 rolling_volume_usd: float = 0.0,
                 holding_hours: float = 0.0, include_transfer_fees: bool = False) -> TradeLedger:
    """Charge both order fills and produce an auditable spot/perp P&L ledger.

    Quote fees are calculated on executed notional. Funding uses midpoint
    entry notional and linear 8-hour pro-rata approximation (not actual marks).
    No withdrawal fees are charged per trade unless opted in.
    """
    holding_hours = _finite(holding_hours, 'holding_hours')
    buy = estimate_execution(entry_mid, quantity_base, 'buy', entry_liquidity,
                             settings, volatility_frac, rolling_volume_usd)
    sell = estimate_execution(exit_mid, quantity_base, 'sell', exit_liquidity,
                              settings, volatility_frac, rolling_volume_usd)
    gross = quantity_base * (exit_mid - entry_mid)
    fees = buy.fee_quote + sell.fee_quote
    spread = buy.spread_quote + sell.spread_quote
    slip = buy.slippage_quote + sell.slippage_quote
    funding = (buy.mid_notional_quote * settings.funding_rate_per_8h *
               holding_hours / 8.0 if settings.instrument == 'perpetual' else 0.0)
    transfer = (settings.withdrawal_fee_quote + settings.network_fee_quote
                if include_transfer_fees else 0.0)
    entry_outlay = buy.executed_notional_quote + buy.fee_quote
    exit_receipts = sell.executed_notional_quote - sell.fee_quote
    net = exit_receipts - entry_outlay - funding - transfer
    decomposition = gross - fees - spread - slip - funding - transfer
    if not math.isclose(net, decomposition, abs_tol=1e-8 * max(1, abs(net))):
        raise ArithmeticError('Cost decomposition did not reconcile')
    if entry_outlay <= 0:
        raise ValueError('Non-positive cost basis')
    return TradeLedger(entry=buy, exit=sell, gross_pnl_quote=gross,
        trading_fees_quote=fees, slippage_quote=slip, spread_quote=spread,
        funding_quote=funding, withdrawal_network_quote=transfer,
        net_pnl_quote=net, entry_total_outlay_quote=entry_outlay,
        exit_total_received_quote=exit_receipts, net_return_on_outlay=net/entry_outlay)


def quantity_for_quote_budget(mid_price: float, quote_budget: float,
                              settings: FeeSettings, *, liquidity: Liquidity = 'taker',
                              volatility_frac: float = 0.,
                              rolling_volume_usd: float = 0.) -> float:
    """Return largest base quantity with price+entry fee <= quote budget.

    Size-dependent slippage makes the price vary with quantity, hence bisection.
    """
    quote_budget = _finite(quote_budget, 'quote_budget')
    mid_price = _finite(mid_price, 'mid_price')
    if mid_price <= 0 or quote_budget <= 0:
        raise ValueError('budget and price must be positive')
    low, high = 0., quote_budget / mid_price * 2
    for _ in range(70):
        mid = (low+high)/2
        if mid == 0:
            break
        execution = estimate_execution(mid_price, mid, 'buy', liquidity,
                            settings, volatility_frac, rolling_volume_usd)
        cost = execution.executed_notional_quote + execution.fee_quote
        if cost <= quote_budget:low=mid
        else:high=mid
    return low


def minimum_break_even_move(entry_mid: float, quote_budget: float,
                            settings: FeeSettings, *, entry_liquidity: Liquidity = 'taker',
                            exit_liquidity: Liquidity = 'taker',
                            volatility_frac: float = 0.,
                            rolling_volume_usd: float = 0., holding_hours: float = 0.,
                            min_net_edge: float = 0.) -> float:
    """Required exit-mid *fractional price gain* to cover all costs and EV edge."""
    min_net_edge = _finite(min_net_edge, 'min_net_edge')
    qty = quantity_for_quote_budget(entry_mid, quote_budget, settings,
                 liquidity=entry_liquidity, volatility_frac=volatility_frac,
                 rolling_volume_usd=rolling_volume_usd)
    def score(move: float) -> float:
        leg = settle_trade(entry_mid, entry_mid*(1+move), qty, settings,
              entry_liquidity=entry_liquidity, exit_liquidity=exit_liquidity,
              volatility_frac=volatility_frac, rolling_volume_usd=rolling_volume_usd,
              holding_hours=holding_hours)
        return leg.net_return_on_outlay - min_net_edge
    low, high = -0.5, 0.05
    while score(high) < 0 and high < 32: high=2*high+0.05
    if score(high) < 0: raise ValueError('No feasible break-even crossing')
    if score(low) >= 0: return low
    for _ in range(65):
        mid=(low+high)/2
        if score(mid)>=0:high=mid
        else:low=mid
    return high


def expected_trade_edge(entry_mid: float, predicted_exit_mid: float,
                        quote_budget: float, settings: FeeSettings, *,
                        minimum_net_return: float, volatility_frac: float=0.,
                        holding_hours: float=0., entry_liquidity: Liquidity='taker',
                        exit_liquidity: Liquidity='taker', rolling_volume_usd: float=0.) -> tuple[bool, TradeLedger]:
    """Strategy gate using exactly the same fee model as settlement."""
    minimum_net_return = _finite(minimum_net_return,'minimum_net_return')
    qty=quantity_for_quote_budget(entry_mid,quote_budget,settings,
                     liquidity=entry_liquidity,volatility_frac=volatility_frac,
                     rolling_volume_usd=rolling_volume_usd)
    ledger=settle_trade(entry_mid,predicted_exit_mid,qty,settings,
            entry_liquidity=entry_liquidity,exit_liquidity=exit_liquidity,
            volatility_frac=volatility_frac,rolling_volume_usd=rolling_volume_usd,
            holding_hours=holding_hours)
    return ledger.net_return_on_outlay >= minimum_net_return, ledger


def ledger_to_log(ledger: TradeLedger) -> dict:
    """JSON-serialisable complete per-trade audit record."""
    return {'gross_pnl_quote': ledger.gross_pnl_quote,
            'entry_fee_quote': ledger.entry.fee_quote,
            'exit_fee_quote': ledger.exit.fee_quote,
            'total_trading_fees_quote': ledger.trading_fees_quote,
            'spread_quote': ledger.spread_quote,
            'slippage_quote': ledger.slippage_quote,
            'funding_quote': ledger.funding_quote,
            'withdrawal_network_quote': ledger.withdrawal_network_quote,
            'total_costs_quote': ledger.total_costs_quote,
            'net_pnl_quote': ledger.net_pnl_quote,
            'net_return_pct': ledger.net_return_on_outlay*100,
            'entry_execution_price': ledger.entry.execution_price,
            'exit_execution_price': ledger.exit.execution_price,
            'entry_order_type': ledger.entry.liquidity,
            'exit_order_type': ledger.exit.liquidity}
