# -*- coding: utf-8 -*-
"""九宫盘绘制

职责：把 Layout 画成一张九宫实景盘。
必须保持纯绘制：不读系统、不碰文件、不做风水判定。
方位旋转的规则在这里（八卦跟方位走），青龙白虎由 main 另行标注（跟人走）。

配色与字体全部由 theme.py 传入，本文件不出现任何写死的色值。

动画：`reveal` 是 0→1 的揭示进度。
    0.00–0.50  宫格由中宫向外依次点亮
    0.30–1.00  图标按五行顺序逐个弹出（带过冲）
    0.70–1.00  文字与图例淡入（Canvas 无 alpha，用「向底色混合」模拟）
传 reveal=1.0 即为静态成图。
"""
from __future__ import annotations

import tkinter as tk

import theme as theme_mod

# ---------------------------------------------------------------- 兼容别名
# 老代码与测试引用过这些名字，保留指向默认主题，避免破坏调用方。
_DEFAULT = theme_mod.get("paper")
BG_BOARD = _DEFAULT["board"]
LINE = _DEFAULT["line"]
LINE_OUTER = _DEFAULT["line_outer"]
INK = _DEFAULT["ink"]
SUB = _DEFAULT["sub"]
WEAK = _DEFAULT["weak"]
ACCENT = _DEFAULT["accent"]
CELL_TINT = _DEFAULT["cell_tint"]
CENTER_EMPTY = _DEFAULT["center_empty"]
WUXING_COLOR = _DEFAULT["wuxing"]

def _halo_text(canvas, x, y, text, fill, font, anchor="center",
               halo=None, d=1):
    """带底色描边的文字：先画上下左右四道 halo 色，再画正文。

    宫名（坎 北、巽 东南）压在图标色块上时（2026-10-27 用户报），主色文字
    直接叠在五彩色上几乎认不出笔画；四道描边把字从色块里"抠"出来——
    重叠照旧，可读性恢复。Tk 的 create_text 没有描边属性，只能这样合成。
    """
    for dx, dy in ((-d, 0), (d, 0), (0, -d), (0, d)):
        canvas.create_text(x + dx, y + dy, text=text, fill=halo,
                           font=font, anchor=anchor)
    return canvas.create_text(x, y, text=text, fill=fill, font=font,
                              anchor=anchor)


_F0 = theme_mod.fonts(1.0)
FONT_GUA = _F0["gua"]
FONT_SMALL = _F0["small"]
FONT_TIP = _F0["tip"]
FONT_CAP = _F0["cap"]

from palace import (  # noqa: E402,F401
    CENTER_INFO, ORIENT_CHOICES, palace_grid,
)

# 中宫向外的点亮顺序
_SPREAD = [(1, 1), (0, 1), (1, 0), (1, 2), (2, 1),
           (0, 0), (0, 2), (2, 0), (2, 2)]


# ---------------------------------------------------------------- 小工具

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out(t: float) -> float:
    """标准缓入缓出。用于"从无到有"的过程，起收都不突兀。"""
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def _ease_back(t: float, s: float = 1.15) -> float:
    """带轻微过冲的弹出曲线。s 越小过冲越弱；1.7 是原值，太跳。"""
    u = t - 1.0
    return 1.0 + (s + 1.0) * u ** 3 + s * u ** 2


# ---------------------------------------------------------------- 圆角方块

RR_RATIO = 0.26          # 圆角半径 ÷ 边长，接近 iOS 图标的观感
RR_SEG = 4               # 每个圆角的采样段数，越大越圆滑


