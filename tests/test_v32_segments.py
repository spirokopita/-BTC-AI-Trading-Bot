import unittest
from research.v32_segments import segments
from research.kraken_archive import STEP

class SegmentIsolation(unittest.TestCase):
    def bars(self, lengths):
        t=0; out=[]
        for n in lengths:
            for _ in range(n):
                out.append((t,100.,101.,99.,100.,1.));t+=STEP
            t+=STEP*2
        return out
    def test_no_cross_gap(self):
        self.assertEqual([(b-a) for a,b in segments(self.bars([1000,999,1200]))],[1000,1200])
    def test_no_performance_selection(self):
        a=self.bars([1200,1300])
        self.assertEqual(segments(a),[(0,1200),(1200,2500)])
        modified=[(x[0],x[1],x[2],x[3],x[4]*2,x[5]) for x in a]
        self.assertEqual(segments(a),segments(modified))
    def test_reject_duplicates(self):
        a=self.bars([1001]);a[3]=(a[2][0],)+a[3][1:]
        with self.assertRaises(ValueError):segments(a)
    def test_minimum(self):
        with self.assertRaises(ValueError):segments([],0)
if __name__=="__main__":unittest.main()
