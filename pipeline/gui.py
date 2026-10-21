"""Tk desktop UI; background tasks never access Tk widgets directly."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .core import (DIMENSIONS, PipelineError, ROOT, STORE, asset_path, download_x, import_asset,
                   load_job, new_job, probe, render, save_job, save_json, writing_prompt)


class App:
    def __init__(self, root):
        self.root = root
        self.directory = None
        self.data = None
        self.busy = False
        self.events = queue.Queue()
        self.fields = {}
        self.comment_fields = []
        self.key = ""
        self.voice_id = ""
        self.voice_model = "speech-2.8-turbo"
        self.text_model = "MiniMax-M2.7"
        self.speed = 1.0
        self.emotion = ""
        root.title("地球人日志 · 视频草稿流水线")
        root.geometry("1060x850")
        root.minsize(880, 680)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=5)
        toolbar = ttk.Frame(root, padding=10)
        toolbar.pack(fill="x")
        for label, action in (("新建任务", self.new), ("打开任务", self.open), ("保存任务", self.save),
                              ("打开任务目录", self.open_directory), ("接口设置（可选）", self.settings)):
            ttk.Button(toolbar, text=label, command=action).pack(side="left", padx=3)
        self.job_label = tk.StringVar(value="先新建任务，或打开已保存的job.json")
        ttk.Label(root, textvariable=self.job_label, padding=(12, 2)).pack(anchor="w")
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=10, pady=6)
        self.tab = ttk.Frame(tabs, padding=12)
        self.comments_tab = ttk.Frame(tabs, padding=12)
        self.script_tab = ttk.Frame(tabs, padding=12)
        self.score_tab = ttk.Frame(tabs, padding=12)
        for frame, name in ((self.tab, "1 素材与选段"), (self.comments_tab, "2 评论截图"),
                            (self.script_tab, "3 口播与字幕"), (self.score_tab, "4 文明观察")):
            tabs.add(frame, text=name)
        self.tab.columnconfigure(1, weight=1)
        self.row(self.tab, 0, "title", "本期标题")
        self.row(self.tab, 1, "source_url", "X 原帖链接", "尝试下载", self.download)
        self.row(self.tab, 2, "source_note", "画面来源标注")
        self.row(self.tab, 3, "event_date", "事件日期（可先留空）")
        self.row(self.tab, 4, "video", "原视频", "选择视频", lambda: self.pick("video"))
        ttk.Button(self.tab, text="播放原片", command=self.open_source).grid(row=4, column=3, padx=4)
        self.row(self.tab, 5, "clip_start", "原片选段起点（秒）")
        self.row(self.tab, 6, "duration", "成片时长（秒）")
        self.row(self.tab, 7, "narration_start", "配音从成片第几秒开始")
        self.row(self.tab, 8, "original_volume", "配音期间原声比例（0–1）")
        self.media_label = tk.StringVar(value="导入后显示原片尺寸与时长。")
        ttk.Label(self.tab, textvariable=self.media_label, wraplength=800).grid(row=9, column=0, columnspan=3, sticky="w", pady=12)
        ttk.Label(self.tab, text="横屏保留完整画面；最多5分钟。自动下载失败时，可导入Chrome扩展保存的视频。", wraplength=800).grid(row=10, column=0, columnspan=3, sticky="w")
        for i in range(2):
            box = ttk.LabelFrame(self.comments_tab, text=f"评论 {i+1}（可不放）", padding=10)
            box.pack(fill="x", pady=8)
            box.columnconfigure(1, weight=1)
            variables = {}
            for r, (key, label) in enumerate((("image", "真实截图"), ("url", "评论定位链接"),
                                             ("translation", "中文译文或简短解释"), ("start", "显示起点（成片秒）"), ("end", "显示终点（成片秒）"))):
                variable = tk.StringVar()
                variables[key] = variable
                ttk.Label(box, text=label).grid(row=r, column=0, sticky="w", padx=4, pady=4)
                ttk.Entry(box, textvariable=variable).grid(row=r, column=1, sticky="ew", padx=4)
                if key == "image":
                    ttk.Button(box, text="选择图片", command=lambda index=i: self.pick_comment(index)).grid(row=r, column=2)
            self.comment_fields.append(variables)
        ttk.Label(self.comments_tab, text="只导入真实截图；译文单独呈现，不生成假网友、假点赞数。截图过长时建议先裁出评论主体。", wraplength=850).pack(anchor="w", pady=8)
        ttk.Label(self.script_tab, text="事实材料（供写稿；贴入已核实背景。链接本身不能替代看过视频）").pack(anchor="w")
        self.facts = ScrolledText(self.script_tab, height=5, font=("Microsoft YaHei UI", 10), wrap="word")
        self.facts.pack(fill="x", pady=4)
        writing = ttk.Frame(self.script_tab)
        writing.pack(fill="x")
        ttk.Button(writing, text="导出写稿提示词", command=self.export_prompt).pack(side="left")
        ttk.Button(writing, text="AI写稿建议（需接口）", command=self.generate_writing).pack(side="left", padx=6)
        ttk.Label(self.script_tab, text="口播稿（每行一段；可直接粘贴你和AI写好的稿件）").pack(anchor="w", pady=(8, 0))
        self.script = ScrolledText(self.script_tab, height=7, font=("Microsoft YaHei UI", 11), wrap="word")
        self.script.pack(fill="both", expand=True, pady=4)
        voice = ttk.Frame(self.script_tab)
        voice.pack(fill="x")
        voice.columnconfigure(1, weight=1)
        self.row(voice, 0, "narration_audio", "配音音频", "导入音频", lambda: self.pick("narration_audio"))
        self.row(voice, 1, "subtitle_file", "准确SRT（可选）", "导入字幕", lambda: self.pick("subtitle_file"))
        ttk.Button(voice, text="MiniMax分段配音（需接口）", command=self.generate_voice).grid(row=2, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Label(self.script_tab, text="保留剪映甜美解说：直接导入已导出的配音。没有准确SRT时按字数估时，需试听校准；SRT使用成片时间轴。", wraplength=850).pack(anchor="w", pady=4)
        self.score_status = tk.StringVar(value="pending")
        ttk.Radiobutton(self.score_tab, text="待评：证据不足时使用", value="pending", variable=self.score_status).pack(anchor="w", pady=6)
        ttk.Radiobutton(self.score_tab, text="填写评分建议（仅展示，不写入正式账本）", value="scored", variable=self.score_status).pack(anchor="w", pady=6)
        self.dim_fields = {}
        names = ("生命福祉", "尊严权利", "知识求真", "协作治理", "长期可持续")
        for key, name in zip(DIMENSIONS, names):
            line = ttk.Frame(self.score_tab)
            line.pack(anchor="w", pady=6)
            ttk.Label(line, text=name, width=18).pack(side="left")
            variable = tk.StringVar(value="0")
            self.dim_fields[key] = variable
            ttk.Spinbox(line, from_=-2, to=2, textvariable=variable, width=6).pack(side="left")
        ttk.Label(self.score_tab, text="评分依据（本期建议分 = 五维之和 × 0.5）").pack(anchor="w", pady=6)
        self.score_reason = ScrolledText(self.score_tab, height=5, font=("Microsoft YaHei UI", 10), wrap="word")
        self.score_reason.pack(fill="x")
        bottom = ttk.Frame(root, padding=(10, 4))
        bottom.pack(fill="x")
        self.resolution = tk.StringVar(value="1080")
        ttk.Label(bottom, text="输出：").pack(side="left")
        ttk.Combobox(bottom, textvariable=self.resolution, values=("1080", "540"), width=7, state="readonly").pack(side="left")
        ttk.Button(bottom, text="生成视频草稿", command=self.render).pack(side="left", padx=8)
        ttk.Button(bottom, text="打开最近成片", command=self.open_output).pack(side="left")
        self.status = tk.StringVar(value="就绪")
        ttk.Label(bottom, textvariable=self.status).pack(side="right")
        self.log_box = ScrolledText(root, height=4, font=("Microsoft YaHei UI", 9), state="disabled")
        self.log_box.pack(fill="x", padx=10, pady=(2, 10))
        root.after(150, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def row(self, frame, row, key, label, button=None, command=None):
        variable = tk.StringVar()
        self.fields[key] = variable
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=7)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=4)
        if button:
            ttk.Button(frame, text=button, command=command).grid(row=row, column=2, padx=4)

    def idle(self):
        if self.busy:
            messagebox.showinfo("正在处理", "当前任务还在处理，请完成后再修改或切换任务。")
            return False
        return True

    def require_job(self):
        if not self.idle():
            return False
        if self.data is None:
            messagebox.showinfo("先建任务", "请先点击新建任务，或打开已保存任务。")
            return False
        return True

    def display(self):
        for key, variable in self.fields.items():
            variable.set(self.data.get(key, ""))
        for box, key in ((self.script, "script"), (self.facts, "facts")):
            box.delete("1.0", "end")
            box.insert("1.0", self.data.get(key, ""))
        for i, variables in enumerate(self.comment_fields):
            comment = self.data["comments"][i] if i < len(self.data["comments"]) else {}
            for key, variable in variables.items():
                variable.set(comment.get(key, ""))
        score = self.data["score"]
        self.score_status.set(score["status"])
        for key, variable in self.dim_fields.items():
            variable.set((score.get("dimensions") or {}).get(key, 0))
        self.score_reason.delete("1.0", "end")
        self.score_reason.insert("1.0", score.get("reason", ""))
        self.job_label.set("任务：" + str(self.directory))
        self.media_label.set("导入后显示原片尺寸与时长。")
        if self.data.get("video"):
            try:
                info = probe(asset_path(self.directory, self.data["video"]))
                self.media_label.set(f"原片：{info['duration']:.2f}秒 / {info['width']}×{info['height']} / 音轨：{'有' if info['has_audio'] else '无'}")
            except PipelineError:
                self.media_label.set("原片读取失败，请重新导入完整视频。")

    def collect(self):
        for key, variable in self.fields.items():
            value = variable.get().strip()
            if key in ("clip_start", "duration", "narration_start", "original_volume"):
                try:
                    value = float(value)
                except ValueError:
                    raise PipelineError("时间和原声比例必须填写数字。")
            self.data[key] = value
        self.data["script"] = self.script.get("1.0", "end").strip()
        self.data["facts"] = self.facts.get("1.0", "end").strip()
        comments = []
        for variables in self.comment_fields:
            comment = {key: var.get().strip() for key, var in variables.items()}
            if comment["image"]:
                try:
                    comment["start"] = float(comment["start"])
                    comment["end"] = float(comment["end"])
                except ValueError:
                    raise PipelineError("评论显示时间应为数字。")
                comments.append(comment)
        self.data["comments"] = comments
        status = self.score_status.get()
        try:
            dimensions = {key: int(v.get()) for key, v in self.dim_fields.items()} if status == "scored" else None
        except ValueError:
            raise PipelineError("评分应为整数。")
        self.data["score"] = {"status": status, "dimensions": dimensions, "reason": self.score_reason.get("1.0", "end").strip()}
        # Editing invalidates previous manual content approval.
        self.data["review"]["content_checked"] = False
        return self.data

    def new(self):
        if not self.idle(): return
        if self.data and not self.save(): return
        self.directory, self.data = new_job()
        self.display()

    def open(self):
        if not self.idle(): return
        if self.data and not self.save(): return
        path = filedialog.askopenfilename(title="打开任务job.json", initialdir=STORE, filetypes=[("任务", "job.json")])
        if path:
            try:
                directory = Path(path).parent
                data = load_job(directory)
                self.directory, self.data = directory, data
                self.display()
            except Exception as exc: messagebox.showerror("打开失败", str(exc))

    def save(self):
        if not self.require_job(): return False
        try:
            from .core import job_lock
            with job_lock(self.directory):
                save_job(self.directory, self.collect())
            reference = self.directory.relative_to(ROOT) if self.directory.is_relative_to(ROOT) else self.directory
            save_json(ROOT / ".pipeline" / "recent.json", {"job": str(reference)})
            self.status.set("已保存")
            return True
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return False

    def pick(self, key):
        if not self.require_job(): return
        filters = {"video": [("视频", "*.mp4 *.mov *.mkv *.webm")],
                   "narration_audio": [("音频", "*.mp3 *.wav *.m4a *.aac *.flac")],
                   "subtitle_file": [("字幕", "*.srt")]}
        path = filedialog.askopenfilename(filetypes=filters[key])
        if path:
            try:
                from .core import job_lock
                with job_lock(self.directory):
                    reference = import_asset(self.directory, path)
                self.fields[key].set(reference)
                if key == "narration_audio" and self.fields["subtitle_file"].get().startswith("generated/"):
                    self.fields["subtitle_file"].set("")
                if key == "video":
                    info = probe(path)
                    self.media_label.set(f"原片：{info['duration']:.2f}秒 / {info['width']}×{info['height']} / 音轨：{'有' if info['has_audio'] else '无'}")
                    if float(self.fields["duration"].get()) > info["duration"]:
                        self.fields["duration"].set(round(info["duration"] - .05, 2))
                self.save()
            except Exception as exc: messagebox.showerror("导入失败", str(exc))

    def pick_comment(self, index):
        if not self.require_job(): return
        path = filedialog.askopenfilename(filetypes=[("截图", "*.png *.jpg *.jpeg *.webp")])
        if path:
            try:
                from .core import job_lock
                with job_lock(self.directory):
                    reference = import_asset(self.directory, path)
                variables = self.comment_fields[index]
                variables["image"].set(reference)
                if not variables["start"].get():
                    length = float(self.fields["duration"].get())
                    begin = max(0, min(15 + index * 6, length - 4))
                    variables["start"].set(begin)
                    variables["end"].set(min(begin + 5, length))
                self.save()
            except Exception as exc: messagebox.showerror("截图导入失败", str(exc))

    def log(self, message):
        self.events.put(("log", message))

    def background(self, operation, success=None):
        if not self.save(): return
        self.busy = True
        self.widget_states = []
        def disable(widget):
            if widget is not self.log_box:
                try:
                    original = widget.cget("state")
                    if original != "disabled":
                        self.widget_states.append((widget, original))
                        widget.configure(state="disabled")
                except tk.TclError:
                    pass
            for child in widget.winfo_children(): disable(child)
        disable(self.root)
        self.status.set("处理中…")
        def worker():
            try:
                result = operation()
                self.events.put(("done", (result, success)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == "log":
                self.log_box.configure(state="normal")
                self.log_box.insert("end", value + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            elif kind == "error":
                self.finish_busy()
                self.status.set("需处理")
                messagebox.showerror("处理未完成", value)
            elif kind == "done":
                self.finish_busy()
                self.status.set("已完成")
                result, callback = value
                self.data = load_job(self.directory)
                self.display()
                if callback: callback(result)
        self.root.after(150, self.poll)

    def finish_busy(self):
        for widget, state in getattr(self, "widget_states", []):
            if widget.winfo_exists(): widget.configure(state=state)
        self.busy = False

    def download(self):
        if self.require_job(): self.background(lambda: download_x(self.directory, self.data, self.log))

    def render(self):
        if not self.require_job(): return
        resolution = int(self.resolution.get())
        self.background(lambda: render(self.directory, self.data, self.log, resolution),
                        lambda output: messagebox.showinfo("草稿已生成", "输出目录：\n" + str(output) + "\n\n请检查审核说明和字幕时间。"))

    def open_directory(self):
        if self.require_job(): os.startfile(str(self.directory))

    def open_source(self):
        if not self.require_job(): return
        reference = self.fields["video"].get().strip()
        if reference and asset_path(self.directory, reference).is_file():
            os.startfile(str(asset_path(self.directory, reference)))
        else:
            messagebox.showinfo("没有原片", "请先导入视频。")

    def open_output(self):
        if not self.require_job(): return
        if self.data.get("last_output"):
            path = self.directory / self.data["last_output"] / "preview.mp4"
            if path.is_file(): os.startfile(str(path)); return
        messagebox.showinfo("还没有成片", "请先生成视频草稿。")

    def export_prompt(self):
        if self.save():
            path = self.directory / "写稿提示词.txt"
            path.write_text(writing_prompt(self.data), encoding="utf-8")
            os.startfile(str(path))

    def settings(self):
        if not self.idle(): return
        dialog = tk.Toplevel(self.root)
        dialog.title("MiniMax接口设置 · 密钥仅本次会话有效")
        dialog.transient(self.root)
        dialog.grab_set()
        variables = {}
        values = (("key", "API Key（不保存到文件）", self.key or os.environ.get("MINIMAX_API_KEY", "")),
                  ("voice_id", "配音音色ID（平台查询）", self.voice_id),
                  ("voice_model", "配音模型", self.voice_model), ("text_model", "写稿模型", self.text_model),
                  ("speed", "配音语速（0.5–2）", self.speed), ("emotion", "情绪（留空自动，可填calm等）", self.emotion))
        for i, (key, label, initial) in enumerate(values):
            ttk.Label(dialog, text=label).grid(row=i, column=0, padx=10, pady=8, sticky="w")
            variable = tk.StringVar(value=initial)
            variables[key] = variable
            ttk.Entry(dialog, textvariable=variable, width=42, show="*" if key == "key" else "").grid(row=i, column=1, padx=10)
        def apply():
            try:
                speed = float(variables["speed"].get())
                if not .5 <= speed <= 2: raise ValueError()
            except ValueError:
                messagebox.showerror("语速错误", "语速应在0.5到2之间。", parent=dialog)
                return
            for key, variable in variables.items(): setattr(self, key, variable.get().strip())
            self.speed = speed
            dialog.destroy()
        ttk.Button(dialog, text="应用到本次会话", command=apply).grid(row=len(values), column=1, pady=12)

    def generate_writing(self):
        if not self.require_job(): return
        if not self.key and not os.environ.get("MINIMAX_API_KEY"):
            messagebox.showinfo("配置接口", "请先填写接口设置，也可以使用导出的提示词在现有AI会话写稿。")
            return
        if not messagebox.askyesno("生成文稿", "将把事实材料和评论译文发送到MiniMax，并产生接口费用。继续生成本次建议？"): return
        from .providers import generate_writing
        def show(result):
            dialog = tk.Toplevel(self.root)
            dialog.title("AI写稿建议 · 审核后选取口播部分")
            box = ScrolledText(dialog, width=85, height=28, font=("Microsoft YaHei UI", 11), wrap="word")
            box.pack(fill="both", expand=True)
            box.insert("1.0", result)
        self.background(lambda: generate_writing(self.directory, self.data, self.key, self.text_model), show)

    def generate_voice(self):
        if not self.require_job(): return
        if not self.key and not os.environ.get("MINIMAX_API_KEY") or not self.voice_id:
            messagebox.showinfo("配置接口", "请先填写API Key和音色ID；或者导入剪映已导出的配音。")
            return
        count = len(self.script.get("1.0", "end").strip())
        if not messagebox.askyesno("生成配音", f"将按段发送约{count}字到MiniMax并产生费用；已缓存的相同段落复用。继续？"): return
        from .providers import generate_voice
        self.background(lambda: generate_voice(self.directory, self.data, self.key, self.voice_model,
            self.voice_id, self.speed, self.emotion, log=self.log))

    def close(self):
        if self.busy:
            messagebox.showinfo("正在处理", "请等待当前操作结束后关闭窗口。")
            return
        if self.data and not self.save(): return
        self.root.destroy()


def main(job=None):
    root = tk.Tk()
    app = App(root)
    if job is None:
        recent = ROOT / ".pipeline" / "recent.json"
        if recent.is_file():
            import json
            try:
                job = ROOT / json.loads(recent.read_text(encoding="utf-8"))["job"]
            except (OSError, ValueError, KeyError):
                job = None
    if job:
        try:
            app.directory = Path(job).resolve()
            app.data = load_job(app.directory)
            app.display()
        except PipelineError:
            app.directory, app.data = None, None
    root.mainloop()
