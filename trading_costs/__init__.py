"""Shared, paper-only price execution and exchange-cost arithmetic."""
from .model import (
    FeeTier, FeeSettings, Execution, TradeLedger, load_settings,
    estimate_execution, settle_trade, quantity_for_quote_budget,
    minimum_break_even_move, expected_trade_edge, ledger_to_log,
)
