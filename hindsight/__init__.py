"""Offline, fee-aware hindsight diagnostics; never a live/causal trading signal."""
from .analysis import (HindsightParameters, chronological_folds, analyze_hindsight,
                       simulate_hindsight_trade)
__all__ = ['HindsightParameters','chronological_folds','analyze_hindsight','simulate_hindsight_trade']
