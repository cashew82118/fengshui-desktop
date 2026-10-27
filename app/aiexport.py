# -*- coding: utf-8 -*-
"""生成给 AI 的问询文件（阶段十一）

单文件 Markdown，落 `exports/AI问询_YYYYMMDD_HHMM.md`。只读数据、**零网络请求**。

隐私：图标名默认不写入（替换为「图标01」…），勾选「含图标文件名」才用真名。
诊断文案里本来会引用图标名，不含文件名时**一并替换**——否则等于没关。

内容分八块：头部／命主／桌面概况／图标明细／当前评分／诊断／推演／规则说明。
「规则说明」是重点：把七项口径、九宫映射、五行归属写清楚，避免 AI 自造风水表。
"""
from __future__ import annotations

import datetime
from pathlib import Path

import fengshui
import mingua
import palace
import project
import software
import paths

ROOT = paths.BASE
OUT_DIR = paths.EXPORTS

KIND_TEXT = {"file": "快捷方式/文件", "dir": "文件夹", "virtual": "系统项"}

# 七项口径（与 fengshui.py 的实现一致；改算法要改这里）
# 2026-10-27：六项风水压到 80 分，另加「顺手」20 分（不是风水项，算鼠标行程与分类）。
SECTION_RULES = (
    ("center", "中宫", 12, "九宫正中宜空。空着满分；每放一个图标扣 4 分。"),
    ("hall", "明堂", 12, "正前方那一格（朱雀位）宜开阔。8 个以内不扣，超过后每个 1.2 分、最多扣 5 分。"
                         "**顶部放常用软件属正常习惯，不要当作硬伤劝改。**"),
    ("sides", "四象", 12, "左右两侧的分布。**不按数量多少扣分**（左多右多都不罚），"
                          "只有两侧全空时扣 6 分。"),
    ("spread", "形态", 12, "外圈贴边、内圈留白、行内对齐、重心落位；这张盘「周不周、正不正」。"),
    ("clutter", "杂物", 16, "安装包、临时文件、重复/无名图标等按数量与面积扣分，最多扣 10 分。"),
    ("wuxing", "生克", 16, "每个图标五行与该宫五行的生克净值累加（生入/比和加分，克入/泄气减分）。"),
    ("comfort", "顺手", 20, "**这一项不是风水**：算鼠标行程与分类。常用软件在三边（顶行、左右两列）"
                             "加分，归档物（安装包/压缩包/种子）压底边加分，同类聚成块加分；"
                             "正中一格堆图标、某一宫挤过 12 个扣分。起算 8 分。"),
)


def _alias(n: int) -> str:
    return "图标%02d" % n


def _name_map(layout: dict) -> dict[str, str]:
    """真名 → 别名（按名字长度倒序替换，避免短名把长名切断）。

    只收 2 字及以上的名字：单字图标名（如「单」）会命中正文里的常用字
    （「清单」「单独」），无脑替换等于把文章改坏——实测踩过。
    单字名在明细表里本来也显示为编号，不会泄漏。
    """
    pairs = {it["name"]: _alias(i + 1)
             for i, it in enumerate(layout.get("icons", []))
             if len(it.get("name") or "") >= 2}
    return dict(sorted(pairs.items(), key=lambda kv: -len(kv[0])))


def _scrub(text: str, mapping: dict[str, str]) -> str:
    for real, alias in mapping.items():
        if real and real in text:
            text = text.replace(real, alias)
    return text


def _cell_label(grid, r: int, c: int) -> str:
    info = grid[r][c]
    return "%s宫（%s）" % (info["gua"], info["dir"]) if info else "中宫"


