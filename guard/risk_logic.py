"""Risk decisions independent of the predictive strategy and exchange keys."""
from datetime import datetime, timezone
from math import isfinite


def risk_decision(state: dict, equity: float, starting_capital: float,
                  now: datetime | None = None):
    """Update persistent state; latch *forever* on breach until operator resets.

    Daily limit: 2% of start-of-UTC-day equity.
    Global trailing drawdown: 5% from highest observed account equity.
    Also check 10% loss vs original capital.
    Note: a snapshot monitor cannot eliminate between-poll price gaps.
    """
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(timezone.utc).date().isoformat()
    if not isfinite(equity) or not isfinite(starting_capital) or equity <= 0 or starting_capital <= 0:
        return {**state, 'locked': True, 'reason': 'invalid account equity'}
    state = dict(state)
    if not state:
        state = {'initial_equity': equity, 'peak_equity': equity,
                 'daily_equity': equity, 'day_utc': day,
                 'locked': False, 'reason': ''}
    if state.get('locked'):
        return state
    if day != state['day_utc']:
        state['day_utc'] = day
        state['daily_equity'] = equity
    state['peak_equity'] = max(state['peak_equity'], equity)
    breaches = [
        (equity <= state['daily_equity'] * 0.98, 'daily equity loss >=2%'),
        (equity <= state['peak_equity'] * 0.95, 'peak-to-trough drawdown >=5%'),
        (equity <= starting_capital * 0.90, 'total loss >=10% of initial capital'),
    ]
    for triggered, reason in breaches:
        if triggered:
            state['locked'] = True
            state['reason'] = reason
            break
    return state
