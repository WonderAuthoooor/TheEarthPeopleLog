from pathlib import Path
import json,threading,os,uuid
from PySide6.QtCore import QThread,Signal,QTimer,Qt,QUrl
from PySide6.QtGui import QPixmap,QDesktopServices,QIcon
from PySide6.QtWidgets import (QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,QPushButton,QComboBox,
    QDoubleSpinBox,QFileDialog,QListWidget,QMessageBox,QProgressBar)
from . import __version__
from .contracts import RenderSpec,ACTIONS
from .models import import_model
from .service import RenderService
from .backend import Runtime,BlenderBackend
from .motion_exchange import export_exchange,verify_exchange

class ExchangeWorker(QThread):
    progress=Signal(int);result=Signal(str,str)
    def __init__(self,source,model,destination,runtime):
        super().__init__();self.source=source;self.model=model;self.destination=destination
        self.runtime=runtime;self.cancel=threading.Event()
    def run(self):
        try:self.result.emit(str(export_exchange(self.source,self.model,self.destination,self.runtime,self.cancel,self.progress.emit)),'')
        except Exception as exc:self.result.emit('',str(exc)+'\n诊断目录：'+str(self.destination))

class Worker(QThread):
    progress=Signal(int);result=Signal(str,str)
    def __init__(self,service,ident):
        super().__init__();self.service=service;self.ident=ident;self.cancel=threading.Event()
    def run(self):
        try:self.result.emit(str(self.service.run(self.ident,self.cancel,self.progress.emit)),'')
        except Exception as exc:self.result.emit('',str(exc))

