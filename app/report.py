# -*- coding: utf-8 -*-
"""单文件 HTML 报告（阶段四）

要求（见 docs/03-设计规范.md 第 9 节）：
  单文件、内联 CSS、**无任何外链、无 JS**、900px 居中、可直接 Ctrl+P 打印成 A4。
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

import classify
import fengshui
import pericon
import project
import prose
from palace import ORIENT_CHOICES, WUXING_COLOR, palace_grid
import paths

OUT_DIR = paths.REPORTS
CELL_TINT = "#EF9F27"
BG_BOARD = "#FDFCF9"

ICON_LABEL = {"file": "文件", "dir": "文件夹", "virtual": "系统项"}
DIR_LABEL = dict(ORIENT_CHOICES)


def _mix(fg: str, bg: str, alpha: float) -> str:
    f = [int(fg[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    c = [round(b[i] * (1 - alpha) + f[i] * alpha) for i in range(3)]
    return "#%02x%02x%02x" % tuple(c)


def _alpha(n: int) -> float:
    if n <= 0:
        return 0.0
    if n <= 4:
        return 0.10
    if n <= 9:
        return 0.18
    return 0.26


# ---------------------------------------------------------------- 九宫盘 SVG

def board_svg(layout: dict, top_dir: int, width: int = 760) -> str:
    cw_all, ch_all = layout["canvas"]
    h = width * ch_all / cw_all
    top_pad, bot_pad = 30, 76
    total_h = h + top_pad + bot_pad
    grid = palace_grid(top_dir)
    counts = [[0, 0, 0] for _ in range(3)]
    for it in layout["icons"]:
        counts[it["row"]][it["col"]] += 1
    cwid, chei = width / 3.0, h / 3.0
    scale = width / cw_all
    box = max(4.0, layout["cell"][0] * scale * 0.5)
    half = box / 2.0
    radius = box * 0.26
    oy = top_pad

    by_cell: dict[tuple[int, int], list[dict]] = {}
    for it in layout["icons"]:
        by_cell.setdefault((it["row"], it["col"]), []).append(it)

    p = ['<svg viewBox="0 0 %d %.1f" width="100%%" xmlns="http://www.w3.org/2000/svg" '
         'style="display:block" role="img" class="board-svg">' % (width, total_h)]
    p.append('<title>桌面九宫实景盘</title>')
    p.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="12" '
             'fill="#888780" font-family="sans-serif">▲ 视线尽头 · 明堂</text>'
             % (width / 2, top_pad - 12))

    # 宫格与图标：每宫一个 <g class="cell">，图标是其子节点，
    # 这样"鼠标在图标上"也算"在本宫上"，CSS 才能直接做宫高亮。
    p.append('<g class="boardg">')
    for r in range(3):
        for c in range(3):
            x0, y0 = c * cwid, oy + r * chei
            n = counts[r][c]
            info = grid[r][c]
            p.append('<g class="cell">')
            fill = "#FAEEDA" if (info is None and n == 0) else (
                _mix(CELL_TINT, BG_BOARD, _alpha(n)) if n else "")
            if fill:
                p.append('<rect class="cbg" x="%.1f" y="%.1f" width="%.1f" '
                         'height="%.1f" fill="%s"/>'
                         % (x0, y0, cwid, chei, fill))

            for it in by_cell.get((r, c), []):
                cx, cy = it["cx"] * width, oy + it["cy"] * h
                color = WUXING_COLOR.get(it.get("wuxing", ""), "#2C2C2A")
                name = html.escape(it["name"])
                short = name if len(it["name"]) <= 24 else name[:23] + "…"

                # 提示默认在图标上方；顶到画布边上就翻到下方
                ty = cy - half - 8
                if ty < oy + 12:
                    ty = cy + half + 14
                if cx < 90:
                    tx, anchor = max(2.0, cx - half), "start"
                elif cx > width - 90:
                    tx, anchor = min(width - 2.0, cx + half), "end"
                else:
                    tx, anchor = cx, "middle"

                wux = it.get("wuxing", "")
                kind = ICON_LABEL.get(it.get("kind", ""), "")
                detail = " · ".join(x for x in (
                    wux, kind, ("%s宫" % info["gua"]) if info else "中宫") if x)

                p.append('<g class="ic">')
                p.append('<rect class="dot" x="%.1f" y="%.1f" width="%.1f" '
                         'height="%.1f" rx="%.2f" fill="%s"/>'
                         % (cx - half, cy - half, box, box, radius, color))
                p.append('<text class="tip" x="%.1f" y="%.1f" text-anchor="%s">'
                         '%s</text>' % (tx, ty, anchor, short))
                p.append('<text class="tip tsub" x="%.1f" y="%.1f" '
                         'text-anchor="%s">%s</text>'
                         % (tx, ty + 11, anchor, html.escape(detail)))
                p.append('</g>')
            p.append('</g>')
    p.append('</g>')

    for i in (1, 2):
        p.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#E5E2D9" '
                 'stroke-width="1"/>' % (cwid * i, oy, cwid * i, oy + h))
        p.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#E5E2D9" '
                 'stroke-width="1"/>' % (oy + chei * i, width, oy + chei * i))
    p.append('<rect x="0.5" y="%.1f" width="%.1f" height="%.1f" fill="none" '
             'stroke="#D3D1C7" stroke-width="1"/>' % (oy, width - 1, h))

    for r in range(3):
        for c in range(3):
            x0, y0 = c * cwid, oy + r * chei
            info = grid[r][c]
            n = counts[r][c]
            by = y0 + chei - 8
            if info is None:
                if n == 0:
                    p.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                             'font-size="12" fill="#854F0B" font-family="sans-serif">'
                             '中宫空 · 吉</text>' % (x0 + cwid / 2, y0 + chei / 2 + 4))
                else:
                    p.append('<text x="%.1f" y="%.1f" font-size="11" fill="#854F0B" '
                             'font-family="sans-serif">中宫</text>' % (x0 + 8, by))
                    p.append('<text x="%.1f" y="%.1f" text-anchor="end" font-size="11" '
                             'fill="#5F5E5A" font-family="sans-serif">%d</text>'
                             % (x0 + cwid - 8, by, n))
                continue
            p.append('<text x="%.1f" y="%.1f" font-size="11" fill="#854F0B" '
                     'font-family="sans-serif">%s %s</text>'
                     % (x0 + 8, by, info["gua"], info["dir"]))
            p.append('<text x="%.1f" y="%.1f" text-anchor="end" font-size="11" '
                     'fill="%s" font-family="sans-serif">%s</text>'
                     % (x0 + cwid - 8, by, "#5F5E5A" if n else "#888780",
                        str(n) if n else "空"))

    p.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" '
             'fill="#888780" font-family="sans-serif">▼ 你坐的位置 · 坐方</text>'
             % (width / 2, oy + h + 20))
    p.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" '
             'fill="#888780" font-family="sans-serif">左青龙 宜动　·　右白虎 宜静</text>'
             % (width / 2, oy + h + 42))

    lx = width / 2 - 108
    for name, color in WUXING_COLOR.items():
        p.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>'
                 % (lx + 3, oy + h + 66, color))
        p.append('<text x="%.1f" y="%.1f" font-size="11" fill="#888780" '
                 'font-family="sans-serif">%s</text>' % (lx + 11, oy + h + 70, name))
        lx += 43
    p.append("</svg>")
    return "".join(p)


# ---------------------------------------------------------------- HTML

# 报告正文字体：设置里选（跟界面共用一份 13 项清单），默认宋体。
# 衬线类回落宋体，黑体类回落无衬线——回退要有"同类"意识，否则楷体缺字体会突然变成黑体。
BODY_FONT_SLOT = "__BODY_FONT__"     # CSS 里的占位符，生成时替换成实际字体栈
_SERIF_FAMS = {"SimSun", "NSimSun", "STSong", "STZhongsong", "FangSong",
               "STFangsong", "KaiTi", "STKaiti", "LiSu", "STLiti",
               "STXingkai", "STXinwei"}
REPORT_FONT_DEFAULT = "SimSun"


def _stack(fam: str | None) -> str:
    """字体栈：首选字体 + 同类回退。列表去重，免得选出 "SimSun","SimSun"。"""
    fam = fam or REPORT_FONT_DEFAULT
    if fam in _SERIF_FAMS:
        chain = [fam, "SimSun", "Songti SC", "Noto Serif CJK SC", "serif"]
    else:
        chain = [fam, "Microsoft YaHei", "PingFang SC", "sans-serif"]
    out = []
    for x in chain:
        if x not in out:
            out.append(x)
    return ",".join(('"%s"' % x) if x not in ("serif", "sans-serif") else x
                    for x in out)


def _scale_css(css: str, scale: float) -> str:
    """把 CSS 里所有 font-size 的字号按倍率缩放。

    只动 font-size，不动 padding/margin 的 clamp()——盘中留白是版面，不是字号。
    SVG 里的 font-size="12" 是属性，不是 CSS，也留着不缩：盘面是张图，
    字放大容易溢出格子。
    """
    if not scale or abs(scale - 1.0) < 0.005:
        return css

    def _clamp(m):
        lo, vw, hi = float(m.group(1)), m.group(2), float(m.group(3))
        return "font-size:clamp(%gpx,%svw,%gpx)" % (
            round(lo * scale, 1), vw, round(hi * scale, 1))

    def _px(m):
        return "font-size:%gpx" % round(float(m.group(1)) * scale, 1)

    css = re.sub(r"font-size:clamp\(([\d.]+)px,([\d.]+)vw,([\d.]+)px\)",
                 _clamp, css)
    return re.sub(r"font-size:([\d.]+)px", _px, css)


def css_for(font: str | None = None, scale: float = 1.0) -> str:
    """按设置生成这份报告用的 CSS。"""
    return _scale_css(CSS.replace(BODY_FONT_SLOT, _stack(font)), scale)


CSS = """
:root{
 --paper:#FAF8F3;--card:#FEFDFB;--ink:#23221F;--sub:#4F4E49;
 --weak:#6B6961;--line:#E3DED1;--hair:#EFEAE0;--accent:#8A3B12;--seal:#9C2B24
}
*{box-sizing:border-box}
html{background:var(--paper)}
body{margin:0;color:var(--ink);background:var(--paper);
 font-family:__BODY_FONT__;
 font-size:13.5px;line-height:1.85;-webkit-font-smoothing:antialiased}
