"""Reusable animation generator; separate process keeps the editor responsive."""
from pathlib import Path
import json
import sys
import uuid
from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QDoubleSpinBox, QPushButton, QFileDialog, QProgressBar, QScrollArea, QWidget, QCompleter, QCheckBox, QGridLayout)
from pipeline import core, globe, cities
from . import __version__


class CityCompleter(QCompleter):
    def pathFromIndex(self,index):
        return index.data(Qt.DisplayRole)


def city_picker(points, default_origin=False):
    combo=QComboBox()
    if default_origin:combo.addItem('地球观察站 · 默认起点',None)
    for point in points:
        combo.addItem(point['name']+'  '+point['aliases'][1],point)
        combo.setItemData(combo.count()-1,' '.join([point['name'],*point['aliases']]),Qt.UserRole+1)
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.setMaxVisibleItems(12)
    combo.lineEdit().setPlaceholderText('输入中文城市、英文或国家／地区，选择搜索结果')
    completer=CityCompleter(combo.model(),combo)
    completer.setCompletionRole(Qt.UserRole+1)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setMaxVisibleItems(12)
    combo.setCompleter(completer)
    completer.activated[str].connect(lambda text: combo.setCurrentIndex(combo.findText(text)))
    return combo


class AnimationDialog(QDialog):
    def __init__(self, workspace, parent=None):
        super().__init__(parent)
        self.workspace=Path(workspace)
        self.process=None
        self.request=None
        self.output=None
        self.setWindowTitle('地球人日志 · 地点动画 '+__version__)
        self.resize(740,780)
        layout=QVBoxLayout(self)
        note=QLabel('选择附近城市，填写显示地点，生成纯地球开场或转场。\n导出MP4后，在剪映中与新闻和虚拟主播分别组合。')
        note.setWordWrap(True);layout.addWidget(note)
        fields=QWidget()
        form=QFormLayout(fields)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(fields)
        layout.addWidget(scroll,1)
        self.style=QComboBox();self.style.addItems(['复古夸张 · 橡皮管动画','原版 · 平稳地球'])
        form.addRow('动画风格',self.style)
        self.mode=QComboBox();self.mode.addItems(['开场 · 大手拨动地球','资讯间 · 地点转场'])
        form.addRow('生成类型',self.mode)
        self.locations=list(cities.catalog())
        self.origin=city_picker(self.locations,True)
        form.addRow('从哪里出发',self.origin)
        self.target=city_picker(self.locations);form.addRow('附近城市 · 可搜索',self.target)
        load_locations=QPushButton('从每日选题JSON导入地点');load_locations.clicked.connect(self.import_locations);form.addRow(load_locations)
        self.name=QLineEdit(self.locations[0]['name']);self.name.setMaxLength(120)
        self.name.setPlaceholderText('例如：日本 · 爱知县丰田市某汽车工厂；不改变地球落点')
        form.addRow('动画显示地点 · 可详细填写',self.name)
        self.precision=QLabel('文字默认不生成；如需显示地点，请勾选下方对应项。填写文字不改变落点。');self.precision.setWordWrap(True);form.addRow(self.precision)
        self.text_checks={}
        text_widget=QWidget();text_grid=QGridLayout(text_widget);text_grid.setContentsMargins(0,0,0,0)
        for index,(key,label) in enumerate(globe.TEXT_OPTIONS.items()):
            check=QCheckBox(label);check.setChecked(False)
            self.text_checks[key]=check;text_grid.addWidget(check,index//2,index%2)
        form.addRow('画面文字 · 默认关闭',text_widget)
        self.hand=QComboBox();self.hand.addItem('复古白手套',str(globe.ASSETS/'hands/rubber_glove.svg'));self.hand.addItem('软萌外星手',str(globe.ASSETS/'hands/alien.svg'));self.hand.addItem('机械手套',str(globe.ASSETS/'hands/robot.svg'));form.addRow('开场大手',self.hand)
        row=QHBoxLayout()
        choose=QPushButton('导入手部SVG／透明PNG');choose.clicked.connect(self.choose_hand);row.addWidget(choose)
        form.addRow(row)
        self.show_hand=QCheckBox('开场显示大手');self.show_hand.setChecked(True);form.addRow(self.show_hand)
        self.show_hand.toggled.connect(lambda checked:self.hand.setEnabled(checked and self.mode.currentIndex()==0))
        self.duration=QDoubleSpinBox();self.duration.setRange(1,20);self.duration.setValue(3);self.duration.setSuffix(' 秒');form.addRow('时长',self.duration)
        self.resolution=QComboBox();self.resolution.addItems(['1080 × 1920','540 × 960 · 快速预览']);form.addRow('竖屏输出',self.resolution)
        self.preview=QLabel('生成后显示地点画面');self.preview.setAlignment(Qt.AlignCenter);self.preview.setMinimumHeight(120);self.preview.setMaximumHeight(180);layout.addWidget(self.preview)
        self.progress=QProgressBar();layout.addWidget(self.progress)
        self.message=QLabel('静音MP4可直接导入剪映；人物与评分在其他素材层组合。');self.message.setWordWrap(True);layout.addWidget(self.message)
        actions=QHBoxLayout();layout.addLayout(actions)
        self.generate=QPushButton('生成动画');self.generate.clicked.connect(self.start);actions.addWidget(self.generate)
        self.cancel=QPushButton('取消生成');self.cancel.setEnabled(False);self.cancel.clicked.connect(self.cancel_run);actions.addWidget(self.cancel)
        open_folder=QPushButton('打开输出目录');open_folder.clicked.connect(self.open_folder);actions.addWidget(open_folder)
        self.target.currentIndexChanged.connect(self.change_target)
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.style.currentIndexChanged.connect(lambda _:self.change_mode(self.mode.currentIndex()))
        self.timer=QTimer(self);self.timer.setInterval(400);self.timer.timeout.connect(self.poll)
        self.restore_preferences()

    def restore_preferences(self):
        path=self.workspace/'preferences.json'
        if not path.exists():return
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
            if 'style' not in raw:
                raw['style']='rubberhose'
                hand=Path(raw.get('hand') or '')
                if hand.name=='alien.svg' and hand.parent.name=='hands' and hand.parent.parent.name=='assets':
                    raw['hand']=str(globe.ASSETS/'hands/rubber_glove.svg')
            config=globe.validate(raw)
            self.style.setCurrentIndex(globe.STYLES.index(config['style']))
            self.mode.setCurrentIndex(globe.MODES.index(config['mode']))
            for combo,key in ((self.origin,'origin'),(self.target,'target')):
                point=config[key]
                for index in range(combo.count()):
                    candidate=combo.itemData(index) or {}
                    if candidate.get('id')==(point.get('city_id') or point.get('id')):
                        combo.setCurrentIndex(index);break
            self.name.setText(config['target']['name'])
            self.duration.setValue(config['duration'])
            self.resolution.setCurrentIndex(0 if config['width']==1080 else 1)
            self.show_hand.setChecked(config['show_hand'])
            for key,check in self.text_checks.items():check.setChecked(config['text_options'][key])
            if config.get('hand'):
                index=self.hand.findData(config['hand'])
                if index<0:self.hand.addItem(Path(config['hand']).stem,config['hand']);index=self.hand.count()-1
                self.hand.setCurrentIndex(index)
        except Exception as exc:
            self.message.setText('上次设置未载入，已保留原文件：'+str(exc))

    def change_target(self,index):
        if index<0:return
        item=self.target.itemData(index)
        if item:self.name.setText(item.get('display_name',item['name']))

    def change_mode(self,index):
        self.duration.setValue(([3,1.4] if self.style.currentIndex()==0 else [5,3])[index])
        self.hand.setEnabled(index==0 and self.show_hand.isChecked())
        self.show_hand.setEnabled(index==0)

    def choose_hand(self):
        path,_=QFileDialog.getOpenFileName(self,'选择手部组件','','组件 (*.svg *.png)')
        if path:self.hand.addItem(Path(path).stem,path);self.hand.setCurrentIndex(self.hand.count()-1)

    def import_locations(self):
        path,_=QFileDialog.getOpenFileName(self,'选择资讯包stories.json',str(self.workspace.parent/'content'/'digests'),'选题数据 (*.json)')
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            points=[]
            for story in data['stories']:
                location=dict(story['location'])
                point=dict(cities.resolve(location))
                point['display_name']=location.get('name',point['name'])
                points.append(point)
            for point in points:
                self.locations.append(point)
                label=point['name']+' · '+point['display_name']
                for combo in (self.target,self.origin):
                    combo.addItem(label,point)
                    combo.setItemData(combo.count()-1,' '.join([label,*point['aliases']]),Qt.UserRole+1)
            self.message.setText(f'已导入{len(points)}个资讯地点，请从预设选择。')
        except Exception as exc:self.message.setText('无法导入：'+str(exc))

    def settings(self):
        for combo in (self.origin,self.target):
            if combo.currentIndex()<0 or combo.currentText()!=combo.itemText(combo.currentIndex()):
                raise core.PipelineError('请从城市搜索结果中选定附近城市；详细地址填在动画显示地点栏')
        origin=self.origin.currentData() or {'name':'地球观察站','lat':15,'lon':-20}
        city=self.target.currentData()
        target={'name':self.name.text().strip() or city['name'],'lat':city['lat'],'lon':city['lon'],
                'city_name':city['name'],'city_id':city['id'],'precision':'按附近城市估算，非详细地址精确定位'}
        return globe.validate({'mode':globe.MODES[self.mode.currentIndex()],'style':globe.STYLES[self.style.currentIndex()],'origin':origin,
            'target':target,
            'width':1080 if self.resolution.currentIndex()==0 else 540,'fps':30,'duration':self.duration.value(),
            'hand':self.hand.currentData(),'show_hand':self.show_hand.isChecked(),
            'text_options':{key:check.isChecked() for key,check in self.text_checks.items()}})

    def start(self):
        try:
            config=self.settings()
            core.save_json(self.workspace/'preferences.json',config)
            run=self.workspace/'animation-runs'/uuid.uuid4().hex;run.mkdir(parents=True)
            self.request={'config':config,'output_root':str(self.workspace/'animations'),'progress_file':str(run/'progress.json'),
                          'result_file':str(run/'result.json'),'cancel_file':str(run/'cancel')}
            path=run/'request.json';core.save_json(path,self.request)
            self.process=QProcess(self)
            self.process.setStandardErrorFile(str(run/'stderr.log'))
            self.process.setStandardOutputFile(str(run/'stdout.log'))
            self.process.finished.connect(self.process_finished)
            args=['--animation',str(path)]
            if not getattr(sys,'frozen',False):args=['-X','utf8',str(Path(__file__).resolve().parent.parent/'globe_entry.py')]+args
            self.process.start(sys.executable,args)
            if not self.process.waitForStarted(3000):raise core.PipelineError('动画进程未启动')
            self.generate.setEnabled(False);self.cancel.setEnabled(True);self.progress.setValue(0)
            self.message.setText('正在独立进程生成，可以继续编辑其他项目。');self.timer.start()
        except Exception as exc:self.message.setText(str(exc))

    def poll(self):
        if self.request:
            path=Path(self.request['progress_file'])
            if path.exists():
                try:self.progress.setValue(json.loads(path.read_text(encoding='utf-8'))['progress'])
                except (OSError,ValueError,KeyError):pass

    def process_finished(self,*args):
        self.timer.stop();self.generate.setEnabled(True);self.cancel.setEnabled(False)
        try:
            result=json.loads(Path(self.request['result_file']).read_text(encoding='utf-8'))
            if result['status']!='succeeded':raise core.PipelineError(result.get('error','生成未完成'))
            self.output=Path(result['output']);self.progress.setValue(100)
            pixmap=QPixmap(str(self.output/'last-frame.png'))
            self.preview.setPixmap(pixmap.scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
            self.message.setText('已生成：'+str(self.output)+'。将MP4放在剪映开场或相邻新闻之间。')
        except Exception as exc:self.message.setText(str(exc))
        self.process.deleteLater();self.process=None

    def cancel_run(self):
        if self.request:Path(self.request['cancel_file']).touch();self.message.setText('已请求取消，等待当前帧结束。')

    def open_folder(self):
        path=self.output or self.workspace/'animations'
        if path.exists():QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self,event):
        if self.process and self.process.state()!=QProcess.NotRunning:
            self.cancel_run();event.ignore();return
        event.accept()
