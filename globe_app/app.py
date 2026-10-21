"""Independent Qt location tool; no studio storage, avatar runtime or service."""
from pathlib import Path
import sys
import time
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont,QIcon
from .dialog import AnimationDialog
from . import __version__
from pipeline import core,cities


def launch(app,workspace,check_export=None):
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EarthPeopleLog.Globe')
    app.setApplicationName('EarthPeopleLogGlobe')
    app.setOrganizationName('EarthPeopleLog')
    app.setWindowIcon(QIcon(str(Path(__file__).parent/'assets/app-icon.ico')))
    app.setFont(QFont('Microsoft YaHei UI',10))
    app.setStyleSheet('QWidget{font-size:14px;} QLineEdit,QComboBox,QDoubleSpinBox{min-height:30px;} QPushButton{padding:8px;}')
    folder=Path(workspace).resolve();folder.mkdir(parents=True,exist_ok=True)
    dialog=AnimationDialog(folder)
    dialog.setWindowIcon(app.windowIcon())
    dialog.setWindowTitle('地球人日志 · 地点动画 '+__version__)
    dialog.show()
    if check_export:
        dialog.mode.setCurrentIndex(1)
        for combo,query in ((dialog.origin,'英国 · 伦敦'),(dialog.target,'日本 · 东京')):
            point=cities.resolve({'city':query})
            for i in range(combo.count()):
                if (combo.itemData(i) or {}).get('id')==point['id']:
                    combo.setCurrentIndex(i);break
        dialog.name.setText('日本 · 东京 · 新闻现场（测试地点）')
        dialog.resolution.setCurrentIndex(1);dialog.duration.setValue(1)
        began=time.monotonic();timer=QTimer(dialog);timer.setInterval(250)
        def finish():
            if dialog.output or (dialog.request and dialog.process is None) or time.monotonic()-began>100:
                core.save_json(check_export,{'version':__version__,'output':str(dialog.output) if dialog.output else None,
                    'message':dialog.message.text(),'at':core.now(),'city_count':dialog.target.count(),
                    'coordinate_fields':hasattr(dialog,'lat') or hasattr(dialog,'lon'),
                    'avatar_fields':any(hasattr(dialog,k) for k in ('mascot_path','score','reason')),
                    'config':dialog.settings()})
                dialog.grab().save(str(Path(check_export).with_suffix('.png')))
                timer.stop();dialog.close()
        timer.timeout.connect(finish);timer.start();QTimer.singleShot(300,dialog.start)
    return app.exec()
