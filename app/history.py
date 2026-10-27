# -*- coding: utf-8 -*-
"""本地历史记录（阶段四）

每次扫描追加一行到 data/history.jsonl。
只存统计数字：时间、总分、断语、九宫计数、图标总数。
**绝不存文件名**（见 docs/01-需求规范.md H3/H4）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import paths

DATA = paths.DATA
FILE = DATA / "history.jsonl"
MAX_LINES = 200

# 评分口径版本。改评分规则就要 +1，历史页会在交界处画分界线。
#   1 = 2026-10-24 首版六项（15/15/15/15/20/20）
#   2 = 2026-10-27 七项（12/12/12/12/16/16 + 顺手 20）
RUBRIC = 2


def rubric_of(rec: dict) -> int:
    """旧记录没有 rubric 字段，一律当 1。"""
    try:
        return int(rec.get("rubric") or 1)
    except (TypeError, ValueError):
        return 1


def read_all() -> list[dict]:
    if not FILE.exists():
        return []
    out: list[dict] = []
    try:
        for line in FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def last() -> dict | None:
    items = read_all()
    return items[-1] if items else None


def append(score: int, grade: str, counts: list[int], total: int) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if FILE.exists():
            try:
                lines = FILE.read_text(encoding="utf-8").splitlines()
            except OSError:
                lines = []
        rec = {
            "t": datetime.now().isoformat(timespec="seconds"),
            "score": score,
            "grade": grade,
            "total": total,
            "counts": counts,
            # 评分口径版本：2 = 2026-10-27 起（六项压到 80、另加「顺手」20）。
            # 1 及以前没有这个字段，读的时候按 1 处理——趋势图上要标出断层，
            # 否则用户会以为自己的桌面突然变好了。
            "rubric": RUBRIC,
        }
        lines.append(json.dumps(rec, ensure_ascii=False))
        FILE.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass          # 历史写不进去不影响主流程
