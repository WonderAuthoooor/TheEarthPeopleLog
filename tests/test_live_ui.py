import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT),str(ROOT/'tests')]
from PySide6.QtWidgets import QApplication
from avatar3d.live_ui import LivePanel
import test_live_package


class LiveUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.fixture=test_live_package.LivePackageTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.panel=LivePanel(self.fixture.root); self.addCleanup(self.panel.close)
        self.panel.package.setText(str(self.fixture.package))
        self.panel.install.setText(str(self.fixture.target()))
    def wait(self):
        deadline=time.monotonic()+10
        while (self.panel.busy or (self.panel.worker and self.panel.worker.isRunning())) and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.01)
        self.app.processEvents(); self.assertFalse(self.panel.busy,self.panel.status.text())
    def test_check_restore_recheck_and_saved_paths(self):
        p=self.panel; p.check.click(); self.assertFalse(p.package.isEnabled()); self.wait()
        self.assertTrue(p.restore.isEnabled()); p.restore.click(); self.wait()
        self.assertIn('新增3项',p.status.text()); self.assertFalse(p.restore.isEnabled())
        p.check.click(); self.wait(); self.assertIn('无需恢复',p.status.text())
        second=LivePanel(self.fixture.root); self.addCleanup(second.close)
        self.assertEqual(second.package.text(),p.package.text())
    def test_changed_path_invalidates_plan(self):
        p=self.panel; p.check.click();self.wait();self.assertTrue(p.restore.isEnabled())
        p.package.setText(str(self.fixture.root/'missing'))
        self.assertFalse(p.restore.isEnabled());self.assertIsNone(p.plan)
        p.check.click();self.wait();self.assertIn('未完成',p.status.text())
    def test_conflict_blocks_restore(self):
        target=self.fixture.target()/'Warudo_Data/StreamingAssets/Scenes/C_Live.json'
        target.parent.mkdir();target.write_text('user scene')
        p=self.panel;p.check.click();self.wait();self.assertFalse(p.restore.isEnabled())
        self.assertIn('冲突',p.report.toPlainText());self.assertEqual(target.read_text(),'user scene')

    def test_invalid_settings_are_ignored(self):
        (self.fixture.root/'live-settings.json').write_text('[]',encoding='utf-8')
        second=LivePanel(self.fixture.root);self.addCleanup(second.close)
        self.assertEqual(second.package.text(),'');self.assertFalse(second.restore.isEnabled())
