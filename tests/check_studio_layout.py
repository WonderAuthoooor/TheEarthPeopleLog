"""Qt logical layout and screenshot check at explicit display scale factors."""
from pathlib import Path
import os
import sys
ROOT = Path(__file__).resolve().parent.parent
os.environ["QT_SCALE_FACTOR"] = sys.argv[1]
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from studio.app import Window

app = QApplication([])
window = Window(ROOT / ".runtime" / ("layout-qa-" + sys.argv[1]))
window.poll.stop()
quick_mode = len(sys.argv) > 2 and sys.argv[2] == "quick"
if quick_mode:
    window.new_project(True)
window.resize(1000, 650)
window.show()
QTest.qWait(300)
assert window.export_button.isVisible()
assert window.export_button.mapTo(window, window.export_button.rect().bottomRight()).x() < window.width()
assert window.tabs.tabBar().width() <= window.tabs.width()
folder = ROOT / ".runtime" / "distribution-qa"
folder.mkdir(exist_ok=True)
if quick_mode:
    assert window.tabs.isTabVisible(5) and window.quick_context.isVisible()
window.grab().save(str(folder / (("scale-quick-" if quick_mode else "scale-") + sys.argv[1] + ".png")))
window.close()
print("quick" if quick_mode else "classic", "scale", sys.argv[1], "passed")
