"""Render the editable SVG into Windows multi-resolution ICO and preview PNG."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
from PIL import Image
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def generate():
    assets = ROOT / "studio" / "assets"
    renderer = QSvgRenderer(str(assets / "app-icon.svg"))
    if not renderer.isValid():
        raise RuntimeError("应用图标SVG无效")
    images = {}
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256, 512):
        canvas = QImage(size, size, QImage.Format_RGBA8888)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        images[size] = Image.frombytes("RGBA", (size, size), bytes(canvas.bits()))
    images[512].save(assets / "app-icon.png")
    sizes = [(n, n) for n in images if n <= 256]
    images[256].save(assets / "app-icon.ico", sizes=sizes,
                     append_images=[images[n] for n in images if n < 256])
    print(assets / "app-icon.ico")


if __name__ == "__main__":
    generate()
