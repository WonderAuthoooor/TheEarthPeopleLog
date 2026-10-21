"""Actual quick GUI, batch workers, covers, output cache and template persistence."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from pipeline import core
from studio.storage import Workspace, read_json
from studio import quick


def prepare(workspace):
    store = Workspace(workspace)
    document = store.migrate(ROOT / ".pipeline" / "jobs" / "20261018-55d72b73")
    document["job"] = quick.defaults(document["job"])
    document["job"].update(title="快速切片 · 内部技术测试", context="用户提供素材；统计口径尚未核查", observation="先核对口径，再看数字。", duration=3., cover_at=1., quick_theme="paper")
    store.save(document)
    store.close()
    return document["project_id"]


def verify_outputs(row, expected_seconds):
    assert row["state"] == "SUCCEEDED", row
    output = Path(row["output"])
    media = core.probe(output / "preview.mp4")
    assert abs(media["duration"] - expected_seconds) < .1 and media["has_audio"]
    for name in ("cover.png", "title.txt", "description.txt", "publish-copy.json"):
        assert (output / name).is_file(), name
    from PIL import Image
    with Image.open(output / "cover.png") as image:
        assert image.size == (media["width"], media["height"])
    publish = read_json(output / "publish-copy.json")
    assert "观察：" in publish["description"] and "待评" in publish["description"]
    return output


def gui(workspace):
    from PySide6.QtWidgets import QApplication, QTableWidgetItem
    from PySide6.QtTest import QTest
    from studio.app import Window
    app = QApplication.instance() or QApplication([])
    window = Window(workspace)
    window.poll.stop()
    window.show()
    assert window.tabs.currentIndex() == 5 and not window.tabs.isTabVisible(0)
    assert not window.document["job"]["narration_audio"] and window.volume.value() == 1
    window.resolution.setCurrentIndex(1)
    window.quick_theme.setCurrentIndex(0)
    window.save_quick_preset()
    preset = read_json(Path(workspace) / "quick-preset.json")
    assert preset == {"theme": "slate", "resolution_index": 1}
    window.add_quick_cut()
    window.start.setValue(3)
    window.quick_cover.setValue(4)
    window.title.setText("第二个看点 · 技术测试")
    window.add_quick_cut()
    window.quick_table.setItem(1, 2, QTableWidgetItem("1000"))
    window.enqueue_quick_batch()
    assert not window.store.tasks(), "bad last row must not queue the first row"
    window.quick_table.setItem(1, 2, QTableWidgetItem("6"))
    window.enqueue_quick_batch()
    assert len(window.store.tasks()) == 2
    window.poll.start()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        QTest.qWait(200)
        tasks = window.store.tasks()
        if all(r["state"] in ("SUCCEEDED", "FAILED", "INTERRUPTED") for r in tasks):
            break
    outputs = [verify_outputs(row, 3) for row in window.store.tasks()]
    # Editing list rows does not alter already queued snapshots.
    assert core.load_job(window.store.runs / tasks[0]["id"])["clip_start"] == 3
    window.select_task(tasks[0]["id"])
    window.use_result()
    window.player.play()
    QTest.qWait(1000)
    assert window.video_widget.frame is not None
    window.grab().save(str(Path(workspace).parent / "quick-workbench.png"))
    window.tabs.setCurrentIndex(5)
    window.grab().save(str(Path(workspace).parent / "quick-settings.png"))
    assert len(window.document["job"]["quick_clips"]) == 2
    window.player.stop()
    QTest.qWait(900)
    window.close()
    QTest.qWait(200)
    reopened = Window(workspace)
    reopened.poll.stop()
    assert reopened.quick_table.rowCount() == 2
    reopened.new_project(True)
    assert reopened.quick_theme.currentIndex() == 0 and reopened.resolution.currentIndex() == 1
    reopened.close()
    core.save_json(Path(workspace).parent / "report.json", {"at": core.now(), "outputs": [str(p) for p in outputs], "checks": ["quick GUI", "all ranges validate before queue", "two actual queued clips", "covers and posting copy", "original audio", "preset reuse", "batch autosave/reopen"]})
    print(Path(workspace).parent / "report.json")


if __name__ == "__main__":
    folder = ROOT / ".runtime" / ("quick-qa-" + str(time.time_ns()))
    folder.mkdir()
    workspace = folder / "短新闻 工作区"
    prepare(workspace)
    gui(workspace)
