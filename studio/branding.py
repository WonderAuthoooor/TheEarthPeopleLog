"""Brand assets resolve identically in source and PyInstaller onedir builds."""
from pathlib import Path
import sys

ICON_PATH = Path(__file__).resolve().parent / "assets" / "app-icon.ico"
APP_ID = "EarthPeopleLog.Studio"


def configure_windows_identity():
    if sys.platform == "win32":
        import ctypes
        # A stable identity keeps the taskbar icon separate from the Python host.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (OSError, AttributeError):
            pass
