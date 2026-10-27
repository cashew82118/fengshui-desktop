# -*- coding: utf-8 -*-
"""理想布局推演（阶段五）

铁律：**只算不改**。本模块只产出"如果这样摆会怎样"的虚拟布局，
绝不移动真实图标，不调用任何 win32 写操作。

推演原则（2026-10-24 按用户反馈重做）：
  1. **不搞九宫均摊**。把图标平摊到所有宫，气是"周"了，但你根本懒得去点右边和右下。
  2. **就近安置**。挪出去的图标优先落在原宫附近，不让它从左上跑到右下。
  3. **热靠左、冷靠右**。常用器物往左上靠；承载之物（土：文件夹、安装包、素材包）可放远些。
  4. **成组不打散**。同五行的已经在那宫里，就优先并入，别把一类东西拆到两处。
  5. **只补空位**。目标宫只找空着的格子填进去，不重排原有图标。
"""
from __future__ import annotations

import copy

from fengshui import relation
from palace import palace_at, palace_grid

HALL_CAP = 4          # 明堂上限
CENTER = (1, 1)
CELL_SOFT_CAP = 8     # 单宫超过这个数就嫌挤，不再往里塞


def _grid_split(layout: dict) -> tuple[list[int], list[int], int]:
    """按**网格索引**把 3x3 宫切好，返回 (每宫行数, 每宫行起点, 每宫列数)。

    不能按像素三等分：2560/3 = 853.33 不是 93 的整数倍，
    按像素分会把图标推到格子外、对齐度崩掉（实测踩过）。
    """
    w, h = layout["canvas"]
    cw, ch = layout["cell"]
    total_cols = max(3, int((w - cw) // cw) + 1)
    total_rows = max(3, int((h - ch) // ch) + 1)
    base_r, rem = divmod(total_rows, 3)
    rows_each = [base_r + (1 if i < rem else 0) for i in range(3)]
    row_start = [sum(rows_each[:i]) for i in range(3)]
    return rows_each, row_start, total_cols // 3


def _cell_slots(r: int, c: int, rows_each: list[int], cols_each: int
                ) -> list[tuple[int, int]]:
    """给出某宫的填格顺序（局部列, 局部行）。

    **每个宫从朝向屏幕边的那一侧开始填**，这样图标贴的是屏幕边、中间自然空出来：
        左列 c=0 从左往右；右列 c=2 从右往左；
        上行 r=0 从上往下；下行 r=2 从下往上；中列/中行按常规方向。
    若一律从宫左上角开始，图标会贴在"宫界"上而不是"屏幕边"上，
    坤宫（右上）的图标反而从屏幕三分之一处才开始排——这不是人摆桌面的样子。
    """
    hs = (range(cols_each) if c != 2 else range(cols_each - 1, -1, -1))
    vs = (range(rows_each[r]) if r != 2 else range(rows_each[r] - 1, -1, -1))
    return [(h, v) for h in hs for v in vs]


def _slot_xy(layout, h: int, v: int, r: int, c: int,
             row_start: list[int], cols_each: int,
             base_x: int, base_y: int) -> tuple[int, int]:
    cw, ch = layout["cell"]
    return (int(base_x + (c * cols_each + h) * cw),
            int(base_y + (row_start[r] + v) * ch))


def _first_free(layout, items: list[dict], r: int, c: int,
                rows_each, row_start, cols_each, base_x, base_y
                ) -> tuple[int, int] | None:
    """按"贴边优先"的顺序找第一个没被占的格位，不重排原有图标。"""
    taken = {(i["x"], i["y"]) for i in items}
    for h, v in _cell_slots(r, c, rows_each, cols_each):
        xy = _slot_xy(layout, h, v, r, c, row_start, cols_each, base_x, base_y)
        if xy not in taken:
            return xy
    return None


def _cell_score(icon: dict, rc: tuple[int, int], cells: dict, grid,
                use_distance: bool = True) -> float | None:
    """给"把 icon 放进 rc 这一宫"打分。None 表示放不下。"""
    r, c = rc
    n = len(cells[rc])
    if n >= CELL_SOFT_CAP:
        return None
    info = palace_at(grid, r, c)
    _, w = relation(icon.get("wuxing", "金"), info["wuxing"])

    score = 1.2 * w                                  # 五行：生入最优
    if use_distance:
        r0, c0 = icon["row"], icon["col"]
        score -= 0.9 * (abs(r - r0) + abs(c - c0))   # 就近：别乱跑

    reach = 0.30 * (r + c)                           # 顺手：越靠左上越好
    if icon.get("wuxing") == "土":
        reach *= 0.35                                # 承载之物可放远处
    score -= reach

    same = sum(1 for i in cells[rc] if i.get("wuxing") == icon.get("wuxing"))
    score += 0.35 * min(3, same)                     # 成组：别拆散同类
    score -= 0.35 * max(0, n - 4)                    # 太挤不好用
    return score


def project(layout: dict, top_dir: int = 180) -> tuple[dict, list[dict]]:
    """返回 (推演后的 layout, 移动记录)。原 layout 不被修改。"""
    new = copy.deepcopy(layout)
    icons = new["icons"]
    grid = palace_grid(top_dir)
    rows_each, row_start, cols_each = _grid_split(new)
    base_x = min(i["x"] for i in icons) if icons else 0
    base_y = min(i["y"] for i in icons) if icons else 0

    cells: dict[tuple[int, int], list[dict]] = {(r, c): [] for r in range(3)
                                                for c in range(3)}
    for it in icons:
        cells[(it["row"], it["col"])].append(it)
    for k in cells:
        cells[k].sort(key=lambda i: (i["y"], i["x"]))

    moves: list[dict] = []
    w, h = new["canvas"]
    cw, ch = new["cell"]

    def relocate(items: list[dict], reason: str) -> None:
        for it in items:
            src = (it["row"], it["col"])
            best, best_score = None, None
            for r in range(3):
                for c in range(3):
                    rc = (r, c)
                    if rc == CENTER or rc == src:
                        continue
                    if rc == (0, 1) and len(cells[(0, 1)]) >= HALL_CAP:
                        continue
                    xy = _first_free(new, cells[rc], r, c, rows_each,
                                     row_start, cols_each, base_x, base_y)
                    if xy is None:
                        continue
                    sc = _cell_score(it, rc, cells, grid)
                    if sc is None:
                        continue
                    if best_score is None or sc > best_score:
                        best_score, best = sc, (rc, xy)
            if best is None:
                continue
            rc, xy = best
            cells[src].remove(it)
            cells[rc].append(it)
            it["x"], it["y"] = xy
            it["cx"] = round((it["x"] + cw / 2.0) / w, 6)
            it["cy"] = round((it["y"] + ch / 2.0) / h, 6)
            it["row"], it["col"] = rc
            moves.append({"name": it["name"], "from": src, "to": rc,
                          "why": reason})

    # 1. 清空中宫（中宫必须留空）
    relocate(list(cells[CENTER]), "中宫宜虚")

    # 2. 明堂超限，溢出的往外挪
    hall = cells[(0, 1)]
    if len(hall) > HALL_CAP:
        relocate(hall[HALL_CAP:], "明堂宜开阔")

    return new, moves


def repack(layout: dict, top_dir: int = 180) -> tuple[dict, list[dict]]:
    """全部重摆：按「外实内虚」把每个图标重新分配，只为看效果。

    与 `project()` 的区别：
      · `project()` 是"最小改动"，只挪必须挪的，能照着做；
      · `repack()` 是"彻底重来"，48 个全部重新落位，好看但得手动挪 48 次。
    共同点：都从屏幕边开始填，中间留空；都不碰真实桌面。
    """
    new = copy.deepcopy(layout)
    icons = new["icons"]
    grid = palace_grid(top_dir)
    rows_each, row_start, cols_each = _grid_split(new)
    base_x = min(i["x"] for i in icons) if icons else 0
    base_y = min(i["y"] for i in icons) if icons else 0
    w, h = new["canvas"]
    cw, ch = new["cell"]

    cells: dict[tuple[int, int], list[dict]] = {(r, c): [] for r in range(3)
                                                for c in range(3)}
    moves: list[dict] = []

    # 热的先挑位置（土类＝承载之物，算冷，让它捡剩下的）
    order = sorted(icons, key=lambda i: (1 if i.get("wuxing") == "土" else 0,
                                         i["name"]))

    for it in order:
        best, best_score = None, None
        for r in range(3):
            for c in range(3):
                rc = (r, c)
                if rc == CENTER:
                    continue
                if rc == (0, 1) and len(cells[(0, 1)]) >= HALL_CAP:
                    continue
                xy = _first_free(new, cells[rc], r, c, rows_each,
                                 row_start, cols_each, base_x, base_y)
                if xy is None:
                    continue
                sc = _cell_score(it, rc, cells, grid, use_distance=False)
                if sc is None:
                    continue
                if best_score is None or sc > best_score:
                    best_score, best = sc, (rc, xy)
        if best is None:
            continue
        rc, xy = best
        cells[rc].append(it)
        old = (it["row"], it["col"])
        it["x"], it["y"] = xy
        it["cx"] = round((it["x"] + cw / 2.0) / w, 6)
        it["cy"] = round((it["y"] + ch / 2.0) / h, 6)
        it["row"], it["col"] = rc
        if old != rc:
            moves.append({"name": it["name"], "from": old, "to": rc,
                          "why": "重排至外圈"})

    return new, moves


def _find_gua(grid: list, gua: str) -> tuple[int, int] | None:
    """按卦名找宫位（同一卦随朝向落在不同格子）。"""
    for r in range(3):
        for c in range(3):
            info = grid[r][c]
            if info and info["gua"] == gua:
                return (r, c)
    return None


def focus(layout: dict, top_dir: int, target_gua: str, pick,
          why_in: str = "归入此宫",
          why_out: str = "让位") -> tuple[dict, list[dict]]:
    """目标导向推演：把 pick 选中的图标集中到指定卦宫。

    与 project()/repack() 的区别：这两档**允许牺牲就近与顺手**——
    本来就是"为一个目标重排"，移动量必然更大。规则：
      1. 目标宫里的非目标图标先请出去（就近挑次好去处，不进中宫）；
      2. 目标图标按五行合盘次序搬进来，目标宫满则以最近空宫收尾；
      3. 只算不改，返回 (虚拟布局, 移动记录)。
    pick 为 None 表示"只清不搬"（目标宫腾干净）。
    """
    new = copy.deepcopy(layout)
    icons = new["icons"]
    moves: list[dict] = []
    if not icons:
        return new, moves
    grid = palace_grid(top_dir)
    target = _find_gua(grid, target_gua)
    if target is None or target == CENTER:
        return new, moves

    rows_each, row_start, cols_each = _grid_split(new)
    base_x = min(i["x"] for i in icons)
    base_y = min(i["y"] for i in icons)
    w, h = new["canvas"]
    cw, ch = new["cell"]

    cells: dict[tuple[int, int], list[dict]] = {(r, c): [] for r in range(3)
                                                for c in range(3)}
    for it in icons:
        cells[(it["row"], it["col"])].append(it)
    for k in cells:
        cells[k].sort(key=lambda i: (i["y"], i["x"]))

    def place(it: dict, rc: tuple[int, int], why: str) -> bool:
        src = (it["row"], it["col"])
        if src == rc:
            return False
        xy = _first_free(new, cells[rc], rc[0], rc[1], rows_each,
                         row_start, cols_each, base_x, base_y)
        if xy is None:
            return False
        cells[src].remove(it)
        cells[rc].append(it)
        it["x"], it["y"] = xy
        it["cx"] = round((it["x"] + cw / 2.0) / w, 6)
        it["cy"] = round((it["y"] + ch / 2.0) / h, 6)
        it["row"], it["col"] = rc
        moves.append({"name": it["name"], "from": src, "to": rc, "why": why})
        return True

    def best_other(it: dict, avoid: tuple[int, int]) -> tuple[int, int] | None:
        """被请出者的次好去处：就近、合五行、避开目标宫与中宫。"""
        best, best_score = None, None
        for r in range(3):
            for c in range(3):
                rc = (r, c)
                if rc in (CENTER, avoid, (it["row"], it["col"])):
                    continue
                if rc == (0, 1) and len(cells[(0, 1)]) >= HALL_CAP:
                    continue
                sc = _cell_score(it, rc, cells, grid)
                if sc is None:
                    continue
                if best_score is None or sc > best_score:
                    best_score, best = sc, rc
        return best

    # 目标宫容量：明堂要留空（与 project() 同一口径），别把 10 个图标
    # 全堆到正前方那一格——那会跟「明堂宜开阔」的自家规则打架。
    cap = HALL_CAP if target == (0, 1) else CELL_SOFT_CAP

    # 1. 请出目标宫里的非目标图标
    if pick is not None:
        for it in list(cells[target]):
            if not pick(it):
                rc = best_other(it, target)
                if rc is not None:
                    place(it, rc, why_out)

    # 2. 目标图标搬进来：五行合盘优先（生入最合），再按远近
    if pick is not None:
        chosen = [it for it in icons if pick(it)]
        chosen.sort(key=lambda it: (
            -_cell_score(it, target, cells, grid, use_distance=False)
            if _cell_score(it, target, cells, grid,
                           use_distance=False) is not None else -99,
            it["y"], it["x"]))
        for it in chosen:
            if len(cells[target]) >= cap:
                break
            place(it, target, why_in)

    return new, moves