.sheet{max-width:940px;margin:26px auto;background:var(--card);
 padding:clamp(32px,5vw,56px) clamp(28px,6vw,60px) 58px;
 border:1px solid var(--line)}
header{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:30px}
h1,h2,.num,.seal{font-family:"Songti SC","SimSun","Noto Serif CJK SC",
 Georgia,serif}
h1{font-size:clamp(21px,3vw,26px);font-weight:600;letter-spacing:2px;
 margin:0 0 10px;display:flex;align-items:center;gap:13px;line-height:1.3}
.seal{width:34px;height:34px;background:var(--seal);color:#FEFDFB;
 display:inline-flex;align-items:center;justify-content:center;
 font-size:19px;flex:0 0 auto;letter-spacing:0}
.meta{color:var(--weak);font-size:12px;margin:0;letter-spacing:.3px}
.board{background:var(--card);padding:18px 18px 6px;margin:0 0 28px;
 border:1px solid var(--line)}
.score{display:flex;align-items:baseline;gap:15px;margin:0 0 2px}
.num{font-size:48px;font-weight:600;line-height:1;letter-spacing:-1px}
.grade{font-size:16px;color:var(--sub)}
.summary{color:var(--sub);margin:0 0 26px}
h2{font-size:15px;font-weight:600;color:var(--accent);margin:38px 0 14px;
 padding-bottom:7px;border-bottom:1px solid var(--line);letter-spacing:1.5px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--hair)}
