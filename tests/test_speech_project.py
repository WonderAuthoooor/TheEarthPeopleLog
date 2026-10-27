"""分段改稿、增量渲染、重排时轴及中断恢复；不把夹具当真实3D渲染。"""
from pathlib import Path
import copy
import json
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.runtime/python'), str(ROOT)]
import numpy as np
from avatar3d.audio_mouth import write_wav
from avatar3d.jobs import Jobs
from avatar3d.models import atomic_json
from avatar3d.speech_project import create, bind_audio, plan, render_project, validate


class SpeechTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT/'.runtime/avatar3d-tests'; scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root/'a.wav'; self.b = self.root/'b.wav'
        write_wav(self.a, np.sin(np.arange(4000)*.15)*.2, .25)
        write_wav(self.b, np.sin(np.arange(8000)*.18)*.2, .5)
        self.project = create('a'*64, '第一段。\n\n第二段。', 320, 30)
        self.ids = [s['id'] for s in self.project['segments']]
        self.project = bind_audio(self.project, self.ids[0], self.root, self.a)
        self.project = bind_audio(self.project, self.ids[1], self.root, self.b)
        self.file = self.root/'project.json'; atomic_json(self.file, self.project)
        self.calls = []
        self.service = Mock(workspace=self.root, jobs=Jobs(self.root))
        self.service.run.side_effect = self.fake_render
        self.service.completed_folder.side_effect = self.completed

    def fake_render(self, ident, cancel, progress=lambda _:None):
        self.service.jobs.claim(ident)
        self.calls.append(ident)
        folder = self.root/'jobs'/ident; folder.mkdir(parents=True)
        (folder/'ok').write_text('complete')
        self.service.jobs.finish(ident, 'complete')
        return folder

    def completed(self, ident):
        folder = self.root/'jobs'/ident
        if (folder/'ok').read_text() != 'complete':raise ValueError('损坏')
        return folder

    def run_project(self, engine='fixture-v1', cancel=None):
        atomic_json(self.file, self.project)
        output = render_project(self.file, self.service, engine, cancel)
        return output, json.loads((output/'complete.json').read_text(encoding='utf-8'))

    def test_changed_text_blocks_render_until_rebound(self):
        self.project['segments'][0]['text'] = '新的第一段。'
        p = plan(self.project, self.root)
        self.assertFalse(p['ready']); self.assertEqual(p['segments'][0]['status'], 'stale_audio')
        self.assertIsNone(p['segments'][1]['start_frame'])
        with self.assertRaisesRegex(ValueError, '配音'):self.run_project()
        self.assertFalse(self.calls)
        self.project = bind_audio(self.project, self.ids[0], self.root, self.b)
        self.assertTrue(plan(self.project, self.root)['ready'])

    def test_identical_render_reuses_then_audio_change_only_redoes_one(self):
        _, first = self.run_project()
        self.assertEqual(len(self.calls), 2)
        _, second = self.run_project()
        self.assertTrue(all(s['reused'] for s in second['segments']))
        self.project = bind_audio(self.project, self.ids[0], self.root, self.b)
        self.project['segments'][0]['action'] = 'explain'
        _, third = self.run_project()
        self.assertEqual(len(self.calls), 3)
        self.assertNotEqual(first['segments'][0]['job_id'], third['segments'][0]['job_id'])
        self.assertEqual(first['segments'][1]['job_id'], third['segments'][1]['job_id'])
        self.assertEqual(third['segments'][1]['start_frame'], 21)

    def test_reorder_preserves_jobs_but_rebuilds_frame_timeline_and_srt(self):
        _, first = self.run_project()
        self.project['segments'].reverse()
        output, second = self.run_project()
        self.assertEqual(second['segments'][0]['job_id'], first['segments'][1]['job_id'])
        self.assertEqual(second['segments'][1]['start_frame'], 21)
        self.assertEqual(len(self.calls), 2)
        srt = (output/'段落字幕草稿.srt').read_text(encoding='utf-8-sig')
        self.assertIn('00:00:00,000 --> 00:00:00,500\n第二段。', srt)
        self.assertIn('00:00:00,700 --> 00:00:00,950\n第一段。', srt)

    def test_engine_change_invalidates_all(self):
        self.run_project(); self.run_project(engine='fixture-v2')
        self.assertEqual(len(self.calls), 4)

    def test_broken_completed_output_regenerates_only_bad_segment(self):
        _, first = self.run_project()
        (Path(first['segments'][1]['folder'])/'ok').write_text('corrupt')
        _, second = self.run_project()
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(second['segments'][0]['reused']); self.assertFalse(second['segments'][1]['reused'])

    def test_cancel_after_first_segment_leaves_no_complete_and_resumes(self):
        cancel = threading.Event()
        def partial(ident, event, progress=lambda _:None):
            output = self.fake_render(ident, event); cancel.set(); return output
        self.service.run.side_effect = partial
        with self.assertRaises(InterruptedError):self.run_project(cancel=cancel)
        run = next((self.root/'runs').iterdir())
        self.assertTrue((run/'error.json').exists()); self.assertFalse((run/'complete.json').exists())
        self.service.run.side_effect = self.fake_render
        _, final = self.run_project()
        self.assertEqual(len(self.calls), 2); self.assertTrue(final['segments'][0]['reused'])

    def test_audio_deleted_or_corrupt_and_duplicate_ids_rejected(self):
        self.a.unlink(); self.b.unlink()
        self.assertTrue(plan(self.project, self.root)['ready'])
        asset = self.root/'audio'/self.project['segments'][0]['audio']['sha256']/'speech.wav'
        asset.write_bytes(b'broken')
        self.assertEqual(plan(self.project, self.root)['segments'][0]['status'], 'invalid_audio')
        duplicate = copy.deepcopy(self.project); duplicate['segments'][1]['id'] = self.ids[0]
        with self.assertRaises(ValueError):validate(duplicate)

    def test_preview_escapes_text_and_new_order_keeps_old_revision(self):
        self.project['segments'][0]['text'] = '<script>alert(1)</script>'
        self.project = bind_audio(self.project, self.ids[0], self.root, self.a)
        output, first = self.run_project()
        page = (output/'预览.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>', page); self.assertIn('&lt;script&gt;', page)
        self.project['segments'].reverse(); self.run_project()
        original = json.loads((output/'plan.json').read_text(encoding='utf-8'))
        self.assertEqual(original['segments'][0]['id'], self.ids[0])


if __name__ == '__main__':unittest.main()
