"""Warudo模型副本导入：只新增、不覆盖、失败不留下可加载半成品。"""
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('warudo_prepare',ROOT/'scripts/prepare-warudo-model.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
TEMP=ROOT/'.runtime/avatar3d-tests';TEMP.mkdir(exist_ok=True)
SAMPLE=ROOT/'avatar3d/assets/Seed-san.vrm'


class WarudoPrepareTests(unittest.TestCase):
    def setup_install(self,tmp):
        install=Path(tmp)/'Warudo';characters=install/'Warudo_Data/StreamingAssets/Characters'
        characters.mkdir(parents=True);(install/'Warudo.exe').write_bytes(b'test installation fixture')
        return install,characters

    def test_copy_is_verified_and_repeat_reuses_without_modifying_other_models(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            install,characters=self.setup_install(tmp);existing=characters/'existing.vrm';existing.write_bytes(b'preserve')
            record=Path(tmp)/'record.json';a=module.prepare_model(install,SAMPLE,record)
            b=module.prepare_model(install,SAMPLE,record)
            self.assertFalse(a['existing_identical_reused']);self.assertTrue(b['existing_identical_reused'])
            self.assertEqual(module.digest(a['character_path']),module.digest(SAMPLE))
            self.assertEqual(existing.read_bytes(),b'preserve');self.assertFalse(b['warudo_load_verified'])

    def test_collision_and_incomplete_install_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            install,characters=self.setup_install(tmp);record=Path(tmp)/'record.json'
            target=characters/('AvatarLab_Test_'+module.digest(SAMPLE)[:12]+'.vrm');target.write_bytes(b'important original')
            with self.assertRaises(ValueError):module.prepare_model(install,SAMPLE,record)
            self.assertEqual(target.read_bytes(),b'important original');self.assertFalse(record.exists())
            with self.assertRaises(ValueError):module.prepare_model(Path(tmp)/'missing',SAMPLE,record)

    def test_failed_publication_leaves_no_vrm_or_partial(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            install,characters=self.setup_install(tmp);record=Path(tmp)/'record.json'
            with patch.object(module.os,'link',side_effect=OSError('filesystem failure')):
                with self.assertRaises(OSError):module.prepare_model(install,SAMPLE,record)
            self.assertEqual(list(characters.iterdir()),[]);self.assertFalse(record.exists())


if __name__=='__main__':unittest.main()