def build(result: dict, layout: dict, owner: dict | None = None,
          top_dir: int = 180, orient_text: str = "",
          include_names: bool = False, include_diag: bool = False,
          note: str = "") -> str:
    """把一次分析拼成 Markdown。纯函数：不写盘、不联网。"""
    now = datetime.datetime.now()
    grid = palace.palace_grid(top_dir)
    mapping = _name_map(layout)
    st = result["stats"]

    def nm(it: dict, idx: int) -> str:
        if include_names:
            return it.get("name") or _alias(idx)
        return mapping.get(it.get("name", ""), _alias(idx))

    def scrub(t: str) -> str:
        return _scrub(str(t), mapping)

    L: list[str] = []
    L.append("# 桌面风水 · AI 问询包")
    L.append("")
    L.append("- 导出时间：%s" % now.strftime("%Y-%m-%d %H:%M"))
    L.append("- 生成程序：桌面风水分析器（本地离线，全程未联网）")
    L.append("- **隐私提醒**：本文件含我的出生信息%s，请勿公开发布。"
             % ("与桌面图标名称" if include_names else ""))
    if note.strip():
        L.append("- 补充背景：%s" % note.strip())
    L.append("")

    # ---------------- 命主
    L.append("## 一、命主")
    L.append("")
    if owner:
        L.append("- 出生：%04d-%02d-%02d · %s%s"
                 % (owner["year"], owner["month"], owner["day"], owner["gender"],
                    "（立春前，按 %d 年计）" % owner["y_eff"] if owner["shifted"] else ""))
        L.append("- 年柱：%s ｜ 纳音：%s（%s）"
                 % (owner["ganzhi"], owner["nayin"], owner["nayin_wuxing"]))
        L.append("- 命卦：%s命（%s）" % (owner["gua"], owner["group"]))
        L.append("- 四吉方：" + "；".join(
            "%s %s宫（%s）" % (s, g, d) for s, g, d in owner["good"]))
        L.append("- 四凶方：" + "；".join(
            "%s %s宫（%s）" % (s, g, d) for s, g, d in owner["bad"]))
        L.append("- 本命文昌：%s宫（%s）" % (owner["wenchang_gua"],
                                            owner["wenchang_dir"]))
    else:
        L.append("- 本次未提供生辰：命主相关内容（命卦、四吉四凶、文昌、纳音）不适用，"
                 "涉及「我个人取向」的问题请直接说明无法判断。")
    L.append("")

    # ---------------- 桌面概况
    L.append("## 二、桌面概况")
    L.append("")
    empty_n = len(st["empty"]) if isinstance(st["empty"], (list, dict)) \
        else int(st["empty"])
    L.append("- 画布：%d×%d ｜ 图标总数：%d ｜ 已占用宫位：%d ｜ 空宫：%d"
             % (layout["canvas"][0], layout["canvas"][1], st["total"],
                st["occupied"], empty_n))
    L.append("- 朝向：上方朝%s（%d°）" % (orient_text or "—", top_dir))
    L.append("- 五行分布：" + " ｜ ".join(
        "%s %d" % (k, v) for k, v in st["dist"].items() if v))
    L.append("")
    L.append("| 宫位 | 方位 | 图标数 | 五行净值 |")
    L.append("|---|---|---|---|")
    cells = {(p["row"], p["col"]): p for p in st["palace_detail"]}
    for r in range(3):
        for c in range(3):
            info = grid[r][c]
            if info is None:
                p = cells.get((r, c), {"count": st["center"], "net": 0})
                L.append("| 中宫 | 中央 | %d | — |" % p["count"])
            else:
                p = cells.get((r, c), {"count": 0, "net": 0})
                L.append("| %s | %s | %d | %+.1f |"
                         % (info["gua"], info["dir"], p["count"], p["net"]))
    L.append("")

    # ---------------- 图标明细
    L.append("## 三、图标明细")
    L.append("")
    if include_names:
        L.append("（已按你的勾选包含真实图标名）")
    else:
        L.append("（为保护隐私，图标名已替换为编号；名称不影响判断）")
    L.append("")
    L.append("| # | 名称 | 五行 | 所在宫 | 类型 | 归类依据 |")
    L.append("|---|---|---|---|---|---|")
    for i, it in enumerate(layout.get("icons", [])):
        r, c = it["row"], it["col"]
        where = (_cell_label(grid, r, c) if grid[r][c] else "中宫")
        L.append("| %d | %s | %s | %s | %s | %s |"
                 % (i + 1, nm(it, i + 1), it.get("wuxing", "—"), where,
                    KIND_TEXT.get(it.get("kind", ""), it.get("kind", "")),
                    scrub(it.get("wuxing_note", "") or "—")))
    L.append("")

    # ---------------- 评分
    L.append("## 四、当前评分")
    L.append("")
    L.append("- 总分：**%d / 100** ｜ %s" % (result["score"], result["grade"]))
    L.append("- 一句话：%s" % scrub(result.get("summary", "")))
    L.append("- 扣分合计：%.1f" % result.get("deduct_total", 0))
    L.append("")
    L.append("| 项 | 得分 | 满分 | 口径 |")
    L.append("|---|---|---|---|")
    by_key = {k: (name, mx, rule) for k, name, mx, rule in SECTION_RULES}
    for key, sec in result["sections"].items():
        name, mx, rule = by_key.get(key, (sec.get("name", key),
                                          sec.get("max", 0), ""))
        L.append("| %s | %.1f | %d | %s |"
                 % (name, sec.get("score", 0), sec.get("max", mx), rule))
    L.append("")

    # ---------------- 诊断
    L.append("## 五、诊断")
    L.append("")
    diags = result.get("diagnoses", [])
    picked = diags if include_diag else diags[:5]
    if not include_diag and len(diags) > len(picked):
        L.append("（只列前 %d 条；完整 %d 条见「含完整诊断」勾选后的版本）"
                 % (len(picked), len(diags)))
        L.append("")
    for d in picked:
        L.append("### %s ｜ %s ｜ 扣 %d 分" % (d["key"], d["level"], d["deduct"]))
        L.append("")
        L.append("- 现象：%s" % scrub(d["evidence"]))
        L.append("- 理：%s" % scrub(d["principle"]))
        L.append("- 改：%s" % scrub(d["advice"]))
        L.append("")

    # ---------------- 推演
    L.append("## 六、推演（只算不改，桌面没被动过）")
    L.append("")
    try:
        p_layout, p_moves = project.project(layout, top_dir)
        p_score = fengshui.analyze(p_layout, top_dir)["score"]
        L.append("- 最小调整：移 %d 个 → %d 分（现状 %d）"
                 % (len(p_moves), p_score, result["score"]))
        if p_moves:
            L.append("")
            L.append("| 图标 | 从 | 到 | 缘由 |")
            L.append("|---|---|---|---|")
            for mv in p_moves[:12]:
                L.append("| %s | %s | %s | %s |"
                         % (mv["name"] if include_names else
                            mapping.get(mv["name"], "图标"),
                            _cell_label(grid, *mv["from"]),
                            _cell_label(grid, *mv["to"]), mv.get("why", "")))
            if len(p_moves) > 12:
                L.append("")
                L.append("（其余 %d 个略）" % (len(p_moves) - 12))
    except Exception as exc:                       # 纯计算，失败不该毁掉整份文件
        L.append("- 推演计算失败：%s" % exc)
    wc = owner["wenchang_gua"] if owner else "巽"
    ck = owner["good"][0][1] if owner else "乾"
    L.append("")
    L.append("- 优先文昌落点：%s —— 把文书、笔记、学习类集中过去" % wc)
    L.append("- 优先财库落点：%s —— 把工具、管理、生产力类集中过去" % ck)
    if not owner:
        L.append("- （未填生辰：文昌用巽宫总位、财库用乾宫；填了生辰会换成本命的）")
    L.append("")

    # ---------------- 规则说明
    L.append("## 七、规则说明（请按这套读，不要另造风水表）")
    L.append("")
    L.append("### 7.1 七项评分")
    L.append("")
    for _k, name, mx, rule in SECTION_RULES:
        L.append("- **%s（满分 %d）**：%s" % (name, mx, rule))
    L.append("")
    L.append("### 7.2 九宫方位映射（按本盘朝向）")
    L.append("")
    L.append("| 屏幕位置 | 宫位 | 方位 |")
    L.append("|---|---|---|")
    pos = (("左上", 0, 0), ("上中", 0, 1), ("右上", 0, 2),
           ("左中", 1, 0), ("正中", 1, 1), ("右中", 1, 2),
           ("左下", 2, 0), ("下中", 2, 1), ("右下", 2, 2))
    for label, r, c in pos:
        info = grid[r][c]
        L.append("| %s | %s | %s |"
                 % (label, info["gua"] if info else "中宫",
                    info["dir"] if info else "中央"))
    L.append("")
    L.append("### 7.3 五行归属怎么来的")
    L.append("")
    L.append("- 顺序：系统项白名单 → 安装包判定 → 文件夹 → 软件名录（%d 条）→ "
             "语义词典 → 扩展名 → 兜底为金。" % software.TOTAL)
    L.append("- 颜色/强度只影响权重，不改变五行归属；用户自定义覆盖优先于以上全部。")
    L.append("- 五行含义：木＝文字/代码/知识/生长，火＝显象/娱乐/声光，"
             "土＝承载/存储/中介，金＝器物/工具/决断，水＝流动/沟通/通达。")
    L.append("")
    L.append("### 7.4 边界")
    L.append("")
    L.append("- 这套评分是**启发式**，用来比较布局改进，不是命理定论，也不预测现实结果。")
    L.append("- 文件中没有的历法、星宿、流日信息，一律视为不存在；被问到就说不知道。")
    L.append("")

    return "\n".join(L)


def write(text: str) -> Path:
    """写进 exports/，返回路径。文件名带时间戳，不覆盖旧文件。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = "AI问询_%s.md" % datetime.datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / name
    n = 2
    while path.exists():
        path = OUT_DIR / ("AI问询_%s_%d.md"
                          % (datetime.datetime.now().strftime("%Y%m%d_%H%M"), n))
        n += 1
    path.write_text(text, encoding="utf-8")
    return path
