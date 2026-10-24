"""核对外观产物、来源、许可元数据及非空透明图片；不代替美术验收。"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from PIL import Image
from avatar3d.appearance_study import study_spec
from avatar3d.models import atomic_json, digest
from avatar3d.rig_audit import audit_vrm


def metadata(path):
    with path.open('rb') as stream:
        header = stream.read(20)
        document = json.loads(stream.read(struct.unpack_from('<I', header, 12)[0]))
    return {k: v for k, v in document['extensions']['VRMC_vrm']['meta'].items()
            if k != 'thumbnailImage'}


def check(folder):
    folder = Path(folder).resolve()
    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
    record = json.loads((folder / 'complete.json').read_text(encoding='utf-8'))
    variants, views, _ = study_spec(request.get('study', 'collar'))
    source = Path(request['source'])
    if digest(source) != record['source_sha256'] or record['source_sha256'] != request['source_sha256']:
        raise ValueError('源模型与生成记录不一致。')
    if [v['key'] for v in record['variants']] != [v.key for v in variants]:
        raise ValueError('候选列表不完整。')
    if digest(folder / 'A/C-character.vrm') != digest(source):
        raise ValueError('A原版与来源不一致。')
    source_audit, source_meta = audit_vrm(source), metadata(source)
    page = (folder / '预览.html').read_text(encoding='utf-8')
    images = []
    for variant in record['variants']:
        path = folder / variant['key']
        for name, sha in variant['files'].items():
            if Path(name).name != name or digest(path / name) != sha:
                raise ValueError('产物损坏或路径不合法：' + name)
        audit = audit_vrm(path / 'C-character.vrm')
        for key in ('humanoid_bones', 'expression_bind_counts', 'spring_chains', 'spring_joints', 'colliders', 'collider_groups'):
            if audit[key] != source_audit[key]:
                raise ValueError('驱动结构发生变化：' + key)
        if metadata(path / 'C-character.vrm') != source_meta:
            raise ValueError('源作者／许可元数据发生变化。')
        for key, *_ in views:
            if f'{variant["key"]}/{key}.png' not in page:
                raise ValueError('对照页缺少图片入口。')
            with Image.open(path / (key + '.png')) as image:
                if image.mode != 'RGBA' or image.size != (480, 720):
                    raise ValueError('图片尺寸／透明格式不匹配。')
                alpha = image.getchannel('A')
                count = image.width * image.height - alpha.histogram()[0]
                if alpha.getextrema() != (0, 255) or not 10000 < count < image.width * image.height * .95:
                    raise ValueError('图片可能为空或缺少透明背景。')
                images.append({'variant': variant['key'], 'view': key, 'foreground_pixels': count})
    return {'source_unchanged': True, 'baseline_identical': True, 'license_metadata_preserved': True,
            'image_checks': images, 'preview_html_sha256': digest(folder / '预览.html'),
            'native_preview_verified': False, 'warudo_verified': False,
            'manual_appearance_accepted': False, 'result': record}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError('检查报告已存在，请选择新路径。')
    result = check(args.folder)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(args.report, result)
    print(f'通过：{len(result["image_checks"])}张透明图片、模型结构、来源及许可元数据。')
