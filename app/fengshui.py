# -*- coding: utf-8 -*-
"""形法诊断与评分引擎（阶段三）

六项评分（合计 100）：
    中宫 15 ｜ 明堂 15 ｜ 四象左右 15 ｜ 聚散秩序 15 ｜ 杂物煞 20 ｜ 五行生克 20

计分铁律：每项按"扣分"计。**总分 = 100 − 各项扣分之和**，明细必须能与总分对账。
每条诊断四要素齐全：现象(evidence) / 原理(principle) / 改法(advice) / 分数(deduct)。
本模块为纯函数：输入 layout dict，输出结果 dict，不碰系统、不碰 GUI。
"""
from __future__ import annotations

import classify
import phrases
from palace import palace_at, palace_grid
import paths

POS_LABEL = {
    (0, 0): "左上", (0, 1): "上中", (0, 2): "右上",
    (1, 0): "左中", (1, 1): "正中", (1, 2): "右中",
    (2, 0): "左下", (2, 1): "下中", (2, 2): "右下",
}

LEVEL_ORDER = {"忌": 0, "平": 1, "吉": 2, "述": 3}

GRADES = [
    (90, "上吉 · 气局周流"),
    (75, "中吉 · 小有壅滞"),
    (60, "平 · 可用待理"),
    (45, "小滞 · 宜作调整"),
    (0, "滞 · 当移当清"),
]


# ---------------------------------------------------------------- 生克

def relation(icon_wx: str, palace_wx: str) -> tuple[str, float]:
    """图标五行 对 宫位五行 的作用。返回 (关系名, 权重)。"""
    if icon_wx == palace_wx:
        return "比和", 0.0
    if classify.SHENG[icon_wx] == palace_wx:
        return "生入", 0.6
    if classify.KE[icon_wx] == palace_wx:
        return "克入", -1.0
    if classify.SHENG[palace_wx] == icon_wx:
        return "泄气", -0.7
    return "主克客", -0.4


def _full_name(grid, row: int, col: int) -> str:
    info = palace_at(grid, row, col)
    return "%s宫（%s·%s）" % (info["gua"], POS_LABEL[(row, col)], info["wuxing"])


def pick_target(icon: dict, grid, counts: dict) -> str:
    """为图标挑落脚宫：空宫优先，以"生入"为佳，靠下方略优。"""
    best = None
    best_key = None
    for r in range(3):
        for c in range(3):
            if counts[(r, c)] > 0:
                continue
            if (r, c) == (1, 1):
                continue          # 中宫必须留空，绝不往这里建议
            info = palace_at(grid, r, c)
            _, w = relation(icon.get("wuxing", "金"), info["wuxing"])
            key = (-w, -r, c)
            if best_key is None or key < best_key:
                best_key = key
                best = (r, c)
    if best is None:
        return "（盘上已无空宫，宜先清减）"
    return _full_name(grid, best[0], best[1])


def _level(score: float, mx: float) -> str:
    r = (score / mx) if mx else 1.0
    if r >= 0.8:
        return "吉"
    return "平" if r >= 0.5 else "忌"


def _dominant(rel: dict) -> str:
    """该宫以哪种相碍关系为主——决定文案说理与举例。"""
    if rel["克入"] and rel["克入"] >= max(rel["泄气"], rel["主克客"]):
        return "克入"
    if rel["泄气"] and rel["泄气"] >= max(rel["克入"], rel["主克客"]):
        return "泄气"
    if rel["主克客"]:
        return "主克客"
    return "mixed"


def _diag(key, level, deduct, score, mx, evidence, principle, advice,
          palace=None, icons=None) -> dict:
    return {"key": key, "level": level, "deduct": round(deduct, 1),
            "score": round(score, 1), "max": mx,
            "evidence": evidence, "principle": principle, "advice": advice,
            "palace": palace, "icons": icons or []}


def _info(key, evidence, principle, advice) -> dict:
    """不参与计分的补充说明。"""
    return {"key": key, "level": "述", "deduct": 0, "score": 0, "max": 0,
            "evidence": evidence, "principle": principle, "advice": advice,
            "palace": None, "icons": []}


# ---------------------------------------------------------------- 主分析

