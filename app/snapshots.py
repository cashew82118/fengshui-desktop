# -*- coding: utf-8 -*-
"""桌面快照（阶段十一之后新增）

一次「保存本次分析」= 一个 JSON，落在 `data/snapshots/snap_YYYYMMDD_HHMMSS.json`。
存的是**纯现状**：图标名/坐标/行列/五行/来源、画布与格子尺寸、朝向、
分数/评级/六项得分/九宫计数/五行分布。不含推演结果。

与 `data/history.jsonl` 的分工：
  · history 只存统计（分数、九宫计数），轻量，供趋势图用，每次分析自动写；
  · 快照是完整盘面，**只有用户点「保存本次分析」才写**，用于日后翻看。

全部本地，零网络。快照上限 200 个，超出从最旧的删。坏文件读取时跳过，不抛异常。
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
import paths

ROOT = paths.BASE
DIR = paths.SNAPSHOTS
LIMIT = 200

# 存盘时只保留这些字段：够重画一张盘、够复算分数，不带路径（隐私更少一点）
ICON_KEYS = ("index", "name", "kind", "ext", "x", "y", "cx", "cy",
             "row", "col", "wuxing", "wuxing_source", "wuxing_note",
             "intensity")


def _pack_icon(it: dict) -> dict:
    out = {k: it.get(k) for k in ICON_KEYS if k in it}
    out.pop("path", None)                 # 绝不存全路径
    return out


def save(result: dict, layout: dict, top_dir: int,
         orient_text: str = "") -> Path:
    """写一个快照，返回路径。纯本地写盘。"""
    DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now()
    data = {
        "t": now.isoformat(timespec="seconds"),
        "top_dir": top_dir,
        "orient_text": orient_text,
        "canvas": list(layout.get("canvas", [0, 0])),
        "cell": list(layout.get("cell", [0, 0])),
        "score": result.get("score"),
        "grade": result.get("grade"),
        "summary": result.get("summary", ""),
        "sections": {k: {"name": v.get("name"), "score": v.get("score"),
                         "max": v.get("max")}
                     for k, v in result.get("sections", {}).items()},
        "counts": list(result.get("stats", {}).get("counts", [])),
        "dist": dict(result.get("stats", {}).get("dist", {})),
        "icons": [_pack_icon(it) for it in layout.get("icons", [])],
    }
    path = DIR / ("snap_%s.json" % now.strftime("%Y%m%d_%H%M%S"))
    n = 2
    while path.exists():
        path = DIR / ("snap_%s_%d.json" % (now.strftime("%Y%m%d_%H%M%S"), n))
        n += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    _prune()
    return path


def _prune() -> None:
    files = sorted(DIR.glob("snap_*.json"))
    for f in files[:-LIMIT]:
        try:
            f.unlink()
        except OSError:
            pass


def load(path) -> dict | None:
    """读一个快照；坏文件返回 None。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "icons" not in data:
        return None
    return data


def to_layout(snap: dict) -> dict:
    """快照 → 能直接喂给 fengshui/render 的 layout。"""
    return {"canvas": tuple(snap.get("canvas") or (0, 0)),
            "cell": tuple(snap.get("cell") or (0, 0)),
            "icons": list(snap.get("icons") or [])}


def list_all() -> list[dict]:
    """全部快照的索引（按时间倒序）：[{path, t, day, score, grade}]。"""
    out = []
    for f in DIR.glob("snap_*.json"):
        data = load(f)
        if not data:
            continue
        t = None
        try:
            t = datetime.datetime.fromisoformat(str(data.get("t")))
        except ValueError:
            m = f.stem.replace("snap_", "")[:15]
            try:
                t = datetime.datetime.strptime(m, "%Y%m%d_%H%M%S")
            except ValueError:
                continue
        out.append({"path": f, "t": t, "day": t.strftime("%Y-%m-%d"),
                    "score": data.get("score"), "grade": data.get("grade", "")})
    out.sort(key=lambda r: r["t"], reverse=True)
    return out


def by_day() -> dict[str, list[dict]]:
    """按日期分组，日内按时间倒序：{"2026-10-25": [ ... ]}。"""
    out: dict[str, list[dict]] = {}
    for rec in list_all():
        out.setdefault(rec["day"], []).append(rec)
    return out


def count() -> int:
    return len(list(DIR.glob("snap_*.json"))) if DIR.exists() else 0
