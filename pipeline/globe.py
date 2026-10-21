"""Offline cartoon globe packaging. News facts and scores remain editorial inputs."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import json
import math
import os
import random
import shutil
import subprocess
import uuid
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from . import core

ASSETS = Path(__file__).resolve().parent / "assets"
MODES = ("intro", "transition")
STYLES = ("rubberhose", "classic")
TEXT_OPTIONS = {
    'title': '栏目名称：地球人日志',
    'subtitle': '英文副标题',
    'status': '过程提示语',
    'location': '详细地点名称',
    'nearby': '附近城市／位置示意',
    'footer': '底部栏目说明',
}


def smooth(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)


def number(value, low, high, label):
    if isinstance(value, bool):
        raise core.PipelineError(label + "必须为数字")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise core.PipelineError(label + "必须为数字")
    if not math.isfinite(value) or not low <= value <= high:
        raise core.PipelineError(f"{label}须在{low}至{high}之间")
    return value


def validate(config):
    c = dict(config)
    removed = {'mascot', 'show_mascot', 'score', 'score_status', 'score_reason', 'score_tail_seconds'} & c.keys()
    if c.get('mode') == 'mascot' or removed:
        raise core.PipelineError('这是旧版人物／评分动画设置。地点应用仅生成地球转场；旧输出保留，请重新选择城市生成纯地点动画。')
    c['schema_version'] = 2
    c.setdefault('style','classic')
    if c['style'] not in STYLES:
        raise core.PipelineError('动画风格无效')
    options=c.get('text_options',{})
    if not isinstance(options,dict) or set(options)-TEXT_OPTIONS.keys() or any(type(v) is not bool for v in options.values()):
        raise core.PipelineError('文字选项须为有效的勾选开关')
    c['text_options']={key:options.get(key,False) for key in TEXT_OPTIONS}
    c.setdefault("mode", "intro")
    if c["mode"] not in MODES:
        raise core.PipelineError("动画类型无效")
    c["width"] = int(number(c.get("width", 1080), 320, 1920, "宽度"))
    if c["width"] % 2:
        raise core.PipelineError("宽度须为偶数")
    c["height"] = 2 * round(c["width"] * 16 / 9 / 2)
    c["fps"] = int(number(c.get("fps", 30), 12, 30, "帧率"))
    c["duration"] = number(c.get("duration", 5 if c["mode"] == "intro" else 3), 1, 20, "时长")
    for key, default in [("target", {"name":"日本 · 种子岛", "lat":30.4, "lon":130.97}),
                         ("origin", {"name":"地球观察站", "lat":15, "lon":-20})]:
        point = dict(c.get(key, default))
        point["lat"] = number(point.get("lat"), -90, 90, "纬度")
        point["lon"] = number(point.get("lon"), -180, 180, "经度")
        point["name"] = ' '.join(str(point.get("name", "地点待补")).split())[:120]
        c[key] = point
    c['show_hand'] = bool(c.get('show_hand', True))
    if c['mode'] == 'intro' and c['show_hand']:
        default_hand='rubber_glove.svg' if c['style']=='rubberhose' else 'alien.svg'
        p = Path(c.get('hand') or ASSETS / 'hands' / default_hand).resolve()
        # Bundled component paths change when upgrading a versioned application.
        if p.name in ('rubber_glove.svg','alien.svg','robot.svg') and p.parent.name=='hands' and p.parent.parent.name=='assets' and p.parent.parent.parent.name=='pipeline':
            p=(ASSETS/'hands'/p.name).resolve()
        if not p.is_file() or p.suffix.lower() not in ('.svg', '.png') or p.stat().st_size > 8 * 1024 * 1024:
            raise core.PipelineError('开场手部须为8MB以内的本地SVG或透明PNG')
        c['hand'] = str(p)
    else:
        c.pop('hand', None)
    return c


def project(lat, lon, camera_lat, camera_lon):
    """Orthographic coordinates: east right, north up, visibility toward camera."""
    p, p0, delta = map(math.radians, (lat, camera_lat, lon - camera_lon))
    return (math.cos(p) * math.sin(delta),
            math.cos(p0) * math.sin(p) - math.sin(p0) * math.cos(p) * math.cos(delta),
            math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(delta))


@lru_cache(maxsize=12)
def sprite(path, size):
    p = Path(path)
    if p.suffix.lower() == ".svg":
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        renderer = QSvgRenderer(str(p))
        if not renderer.isValid():
            raise core.PipelineError("SVG组件无法读取")
        box = renderer.viewBoxF()
        height = max(1, round(size * box.height() / box.width()))
        canvas = QImage(size, height, QImage.Format_RGBA8888)
        canvas.fill(Qt.transparent)
        paint = QPainter(canvas)
        renderer.render(paint, QRectF(0, 0, size, height))
        paint.end()
        return Image.frombytes("RGBA", (size, height), bytes(canvas.bits()))
    image = Image.open(p).convert("RGBA")
    if image.width * image.height > 16_000_000:
        raise core.PipelineError("组件图片尺寸过大")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image


@lru_cache(maxsize=2)
def texture(style="classic"):
    w, h = 2048, 1024
    retro=style=='rubberhose'
    ocean='#639b8b' if retro else '#438eae'
    land='#e7bd70' if retro else '#b7e6a0'
    grid='#83b09a' if retro else '#5b9eb7'
    world = Image.new("RGB", (w, h), ocean)
    draw = ImageDraw.Draw(world)
    for x in range(0, w, w // 12):
        draw.line((x, 0, x, h), fill=grid, width=2)
    for y in range(h // 6, h, h // 6):
        draw.line((0, y, w, y), fill=grid, width=2)
    data = json.loads((ASSETS / "ne_110m_land.geojson").read_text(encoding="utf-8"))
    for feature in data["features"]:
        geo = feature["geometry"]
        polygons = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
        for rings in polygons:
            for index, ring in enumerate(rings):
                points = [((lon + 180) / 360 * w, (90 - lat) / 180 * h) for lon, lat, *_ in ring]
                draw.polygon(points, fill=land if index == 0 else ocean)
                if retro:draw.line(points+[points[0]],fill='#425145',width=3,joint='curve')
    tiled = Image.new("RGB", (w * 3, h))
    for x in range(3):
        tiled.paste(world, (x * w, 0))
    return tiled


@lru_cache(maxsize=4)
def sphere_masks(size):
    mask = Image.new("L", (size, size))
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    light = Image.new("L", (size, size), 255)
    px = light.load()
    for y in range(size):
        for x in range(size):
            sx, sy = 2 * x / (size - 1) - 1, 1 - 2 * y / (size - 1)
            z = math.sqrt(max(0, 1 - sx * sx - sy * sy))
            px[x, y] = int(140 + 115 * max(0, -.35 * sx + .25 * sy + .85 * z))
    return mask, light


def globe(size, latitude, longitude, style="classic"):
    tiled = texture(style)
    tw, th = tiled.width / 3, tiled.height
    p = math.radians(latitude)
    sinp, cosp = math.sin(p), math.cos(p)
    cells = 40
    nodes = {}
    for j in range(cells + 1):
        for i in range(cells + 1):
            x, y = 2 * i / cells - 1, 1 - 2 * j / cells
            # The mask hides outside vertices; clamp to limb for stable interpolation.
            length = math.hypot(x, y)
            if length > .99999:
                x, y = x / length * .99999, y / length * .99999
            z = math.sqrt(max(0, 1 - x*x - y*y))
            lat = math.asin(max(-1., min(1., cosp * y + sinp * z)))
            lon = math.atan2(x, cosp * z - sinp * y)
            nodes[i,j] = ((lon + math.radians(longitude)) / (2 * math.pi) * tw + 1.5 * tw,
                          (.5 - lat / math.pi) * th)
    mesh = []
    for j in range(cells):
        for i in range(cells):
            corners = [nodes[i,j], nodes[i,j+1], nodes[i+1,j+1], nodes[i+1,j]]
            anchor = corners[0][0]
            corners = [(u + round((anchor-u)/tw)*tw, v) for u,v in corners]
            quad = tuple(value for point in corners for value in point)
            box = (round(i*size/cells), round(j*size/cells), round((i+1)*size/cells), round((j+1)*size/cells))
            mesh.append((box, quad))
    image = tiled.transform((size,size), Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)
    mask, light = sphere_masks(size)
    if style=='rubberhose':light=light.point(lambda value:252 if value>218 else (238 if value>177 else 219))
    image = ImageChops.multiply(image, Image.merge("RGB", (light, light, light))).convert("RGBA")
    image.putalpha(mask)
    return image


@lru_cache(maxsize=3)
def background(w, h):
    image = Image.new("RGB", (64, 114))
    px = image.load()
    for y in range(114):
        for x in range(64):
            glow = max(0, 1 - math.hypot((x-32)/46, (y-53)/70))
            px[x,y] = (int(28+22*glow), int(28+24*glow), int(58+35*glow))
    image = image.resize((w,h), Image.Resampling.BICUBIC).convert("RGBA")
    draw = ImageDraw.Draw(image)
    rng = random.Random(37)
    for _ in range(75):
        x, y = rng.randrange(w), rng.randrange(h)
        radius = max(1, round(w/540))
        draw.ellipse((x,y,x+radius,y+radius), fill=(188,190,221,160))
    return image


def caption(draw, xy, text, size, fill="#f8edcf", anchor="mm", max_width=None):
    font = core.font(max(10, round(size)), True)
    if max_width:
        while draw.textlength(text, font=font) > max_width and size > 11:
            size -= 1
            font = core.font(round(size), True)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def location_caption(draw, w, h, target, fill="#f8edcf"):
    text=target['name']
    size=max(12,round(w*.045))
    def wrap(font):
        lines=[];line=''
        for char in text:
            if char=='\n' or (line and draw.textlength(line+char,font=font)>w*.84):
                lines.append(line);line=''
            if char!='\n':line+=char
        if line:lines.append(line)
        return lines
    while True:
        font=core.font(size,True);lines=wrap(font)
        if len(lines)<=4 or size<=max(10,round(w*.022)):break
        size-=1
    line_height=max(size*1.35,1)
    top=h*.695-(len(lines)-1)*line_height/2
    for index,line in enumerate(lines[:4]):
        draw.text((w*.5,top+index*line_height),line,font=font,fill=fill,anchor='mm')


def draw_text(image,c,progress):
    w,h=c['width'],c['height'];text=c['text_options'];target=c['target'];d=ImageDraw.Draw(image)
    retro=c['style']=='rubberhose';ink='#302e25' if retro else '#f8edcf';muted='#716046' if retro else '#bcb6d1'
    if text['title']:caption(d,(w*.12,h*.085),'地球人日志',w*.043,fill=ink,anchor='lm')
    if text['subtitle']:caption(d,(w*.12,h*.12),'EARTH PEOPLE LOG / DAILY OBSERVER',w*.018,fill=muted,anchor='lm')
    status='观察地点已锁定' if progress>.8 else ('今天，地球人又在忙什么？' if c['mode']=='intro' else '下一站，继续记录')
    if text['status']:caption(d,(w*.5,h*.635),status,w*.032,fill=muted)
    if progress>.76:
        if text['location']:location_caption(d,w,h,target,fill=ink)
        if text['nearby']:
            nearby=target.get('city_name','附近城市')+' · 位置示意'
            caption(d,(w*.12,h*.77),nearby,w*.021,fill=muted,anchor='lm',max_width=w*.76)
    if text['footer']:caption(d,(w*.12,h*.91),'观察员值班中 · 栏目动画',w*.021,fill=muted,anchor='lm')
    return image


def frame(config, progress):
    c = config
    if c['style']=='rubberhose':
        from .globe_retro import frame as retro_frame
        return draw_text(retro_frame(c,progress),c,progress)
    w,h = c["width"],c["height"]
    image = background(w,h).copy()
    d = ImageDraw.Draw(image)
    q = smooth((progress-.1)/.7)
    origin,target = c["origin"],c["target"]
    delta = (target["lon"]-origin["lon"]+180)%360-180
    if c["mode"] == "intro":
        delta += 360
    lat = origin["lat"] + (target["lat"]-origin["lat"])*q
    lon = (origin["lon"]+delta*q+180)%360-180
    # Fixed sphere raster resolution avoids rebuilding large shading masks per frame.
    size = round(w*.72)
    planet = globe(size,lat,lon)
    scale = 1 + .12*smooth((progress-.65)/.25)
    final = round(size*scale)
    if final != size:
        planet = planet.resize((final,final),Image.Resampling.LANCZOS)
    cx,cy = w*.5,h*.465
    glow = Image.new("RGBA",(w,h));gd=ImageDraw.Draw(glow)
    gd.ellipse((cx-final*.53,cy-final*.53,cx+final*.53,cy+final*.53),fill="#625c9b")
    glow=glow.filter(ImageFilter.GaussianBlur(w*.025))
    image.alpha_composite(glow)
    image.alpha_composite(planet,(round(cx-final/2),round(cy-final/2)))
    d=ImageDraw.Draw(image)
    # A visible locator appears only while the target is on the front hemisphere.
    sx,sy,z = project(target["lat"],target["lon"],lat,lon)
    if progress>.67 and z>0:
        mx,my=cx+sx*final/2,cy-sy*final/2
        radius=w*(.022+.008*math.sin(progress*math.tau*3))
        d.ellipse((mx-radius,my-radius,mx+radius,my+radius),outline="#fff0b3",width=max(2,round(w*.005)))
        d.ellipse((mx-w*.009,my-w*.009,mx+w*.009,my+w*.009),fill="#fff0b3")
    if c["mode"]=="intro" and c["show_hand"] and progress<.67:
        hand = sprite(c["hand"],round(w*.59))
        arrival=smooth(progress/.17)*(1-smooth((progress-.48)/.18))
        hand=hand.rotate(-12+20*q,Image.Resampling.BICUBIC,expand=True)
        image.alpha_composite(hand,(round(w*.51+(1-arrival)*w*.8),round(h*.22)))
    return draw_text(image,c,progress)


def render_package(config, output_root, progress=None, cancelled=None):
    c=validate(config)
    # A unique output folder never overwrites an existing animation or user video.
    out=Path(output_root).resolve()/ (core.now()[:19].replace(':','').replace('-','').replace('T','_')+'_'+c['mode']+'_'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    components=out/'components'
    components.mkdir()
    for key in ('hand',) if 'hand' in c else ():
        source=Path(c[key])
        saved=components/(key+source.suffix.lower())
        shutil.copy2(source,saved)
        c[key]=str(saved)
    core.save_json(out/'settings.json',c)
    destination=out/(c['mode']+'.mp4')
    temporary=destination.with_name(destination.stem+'.part'+destination.suffix)
    result={'status':'running','config':c,'output':str(destination),'created_at':core.now()}
    core.save_json(out/'manifest.json',result)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    args=[core.ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgba','-video_size',f"{c['width']}x{c['height']}",'-framerate',str(c['fps']),'-i','pipe:0','-an']
    args+=['-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart']
    args += [str(temporary)]
    from .processes import ChildGroup
    group=ChildGroup(); child=None
    try:
        with (out/'encoder.log').open('wb') as error:
            child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=error,creationflags=flags)
            group.attach(child)
            count=max(2,round(c['duration']*c['fps']))
            for i in range(count):
                if cancelled and cancelled():
                    raise core.PipelineError('动画生成已取消')
                still=frame(c,i/(count-1))
                if i in (0,count-1):
                    still.save(out/('first-frame.png' if i==0 else 'last-frame.png'))
                child.stdin.write(still.tobytes())
                if progress:progress(round((i+1)/count*100))
            child.stdin.close()
            if child.wait(timeout=120):
                raise core.PipelineError('编码失败，请查看encoder.log')
        os.replace(temporary,destination)
        result.update(status='succeeded',completed_at=core.now(),sha256=core.fingerprint(destination),metadata=core.probe(destination),alpha=False,
                      note='纯地点动画；附近城市为位置示意，不含人物或评分。')
        core.save_json(out/'manifest.json',result)
        return out
    except Exception as exc:
        if child and child.poll() is None:
            child.kill();child.wait(timeout=15)
        temporary.unlink(missing_ok=True)
        result.update(status='cancelled' if cancelled and cancelled() else 'failed',error=str(exc))
        core.save_json(out/'manifest.json',result)
        raise
    finally:
        group.close()


def publish_progress(path, value):
    # Windows may briefly deny replacing a file while the UI is reading it.
    # Progress is disposable; a lost update must not discard an encoded video.
    try:
        core.save_json(path, {'progress':value})
    except PermissionError:
        pass


def execute_request(request_path):
    request=json.loads(Path(request_path).read_text(encoding='utf-8'))
    cancel=Path(request['cancel_file'])
    try:
        out=render_package(request['config'],request['output_root'],
            lambda value: publish_progress(request['progress_file'],value),cancel.exists)
        core.save_json(request['result_file'],{'status':'succeeded','output':str(out)})
        return 0
    except Exception as exc:
        core.save_json(request['result_file'],{'status':'cancelled' if cancel.exists() else 'failed','error':str(exc)})
        return 1