# ---------------------------------------------------------------- 顺手度
# 2026-10-27 新增：风水六项压到 80 分后，另外 20 分专门算「顺不顺手」。
#
# 这套是经验规则，不是玄学，也不假装是科学。目的只有一个：
# 别把「顶上放常用软件」「左边堆一片」这种手顺的摆法判成错。
# 所以它故意不看吉凶方位，只看鼠标行程与分类。

ARCHIVE_EXT = {"exe", "msi", "zip", "rar", "7z", "iso", "torrent", "part",
               "tmp", "apk", "dmg", "cab", "gz"}

COMFORT_MAX = 20


def _is_archive(icon: dict, clutter_names: set) -> bool:
    """归档物：清洁单上点了名的，或安装包／压缩包／种子这类「下完就该挪走」的。"""
    if icon["name"] in clutter_names:
        return True
    ext = (icon.get("ext") or "").lower().lstrip(".")
    return ext in ARCHIVE_EXT


def _in_hot_zone(rc: tuple) -> bool:
    """热区＝贴手的三边：顶行三格 + 左中 + 右中。

    四角归冷区：虽然也贴边，但行程最长，而且多数人是右手握鼠标、
    左上角是「我的电脑」习惯位，四角放归档物更合理。
    """
    r, c = rc
    return r == 0 or (r == 1 and c in (0, 2))


def _in_cold_zone(rc: tuple) -> bool:
    """冷区＝底行三格（含两个下角）。"""
    return rc[0] == 2


def comfort(icons: list[dict], cells: dict, counts: dict,
            clutter: list[dict]) -> dict:
    """顺手度 0–20。起算 8，加最多 15、扣最多 8。

    起算值定 8 而不是 12：实测三边热区（5 格）能装下大半图标，
    普通桌面 hot_ratio 就有 0.85，起算 12 会让这一项恒满 20 分、失去区分度。
    """
    total = len(icons)
    base = 8.0
    names = {c["name"] for c in clutter}
    archive = [i for i in icons if _is_archive(i, names)]
    common = [i for i in icons if not _is_archive(i, names)]

    # 1) 常用在热区（最多 +6）：八成常用物在三边即满分
    hot_n = sum(1 for i in common if _in_hot_zone((i["row"], i["col"])))
    hot_ratio = hot_n / len(common) if common else 0.0
    if len(common) < 3:
        s_hot = 3.0                    # 常用物太少，谈不上布局，给中位
    else:
        s_hot = 6.0 * min(1.0, hot_ratio / 0.8)

    # 2) 归档在冷区（最多 +4）：没有归档物＝满分（没得可收拾）
    cold_n = sum(1 for i in archive if _in_cold_zone((i["row"], i["col"])))
    cold_ratio = cold_n / len(archive) if archive else 0.0
    s_cold = 4.0 if not archive else 4.0 * min(1.0, cold_ratio / 0.6)

    # 3) 聚成团（最多 +5）：同一宫里同 kind + 同扩展名 ≥3 个算一块
    cover = 0
    for items in cells.values():
        grp: dict[tuple, int] = {}
        for it in items:
            k = (it["kind"], (it.get("ext") or "").lower())
            grp[k] = grp.get(k, 0) + 1
        cover += sum(v for v in grp.values() if v >= 3)
    cluster_ratio = cover / total if total else 0.0
    s_cluster = 5.0 * min(1.0, cluster_ratio / 0.35)

    # 4) 中宫别堵（最多 −5）
    center_n = len(cells.get((1, 1), []))
    d_center = min(5.0, 2.0 * center_n)

    # 5) 别塞太满（最多 −3）：最挤那一宫超过 12 个开始扣
    busiest = max(counts.values()) if counts else 0
    d_crowd = min(3.0, max(0.0, float(busiest - 12)))

    score = base + s_hot + s_cold + s_cluster - d_center - d_crowd
    score = round(max(0.0, min(float(COMFORT_MAX), score)), 1)
    return {
        "score": score,
        "subs": {"hot": round(s_hot, 1), "cold": round(s_cold, 1),
                 "cluster": round(s_cluster, 1),
                 "center": -round(d_center, 1), "crowd": -round(d_crowd, 1)},
        "stats": {
            "hot_n": hot_n, "hot_ratio": round(hot_ratio, 3),
            "cold_n": cold_n, "cold_ratio": round(cold_ratio, 3),
            "archive": len(archive), "common": len(common),
            "cover": cover, "cluster_ratio": round(cluster_ratio, 3),
            "center_n": center_n, "busiest": busiest,
        },
    }


