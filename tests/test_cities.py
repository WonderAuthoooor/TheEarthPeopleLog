"""City selection is independent of detailed text and needs no user coordinates."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'))
sys.path.insert(0,str(ROOT))
from pipeline import cities,core


class CityTests(unittest.TestCase):
    def test_global_catalog_and_language_search(self):
        self.assertGreaterEqual(len(cities.catalog()),1200)
        for query in ('上海','London','东京','Sydney','开普敦','阿布扎比','墨西哥城','华盛顿'):
            with self.subTest(query=query):self.assertTrue(cities.search(query))

    def test_legacy_location_snaps_to_nearby_city(self):
        p=cities.resolve({'name':'英国·伦敦某数据中心','lat':51.51,'lon':-.13})
        self.assertEqual(p['city'],'伦敦')

    def test_city_name_without_coordinates(self):
        self.assertEqual(cities.resolve({'name':'中国 · 上海市浦东新区某研究院'})['city'],'上海')
        self.assertEqual(cities.resolve({'city':'Tokyo'})['city'],'东京')

    def test_unknown_address_and_country_do_not_guess(self):
        for text in ('某个不知名城市','日本','马尔代夫某工厂'):
            with self.subTest(text=text),self.assertRaises(core.PipelineError):cities.resolve({'name':text})

    def test_nearest_across_dateline(self):
        p=cities.nearest(-36.85,174.76)
        self.assertIn('奥克兰',p['name'])


if __name__=='__main__':unittest.main()