def rr_points(cx: float, cy: float, half: float, ratio: float = RR_RATIO,
              seg: int = RR_SEG) -> list[float]:
    """圆角方形的顶点序列（可直接喂给 Canvas 的 polygon / coords）。

    Canvas 没有圆角矩形，只能自己采样圆角弧线。点数固定（(seg+1)*4），
    所以放大缩小时可以直接用 coords(item, *rr_points(...)) 换点，不必重建图元。
    """
    half = max(0.6, half)
    size = half * 2.0
    r = min(half, max(0.8, size * ratio))
    x0, y0 = cx - half, cy - half
    x1, y1 = cx + half, cy + half

    import math
    pts: list[float] = []
    # 四角圆心与起止角：右上 → 右下 → 左下 → 左上（顺时针）
    corners = (
        (x1 - r, y0 + r, -90.0, 0.0),
        (x1 - r, y1 - r, 0.0, 90.0),
        (x0 + r, y1 - r, 90.0, 180.0),
        (x0 + r, y0 + r, 180.0, 270.0),
    )
    for ox, oy, a0, a1 in corners:
        for i in range(seg + 1):
            a = math.radians(a0 + (a1 - a0) * i / seg)
            pts.append(ox + r * math.cos(a))
            pts.append(oy + r * math.sin(a))
    return pts


def cell_box(layout: dict, area_w: int, area_h: int, fonts: dict | None,
             row: int, col: int) -> tuple[float, float, float, float]:
    """某一宫在画布上的矩形，供界面做悬停高亮用。"""
    fonts = fonts or _F0
    fs = theme_mod.scale_of(fonts)
    cw_all, ch_all = layout["canvas"]
    ox, oy, w, h, _s = fit_board(area_w, area_h, (cw_all, ch_all), fs)
    cw, ch = w / 3.0, h / 3.0
    return ox + cw * col, oy + ch * row, ox + cw * (col + 1), oy + ch * (row + 1)


# ---------------------------------------------------------------- 空盘（未分析）

EMPTY_ASPECT = 2560 / 1440.0        # 没有真实数据时，用本机画布比例画个九宫格


