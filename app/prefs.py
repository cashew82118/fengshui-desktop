# -*- coding: utf-8 -*-
"""界面偏好（主题、字号、动效、命主生辰、盘上标记开关）

写在 data/prefs.json，与 plan 数据分开，删掉不影响分析结果。
读失败一律回默认值，不抛异常——偏好坏了不该让程序开不起来。
生辰只存本机，不上传；坏数据 load 时直接丢弃回 None。
"""
from __future__ import annotations

import json
from pathlib import Path

import theme
import paths

PATH = paths.DATA / "prefs.json"

DEFAULTS = {"theme": "paper", "font": theme.DEFAULT_STEP, "anim": True,
            "birth": None, "marks": True, "orient": 180,
            "font_family": theme.BODY_DEFAULT,
            "report_font": "SimSun", "report_size": 1}

# 八个方位（与 palace.ORIENT_CHOICES 的角度一致）：0/45/…/315
_ORIENT_OK = set(range(0, 360, 45))


def _valid_birth(b) -> dict | None:
    """生辰四元组合法性：年 1900–2099、月 1–12、日 1–31、性别男/女。"""
    if not isinstance(b, dict):
        return None
    try:
        y, m, d, g = int(b["y"]), int(b["m"]), int(b["d"]), b["g"]
    except (KeyError, TypeError, ValueError):
        return None
    if g not in ("男", "女") or not 1900 <= y <= 2099 \
            or not 1 <= m <= 12 or not 1 <= d <= 31:
        return None
    return {"y": y, "m": m, "d": d, "g": g}


def load() -> dict:
    out = dict(DEFAULTS)
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    if isinstance(raw, dict):
        if raw.get("theme") in theme.THEMES:
            out["theme"] = raw["theme"]
        try:
            idx = int(raw.get("font", out["font"]))
            out["font"] = min(max(0, idx), len(theme.FONT_STEPS) - 1)
        except (TypeError, ValueError):
            pass
        out["anim"] = bool(raw.get("anim", True))
        out["birth"] = _valid_birth(raw.get("birth"))
        out["marks"] = bool(raw.get("marks", True))
        try:
            ang = int(raw.get("orient", out["orient"]))
        except (TypeError, ValueError):
            ang = out["orient"]
        if ang in _ORIENT_OK:            # 越界或坏值一律用默认，别把盘转歪
            out["orient"] = ang
        fam = raw.get("font_family")
        if isinstance(fam, str) and fam in theme.BODY_LABELS:
            out["font_family"] = fam
        rf = raw.get("report_font")
        if isinstance(rf, str) and rf in theme.BODY_LABELS:
            out["report_font"] = rf
        try:
            rs = int(raw.get("report_size", out["report_size"]))
            out["report_size"] = min(max(0, rs), len(theme.FONT_STEPS) - 1)
        except (TypeError, ValueError):
            pass
    return out


def save(data: dict) -> None:
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except OSError:
        pass
