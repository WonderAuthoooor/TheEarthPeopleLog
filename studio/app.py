"""A single-screen Qt workbench backed by portable workspace documents."""
from __future__ import annotations
import json
import os
from pathlib import Path
import copy
import sys
from PySide6.QtCore import Qt, QTimer, QUrl, QProcess
from PySide6.QtGui import QDesktopServices, QFont, QPixmap, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QSplitter, QTabWidget, QFormLayout,
    QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QFileDialog, QMessageBox,
    QSlider, QGroupBox, QCheckBox, QComboBox, QScrollArea, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from pipeline import core
from .storage import Workspace, read_json
from . import __version__, quick
from .branding import ICON_PATH, configure_windows_identity

STATUS = {"QUEUED": "排队中", "RUNNING": "处理中", "SUCCEEDED": "已完成",
          "FAILED": "失败", "INTERRUPTED": "已中断", "CANCELLED": "已取消"}


def button(text, callback):
    control = QPushButton(text)
    control.clicked.connect(callback)
    return control


def spin(maximum=300, minimum=0, step=.1):
    control = QDoubleSpinBox()
    control.setRange(minimum, maximum)
    control.setDecimals(2)
    control.setSingleStep(step)
    control.setSuffix(" 秒")
    return control


class FrameView(QLabel):
    """CPU-backed preview also captures correctly in diagnostics/screenshots."""
    def __init__(self):
        super().__init__("导入视频后在此预览")
        self.frame = None
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#101c22;color:#9ab0b8;border-radius:6px;")

    def show_frame(self, frame):
        image = frame.toImage()
        if not image.isNull():
            self.frame = QPixmap.fromImage(image)
            self.refresh()

    def refresh(self):
        if self.frame:
            self.setPixmap(self.frame.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        self.refresh()
        super().resizeEvent(event)


class Window(QMainWindow):
    def __init__(self, workspace):
        super().__init__()
        self.store = Workspace(workspace)
        self.document = None
        self.loading = True
        self.dirty = False
        self.process = None
        self.active_task = None
        self.last_played = ""
        self.preview_is_output = False
        self.setWindowTitle(f"地球人日志工作室 · {__version__} 内部测试版")
        self.task_titles = {}
        self.resize(1380, 880)
        self.setMinimumSize(1000, 650)
        self.autosave = QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.setInterval(500)
        self.autosave.timeout.connect(self.save)
        self.poll = QTimer(self)
        self.poll.setInterval(700)
        self.poll.timeout.connect(self.tick)
        self.build()
        self.refresh_projects()
        recent = self.store.root / "recent.json"
        project_id = None
        try:
            project_id = read_json(recent).get("project_id") if recent.exists() else None
            if project_id:
                self.open_project(project_id)
        except Exception as exc:
            self.notice.setText(str(exc))
        if not self.document:
            projects = [r for r in self.store.list_projects() if not r[3]]
            if projects:
                self.open_project(projects[0][1])
            else:
                self.new_project()
        self.store.reconcile()
        self.poll.start()

    def build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 12)
        header = QHBoxLayout()
        brand = QLabel("地球人日志  /  创作工作台")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        self.saved = QLabel("准备就绪")
        header.addWidget(self.saved)
        header.addWidget(button("打开工作区", lambda: self.open_path(self.store.root)))
        header.addWidget(button("切换工作区", self.change_workspace))
        self.export_button = button("生成视频草稿", lambda: self.enqueue("render"))
        self.export_button.setObjectName("primary")
        header.addWidget(self.export_button)
        layout.addLayout(header)
        self.notice = QLabel("本地制作，不调用收费接口。导出成功与内容审核分开记录。")
        self.notice.setWordWrap(True)
        self.notice.setObjectName("notice")
        layout.addWidget(self.notice)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 10, 0)
        ll.addWidget(QLabel("项目"))
        ll.addWidget(button("＋ 快速切片", lambda: self.new_project(True)))
        ll.addWidget(button("＋ 新建一期", self.new_project))
        ll.addWidget(button("地球动画工坊…", self.open_animation))
        ll.addWidget(button("导入旧版任务…", self.migrate))
        ll.addWidget(button("从快照恢复项目…", self.restore_project))
        self.projects = QListWidget()
        self.projects.itemClicked.connect(lambda item: self.open_project(item.data(Qt.UserRole)))
        ll.addWidget(self.projects, 1)
        ll.addWidget(button("打开当前项目目录", lambda: self.open_path(self.project_folder())))
        ll.addWidget(QLabel("原片与截图复制归档\n编辑自动保存 · 原始文件保留"))
        splitter.addWidget(left)
        middle = QWidget()
        ml = QVBoxLayout(middle)
        ml.setContentsMargins(4, 0, 8, 0)
        self.title = QLineEdit()
        self.title.setPlaceholderText("本期标题 · 最多40字")
        self.title.setMaxLength(40)
        self.title.setObjectName("title")
        self.title.textChanged.connect(self.changed)
        ml.addWidget(self.title)
        self.tabs = QTabWidget()
        ml.addWidget(self.tabs, 1)
        form = self.page("素材与选段")
        self.source_url = self.line("X原帖链接", form, "https://x.com/…/status/…")
        form.addRow(button("从X获取单帖视频", lambda: self.enqueue("download")))
        self.source_note = self.line("画面来源", form, "作者 / 机构 / 来源待核查")
        self.event_date = self.line("事件日期", form, "YYYY-MM-DD；未知则留空")
        self.video_label = QLabel("未导入视频")
        self.video_label.setWordWrap(True)
        form.addRow(self.video_label)
        form.addRow(button("导入本地视频…", lambda: self.import_file("video")))
        self.start = spin(86400)
        self.duration = spin(300, .1)
        self.start.valueChanged.connect(self.changed)
        self.duration.valueChanged.connect(self.changed)
        form.addRow("原片起点", self.start)
        form.addRow("成片时长", self.duration)
        range_buttons = QHBoxLayout()
        range_buttons.addWidget(button("当前画面设为起点", self.set_in))
        range_buttons.addWidget(button("当前画面设为终点", self.set_out))
        form.addRow(range_buttons)
        self.resolution = QComboBox()
        self.resolution.addItems(["1080 × 1920 正式草稿", "540 × 960 快速试剪"])
        form.addRow("导出尺寸", self.resolution)

        form = self.page("文稿与声音")
        self.facts = QPlainTextEdit()
        self.facts.setPlaceholderText("记录已核实事实、来源和仍待确认的内容。模型输出不能作为证据。")
        self.facts.setMinimumHeight(120)
        self.facts.textChanged.connect(self.changed)
        form.addRow("事实与核查备注", self.facts)
        self.script = QPlainTextEdit()
        self.script.setPlaceholderText("粘贴口播稿。原创观察与网友原话分清；无音频时不会自动生成配音。")
        self.script.setMinimumHeight(180)
        self.script.textChanged.connect(self.changed)
        form.addRow("口播稿", self.script)
        form.addRow(button("复制AI写稿提示词", self.copy_prompt))
        self.voice_label = QLabel("未导入配音 · 默认沿用甜美解说")
        self.voice_label.setWordWrap(True)
        form.addRow(self.voice_label)
        form.addRow(button("导入甜美解说 / 其他配音…", lambda: self.import_file("narration_audio")))
        form.addRow(button("清除配音引用", lambda: self.clear_asset("narration_audio")))
        self.voice_start = spin(300)
        self.voice_start.valueChanged.connect(self.changed)
        form.addRow("配音进入时间", self.voice_start)
        self.volume = spin(1, 0, .05)
        self.volume.setSuffix("")
        self.volume.valueChanged.connect(self.changed)
        form.addRow("旁白时段原声音量", self.volume)
        self.srt_label = QLabel("未导入SRT · 有稿时仅按字数估时，需试听校准")
        self.srt_label.setWordWrap(True)
        form.addRow(self.srt_label)
        form.addRow(button("导入准确字幕SRT…", lambda: self.import_file("subtitle_file")))
        form.addRow(button("清除字幕引用", lambda: self.clear_asset("subtitle_file")))

        form = self.page("真实评论")
        help_text = QLabel("最多两张真实截图；译文与原创回应分开。显示时段使用成片时间轴。")
        help_text.setWordWrap(True)
        form.addRow(help_text)
        self.comment_widgets = []
        for index in range(2):
            box = QGroupBox(f"评论 {index + 1}")
            cf = QFormLayout(box)
            active = QCheckBox("在成片中显示")
            active.toggled.connect(self.changed)
            image = QLabel("未导入截图")
            image.setWordWrap(True)
            cf.addRow(active)
            cf.addRow(image)
            cf.addRow(button("选择真实截图…", lambda checked=False, i=index: self.import_comment(i)))
            url = self.line("定位链接", cf)
            translation = self.line("忠实译文", cf)
            translation.setMaxLength(56)
            start, end = spin(300), spin(300)
            start.valueChanged.connect(self.changed)
            end.valueChanged.connect(self.changed)
            cf.addRow("出现", start)
            cf.addRow("消失", end)
            self.comment_widgets.append({"active": active, "label": image, "image": "", "url": url, "translation": translation, "start": start, "end": end})
            form.addRow(box)

        form = self.page("文明观察与审核")
        self.score_mode = QComboBox()
        self.score_mode.addItems(["待评 · 证据不足", "已有依据 · 填写五维评分"])
        self.score_mode.currentIndexChanged.connect(self.changed)
        form.addRow("评分状态", self.score_mode)
        self.dimensions = {}
        for key, label in zip(core.DIMENSIONS, ("生命福祉", "尊严权利", "知识求真", "协作治理", "长期可持续")):
            s = QSpinBox()
            s.setRange(-2, 2)
            s.valueChanged.connect(self.changed)
            self.dimensions[key] = s
            form.addRow(label, s)
        self.reason = self.line("评分范围与依据", form)
        self.score_total = QLabel("文明观察：待评")
        form.addRow(self.score_total)
        self.review = {}
        for key, label in (("facts_checked", "事实与日期已核查"), ("materials_checked", "素材使用依据已检查"), ("content_checked", "内容与幽默表达已过稿")):
            c = QCheckBox(label)
            c.toggled.connect(self.changed)
            self.review[key] = c
            form.addRow(c)
        hint = QLabel("这里只存本期评分建议。应用不会发布作品或修改正式文明账本。")
        hint.setWordWrap(True)
        form.addRow(hint)

        form = self.page("任务队列")
        self.queue_list = QListWidget()
        self.queue_list.setMinimumHeight(220)
        self.queue_list.currentItemChanged.connect(self.show_task)
        form.addRow(self.queue_list)
        self.task_detail = QLabel("提交任务后可继续编辑；任务使用提交时的版本。")
        self.task_detail.setWordWrap(True)
        form.addRow(self.task_detail)
        self.progress = QProgressBar()
        form.addRow(self.progress)
        form.addRow(button("取消选中任务", self.cancel_task))
        form.addRow(button("按原快照重新执行", self.retry_task))
        form.addRow(button("查看成片 / 导入下载结果", self.use_result))
        form.addRow(button("打开选中任务目录", self.open_task))
        self.build_quick_page()
        splitter.addWidget(middle)

        preview = QWidget()
        pl = QVBoxLayout(preview)
        pl.setContentsMargins(6, 0, 0, 0)
        self.preview_label = QLabel("预览 · 原始素材")
        pl.addWidget(self.preview_label)
        self.video_widget = FrameView()
        self.video_widget.setMinimumSize(280, 320)
        pl.addWidget(self.video_widget, 1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video_sink = QVideoSink(self)
        self.video_sink.videoFrameChanged.connect(self.video_widget.show_frame)
        self.player.setVideoSink(self.video_sink)
        self.player.errorOccurred.connect(lambda error, message: self.notice.setText("内嵌播放失败，可点“外部播放”：" + message))
        self.seek = QSlider(Qt.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.durationChanged.connect(lambda duration: self.seek.setRange(0, duration))
        self.player.positionChanged.connect(self.position_changed)
        pl.addWidget(self.seek)
        self.time_label = QLabel("00:00 / 00:00")
        pl.addWidget(self.time_label)
        controls = QHBoxLayout()
        controls.addWidget(button("播放 / 暂停", self.toggle_play))
        controls.addWidget(button("原片", self.preview_source))
        controls.addWidget(button("外部播放", lambda: self.open_path(self.last_played)))
        pl.addLayout(controls)
        self.range_label = QLabel("选段范围尚未设置")
        self.range_label.setWordWrap(True)
        pl.addWidget(self.range_label)
        hint = QLabel("原片预览不包含未渲染的文字和评论；生成后在队列中查看完整草稿。")
        hint.setWordWrap(True)
        pl.addWidget(hint)
        splitter.addWidget(preview)
        splitter.setSizes([210, 650, 420])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        self.setStyleSheet("""
            QMainWindow,QWidget { background:#f4f5f2; color:#20343a; }
            QLabel#brand {font-size:20px;font-weight:700;}
            QLabel#notice {background:#e3eee8;padding:9px;border-radius:6px;}
            QLineEdit,QPlainTextEdit,QListWidget,QSpinBox,QDoubleSpinBox,QComboBox {
                background:white;border:1px solid #cbd6d0;border-radius:5px;padding:7px;selection-background-color:#167c70;}
            QLineEdit#title {font-size:20px;font-weight:600;padding:12px;}
            QPushButton {background:white;border:1px solid #bfcfc6;border-radius:6px;padding:8px 10px;}
            QPushButton:hover {background:#dcece5;} QPushButton#primary {background:#137c6e;color:white;border:0;font-weight:600;}
            QTabWidget::pane {border:1px solid #d4dcd7;border-radius:5px;}
            QTabBar::tab {padding:10px 8px;} QTabBar::tab:selected {background:#dcece5;color:#086e61;}
            QGroupBox {border:1px solid #cbd6d0;border-radius:6px;margin-top:14px;padding-top:12px;}
            QProgressBar {border:1px solid #cbd6d0;border-radius:4px;text-align:center;}
            QProgressBar::chunk {background:#329884;} QVideoWidget {background:#101c22;}
        """)

    def page(self, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(14, 16, 14, 16)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, title)
        return form

    def line(self, label, form, placeholder=""):
        control = QLineEdit()
        control.setPlaceholderText(placeholder)
        control.textChanged.connect(self.changed)
        form.addRow(label, control)
        return control

    def build_quick_page(self):
        form = self.page("快速切片")
        hint = QLabel("①导入原片 → ②选段 → ③填写背景/观察 → ④导出。默认保留原声，不要求配音、评论或音乐。")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.quick_video_label = QLabel("未导入视频")
        self.quick_video_label.setWordWrap(True)
        form.addRow(self.quick_video_label)
        form.addRow(button("导入原片…", lambda: self.import_file("video")))
        for label, original in (("来源链接", self.source_url), ("来源名称", self.source_note), ("事件日期", self.event_date)):
            mirror = QLineEdit()
            mirror.setPlaceholderText(original.placeholderText())
            mirror.textChanged.connect(original.setText)
            original.textChanged.connect(mirror.setText)
            form.addRow(label, mirror)
        self.quick_start = spin(86400)
        self.quick_duration = spin(300, 1)
        for a, b in ((self.quick_start, self.start), (self.quick_duration, self.duration)):
            a.valueChanged.connect(b.setValue)
            b.valueChanged.connect(a.setValue)
        form.addRow("原片起点", self.quick_start)
        form.addRow("片段时长", self.quick_duration)
        ranges = QHBoxLayout()
        ranges.addWidget(button("当前画面设为起点", self.set_in))
        ranges.addWidget(button("当前画面设为终点", self.set_out))
        form.addRow(ranges)
        self.quick_context = self.line("一句背景", form, "准确说明事件背景；不要填未经核实的结论")
        self.quick_context.setMaxLength(64)
        self.quick_observation = self.line("一句观察", form, "你的解释或幽默点评，与事实分开标注")
        self.quick_observation.setMaxLength(52)
        self.quick_cover = spin(86700, -1)
        self.quick_cover.setSpecialValueText("片段起点（自动）")
        self.quick_cover.valueChanged.connect(self.changed)
        form.addRow("封面原片时刻", self.quick_cover)
        form.addRow(button("用当前原片画面作封面", self.set_cover))
        self.quick_theme = QComboBox()
        self.quick_theme.addItems(["深色 · 简洁", "浅色 · 简洁"])
        self.quick_theme.currentIndexChanged.connect(self.changed)
        form.addRow("画面模板", self.quick_theme)
        self.quick_resolution = QComboBox()
        self.quick_resolution.addItems(["1080 × 1920", "540 × 960 试剪"])
        self.quick_resolution.currentIndexChanged.connect(self.resolution.setCurrentIndex)
        self.resolution.currentIndexChanged.connect(self.quick_resolution.setCurrentIndex)
        form.addRow("输出尺寸", self.quick_resolution)
        form.addRow(button("记住模板和输出尺寸", self.save_quick_preset))
        form.addRow(button("导出当前片段", lambda: self.enqueue("render")))
        self.quick_table = QTableWidget(0, 6)
        self.quick_table.setHorizontalHeaderLabels(["切片标题", "原片起点", "原片终点", "一句背景", "一句观察", "封面时刻"])
        self.quick_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.quick_table.setColumnWidth(0, 180)
        self.quick_table.setColumnWidth(1, 90)
        self.quick_table.setColumnWidth(2, 90)
        self.quick_table.setColumnWidth(3, 180)
        self.quick_table.setColumnWidth(4, 180)
        self.quick_table.setColumnWidth(5, 90)
        self.quick_table.setMinimumHeight(160)
        self.quick_table.itemChanged.connect(self.changed)
        form.addRow("可选：多个独立看点", self.quick_table)
        actions = QHBoxLayout()
        actions.addWidget(button("把当前设置加入列表", self.add_quick_cut))
        actions.addWidget(button("删除选中行", self.remove_quick_cut))
        form.addRow(actions)
        form.addRow(button("批量导出列表", self.enqueue_quick_batch))
        note = QLabel("列表可双击修改，时间全部基于原片。留空封面时刻会用各片段起点；批量评分保持待评。使用原片已有字幕，不会自动识别、翻译或寻找热点。")
        note.setWordWrap(True)
        form.addRow(note)

    def set_cover(self):
        if self.preview_is_output:
            self.notice.setText("请切回原片，再选择封面帧。")
            return
        self.quick_cover.setValue(self.player.position() / 1000)

    def quick_rows(self):
        return [[self.quick_table.item(r, c).text() if self.quick_table.item(r, c) else "" for c in range(6)]
                for r in range(self.quick_table.rowCount())]

    def fill_quick_rows(self, rows):
        self.quick_table.setRowCount(0)
        for row in rows:
            index = self.quick_table.rowCount()
            self.quick_table.insertRow(index)
            for column, value in enumerate(row[:6]):
                self.quick_table.setItem(index, column, QTableWidgetItem(str(value)))

    def add_quick_cut(self):
        if self.quick_table.rowCount() >= 20:
            self.notice.setText("每批最多20条；先检查各条是否有独立看点。")
            return
        row = [self.title.text(), str(self.start.value()), str(round(self.start.value() + self.duration.value(), 2)),
               self.quick_context.text(), self.quick_observation.text(), "" if self.quick_cover.value() < 0 else str(self.quick_cover.value())]
        rows = self.quick_rows()
        rows.append(row)
        self.fill_quick_rows(rows)
        self.changed()

    def remove_quick_cut(self):
        row = self.quick_table.currentRow()
        if row >= 0:
            self.quick_table.removeRow(row)
            self.changed()

    def save_quick_preset(self):
        try:
            core.save_json(self.store.root / "quick-preset.json", {"theme": quick.THEMES[self.quick_theme.currentIndex()],
                                                                   "resolution_index": self.resolution.currentIndex()})
            self.notice.setText("已记住画面模板和尺寸。下次新建快速切片时应用，不复制文稿或评分。")
        except OSError as exc:
            self.notice.setText("模板保存失败：" + str(exc))

    def enqueue_quick_batch(self):
        if not self.save():
            return
        try:
            prepared = quick.prepare_batch(self.document, self.quick_rows(), self.project_folder())
            ids = [self.store.enqueue(d, "render", 1080 if self.resolution.currentIndex() == 0 else 540) for d in prepared]
            self.notice.setText(f"已提交{len(set(ids))}个切片，逐个处理；输入未变的任务会复用。")
            self.tabs.setCurrentIndex(4)
            self.tick()
            self.select_task(ids[0])
        except Exception as exc:
            self.notice.setText(str(exc))

    def project_folder(self):
        return self.store.path(self.document["project_id"]) if self.document else self.store.root

    def changed(self, *args):
        if self.loading or not self.document:
            return
        self.dirty = True
        self.saved.setText("修改中…")
        self.autosave.start()
        self.update_range()

    def gather(self):
        d = self.document["job"]
        for key, control in (("title", self.title), ("source_url", self.source_url), ("source_note", self.source_note), ("event_date", self.event_date)):
            d[key] = control.text()
        d.update(script=self.script.toPlainText(), facts=self.facts.toPlainText(), clip_start=self.start.value(), duration=self.duration.value(), narration_start=self.voice_start.value(), original_volume=self.volume.value())
        d["comments"] = [{k: w[k].text() if k in ("url", "translation") else w[k].value() if k in ("start", "end") else w[k] for k in ("image", "url", "translation", "start", "end")} for w in self.comment_widgets if w["active"].isChecked()]
        d["score"] = {"status": "pending" if self.score_mode.currentIndex() == 0 else "scored", "dimensions": None if self.score_mode.currentIndex() == 0 else {k: c.value() for k, c in self.dimensions.items()}, "reason": self.reason.text()}
        d["review"] = {k: c.isChecked() for k, c in self.review.items()}
        if d.get("layout") == "quick":
            d.update(context=self.quick_context.text(), observation=self.quick_observation.text(),
                     quick_theme=quick.THEMES[self.quick_theme.currentIndex()],
                     cover_at=None if self.quick_cover.value() < 0 else self.quick_cover.value(),
                     quick_clips=self.quick_rows())
        try:
            score = core.score_value(d["score"])
            self.score_total.setText("文明观察：待评" if score is None else f"本期建议 {score:+.1f} 分 · 不写入正式账本")
        except core.PipelineError as exc:
            self.score_total.setText(str(exc))

    def save(self):
        if not self.document or not self.dirty:
            return True
        try:
            self.gather()
            self.store.save(self.document)
            self.dirty = False
            self.saved.setText(f"已保存 · r{self.document['revision']}")
            self.refresh_projects()
            return True
        except Exception as exc:
            self.saved.setText("保存失败 · 修改仍在窗口中")
            self.notice.setText(str(exc))
            return False

    def refresh_projects(self):
        self.projects.clear()
        for _, project_id, title, error in self.store.list_projects():
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, project_id)
            self.projects.addItem(item)

    def open_project(self, project_id):
        if not self.save():
            return
        try:
            document = self.store.load(project_id)
        except Exception as exc:
            self.notice.setText(str(exc))
            self.open_path(self.store.path(project_id))
            return
        self.document = document
        self.loading = True
        d = document["job"]
        for key, control in (("title", self.title), ("source_url", self.source_url), ("source_note", self.source_note), ("event_date", self.event_date)):
            control.setText(d.get(key, ""))
        self.script.setPlainText(d.get("script", ""))
        self.facts.setPlainText(d.get("facts", ""))
        self.start.setValue(float(d["clip_start"]))
        self.duration.setValue(float(d["duration"]))
        self.voice_start.setValue(float(d["narration_start"]))
        self.volume.setValue(float(d["original_volume"]))
        self.quick_context.setText(d.get("context", ""))
        self.quick_observation.setText(d.get("observation", ""))
        self.quick_cover.setValue(-1 if d.get("cover_at") is None else float(d["cover_at"]))
        self.quick_theme.setCurrentIndex(1 if d.get("quick_theme") == "paper" else 0)
        self.fill_quick_rows(d.get("quick_clips", []))
        for index, w in enumerate(self.comment_widgets):
            c = d.get("comments", [])[index] if index < len(d.get("comments", [])) else {}
            w["active"].setChecked(bool(c))
            w["image"] = c.get("image", "")
            w["label"].setText(Path(w["image"]).name or "未导入截图")
            for key in ("url", "translation"):
                w[key].setText(c.get(key, ""))
            w["start"].setValue(float(c.get("start", 3 + index * 5)))
            w["end"].setValue(float(c.get("end", 7 + index * 5)))
        score = d.get("score", {})
        self.score_mode.setCurrentIndex(0 if score.get("status") == "pending" else 1)
        for k, control in self.dimensions.items():
            control.setValue((score.get("dimensions") or {}).get(k, 0))
        self.reason.setText(score.get("reason", ""))
        for key, control in self.review.items():
            control.setChecked(d.get("review", {}).get(key, False))
        self.loading = False
        self.dirty = False
        self.saved.setText(f"已保存 · r{document['revision']}")
        self.update_assets()
        self.update_range()
        self.preview_source()
        core.save_json(self.store.root / "recent.json", {"project_id": project_id})
        is_quick = d.get("layout") == "quick"
        self.tabs.setTabVisible(0, not is_quick)
        self.tabs.setTabVisible(1, not is_quick)
        self.tabs.setTabVisible(2, not is_quick)
        self.tabs.setTabVisible(5, is_quick)
        self.tabs.setCurrentIndex(5 if is_quick else 0)
        if is_quick:
            self.notice.setText("快速切片：原片已有字幕直接保留。填写标题、背景与观察，单条或列表批量导出；评分默认待评。")

    def new_project(self, quick_mode=False):
        if not self.save():
            return
        document = self.store.create()
        if quick_mode:
            preset = {}
            try:
                preset = read_json(self.store.root / "quick-preset.json")
                if not isinstance(preset, dict):
                    preset = {}
            except (OSError, ValueError):
                pass
            document["job"] = quick.defaults(document["job"], preset)
            document["job"]["title"] = "新切片"
            self.store.save(document)
            self.resolution.setCurrentIndex(1 if preset.get("resolution_index") == 1 else 0)
        self.refresh_projects()
        self.open_project(document["project_id"])

    def migrate(self):
        path = QFileDialog.getExistingDirectory(self, "选择含 job.json 的旧任务目录")
        if path and self.save():
            try:
                d = self.store.migrate(path)
                self.refresh_projects()
                self.open_project(d["project_id"])
                self.notice.setText("旧任务已复制迁移，旧版数据和素材保持原样。")
            except Exception as exc:
                self.notice.setText(str(exc))

    def restore_project(self):
        path = QFileDialog.getOpenFileName(self, "选择项目 snapshots 内的历史JSON；现文件会另行备份", str(self.store.projects), "项目快照 (*.json)")[0]
        if not path or not self.save():
            return
        try:
            document = self.store.restore(path)
            self.refresh_projects()
            self.open_project(document["project_id"])
            self.notice.setText("快照已恢复，恢复前的项目文件已留存于 snapshots。")
        except Exception as exc:
            self.notice.setText(str(exc))

    def import_file(self, key, provided=None):
        path = provided or QFileDialog.getOpenFileName(self, "导入素材", "", "视频/音频/字幕 (*.mp4 *.mov *.mkv *.webm *.wav *.mp3 *.m4a *.aac *.srt);;所有文件 (*)")[0]
        if not path:
            return
        try:
            if key == "subtitle_file":
                core.read_srt(path)
            else:
                meta = core.probe(path)
                if key == "video" and not meta["has_video"] or key == "narration_audio" and not meta["has_audio"]:
                    raise core.PipelineError("该文件没有所需的视频或音频流。")
            reference = core.import_asset(self.project_folder(), path)
            self.document["job"][key] = reference
            if key == "video":
                self.start.setValue(0)
                self.duration.setValue(min(30, meta["duration"]))
            self.changed()
            self.save()
            self.update_assets()
            if key == "video":
                self.preview_source()
        except Exception as exc:
            self.notice.setText(str(exc))

    def clear_asset(self, key):
        self.document["job"][key] = ""
        self.changed()
        self.update_assets()

    def import_comment(self, index):
        path = QFileDialog.getOpenFileName(self, "选择真实评论截图", "", "图片 (*.png *.jpg *.jpeg *.webp)")[0]
        if not path:
            return
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
            w = self.comment_widgets[index]
            w["image"] = core.import_asset(self.project_folder(), path)
            w["label"].setText(Path(path).name)
            w["active"].setChecked(True)
            self.changed()
        except Exception as exc:
            self.notice.setText(str(exc))

    def update_assets(self):
        d = self.document["job"]
        self.video_label.setText("视频：" + (Path(d.get("video", "")).name or "未导入"))
        self.quick_video_label.setText(self.video_label.text())
        self.voice_label.setText("配音：" + (Path(d.get("narration_audio", "")).name or "未导入 · 可使用甜美解说"))
        self.srt_label.setText("字幕：" + (Path(d.get("subtitle_file", "")).name or "未导入SRT · 按字数估时，需试听校准"))

    def enqueue(self, kind):
        if not self.save():
            return
        try:
            task_id = self.store.enqueue(self.document, kind, 1080 if self.resolution.currentIndex() == 0 else 540)
            self.notice.setText(f"已排队 · r{self.document['revision']}。可以继续编辑，任务使用提交时的快照。")
            self.tabs.setCurrentIndex(4)
            self.tick()
            self.select_task(task_id)
        except Exception as exc:
            self.notice.setText(str(exc))

    def tick(self):
        # A starting process owns this task even before its OS lease is acquired.
        if self.process and self.process.state() == QProcess.NotRunning:
            self.process.deleteLater()
            self.process = None
            self.active_task = None
        if not self.process:
            self.store.reconcile()
        else:
            run = self.store.runs / self.active_task
            if (run / "result.json").exists():
                self.store.reconcile()
            elif (run / "progress.json").exists():
                try:
                    event = read_json(run / "progress.json")
                    self.store.update_task(self.active_task, message=event["message"], progress=event["progress"])
                except (ValueError, OSError, KeyError):
                    pass
        rows = self.store.tasks()
        if not self.process and not any(row["state"] == "RUNNING" for row in rows):
            pending = next((r for r in reversed(rows) if r["state"] == "QUEUED"), None)
            if pending:
                self.start_task(pending["id"])
                rows = self.store.tasks()
        selected = self.queue_list.currentItem()
        selected_id = selected.data(Qt.UserRole) if selected else None
        self.queue_list.blockSignals(True)
        self.queue_list.clear()
        for row in rows:
            if row["id"] not in self.task_titles:
                try:
                    self.task_titles[row["id"]] = core.load_job(self.store.runs / row["id"])["title"]
                except Exception:
                    self.task_titles[row["id"]] = ""
            label = f"{STATUS.get(row['state'], row['state'])} · {self.task_titles[row['id']]} · {'导出' if row['kind'] == 'render' else '下载'} · r{row['revision']}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, row["id"])
            self.queue_list.addItem(item)
            if row["id"] == selected_id:
                self.queue_list.setCurrentItem(item)
        self.queue_list.blockSignals(False)
        self.show_task()

    def start_task(self, task_id):
        run = self.store.runs / task_id
        self.store.update_task(task_id, state="RUNNING", message="启动独立工作进程")
        self.active_task = task_id
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(run))
        self.process.setStandardErrorFile(str(run / "worker-stderr.log"))
        self.process.setStandardOutputFile(str(run / "worker-stdout.log"))
        if getattr(sys, "frozen", False):
            program, args = sys.executable, ["--worker", str(run)]
        else:
            program = sys.executable
            args = ["-X", "utf8", str(Path(__file__).resolve().parent.parent / "studio_entry.py"), "--worker", str(run)]
        self.process.start(program, args)
        if not self.process.waitForStarted(3000):
            self.store.update_task(task_id, state="FAILED", message="无法启动工作进程，请检查安装文件完整性。")

    def select_task(self, task_id):
        for index in range(self.queue_list.count()):
            item = self.queue_list.item(index)
            if item.data(Qt.UserRole) == task_id:
                self.queue_list.setCurrentItem(item)
                break

    def selected_task(self):
        item = self.queue_list.currentItem()
        task_id = item.data(Qt.UserRole) if item else None
        return next((r for r in self.store.tasks() if r["id"] == task_id), None)

    def show_task(self, *args):
        row = self.selected_task()
        if row:
            self.task_detail.setText(row["message"] or "等待开始")
            self.progress.setValue(round(row["progress"]))

    def cancel_task(self):
        row = self.selected_task()
        if row:
            self.store.cancel(row["id"])
            self.notice.setText("已请求取消。下载网络请求最长需等待当前超时；项目和素材保留。")

    def retry_task(self):
        row = self.selected_task()
        if row:
            try:
                self.store.retry(row["id"])
                self.tick()
            except Exception as exc:
                self.notice.setText(str(exc))

    def use_result(self):
        row = self.selected_task()
        if not row or row["state"] != "SUCCEEDED":
            self.notice.setText("请选择已完成的任务。")
            return
        if row["kind"] == "render":
            self.play_file(Path(row["output"]) / "preview.mp4", True)
        elif row["project_id"] != self.document["project_id"]:
            self.notice.setText("先打开该下载任务所属项目，再导入结果。")
        else:
            self.import_file("video", row["output"])
            self.notice.setText("下载结果已复制到项目；请核查原帖日期、背景和素材使用依据。")

    def open_task(self):
        row = self.selected_task()
        if row:
            self.open_path(row["output"] if row["kind"] == "render" and row["output"] else self.store.runs / row["id"])

    def preview_source(self):
        if self.document and self.document["job"].get("video"):
            self.play_file(core.asset_path(self.project_folder(), self.document["job"]["video"]), False)

    def play_file(self, path, output=False):
        path = Path(path)
        if path.is_file():
            self.last_played = str(path.resolve())
            self.preview_is_output = output
            self.player.stop()
            self.video_widget.frame = None
            self.video_widget.clear()
            # Show a first frame without automatically playing audio.
            try:
                import av
                with av.open(self.last_played) as media:
                    frame = next(media.decode(video=0))
                    from PIL.ImageQt import ImageQt
                    self.video_widget.frame = QPixmap.fromImage(ImageQt(frame.to_image()))
                    self.video_widget.refresh()
            except Exception:
                self.video_widget.setText("点击播放预览；也可使用外部播放器")
            self.player.setSource(QUrl.fromLocalFile(self.last_played))
            self.preview_label.setText("预览 · 已生成草稿" if output else "预览 · 原始素材")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.time_label.setText(f"{position / 1000:.2f}s / {self.player.duration() / 1000:.2f}s")

    def set_in(self):
        if self.preview_is_output:
            self.notice.setText("请先切回原片，再设置选段。")
            return
        self.start.setValue(self.player.position() / 1000)

    def set_out(self):
        if self.preview_is_output:
            self.notice.setText("请先切回原片，再设置选段。")
            return
        duration = self.player.position() / 1000 - self.start.value()
        if duration > 0:
            self.duration.setValue(duration)

    def update_range(self):
        self.range_label.setText(f"原片 {self.start.value():.2f}s → {self.start.value() + self.duration.value():.2f}s\n成片 {self.duration.value():.2f}s · 配音从 {self.voice_start.value():.2f}s 进入")

    def copy_prompt(self):
        self.gather()
        QApplication.clipboard().setText(core.writing_prompt(self.document["job"]))
        self.notice.setText("提示词已复制；可交给当前AI编辑，不产生API调用。")

    def open_animation(self):
        from .animation_dialog import AnimationDialog
        if not getattr(self, "animation_dialog", None):
            self.animation_dialog = AnimationDialog(self.store.root, self)
        self.animation_dialog.show()
        self.animation_dialog.raise_()

    def open_path(self, path):
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    def change_workspace(self):
        path = QFileDialog.getExistingDirectory(self, "选择工作区；下次启动使用。现有项目保留原位置。")
        if path and self.save():
            self.workspace_next = path
            self.notice.setText("新工作区将在重启后启用；现有任务继续在原工作区完成。")

    def closeEvent(self, event):
        if not self.save():
            QMessageBox.warning(self, "尚未保存", "保存失败，窗口将保留。请先处理工作区写入错误，或复制文稿备份。")
            event.ignore()
            return
        animation = getattr(self, "animation_dialog", None)
        if animation and animation.process and animation.process.state() != QProcess.NotRunning:
            animation.cancel_run()
            self.notice.setText("正在取消动画生成；项目已保存，完成后请再次关闭窗口。")
            event.ignore()
            return
        running = [r for r in self.store.tasks() if r["state"] == "RUNNING"]
        if running:
            answer = QMessageBox.question(self, "仍有任务运行", "退出会请求取消当前任务并保留项目；排队任务下次继续。现在退出？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            for row in running:
                self.store.cancel(row["id"])
            if self.process:
                # Network downloads may wait for timeout. Keep UI open until worker exits.
                self.notice.setText("正在取消任务；完成后请再次关闭窗口。")
                event.ignore()
                return
        self.poll.stop()
        self.player.stop()
        self.store.close()
        event.accept()


def launch(workspace, screenshot=None, check_export=None, check_batch=False, check_animation=None):
    configure_windows_identity()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("EarthPeopleLogStudio")
    app.setOrganizationName("EarthPeopleLog")
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = Window(workspace)
    window.setWindowIcon(app.windowIcon())
    window.show()
    if check_animation:
        import time
        began = time.monotonic()
        window.open_animation()
        dialog = window.animation_dialog
        dialog.resolution.setCurrentIndex(1)
        dialog.duration.setValue(1)
        timer = QTimer(window)
        timer.setInterval(300)
        def verify_animation():
            if dialog.output or (dialog.request and dialog.process is None) or time.monotonic() - began > 100:
                core.save_json(check_animation, {"output": str(dialog.output) if dialog.output else None,
                    "message": dialog.message.text(), "at": core.now(),
                    "city_count": dialog.target.count(),
                    "coordinate_fields": hasattr(dialog,"lat") or hasattr(dialog,"lon"),
                    "target": dialog.settings()["target"]})
                dialog.grab().save(str(Path(check_animation).with_suffix(".png")))
                timer.stop()
                dialog.close()
                window.close()
        timer.timeout.connect(verify_animation)
        timer.start()
        QTimer.singleShot(400, dialog.start)
    if check_export:
        # Only explicit diagnostic mode: exercise the packaged GUI -> QProcess path.
        import time
        began = time.monotonic()
        check_timer = QTimer(window)
        check_timer.setInterval(300)
        def verify_export():
            rows = window.store.tasks()
            selected = window.queue_list.currentItem()
            task_id = selected.data(Qt.UserRole) if selected else None
            task = next((r for r in rows if r["id"] == task_id), None)
            completed = (bool(rows) and all(r["state"] in ("SUCCEEDED", "FAILED", "INTERRUPTED", "CANCELLED") for r in rows)) if check_batch else (task and task["state"] in ("SUCCEEDED", "FAILED", "INTERRUPTED"))
            if completed or time.monotonic() - began > 100:
                core.save_json(check_export, {"task": task, "tasks": rows, "notice": window.notice.text(), "at": core.now()})
                check_timer.stop()
                window.close()
        QTimer.singleShot(500, window.enqueue_quick_batch if check_batch else lambda: window.enqueue("render"))
        check_timer.timeout.connect(verify_export)
        check_timer.start()
    if screenshot and not check_export:
        def capture():
            window.grab().save(str(screenshot))
            window.close()
        QTimer.singleShot(1800, capture)
    app.exec()
    return getattr(window, "workspace_next", None)
