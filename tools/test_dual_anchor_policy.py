import unittest
import numpy as np
from dual_anchor_policy import simulate
def v(deg):
    t=np.deg2rad(deg)
    return np.array([np.cos(t),np.sin(t),0.0])
def profile(name,truth,first,last):
    a=v(first);b=v(last);m=a+b;m=m/np.linalg.norm(m)
    return {"local":name,"truth":truth,"valid":"PASS" if float(a@b)>=.84 else "AGREEMENT_REJECT","v":m,"early":a,"late":b}
class DualAnchorTests(unittest.TestCase):
    def test_rescue_does_not_enroll_or_adapt(self):
        clips=[{"id":"seed","profiles":[profile("a","A",0,0)]}]
        clips += [{"id":str(i),"profiles":[profile("r","A",30,-20)]} for i in range(40)]
        clips += [{"id":"edge","profiles":[profile("e","A",-30,-30)]}]
        m,e=simulate(clips,np)
        self.assertEqual(m["global_ids"],1)
        self.assertEqual(m["rescued_assignments"],40)
        self.assertEqual(e[-1]["id"],"Speaker 1")
    def test_one_bad_half_cannot_hide_in_average(self):
        m,e=simulate([{"id":"seed","profiles":[profile("a","A",0,0)]},
            {"id":"bad","profiles":[profile("r","MIX",0,50)]}],np)
        self.assertIsNone(e[-1]["id"])
    def test_speaker_switch_rejected(self):
        m,e=simulate([{"id":"seed","profiles":[profile("a","A",0,0),profile("b","B",90,90)]},
            {"id":"switch","profiles":[profile("m","MIX",0,90)]}],np)
        self.assertIsNone(e[-1]["id"])
    def test_collision_blocks_both(self):
        m,e=simulate([{"id":"seed","profiles":[profile("a","A",0,0)]},
            {"id":"clash","profiles":[profile("r","A",30,-20),profile("s","A",30,-20)]}],np)
        self.assertTrue(all(x["id"] is None for x in e[-2:]))
        self.assertEqual(m["collisions"],2)
    def test_no_anchor_means_no_enrollment(self):
        m,e=simulate([{"id":"empty","profiles":[profile("r","A",30,-20)]}],np)
        self.assertEqual(m["global_ids"],0)
        self.assertIsNone(e[0]["id"])
if __name__=="__main__":unittest.main()
