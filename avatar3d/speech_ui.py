"""桌面分段编辑器；仅调用项目服务，重任务在后台串行执行。"""
from pathlib import Path
import copy
import json
import threading
import uuid
import os

from PySide6.QtCore import QThread, Signal, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QListWidget, QPlainTextEdit, QComboBox, QFileDialog, QSplitter)
from . import speech_project as speech
from .models import atomic_json, digest


class ProjectWorker(QThread):
    progress = Signal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.cancel = threading.Event()
        self.value = None
        self.error = ''

    def run(self):
        try:self.value = self.operation(self.cancel, self.progress.emit)
        except Exception as exc:self.error = str(exc)


class SpeechPanel(QWidget):
    def __init__(self, host, runtime_file):
        super().__init__()
        self.host = host
        self.workspace = host.workspace.resolve()
        self.runtime_file = Path(runtime_file)
        self.path = None; self.document = None; self.saved_hash = None
        self.last_output = None; self.worker = None; self.busy = False
        self.loading = False; self.dirty = False
        self.save_timer = QTimer(self); self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        root = QVBoxLayout(self)
        self.toolbar = QWidget(); top = QHBoxLayout(self.toolbar); top.setContentsMargins(0,0,0,0)
        self.new_button = QPushButton('新建项目'); self.new_button.clicked.connect(self.new_project); top.addWidget(self.new_button)
        self.open_button = QPushButton('打开项目…'); self.open_button.clicked.connect(self.choose_project); top.addWidget(self.open_button)
        self.save_button = QPushButton('保存'); self.save_button.clicked.connect(self.save); top.addWidget(self.save_button)
        self.copy_button = QPushButton('另存副本'); self.copy_button.clicked.connect(self.save_copy); top.addWidget(self.copy_button)
        self.copy_settings = QPushButton('采用单段页的模型／画幅'); self.copy_settings.clicked.connect(self.adopt_settings); top.addWidget(self.copy_settings)
        root.addWidget(self.toolbar)
        self.project_label = QLabel('先在单段页选择模型，再新建分段项目。'); self.project_label.setWordWrap(True); root.addWidget(self.project_label)
        self.settings_label = QLabel(); self.settings_label.setWordWrap(True); root.addWidget(self.settings_label)
        self.edit_area = QWidget(); body = QHBoxLayout(self.edit_area); body.setContentsMargins(0,0,0,0)
        splitter = QSplitter(); body.addWidget(splitter)
        left = QWidget(); left_layout = QVBoxLayout(left)
        self.list = QListWidget(); self.list.currentRowChanged.connect(self.select); left_layout.addWidget(self.list)
        row = QHBoxLayout()
        self.add_button = QPushButton('新增'); self.add_button.clicked.connect(self.add); row.addWidget(self.add_button)
        self.remove_button = QPushButton('移除'); self.remove_button.clicked.connect(self.remove); row.addWidget(self.remove_button)
        self.up_button = QPushButton('上移'); self.up_button.clicked.connect(lambda:self.move(-1)); row.addWidget(self.up_button)
        self.down_button = QPushButton('下移'); self.down_button.clicked.connect(lambda:self.move(1)); row.addWidget(self.down_button)
        left_layout.addLayout(row); splitter.addWidget(left)
        right = QWidget(); right_layout = QVBoxLayout(right)
        self.segment_label = QLabel('选择段落'); right_layout.addWidget(self.segment_label)
        self.text = QPlainTextEdit(); self.text.setPlaceholderText('输入本段口播文本。修改后需重新绑定对应配音。')
        self.text.textChanged.connect(self.edit_text); right_layout.addWidget(self.text)
        self.action = QComboBox(); self.action.addItem('轻缓待机','idle'); self.action.addItem('单手讲解','explain')
        self.action.currentIndexChanged.connect(self.edit_action); right_layout.addWidget(self.action)
        audio_row = QHBoxLayout()
        self.bind_button = QPushButton('绑定本段配音…'); self.bind_button.clicked.connect(self.choose_audio); audio_row.addWidget(self.bind_button)
        self.clear_button = QPushButton('清除配音'); self.clear_button.clicked.connect(self.clear_audio); audio_row.addWidget(self.clear_button)
        right_layout.addLayout(audio_row)
        self.audio_label = QLabel(); self.audio_label.setWordWrap(True); right_layout.addWidget(self.audio_label)
        hint = QLabel('每段配音0.25—29.75秒。先确认文本与配音一致；程序不识别录音内容。\n文本自动保存，移除段落不会删除旧素材。')
        hint.setWordWrap(True); right_layout.addWidget(hint)
        splitter.addWidget(right); splitter.setSizes([330,520]); root.addWidget(self.edit_area,1)
        self.export_area = QWidget(); actions = QHBoxLayout(self.export_area); actions.setContentsMargins(0,0,0,0)
        self.render_one = QPushButton('导出选中段'); self.render_one.clicked.connect(lambda:self.render(True)); actions.addWidget(self.render_one)
        self.render_all = QPushButton('导出全部／继续未完成'); self.render_all.clicked.connect(lambda:self.render(False)); actions.addWidget(self.render_all)
        self.preview = QPushButton('打开最近导出预览'); self.preview.clicked.connect(self.open_preview); actions.addWidget(self.preview)
        self.folder_button = QPushButton('打开项目目录'); self.folder_button.clicked.connect(self.open_folder); actions.addWidget(self.folder_button)
        root.addWidget(self.export_area)
        self.cancel_button = QPushButton('取消本次导出／导入'); self.cancel_button.clicked.connect(self.cancel); root.addWidget(self.cancel_button)
        self.status = QLabel('分段配音分别导出；字幕为段落草稿，动作尚无跨段混合。'); self.status.setWordWrap(True); root.addWidget(self.status)
        self.set_busy(False)
        state = self.workspace/'speech-ui.json'
        if state.exists():
            try:self.load_project(Path(json.loads(state.read_text(encoding='utf-8'))['project']))
            except Exception as exc:self.status.setText('上次项目未打开：'+str(exc))

    def selected(self):
        row = self.list.currentRow()
        return self.document['segments'][row] if self.document and 0 <= row < len(self.document['segments']) else None

    def current_settings(self):
        model = self.host.model.currentData()
        if not model:raise ValueError('请先在单段页导入或选择模型。')
        return {'model_sha256':model['sha256'], 'width':self.host.width.currentData(),
                'fps':self.host.fps.currentData(), 'azimuth':self.host.angle.currentData(),
                'framing':self.host.framing.currentData()}

    def new_project(self):
        if self.busy or not self.save():return
        try:
            settings = self.current_settings()
            doc = {'schema':1,'settings':settings,'segments':[{'id':uuid.uuid4().hex[:12],'text':'','action':'idle'}]}
            path = self.workspace/'projects'/uuid.uuid4().hex/'project.json'
            speech.save_draft(path, doc)
            self.load_project(path)
        except Exception as exc:self.status.setText(str(exc))

    def choose_project(self):
        if self.busy or not self.save():return
        path,_ = QFileDialog.getOpenFileName(self,'打开工作区内的口播项目',str(self.workspace/'projects'),'口播项目 (*.json)')
        if path:
            try:self.load_project(Path(path))
            except Exception as exc:self.status.setText(str(exc))

    def load_project(self, path):
        if self.busy:raise ValueError('请等待当前任务结束。')
        if not self.save():raise ValueError('当前项目未能保存。')
        path = Path(path).resolve()
        if not path.is_relative_to(self.workspace):raise ValueError('请选择当前工作区内的项目。')
        document = speech.validate(json.loads(path.read_text(encoding='utf-8')), allow_draft=True)
        self.path = path; self.document = document; self.saved_hash = speech.fingerprint(document)
        self.dirty = False; self.last_output = None
        view = path.with_name('view.json')
        if view.exists():
            try:
                output = Path(json.loads(view.read_text(encoding='utf-8'))['output']).resolve()
                if output.is_relative_to(path.parent/'runs'):self.last_output = output
            except (ValueError,KeyError):pass
        atomic_json(self.workspace/'speech-ui.json', {'project':str(path)})
        self.project_label.setText('项目：'+str(path.relative_to(self.workspace)))
        self.show_settings(); self.refresh(0); self.set_busy(False)
        self.status.setText('项目已打开。修改会自动保存；导出时检查配音与成品完整性。')

    def save(self):
        self.save_timer.stop()
        if not self.dirty or self.document is None:return True
        try:
            self.saved_hash = speech.save_draft(self.path, self.document, self.saved_hash)
            self.dirty = False; self.status.setText('已自动保存。'); return True
        except Exception as exc:self.status.setText('保存失败：'+str(exc)); return False

    def save_copy(self):
        if self.busy or self.document is None:return
        try:
            path = self.workspace/'projects'/uuid.uuid4().hex/'project.json'
            speech.save_draft(path, self.document)
            self.dirty = False  # 新副本已落盘；无需覆盖可能被外部修改的原文件。
            self.load_project(path)
        except Exception as exc:self.status.setText('另存失败：'+str(exc))

    def changed(self):
        self.dirty = True; self.save_timer.start(500)
        self.status.setText('有修改，正在等待自动保存…')
        self.update_rows(); self.show_audio()

    @staticmethod
    def segment_status(segment):
        if not segment['text'].strip():return '待填文本'
        audio = segment.get('audio', {})
        if not audio.get('sha256'):return '待配音'
        return '配音已过期' if audio.get('text_sha256') != speech.text_hash(segment['text']) else '已绑定配音'

    def update_rows(self):
        if not self.document:return
        for i,segment in enumerate(self.document['segments']):
            self.list.item(i).setText(f'{i+1}. {self.segment_status(segment)}\n'+(segment['text'].replace('\n',' ')[:26] or '（空段落）'))

    def refresh(self, row):
        self.loading = True; self.list.blockSignals(True); self.list.clear()
        for segment in self.document['segments']:self.list.addItem(segment['id'])
        self.update_rows(); self.list.setCurrentRow(row); self.list.blockSignals(False); self.loading = False
        self.select(row)

    def select(self, row):
        segment = self.selected(); self.loading = True
        self.text.setPlainText(segment['text'] if segment else '')
        if segment:
            self.action.setCurrentIndex(self.action.findData(segment['action']))
            self.segment_label.setText(f'第{row+1}段 · {segment["id"]}')
        self.loading = False; self.show_audio()

    def edit_text(self):
        if self.loading or self.busy:return
        segment = self.selected()
        if segment is not None:segment['text'] = self.text.toPlainText(); self.changed()

    def edit_action(self):
        if self.loading or self.busy:return
        segment = self.selected()
        if segment:segment['action'] = self.action.currentData(); self.changed()

    def show_audio(self):
        segment = self.selected()
        self.audio_label.setText(self.segment_status(segment) if segment else '尚无段落')

    def add(self):
        if not self.document or self.busy:return
        if len(self.document['segments']) >= 200:self.status.setText('最多200段。'); return
        row = self.list.currentRow()+1
        self.document['segments'].insert(row, {'id':uuid.uuid4().hex[:12],'text':'','action':'idle'})
        self.refresh(row); self.changed()

    def remove(self):
        if not self.document or self.busy:return
        if len(self.document['segments']) == 1:self.status.setText('至少保留一段；可直接修改文本。'); return
        row = self.list.currentRow(); del self.document['segments'][row]
        self.refresh(min(row,len(self.document['segments'])-1)); self.changed()

    def move(self, delta):
        if not self.document or self.busy:return
        row = self.list.currentRow(); target = row+delta
        if 0 <= target < len(self.document['segments']):
            segments = self.document['segments']; segments[row],segments[target] = segments[target],segments[row]
            self.refresh(target); self.changed()

    def show_settings(self):
        if not self.document:return
        settings = self.document['settings']; name = settings['model_sha256'][:12]
        try:name = json.loads((self.workspace/'models'/(settings['model_sha256']+'.json')).read_text(encoding='utf-8'))['name']
        except (OSError,ValueError,KeyError):pass
        self.settings_label.setText(f'模型：{name} ｜ {settings["width"]}×{settings["width"]*3//2} ｜ {settings["fps"]}fps ｜ '+
                                   ('半身' if settings['framing']=='bust' else '全身')+f' ｜ 视角{settings["azimuth"]}°')

    def adopt_settings(self):
        if not self.document or self.busy:return
        try:self.document['settings'] = self.current_settings(); self.show_settings(); self.changed()
        except Exception as exc:self.status.setText(str(exc))

    def can_start(self):
        if self.busy:return False
        if any(w and w.isRunning() for w in (self.host.worker,self.host.audio_worker,self.host.preview_worker,self.host.exchange_worker)):
            self.status.setText('单段页有任务正在执行，请待完成或取消后重试。'); return False
        return self.save()

    def start(self, operation, kind):
        if not self.can_start():return False
        self.kind = kind; self.worker = ProjectWorker(operation)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished.connect(self.work_finished)
        self.set_busy(True); self.worker.start(); return True

    def choose_audio(self):
        if not self.can_start() or not self.selected():return
        if not self.selected()['text'].strip():self.status.setText('请先填写本段文本。'); return
        path,_ = QFileDialog.getOpenFileName(self,'绑定当前文本对应的配音','','音频 (*.wav *.mp3 *.m4a *.aac *.flac *.ogg)')
        if path:self.bind_path(path)

    def bind_path(self, path):
        if not self.selected() or not self.can_start():return
        ident = self.selected()['id']; document = copy.deepcopy(self.document)
        self.start(lambda cancel,progress:speech.bind_audio(document,ident,self.workspace,path,cancel), 'bind')
        self.status.setText('正在导入配音并保存副本…')

    def clear_audio(self):
        if self.selected() and not self.busy:self.selected().pop('audio',None); self.changed()

    def render(self, selected_only=False):
        if not self.document or not self.can_start():return
        ids = [self.selected()['id']] if selected_only and self.selected() else None
        self.start(lambda cancel,progress:speech.render_project(self.path,self.host.service,
                   speech.engine_signature(self.runtime_file),cancel,progress,segment_ids=ids), 'render')
        self.status.setText('正在校验项目和缓存，随后逐段生成…')

    def work_finished(self):
        worker = self.worker
        if worker is None:return
        self.set_busy(False); self.worker = None
        if worker.error:self.status.setText('本次任务未完成：'+worker.error+'\n已完成素材保留，可再次导出继续。')
        elif self.kind == 'bind':
            self.document = worker.value; self.changed(); self.save()
        else:
            self.last_output = Path(worker.value)
            try:
                atomic_json(self.path.with_name('view.json'), {'output':str(self.last_output)})
                self.status.setText('导出完成。可打开最近预览；MOV和WAV同起点，字幕为段落草稿。')
            except Exception as exc:self.status.setText('素材已完成，最近入口保存失败：'+str(exc)+'\n'+str(self.last_output))
        self.host.refresh(); worker.deleteLater()

    def set_busy(self, busy):
        self.busy = busy
        self.toolbar.setEnabled(not busy)
        self.edit_area.setEnabled(not busy and self.document is not None)
        self.export_area.setEnabled(not busy and self.document is not None)
        self.cancel_button.setEnabled(busy)
        if hasattr(self.host,'tabs'):self.host.tabs.setTabEnabled(0,not busy)

    def cancel(self):
        if self.worker:self.worker.cancel.set(); self.status.setText('正在取消，已完成段落会保留…')

    def open_preview(self):
        try:
            if not self.last_output:raise ValueError('请先导出；这里打开最近一次完成版本。')
            record = json.loads((self.last_output/'complete.json').read_text(encoding='utf-8'))
            for name in ('plan.json','timeline.json','预览.html'):
                if digest(self.last_output/name) != record['files'][name]:raise ValueError('预览清单损坏，请再次导出重建。')
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output/'预览.html'))):raise ValueError('系统未能打开预览，请从项目目录进入runs。')
        except Exception as exc:self.status.setText(str(exc))

    def open_folder(self):
        if self.path:os.startfile(str(self.path.parent))

    def shutdown(self):
        self.save_timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            if not self.worker.wait(15000):self.status.setText('正在停止分段任务，请稍后再关闭。'); return False
        # finished信号可能尚未派发：关闭前保存已成功导入的音频绑定。
        if self.worker:self.work_finished()
        return self.save()
