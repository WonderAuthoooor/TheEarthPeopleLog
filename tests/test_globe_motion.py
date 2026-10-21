"""Motion behavior and geographic endpoints for the original retro globe."""
from pathlib import Path
import sys,unittest,math
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'));sys.path.insert(0,str(ROOT))
from pipeline import globe
from pipeline.globe_motion import pose

class RetroMotionTests(unittest.TestCase):
    def config(self,mode='transition',**values):
        return globe.validate({'mode':mode,'style':'rubberhose','width':320,'show_hand':False,
             'origin':{'name':'A','lat':51.5,'lon':179},'target':{'name':'B','lat':35.7,'lon':-179},**values})

    def test_pull_out_then_push_in_and_stable_hold(self):
        c=self.config();start,middle,end=[pose(c,p) for p in (0,.25,1)]
        self.assertGreater(start['zoom'],middle['zoom']);self.assertGreater(end['zoom'],middle['zoom'])
        for p in (.92,.97,1):
            m=pose(c,p);self.assertAlmostEqual(m['lat'],c['target']['lat']);self.assertAlmostEqual(m['lon'],c['target']['lon'])
            self.assertEqual((m['sx'],m['sy'],m['roll'],m['smear'],m['hand']),(1.,1.,0.,0.,0.))

    def test_transition_uses_short_route_across_dateline(self):
        c=self.config();previous=pose(c,0)['lon'];travel=0
        for i in range(1,201):
            lon=pose(c,i/200)['lon'];travel+=(lon-previous+180)%360-180;previous=lon
        self.assertAlmostEqual(travel,2)

    def test_intro_has_multiple_spins_and_contact_deformation(self):
        c=self.config('intro');previous=pose(c,0)['lon'];travel=0
        for i in range(1,401):
            lon=pose(c,i/400)['lon'];travel+=(lon-previous+180)%360-180;previous=lon
        self.assertGreater(travel,1000);contact=pose(c,.1)
        self.assertGreater(contact['sx'],1.15);self.assertLess(contact['sy'],.9)
        self.assertGreater(pose(c,.3)['smear'],.5)

    def test_final_intro_matches_next_transition_first_frame(self):
        first=self.config('intro');next_clip=self.config(origin=first['target'],target={'name':'C','lat':-33.9,'lon':151.2})
        self.assertEqual(globe.frame(first,1).tobytes(),globe.frame(next_clip,0).tobytes())

    def test_retro_has_no_text_and_classic_remains_available(self):
        for mode in ('intro','transition'):
            c=self.config(mode)
            with patch('PIL.ImageDraw.ImageDraw.text',side_effect=AssertionError('No default text')):
                for p in (0,.1,.3,.7,1):globe.frame(c,p)
        retro=globe.frame(self.config(),.25)
        classic=globe.frame(self.config(style='classic'),.25)
        self.assertNotEqual(retro.tobytes(),classic.tobytes())

    def test_bundled_hand_rebases_after_upgrade(self):
        c=globe.validate({'style':'rubberhose','hand':str(ROOT/'missing-old-version/_internal/pipeline/assets/hands/robot.svg')})
        self.assertEqual(Path(c['hand']),globe.ASSETS/'hands/robot.svg')
        self.assertEqual(Path(globe.validate({'style':'rubberhose'})['hand']).name,'rubber_glove.svg')

    def test_invalid_style_and_finite_camera_for_extreme_locations(self):
        with self.assertRaises(Exception):globe.validate({'style':'unknown'})
        for lat,lon in ((90,180),(-90,-180),(0,0)):
            c=self.config(target={'name':'edge','lat':lat,'lon':lon})
            for p in (0,.1,.25,.6,1):
                m=pose(c,p)
                self.assertTrue(all(math.isfinite(m[k]) for k in ('lat','lon','zoom','sx','sy','roll')))
