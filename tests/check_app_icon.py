"""Check shipped assets and actual Windows executable icon resources."""
from pathlib import Path
import ctypes
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from PIL import Image
from PySide6.QtGui import QGuiApplication, QIcon
import pefile
from studio import __version__
from studio.branding import ICON_PATH


def digest(p):
    with p.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if __name__ == "__main__":
    app = QGuiApplication([])
    wanted = {16, 20, 24, 32, 40, 48, 64, 128, 256}
    with Image.open(ICON_PATH) as image:
        assert image.format == "ICO"
        assert image.ico.sizes() == {(n, n) for n in wanted}
    icon = QIcon(str(ICON_PATH))
    for size in wanted:
        assert not icon.pixmap(size, size).isNull(), size
    folder = ROOT / "dist" / __version__ / "EarthPeopleLogStudio"
    shipped = folder / "_internal" / "studio" / "assets" / "app-icon.ico"
    assert digest(shipped) == digest(ICON_PATH)
    results = []
    for exe in [folder / "EarthPeopleLogStudio.exe",
                ROOT / "dist" / f"EarthPeopleLogStudio-{__version__}-Setup.exe"]:
        with pefile.PE(str(exe)) as pe:
            resources = {entry.id: entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}
            assert 3 in resources and 14 in resources, exe
            assert len(resources[3].directory.entries) >= len(wanted), exe
            # Confirm the high-resolution original is embedded, not a default icon.
            ico_bytes = ICON_PATH.read_bytes()
            count = struct.unpack_from("<H", ico_bytes, 4)[0]
            entry = next(6 + 16 * n for n in range(count)
                         if ico_bytes[6 + 16 * n:8 + 16 * n] == b"\x00\x00")
            size, offset = struct.unpack_from("<II", ico_bytes, entry + 8)
            payload = ico_bytes[offset:offset + size]
            assert payload in exe.read_bytes(), exe
        shell = ctypes.windll.shell32
        shell.ExtractIconExW.argtypes = [ctypes.c_wchar_p, ctypes.c_int,
                                        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint]
        shell.ExtractIconExW.restype = ctypes.c_uint
        large, small = ctypes.c_void_p(), ctypes.c_void_p()
        extracted = shell.ExtractIconExW(str(exe), 0, ctypes.byref(large), ctypes.byref(small), 1)
        assert extracted > 0 and large.value and small.value, (exe, extracted)
        ctypes.windll.user32.DestroyIcon.argtypes = [ctypes.c_void_p]
        ctypes.windll.user32.DestroyIcon(large)
        ctypes.windll.user32.DestroyIcon(small)
        results.append({"path": str(exe.relative_to(ROOT)), "sha256": digest(exe), "windows_icon_extraction": True})
    report = ROOT / "state" / "verification" / "2026-10-19-app-icon" / "icons.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"version": __version__, "sizes": sorted(wanted), "icon_sha256": digest(ICON_PATH),
                                  "packaged_asset_matches": True, "executables": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report)
