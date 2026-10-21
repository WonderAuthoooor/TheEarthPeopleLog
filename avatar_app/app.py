from pathlib import Path
import json
import math
import os
import threading
import time

from PySide6.QtCore import QThread, Signal, QTimer, QUrl, Qt
from PySide6.QtGui import QImage, QPixmap, QIcon,QShortcut,QKeySequence
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QFileDialog,QSpinBox,QComboBox,QCheckBox,QProgressBar,QMessageBox,QSlider,QTabWidget,
    QGridLayout,QDoubleSpinBox,QApplication)

from . import __version__
from .rig import Rig,Envelope,checker
from .export import export_clip,save_json
from .live import LiveCapture,OutputWindow
from .actions import ACTION_NAMES,ACTION_ORDER,ActionController
from .hotkeys import GlobalHotkeys


class RenderWorker(QThread):
    percent = Signal(int)
    result = Signal(str,str)

    def __init__(self,request):
        super().__init__()
        self.request = request
        self.cancel = threading.Event()

    def run(self):
        try:
            folder = export_clip(**self.request,cancel=self.cancel,progress=self.percent.emit)
            self.result.emit(str(folder),"")
        except Exception as exc:
            self.result.emit("",str(exc))


class Window(QMainWindow):
    def __init__(self,workspace,smoke=None):
        super().__init__()
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True,exist_ok=True)
        self.setWindowTitle(f"地球人日志 · 角色工坊 {__version__}（分层试验版）")
        self.setWindowIcon(QIcon(str(Path(__file__).parent/"assets/app-icon.ico")))
        self.rig = Rig(scale=360/1024)
        self.actions=ActionController()
        self.source_mode=0
        self.audio = None
        self.envelope = None
        self.worker = None
        self.output = None
        self.playing = False
        self.elapsed = 0.0
        self.blink_until = 0.0
        self.smoke = smoke
        self.started = time.monotonic()
        self.player = QMediaPlayer(self)
        self.speaker = QAudioOutput(self)
        self.player.setAudioOutput(self.speaker)
        self.player.errorOccurred.connect(lambda *_: self.status.setText("音频预览失败："+self.player.errorString()))
        root = QWidget()
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        self.image = QLabel()
        self.image.setFixedSize(360,540)
        row.addWidget(self.image)
        self.tabs = QTabWidget()
        row.addWidget(self.tabs)
        offline = QWidget()
        controls = QVBoxLayout(offline)
        self.tabs.addTab(offline,"口播素材")
        title = QLabel("C · 深色发通讯员")
        title.setStyleSheet("font-size:22px;font-weight:bold")
        controls.addWidget(title)
        note = QLabel("口播＋表情／手势预设，透明导出供剪映。\n本版为自定义2D绑定，不是标准Live2D模型。")
        note.setWordWrap(True)
        controls.addWidget(note)
        self.choose = QPushButton("选择本地口播音频…")
        self.choose.clicked.connect(self.choose_audio)
        controls.addWidget(self.choose)
        self.clear_audio = QPushButton("清除音频，制作待机素材")
        self.clear_audio.clicked.connect(self.clear)
        controls.addWidget(self.clear_audio)
        self.audio_label = QLabel("未选音频：导出静音待机动作")
        self.audio_label.setWordWrap(True)
        controls.addWidget(self.audio_label)
        self.play = QPushButton("播放／暂停预览")
        self.play.clicked.connect(self.toggle)
        controls.addWidget(self.play)
        self.blink_button = QPushButton("测试眨眼")
        self.blink_button.clicked.connect(lambda: setattr(self,"blink_until",time.monotonic()+.14))
        controls.addWidget(self.blink_button)
        controls.addWidget(QLabel("转头方向（小幅网格变形）"))
        self.yaw = QSlider(Qt.Orientation.Horizontal)
        self.yaw.setRange(-100,100)
        controls.addWidget(self.yaw)
        self.auto = QCheckBox("自动小幅转头（导出沿用）")
        self.auto.setChecked(True)
        controls.addWidget(self.auto)
        self.duration = QSpinBox()
        self.duration.setRange(1,180)
        self.duration.setValue(6)
        self.duration.setSuffix(" 秒 · 无音频时长")
        controls.addWidget(self.duration)
        self.width = QComboBox()
        for w in (480,720,1080):
            self.width.addItem(f"{w} × {w*3//2}",w)
        self.width.setCurrentIndex(1)
        controls.addWidget(self.width)
        self.export_action=QComboBox()
        for key,label in ACTION_NAMES.items():self.export_action.addItem(label,key)
        self.export_action.currentIndexChanged.connect(lambda _:self.trigger_action(self.export_action.currentData()))
        controls.addWidget(self.export_action)
        self.export = QPushButton("导出透明MOV ＋ 棋盘预览")
        self.export.clicked.connect(self.start_export)
        controls.addWidget(self.export)
        self.cancel = QPushButton("取消导出")
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(lambda: self.worker.cancel.set() if self.worker else None)
        controls.addWidget(self.cancel)
        self.progress = QProgressBar()
        controls.addWidget(self.progress)
        self.status = QLabel("MOV带透明通道、无声音。剪映中叠回原口播音轨。")
        self.status.setWordWrap(True)
        controls.addWidget(self.status)
        self.open = QPushButton("打开导出目录")
        self.open.clicked.connect(lambda: os.startfile(str(self.output or self.workspace/"exports")))
        self.open.setEnabled(False)
        controls.addWidget(self.open)
        controls.addStretch()
        live_page = QWidget()
        live_layout = QVBoxLayout(live_page)
        live_title = QLabel("摄像头直播 · C通讯员")
        live_title.setStyleSheet("font-size:20px;font-weight:bold")
        live_layout.addWidget(live_title)
        live_layout.addWidget(QLabel("跟随眼口、轻微头动和肩线倾斜。\n表情动作页可叠加手势；没有实时手指捕捉。"))
        self.live = LiveCapture()
        live_layout.addWidget(self.live)
        self.output_window = OutputWindow()
        output_button = QPushButton("打开独立直播画面（绿幕）")
        output_button.clicked.connect(self.show_output)
        live_layout.addWidget(output_button)
        capture_note = QLabel("直播软件添加“窗口捕获”，选择“地球角色直播画面”，\n再用绿色色度键去底；麦克风声音由直播软件采集。\n保持画面窗口显示，避免最小化。当前未接入虚拟摄像头。")
        capture_note.setWordWrap(True)
        live_layout.addWidget(capture_note)
        live_layout.addStretch()
        self.tabs.addTab(live_page,"直播跟随")
        action_page=QWidget();action_layout=QVBoxLayout(action_page)
        self.action_label=QLabel("当前：待机")
        self.action_label.setStyleSheet("font-size:20px;font-weight:bold")
        action_layout.addWidget(self.action_label)
        action_layout.addWidget(QLabel("点击切换；预设持续到下一次切换。\n可叠加当前口播／面捕，本页不会自动打开摄像头。"))
        grid=QGridLayout();action_layout.addLayout(grid)
        self.action_buttons={};self.shortcuts=[]
        for i,key in enumerate(ACTION_ORDER):
            shortcut='Alt+0' if i==0 else f'F{i}'
            button=QPushButton(f'{ACTION_NAMES[key]} · {shortcut}')
            button.clicked.connect(lambda checked=False,k=key:self.trigger_action(k))
            grid.addWidget(button,i//3,i%3);self.action_buttons[key]=button
            binding=QShortcut(QKeySequence(shortcut),self)
            binding.setContext(Qt.ShortcutContext.ApplicationShortcut)
            binding.activated.connect(lambda k=key:self.trigger_action(k))
            self.shortcuts.append(binding)
        self.score_confirm=QCheckBox("显示已人工确认的本条评分")
        self.score_value=QDoubleSpinBox();self.score_value.setRange(-5,5);self.score_value.setSingleStep(.5);self.score_value.setDecimals(1)
        self.score_value.setSuffix(' 分');self.score_value.setEnabled(False)
        self.score_value.valueChanged.connect(lambda value:self.score_value.setValue(round(value*2)/2) if abs(value*2-round(value*2))>1e-8 else None)
        self.score_confirm.toggled.connect(self.score_value.setEnabled)
        action_layout.addWidget(self.score_confirm);action_layout.addWidget(self.score_value)
        action_layout.addWidget(QLabel("未勾选显示待评；只改牌面，不自动评分或记账。"))
        self.global_keys=QCheckBox("启用后台快捷键 Ctrl+Alt+0—9 / A")
        self.global_keys.toggled.connect(self.toggle_global_keys)
        action_layout.addWidget(self.global_keys)
        self.action_note=QLabel("F1—F10需本应用获得焦点；后台快捷键默认关闭。")
        self.action_note.setWordWrap(True);action_layout.addWidget(self.action_note)
        self.demo_export=QPushButton("导出全部动作合集（静音）")
        self.demo_export.clicked.connect(lambda:self.start_export(demo=True))
        action_layout.addWidget(self.demo_export);action_layout.addStretch()
        self.tabs.addTab(action_page,"表情动作")
        self.hotkeys=GlobalHotkeys(self.trigger_action)
        QApplication.instance().installNativeEventFilter(self.hotkeys)
        self.tabs.currentChanged.connect(self.mode_changed)
        self.resize(810,590)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.load_settings()
        if smoke:
            QTimer.singleShot(200,self.smoke_start)

    def mode_changed(self,index):
        if index in (0,1):
            self.source_mode=index
            self.player.pause()
            self.playing = False
        if index==0:
            self.live.stop()
            self.output_window.hide()

    def trigger_action(self,key):
        self.actions.trigger(key)
        self.action_label.setText('当前：'+ACTION_NAMES[key])
        index=self.export_action.findData(key)
        if index!=self.export_action.currentIndex():
            self.export_action.blockSignals(True);self.export_action.setCurrentIndex(index);self.export_action.blockSignals(False)

    def toggle_global_keys(self,enabled):
        try:
            if enabled:
                self.hotkeys.enable(ACTION_ORDER)
                self.action_note.setText('后台Ctrl+Alt+0待机，1—8对应前八动作，9大笑，A生气。关闭应用即释放。')
            else:
                self.hotkeys.disable()
                self.action_note.setText('后台快捷键已释放；F1—F10在本应用内可用。')
        except Exception as exc:
            self.global_keys.blockSignals(True);self.global_keys.setChecked(False);self.global_keys.blockSignals(False)
            self.action_note.setText(str(exc))

    def current_score(self):
        return f'{self.score_value.value():+.1f}' if self.score_confirm.isChecked() else '待评'

    def show_output(self):
        self.output_window.show()
        self.output_window.raise_()

    def load_settings(self):
        path = self.workspace/"settings.json"
        if path.exists():
            try:
                cfg = json.loads(path.read_text(encoding="utf-8"))
                self.duration.setValue(int(cfg.get("duration",6)))
                self.auto.setChecked(bool(cfg.get("turn",True)))
                self.yaw.setValue(round(float(cfg.get("fixed_turn",0))*100))
                index = self.width.findData(cfg.get("width",720))
                if index >= 0:
                    self.width.setCurrentIndex(index)
            except (ValueError,TypeError):
                self.status.setText("上次设置无法读取，已用默认值；旧文件保留。")

    def choose_audio(self):
        path,_ = QFileDialog.getOpenFileName(self,"选择口播音频","","音频 (*.wav *.mp3 *.m4a *.aac *.flac *.ogg);;所有文件 (*)")
        if path:
            try:
                self.set_audio(path)
            except Exception as exc:
                QMessageBox.warning(self,"无法读取音频",str(exc))

    def set_audio(self,path):
        envelope = Envelope(path)
        self.player.stop()
        self.audio = Path(path)
        self.envelope = envelope
        self.player.setSource(QUrl.fromLocalFile(str(self.audio)))
        self.audio_label.setText(f"{self.audio.name} · {envelope.duration:.2f}秒\n口型方式：音量开合，非逐字对齐")
        self.duration.setEnabled(False)
        self.playing = False
        self.elapsed = 0

    def clear(self):
        self.player.stop()
        self.audio = self.envelope = None
        self.playing = False
        self.elapsed = 0
        self.duration.setEnabled(True)
        self.audio_label.setText("未选音频：导出静音待机动作")

    def toggle(self):
        if self.audio:
            if self.playing:
                self.player.pause()
            else:
                if self.player.position() >= self.envelope.duration*1000-100:
                    self.player.setPosition(0)
                self.player.play()
        else:
            self.started = time.monotonic()-self.elapsed
        self.playing = not self.playing

    def tick(self):
        if self.worker and self.worker.isRunning():
            return
        pose=self.actions.sample()
        if self.source_mode==1:
            t = time.monotonic()-self.started
            motion,found = self.live.sample()
            if self.live.active:
                # 真实追踪和丢失回正均使用同一参数；无脸时不伪造面捕。
                frame = self.rig.frame(t,(360,540),**motion.kwargs(),pose=pose,score=self.current_score())
            else:
                frame = self.rig.frame(t,(360,540),pose=pose,score=self.current_score())
            self.display_frame(frame)
            return
        if self.audio:
            t = self.player.position()/1000
        else:
            t = time.monotonic()-self.started if self.playing else self.elapsed
        self.elapsed = t
        yaw = math.sin(t*2*math.pi/7)*.7 if self.auto.isChecked() else self.yaw.value()/100
        frame = self.rig.frame(t,(360,540),self.envelope.at(t) if self.envelope else 0,yaw,
            1.0 if time.monotonic() < self.blink_until else None,pose=pose,score=self.current_score())
        self.display_frame(frame)

    def display_frame(self,frame):
        picture = checker(frame)
        qimage = QImage(picture.tobytes(),360,540,360*3,QImage.Format.Format_RGB888).copy()
        self.image.setPixmap(QPixmap.fromImage(qimage))
        if self.output_window.isVisible():
            self.output_window.update_image(frame)

    def start_export(self,checked=False,demo=False):
        if self.worker and self.worker.isRunning():
            return
        if self.live.active or self.output_window.isVisible():
            self.action_note.setText('请先停止摄像头并关闭独立直播画面，再导出素材，避免直播画面暂停。')
            return
        self.player.pause()
        self.playing = False
        cfg = {"duration":self.duration.value(),"width":self.width.currentData(),"turn":self.auto.isChecked(),"fixed_turn":self.yaw.value()/100}
        try:
            save_json(self.workspace/"settings.json",cfg)
        except OSError as exc:
            self.status.setText("工作区无法写入："+str(exc))
            return
        request = dict(cfg,destination=self.workspace/"exports",audio=None if demo else self.audio,
                       action='all' if demo else self.export_action.currentData(),score_text='待评' if demo else self.current_score())
        self.worker = RenderWorker(request)
        self.worker.percent.connect(self.progress.setValue)
        self.worker.result.connect(self.export_result)
        self.worker.finished.connect(lambda: self.set_busy(False))
        self.set_busy(True)
        self.progress.setValue(0)
        self.status.setText("正在生成透明角色素材…")
        self.worker.start()

    def set_busy(self,busy):
        self.tabs.setTabEnabled(1,not busy)
        self.tabs.setTabEnabled(2,not busy or self.tabs.currentIndex()==2)
        self.demo_export.setEnabled(not busy)
        for control in (self.export,self.choose,self.clear_audio,self.play,self.auto,self.width,self.yaw,self.blink_button):
            control.setEnabled(not busy)
        self.cancel.setEnabled(busy)

    def export_result(self,folder,error):
        if error:
            self.status.setText(error)
        else:
            self.output = Path(folder)
            self.open.setEnabled(True)
            self.status.setText("已完成。透明MOV放入剪映上层轨道，与原音频起点对齐。")
        if self.smoke:
            self.grab().save(str(self.smoke/"window.png"))
            save_json(self.smoke/"gui-result.json",{"folder":folder,"error":error})
            QTimer.singleShot(300,self.close)

    def smoke_start(self):
        self.smoke.mkdir(parents=True,exist_ok=True)
        audio = self.smoke/"speech.wav"
        if audio.exists():
            self.set_audio(audio)
        self.width.setCurrentIndex(0)
        self.duration.setValue(1)
        self.start_export()

    def closeEvent(self,event):
        if not self.live.shutdown():
            self.status.setText("追踪正在停止，请稍候再关闭。")
            event.ignore()
            return
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            if not self.worker.wait(5000):
                self.status.setText("正在停止导出，请稍候再关闭。")
                event.ignore()
                return
        self.player.stop()
        self.output_window.close()
        self.hotkeys.disable()
        QApplication.instance().removeNativeEventFilter(self.hotkeys)
        event.accept()
