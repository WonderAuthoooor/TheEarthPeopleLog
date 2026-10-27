"""真实Qt控件的编辑/恢复/线程互斥；渲染像素另由集成样片检查。"""
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
from PySide6.QtWidgets import QApplication
import numpy as np
from avatar3d.app import Window
from avatar3d.audio_mouth import write_wav
from avatar3d.models import atomic_json
from avatar3d import speech_project as speech


class SpeechUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        temp=ROOT/'.runtime/avatar3d-tests'; temp.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=temp); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.dispatch=patch.object(Window,'dispatch'); self.dispatch.start(); self.addCleanup(self.dispatch.stop)
        self.window=Window(self.root,ROOT/'.runtime/avatar3d/runtime.json',ROOT/'avatar3d/assets/Seed-san.vrm')
        self.addCleanup(lambda:self.window.close())
        self.window.demo.click(); self.panel=self.window.speech
        self.window.tabs.setCurrentIndex(1); self.panel.new_button.click()
        self.source=self.root/'tone.wav'; write_wav(self.source,np.sin(np.arange(4000)*.15)*.2,.25)

    def wait(self):
        deadline=time.monotonic()+15
        while self.panel.busy and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.01)
        self.assertFalse(self.panel.busy,self.panel.status.text())

    def test_edit_save_reorder_remove_restart_preserve_ids(self):
        p=self.panel;p.text.setPlainText('第一段'); first=p.selected()['id']
        p.add_button.click();p.text.setPlainText('第二段'); second=p.selected()['id']
        p.up_button.click();p.save_button.click()
        disk=json.loads(p.path.read_text(encoding='utf-8'))
        self.assertEqual([s['id'] for s in disk['segments']],[second,first])
        path=p.path;self.window.close()
        self.window=Window(self.root,ROOT/'.runtime/avatar3d/runtime.json',ROOT/'avatar3d/assets/Seed-san.vrm')
        self.panel=self.window.speech;p=self.panel
        self.assertEqual(p.path,path);self.assertEqual(p.selected()['text'],'第二段')
        p.remove_button.click();p.save()
        self.assertEqual(p.selected()['id'],first)
        self.assertTrue(list((path.parent/'revisions').glob('*.json')))

    def test_audio_binding_worker_freezes_editing_and_text_change_marks_stale(self):
        p=self.panel;p.text.setPlainText('口播测试');p.bind_path(self.source)
        self.assertTrue(p.busy);self.assertFalse(p.edit_area.isEnabled());self.assertFalse(self.window.tabs.isTabEnabled(0))
        self.wait();self.assertIn('已绑定',p.audio_label.text())
        p.text.setPlainText('修改口播');self.assertIn('已过期',p.audio_label.text());self.assertTrue(p.save())
        self.assertFalse(speech.plan(p.document,self.root)['ready'])
        self.assertTrue(self.window.tabs.isTabEnabled(0))

    def test_empty_other_draft_does_not_block_binding_selected_segment(self):
        p=self.panel;p.add_button.click();p.text.setPlainText('第二段先配音');p.bind_path(self.source);self.wait()
        self.assertIn('已绑定',p.audio_label.text());self.assertEqual(p.document['segments'][0]['text'],'')
        with patch('avatar3d.speech_ui.speech.engine_signature',return_value='test'),patch('avatar3d.speech_ui.speech.render_project',side_effect=ValueError('fixture stop')) as render:
            p.render_one.click();self.wait()
            self.assertEqual(render.call_args.kwargs['segment_ids'],[p.selected()['id']])

    def test_conflicting_disk_edit_preserved_and_save_copy_recovers(self):
        p=self.panel;p.text.setPlainText('自己的稿');p.save();old=p.path
        external=json.loads(old.read_text(encoding='utf-8'));external['segments'][0]['text']='外部修改'
        atomic_json(old,external)
        p.text.setPlainText('未保存的新稿');self.assertFalse(p.save());p.copy_button.click()
        self.assertNotEqual(p.path,old);self.assertEqual(p.selected()['text'],'未保存的新稿')
        self.assertEqual(json.loads(old.read_text(encoding='utf-8'))['segments'][0]['text'],'外部修改')

    def test_single_worker_blocks_project_and_project_blocks_dispatch(self):
        p=self.panel;self.window.worker=Mock();self.window.worker.isRunning.return_value=True
        self.assertFalse(p.can_start());self.window.worker=None
        p.set_busy(True)
        with patch.object(self.window.service.jobs,'next_queued') as queued:
            # 调用未被setUp替换的实现。
            self.dispatch.stop()
            try:self.window.dispatch();queued.assert_not_called()
            finally:self.dispatch.start()
        p.set_busy(False)

    def test_shutdown_flushes_unsaved_text(self):
        p=self.panel;p.text.setPlainText('关闭前输入');path=p.path
        self.window.close()
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['segments'][0]['text'],'关闭前输入')

    def test_cancel_worker_restores_controls_and_keeps_saved_draft(self):
        p=self.panel;p.text.setPlainText('取消不丢稿')
        def operation(cancel,progress):
            cancel.wait(10)
            if cancel.is_set():raise InterruptedError('已取消')
            raise TimeoutError('测试未收到取消')
        self.assertTrue(p.start(operation,'render'))
        p.cancel_button.click();self.wait()
        self.assertTrue(p.edit_area.isEnabled());self.assertIn('已取消',p.status.text())
        self.assertEqual(json.loads(p.path.read_text(encoding='utf-8'))['segments'][0]['text'],'取消不丢稿')


if __name__=='__main__':unittest.main()
