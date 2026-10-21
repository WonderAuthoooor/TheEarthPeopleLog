"""开发验收：公开样例图→Qt视频帧→后台模型→角色窗口；绝不启用摄像头。"""
from dataclasses import asdict
from pathlib import Path
import sys,time

import numpy as np
from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoFrame

from .app import Window
from .live import InferenceWorker
from .tracking import MediaPipeEngine
from .export import save_json


def check_live(app,folder):
    folder=Path(folder).resolve()
    portrait=Image.open(folder/'portrait.jpg').convert('RGB')
    pose=Image.open(folder/'pose.jpg').convert('RGB')
    portrait.thumbnail((640,480));pose.thumbnail((640,480))
    engine=MediaPipeEngine()
    try:
        engine.detect(np.array(pose),0)
        pose_angle=engine.last_shoulder
        observation=engine.detect(np.array(portrait),1000)
        assert observation is not None,'公开人像样例未识别人脸'
        assert pose_angle is not None,'公开姿态样例未识别肩线'
    finally:
        engine.close()
    window=Window(folder/'workspace')
    window.show();window.tabs.setCurrentIndex(1);window.show_output()
    assert window.live.camera is None
    rgb=portrait.tobytes()
    qimage=QImage(rgb,portrait.width,portrait.height,portrait.width*3,QImage.Format.Format_RGB888).copy()
    video=QVideoFrame(qimage)
    assert not video.toImage().isNull()
    worker=InferenceWorker(body=True)
    window.live.worker=worker
    received=[];errors=[]
    worker.observation.connect(lambda result:(received.append(result),window.live.received(result)))
    worker.ready.connect(lambda:window.live.frame_received(video))
    worker.failed.connect(errors.append)
    worker.finished.connect(window.live.worker_finished)
    worker.start()
    deadline=time.monotonic()+15
    try:
        while not received and not errors and time.monotonic()<deadline:
            app.processEvents();time.sleep(.005)
        assert not errors,errors
        assert received and received[0] is not None,'后台线程未返回人脸'
        window.live.status.setText('公开样例图驱动测试；未开启真实摄像头。')
        window.tick();app.processEvents()
        window.grab().save(str(folder/'live-window.png'))
        window.output_window.grab().save(str(folder/'output-window.png'))
        assert window.live.camera is None
        report={'frozen':bool(getattr(sys,'frozen',False)),
                'face_observation':asdict(observation),'pose_shoulder_angle':pose_angle,
                'thread_observation':asdict(received[0]),'qt_frame_conversion':True,
                'camera_started':False,'input':'公开静态样例，非真人摄像头试用'}
        save_json(folder/'live-result.json',report)
    finally:
        worker.stop()
        assert worker.wait(5000),'追踪线程未按时停止'
        app.processEvents();window.close();app.processEvents()
    return 0


def check_actions(app,folder):
    """真实Qt按钮／快捷键信号→预览→后台透明导出，不开启摄像头或注册全局键。"""
    from .actions import ACTION_ORDER
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    window=Window(folder/'workspace');window.show();window.tabs.setCurrentIndex(2)
    try:
        for key in ACTION_ORDER:
            window.action_buttons[key].click()
            assert window.actions.action==key
        window.shortcuts[7].activated.emit()
        assert window.actions.action=='wave'
        window.score_value.setValue(1.3)
        assert window.score_value.value()==1.5
        assert window.current_score()=='待评'
        window.score_confirm.setChecked(True)
        assert window.current_score()=='+1.5'
        window.action_buttons['score'].click();window.actions.since-=1
        window.tick();app.processEvents()
        window.grab().save(str(folder/'actions-window.png'))
        assert not window.hotkeys.registered and window.live.camera is None
        window.tabs.setCurrentIndex(1);window.show_output();window.tabs.setCurrentIndex(2)
        assert window.source_mode==1
        window.tick();app.processEvents()
        window.output_window.grab().save(str(folder/'score-output.png'))
        window.start_export();assert window.worker is None,'直播输出显示时必须阻止导出冻结'
        window.output_window.hide();window.tabs.setCurrentIndex(0)
        window.width.setCurrentIndex(0);window.duration.setValue(1)
        window.start_export()
        deadline=time.monotonic()+90
        while window.worker.isRunning() and time.monotonic()<deadline:
            app.processEvents();time.sleep(.005)
        assert not window.worker.isRunning(),'动作导出超时'
        app.processEvents()
        assert window.output and (window.output/'角色透明.mov').is_file(),window.status.text()
        save_json(folder/'actions-result.json',{'frozen':bool(getattr(sys,'frozen',False)),
            'actions':list(ACTION_ORDER),'ui_buttons':True,'application_shortcut_signal':True,
            'score_default_pending':True,'score_step':.5,'export':str(window.output),
            'live_export_guard':True,'camera_started':False,'global_hotkeys_registered':False})
    finally:
        window.close();app.processEvents()
    return 0
