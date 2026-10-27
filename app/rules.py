# -*- coding: utf-8 -*-
"""用户五行覆盖层（阶段九）。

三张表，存 data/rules.json：

    {"software": {"LosslessCut": "木"},     ← 软件名（词边界匹配，同内置名录）
     "keyword":  {"素材": "土"},             ← 关键词（子串匹配）
     "ext":      {".xyz": "火"},             ← 扩展名（精确匹配）
     "updated":  "2026-10-24T12:30:00"}

合并原则：**用户覆盖 > 内置**。classify 主判定的第 0 步查这里，命中即停——
用户显式指定的归属压过一切内置规则（含白名单与安装包判定）。

「恢复默认」= 删除文件（不是清空内容），内置表永不改写。
坏文件/不存在的文件一律静默降级为空覆盖，绝不抛异常打断主流程。
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import software
import paths

PATH = paths.DATA / "rules.json"
TABLES = ("software", "keyword", "ext")
VALID_WUXING = ("木", "火", "土", "金", "水")

_cache: dict | None = None


# ---------------------------------------------------------------- 读写


def _empty() -> dict:
    return {t: {} for t in TABLES}


def _normalize(table: str, key: str) -> str:
    """键的规范形：扩展名统一小写补点，其余去首尾空白。"""
    key = (key or "").strip()
    if table == "ext":
        if key and not key.startswith("."):
            key = "." + key
        key = key.lower()
    elif table == "keyword":
        key = key.lower()
    return key


def load(force: bool = False) -> dict:
    """读覆盖层（带模块级缓存）。坏文件/不存在 → 空覆盖。"""
    global _cache
    if _cache is not None and not force:
        return copy.deepcopy(_cache)
    tables = _empty()
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
        for t in TABLES:
            src = raw.get(t)
            if isinstance(src, dict):
                for k, v in src.items():
                    if isinstance(k, str) and isinstance(v, str) \
                            and v in VALID_WUXING:
                        k2 = _normalize(t, k)
                        if k2:
                            tables[t][k2] = v
    except (OSError, ValueError):
        pass
    _cache = tables
    return copy.deepcopy(_cache)


def save(tables: dict) -> None:
    """写文件并刷新缓存。只在内存数据合法（由 set/remove 保证）时被调用。"""
    global _cache
    clean = _empty()
    for t in TABLES:
        for k, v in (tables.get(t) or {}).items():
            if v in VALID_WUXING and k:
                clean[t][k] = v
    PATH.parent.mkdir(parents=True, exist_ok=True)
    clean["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    _cache = {t: dict(clean[t]) for t in TABLES}


def refresh() -> None:
    """丢弃缓存，下次 load 重读文件。GUI 改表后、或外部改了文件后调用。"""
    global _cache
    _cache = None
    load(force=True)


def reset() -> None:
    """恢复默认 = 删除覆盖文件。内置表不动。"""
    global _cache
    try:
        PATH.unlink()
    except FileNotFoundError:
        pass
    _cache = _empty()


# ---------------------------------------------------------------- 增删改


def set_rule(table: str, key: str, wuxing: str) -> tuple[bool, str]:
    """新增或修改一条覆盖。返回 (是否成功, 提示)。非法输入拒绝且不写文件。"""
    if table not in TABLES:
        return False, "未知的表：%s" % table
    if wuxing not in VALID_WUXING:
        return False, "五行只能是 木火土金水"
    key = _normalize(table, key)
    if not key:
        return False, "键不能为空"
    tables = load()
    tables[table][key] = wuxing
    save(tables)
    return True, ""


def remove_rule(table: str, key: str) -> tuple[bool, str]:
    """删除一条覆盖。不存在也算成功（幂等）。"""
    if table not in TABLES:
        return False, "未知的表：%s" % table
    key = _normalize(table, key)
    tables = load()
    if key in tables[table]:
        del tables[table][key]
        save(tables)
    return True, ""


def items(table: str) -> list[tuple[str, str]]:
    """某张表的全部覆盖，键排序（列表展示用）。"""
    return sorted(load()[table].items())


def count(table: str) -> int:
    return len(load()[table])


# ---------------------------------------------------------------- 匹配


def match(name: str, ext: str) -> tuple[str, str] | None:
    """classify 主判定第 0 步。返回 (五行, 说明) 或 None。

    命中顺序：软件名（词边界，与内置名录同语义）→ 关键词（子串）→ 扩展名。
    """
    tables = load()
    if not any(tables.values()):
        return None
    low = (name or "").strip().lower()
    for k, wx in tables["software"].items():
        if any(ord(c) > 127 for c in k):
            if k.lower() in low:
                return wx, "自定义指定「%s」为%s" % (k, wx)
        # word_hit 内部拿 kw 原样在 name.lower() 里 find，内置表键全小写才没事；
        # 用户键保留原始大小写展示，匹配时必须统一小写
        elif software.word_hit(k.lower(), name or ""):
            return wx, "自定义指定「%s」为%s" % (k, wx)
    for k, wx in tables["keyword"].items():
        if k and k in low:
            return wx, "关键词「%s」→%s（自定义添加）" % (k, wx)
    if ext:
        wx = tables["ext"].get(ext.lower())
        if wx:
            return wx, "扩展名 %s →%s（自定义添加）" % (ext.lower(), wx)
    return None
