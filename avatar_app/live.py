"""Qt摄像头与后台推理；仅点击开始后采集，角色输出不包含真人画面。"""
import threading
import time

import numpy as np
from PySide6.QtCore import QThread,Signal,QTimer,Qt
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtMultimedia import QCamera,QMediaCaptureSession,QVideoSink,QMediaDevices
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QPushButton,QComboBox,QCheckBox

from .tracking import MediaPipeEngine,MotionFilter,Motion


class InferenceWorker(QThread):
    observation = Signal(object)
    ready = Signal()
    failed = Signal(str)

    def __init__(self,body=True):
        super().__init__()
        self.body = body
        self.condition = threading.Condition()
        self.pending = None
        self.stopping = False

    def submit(self,rgb):
        with self.condition:
            if not self.stopping:
                self.pending = (rgb,time.monotonic())
                self.condition.notify()

    def stop(self):
        with self.condition:
            self.stopping = True
            self.pending = None
            self.condition.notify()

    def run(self):
        engine = None
        try:
            engine = MediaPipeEngine(body=self.body)
            start = time.monotonic()
            with self.condition:
                if self.stopping:
                    return
            self.ready.emit()
            while True:
                with self.condition:
                    while self.pending is None and not self.stopping:
                        self.condition.wait(.2)
                    if self.stopping:
                        break
                    rgb,stamp = self.pending
                    self.pending = None
                observation = engine.detect(rgb,round((stamp-start)*1000))
                self.observation.emit(observation)
        except Exception as exc:
            self.failed.emit("追踪启动／推理失败："+str(exc))
        finally:
            if engine:
                engine.close()