class Window(QMainWindow):
    def __init__(self,workspace,runtime,sample,smoke=None,smoke_exchange=False):
        super().__init__();self.workspace=Path(workspace);self.runtime=Runtime.load(runtime)
        self.service=RenderService(workspace,BlenderBackend(self.runtime));self.service.jobs.recover()
        self.worker=None;self.exchange_worker=None;self.last_exchange=None
        self.current=None;self.last_output=None;self.smoke=smoke;self.smoke_exchange=smoke_exchange
        self.setWindowTitle('地球人日志 · 三维角色工坊 '+__version__)
        self.setWindowIcon(QIcon(str(Path(__file__).parent/'assets/app-icon.ico')))
        root=QWidget();self.setCentralWidget(root);row=QHBoxLayout(root)
        self.picture=QLabel('导入VRM模型，生成姿势预览或动画。\n当前为离线三维验证，尚无实时拖拽骨架／直播。')
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter);self.picture.setFixedSize(400,600);self.picture.setStyleSheet('background:#293139;color:#d8eee9;')
        row.addWidget(self.picture);controls=QVBoxLayout();row.addLayout(controls)
        title=QLabel('3D骨骼 · 卡通渲染');title.setStyleSheet('font-size:22px;font-weight:600');controls.addWidget(title)
        self.model=QComboBox();self.model.currentIndexChanged.connect(self.select_model);controls.addWidget(self.model)
        choose=QPushButton('导入本地VRM模型…');choose.clicked.connect(self.choose_model);controls.addWidget(choose)
        self.demo=QPushButton('加载官方测试模型并预览');self.demo.clicked.connect(lambda:self.load_model(sample));controls.addWidget(self.demo)
        self.info=QLabel('正式C模型尚未建成；测试模型不会替代C。');self.info.setWordWrap(True);controls.addWidget(self.info)
        self.action=QComboBox()
        for key,name in ACTIONS.items():self.action.addItem(name,key)
        controls.addWidget(self.action)
        self.angle=QComboBox()
        for label,value in (('正面',0),('左侧45°',45),('右侧45°',-45),('侧面90°',90)):self.angle.addItem(label,value)
        controls.addWidget(self.angle)
        self.width=QComboBox()
        for width in (320,480,720,1080):self.width.addItem(f'{width} × {width*3//2}',width)
        self.width.setCurrentIndex(1);controls.addWidget(self.width)
        self.duration=QDoubleSpinBox();self.duration.setRange(.5,30);self.duration.setValue(3);self.duration.setSuffix(' 秒');controls.addWidget(self.duration)
        self.preview=QPushButton('生成短姿势预览');self.preview.clicked.connect(lambda:self.add_job(True));controls.addWidget(self.preview)
        self.export=QPushButton('生成动画＋透明MOV');self.export.clicked.connect(lambda:self.add_job(False));controls.addWidget(self.export)
        self.cancel=QPushButton('取消当前任务');self.cancel.clicked.connect(self.cancel_active);controls.addWidget(self.cancel)
        self.progress=QProgressBar();controls.addWidget(self.progress)
        self.status=QLabel('先确认模型比例，再扩展动作。');self.status.setWordWrap(True);controls.addWidget(self.status)
        self.list=QListWidget();self.list.setMaximumHeight(110);controls.addWidget(self.list)
        retry=QPushButton('重试选中的失败／中断任务');retry.clicked.connect(self.retry);controls.addWidget(retry)
        play=QPushButton('播放最近完成的动作预览');play.clicked.connect(self.play);controls.addWidget(play)
        self.exchange=QPushButton('导出选中动作交换包（FBX）');self.exchange.clicked.connect(self.export_motion);controls.addWidget(self.exchange)
        exchange_open=QPushButton('打开最近导出的动作交换包');exchange_open.clicked.connect(self.open_exchange);controls.addWidget(exchange_open)
        output=QPushButton('打开选中任务／诊断目录');output.clicked.connect(self.open_folder);controls.addWidget(output)
        controls.addStretch();self.resize(850,650)
        for path in sorted((self.workspace/'models').glob('*.json')):
            try:
                info=json.loads(path.read_text(encoding='utf-8'));self.model.addItem(info['name'],info)
            except (ValueError,KeyError):pass
        self.timer=QTimer(self);self.timer.timeout.connect(self.dispatch);self.timer.start(300)
        self.refresh()
        if self.model.currentData() and not smoke:
            QTimer.singleShot(0,lambda:self.ensure_model_preview(self.model.currentData()))
        if smoke:QTimer.singleShot(200,lambda:self.smoke_start(sample))

    def load_model(self,path):
        try:
            self.status.setText('正在导入模型…')
            info=import_model(self.workspace,path)
            found=-1
            for i in range(self.model.count()):
                if self.model.itemData(i)['sha256']==info['sha256']:found=i;break
            if found<0:
                self.model.addItem(info['name'],info);found=self.model.count()-1
            self.model.setCurrentIndex(found)
            self.select_model(found)
            self.ensure_model_preview(info)
        except Exception as exc:self.status.setText('导入失败：'+str(exc))

    def choose_model(self):
        path,_=QFileDialog.getOpenFileName(self,'选择标准VRM模型','','VRM模型 (*.vrm)')
        if path:self.load_model(path)

    def select_model(self,index):
        if not hasattr(self,'info'):return
        info=self.model.currentData()
        if info:
            meta=info['metadata'];authors=meta.get('authors',[meta.get('author','未填写')])
            self.info.setText(f"{info['name']} · VRM {info['vrm_version']} · {len(info['bones'])}映射骨骼\n作者：{', '.join(authors)}\n"+
                ('官方测试模型，非C角色。\n' if info['name']=='Seed-san' else '')+'使用范围以模型元数据与来源约定为准。')
            self.picture.clear()
            self.picture.setText('已选择：'+info['name']+'\n正在检查预览…')
            if hasattr(self,'timer'):self.ensure_model_preview(info)

    @staticmethod
    def model_preview_spec(info):
        return RenderSpec(info['sha256'],'neutral',.5,320,12,0)

    def show_picture(self,path):
        pixmap=QPixmap(str(path))
        if pixmap.isNull():raise ValueError('模型预览图片无法读取。')
        self.picture.setPixmap(pixmap.scaled(self.picture.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def ensure_model_preview(self,info):
        spec=self.model_preview_spec(info)
        existing=self.service.jobs.matching(spec,('complete',))
        if existing:
            try:
                folder=self.service.completed_folder(existing)
                self.show_picture(folder/'姿势预览.png');self.last_output=folder
                self.status.setText('已加载 '+info['name']+'，显示已有模型预览。可选择动作和视角继续生成。')
                return
            except (OSError,ValueError,KeyError):pass
        pending=self.service.jobs.matching(spec,('queued','running'))
        if pending:
            self.picture.clear();self.picture.setText('已加载：'+info['name']+'\n首次预览正在生成或排队，请稍候…')
            self.status.setText('已加载 '+info['name']+'，首次预览正在生成或排队；无需重复点击。')
            return
        self.service.jobs.add(spec)
        self.picture.clear();self.picture.setText('已加载：'+info['name']+'\n正在生成首次预览，请稍候…')
        self.refresh();self.dispatch()
        self.status.setText('已加载 '+info['name']+'，正在生成首次预览；首次材质编译可能需要较长时间。')

    def add_job(self,preview):
        info=self.model.currentData()
        if not info:self.status.setText('请先导入模型或加载技术测试模型。');return
        try:
            spec=RenderSpec(info['sha256'],self.action.currentData(),.5 if preview else self.duration.value(),self.width.currentData(),12 if preview else 24,self.angle.currentData())
            self.service.jobs.add(spec);self.status.setText('任务已入队。模型、动作和参数已保存快照。');self.refresh();self.dispatch()
        except Exception as exc:self.status.setText(str(exc))

    def dispatch(self):
        if self.worker and self.worker.isRunning():return
        if self.exchange_worker and self.exchange_worker.isRunning():return
        ident=self.service.jobs.next_queued()
        if not ident:return
        self.current=ident;self.worker=Worker(self.service,self.current)
        self.worker.progress.connect(self.progress.setValue);self.worker.result.connect(self.finished)
        self.worker.start();self.status.setText('正在独立进程中渲染；界面可继续入队。');self.refresh()

    def finished(self,folder,error):
        if error:self.status.setText(error+'\n日志已保留，可重试。')
        else:
            self.last_output=Path(folder)
            request=json.loads((self.last_output/'request.json').read_text(encoding='utf-8'))
            selected=self.model.currentData()
            if selected and selected['sha256']==request['model_sha256']:
                self.show_picture(self.last_output/'姿势预览.png')
            self.status.setText('已完成。透明MOV供剪映；scene.blend保留可编辑模型与骨架。')
        self.refresh()
        if self.smoke:
            if not error:
                count=len(self.service.jobs.list())
                self.demo.click()
                assert len(self.service.jobs.list())==count,'重复加载不应再排队'
                assert self.picture.pixmap() and not self.picture.pixmap().isNull()
                if self.smoke_exchange:
                    self.exchange.click()
                    return
            self.grab().save(str(self.smoke/'window.png'))
            from .models import atomic_json
            atomic_json(self.smoke/'gui-result.json',{'folder':folder,'error':error,
                'load_button_auto_preview':not bool(error),'repeated_click_reuses_preview':not bool(error)})
            QTimer.singleShot(500,self.close)

    def refresh(self):
        self.list.clear()
        for row in self.service.jobs.list():
            self.list.addItem(f"{row['id'][:8]} · {row['status']} · {row['progress']}%")
            self.list.item(self.list.count()-1).setData(Qt.ItemDataRole.UserRole,row['id'])

    def retry(self):
        item=self.list.currentItem()
        if item:
            try:self.service.jobs.retry(item.data(Qt.ItemDataRole.UserRole));self.refresh();self.dispatch()
            except Exception as exc:self.status.setText(str(exc))

    def play(self):
        item=self.list.currentItem()
        ident=item.data(Qt.ItemDataRole.UserRole) if item else (self.last_output.name if self.last_output else None)
        if ident:
            try:
                folder=self.service.completed_folder(ident)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder/'动作预览.mp4')))
            except Exception as exc:self.status.setText(str(exc))

    def open_folder(self):
        item=self.list.currentItem()
        folder=self.workspace/'jobs'/item.data(Qt.ItemDataRole.UserRole) if item else (self.last_output or self.workspace/'jobs')
        folder.mkdir(parents=True,exist_ok=True);os.startfile(str(folder))

    def export_motion(self):
        if ((self.worker and self.worker.isRunning()) or
                (self.exchange_worker and self.exchange_worker.isRunning())):
            self.status.setText('请等待当前任务完成，或先取消当前任务，再导出动作包。');return
        item=self.list.currentItem()
        ident=item.data(Qt.ItemDataRole.UserRole) if item else (self.last_output.name if self.last_output else None)
        if not ident:self.status.setText('请先生成动画，再选择已完成任务导出动作包。');return
        try:
            source=self.service.completed_folder(ident)
            record=json.loads((source/'complete.json').read_text(encoding='utf-8'))
            model=self.workspace/'models'/(record['model_sha256']+'.vrm')
            destination=self.workspace/'exchanges'/(ident[:8]+'-'+uuid.uuid4().hex[:8])
            self.exchange_worker=ExchangeWorker(source,model,destination,self.runtime)
            self.exchange_worker.progress.connect(self.progress.setValue)
            self.exchange_worker.result.connect(self.exchange_finished)
            self.exchange_worker.start()
            self.status.setText('正在导出骨骼动作并重导入检查；模型和原任务会保留。')
        except Exception as exc:self.status.setText('动作包导出失败：'+str(exc))

    def exchange_finished(self,folder,error):
        if error:self.status.setText('动作包导出失败：'+error)
        else:
            self.last_exchange=Path(folder)
            self.status.setText('动作包已完成，可打开目录。FBX往返检查通过；Unity／Warudo播放仍待验证。')
        if self.smoke and self.smoke_exchange:
            from .models import atomic_json
            if not error:verify_exchange(folder)
            self.grab().save(str(self.smoke/'window.png'))
            atomic_json(self.smoke/'gui-exchange-result.json',{'folder':folder,'error':error,
                'public_export_button':not bool(error),'worker':self.exchange_worker.__class__.__name__})
            QTimer.singleShot(500,self.close)

    def open_exchange(self):
        if not self.last_exchange:self.status.setText('请先导出动作交换包。');return
        try:
            verify_exchange(self.last_exchange);os.startfile(str(self.last_exchange))
        except Exception as exc:self.status.setText(str(exc))

    def cancel_active(self):
        for worker in (self.worker,self.exchange_worker):
            if worker and worker.isRunning():worker.cancel.set()

    def smoke_start(self,sample):
        self.smoke.mkdir(parents=True,exist_ok=True)
        self.demo.click();self.demo.click()
        assert len(self.service.jobs.list())==1,'连点加载按钮不能生成重复预览'
        self.grab().save(str(self.smoke/'loading.png'))

    def closeEvent(self,event):
        self.timer.stop()
        for worker in (self.worker,self.exchange_worker):
            if worker and worker.isRunning():
                worker.cancel.set()
                if not worker.wait(15000):self.status.setText('正在停止本任务，请稍候再关闭。');event.ignore();self.timer.start(300);return
        event.accept()
