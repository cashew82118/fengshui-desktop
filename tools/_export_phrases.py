# -*- coding: utf-8 -*-
"""把诊断文案池导成 Excel，方便逐条看文案。

用法：python _export_phrases.py
输出：exports/文案库_说法池_YYYYMMDD_HHMM.xlsx

三张表：
  1) 文案总表 —— 每个分支每一组一行；F/G/H 是模板，I/J/K 是按该分支条件填好的成品
  2) 进度与计划 —— 已完成 / 待写的分支清单与组数
  3) 怎么用 —— 改文案的位置与可用占位符
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import phrases_pool as P  # noqa: E402

# 分支键 → (卡片, 触发条件)
BRANCH = {
    "center.empty.low": ("中宫", "中宫空 · 图标总数 ≤ 20"),
    "center.empty.mid": ("中宫", "中宫空 · 图标总数 21–40"),
    "center.empty.high": ("中宫", "中宫空 · 图标总数 > 40"),
    "center.press.one": ("中宫", "中宫受压 · 正中 1 个"),
    "center.press.small": ("中宫", "中宫受压 · 正中 2–3 个"),
    "center.press.big": ("中宫", "中宫受压 · 正中 ≥ 4 个"),
    "hall.block.light": ("明堂", "明堂壅塞 · 该宫 ≤ 9 个"),
    "hall.block.mid": ("明堂", "明堂壅塞 · 该宫 10–14 个"),
    "hall.block.heavy": ("明堂", "明堂壅塞 · 该宫 ≥ 15 个"),
    "hall.open.none": ("明堂", "明堂开阔 · 该宫 0 个"),
    "hall.open.some": ("明堂", "明堂开阔 · 该宫 1–3 个"),
    "sides.baihu.light": ("四象", "白虎抬头 · 右多于左 1–3 个"),
    "sides.baihu.mid": ("四象", "白虎抬头 · 右多于左 4–10 个"),
    "sides.baihu.heavy": ("四象", "白虎抬头 · 右多于左 ≥ 11 个"),
    "sides.qinglong.strong": ("四象", "青龙过旺 · 左右比 5–8"),
    "sides.qinglong.alone": ("四象", "青龙过旺 · 左右比 > 8"),
    "sides.both_empty": ("四象", "左右两侧皆空"),
    "sides.good.no_right": ("四象", "左右得宜 · 右侧 0 个"),
    "sides.good.left_wide": ("四象", "左右得宜 · 左右比 ≥ 2"),
    "sides.good.balanced": ("四象", "左右得宜 · 左右比 < 2"),
    "form.good": ("形态", "形态得宜 · 该得分 ≥ 90%"),
    "form.mild.zone": ("形态", "形态小瑕 · 主因盘心压物"),
    "form.mild.align": ("形态", "形态小瑕 · 主因未对齐"),
    "form.mild.flow": ("形态", "形态小瑕 · 主因空宫略多"),
    "form.bad.zone": ("形态", "中庭受压 · 主因盘心"),
    "form.bad.align": ("形态", "排列散乱 · 主因未对齐"),
    "form.bad.flow": ("形态", "气不周流 · 主因空宫多"),
    "clutter.dirty": ("杂物", "杂物压盘 · 检出杂物并扣分"),
    "clutter.clean": ("杂物", "盘面洁净 · 未检出"),
    "wuxing.block": ("生克", "五行相碍 · 本宫克泄成势"),
    "wuxing.ok.positive": ("生克", "五行相安 · 净气为正"),
    "wuxing.ok.neutral": ("生克", "五行相安 · 净气不为正"),
    "bianque.missing": ("偏枯", "某行全无"),
    "bianque.full": ("偏枯", "某行过旺"),
    "axis.none": ("述类", "中轴观 · 中轴无物"),
    "axis.light": ("述类", "中轴观 · 中轴占 <8%"),
    "axis.heavy": ("述类", "中轴观 · 中轴占 ≥8%"),
    "balance.center": ("述类", "重心观 · 距盘心 <0.08"),
    "balance.light": ("述类", "重心观 · 0.08–0.18"),
    "balance.heavy": ("述类", "重心观 · ≥0.18"),
    "corner.full": ("述类", "四隅观 · 四角皆有物"),
    "corner.part": ("述类", "四隅观 · 空 1–2 角"),
    "corner.empty": ("述类", "四隅观 · 空 ≥3 角"),
    "density.wide": ("述类", "宫内疏密 · 铺占 ≥45%"),
    "density.half": ("述类", "宫内疏密 · 铺占 25–45%"),
    "density.corner": ("述类", "宫内疏密 · 铺占 <25%"),
    "cluster.both": ("述类", "成墙与孤岛 · 两者都有"),
    "cluster.wall": ("述类", "成墙与孤岛 · 只有墙"),
    "cluster.island": ("述类", "成墙与孤岛 · 只有岛"),
    "bands.no_root": ("述类", "三才 · 下带为零"),
    "bands.sky_heavy": ("述类", "三才 · 天重于地"),
    "bands.earth_heavy": ("述类", "三才 · 地重于天"),
    "bands.even": ("述类", "三才 · 三带相若"),
    "mix.system_only": ("述类", "器类构成 · 几乎只有系统项"),
    "mix.no_dir": ("述类", "器类构成 · 零文件夹"),
    "mix.few_dir": ("述类", "器类构成 · 文件夹 <15%"),
    "mix.dir_heavy": ("述类", "器类构成 · 文件夹 >50%"),
    "mix.half": ("述类", "器类构成 · 参半"),
    "synth.center_hall": ("述类", "局之总象 · 中宫虚而明堂塞"),
    "synth.hall_open_center_full": ("述类", "局之总象 · 中宫塞而明堂通"),
    "synth.baihu_clutter": ("述类", "局之总象 · 白虎抬头＋杂物"),
    "synth.baihu_zero": ("述类", "局之总象 · 白虎抬头＋五行缺"),
    "synth.all_empty": ("述类", "局之总象 · 中宫明堂皆虚"),
    "synth.hall_ok_clutter": ("述类", "局之总象 · 明堂通＋杂物多"),
    "synth.best": ("述类", "局之总象 · 中宫虚/五行全/杂物净"),
    "synth.zero_wide": ("述类", "局之总象 · 五行缺＋九宫铺开"),
}

# 公共样例值 + 每个分支自己的数字（必须与「触发条件」自洽，
# 否则会出现「明堂开阔·1–3 个」却填 12 个这种自相矛盾的示例）
BASE = dict(total=46, gua="离", avg=2.0, ratio=6.0, move_n=6,
            names="「ai workshop」", first="ai workshop", target="坎宫（北）",
            n=12, nl=20, nr=14, diff=6, sample="ai workshop",
            occupied=7, pct=96, zone_n=0, empty_n=1,
            zone_txt="盘心空着",
            ev="7 宫有图标，96% 落网格，盘心一片干净")
SAMPLE = {
    "center.empty.low": dict(total=8),
    "center.empty.mid": dict(total=30),
    "center.empty.high": dict(total=60),
    "center.press.one": dict(n=1, names="「ai workshop」"),
    "center.press.small": dict(n=3, names="「ai workshop」「单」「tools」"),
    "center.press.big": dict(n=5, names="「ai workshop」「单」「tools」等"),
    "hall.block.light": dict(n=6, ratio=3.0, move_n=3),
    "hall.block.mid": dict(n=12, ratio=6.0, move_n=6),
    "hall.block.heavy": dict(n=18, ratio=9.0, move_n=8),
    "hall.open.none": dict(n=0),
    "hall.open.some": dict(n=2),
    "sides.baihu.light": dict(nl=20, nr=23, diff=3),
    "sides.baihu.mid": dict(nl=18, nr=25, diff=7),
    "sides.baihu.heavy": dict(nl=10, nr=26, diff=16),
    "sides.qinglong.strong": dict(nl=24, nr=4, ratio=6.0),
    "sides.qinglong.alone": dict(nl=30, nr=2, ratio=15.0),
    "sides.both_empty": dict(total=46),
    "sides.good.no_right": dict(nl=22, nr=0, ratio=22.0),
    "sides.good.left_wide": dict(nl=24, nr=8, ratio=3.0),
    "sides.good.balanced": dict(nl=14, nr=11, ratio=1.3),
    "form.good": dict(occupied=7, pct=100, zone_n=0, empty_n=1,
                      zone_txt="盘心空着",
                      ev="7 宫有图标，100% 落网格，盘心一片干净"),
    "form.mild.zone": dict(occupied=7, pct=96, zone_n=2, empty_n=1,
                           zone_txt="盘心压着 2 个",
                           ev="7 宫有图标，96% 落网格，盘心压着 2 个"),
    "form.mild.align": dict(occupied=6, pct=72, zone_n=0, empty_n=2,
                            zone_txt="盘心空着",
                            ev="6 宫有图标，72% 落网格，盘心一片干净"),
    "form.mild.flow": dict(occupied=4, pct=100, zone_n=0, empty_n=4,
                           zone_txt="盘心空着",
                           ev="4 宫有图标，100% 落网格，盘心一片干净"),
    "form.bad.zone": dict(occupied=6, pct=88, zone_n=9, empty_n=2,
                          zone_txt="盘心压着 9 个",
                          ev="6 宫有图标，88% 落在整齐网格上；"
                             "盘心一带压着 9 个（占 20%）"),
    "form.bad.align": dict(occupied=7, pct=41, zone_n=1, empty_n=1,
                           zone_txt="盘心压着 1 个",
                           ev="7 宫有图标，41% 落在整齐网格上；"
                              "盘心一带压着 1 个（占 2%）"),
    "form.bad.flow": dict(occupied=3, pct=100, zone_n=0, empty_n=5,
                          zone_txt="盘心空着",
                          ev="3 宫有图标，100% 落在整齐网格上"),
    "clutter.dirty": dict(n=5, cap=7, names="「下载(3).exe」「新建文件夹」",
                          kind_word="安装包"),
    "clutter.clean": dict(),
    "wuxing.block": dict(gua="离", gw="火", count=9, bad=4, net_txt="-2.5",
                         kind_word="客克主", kind_tip="物反过来克宫，是客克主",
                         kind_ad="把克本宫的那几类移出本宫",
                         names="「某壁纸」「某主题」", icon_wx="水"),
    "wuxing.ok.positive": dict(net_txt="+2.6"),
    "wuxing.ok.neutral": dict(net_txt="-0.2"),
    "bianque.missing": dict(w="木", total=46, w_role="文思",
                            w_miss_ad="添一两件文书、笔记类入盘"),
    "bianque.full": dict(w="木", n=20, share_pct="43%", w_role="文思",
                         w_risk="文思过盛而落地不足",
                         w_full_ad="移走一部分文书类"),
    "axis.none": dict(axis_n=0, total=46, axis_pct="0%"),
    "axis.light": dict(axis_n=2, total=46, axis_pct="4%"),
    "axis.heavy": dict(axis_n=6, total=46, axis_pct="13%"),
    "balance.center": dict(off="0.03", dir="左"),
    "balance.light": dict(off="0.12", dir="左上"),
    "balance.heavy": dict(off="0.27", dir="左上"),
    "corner.full": dict(corner_n=0, names="乾宫、坤宫"),
    "corner.part": dict(corner_n=2, names="乾宫、坤宫"),
    "corner.empty": dict(corner_n=4, names="乾宫、坤宫、艮宫、巽宫"),
    "density.wide": dict(gua="离", n=6, frac_pct="62%"),
    "density.half": dict(gua="离", n=6, frac_pct="32%"),
    "density.corner": dict(gua="艮", n=6, frac_pct="6%"),
    "cluster.both": dict(wall="左侧有 3 列连成一道墙", island="右下有一处孤岛"),
    "cluster.wall": dict(wall="左侧有 3 列连成一道墙", island=""),
    "cluster.island": dict(wall="", island="右下有一处孤岛"),
    "bands.no_root": dict(tian=30, ren=16, di=0),
    "bands.sky_heavy": dict(tian=30, ren=10, di=6),
    "bands.earth_heavy": dict(tian=6, ren=10, di=30),
    "bands.even": dict(tian=16, ren=15, di=15),
    "mix.system_only": dict(n_file=0, n_dir=0, n_virtual=5, dir_pct="0%"),
    "mix.no_dir": dict(n_file=37, n_dir=0, n_virtual=5, dir_pct="0%"),
    "mix.few_dir": dict(n_file=37, n_dir=4, n_virtual=5, dir_pct="10%"),
    "mix.dir_heavy": dict(n_file=6, n_dir=20, n_virtual=5, dir_pct="77%"),
    "mix.half": dict(n_file=20, n_dir=12, n_virtual=5, dir_pct="38%"),
}
# 局之总象：8 支共用一套字段
for _k in ("synth.center_hall", "synth.hall_open_center_full",
           "synth.baihu_clutter", "synth.baihu_zero", "synth.all_empty",
           "synth.hall_ok_clutter", "synth.best", "synth.zero_wide"):
    SAMPLE[_k] = dict(hall_n=12, occupied=7, zero_w="木")

# 待写分支（实际在用 69 个分支 − 已进池的 27 个）
PLAN: list[tuple[str, int, str, int]] = []      # 全部写完，无待写分支

HEAD_FILL = PatternFill("solid", fgColor="F2EDE3")
CARD_FILL = PatternFill("solid", fgColor="FAF7F0")
LINE = Side(style="thin", color="D8D0C0")
BORDER = Border(left=LINE, right=LINE, top=LINE, bottom=LINE)
FONT = Font(name="微软雅黑", size=10)
FONT_H = Font(name="微软雅黑", size=10, bold=True, color="6B4A2F")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="top")


def fill(tpl: str, key: str) -> str:
    """按该分支的条件填样例；填不进去原样返回模板。"""
    kw = dict(BASE)
    kw.update(SAMPLE.get(key, {}))
    try:
        return tpl.format(**kw)
    except (KeyError, IndexError, ValueError):
        return tpl


DEAD = ("spread_empty", "spread_messy", "spread_good")   # 已废弃，界面不出现


def count_branches() -> int:
    """数 phrases.py 里**界面上会出现的**分支数。

    · 死代码（旧聚散三函数）不计；
    · form() 只有 1 个 return，但内部按 worst 分三套说法（盘心/对齐/空宫），
      在界面上是三种不同文案，所以补 2；
    · 述类有 3 支返回空值、根本不出卡片（成墙与孤岛都无 / 三才全零 /
      局之总象兜底），要扣掉，否则进度表会显示「有 3 个没写」。
    """
    src = (ROOT / "app" / "phrases.py").read_text(encoding="utf-8")
    total = 0
    for body in re.split(r"\ndef ", src)[1:]:
        name = body.split("(")[0]
        # 下划线开头的是内部助手（_pick / _form_kw …），不是界面分支
        if name.startswith("_") or name in DEAD:
            continue
        total += max(1, body.count("return ("))
    return total + 2 - 3


def build() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "文案总表"

    heads = ["序号", "卡片", "分支键", "触发条件", "组号",
             "现象（模板）", "理（模板）", "改（模板）",
             "示例·现象", "示例·理", "示例·改"]
    widths = [6, 7, 18, 25, 6, 40, 40, 40, 40, 40, 40]
    for i, (h, w) in enumerate(zip(heads, widths), 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font, c.fill, c.border = FONT_H, HEAD_FILL, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "F2"
    ws.row_dimensions[1].height = 26

    r = 2
    idx = 0
    for key in P.POOL:
        card, cond = BRANCH.get(key, ("待补", key))
        for gi, (ev, pr, ad) in enumerate(P.POOL[key], 1):
            idx += 1
            vals = [idx, card, key, cond, gi, ev, pr, ad,
                    fill(ev, key), fill(pr, key), fill(ad, key)]
            for ci, v in enumerate(vals, 1):
                c = ws.cell(row=r, column=ci, value=v)
                c.font, c.border = FONT, BORDER
                c.alignment = CENTER if ci <= 5 else WRAP
                if ci >= 9:                      # 成品列淡底，与模板区分
                    c.fill = CARD_FILL
            ws.row_dimensions[r].height = 56
            r += 1

    # ---------------- 进度表
    ws2 = wb.create_sheet("进度与计划")
    total_branch = count_branches()
    done_branch = len(P.POOL)
    done_groups = sum(len(v) for v in P.POOL.values())

    ws2["A1"] = "诊断文案池 · 进度"
    ws2["A1"].font = Font(name="微软雅黑", size=14, bold=True, color="6B4A2F")
    ws2.merge_cells("A1:E1")

    info = [
        ("分支总数（phrases.py 实数的 return 分支）", total_branch),
        ("已进池的分支", done_branch),
        ("已写组数（每组＝现象+理+改）", done_groups),
        ("待写分支", total_branch - done_branch),
        ("待写组数（判断类 ×10、述类 ×4）",
         sum(b * n for _c, b, _d, n in PLAN)),
        ("导出时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]
    r = 3
    for k, v in info:
        ws2.cell(row=r, column=1, value=k).font = FONT
        c = ws2.cell(row=r, column=2, value=v)
        c.font = Font(name="微软雅黑", size=10, bold=True)
        c.alignment = Alignment(horizontal="left")
        r += 1

    r += 1
    ws2.cell(row=r, column=1, value="已完成").font = FONT_H
    r += 1
    for key in P.POOL:
        card, cond = BRANCH.get(key, ("待补", key))
        ws2.cell(row=r, column=1, value=card).font = FONT
        ws2.cell(row=r, column=2, value=key).font = FONT
        ws2.cell(row=r, column=3, value=cond).font = FONT
        ws2.cell(row=r, column=4, value="%d 组" % len(P.POOL[key])).font = FONT
        r += 1

    r += 1
    hdr = ["卡片", "待写分支数", "分支明细", "每支组数", "小计"]
    for ci, h in enumerate(hdr, 1):
        c = ws2.cell(row=r, column=ci, value=h)
        c.font, c.fill, c.border = FONT_H, HEAD_FILL, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center")
    r += 1
    for card, n, detail, per in PLAN:
        for ci, v in enumerate([card, n, detail, per, n * per], 1):
            c = ws2.cell(row=r, column=ci, value=v)
            c.font, c.border = FONT, BORDER
            c.alignment = WRAP if ci == 3 else CENTER
        r += 1

    for col, w in zip("ABCDE", (30, 16, 62, 12, 10)):
        ws2.column_dimensions[col].width = w

    # ---------------- 说明
    ws3 = wb.create_sheet("怎么用")
    notes = [
        "这个文件是什么",
        "  桌面风水程序里「分条评价」的文案池。每条卡片分「现象 / 理 / 改」三段，",
        "  每个分支现在有 10 组同义说法，每次分析随机抽一组——所以同一张桌面重开一次，说法会变。",
        "",
        "怎么看",
        "  · F/G/H 列是模板原文（带 {total} 这类占位符）；I/J/K 列淡底，是按该分支条件",
        "    填好数字的成品——看文案质量看这三列就行。",
        "  · 同一分支连着 10 行（E 列组号 1–10），这 10 行是同一句话的 10 种写法。",
        "  · 「进度与计划」：界面上会出现的分支共 66 个——判断 34 ×10 组、述 32 ×4 组，"
        "全部写完。",
        "    注 1：旧「聚散」三个函数的 7 个分支是死代码（聚散早已并入「形态」），不计入。",
        "    注 2：述类另有 3 支返回空值、不出卡片（成墙与孤岛都无／三才全零／局之总象兜底），",
        "          所以 35 个述类分支里只写了 32 支。",
        "",
        "改文案怎么改",
        "  改 app/phrases_pool.py 里对应的那几行即可，改完重开程序就生效；",
        "  可用的占位符只有这些：",
        "    {total} 图标总数   {n} 本宫图标数   {names} 图标名（已含「」）",
        "    {first} 第一个图标名   {target} 建议移去的宫   {gua} 本宫卦名",
        "    {avg} 全盘均值   {ratio} 倍数   {move_n} 建议移动个数",
        "    四象另有：{nl} 左侧个数   {nr} 右侧个数   {diff} 左右差   {sample} 右侧样例图标名",
        "    形态另有：{occupied} 占用宫数   {pct} 对齐率   {zone_n} 盘心个数",
        "    杂物/生克：{n} 件数  {cap} 扣分  {kind_word} 类别  {kind_tip} 原理句",
        "              {kind_ad} 动作句  {net_txt} 净气（带正负）  {icon_wx} 图标五行",
        "    偏枯另有：{w} 五行  {w_role} 该行主什么  {w_risk} 过旺后果",
        "              {w_miss_ad} 缺了怎么补  {w_full_ad} 多了怎么减  {share_pct} 占比",
        "              {zone_txt} 盘心状况（一句完整描述）   {empty_n} 空宫数   {ev} 自动拼好的现象句",
        "  两个注意点：",
        "    · {names} 本身已带引号，模板里不要再包一层「」，否则会渲染成「「甲」」。",
        "    · 写 {target} 时前面要带动词或介词（移去/挪到/落到），它只填宫名如「坎宫（北）」。",
    ]
    for i, line in enumerate(notes, 1):
        c = ws3.cell(row=i, column=1, value=line)
        c.font = Font(name="微软雅黑", size=10,
                      bold=(i == 1), color="6B4A2F" if i == 1 else "000000")
    ws3.column_dimensions["A"].width = 110

    out_dir = ROOT / "exports"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / ("文案库_说法池_%s.xlsx"
                     % datetime.datetime.now().strftime("%Y%m%d_%H%M"))
    wb.save(path)
    print("saved", path)
    print("行数 %d ｜ 分支 %d ｜ 组数 %d ｜ 分支总数(phrases) %d"
          % (idx, done_branch, done_groups, total_branch))
    return path


if __name__ == "__main__":
    build()
