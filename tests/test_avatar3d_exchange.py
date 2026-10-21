"""交换包失败／取消不发布、源数据保护与完成后损坏检测。"""
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
from avatar3d.backend import Runtime
from avatar3d.contracts import RenderSpec
from avatar3d.models import atomic_json,digest
from avatar3d.motion_exchange import export_exchange,inspect_source,verify_exchange,SOURCE_FILES

TEMP=ROOT/'.runtime/avatar3d-tests';TEMP.mkdir(exist_ok=True)
SAMPLE=ROOT/'avatar3d/assets/Seed-san.vrm'


class ExchangeTests(unittest.TestCase):
    def source(self,root):
        folder=Path(root)/'source';folder.mkdir()
        for name in SOURCE_FILES:(folder/name).write_bytes(name.encode())
        spec=RenderSpec(digest(SAMPLE),action='wave',duration=.5,fps=12)
        atomic_json(folder/'request.json',spec.to_dict())
        atomic_json(folder/'scene-report.json',{'model_sha256':spec.model_sha256,'humanoid_bones':{'hips':'hips'}})
        atomic_json(folder/'complete.json',{'schema':1,'job_id':'source-job',
            'model_sha256':spec.model_sha256,'action':'wave','frames':6,'fps':12,'sample_only':True,
            'files':{name:digest(folder/name) for name in SOURCE_FILES}})
        return folder

    def test_tampered_source_and_parameter_mismatch_rejected_before_child(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            source=self.source(tmp)
            request=json.loads((source/'request.json').read_text(encoding='utf-8'))
            request['fps']=24;atomic_json(source/'request.json',request)
            with self.assertRaises(ValueError):inspect_source(source)
            request['fps']=12;atomic_json(source/'request.json',request)
            (source/'scene.blend').write_bytes(b'tampered')
            with self.assertRaises(ValueError):inspect_source(source)

    def test_cancel_and_existing_destination_preserve_files(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            source=self.source(tmp);target=Path(tmp)/'target';runtime=Runtime.load(ROOT/'.runtime/avatar3d/runtime.json')
            event=threading.Event();event.set()
            with self.assertRaises(InterruptedError):export_exchange(source,SAMPLE,target,runtime,event)
            self.assertFalse(target.exists())
            target.mkdir();(target/'important.txt').write_text('preserve')
            with self.assertRaises(FileExistsError):export_exchange(source,SAMPLE,target,runtime,threading.Event())
            self.assertEqual((target/'important.txt').read_text(),'preserve')

    def test_failed_worker_does_not_publish_marker_or_change_source(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            source=self.source(tmp);target=Path(tmp)/'target';before=digest(source/'scene.blend')
            runtime=Runtime.load(ROOT/'.runtime/avatar3d/runtime.json')
            with patch('avatar3d.motion_exchange.launch_external') as launch:
                launch.return_value.poll.return_value=23;launch.return_value.returncode=23
                with self.assertRaises(RuntimeError):export_exchange(source,SAMPLE,target,runtime,threading.Event())
            self.assertFalse((target/'exchange-complete.json').exists())
            self.assertEqual(digest(source/'scene.blend'),before)

    def test_cancel_terminates_only_the_export_child_and_leaves_no_complete_marker(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            source=self.source(tmp);target=Path(tmp)/'target';event=threading.Event()
            process=Mock();process.poll.return_value=None
            def launch(*args):
                event.set()
                return process
            with patch('avatar3d.motion_exchange.launch_external',side_effect=launch):
                with self.assertRaises(InterruptedError):
                    export_exchange(source,SAMPLE,target,Runtime.load(ROOT/'.runtime/avatar3d/runtime.json'),event)
            process.terminate.assert_called_once();process.wait.assert_called_once_with(10)
            self.assertFalse((target/'exchange-complete.json').exists())

    def test_complete_marker_verifies_every_asset_and_rejects_extra_paths(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            folder=Path(tmp)
            names={'source.blend','character.vrm','animation.fbx','transparent.mov','preview.mp4',
                   'poster.png','model-metadata.json','manifest.json','roundtrip.json','使用说明.txt'}
            for name in names:(folder/name).write_bytes(name.encode())
            record={'schema':1,'files':{name:digest(folder/name) for name in names}}
            atomic_json(folder/'exchange-complete.json',record);verify_exchange(folder)
            (folder/'animation.fbx').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):verify_exchange(folder)
            record['files']['../elsewhere']='a'*64;atomic_json(folder/'exchange-complete.json',record)
            with self.assertRaises(ValueError):verify_exchange(folder)


if __name__=='__main__':unittest.main()
