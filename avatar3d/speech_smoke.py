"""显式命令行触发的离屏集成检查；不会在日常启动执行。"""
from pathlib import Path
import json
import time
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from .models import import_model, atomic_json


def start(window, fixture, output):
    fixture = json.loads(Path(fixture).read_text(encoding='utf-8'))
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    window.timer.stop()
    font = Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():QFontDatabase.addApplicationFont(str(font)); window.setFont(QFont('Microsoft YaHei UI',9))
    # 本次聚焦分段按钮链路，省略已有独立覆盖的单段首次姿态渲染。
    info = import_model(window.workspace,fixture['model'])
    window.model.blockSignals(True); window.model.addItem(info['name'],info)
    window.model.setCurrentIndex(window.model.count()-1); window.model.blockSignals(False)
    window.width.setCurrentIndex(window.width.findData(320)); window.fps.setCurrentIndex(window.fps.findData(30))
    window.framing.setCurrentIndex(window.framing.findData('bust'))
    p = window.speech; window.tabs.setCurrentIndex(1)
    state = {'step':0,'start':time.monotonic(),'outputs':[]}
    timer = QTimer(window); timer.setInterval(100); window.project_smoke_timer = timer

    def finish(error=''):
        timer.stop(); window.grab().save(str(output/'window.png'))
        atomic_json(output/'project-gui-result.json',{'error':error,'outputs':state['outputs'],
                    'project':str(p.path),'steps':state['step'],'native_browser_playback':'not verified'})
        window.close()

    def tick():
        try:
            if time.monotonic()-state['start']>900:raise TimeoutError('分段GUI检查超时')
            if p.busy:return
            step = state['step']
            if step and ('失败' in p.status.text() or '未完成：' in p.status.text()):raise RuntimeError(p.status.text())
            if step == 0:
                p.new_button.click(); assert p.document
                p.text.setPlainText('第一段技术验证。'); p.bind_path(fixture['audio_a'])
            elif step == 1:
                assert p.selected().get('audio')
                p.add_button.click(); p.text.setPlainText('第二段技术验证。')
                p.action.setCurrentIndex(p.action.findData('explain')); p.bind_path(fixture['audio_b'])
            elif step == 2:
                p.list.setCurrentRow(0); p.render_one.click()
            elif step in (3,4,5):
                assert p.last_output
                record = json.loads((p.last_output/'complete.json').read_text(encoding='utf-8'))
                state['outputs'].append(str(p.last_output))
                if step == 3:
                    assert len(record['segments'])==1
                    p.render_all.click()
                elif step == 4:
                    assert len(record['segments'])==2 and record['segments'][0]['reused']
                    p.list.setCurrentRow(1); p.up_button.click(); p.render_all.click()
                else:
                    assert all(s['reused'] for s in record['segments'])
                    finish(); return
            state['step'] += 1
        except Exception as exc:finish(str(exc))
    timer.timeout.connect(tick); timer.start()
