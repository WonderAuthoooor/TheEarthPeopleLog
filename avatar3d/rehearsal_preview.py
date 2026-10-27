"""从校验过的排练母版派生播放预览，不改变动作或源工程。"""
from pathlib import Path
import json

from .models import digest
from .rehearsal import validate


def source_info(folder):
    folder = Path(folder).resolve()
    record = json.loads((folder / 'rehearsal-complete.json').read_text(encoding='utf-8'))
    for name in ('scene.blend', 'request.json'):
        if digest(folder / name) != record['files'].get(name):
            raise ValueError('排练母版或请求已改变，请重新生成后再预览。')
    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
    plan = validate(request['rehearsal'])
    fps = request['fps']
    total = round(plan['duration'] * fps)
    if fps != 30 or record['baked_frames'] != total or not 2 <= total <= 900:
        raise ValueError('排练母版帧数或帧率不一致。')
    return {'source': str(folder), 'master_sha256': record['files']['scene.blend'],
            'request_sha256': record['files']['request.json'], 'frames': total,
            'fps': fps, 'duration': total / fps}


def output_settings(source, width=320, samples=2, quality='motion'):
    if type(width) is not int or width not in (240, 320, 480):
        raise ValueError('预览宽度须为240、320或480。')
    if type(samples) is not int or not 1 <= samples <= 16:
        raise ValueError('预览采样数须为1—16。')
    if quality not in ('motion', 'material'):
        raise ValueError('预览模式无效。')
    engine = 'BLENDER_WORKBENCH' if quality == 'motion' else 'BLENDER_EEVEE_NEXT'
    return dict(source, revision=1, engine=engine, quality=quality, width=width,
                height=width * 3 // 2, samples=samples)


def check_frame(path, size):
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        if image.size != size or image.mode != 'RGBA':
            raise ValueError('预览帧尺寸或颜色通道不完整。')
        low, high = image.getchannel('A').getextrema()
        if low != 0 or high < 200:
            raise ValueError('预览帧为空或缺少透明背景。')


def reusable_frames(folder, settings):
    """仅复用已登记哈希的完整帧；损坏／中断帧需重新渲染。"""
    folder = Path(folder)
    saved = json.loads((folder / 'preview-request.json').read_text(encoding='utf-8'))
    if saved != settings:
        raise ValueError('预览参数或源母版不同，请使用新输出目录。')
    good = {}
    for index in range(settings['frames']):
        frame = folder / 'frames' / f'{index:05d}.png'
        receipt = frame.with_suffix('.sha256')
        if not frame.is_file() or not receipt.is_file():
            continue
        try:
            sha = digest(frame)
            if sha != receipt.read_text(encoding='ascii').strip():
                continue
            check_frame(frame, (settings['width'], settings['height']))
        except (OSError, ValueError):
            continue
        good[index] = sha
    return good
