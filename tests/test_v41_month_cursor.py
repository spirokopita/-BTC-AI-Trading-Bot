import unittest
from research.v41_month_cursor import seed,plan,record,validate,MONTHS
class TestCursor(unittest.TestCase):
    def test_seed(self):
        s=seed();self.assertEqual(len(s["months"]),40);self.assertEqual(plan(s)[0],"2020-03")
        self.assertFalse(set(plan(s)) & set(s["months"]))
    def test_empty(self):
        s=seed();m=plan(s)[0];record(s,m,"OK_DATE_FILTERS_VERIFIED",0,"2026-11-12T00:00:00Z")
        self.assertNotIn(m,plan(s))
    def test_retry(self):
        s=seed();m=plan(s)[0];record(s,m,"HTTP 429",0,"2026-11-12T00:00:00Z")
        self.assertEqual(plan(s)[0],m)
    def test_no_rewrite(self):
        with self.assertRaises(ValueError):record(seed(),"2020-01","OK_DATE_FILTERS_VERIFIED",1,"2026-11-12T00:00:00Z")
    def test_bounds(self):
        with self.assertRaises(ValueError):plan(seed(),13)
        with self.assertRaises(ValueError):validate({"schema":"monthly_cursor_v1","months":{"1900-01":{"status":"complete"}}})
    def test_coverage(self):self.assertEqual(len(MONTHS),82)
if __name__=="__main__":unittest.main()