def analyze(layout: dict, top_dir: int = 180) -> dict:
    icons = layout["icons"]
    grid = palace_grid(top_dir)
    dist = classify.apply_wuxing(layout)
    zero_w = [w for w in classify.WUXING_ORDER if dist[w] == 0]

    cells = {(r, c): [] for r in range(3) for c in range(3)}
    for it in icons:
        cells[(it["row"], it["col"])].append(it)
    counts = {k: len(v) for k, v in cells.items()}
    total = len(icons)

    diags: list[dict] = []
    sections: dict[str, dict] = {}

    def _record(key, section_name, mx, d):
        sections[key] = {"name": section_name,
                         "score": round(mx - d["deduct"], 1), "max": mx}
        diags.append(d)

    # ---------- 1. 中宫 ----------
    center = cells[(1, 1)]
    if not center:
        ev, pr, ad = phrases.center_empty(total)
        _record("center", "中宫", 12, _diag(
            "中宫空", "吉", 0, 12, 12, ev, pr, ad, palace="中"))
    else:
        d = min(12, 4 * len(center))
        names = "、".join("「%s」" % i["name"] for i in center[:4])
        ev, pr, ad = phrases.center_press(
            len(center), names, center[0]["name"],
            pick_target(center[0], grid, counts))
        _record("center", "中宫", 12, _diag(
            "中宫受压", _level(12 - d, 12), d, 12 - d, 12, ev, pr, ad,
            palace="中"))

    # ---------- 2. 明堂（上方中间，朱雀位） ----------
    hall = cells[(0, 1)]
    n_hall = len(hall)
    hall_gua = palace_at(grid, 0, 1)
    avg = total / 9.0
    # 2026-10-27 放宽：原先"超过 4 个就扣、每多一个 2 分、最多 15"，
    # 等于把「顶上放常用软件」这种顺手习惯判成硬伤。现在 8 个以内不扣，
    # 超过后每个 1.2 分、最多 5 分——明堂不再是杀器，只做提醒。
    d = min(5, max(0, (n_hall - 8) * 1.2))
    if d > 0:
        ev, pr, ad = phrases.hall_block(
            n_hall, hall_gua["gua"], avg, n_hall / max(avg, 0.1), n_hall - 4,
            hall[0]["name"], pick_target(hall[-1], grid, counts))
        _record("hall", "明堂", 12, _diag(
            "明堂壅塞", _level(12 - d, 12), d, 12 - d, 12, ev, pr, ad,
            palace=hall_gua["gua"]))
    else:
        ev, pr, ad = phrases.hall_open(hall_gua["gua"], n_hall)
        _record("hall", "明堂", 12, _diag(
            "明堂开阔", "吉", 0, 12, 12, ev, pr, ad, palace=hall_gua["gua"]))

    # ---------- 3. 四象左右 ----------
    left = [i for i in icons if i["cx"] < 1 / 3]
    right = [i for i in icons if i["cx"] >= 2 / 3]
    n_l, n_r = len(left), len(right)
    # 2026-10-27：**取消按左右数量扣分**。原来「右边比左边多就判白虎抬头、
    # 最多扣 15」，本质是拿传统规矩套个人习惯（左手党、任务栏位置都会影响），
    # 与「顺手」直接冲突。现在只有「两侧全空」算硬伤，其余都只作说明、不计分。
    #
    # 文案也不再走说法池：池子里那批句子的语气是「这是毛病」，
    # 既然不扣分了，再那样说就自相矛盾。这里改成中性描述，把判断权交回用户。
    ratio = n_l / max(1, n_r)
    if n_l == 0 and n_r == 0:
        d, key, level = 6, "左右皆空", "平"
        ev, pr, ad = phrases.sides_both_empty(total)
    else:
        d = 0
        if ratio >= 2:
            key, level = "青龙为主", "述"
        elif ratio <= 0.5:
            key, level = "白虎稍盛", "述"
        else:
            key, level = "左右均衡", "吉"
        ev = "左侧（青龙）%d 个，右侧（白虎）%d 个，左:右 ≈ %.1f:1" % (
            n_l, n_r, max(ratio, 1 / ratio))
        pr = ("左右哪边多，多半取决于你惯用哪只手、任务栏放在哪边，不是对错问题。"
              "形法讲「左青龙右白虎」，但那是给院落立向用的，方寸之间不必套死。")
        ad = ("这一项只作说明、不扣分。真要动，把最常用的放在你起手最快的那一边即可。")
    _record("sides", "四象", 12, _diag(
        key, level, d, 12 - d, 12, ev, pr, ad))

    # ---------- 4. 形态（对齐／周流／贴边／中轴／重心） ----------
    cw, ch = layout["cell"]
    W, H = layout["canvas"]
    base_x = min(i["x"] for i in icons) if icons else 0
    base_y = min(i["y"] for i in icons) if icons else 0
    aligned = sum(1 for i in icons
                  if cw and ch and (i["x"] - base_x) % cw == 0
                  and (i["y"] - base_y) % ch == 0)
    align_ratio = aligned / total if total else 0
    occupied = sum(1 for v in counts.values() if v > 0)
    # 中宫不列入"空宫"：它本就宜空
    empty_cells = [_full_name(grid, r, c)
                   for r in range(3) for c in range(3)
                   if counts[(r, c)] == 0 and (r, c) != (1, 1)]

    # 中庭留白：盘心一带压了多少图标。**越少越好**——
    # 「外实内虚」才顺手：四周有落处，中间空出来露壁纸。
    # （原来用"贴边"做这一项，等于把贴边当缺点扣分，与"四周贴边、
    #   中间留白"的习惯相反，2026-10-24 按用户反馈改掉。）
    zone_n = sum(1 for i in icons
                 if 0.30 <= i["cx"] <= 0.70 and 0.30 <= i["cy"] <= 0.70)
    zone_ratio = zone_n / total if total else 0.0

    half_x = (cw / 2.0) / W if W else 0.0
    half_y = (ch / 2.0) / H if H else 0.0
    axis_n = sum(1 for i in icons if 0.46 <= i["cx"] <= 0.54)
    # 贴边率仍统计，但只作说明、不参与评分
    edge_n = sum(1 for i in icons
                 if i["cx"] <= half_x or i["cx"] >= 1 - half_x
                 or i["cy"] <= half_y or i["cy"] >= 1 - half_y)
    edge_ratio = edge_n / total if total else 0.0

    gx = sum(i["cx"] for i in icons) / total if total else 0.5
    gy = sum(i["cy"] for i in icons) / total if total else 0.5
    off = ((gx - 0.5) ** 2 + (gy - 0.5) ** 2) ** 0.5

    subs = {
        "align": (0.45, align_ratio),
        # 周流：占满 6 宫即满分。不能按 9 宫算——那等于奖励"摊到每个宫"，
        # 与"顺手"相悖，推演会被逼着把图标撒到右下角（2026-10-24 修正）
        "flow": (0.30, min(1.0, occupied / 6.0)),
        # 中庭：盘心 40% 见方区域内不超过 25% 的图标即满分
        "zone": (0.25, max(0.0, 1.0 - zone_ratio / 0.25)),
    }
    sub_deduct = {k: 12 * w * (1 - s) for k, (w, s) in subs.items()}
    worst_sub = max(sub_deduct, key=lambda k: sub_deduct[k])
    score4 = round(12 - sum(sub_deduct.values()), 1)
    d4 = round(12 - score4, 1)

    ratio4 = score4 / 12.0
    if ratio4 >= 0.9:
        k4 = "形态得宜"
        ev4, pr4, ad4 = phrases.form_good(align_ratio, occupied, zone_n, total)
    elif ratio4 >= 0.8:
        k4 = "形态小瑕"
        ev4, pr4, ad4 = phrases.form_mild(align_ratio, occupied, zone_n,
                                          total, worst_sub)
    else:
        k4 = {"zone": "中庭受压", "align": "排列散乱"}.get(worst_sub, "气不周流")
        ev4, pr4, ad4 = phrases.form(align_ratio, occupied, zone_n, total,
                                     worst_sub)
    _record("spread", "形态", 12, _diag(
        k4, _level(score4, 12), d4, score4, 12, ev4, pr4, ad4))

    # ---------- 5. 杂物煞 ----------
    clutter = classify.clutter_items(icons)
    w5 = min(classify.CLUTTER_CAP, sum(c["weight"] for c in clutter))
    if clutter:
        top = sorted(clutter, key=lambda c: -c["weight"])
        detail = ["%s（%s）" % (c["name"], c["reason"]) for c in top]
        ev5, pr5, ad5 = phrases.clutter_dirty(
            len(clutter), classify.clutter_kind(clutter), detail, w5)
        _record("clutter", "杂物", 16, _diag(
            "杂物压盘", _level(16 - w5, 16), w5, 16 - w5, 16, ev5, pr5, ad5,
            icons=[c["name"] for c in top]))
    else:
        ev5, pr5, ad5 = phrases.clutter_clean()
        _record("clutter", "杂物", 16, _diag(
            "盘面洁净", "吉", 0, 16, 16, ev5, pr5, ad5))

    # ---------- 6. 五行生克 ----------
    net = 0.0
    rel_stat = {"生入": 0, "比和": 0, "克入": 0, "泄气": 0, "主克客": 0}
    palace_detail = []
    for (r, c), items in cells.items():
        if not items:
            continue
        info = palace_at(grid, r, c)
        local = {"生入": 0, "比和": 0, "克入": 0, "泄气": 0, "主克客": 0}
        net_local = 0.0
        for it in items:
            rl, w = relation(it["wuxing"], info["wuxing"])
            local[rl] += 1
            rel_stat[rl] += 1
            net_local += w
            net += w
        palace_detail.append({
            "row": r, "col": c, "gua": info["gua"], "wuxing": info["wuxing"],
            "count": len(items), "net": round(net_local, 2), "rel": local,
            "icons": items,
        })
    pen_ratio = max(0.0, -net) / max(1, total)
    score6 = round(16 * (1 - min(1.0, pen_ratio)), 1)
    d6 = round(16 - score6, 1)
    worst = sorted([p for p in palace_detail if p["net"] < 0],
                   key=lambda p: p["net"])[:2]
    if worst:
        first = worst[0]
        gw = first["wuxing"]
        kind = _dominant(first["rel"])
        rule = {
            "克入": lambda it: classify.KE.get(it["wuxing"]) == gw,
            "泄气": lambda it: classify.SHENG.get(gw) == it["wuxing"],
            "主克客": lambda it: classify.KE.get(gw) == it["wuxing"],
        }.get(kind)
        cands = [i for i in first["icons"] if rule(i)] if rule else []
        if not cands:
            cands = first["icons"]
        wi = min(cands, key=lambda i: relation(i["wuxing"], gw)[1])
        bad = (first["rel"]["克入"] + first["rel"]["泄气"]
               + first["rel"]["主克客"])
        ev6, pr6, ad6 = phrases.wuxing_block(
            first["gua"], gw, first["count"], bad, first["net"], kind,
            first["count"], [i["name"] for i in cands], cands[0]["wuxing"])
        ad6 += " 具体说：把「%s」（%s）挪到%s。" % (
            wi["name"], wi["wuxing"], pick_target(wi, grid, counts))
        _record("wuxing", "生克", 16, _diag(
            "五行相碍", _level(score6, 16), d6, score6, 16, ev6, pr6, ad6,
            palace=first["gua"]))
    else:
        ev6, pr6, ad6 = phrases.wuxing_ok(net)
        _record("wuxing", "生克", 16, _diag(
            "五行相安", "吉", 0, 16, 16, ev6, pr6, ad6))

    # ---------- 7. 顺手度 ----------
    cf = comfort(icons, cells, counts, clutter)
    ev7, pr7, ad7, k7, lv7 = phrases.comfort(cf)
    _record("comfort", "顺手", COMFORT_MAX, _diag(
        k7, lv7, round(COMFORT_MAX - cf["score"], 1), cf["score"],
        COMFORT_MAX, ev7, pr7, ad7))

    # ---------- 五行偏枯（补充说明，不计分） ----------
    if total:
        for w in classify.WUXING_ORDER:
            share = dist[w] / total
            if dist[w] == 0:
                ev, pr, ad = phrases.bianque_missing(w, total)
                diags.append(_info("%s气全无" % w, ev, pr, ad))
            elif share >= 0.40:
                ev, pr, ad = phrases.bianque_full(w, dist[w], share)
                diags.append(_info("%s气过旺" % w, ev, pr, ad))

    # ---------- 补充观察：新维度，不计分但计入诊断 ----------
    ev, pr, ad = phrases.axis_note(axis_n, total)
    diags.append(_info("中轴观", ev, pr, ad))

    ev, pr, ad = phrases.balance_note(off, gx, gy)
    diags.append(_info("重心观", ev, pr, ad))

    corner_empty = [(r, c) for r, c in ((0, 0), (0, 2), (2, 0), (2, 2))
                    if counts[(r, c)] == 0]
    ev, pr, ad = phrases.corner_note(
        len(corner_empty), [_full_name(grid, r, c) for r, c in corner_empty])
    diags.append(_info("四隅观", ev, pr, ad))

    # ---------- 补充观察其二：宫内疏密／成墙孤岛／三才／器类 ----------
    dens = None
    for (r, c), items in cells.items():
        if len(items) < 4:
            continue
        lxs = [i["cx"] * 3 - c for i in items]
        lys = [i["cy"] * 3 - r for i in items]
        frac = (max(lxs) - min(lxs)) * (max(lys) - min(lys))
        if dens is None or frac < dens[0]:
            dens = (frac, r, c, len(items))

    col_counts: dict[int, int] = {}
    for it in icons:
        k = int((it["x"] - base_x) // cw) if cw else 0
        col_counts[k] = col_counts.get(k, 0) + 1
    keys = sorted(col_counts)
    runs: list[list[int]] = []
    if keys:
        cur = [keys[0]]
        for a, b in zip(keys, keys[1:]):
            if b == a + 1:
                cur.append(b)
            else:
                runs.append(cur)
                cur = [b]
        runs.append(cur)

    wall_desc = ""
    max_k = keys[-1] if keys else 0
    for run in runs:
        if len(run) >= 3 and all(col_counts[k] >= 5 for k in run):
            side = "左" if run[0] <= max_k * 0.35 else (
                "右" if run[0] >= max_k * 0.65 else "中")
            wall_desc = "%s侧有 %d 列连成一道墙，共 %d 个图标" % (
                side, len(run), sum(col_counts[k] for k in run))
            break
    island_runs = [x for x in runs if sum(col_counts[k] for k in x) <= 2]
    island_desc = ""
    if len(island_runs) >= 2:
        island_desc = "另散着 %d 处孤立图标（各一两个，左右不接）" % len(island_runs)

    tian = sum(1 for i in icons if i["cy"] < 1 / 3)
    ren = sum(1 for i in icons if 1 / 3 <= i["cy"] < 2 / 3)
    di = total - tian - ren
    n_file = sum(1 for i in icons if i["kind"] == "file")
    n_dir = sum(1 for i in icons if i["kind"] == "dir")
    n_virtual = sum(1 for i in icons if i["kind"] == "virtual")

    if dens:
        ev, pr, ad = phrases.density_note(
            palace_at(grid, dens[1], dens[2])["gua"], dens[3], dens[0])
        diags.append(_info("宫内疏密", ev, pr, ad))

    ev, pr, ad = phrases.cluster_note(wall_desc, island_desc)
    if ev:
        diags.append(_info("成墙与孤岛", ev, pr, ad))

    ev, pr, ad = phrases.three_bands(tian, ren, di)
    if ev:
        diags.append(_info("三才", ev, pr, ad))

    ev, pr, ad = phrases.kind_mix(n_file, n_dir, n_virtual)
    diags.append(_info("器类构成", ev, pr, ad))

    # ---------- 组合推理：把几条事实合起来看 ----------
    syn_ev, syn_pr = phrases.synthesis(
        not center, n_hall, n_r > n_l, bool(clutter), occupied, zero_w)
    if syn_ev:
        diags.append(_info(
            "局之总象", syn_ev, syn_pr,
            "这一条不是新问题，是把上面几条合起来看的结果；那几条改了，它自会跟着变。"))

    # ---------- 汇总 ----------
    deduct_total = sum(s["max"] - s["score"] for s in sections.values())
    score = max(0, min(100, int(round(100 - deduct_total))))
    grade = next(g for th, g in GRADES if score >= th)

    diags.sort(key=lambda x: (LEVEL_ORDER[x["level"]], -x["deduct"]))
    urgent = [x for x in diags if x["level"] == "忌"][:3]

    return {
        "score": score,
        "grade": grade,
        "summary": _summary(urgent),
        "sections": sections,
        "deduct_total": round(deduct_total, 1),
        "diagnoses": diags,
        "urgent": urgent,
        "stats": {
            "total": total,
            "dist": dist,
            "counts": {"%d,%d" % k: v for k, v in counts.items()},
            "occupied": occupied,
            "empty": empty_cells,
            "left": n_l, "right": n_r,
            "hall": n_hall, "center": len(center),
            "align_ratio": round(align_ratio, 3),
            "edge_n": edge_n, "edge_ratio": round(edge_ratio, 3),
            "zone_n": zone_n, "zone_ratio": round(zone_ratio, 3),
            "axis_n": axis_n, "centroid": [round(gx, 3), round(gy, 3)],
            "offset": round(off, 3),
            "corner_empty": len(corner_empty),
            "tian": tian, "ren": ren, "di": di,
            "n_file": n_file, "n_dir": n_dir, "n_virtual": n_virtual,
            "wall": wall_desc, "islands": len(island_runs),
            "density": (round(dens[0], 3) if dens else None),
            "net": round(net, 2),
            "rel": rel_stat,
            "palace_detail": palace_detail,
            "clutter": [{"name": c["name"], "weight": c["weight"],
                         "reason": c["reason"]} for c in clutter],
            "comfort": cf,
        },
        "orientation": top_dir,
    }


def _summary(urgent: list[dict]) -> str:
    if not urgent:
        return "全局无大碍，气机尚顺。"
    keys = [x["key"] for x in urgent]
    if len(keys) == 1:
        return "最需动手：%s。" % keys[0]
    return "最需动手：%s、%s。" % (keys[0], keys[1])


# ---------------------------------------------------------------- 调试入口

def _print_report(res: dict) -> None:
    print("=" * 76)
    print("总分 %d ｜ %s ｜ %s" % (res["score"], res["grade"], res["summary"]))
    print("对账：100 − 扣分合计 %.1f = %d" % (res["deduct_total"], res["score"]))
    print("=" * 76)
    print("\n[七项评分]")
    for s in res["sections"].values():
        filled = int(round(s["score"] / s["max"] * 20)) if s["max"] else 0
        print("  %-3s %5.1f / %-2d  扣%4.1f  %s%s" % (
            s["name"], s["score"], s["max"], s["max"] - s["score"],
            "█" * filled, "·" * (20 - filled)))

    st = res["stats"]
    print("\n[五行分布] " + "  ".join("%s:%d" % (w, st["dist"][w])
                                     for w in classify.WUXING_ORDER))
    print("[四象] 左(青龙) %d ／ 右(白虎) %d ／ 明堂 %d ／ 中宫 %d"
          % (st["left"], st["right"], st["hall"], st["center"]))
    print("[生克] 生入 %d ／ 比和 %d ／ 克入 %d ／ 泄气 %d ／ 主克客 %d ／ 净气 %.1f"
          % (st["rel"]["生入"], st["rel"]["比和"], st["rel"]["克入"],
             st["rel"]["泄气"], st["rel"]["主克客"], st["net"]))
    print("[空宫] %s" % ("、".join(st["empty"]) or "无"))

    print("\n[各宫生克]")
    for p in sorted(st["palace_detail"], key=lambda x: x["net"]):
        print("  %s宫(%s) %2d个  净气%+.1f  生入%d 比和%d 克入%d 泄气%d 主克客%d"
              % (p["gua"], p["wuxing"], p["count"], p["net"],
                 p["rel"]["生入"], p["rel"]["比和"], p["rel"]["克入"],
                 p["rel"]["泄气"], p["rel"]["主克客"]))

    print("\n[诊断]")
    for x in res["diagnoses"]:
        tag = {"忌": "忌", "平": "平", "吉": "吉", "述": "述"}[x["level"]]
        print("\n  【%s】%s   扣 %.1f（得 %s/%s）"
              % (tag, x["key"], x["deduct"], x["score"], x["max"]))
        print("    现象：%s" % x["evidence"])
        print("    原理：%s" % x["principle"])
        print("    改法：%s" % x["advice"])

    print("\n[每图标五行]")
    for it in res["_icons"]:
        src = classify.SOURCE_LABEL.get(it["wuxing_source"], it["wuxing_source"])
        print("  %-32s %s  ← %s" % (it["name"][:30], it["wuxing"], src))


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    sys.stdout.reconfigure(encoding="utf-8")
    path = paths.DATA / "layout_debug.json"
    if not path.exists():
        print("没有 %s —— 先跑 python desk_reader.py 生成一份" % path)
        raise SystemExit(1)
    layout = json.loads(path.read_text(encoding="utf-8"))
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    result = analyze(layout, top)
    result["_icons"] = layout["icons"]
    _print_report(result)
