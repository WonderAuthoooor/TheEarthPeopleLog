"""音频快照、旧任务兼容、损坏阻断及桌面入队链路。"""
from pathlib import Path
import sys,json,tempfile,threading,sqlite3,unittest
from unittest.mock import patch,Mock
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
import numpy as np
from PIL import Image
from avatar3d.audio_mouth import write_wav
from avatar3d.audio_assets import import_audio,load_audio,output_duration
from avatar3d.models import import_model,atomic_json,digest
from avatar3d.contracts import RenderSpec
from avatar3d.service import RenderService
from avatar3d.jobs import Jobs
from avatar3d.browser_preview import prepare
TEMP=ROOT/'.runtime/avatar3d-tests';TEMP.mkdir(exist_ok=True)
SAMPLE=ROOT/'avatar3d/assets/Seed-san.vrm'


class AudioJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=TEMP);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'input.wav'
        write_wav(self.source,np.sin(np.arange(4000)*.15)*.2,.25)

    def test_snapshot_survives_source_deleted_and_reuses_unchanged_assets(self):
        info=import_audio(self.root,self.source)
        self.assertEqual(info,import_audio(self.root,self.source))
        self.source.unlink()
        self.assertEqual(load_audio(self.root,info['source_sha256']),info)
        self.assertEqual(output_duration(info,30),.5)
        (self.root/'audio'/info['source_sha256']/'speech.wav').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'损坏'):load_audio(self.root,info['source_sha256'])

    def test_cancelled_import_publishes_no_asset(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(InterruptedError):import_audio(self.root,self.source,cancel)
        self.assertFalse((self.root/'audio').exists())

    def test_snapshot_publish_retries_transient_windows_lock(self):
        import os
        rename = os.rename
        locked = PermissionError('Windows sharing fixture'); locked.winerror = 5
        count = 0
        def flaky(source, target):
            nonlocal count
            count += 1
            if count < 3:raise locked
            return rename(source, target)
        with patch('avatar3d.audio_assets.os.rename', side_effect=flaky):
            info = import_audio(self.root, self.source)
        self.assertEqual(count, 3)
        self.assertEqual(load_audio(self.root, info['source_sha256']), info)

    def test_snapshot_publish_persistent_denial_is_bounded_and_cancel_does_not_publish(self):
        locked = PermissionError('persistent fixture'); locked.winerror = 5
        cancel = threading.Event()
        with patch('avatar3d.audio_assets.os.rename', side_effect=locked) as rename:
            with self.assertRaises(PermissionError):import_audio(self.root, self.source)
            self.assertEqual(rename.call_count, 5)
        self.assertFalse(list((self.root/'audio').glob('*/complete.json')))
        def cancelled(*_):
            cancel.set();raise locked
        with patch('avatar3d.audio_assets.os.rename', side_effect=cancelled):
            with self.assertRaises(InterruptedError):import_audio(self.root, self.source, cancel)
        self.assertFalse(list((self.root/'audio').glob('*/complete.json')))

    def test_schema1_snapshots_unchanged_schema2_retry_and_downgrade_guard(self):
        old={'schema':1,'model_sha256':'a'*64,'action':'neutral','duration':3,'width':480,'fps':24,'azimuth':0}
        self.assertEqual(RenderSpec.from_dict(old).to_dict(),old)
        jobs=Jobs(self.root)
        first=jobs.add(RenderSpec.from_dict(old))
        self.assertEqual(jobs.matching(RenderSpec.from_dict(old),('queued',)),first)
        audio=RenderSpec('a'*64,'idle',.5,320,30,schema=2,audio_sha256='b'*64,framing='bust')
        ident=jobs.add(audio);jobs.claim(ident);jobs.finish(ident,'cancelled')
        retry=jobs.retry(ident)
        self.assertEqual(jobs.get(retry)['request'],audio.to_dict())
        with closing(sqlite3.connect(jobs.path)) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
        Jobs(self.root)
        with closing(sqlite3.connect(jobs.path)) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
        with self.assertRaises(ValueError):RenderSpec('a'*64,audio_sha256='b'*64).validate()

    def make_job(self,backend):
        model=import_model(self.root,SAMPLE)
        audio=import_audio(self.root,self.source)
        self.source.unlink()
        service=RenderService(self.root,backend)
        spec=RenderSpec(model['sha256'],'idle',output_duration(audio,30),320,30,
                        schema=2,audio_sha256=audio['source_sha256'],framing='bust')
        return service,service.jobs.add(spec),audio

    def test_real_codec_audio_job_preview_and_hashes(self):
        backend=Mock()
        def render(request,folder,cancel,progress):
            self.assertEqual(request['framing'],'bust')
            self.assertTrue(Path(request['mouth_track']).is_file())
            atomic_json(folder/'mouth-pose-checks.json',[{'aa':.2}])
            (folder/'scene.blend').write_bytes(b'synthetic backend fixture')
            files=[]
            for i in range(15):
                path=folder/f'{i:05}.png'
                image=Image.new('RGBA',(64,96));image.paste((90+i*5,160,180,255),(10,10,55,90));image.save(path);files.append(path)
            return files
        backend.render.side_effect=render
        service,ident,audio=self.make_job(backend)
        folder=service.run(ident,threading.Event())
        self.assertEqual(service.completed_folder(ident),folder)
        record=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
        self.assertEqual(record['audio_sha256'],audio['source_sha256'])
        page=prepare(folder)
        html=page.read_text(encoding='utf-8')
        self.assertIn('../有声预览.webm',html);self.assertNotIn('loop muted',html)
        self.assertIn('备用动画无声',html)
        (folder/'口播.wav').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):service.completed_folder(ident)
        with self.assertRaises(ValueError):prepare(folder)

    def test_bad_snapshot_blocked_before_backend_and_retry_preserves_audio_id(self):
        backend=Mock();service,ident,audio=self.make_job(backend)
        asset=self.root/'audio'/audio['source_sha256']/'mouth-track.json';asset.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):service.run(ident,threading.Event())
        backend.render.assert_not_called()
        self.assertEqual(service.jobs.get(ident)['status'],'failed')
        self.assertFalse((self.root/'jobs'/ident/'complete.json').exists())
        retry=service.jobs.retry(ident)
        self.assertEqual(service.jobs.get(retry)['request']['audio_sha256'],audio['source_sha256'])

    def test_audio_cancel_during_render_is_recoverable(self):
        backend=Mock();backend.render.side_effect=InterruptedError('cancel fixture')
        service,ident,audio=self.make_job(backend)
        with self.assertRaises(InterruptedError):service.run(ident,threading.Event())
        self.assertEqual(service.jobs.get(ident)['status'],'cancelled')
        self.assertFalse((self.root/'jobs'/ident/'complete.json').exists())
        self.assertEqual(load_audio(self.root,audio['source_sha256']),audio)


class AudioUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_audio_select_export_fps_change_clear_and_old_preview(self):
        from avatar3d.app import Window
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            root=Path(tmp);source=root/'input.wav';write_wav(source,np.zeros(8000),.5)
            info=import_audio(root,source)
            window=Window(root,ROOT/'.runtime/avatar3d/runtime.json',SAMPLE)
            try:
                window.demo.click();self.assertEqual(len(window.service.jobs.list()),1)
                window.audio_finished(info,'')
                self.assertFalse(window.duration.isEnabled())
                self.assertEqual(window.action.currentData(),'idle')
                window.export.click();job=window.service.jobs.get(window.service.jobs.list()[0]['id'])
                self.assertEqual(job['request']['audio_sha256'],info['source_sha256'])
                self.assertEqual(job['request']['duration'],output_duration(info,30))
                window.fps.setCurrentIndex(window.fps.findData(24));window.export.click()
                job2=window.service.jobs.get(window.service.jobs.list()[0]['id'])
                self.assertEqual(job2['request']['duration'],output_duration(info,24))
                window.preview.click();preview=window.service.jobs.get(window.service.jobs.list()[0]['id'])
                self.assertIsNone(preview['request'].get('audio_sha256'))
                window.audio_clear.click();self.assertTrue(window.duration.isEnabled())
                self.assertEqual(window.service.jobs.get(job['id'])['request'],job['request'])
                source.unlink()
            finally:window.close()


if __name__=='__main__':unittest.main()
