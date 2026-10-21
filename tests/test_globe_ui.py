"""Behavioral checks for independent city UI and saved output settings."""
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'));sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from pipeline import core,cities
from globe_app.dialog import AnimationDialog

class GlobeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_no_avatar_fields_and_city_text_is_independent(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".runtime") as tmp:
            d=AnimationDialog(tmp)
            self.assertEqual(d.mode.count(),2)
            self.assertFalse(any(check.isChecked() for check in d.text_checks.values()))
            self.assertFalse(any(hasattr(d,k) for k in ('lat','lon','mascot_path','score')))
            before=d.settings()['target'];d.name.setText('详细新闻地点')
            after=d.settings()['target']
            self.assertEqual(before['lat'],after['lat']);self.assertEqual(after['name'],'详细新闻地点')
            d.mode.setCurrentIndex(1);self.assertNotIn('hand',d.settings());d.close()

    def test_restore_last_generated_settings(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".runtime") as tmp:
            d=AnimationDialog(tmp);d.mode.setCurrentIndex(1)
            point=cities.resolve({'city':'英国 · 伦敦'})
            for i in range(d.target.count()):
                if d.target.itemData(i)['id']==point['id']:d.target.setCurrentIndex(i);break
            d.name.setText('伦敦 · 某会场');d.text_checks['location'].setChecked(True);c=d.settings();core.save_json(Path(tmp)/'preferences.json',c);d.close()
            again=AnimationDialog(tmp)
            self.assertEqual(again.settings()['target'],c['target'])
            self.assertEqual(again.settings()['mode'],'transition')
            self.assertTrue(again.text_checks['location'].isChecked())
            self.assertFalse(any(check.isChecked() for key,check in again.text_checks.items() if key!='location'));again.close()

    def test_unknown_typed_city_is_not_silently_used(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".runtime") as tmp:
            d=AnimationDialog(tmp);d.target.setEditText('不存在的城市xyz')
            with self.assertRaises(core.PipelineError):d.settings()
            d.close()

    def test_old_preferences_without_text_switches_stay_clean(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime') as tmp:
            config=__import__('pipeline.globe',fromlist=['validate']).validate({'mode':'transition'})
            config.pop('text_options');core.save_json(Path(tmp)/'preferences.json',config)
            d=AnimationDialog(tmp)
            self.assertFalse(any(d.settings()['text_options'].values()));d.close()

    def test_style_defaults_and_switching_duration(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime') as tmp:
            d=AnimationDialog(tmp)
            self.assertEqual(d.settings()['style'],'rubberhose');self.assertEqual(d.duration.value(),3)
            d.mode.setCurrentIndex(1);self.assertAlmostEqual(d.duration.value(),1.4)
            d.style.setCurrentIndex(1);self.assertEqual(d.settings()['style'],'classic');self.assertEqual(d.duration.value(),3)
            d.mode.setCurrentIndex(0);self.assertEqual(d.duration.value(),5);d.close()

    def test_style_and_custom_duration_restore(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime') as tmp:
            d=AnimationDialog(tmp);d.style.setCurrentIndex(1);d.duration.setValue(4.2)
            c=d.settings();core.save_json(Path(tmp)/'preferences.json',c);d.close()
            again=AnimationDialog(tmp)
            self.assertEqual(again.settings()['style'],'classic');self.assertAlmostEqual(again.duration.value(),4.2);again.close()