class LiveCapture(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.worker = None
        self.camera = None
        self.session = None
        self.sink = None
        self.filter = MotionFilter()
        self.last_submit = 0.0
        self.devices = QMediaDevices.videoInputs()
        layout = QVBoxLayout(self)
        self.device = QComboBox()
        for d in self.devices:
            self.device.addItem(d.description())
        if not self.devices:
            self.device.addItem("未发现摄像头")
        layout.addWidget(self.device)
        self.refresh = QPushButton("刷新摄像头列表")
        self.refresh.clicked.connect(self.refresh_devices)
        layout.addWidget(self.refresh)
        self.body = QCheckBox("跟随肩线倾斜（需拍到双肩）")
        self.body.setChecked(True)
        layout.addWidget(self.body)
        self.mirror = QCheckBox("镜像跟随")
        self.mirror.setChecked(True)
        layout.addWidget(self.mirror)
        self.toggle = QPushButton("开启摄像头跟随")
        self.toggle.clicked.connect(self.toggle_capture)
        self.toggle.setEnabled(bool(self.devices))
        layout.addWidget(self.toggle)
        self.center = QPushButton("睁眼闭嘴、正视镜头后校准")
        self.center.clicked.connect(self.calibrate)
        self.center.setEnabled(False)
        layout.addWidget(self.center)
        self.status = QLabel("摄像头未开启。画面在本机处理，不录制；直播画面只有角色。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    @property
    def active(self):
        return self.worker is not None

    def refresh_devices(self):
        if self.active:
            return
        self.devices = QMediaDevices.videoInputs()
        self.device.clear()
        for d in self.devices:
            self.device.addItem(d.description())
        if not self.devices:
            self.device.addItem("未发现摄像头")
        self.toggle.setEnabled(bool(self.devices))

    def toggle_capture(self):
        if self.active:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.active or not self.devices:
            return
        self.filter = MotionFilter()
        worker = InferenceWorker(self.body.isChecked())
        self.worker = worker
        worker.ready.connect(self.start_camera)
        worker.observation.connect(self.received)
        worker.failed.connect(self.failed)
        worker.finished.connect(self.worker_finished)
        self.device.setEnabled(False)
        self.refresh.setEnabled(False)
        self.body.setEnabled(False)
        self.toggle.setText("停止摄像头")
        self.status.setText("正在加载本机追踪模型…")
        worker.start()

    def start_camera(self):
        if not self.worker or self.worker.stopping:
            return
        self.camera = QCamera(self.devices[self.device.currentIndex()],self)
        # 选择较小的真实硬件格式，降低采集／推理开销。
        formats = self.camera.cameraDevice().videoFormats()
        usable = [f for f in formats if f.resolution().width()<=1280 and f.maxFrameRate()>=15]
        if usable:
            self.camera.setCameraFormat(min(usable,key=lambda f:abs(f.resolution().width()-640)))
        self.session = QMediaCaptureSession(self)
        self.sink = QVideoSink(self)
        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self.frame_received)
        self.camera.errorOccurred.connect(lambda *_:self.failed("摄像头错误："+self.camera.errorString()) if self.camera else None)
        self.camera.start()
        self.center.setEnabled(True)
        self.status.setText("摄像头已请求启动，等待人脸。请正视镜头后校准。")

    def frame_received(self,frame):
        if not self.worker or self.worker.stopping or time.monotonic()-self.last_submit<.065:
            return
        image = frame.toImage()
        if image.isNull():
            return
        image = image.scaled(640,480,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)
        image = image.convertToFormat(QImage.Format.Format_RGB888)
        data = np.frombuffer(image.bits(),dtype=np.uint8,count=image.sizeInBytes()).reshape(image.height(),image.bytesPerLine())
        rgb = data[:,:image.width()*3].reshape(image.height(),image.width(),3).copy()
        self.last_submit = time.monotonic()
        self.worker.submit(rgb)

    def received(self,observation):
        if self.worker and not self.worker.stopping:
            self.filter.observe(observation)

    def sample(self):
        if not self.active:
            return Motion(),False
        motion,found = self.filter.sample(mirror=self.mirror.isChecked())
        if self.camera:
            self.status.setText("人脸跟随中 · "+("肩线可见" if self.filter.latest and self.filter.latest.shoulder_roll is not None and found else "未识别肩线")
                                if found else "未识别人脸／数据中断，角色正在回正。")
        return motion,found

    def calibrate(self):
        self.status.setText("已校准居中。" if self.filter.calibrate() else "请先让摄像头识别到正面人脸。")

    def failed(self,message):
        self.status.setText(message)
        self.stop(keep_status=True)

    def stop(self,keep_status=False):
        if self.camera:
            self.camera.stop()
        if self.session:
            self.session.setCamera(None)
            self.session.setVideoSink(None)
        for obj in (self.camera,self.session,self.sink):
            if obj:
                obj.deleteLater()
        self.camera = self.session = self.sink = None
        self.center.setEnabled(False)
        if self.worker:
            self.worker.stop()
            self.toggle.setEnabled(False)
        if not keep_status:
            self.status.setText("摄像头已停止，不再采集。")
        self.filter = MotionFilter()

    def worker_finished(self):
        self.worker = None
        self.device.setEnabled(True)
        self.refresh.setEnabled(True)
        self.body.setEnabled(True)
        self.toggle.setEnabled(bool(self.devices))
        self.toggle.setText("开启摄像头跟随")

    def shutdown(self):
        self.stop()
        return not self.worker or self.worker.wait(5000)


class OutputWindow(QWidget):
    """给OBS等窗口捕获的干净画面。绿幕需在直播软件添加色度键。"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("地球角色直播画面")
        self.setStyleSheet("background:#00ff00;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setStyleSheet("background:#00ff00;")
        layout.addWidget(self.image)
        self.resize(480,720)

    def update_image(self,image):
        # 仅角色RGBA合成到绿底，没有任何摄像头帧传入此窗口。
        from PIL import Image
        background = Image.new("RGBA",image.size,(0,255,0,255))
        background.alpha_composite(image)
        rgb = background.convert("RGB")
        qimage = QImage(rgb.tobytes(),rgb.width,rgb.height,rgb.width*3,QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimage)
        self.image.setPixmap(pixmap.scaled(self.image.size(),Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