th{color:var(--weak);font-weight:400;letter-spacing:.6px}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.bar{height:5px;background:#EDE7DA;overflow:hidden;min-width:90px}
.bar i{display:block;height:5px}
.card{border-left:2px solid var(--line);border-bottom:1px solid var(--hair);
 padding:13px 0 13px 17px;margin:0}
.ch{display:flex;justify-content:space-between;align-items:baseline;
 margin-bottom:4px;gap:12px}
.ck{font-weight:600;font-size:13.5px}
.tag{font-size:11px;padding:1px 0;margin-right:9px;letter-spacing:2px}
.ev{color:var(--sub);font-size:12.5px}
.pr{font-size:12.5px;margin-top:4px}
.ad{font-size:12.5px;color:var(--accent);margin-top:4px}
.prose>p{text-indent:2em;margin:0 0 15px;line-height:2.05;
 font-size:13.5px;text-align:justify}
.prose>p:first-child{text-indent:0}
.prose>p:first-child::first-letter{
 float:left;font-family:"Songti SC","SimSun",Georgia,serif;
 font-size:3.3em;line-height:.82;padding:7px 11px 0 0;color:var(--seal)}
.cmp{display:flex;gap:16px;align-items:flex-start}
.cmp>div{flex:1;min-width:0}
.sub{font-size:12px;color:var(--accent);margin-bottom:8px;letter-spacing:1px}
.foot{margin-top:42px;padding-top:18px;border-top:1px solid var(--line);
 color:var(--weak);font-size:11.5px;line-height:1.95}

/* ---------- 分图标（<details> 折叠，仍然无 JS） ---------- */
details{border-top:1px solid var(--hair);padding:8px 0}
details>summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--ink);
 list-style:none;padding-left:15px;position:relative}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"▸";position:absolute;left:0;top:1px;
 color:var(--weak);font-size:11px}
