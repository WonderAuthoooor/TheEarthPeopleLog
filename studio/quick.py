"""Short-source clip preparation; does not guess highlights, facts or scores."""
import copy
from pathlib import Path
from pipeline import core

THEMES = ("slate", "paper")


def defaults(job, preset=None):
    result = copy.deepcopy(job)
    preset = preset or {}
    result.update(layout="quick", quick_theme=preset.get("theme", "slate") if preset.get("theme") in THEMES else "slate",
                  context="", observation="", cover_at=None, quick_clips=[],
                  script="", narration_audio="", subtitle_file="", narration_start=0.,
                  comments=[], original_volume=1., duration=20.,
                  score={"status": "pending", "dimensions": None, "reason": "依据待核查"})
    return result


def prepare_batch(document, rows, directory):
    """Validate ALL cuts before enqueueing any; rows use the original time axis."""
    if not 1 <= len(rows) <= 20:
        raise core.PipelineError("请添加1—20个独立看点的切片。")
    source = document["job"]
    if len(rows) > 1 and (source.get("narration_audio") or source.get("subtitle_file")):
        raise core.PipelineError("批量切片先使用原声和原片已有字幕；导入旁白或SRT时请单条导出，以免时轴错位。")
    prepared = []
    for index, row in enumerate(rows, 1):
        if len(row) != 6:
            raise core.PipelineError(f"第{index}行切片数据不完整。")
        try:
            title, begin, end, context, observation, cover = row
            begin = core.number(begin, f"第{index}行起点", 0, 86400)
            end = core.number(end, f"第{index}行终点", begin, 86700)
            if not title.strip():
                raise core.PipelineError("请填写该切片的标题。")
            item = copy.deepcopy(document)
            item["job"].update(layout="quick", title=title.strip(), clip_start=begin, duration=end - begin,
                               context=context.strip(), observation=observation.strip(),
                               cover_at=None if not str(cover).strip() else core.number(cover, "封面时刻", begin, end),
                               quick_clips=[])
            if len(rows) > 1:
                item["job"]["score"] = {"status": "pending", "dimensions": None, "reason": "各切片评估范围需分别核查"}
                item["job"]["review"] = dict.fromkeys(("facts_checked", "materials_checked", "content_checked"), False)
            core.validate_job(directory, item["job"])
            prepared.append(item)
        except core.PipelineError as exc:
            raise core.PipelineError(f"第{index}行：{exc}") from exc
    return prepared


def posting_copy(data):
    score = core.score_value(data["score"])
    parts = [data.get("context", "").strip()]
    if data.get("observation", "").strip():
        parts.append("观察：" + data["observation"].strip())
    parts.append("文明观察：待评" if score is None else f"文明观察建议：{score:+.1f}分；{data['score'].get('reason', '')}")
    if data.get("event_date"):
        parts.append("事件日期：" + data["event_date"])
    if data.get("source_note"):
        parts.append("来源：" + data["source_note"])
    if data.get("source_url"):
        parts.append(data["source_url"])
    return {"title": data["title"], "description": "\n".join(p for p in parts if p),
            "status": "draft", "requires_review": True, "published": False}