def _rrect_pts(x0: float, y0: float, x1: float, y1: float, r: float,
               seg: int = RR_SEG) -> list[float]:
    """任意长宽比的圆角矩形顶点。rr_points 只支持正方形。"""
    import math
    r = max(0.5, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    pts: list[float] = []
    for cx, cy, a0, a1 in ((x1 - r, y0 + r, -90.0, 0.0),
                           (x1 - r, y1 - r, 0.0, 90.0),
                           (x0 + r, y1 - r, 90.0, 180.0),
                           (x0 + r, y0 + r, 180.0, 270.0)):
        for i in range(seg + 1):
            a = math.radians(a0 + (a1 - a0) * i / seg)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def draw_empty(canvas: tk.Canvas, area_w: int, area_h: int,
               th: dict | None = None, fonts: dict | None = None,
               label: str = "开始分析",
               hint: str = "点击后读取桌面图标位置 · 只读，不改动任何东西"
               ) -> dict | None:
    """未分析时的空盘：九宫格线照画（不留白板），正中一个大按钮。

    返回按钮的矩形，供点击命中判断。
    """
    th = th or _DEFAULT
    fonts = fonts or _F0
    fs = theme_mod.scale_of(fonts)
    bg = th["board"]
    canvas.delete("all")
    canvas.configure(bg=bg)

    ox, oy, w, h, _s = fit_board(area_w, area_h, (2560, 1440), fs)
    col_w, row_h = w / 3.0, h / 3.0

    # 宫格线（比正常盘更淡，暗示"还没有内容"）
    faint = _mix(th["line"], bg, 0.55)
    for i in (1, 2):
        canvas.create_line(ox + col_w * i, oy, ox + col_w * i, oy + h,
                           fill=faint, width=1)
        canvas.create_line(ox, oy + row_h * i, ox + w, oy + row_h * i,
                           fill=faint, width=1)
    canvas.create_rectangle(ox, oy, ox + w, oy + h, outline=faint, width=1)

    # 说明文字挂在盘上方，位置与正常盘一致
    canvas.create_text(ox + w / 2, oy - 10 * fs - 4, text="▲ 视线尽头 · 明堂",
                       fill=th["weak"], font=fonts["cap"], anchor="s")

    # 中央按钮（圆角矩形：横向宽于纵向，不能直接用 rr_points）
    bw = min(w * 0.42, 230.0)
    bh = max(40.0, 44.0 * fs)
    cx, cy = ox + w / 2.0, oy + h / 2.0
    x0, y0, x1, y1 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
    canvas.create_polygon(_rrect_pts(x0, y0, x1, y1, 10.0 * fs),
                          fill=_mix(th["accent"], bg, 0.08),
                          outline=th["accent"], width=1.4, tags="startbtn")
    canvas.create_text(cx, cy, text=label, fill=th["accent"],
                       font=fonts["grade"], tags="startbtn")

    if hint:
        canvas.create_text(cx, y1 + 16 * fs, text=hint, fill=th["weak"],
                           font=fonts["small"], width=w * 0.8, justify="center")

    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _mix(fg: str, bg: str, alpha: float) -> str:
    """Canvas 不支持透明度，手工把前景色混到背景色上。"""
    alpha = _clamp(alpha)
    f = [int(fg[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    c = [round(b[i] * (1 - alpha) + f[i] * alpha) for i in range(3)]
    return "#%02x%02x%02x" % tuple(c)


def _tint_alpha(count: int) -> float:
    if count <= 0:
        return 0.0
    if count <= 4:
        return 0.10
    if count <= 9:
        return 0.18
    return 0.26


def cell_fill(th: dict, n: int, is_center: bool = False,
              progress: float = 1.0) -> str:
    """某一宫的底色。空宫返回 ""（不填）。

    `progress` 是入场进度：0 时几乎看不出颜色，1 时完全显色。

    **参数顺序是这个地方最容易错的一点**：`_mix(color, bg, w)` 里 w 是 color 的权重，
    第一个参数是"终值"。写成 `_mix(bg, color, w)` 会把染色反过来——越进场越接近底色，
    最后整盘发白（2026-10-24 踩过，表现为"闪一下色块然后全白"）。
    """
    bg = th["board"]
    if is_center and n == 0:
        color, weight = th["center_empty"], 1.0
    elif n > 0:
        color, weight = th["cell_tint"], _tint_alpha(n)
    else:
        return ""
    weight *= 0.32 + 0.68 * _clamp(progress)
    return _mix(color, bg, weight)


def fit_board(area_w: int, area_h: int, canvas_size: tuple[int, int],
              fs: float = 1.0) -> tuple[float, float, float, float, float]:
    """算出盘的放置矩形。返回 (ox, oy, w, h, scale)。

    盘随窗口缩放：不设尺寸上限，只受可用宽高约束，始终保持原画布长宽比。
    上下留白随字号走，字号调大时不会被裁掉。
    """
    cw, ch = canvas_size
    aspect = (cw / ch) if ch else 1.8
    top_pad = 26.0 * fs + 14.0
    bottom_pad = 96.0 * fs + 12.0

    max_w = max(160.0, area_w - 40.0)
    max_h = max(100.0, area_h - top_pad - bottom_pad)
    w = max_w
    h = w / aspect
    if h > max_h:
        h = max_h
        w = h * aspect
    ox = (area_w - w) / 2.0
    oy = top_pad
    return ox, oy, w, h, (w / cw if cw else 1.0)


# ---------------------------------------------------------------- 主绘制

def draw_board(canvas: tk.Canvas, layout: dict, top_dir: int,
               area_w: int, area_h: int,
               th: dict | None = None, fonts: dict | None = None,
               reveal: float = 1.0,
               hover: int | None = None,
               marks: dict | None = None) -> list[dict]:
    """重画整张盘。返回图标的命中框列表（供 tooltip 与悬停动画用）。

    marks: {卦名: "good"|"bad"} —— 命主四吉四凶角标，None 不画。
    """
    th = th or _DEFAULT
    fonts = fonts or _F0
    fs = theme_mod.scale_of(fonts)
    bg = th["board"]

    canvas.delete("all")
    canvas.configure(bg=bg)

    cw_all, ch_all = layout["canvas"]
    cell_w, cell_h = layout["cell"]
    ox, oy, w, h, scale = fit_board(area_w, area_h, (cw_all, ch_all), fs)
    col_w, row_h = w / 3.0, h / 3.0

    reveal = _clamp(reveal)
    # 三段错开、且各自带缓动：宫格先漫开，图标随后逐个浮起，文字最后浮出。
    grid_t = _ease_in_out(_clamp(reveal / 0.42))
    icon_t = _clamp((reveal - 0.18) / 0.77)
    text_t = _smoothstep(_clamp((reveal - 0.62) / 0.38))

    def fade(color: str) -> str:
        """文字淡入：向底色混合。text_t=1 时为原色。"""
        return _mix(color, bg, text_t)

    # 九宫计数
    counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    for it in layout["icons"]:
        counts[it["row"]][it["col"]] += 1

    grid = palace_grid(top_dir)

    # --- 宫底（由中宫向外点亮）
    lit = int(round(grid_t * 9))
    for idx, (r, c) in enumerate(_SPREAD):
        if idx >= lit:
            continue
        x0, y0 = ox + col_w * c, oy + row_h * r
        x1, y1 = x0 + col_w, y0 + row_h
        n = counts[r][c]
        info = grid[r][c]
        # 每格自己再淡一下，避免"啪"地跳出来；越亮越显色，末帧最完整
        local = _smoothstep(_clamp(grid_t * 9 - idx))
        fill = cell_fill(th, n, info is None, local)
        if not fill:
            continue
        canvas.create_rectangle(x0, y0, x1, y1, outline="", fill=fill)

    # --- 网格线（最后 30% 揭示时浮现）
    if grid_t >= 0.9:
        line_c = fade(th["line"]) if text_t < 1 else th["line"]
        for i in (1, 2):
            canvas.create_line(ox + col_w * i, oy, ox + col_w * i, oy + h,
                               fill=line_c, width=1)
            canvas.create_line(ox, oy + row_h * i, ox + w, oy + row_h * i,
                               fill=line_c, width=1)
        canvas.create_rectangle(ox, oy, ox + w, oy + h,
                               outline=fade(th["line_outer"]), width=1)

    # --- 图标：逐个浮起（圆角方形）
    hits: list[dict] = []
    box = max(3.0, cell_w * scale * 0.5)
    icons = layout["icons"]
    n_icon = max(1, len(icons))
    for idx, it in enumerate(icons):
        start = (idx / n_icon) * 0.55
        p = _clamp((icon_t - start) / 0.45)
        if p <= 0:
            continue
        grow = _ease_back(p, 1.1) if p < 1 else 1.0
        cx = ox + it["cx"] * w
        cy = oy + it["cy"] * h
        half = box * (0.42 + 0.58 * max(0.0, grow)) / 2.0
        fill = th["wuxing"].get(it.get("wuxing", ""), th["ink"])
        hot = (hover is not None and it["index"] == hover)
        if hot:
            half *= 1.55
        rid = canvas.create_polygon(rr_points(cx, cy, half), fill=fill,
                                    outline=th["accent"] if hot else "",
                                    width=1 if hot else 0, tags="ic")
        info = grid[it["row"]][it["col"]]
        tip = it["name"]
        if it.get("wuxing"):
            tip += "\n五行：%s" % it["wuxing"]
        tip += "\n%s宫（%s·%s）" % (
            info["gua"] if info else "中宫",
            info["dir"] if info else "中央",
            info["wuxing"] if info else "土")
        hits.append({"index": it["index"], "id": rid,
                     "cx": cx, "cy": cy, "box": box,
                     "x0": cx - half, "y0": cy - half,
                     "x1": cx + half, "y1": cy + half, "text": tip})

    # --- 宫名与计数（全部带底色描边：压在图标色块上也要能读）
    if text_t > 0:
        d = max(1, int(round(1.1 * fs)))
        halo = fade(th["card"])          # 描边随文字一起淡入
        for r in range(3):
            for c in range(3):
                x0, y0 = ox + col_w * c, oy + row_h * r
                x1, y1 = x0 + col_w, y0 + row_h
                info = grid[r][c]
                n = counts[r][c]
                if info is None:
                    if n == 0:
                        _halo_text(canvas, (x0 + x1) / 2, (y0 + y1) / 2,
                                   text="中宫空 · 吉",
                                   fill=fade(th["accent"]),
                                   font=fonts["small"], halo=halo, d=d)
                    else:
                        _halo_text(canvas, x0 + 10, y1 - 10, text="中宫",
                                   fill=fade(th["accent"]),
                                   font=fonts["small"], anchor="sw",
                                   halo=halo, d=d)
                        _halo_text(canvas, x1 - 10, y1 - 10, text=str(n),
                                   fill=fade(th["sub"]),
                                   font=fonts["small"], anchor="se",
                                   halo=halo, d=d)
                    continue
                _halo_text(canvas, x0 + 10, y1 - 10,
                           text="%s %s" % (info["gua"], info["dir"]),
                           fill=fade(th["accent"]),
                           font=fonts["small"], anchor="sw", halo=halo, d=d)
                _halo_text(canvas, x1 - 10, y1 - 10,
                           text=str(n) if n else "空",
                           fill=fade(th["sub"] if n else th["weak"]),
                           font=fonts["small"], anchor="se", halo=halo, d=d)
                # --- 命主四吉四凶角标：左上角 ● 吉 / × 凶（text_t 淡入）
                if marks and text_t > 0:
                    kind = marks.get(info["gua"])
                    if kind:
                        col = th["level"]["吉"] if kind == "good" \
                            else th["level"]["忌"]
                        if kind == "good":
                            r0 = 3.2 * fs
                            canvas.create_oval(
                                x0 + 9 * fs, y0 + 9 * fs,
                                x0 + 9 * fs + r0, y0 + 9 * fs + r0,
                                fill=col, outline="")
                        else:
                            ax0, ay0 = x0 + 9 * fs, y0 + 9 * fs
                            e = 3.0 * fs
                            canvas.create_line(
                                ax0, ay0, ax0 + e, ay0 + e,
                                ax0 + e, ay0, ax0, ay0 + e,
                                fill=col, width=max(1, int(1.4 * fs)))

    # --- 上方说明
    canvas.create_text(ox + w / 2, oy - 10 * fs - 4, text="▲ 视线尽头 · 明堂",
                       fill=fade(th["weak"]), font=fonts["cap"], anchor="s")

    # --- 下方说明与图例
    ly = oy + h + 16 * fs
    canvas.create_text(ox + w / 2, ly, text="▼ 你坐的位置 · 坐方",
                       fill=fade(th["weak"]), font=fonts["cap"], anchor="n")
    canvas.create_text(ox + w / 2, ly + 24 * fs,
                       text="左青龙 宜动　·　右白虎 宜静",
                       fill=fade(th["weak"]), font=fonts["cap"], anchor="n")

    step = 46 * fs
    lx = ox + w / 2 - step * 2.2
    ly2 = ly + 52 * fs
    for name, color in th["wuxing"].items():
        canvas.create_oval(lx, ly2, lx + 7 * fs, ly2 + 7 * fs,
                           fill=fade(color), outline="")
        canvas.create_text(lx + 11 * fs, ly2 + 3.5 * fs, text=name, anchor="w",
                           fill=fade(th["weak"]), font=fonts["cap"])
        lx += step
    return hits