details[open]>summary::before{content:"▾"}
.pi{margin:7px 0 0 17px;font-size:12.5px;line-height:1.75}
.pi>b{color:var(--ink);font-weight:600}
.pi .rel{color:var(--weak);font-size:11.5px;margin-left:7px}
.pi .sec{margin-top:3px;color:var(--sub)}
.pi .sec .tag{color:var(--weak);margin-right:5px}
.pi .adv{color:var(--accent)}

/* 图例：五级判定 */
.pi-legend{margin-top:16px;padding-top:11px;border-top:1px solid var(--hair);
 font-size:12px;color:var(--sub);line-height:1.95}
.pi-legend .lg-title{color:var(--weak);font-size:11.5px;margin-bottom:4px}
.pi-legend i{display:inline-block;width:7px;height:7px;border-radius:50%;
 margin-right:7px;vertical-align:1px}
.pi-legend b{color:var(--ink);font-weight:600;margin-right:8px;font-size:12.5px}

/* 展开时逐条淡入：<details> 展开本身没有过渡，用 animation 补上 */
@keyframes piIn{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:none}}
details[open]>.pi{animation:piIn .22s cubic-bezier(.2,.7,.3,1) both}
details[open]>.pi:nth-child(2){animation-delay:.04s}
details[open]>.pi:nth-child(3){animation-delay:.08s}
details[open]>.pi:nth-child(4){animation-delay:.12s}
details[open]>.pi:nth-child(5){animation-delay:.16s}
details[open]>.pi:nth-child(6){animation-delay:.2s}
details[open]>.pi:nth-child(7){animation-delay:.24s}
details[open]>.pi:nth-child(8){animation-delay:.28s}
details[open]>.pi:nth-child(9){animation-delay:.3s}
details[open]>.pi:nth-child(n+10){animation-delay:.32s}
@media (prefers-reduced-motion:reduce){
 details[open]>.pi{animation:none}
}

