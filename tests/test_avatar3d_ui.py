"""复现用户实际加载按钮：首次自动排队、有反馈、重复加载复用且不显示别的模型。"""
from pathlib import Path
import sys,tempfile,unittest,json,shutil
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
from PySide6.QtWidgets import QApplication
from PIL import Image
from avatar3d.app import Window
from avatar3d.models import atomic_json,digest
from avatar3d.contracts import RenderSpec

TEMP=ROOT/'.runtime/avatar3d-tests';TEMP.mkdir(exist_ok=True)
SAMPLE=ROOT/'avatar3d/assets/Seed-san.vrm'

class LoadUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def window(self,workspace,sample=SAMPLE):
        return Window(workspace,ROOT/'.runtime/avatar3d/runtime.json',sample)

    def test_real_load_button_enqueues_once_and_feedback_is_visible(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            w=self.window(tmp)
            try:
                w.demo.click();w.demo.click()
                rows=w.service.jobs.list();self.assertEqual(len(rows),1)
                self.assertIn('Seed-san',w.status.text());self.assertIn('预览',w.status.text())
                self.assertIn('Seed-san',w.picture.text())
                request=w.service.jobs.get(rows[0]['id'])['request']
                self.assertEqual(request,RenderSpec(w.model.currentData()['sha256'],'neutral',.5,320,12,0).to_dict())
            finally:w.close()

    def test_repeated_load_restores_verified_preview_and_restart_reuses(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            w=self.window(tmp)
            try:
                w.demo.click();row=w.service.jobs.list()[0];ident=row['id'];w.service.jobs.claim(ident)
                folder=Path(tmp)/'jobs'/ident;folder.mkdir(parents=True)
                (folder/'角色透明.mov').write_bytes(b'fixture');(folder/'动作预览.mp4').write_bytes(b'fixture');(folder/'scene.blend').write_bytes(b'fixture')
                Image.new('RGBA',(320,480),(80,160,120,255)).save(folder/'姿势预览.png')
                atomic_json(folder/'complete.json',{'job_id':ident,'files':{name:digest(folder/name) for name in ('角色透明.mov','动作预览.mp4','scene.blend','姿势预览.png')}})
                atomic_json(folder/'request.json',w.service.jobs.get(ident)['request'])
                w.service.jobs.finish(ident,'complete')
                w.demo.click()
                self.assertEqual(len(w.service.jobs.list()),1)
                self.assertFalse(w.picture.pixmap().isNull());self.assertIn('已有模型预览',w.status.text())
                w.close();w=self.window(tmp);self.app.processEvents()
                self.assertEqual(len(w.service.jobs.list()),1)
                self.assertFalse(w.picture.pixmap().isNull())
                # 图片损坏时不能复用，另建任务修复；原失败缓存文件不覆盖。
                (folder/'姿势预览.png').write_bytes(b'corrupt')
                w.demo.click();self.assertEqual(len(w.service.jobs.list()),2)
            finally:w.close()

    def test_missing_sample_reports_error_instead_of_silent_click(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            w=self.window(tmp,Path(tmp)/'missing.vrm')
            try:
                w.demo.click();self.assertIn('导入失败',w.status.text())
                self.assertEqual(w.service.jobs.list(),[])
            finally:w.close()

    def test_exchange_button_rejects_unfinished_source_and_keeps_existing_job(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            w=self.window(tmp)
            try:
                w.demo.click();w.list.setCurrentRow(0)
                w.exchange.click()
                self.assertIn('任务尚未完成',w.status.text())
                self.assertIsNone(w.exchange_worker)
                self.assertEqual(len(w.service.jobs.list()),1)
            finally:w.close()

    def test_active_exchange_blocks_parallel_renderer_and_cancel_reaches_worker(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            w=self.window(tmp)
            try:
                w.exchange_worker=Mock();w.exchange_worker.isRunning.return_value=True
                with patch.object(w.service.jobs,'next_queued') as next_job:
                    Window.dispatch(w);next_job.assert_not_called()
                w.cancel.click();w.exchange_worker.cancel.set.assert_called_once()
                w.exchange.click();self.assertIn('等待当前任务',w.status.text())
                w.exchange_worker.isRunning.return_value=False
            finally:w.close()

    def test_old_job_result_does_not_replace_newly_selected_model_picture(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp,patch.object(Window,'dispatch'):
            w=self.window(tmp)
            try:
                w.demo.click()
                first=w.model.currentData();other=dict(first,sha256='b'*64,name='其他模型')
                w.model.addItem(other['name'],other);w.model.setCurrentIndex(1)
                folder=Path(tmp)/'old-result';folder.mkdir()
                atomic_json(folder/'request.json',{'model_sha256':first['sha256']})
                Image.new('RGBA',(320,480),(255,0,0,255)).save(folder/'姿势预览.png')
                w.finished(str(folder),'')
                self.assertFalse(w.picture.pixmap() and not w.picture.pixmap().isNull())
                self.assertIn('其他模型',w.picture.text())
            finally:w.close()

if __name__=='__main__':unittest.main()
