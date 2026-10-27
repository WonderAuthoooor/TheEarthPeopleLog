"""仅显式smoke参数启用的直播准备页集成测试；目标必须是隔离目录。"""
from pathlib import Path
import json
import time
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont,QFontDatabase
from .models import atomic_json


def start(window,fixture,output):
    fixture=json.loads(Path(fixture).read_text(encoding='utf-8'))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    install=Path(fixture['install']).resolve()
    if not install.is_relative_to(window.workspace.resolve()):
        raise ValueError('集成检查只允许恢复到隔离工作区内。')
    window.timer.stop();window.tabs.setCurrentWidget(window.live)
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():QFontDatabase.addApplicationFont(str(font));window.setFont(QFont('Microsoft YaHei UI',10))
    p=window.live;p.package.setText(fixture['package']);p.install.setText(str(install))
    state={'step':0,'start':time.monotonic()}; timer=QTimer(window);window.live_smoke_timer=timer
    def finish(error=''):
        timer.stop();window.grab().save(str(output/'window.png'))
        atomic_json(output/'live-gui-result.json',{'error':error,'steps':state['step'],
                    'plan':p.plan,'status':p.status.text(),'diagnostic':getattr(p,'diagnostic',None),
                    'native_load':'not performed'})
        window.close()
    def tick():
        try:
            if time.monotonic()-state['start']>90:raise TimeoutError('直播准备页检查超时')
            if p.busy or (p.worker and p.worker.isRunning()):return
            if state['step'] and '未完成' in p.status.text():raise RuntimeError(p.status.text())
            if state['step']==0:p.check.click()
            elif state['step']==1:
                assert p.plan['can_restore'] and p.restore.isEnabled();p.restore.click()
            elif state['step']==2:
                assert p.plan['restored'] and p.plan['added']==5;p.check.click()
            elif state['step']==3:
                assert all(x['action']=='reuse' for x in p.plan['items'])
                assert not p.restore.isEnabled()
                p.start('diagnose',install/'Warudo_Data/StreamingAssets'/p.plan['scene'])
            else:
                assert p.diagnostic['configuration_ok'],p.diagnostic
                assert not p.diagnostic['runtime_verified'];finish();return
            state['step']+=1
        except Exception as exc:finish(str(exc))
    timer.timeout.connect(tick);timer.start(100)