/* ---------- 交互动效（纯 CSS，无脚本） ---------- */
@keyframes rise{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
h2,.score,.board,.prose p,.meta{animation:rise .62s cubic-bezier(.22,.61,.36,1) both}
/* 卡片只用淡入：动画的 transform 会盖掉 :hover 的位移 */
.card{animation:fade .5s ease both;
 transition:background .22s ease,border-color .22s ease,transform .22s ease}
.card:hover{background:#FDFBF4;border-color:#D8CEB6;transform:translateY(-1px)}
tbody tr{transition:background .18s ease}
tbody tr:hover{background:#FBF8F0}
.bar i{transform-origin:left center;animation:grow .95s cubic-bezier(.22,.61,.36,1) both}
tbody tr:nth-child(2) .bar i{animation-delay:.08s}
tbody tr:nth-child(3) .bar i{animation-delay:.16s}
tbody tr:nth-child(4) .bar i{animation-delay:.24s}
tbody tr:nth-child(5) .bar i{animation-delay:.32s}
tbody tr:nth-child(6) .bar i{animation-delay:.40s}

/* 盘里的小方块：悬停放大、其余变淡、浮出名称 */
.board-svg .dot{transform-box:fill-box;transform-origin:center;
 transition:transform .2s cubic-bezier(.22,.61,.36,1),opacity .2s ease}
.boardg:hover .cell:not(:hover) .dot{opacity:.45}
.board-svg .ic:hover .dot{transform:scale(1.5)}
.board-svg .tip{opacity:0;pointer-events:none;transition:opacity .16s ease;
 font-family:"Microsoft YaHei","PingFang SC",sans-serif;font-size:10.5px;
 fill:#23221F;font-weight:600;paint-order:stroke;stroke:#FDFCF9;
 stroke-width:3px;stroke-linejoin:round}
.board-svg .tip.tsub{font-size:9.5px;font-weight:400;fill:#5F5E5A}
.board-svg .ic:hover .tip{opacity:1}
/* 宫名（坎 北、巽 东南）压在图标上时不许拦截鼠标：
   SVG text 默认会吃掉 hover，下面的图标 tooltip 就出不来了（2026-10-27 用户报）。
   全部文字对鼠标透明——tip 本身只在 .ic:hover 时显示，穿透不影响它。 */
.board-svg text{pointer-events:none}
.board-svg .cell:hover .cbg{filter:brightness(1.04)}
.board-svg .cbg{transition:filter .2s ease}

@media (prefers-reduced-motion:reduce){
 *{animation:none!important;transition:none!important}
 .board-svg .tip{display:none}
}
@media print{
 html,body{background:#fff}
 .sheet{border:0;margin:0;padding:0;max-width:none}
 .card,.board{break-inside:avoid}
 h2{break-after:avoid}
 *{animation:none!important;transition:none!important}
 .board-svg .tip{display:none}
}
"""

LEVEL_STYLE = {
    "忌": ("#FCEBEB", "#A32D2D"),
    "平": ("#F1EFE8", "#5F5E5A"),
    "吉": ("#EAF3DE", "#3B6D11"),
    "述": ("#F1EFE8", "#888780"),
}


LEVEL_FG = {"忌": "#9C2B24", "平": "#5F5E5A", "吉": "#3B6D11", "述": "#6B6961"}


def _card(d: dict) -> str:
    fg = LEVEL_FG.get(d["level"], "#4F4E49")
    tag = '<span class="tag" style="color:%s">%s</span>' % (fg, d["level"])
    right = ""
    if d["max"]:
        right = ('<span style="color:%s;font-size:11.5px">%s</span>'
                 % (fg, ("扣 %g" % d["deduct"]) if d["deduct"] else "满分"))
    return (
        '<div class="card" style="border-left-color:%s">'
        '<div class="ch"><div class="ck">%s%s</div>%s</div>'
        '<div class="ev">%s</div>'
        '<div class="pr">理　%s</div>'
        '<div class="ad">改　%s</div></div>'
        % (fg, tag, html.escape(d["key"]), right,
           html.escape(d["evidence"]), html.escape(d["principle"]),
           html.escape(d["advice"]))
    )


def build_html(layout: dict, result: dict, prev: dict | None = None,
               font: str | None = None, scale: float = 1.0) -> str:
    e = html.escape
    st = result["stats"]
    top_dir = result.get("orientation", 180)

    # 六项
    rows = []
    for s in result["sections"].values():
        ratio = s["score"] / s["max"] if s["max"] else 0
        color = "#3B6D11" if ratio >= 0.8 else ("#854F0B" if ratio >= 0.5 else "#A32D2D")
        rows.append(
            "<tr><td>%s</td><td class='n'>%g / %g</td>"
            "<td style='width:180px'><div class='bar'><i style='width:%.0f%%;"
            "background:%s'></i></div></td><td class='n' style='color:#888780'>扣 %g</td></tr>"
            % (s["name"], s["score"], s["max"], ratio * 100, color,
               s["max"] - s["score"]))
    sections_html = ("<table><tr><th>分项</th><th class='n'>得分</th><th></th>"
                     "<th class='n'>扣分</th></tr>%s</table>" % "".join(rows))

    # 五行分布
    wux = "".join(
        "<tr><td><span style='color:%s'>%s</span></td><td class='n'>%d</td>"
        "<td class='n'>%.0f%%</td></tr>"
        % (WUXING_COLOR[w], w, st["dist"][w],
           st["dist"][w] / st["total"] * 100 if st["total"] else 0)
        for w in classify.WUXING_ORDER)
    wux_html = ("<table><tr><th>五行</th><th class='n'>个数</th><th class='n'>占比</th></tr>"
                "%s</table>" % wux)

    # 各宫
    grid = palace_grid(top_dir)
    cells_html = "".join(
        "<tr><td>%s宫</td><td>%s</td><td class='n'>%d</td><td class='n'>%+.1f</td></tr>"
        % (p["gua"], p["wuxing"], p["count"], p["net"])
        for p in sorted(st["palace_detail"], key=lambda x: (x["row"], x["col"])))
    cells_html = ("<table><tr><th>宫位</th><th>五行</th><th class='n'>图标数</th>"
                  "<th class='n'>净气</th></tr>%s</table>" % cells_html)

    urgent = result["urgent"]
    urgent_html = "".join(_card(d) for d in urgent) or "<p class='ev'>无。</p>"
    all_html = "".join(_card(d) for d in result["diagnoses"])
    prose_html = "".join("<p>%s</p>" % e(p) for p in prose.compose(result))

    # 推演：只算不改（两档：最小调整 / 全部重排）
    proj_layout, moves = project.project(layout, top_dir)
    proj_res = fengshui.analyze(proj_layout, top_dir)
    rep_layout, _rep_moves = project.repack(layout, top_dir)
    rep_res = fengshui.analyze(rep_layout, top_dir)
    grid = palace_grid(top_dir)

    def _cell_name(rc):
        r, c = rc
        info = grid[r][c]
        return (info["gua"] + "宫") if info else "中宫"

    move_html = "、".join(
        "「%s」%s→%s" % (e(m["name"]), _cell_name(m["from"]), _cell_name(m["to"]))
        for m in moves[:10]) or "无需移动"
    proj_html = (
        '<p class="ev">左为现状，右为「最小调整」——只挪明堂溢出与中宫里的图标，'
        '其余一动不动，照着做完就是右边那样：<b>%d → %d 分</b>。</p>'
        '<div class="cmp">'
        '<div><div class="sub">现状 · %d 分</div>%s</div>'
        '<div><div class="sub">最小调整 · %d 分</div>%s</div>'
        '</div>'
        '<p class="ev">移动 %d 个：%s</p>'
        '<div style="margin-top:24px"><div class="sub">全部重排 · %d 分（只看效果）</div>%s</div>'
        '<p class="ev">「全部重排」把 %d 个图标按「外实内虚」重新摆一遍：四周贴边、'
        '中间留空。分数更高，但要手动挪几十次，只作参考——'
        '程序不会动你的桌面，一个图标都不会。</p>'
        % (result["score"], proj_res["score"],
           result["score"], board_svg(layout, top_dir, 398),
           proj_res["score"], board_svg(proj_layout, top_dir, 398),
           len(moves), move_html,
           rep_res["score"], board_svg(rep_layout, top_dir, 760),
           len(layout["icons"])))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    prev_html = ""
    if prev:
        diff = result["score"] - prev.get("score", result["score"])
        sign = "＋%d" % diff if diff > 0 else ("%d" % diff if diff < 0 else "持平")
        prev_html = ("　｜　上次 %s 为 %d 分（%s）"
                     % (prev.get("t", "").replace("T", " ")[:16],
                        prev.get("score", 0), sign))

    # 分图标：九宫 <details> 折叠，每个图标三段
    pericon_html: list[str] = []
    for g in pericon.build(layout, result):
        lv = "宜空" if g["center"] else g["level"]
        lv_color = {"吉": "#3B6D11", "平": "#854F0B",
                    "忌": "#9C2D2D"}.get(g["level"], "#6B6961")
        if g["center"]:
            head = "中宫 · %d 个" % g["count"]
        else:
            head = "%s宫 · %s · %d 个 · 平均 %d" % (
                g["gua"], g["dir"], g["count"], g["avg"])
        rows = []
        for ic in g["icons"]:
            c = ("#3B6D11" if ic["score"] >= 70
                 else ("#854F0B" if ic["score"] >= 45 else "#9C2D2D"))
            rows.append(
                "<div class='pi'><b>%s</b><span class='rel'>%s · %s</span>"
                "<span class='rel' style='color:%s'>%s</span>"
                "<div class='sec'><span class='tag'>现</span>%s</div>"
                "<div class='sec'><span class='tag'>理</span>%s</div>"
                "<div class='sec adv'><span class='tag'>改</span>%s</div></div>"
                % (e(ic["name"]), ic["wuxing"], ic["rel"], c, ic["verdict"],
                   e(ic["evidence"]), e(ic["principle"]), e(ic["advice"])))
        pericon_html.append(
            "<details><summary>%s　<span style='color:%s;font-size:11.5px'>"
            "%s</span></summary>%s</details>"
            % (head, lv_color, lv, "".join(rows)))

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桌面风水报告 · %(now)s</title>
<style>%(css)s</style></head><body>
<main class="sheet">
<header>
<h1><span class="seal">風</span>桌面风水 · 布局分析</h1>
<p class="meta">扫描时间 %(now)s　·　画布 %(cw)d×%(ch)d　·　%(n)d 个图标　·　%(orient)s%(prev)s</p>
</header>

<section class="board">%(board)s</section>

<section>
<div class="score"><span class="num">%(score)d</span><span class="grade">%(grade)s</span></div>
<p class="summary">%(summary)s　（对账：100 − 扣分 %(deduct)g = %(score)d）</p>
</section>

<section><h2>总评</h2>
<div class="prose">%(prose)s</div></section>

<section><h2>七项评分</h2>
%(sections)s</section>

<section><h2>最该动手的三条</h2>
%(urgent)s</section>

<section><h2>全部诊断</h2>
%(all)s</section>

<section><h2>理想布局 · 两档</h2>
%(proj)s</section>

<section><h2>分图标</h2>
<p class="note">每一格里的每一件东西，按它与本宫的五行关系单独判一次；点标题展开。</p>
%(pericon)s
<div class="pi-legend">
<div class="lg-title">判定的意思</div>
<div><i style="background:#2F6B11"></i><b>得位</b>这件东西在养这一宫（生入），放得其所</div>
<div><i style="background:#7A9A1E"></i><b>合宜</b>同气相求（比和），不冲不耗，也不额外帮忙</div>
<div><i style="background:#8A5A12"></i><b>受制</b>这一宫的五行克它（主克客），用起来总差一层</div>
<div><i style="background:#C4631A"></i><b>耗散</b>这一宫的气被它抽走（泄气），越用越虚</div>
<div><i style="background:#8E2318"></i><b>相冲</b>它在压这一宫（克入），最该挪走</div>
</div>
</section>

<section><h2>附录 · 五行分布</h2>
%(wux)s</section>

<section><h2>附录 · 各宫明细</h2>
%(cells)s</section>

<footer class="foot">
本报告由本地程序生成，<strong>未上传任何数据</strong>，未修改桌面上任何图标或文件。<br>
结论基于形法模型（中宫／明堂／四象／形态／杂物／五行生克）推演，仅供自省参考，
不构成对个人运势的判断。<br>
本程序不读取文件名以外的任何文件内容，不读取文件体积与修改时间，不截屏；
推演图为虚拟计算，桌面上的图标一个也没有移动。
</footer>
</main></body></html>
""" % {
        "now": now, "css": css_for(font, scale),
        "cw": layout["canvas"][0], "ch": layout["canvas"][1],
        "n": st["total"], "prev": prev_html,
        "orient": DIR_LABEL.get(top_dir, "上方朝向角 %d°" % top_dir),
        "board": board_svg(layout, top_dir),
        "score": result["score"], "grade": html.escape(result["grade"]),
        "summary": html.escape(result["summary"]),
        "deduct": result["deduct_total"],
        "prose": prose_html,
        "sections": sections_html, "urgent": urgent_html, "all": all_html,
        "proj": proj_html,
        "wux": wux_html, "cells": cells_html,
        "pericon": "".join(pericon_html),
    }


def export(layout: dict, result: dict, prev: dict | None = None,
           font: str | None = None, scale: float = 1.0) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ("风水报告_%s.html" % datetime.now().strftime("%Y%m%d_%H%M"))
    path.write_text(build_html(layout, result, prev, font, scale),
                    encoding="utf-8")
    return path
