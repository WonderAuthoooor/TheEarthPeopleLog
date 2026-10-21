"""Actual GUI autosave, worker render, cancellation and crash recovery checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from pipeline import core
from studio.storage import Workspace, read_json


def wait_for(predicate, seconds=60):
    start = time.monotonic()
    while not predicate():
        if time.monotonic() - start > seconds:
            raise AssertionError("Timed out")
        time.sleep(.1)


def run(executable=None):
    stamp = str(time.time_ns())
    workspace = ROOT / ".runtime" / ("studio-qa-" + stamp) / "中文 空格 工作区"
    store = Workspace(workspace)
    doc = store.migrate(ROOT / ".pipeline" / "jobs" / "20261018-55d72b73")
    doc["job"]["duration"] = 4
    doc["job"]["script"] = "内部技术测试，数据尚未核查。"
    store.save(doc)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    def start(task):
        store.update_task(task, state="RUNNING")
        command = [str(executable)] if executable else [sys.executable, "-X", "utf8", str(ROOT / "studio_entry.py")]
        return subprocess.Popen([*command, "--worker", str(store.runs / task)], creationflags=flags)
    task = store.enqueue(doc, resolution=540)
    child = start(task)
    wait_for(lambda: child.poll() is not None, 120)
    store.reconcile()
    result = store.tasks()[0]
    assert result["state"] == "SUCCEEDED", result
    output = Path(result["output"])
    meta = core.probe(output / "preview.mp4")
    assert meta["width"] == 540 and meta["height"] == 960 and meta["has_audio"]
    assert abs(meta["duration"] - 4) < .2
    assert store.enqueue(doc, resolution=540) == task, "valid cache must reuse task"
    (output / "preview.mp4").write_bytes(b"damaged output")
    repair = store.enqueue(doc, resolution=540)
    assert repair != task, "corrupt cache must be rebuilt"
    child = start(repair)
    wait_for(lambda: child.poll() is not None, 120)
    store.reconcile()
    assert next(r for r in store.tasks() if r["id"] == repair)["state"] == "SUCCEEDED"
    # A longer render provides time to exercise both cancellation and worker death.
    doc["job"]["duration"] = 30
    store.save(doc)
    cancelled = store.enqueue(doc)
    child = start(cancelled)
    wait_for(lambda: (store.runs / cancelled / "progress.json").exists())
    time.sleep(.7)
    store.cancel(cancelled)
    wait_for(lambda: child.poll() is not None, 20)
    store.reconcile()
    assert next(r for r in store.tasks() if r["id"] == cancelled)["state"] == "CANCELLED"
    crashed = store.enqueue(doc)
    child = start(crashed)
    def has_media():
        try:
            return read_json(store.runs / crashed / "progress.json").get("media_pid")
        except (OSError, ValueError):
            return False
    wait_for(has_media)
    media_pid = has_media()
    media_handle = None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        media_handle = kernel.OpenProcess(0x00100000, False, media_pid)
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(5)"], creationflags=flags)
    child.kill()  # Only the Popen object started by this test.
    child.wait(timeout=10)
    if media_handle:
        assert kernel.WaitForSingleObject(media_handle, 10000) == 0, "orphan FFmpeg survived worker exit"
        kernel.CloseHandle(media_handle)
    assert unrelated.poll() is None, "unrelated owned control process was terminated"
    unrelated.wait(timeout=8)
    store.reconcile()
    assert next(r for r in store.tasks() if r["id"] == crashed)["state"] == "INTERRUPTED"
    store.retry(crashed)
    store.cancel(crashed)  # Do not leave a queued test render behind.
    store.close()
    core.save_json(workspace.parent / "qa.json", {"at": core.now(), "frozen": bool(executable), "workspace": str(workspace), "output": str(next(r for r in Workspace_read_tasks(workspace) if r["id"] == repair)["output"]), "checks": ["actual render", "cache reuse", "corrupt cache repair", "cooperative cancellation", "worker crash recovery", "Chinese space path"]})
    print(workspace.parent / "qa.json")
    return workspace


def Workspace_read_tasks(workspace):
    store = Workspace(workspace)
    try:
        return store.tasks()
    finally:
        store.close()


def gui_check(workspace):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from studio.app import Window
    app = QApplication.instance() or QApplication([])
    window = Window(workspace)
    window.show()
    window.poll.stop()
    window.title.setText("自动保存测试 · 重开仍在")
    window.script.setPlainText("这是界面自动保存测试。")
    QTest.qWait(900)
    assert not window.dirty
    project_id = window.document["project_id"]
    assert window.store.load(project_id)["job"]["title"] == "自动保存测试 · 重开仍在"
    # Validate real local MP4/AAC through QtMultimedia, not merely file metadata.
    window.player.play()
    QTest.qWait(1800)
    assert window.player.duration() > 0, window.player.errorString()
    assert window.player.position() > 0, window.player.errorString()
    assert window.video_widget.frame is not None, "decoded preview frame missing"
    window.duration.setValue(4)
    window.enqueue("render")
    # Real QProcess launch from the GUI, while editing a later document revision.
    window.title.setText("渲染期间继续编辑 · 不覆盖")
    window.poll.start()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        QTest.qWait(250)
        row = window.store.tasks()[0]
        if row["state"] in ("SUCCEEDED", "FAILED", "INTERRUPTED"):
            break
    assert row["state"] == "SUCCEEDED", row
    window.select_task(row["id"])
    window.use_result()
    window.player.play()
    QTest.qWait(1000)
    assert window.preview_is_output and window.player.duration() > 0
    assert window.store.load(project_id)["job"]["title"] == "渲染期间继续编辑 · 不覆盖"
    window.grab().save(str(Path(workspace).parent / "workbench.png"))
    QTest.qWait(700)  # Let QProcess finish before closing the test window.
    window.close()
    QTest.qWait(200)
    reopened = Window(workspace)
    reopened.poll.stop()
    assert reopened.title.text() == "渲染期间继续编辑 · 不覆盖"
    reopened.close()
    print("Qt autosave/reopen/MP4 playback passed")


if __name__ == "__main__":
    workspace = run(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    if len(sys.argv) == 1:
        gui_check(workspace)
