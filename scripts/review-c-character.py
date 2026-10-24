"""从已校验的C初稿生成基础驱动检查包；每次使用全新目录。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.backend import Runtime, launch_external
from avatar3d.models import digest, atomic_json
from avatar3d.rig_audit import audit_vrm

LABELS = {'neutral': '自然', 'happy': '开心', 'angry': '生气', 'sad': '难过',
          'relaxed': '放松', 'surprised': '惊讶', 'aa': '嘴形 A', 'ih': '嘴形 I',
          'ou': '嘴形 U', 'ee': '嘴形 E', 'oh': '嘴形 O', 'blink': '眨眼',
          'blinkLeft': '左眼', 'blinkRight': '右眼', 'blink_aa': '眨眼＋张嘴', 'happy_aa': '微笑＋张嘴'}


def finalize(folder):
    """检查渲染证据，复用既有编码器；完成标记只在媒体检查通过后写入。"""
    from avatar3d.service import encode
    folder = Path(folder)
    report = json.loads((folder / 'rig-report.json').read_text(encoding='utf-8'))
    for filename, key in [('C-character.vrm', 'vrm_sha256'), ('C-character.blend', 'blend_sha256')]:
        if digest(folder / filename) != report[key]:
            raise ValueError('模型与驱动检查记录不一致。')
    audit_vrm(folder / 'C-character.vrm')
    manifest = json.loads((folder / 'frames-complete.json').read_text(encoding='utf-8'))
    files = sorted((folder / 'frames').glob('*.png'))
    expected = report['simulation']['frames']
    if len(files) != expected or set(manifest['files']) != {f.name for f in files}:
        raise ValueError('检查帧序列不完整。')
    for i, file in enumerate(files):
        if file.name != f'{i:04}.png' or digest(file) != manifest['files'][file.name]:
            raise ValueError('检查帧序列哈希或编号不一致。')
    for name in LABELS:
        if not (folder / 'expressions' / (name + '.png')).is_file():
            raise ValueError('表情检查图缺失：' + name)
    encode(files, folder, report['simulation']['fps'], threading.Event(), lambda _: None)
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>C角色驱动检查</title>
<style>body{max-width:1100px;margin:30px auto;background:#18212a;color:#eee;font:17px/1.7 system-ui}h1{font-size:28px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}figure{margin:0}img{width:100%;background:#303e47}video{max-height:540px;max-width:100%;background:#303e47}a{color:#80ddce}</style>
<h1>C角色 · 基础驱动检查</h1><p>重新导入VRM后的真实渲染。当前为初稿，表情先检查可用性，强度与细节后续精修。</p>
<video src="动作预览.mp4" controls loop muted playsinline></video>
<p>3秒头部转动、头发物理、眨眼和张嘴组合。张嘴由测试曲线驱动，尚未接入口播音频。棋盘仅用于MP4预览，透明版本为MOV。</p><section>'''
    for name, label in LABELS.items():
        html += f'<figure><img src="expressions/{name}.png"><figcaption>{label}</figcaption></figure>'
    html += '''</section><p>12fps技术检查样片；自然动作、造型满意度、Warudo和剪映实际使用仍待验证。当前保留v005外观。</p>
<a href="C-character.vrm">VRM模型</a> · <a href="C-character.blend">可编辑工程</a> · <a href="角色透明.mov">透明样片</a></html>'''
    (folder / '预览.html').write_text(html, encoding='utf-8')
    (folder / '使用说明.md').write_text('''# C基础驱动检查包
打开预览.html即可观看，不必操作建模软件。含13种基础驱动、自然状态及两种叠加检查图；3秒样片含头部转动、头发物理、眨眼和程序曲线张嘴。

C-character.blend为可编辑母版，C-character.vrm为VRM1派生。动作预览.mp4含棋盘底，只用于看效果；角色透明.mov含透明通道，用于目标软件技术试验。本批480×600、12fps，面部特写，不能替代正式视频角落素材或自然动作。

已移除原帽子／抽绳的3条动态链，保留8条头发链。物理检查使用60Hz固定步长和半秒预滚，并从中立状态重复运行对照。当前不包含口播音素同步或摄像头跟随；Warudo和剪映尚未实测此版本，造型仍待用户反馈。基础表情强度与细节按用户优先级后置。
''', encoding='utf-8')
    names = ['C-character.vrm', 'C-character.blend', '动作预览.mp4', '角色透明.mov',
             '姿势预览.png', 'rig-report.json', 'frames-complete.json', '预览.html', '使用说明.md']
    names += ['expressions/' + name + '.png' for name in LABELS]
    atomic_json(folder / 'complete.json', {'schema': 1, 'stage': 'rig_draft_not_visual_approved',
                'files': {name: digest(folder / name) for name in names}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.runtime/avatar3d/runtime.json')
    args = parser.parse_args()
    source_review, output = args.source_review.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError('输出目录已存在，请使用新版本目录。')
    report = json.loads((source_review / 'export-report.json').read_text(encoding='utf-8'))
    if digest(source_review / 'C-character.blend') != report['blend_sha256']:
        raise ValueError('源工程哈希不一致。')
    for dependency in ('av', 'numpy', 'PIL'):
        if importlib.util.find_spec(dependency) is None:
            raise ValueError('请使用项目媒体依赖运行环境，缺少：' + dependency)
    runtime = Runtime.load(args.runtime)
    logs = ROOT / '.runtime/avatar3d/character-builds'
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / ('rig-' + str(time.time_ns()) + '.log')
    command = [str(runtime.blender), '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '23', '--python', str(ROOT / 'avatar3d/character_rig_review.py'), '--',
               '--source-review', str(source_review), '--output', str(output), '--addon', str(runtime.addon)]
    env = dict(os.environ)
    env['BLENDER_USER_CONFIG'] = str(logs / 'rig-blender-config')
    env['BLENDER_USER_SCRIPTS'] = str(logs / 'rig-blender-scripts')
    with log_path.open('wb') as log:
        child = launch_external(command, env, log)
        try:
            code = child.wait(timeout=1800)
        except (KeyboardInterrupt, subprocess.TimeoutExpired):
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
            raise
    if code:
        raise RuntimeError(f'驱动检查失败({code})，日志：{log_path}')
    finalize(output)
    print(json.dumps({'output': str(output), 'log': str(log_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
