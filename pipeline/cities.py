"""Offline city lookup and approximate event placement; no user coordinate input."""
from functools import lru_cache
from pathlib import Path
import json
import math
import unicodedata
from . import core


def normalized(text):
    text = unicodedata.normalize('NFKD', str(text)).casefold()
    return ''.join(c for c in text if c.isalnum() and not unicodedata.combining(c))


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).resolve().parent/'assets/locations.json').read_text(encoding='utf-8'))


def search(text, limit=20):
    query = normalized(text)
    return [p for p in catalog() if any(query in normalized(a) for a in [p['name'],*p['aliases']])][:limit]


def nearest(latitude, longitude):
    from .globe import number
    lat = math.radians(number(latitude,-90,90,'纬度'))
    lon = math.radians(number(longitude,-180,180,'经度'))
    def distance(p):
        dy=math.radians(p['lat'])-lat
        dx=math.radians(p['lon'])-lon
        return math.sin(dy/2)**2+math.cos(lat)*math.cos(math.radians(p['lat']))*math.sin(dx/2)**2
    return min(catalog(),key=distance)


def resolve(location):
    """Prefer known coordinates when importing legacy event locations; snap to city."""
    if location.get('lat') is not None and location.get('lon') is not None:
        return nearest(location['lat'],location['lon'])
    text=normalized(location.get('city') or location.get('city_name') or location.get('name',''))
    exact=[p for p in catalog() if text and any(text==normalized(a) for a in [p['name'],*p['city_aliases']])]
    if exact:
        if len(exact)>1:
            raise core.PipelineError('城市有重名，请在资讯地点中补充国家或地区')
        return exact[0]
    # Only city-name aliases, never guess a city merely from a country name.
    matches=[(len(normalized(a)),p) for p in catalog() for a in p['city_aliases']
             if len(normalized(a))>=2 and normalized(a) in text]
    if matches:
        matches.sort(key=lambda item:item[0],reverse=True)
        best=[p for size,p in matches if size==matches[0][0]]
        unique={p['id']:p for p in best}
        if len(unique)==1:return next(iter(unique.values()))
    raise core.PipelineError('未能确定附近城市，请从城市搜索结果中选择，不需要查经纬度')
