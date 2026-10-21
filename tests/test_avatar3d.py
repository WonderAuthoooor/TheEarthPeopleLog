"""三维工作流的输入边界、不可变任务、失败恢复和真实编码。"""
from pathlib import Path
import sys,json,struct,tempfile,threading,unittest
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
from avatar3d.models import import_model,inspect_vrm,digest
from avatar3d.contracts import RenderSpec
from avatar3d.jobs import Jobs
from avatar3d.service import RenderService,encode
from avatar3d.motion import arm_targets
from PIL import Image

TEMP=ROOT/'.runtime/avatar3d-tests';TEMP.mkdir(exist_ok=True)
SAMPLE=ROOT/'avatar3d/assets/Seed-san.vrm'

class ThreeDTests(unittest.TestCase):
    def test_vrm_content_addressed_import_and_source_preserved(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            before=digest(SAMPLE);a=import_model(tmp,SAMPLE);b=import_model(tmp,SAMPLE)
            self.assertEqual(a,b);self.assertEqual(before,digest(SAMPLE))
            self.assertEqual(len(list((Path(tmp)/'models').glob('*.vrm'))),1)
            self.assertEqual(a['vrm_version'],'1.0');self.assertIn('rightHand',a['bones'])
            target=Path(tmp)/'models'/(a['sha256']+'.vrm');target.write_bytes(b'corrupted')
            with self.assertRaises(ValueError):import_model(tmp,SAMPLE)
            self.assertEqual(target.read_bytes(),b'corrupted')

    def test_bad_glb_external_resources_and_bones_rejected(self):
        original=SAMPLE.read_bytes();length=struct.unpack_from('<I',original,12)[0];doc=json.loads(original[20:20+length])
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            path=Path(tmp)/'model.vrm'
            for mutation in ('external','bone'):
                changed=json.loads(json.dumps(doc))
                if mutation=='external':changed['images'][0]['uri']='../../outside.png'
                else:changed['extensions']['VRMC_vrm']['humanoid']['humanBones'].pop('head')
                payload=json.dumps(changed).encode();payload+=b' '*((-len(payload))%4)
                path.write_bytes(struct.pack('<4sIIII',b'glTF',2,len(payload)+20,len(payload),0x4E4F534A)+payload)
                with self.assertRaises(ValueError):inspect_vrm(path)
            path.write_bytes(original[:19])
            with self.assertRaises(ValueError):inspect_vrm(path)

    def test_contract_rejects_nonfinite_unknown_and_future(self):
        for kwargs in ({'duration':float('nan')},{'duration':100},{'action':'missing'},{'schema':99},{'azimuth':float('inf')},{'width':999}):
            with self.assertRaises(ValueError):RenderSpec('a'*64,**kwargs).validate()

    def test_claim_once_recover_preserves_old_request_retry_new_id(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            jobs=Jobs(tmp);spec=RenderSpec('a'*64,action='wave');ident=jobs.add(spec)
            jobs.claim(ident)
            with self.assertRaises(ValueError):jobs.claim(ident)
            self.assertEqual(Jobs(tmp).recover(),1)
            self.assertEqual(jobs.get(ident)['status'],'interrupted')
            retried=jobs.retry(ident);self.assertNotEqual(ident,retried)
            self.assertEqual(jobs.get(retried)['request'],spec.to_dict())

    def test_queue_oldest_job_cannot_be_hidden_by_history_limit(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            jobs=Jobs(tmp);first=jobs.add(RenderSpec('a'*64))
            for i in range(105):jobs.add(RenderSpec('a'*64))
            self.assertEqual(len(jobs.list()),100);self.assertEqual(jobs.next_queued(),first)

    def test_backend_failure_and_cancel_never_publish_complete(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            info=import_model(tmp,SAMPLE);backend=Mock();backend.render.side_effect=RuntimeError('GPU failure')
            service=RenderService(tmp,backend)
            ident=service.jobs.add(RenderSpec(info['sha256']))
            with self.assertRaises(RuntimeError):service.run(ident,threading.Event())
            self.assertEqual(service.jobs.get(ident)['status'],'failed')
            self.assertFalse((Path(tmp)/'jobs'/ident/'complete.json').exists())
            with self.assertRaises(ValueError):service.completed_folder(ident)
            cancelled=service.jobs.retry(ident);event=threading.Event();event.set()
            with self.assertRaises(InterruptedError):service.run(cancelled,event)
            self.assertEqual(service.jobs.get(cancelled)['status'],'cancelled')

    def test_altered_model_not_sent_to_renderer(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            info=import_model(tmp,SAMPLE);backend=Mock();service=RenderService(tmp,backend)
            ident=service.jobs.add(RenderSpec(info['sha256']))
            (Path(tmp)/'models'/(info['sha256']+'.vrm')).write_bytes(b'changed')
            with self.assertRaises(ValueError):service.run(ident,threading.Event())
            backend.render.assert_not_called()

    def test_pose_boundaries_and_wave_motion(self):
        for side,sign in (('left',1),('right',-1)):
            self.assertEqual(arm_targets('wave',0,3,side,sign),arm_targets('neutral',0,3,side,sign))
            self.assertEqual(arm_targets('wave',3,3,side,sign),arm_targets('neutral',3,3,side,sign))
        self.assertNotEqual(arm_targets('wave',1,3,'right',-1),arm_targets('wave',1.2,3,'right',-1))

    def test_real_encoded_alpha_frames_and_cancel(self):
        import av
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            folder=Path(tmp);files=[]
            for i in range(6):
                image=Image.new('RGBA',(320,480));image.paste((70+i*20,150,120,255),(80,100,240,400))
                p=folder/f'{i:05}.png';image.save(p);files.append(p)
            encode(files,folder,12,threading.Event(),lambda _:None)
            with av.open(str(folder/'角色透明.mov')) as c:
                frames=list(c.decode(video=0));self.assertEqual(len(frames),6)
                alpha=frames[0].to_ndarray(format='rgba')[:,:,3]
                self.assertEqual(int(alpha[0,0]),0);self.assertGreater(int(alpha[200,160]),245)
            cancel=threading.Event();cancel.set()
            with self.assertRaises(InterruptedError):encode(files,folder,12,cancel,lambda _:None)

    def test_external_child_environment_does_not_inherit_python_paths(self):
        from unittest.mock import patch
        from avatar3d.backend import launch_external
        env={'PYTHONHOME':'other-python','PYTHONPATH':'other-modules','_PYI_ARCHIVE_FILE':'old','KEEP':'value'}
        with patch('avatar3d.backend.subprocess.Popen') as popen:
            launch_external(['blender'],env,None)
            child=popen.call_args.kwargs['env']
            self.assertEqual(child,{'KEEP':'value'})
            self.assertIn('PYTHONPATH',env)

if __name__=='__main__':unittest.main()
