"""直播素材准备页；Qt只负责交互，复用可独立测试的打包恢复服务。"""
import json
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit
from .live_package import plan_restore, restore_package
from .models import atomic_json
from .live_diagnostics import inspect_scene, format_report


class LiveWorker(QThread):
    result = Signal(object, str)
    def __init__(self, operation, package, install, parent, scene=None):
        super().__init__(parent); self.operation=operation; self.package=package; self.install=install; self.scene=scene
    def run(self):
        try:
            if self.operation == 'diagnose':
                self.result.emit(inspect_scene(self.scene, self.install, self.package), '')
                return
            function = restore_package if self.operation == 'restore' else plan_restore
            self.result.emit(function(self.package, self.install), '')
        except Exception as exc: self.result.emit(None, str(exc))


class LivePanel(QWidget):
    def __init__(self, workspace, parent=None):
        super().__init__(parent); self.workspace=Path(workspace); self.worker=None; self.busy=False; self.plan=None
        layout=QVBoxLayout(self)
        title=QLabel('直播准备 · Warudo素材'); title.setStyleSheet('font-size:22px;font-weight:600'); layout.addWidget(title)
        intro=QLabel('把角色、动作和场景一起检查，再恢复到Warudo。实时动作与摄像头跟随在Warudo中使用。')
        intro.setWordWrap(True); layout.addWidget(intro)
        self.package=QLineEdit(); self.install=QLineEdit(); self.browse=[]
        for label, field in [('直播素材包目录（包含manifest.json）',self.package),('Warudo安装目录（包含Warudo.exe）',self.install)]:
            layout.addWidget(QLabel(label)); row=QHBoxLayout(); row.addWidget(field)
            button=QPushButton('选择目录…'); button.clicked.connect(lambda checked=False,f=field:self.choose(f))
            self.browse.append(button); row.addWidget(button); layout.addLayout(row)
            field.textChanged.connect(self.invalidate)
        row=QHBoxLayout(); self.check=QPushButton('检查素材与安装情况'); self.restore=QPushButton('恢复缺失素材到Warudo')
        self.check.clicked.connect(lambda:self.start('plan')); self.restore.clicked.connect(lambda:self.start('restore'))
        self.restore.setEnabled(False); row.addWidget(self.check); row.addWidget(self.restore); layout.addLayout(row)
        self.diagnose=QPushButton('检查已保存的直播场景…')
        self.diagnose.clicked.connect(self.choose_scene); layout.addWidget(self.diagnose)
        self.status=QLabel('请选择素材包和Warudo目录，检查后再恢复。'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.report=QPlainTextEdit(); self.report.setReadOnly(True); layout.addWidget(self.report,1)
        row=QHBoxLayout()
        for label,field in [('打开素材包目录',self.package),('打开Warudo目录',self.install)]:
            button=QPushButton(label); button.clicked.connect(lambda checked=False,f=field:self.open_folder(f)); row.addWidget(button)
        layout.addLayout(row)
        note=QLabel('恢复成功后：在Warudo加载包内对应场景，再检查角色和快捷键。\n'
                    '同名不同内容会停止恢复，保护你保存的场景。此页不启动摄像头或推流。\n'
                    '文件完整不代表动画、脸头跟随或OBS已验证；仍按人工清单检查。')
        note.setWordWrap(True); layout.addWidget(note)
        try:
            settings=json.loads((self.workspace/'live-settings.json').read_text(encoding='utf-8'))
            if not isinstance(settings,dict):raise ValueError('目录设置格式错误')
            self.package.setText(settings.get('package','')); self.install.setText(settings.get('install',''))
        except (OSError,ValueError,TypeError): pass

    def choose(self,field):
        path=QFileDialog.getExistingDirectory(self,'选择目录',field.text())
        if path:field.setText(path)

    def choose_scene(self):
        path,_=QFileDialog.getOpenFileName(self,'选择已保存的Warudo场景',
            str(Path(self.install.text())/'Warudo_Data/StreamingAssets/Scenes'),'Warudo场景 (*.json)')
        if path:self.start('diagnose',Path(path))

    def invalidate(self):
        self.plan=None; self.restore.setEnabled(False)
        if hasattr(self,'report'):self.report.clear(); self.status.setText('目录已变更，请重新检查。')

    def open_folder(self,field):
        path=Path(field.text())
        if field.text() and path.is_dir():QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def start(self,operation,scene=None):
        if self.busy or (self.worker and self.worker.isRunning()):return
        if operation == 'restore' and (not self.plan or not self.plan['can_restore']):return
        if not self.package.text().strip() or not self.install.text().strip():
            self.status.setText('请先选择两个目录。'); return
        try:atomic_json(self.workspace/'live-settings.json',{'package':self.package.text(),'install':self.install.text()})
        except OSError as exc:self.status.setText('保存目录失败：'+str(exc));return
        self.busy=True; self.operation=operation
        for widget in [self.package,self.install,self.check,self.restore,self.diagnose,*self.browse]:widget.setEnabled(False)
        self.status.setText('正在恢复；关闭窗口前请等待完成…' if operation=='restore' else '正在检查文件与安装内容…')
        if operation=='diagnose':self.status.setText('正在读取保存场景并检查资源、快捷键与动作遮罩…')
        self.worker=LiveWorker(operation,Path(self.package.text()),Path(self.install.text()),self,scene)
        self.worker.result.connect(self.completed); self.worker.start()

    def completed(self,result,error):
        self.busy=False
        for widget in [self.package,self.install,self.check,self.diagnose,*self.browse]:widget.setEnabled(True)
        self.restore.setEnabled(False)
        if error:
            self.plan=None; self.status.setText('未完成：'+error); return
        if self.operation=='diagnose':
            self.plan=None; self.report.setPlainText(format_report(result)); self.diagnostic=result
            self.status.setText('保存配置检查完成；运行效果仍按人工清单确认。' if result['configuration_ok']
                                else '发现需要修正的配置，请查看下方报告。未修改场景。')
            return
        self.plan=result
        labels={'add':'待恢复','reuse':'已存在且一致','conflict':'冲突，保留原文件'}
        self.report.setPlainText('场景：'+result['scene']+'\n\n'+'\n'.join(labels[x['action']]+'  '+x['path'] for x in result['items']))
        if result.get('restored'):
            self.status.setText(f"恢复完成：新增{result['added']}项，复用{result['reused']}项。尚未在Warudo加载验证。")
        elif not result['can_restore']:
            self.status.setText('发现同名内容冲突，不能恢复。现有文件保持不变。')
        else:
            count=sum(x['action']=='add' for x in result['items'])
            self.status.setText(f'文件检查通过，{count}项待恢复。' if count else '全部素材已存在且一致；无需恢复。原生使用仍待验证。')
            self.restore.setEnabled(count>0)

    def shutdown(self):
        if self.worker and self.worker.isRunning():
            self.status.setText('正在处理直播素材，请完成后再关闭，避免中断文件恢复。'); return False
        return True
