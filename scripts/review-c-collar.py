"""创建独立C衣领对照，现有输出不覆盖；失败保留日志且不生成完成标记。"""
import argparse
import os
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.backend import Runtime, launch_external
from avatar3d.models import digest, atomic_json
from avatar3d.appearance_study import study_spec
from avatar3d.rig_audit import audit_vrm


def run(source, studio, output, runtime_path, study='collar'):
    variants, views, revision = study_spec(study)
    source, studio, output = [Path(p).resolve() for p in (source, studio, output)]
    runtime = Runtime.load(runtime_path)
    audit_vrm(source)
    request = {'source': str(source), 'source_sha256': digest(source),
               'studio': str(studio), 'studio_sha256': digest(studio),
               'output': str(output), 'addon': str(runtime.addon.resolve()), 'study': study,
               'code_sha256': {name: digest(ROOT / name) for name in (
                   'avatar3d/appearance_study.py', 'avatar3d/appearance_worker.py',
                   'avatar3d/shoulder_repair.py',
                   'avatar3d/round_face.py',
                   'avatar3d/natural_pose.py', 'avatar3d/natural_motion.py',
                   'scripts/review-c-collar.py')}}
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / 'request.json', request)
    env = dict(os.environ, BLENDER_USER_CONFIG=str(output / 'blender-config'),
               BLENDER_USER_SCRIPTS=str(output / 'blender-scripts'))
    with (output / 'blender.log').open('wb') as log:
        process = launch_external([str(runtime.blender), '--background', '--factory-startup',
            '--disable-autoexec', '--python-exit-code', '23', '--python',
            str(ROOT / 'avatar3d/appearance_worker.py'), '--', str(output / 'request.json')], env, log)
        try:
            code = process.wait(timeout=900)
            if code or not (output / 'complete.json').is_file():
                raise RuntimeError('衣领对照未完成，请查看输出目录blender.log。')
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
    sections = []
    for key, label, *_ in views:
        cards = ''.join(f'<figure><img src="{v.key}/{key}.png" alt="{v.label}：{label}"><figcaption>{v.key} · {v.label}</figcaption></figure>' for v in variants)
        sections.append(f'<section><h2>{label}</h2><div class="row">{cards}</div></section>')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>C衣领对照</title>
<style>body{background:#18232b;color:#eee;font:17px system-ui;margin:24px}p{line-height:1.7;max-width:1000px}.row{display:flex;gap:16px;flex-wrap:wrap}figure{margin:0;flex:1;min-width:220px;max-width:480px}img{width:100%;background:repeating-conic-gradient(#303e48 0% 25%,#293640 0% 50%) 50%/32px 32px;border-radius:12px}figcaption{padding:10px}section{margin:32px 0}body.small figure{max-width:180px;min-width:140px}button{padding:10px;font:inherit}</style>
<h1>C角色 · 肩颈衣领对照</h1><p>A保留原版；B只降低黑色内领；C只降低外套立领及薄荷色包边。脸型、身体比例、骨架与动作保持一致。镜头、光照、姿势相同，图片来自导出VRM重新导入后的实际3D渲染。</p>
<p>这是外观研究，尚未替换应用默认角色，也不是最终定稿。未在Warudo验证新候选；静态讲解姿态不代表完整动作穿模验收。</p>
<p>已发现的局限：原版侧面肩领接缝已有露肤，C降低外领后更明显；三个版本都保留原肩部尖角轮廓。近景聚焦肩颈，全身图用于查看完整轮廓。此轮不直接推荐替换正式模型。</p>
<button onclick="document.body.classList.toggle('small')">切换小尺寸／详细对照</button>
''' + ''.join(sections) + '</html>'
    if study == 'shoulder':
        page = page.replace('C衣领对照', 'C肩领修复对照').replace('C角色 · 肩颈衣领对照', 'C角色 · 肩领接缝与袖色分界')
        page = page.replace('A保留原版；B只降低黑色内领；C只降低外套立领及薄荷色包边。',
                            'A保留原版；D切齐黑白袖色分界，并扩大黑色内搭的肩颈覆盖。原版内外领高度保持不变。')
        page = page.replace('已发现的局限：原版侧面肩领接缝已有露肤，C降低外领后更明显；三个版本都保留原肩部尖角轮廓。',
                            '检查重点：肩部黑白分界是否平顺、侧面领口是否仍有意外露肤，讲解姿态下衣服是否变形异常。此轮没有改变面部或人体轮廓。')
    if study == 'rounded':
        page = page.replace('C衣领对照', 'C圆润脸型对照').replace('C角色 · 肩颈衣领对照', 'C角色 · 更圆润可爱一点')
        page = page.replace('A保留原版；B只降低黑色内领；C只降低外套立领及薄荷色包边。脸型、身体比例、骨架与动作保持一致。',
            'A是当前肩领修复版；E是轻度圆润；F是更明显的可爱版。重点比较饱满脸颊、短圆下巴与稍大的眼睛。')
        page = page.replace('未在Warudo验证新候选；静态讲解姿态不代表完整动作穿模验收。',
            '微笑、闭眼和张嘴来自实际表情驱动；候选仍需个人审美与目标软件验证。')
        page = page.replace('已发现的局限：原版侧面肩领接缝已有露肤，C降低外领后更明显；三个版本都保留原肩部尖角轮廓。近景聚焦肩颈，全身图用于查看完整轮廓。此轮不直接推荐替换正式模型。',
            '三版使用相同身体、服装、头发与骨架。已保留可编辑模型；本轮先确认可爱程度，后续可继续调整发型和服装轮廓。')
    (output / '预览.html').write_text(page, encoding='utf-8')
    print(output / '预览.html', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--studio', type=Path, required=True, help='项目自有的可信Blender灯光场景')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.runtime/avatar3d/runtime.json')
    parser.add_argument('--study', choices=('collar', 'shoulder', 'rounded'), default='collar')
    args = parser.parse_args()
    run(args.source, args.studio, args.output, args.runtime, args.study)
