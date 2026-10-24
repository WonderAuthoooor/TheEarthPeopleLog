from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
import numpy as np
from avatar3d.audio_mouth import envelope,at,validate_track,decode,write_wav,RATE

spec=importlib.util.spec_from_file_location('review_audio',ROOT/'scripts/review-audio-mouth.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
TEMP=ROOT/'.runtime/avatar3d-tests';TEMP.mkdir(exist_ok=True)


class AudioMouthTests(unittest.TestCase):
    def fake_model(self, conflict=False, missing=False):
        mouth=SimpleNamespace(name='mouth',value=0.,keyframe_insert=Mock())
        blink=SimpleNamespace(name='blink',value=.8,keyframe_insert=Mock())
        keys={'mouth':mouth,'blink':blink}
        obj=SimpleNamespace(name='face',data=SimpleNamespace(shape_keys=SimpleNamespace(key_blocks=keys)))
        def bind(name):return SimpleNamespace(node=SimpleNamespace(mesh_object_name='face'),index=name,weight=1.)
        expressions={'aa':SimpleNamespace(morph_target_binds=[] if missing else [bind('mouth')]),
                     'blink':SimpleNamespace(morph_target_binds=[bind('mouth' if conflict else 'blink')])}
        extension=SimpleNamespace(is_vrm1=lambda:True,vrm1=SimpleNamespace(expressions=
                                  SimpleNamespace(all_name_to_expression_dict=lambda:expressions)))
        return SimpleNamespace(data=SimpleNamespace(vrm_addon_extension=extension)),keys,SimpleNamespace(data=SimpleNamespace(objects={'face':obj}))

    def test_mouth_binding_preserves_blink_and_records_frames(self):
        from avatar3d.mouth_pose import MouthPose
        arm,keys,bpy=self.fake_model()
        track=envelope(np.sin(np.arange(RATE)*.12)*.2)
        with patch.dict(sys.modules,{'bpy':bpy}):
            pose=MouthPose(arm,track);value=pose.apply(.3,10)
        self.assertEqual(keys['blink'].value,.8)
        self.assertEqual(keys['mouth'].value,value)
        keys['mouth'].keyframe_insert.assert_called_once_with('value',frame=10)

    def test_missing_or_conflicting_bindings_fail_explicitly(self):
        from avatar3d.mouth_pose import MouthPose
        for options in ({'missing':True},{'conflict':True}):
            arm,_,bpy=self.fake_model(**options)
            with patch.dict(sys.modules,{'bpy':bpy}):
                with self.assertRaises(ValueError):MouthPose(arm,envelope(np.zeros(RATE)))

    def test_silence_and_low_noise_close_mouth(self):
        for data in (np.zeros(RATE),np.full(RATE,.002)):
            track=validate_track(envelope(data))
            self.assertEqual(max(track['values']),0)

    def test_speech_pauses_release_and_random_access(self):
        data=np.zeros(RATE*2)
        data[4000:10000]=.2*np.sin(np.arange(6000)*.12)
        data[20000:26000]=.1*np.sin(np.arange(6000)*.19)
        track=validate_track(envelope(data))
        self.assertGreater(at(track,.4),.4)
        self.assertLess(at(track,.95),.002)
        self.assertLess(max(abs(a-b) for a,b in zip(track['values'],track['values'][1:])),.3)
        values=[at(track,t) for t in (.4,1.4,.95,0,3)]
        self.assertEqual(values,[at(track,t) for t in (.4,1.4,.95,0,3)])
        self.assertEqual(at(track,track['times'][-1]),0)

    def test_nonfinite_and_invalid_track_rejected(self):
        for data in ([],[float('nan')],[float('inf')]):
            with self.assertRaises(ValueError):envelope(data)
        valid=envelope(np.zeros(4000))
        for mutation in ('order','nan','weight','revision'):
            track=json.loads(json.dumps(valid))
            if mutation=='order':track['times'][2]=0
            if mutation=='nan':track['values'][1]=float('nan')
            if mutation=='weight':track['values'][1]=2
            if mutation=='revision':track['revision']='future'
            with self.assertRaises(ValueError):validate_track(track)

    def test_decode_resample_padding_and_cancel(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            source=Path(tmp)/'input.wav'
            pcm=(np.sin(np.arange(44100)*.2)*12000).astype('<i2')
            with wave.open(str(source),'wb') as output:
                output.setnchannels(1);output.setsampwidth(2);output.setframerate(44100);output.writeframes(pcm.tobytes())
            decoded=decode(source,threading.Event())
            self.assertEqual(len(decoded),RATE)
            target=Path(tmp)/'output.wav';write_wav(target,decoded,1.25)
            with wave.open(str(target),'rb') as result:
                self.assertEqual(result.getnframes(),20000)
                tail=np.frombuffer(result.readframes(20000),dtype='<i2')[-4000:]
                self.assertEqual(np.count_nonzero(tail),0)
            cancel=threading.Event();cancel.set()
            with self.assertRaises(InterruptedError):decode(source,cancel)

    def test_long_audio_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            source=Path(tmp)/'long.wav';write_wav(source,np.zeros(RATE*30),30)
            with self.assertRaises(ValueError):decode(source,threading.Event())
            with self.assertRaises(FileExistsError):review.run('missing','missing',tmp,'missing')
            self.assertTrue(source.exists())

    def test_mux_real_audio_video_timing(self):
        from PIL import Image
        from avatar3d.service import encode
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            folder=Path(tmp);files=[]
            for i in range(12):
                image=Image.new('RGBA',(64,96),(0,0,0,0))
                for x in range(10,50):
                    for y in range(15,80):image.putpixel((x,y),(200,i*15,50,255))
                path=folder/f'{i:03}.png';image.save(path);files.append(path)
            cancel=threading.Event();encode(files,folder,24,cancel,lambda _:None)
            write_wav(folder/'口播.wav',np.sin(np.arange(8000)*.12)*.1,.5)
            review.sound_previews(folder,24,12,cancel)
            self.assertTrue((folder/'有声预览.webm').is_file())


if __name__=='__main__':unittest.main()
