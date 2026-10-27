# -*- coding: utf-8 -*-
"""宫位与方位（纯数据，不依赖任何 GUI）

上南下北：屏幕上方＝南，屏幕左方＝东。
屏幕上方指向的方位称为"锚"，八宫由锚按固定偏移推得：
    左上 = 锚-45°   上中 = 锚    右上 = 锚+45°
    左中 = 锚-90°   中宫         右中 = 锚+90°
    左下 = 锚-135°  下中 = 锚+180°  右下 = 锚+135°
"""
from __future__ import annotations

# 方位角度 → (卦名, 方位名, 五行)
DIR_INFO = {
    0: ("坎", "北", "水"),
    45: ("艮", "东北", "土"),
    90: ("震", "东", "木"),
    135: ("巽", "东南", "木"),
    180: ("离", "南", "火"),
    225: ("坤", "西南", "土"),
    270: ("兑", "西", "金"),
    315: ("乾", "西北", "金"),
}

# 中宫（不属八卦，五行归土）
CENTER_INFO = {"gua": "中", "dir": "中央", "wuxing": "土", "angle": None}

# (角度, 下拉文案)
ORIENT_CHOICES = [
    (180, "上方朝南 · 坐北朝南"),
    (225, "上方朝西南"),
    (270, "上方朝西"),
    (315, "上方朝西北"),
    (0, "上方朝北 · 坐南朝北"),
    (45, "上方朝东北"),
    (90, "上方朝东"),
    (135, "上方朝东南"),
]

WUXING_COLOR = {"木": "#3B6D11", "火": "#A32D2D", "土": "#854F0B",
                "金": "#5F5E5A", "水": "#185FA5"}

_CELL_OFFSETS = [
    [-45, 0, 45],
    [-90, None, 90],
    [-135, 180, 135],
]


def palace_grid(top_dir: int) -> list[list[dict | None]]:
    """按锚方位生成 3x3 宫位表，中宫为 None。"""
    grid: list[list[dict | None]] = []
    for row in _CELL_OFFSETS:
        line: list[dict | None] = []
        for off in row:
            if off is None:
                line.append(None)
                continue
            ang = (top_dir + off) % 360
            gua, name, wx = DIR_INFO[ang]
            line.append({"gua": gua, "dir": name, "wuxing": wx, "angle": ang})
        grid.append(line)
    return grid


def palace_at(grid: list[list[dict | None]], row: int, col: int) -> dict:
    """取某宫信息，中宫返回 CENTER_INFO。"""
    return grid[row][col] or CENTER_INFO


def gua_name(grid: list[list[dict | None]], row: int, col: int) -> str:
    return palace_at(grid, row, col)["gua"]
