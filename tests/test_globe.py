"""Projection and editorial boundary checks for reusable globe animations."""
from pathlib import Path
import math
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'))
sys.path.insert(0,str(ROOT))
from pipeline import core, globe


class GlobeTests(unittest.TestCase):
    def test_target_is_center_and_antipode_hidden(self):
        for lat,lon in [(0,0),(30.4,130.97),(-33.87,151.21),(89.9,-179.9)]:
            x,y,z=globe.project(lat,lon,lat,lon)
            self.assertAlmostEqual(x,0);self.assertAlmostEqual(y,0);self.assertAlmostEqual(z,1)
            self.assertLess(globe.project(-lat,lon+180,lat,lon)[2],0)

    def test_east_and_north_are_not_mirrored(self):
        self.assertGreater(globe.project(0,10,0,0)[0],0)
        self.assertGreater(globe.project(10,0,0,0)[1],0)
        self.assertAlmostEqual(globe.project(0,-179,0,179)[0],math.sin(math.radians(2)))

    def test_invalid_coordinates_and_nonfinite_inputs(self):
        for key,value in [('lat',91),('lon',181),('lat',float('nan')),('lon',True)]:
            with self.subTest(key=key,value=value),self.assertRaises(core.PipelineError):
                globe.validate({'target':{'lat':0,'lon':0,key:value}})

    def test_legacy_character_requests_are_explicitly_rejected(self):
        for old in [{'mode':'mascot'},{'mascot':'missing.svg'},{'score':5},{'show_mascot':False}]:
            with self.subTest(old=old),self.assertRaisesRegex(core.PipelineError,'旧版'):
                globe.validate(old)

    def test_transition_requires_no_character_or_hand_asset(self):
        with patch.object(globe,'ASSETS',ROOT/'does-not-exist'):
            config=globe.validate({'mode':'transition','hand':'missing.svg'})
            intro=globe.validate({'mode':'intro','show_hand':False})
        self.assertNotIn('hand',config);self.assertNotIn('hand',intro)
        self.assertFalse(any('score' in k or 'mascot' in k for k in config))

    def test_local_components_and_output_constraints(self):
        for settings in [{'hand':'https://example.com/hand.svg'},{'width':541},{'mode':'publish'},{'duration':-1}]:
            with self.subTest(settings=settings),self.assertRaises(core.PipelineError):globe.validate(settings)
        self.assertEqual(globe.validate({'width':1080})['height'],1920)

    def test_transient_progress_lock_does_not_fail_the_video(self):
        with patch.object(core,'save_json',side_effect=PermissionError('reader briefly owns file')):
            globe.publish_progress(Path('unused-progress.json'),50)

    def test_clean_frame_never_loads_character_assets(self):
        config=globe.validate({'mode':'transition','width':320})
        with patch.object(globe,'sprite',side_effect=AssertionError('No sprite should load')):
            frame=globe.frame(config,.98)
        self.assertEqual(frame.size,(320,568))
        self.assertEqual(config['schema_version'],2)

    def test_default_animation_draws_no_text_at_any_stage(self):
        for mode in ('intro','transition'):
            config=globe.validate({'mode':mode,'width':320,'show_hand':False})
            self.assertFalse(any(config['text_options'].values()))
            with patch('PIL.ImageDraw.ImageDraw.text',side_effect=AssertionError('Default animation must contain no text')):
                for progress in (0,.5,1):globe.frame(config,progress)

    def test_each_text_layer_can_render_alone(self):
        from PIL import ImageDraw
        original=ImageDraw.ImageDraw.text
        expectations={'title':'地球人日志','subtitle':'EARTH PEOPLE LOG','status':'观察地点已锁定',
                      'location':'只显示详细地址','nearby':'附近测试城市','footer':'观察员值班中'}
        for key,expected in expectations.items():
            with self.subTest(key=key):
                captured=[]
                def capture(draw,xy,text,*args,**kwargs):
                    captured.append(text);return original(draw,xy,text,*args,**kwargs)
                config=globe.validate({'mode':'transition','width':540,'target':{'name':'只显示详细地址',
                    'city_name':'附近测试城市','lat':0,'lon':0},'text_options':{key:True}})
                with patch.object(ImageDraw.ImageDraw,'text',autospec=True,side_effect=capture):globe.frame(config,1)
                self.assertTrue(any(expected in text for text in captured)),captured
                self.assertEqual(len(captured),1,captured)

    def test_malformed_text_options_fail_before_rendering(self):
        for value in (None,[],{'title':'false'},{'unknown':True}):
            with self.subTest(value=value),self.assertRaises(core.PipelineError):globe.validate({'text_options':value})


if __name__=='__main__':unittest.main()
