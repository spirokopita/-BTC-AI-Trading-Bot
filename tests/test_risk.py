import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guard'))
from risk_logic import risk_decision


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)

    def test_empty_state_is_initialised(self):
        s = risk_decision({}, 1000, 1000, self.now)
        self.assertFalse(s['locked'])
        self.assertEqual(s['peak_equity'], 1000)

    def test_daily_loss_latches(self):
        s = risk_decision({}, 1000, 1000, self.now)
        s = risk_decision(s, 979, 1000, self.now)
        self.assertTrue(s['locked'])
        s = risk_decision(s, 1200, 1000, self.now + timedelta(days=1))
        self.assertTrue(s['locked'])

    def test_trailing_drawdown(self):
        s = risk_decision({}, 1000, 1000, self.now)
        s = risk_decision(s, 1100, 1000, self.now + timedelta(days=1))
        # Next UTC day, 6% below the peak; triggers trailing drawdown.
        s = risk_decision(s, 1034, 1000, self.now + timedelta(days=2))
        self.assertTrue(s['locked'])

    def test_new_utc_day_resets_daily_baseline(self):
        s = risk_decision({}, 1000, 1000, self.now)
        s = risk_decision(s, 995, 1000, self.now + timedelta(days=1))
        self.assertFalse(s['locked'])
        self.assertEqual(s['daily_equity'], 995)

    def test_bad_equity_latches(self):
        self.assertTrue(risk_decision({}, float('nan'), 1000, self.now)['locked'])

if __name__ == '__main__':
    unittest.main()
