# -*- coding: utf-8 -*-
"""整体总评（散文体）

把结构化的诊断结果写成一篇连贯的文章，而不是分块条目。
纯本地生成：按实际数据分支选句，无模板填空感、无联网。

设计原则（见 docs/03-设计规范.md 第 6.2 / 7 节）：
  · 先断，再讲理，最后给法
  · 术语必带白话
  · 不恐吓、不编数据、不承诺现实结果

**口径（2026-10-27 起）**：七项 100 分——中宫 12 / 明堂 12 / 四象 12 / 形态 12 /
杂物 16 / 生克 16 / 顺手 20。三段随之改过：
  · 总起说「七项合参」，并列分项里含顺手（原先写「六项」，漏了顺手 20 分）
  · 明堂按新阈值说话（8 个以内不扣、最多扣 5），5–9 档不再说「已经开始堵」
  · 四象取消左右数量扣分后，文案改中性，老话只作引用、不作判决
  · 新增第 7 段「顺手度」——它占 20 分，且是唯一谈「累不累」的一项，
    只讲步数与归类，不许用气机、旺衰、吉凶这类词

文案一条一条存在 `prose_pool.py`，**每个分支 5 条同义变体**（共 445 条）。
选句按桌面指纹（`prose_pool.seed`）取模，所以同一张盘反复打开看到的是同一版文字，
只有桌面本身变了才可能换一版——这样既有多样性，又不至于每次刷新都换脸。
"""
from __future__ import annotations

import classify
import prose_pool
from palace import ORIENT_CHOICES

_ORIENT = dict(ORIENT_CHOICES)

# 八宫白话——真正的差异化来源：指到哪个宫，说的就是哪个宫的事
PALACE_SAYING = {
    "巽": "巽为风，主消息往来与文昌",
    "离": "离为火，主名声显扬与前途出路",
    "坤": "坤为地，主承载、田土与人事根基",
    "震": "震为雷，主发动、决断与开端",
    "兑": "兑为泽，主口舌、外缘与喜悦",
    "乾": "乾为天，主尊长、权威与主事之位",
    "坎": "坎为水，主智谋，也主险阻",
    "艮": "艮为山，主止、主积蓄与边界",
    "中": "中宫是全局的气枢，主一身之收放",
}

WUXING_SAYING = {
    "木": "木主生发，是开始与成长之气",
    "火": "火主显象，是被看见、也被消耗之气",
    "土": "土主承载，是堆积与沉淀之气",
    "金": "金主决断，是器物与肃杀之气",
    "水": "水主流动，是往来与变通之气",
}

WUXING_NOUN = {
    "金": "器物", "木": "文书", "火": "显象之物", "土": "承载之物", "水": "流动之物",
}

# 该条诊断"关乎什么"——用于总起段的对举，不写死顺序。
# 「顺手」那几条是 2026-10-27 补的：顺手度低时 key 会是「别手」，
# 缺了这几条就会退回默认的「局面的顺逆」，读起来答非所问。
_NATURE = [
    ("顺手", "用起来累不累"),
    ("别手", "用起来累不累"),
    ("尚可", "用起来累不累"),
    ("明堂", "对外的进路"),
    ("杂物", "自身的秩序"),
    ("中宫", "主心与定力"),
    ("五行", "与环境的相处"),
    ("白虎", "人际的分寸"),
    ("青龙", "自身的担当"),
    ("聚散", "起手的分寸"),
    ("排列", "起手的分寸"),
    ("气不周流", "局面的周遍"),
]

# 该条诊断对应的"动作"，用于收束段排优先级
_ACTION = [
    ("顺手", "调顺手位"),
    ("别手", "调顺手位"),
    ("尚可", "调顺手位"),
    ("明堂", "疏明堂"),
    ("杂物", "清杂物"),
    ("中宫", "空出中宫"),
    ("五行", "调宫位"),
    ("白虎", "收白虎"),
    ("青龙", "减青龙"),
    ("聚散", "散一散"),
    ("排列", "对齐网格"),
    ("气不周流", "分散图标"),
    ("左右皆空", "分置左右"),
]

# 主导关系 → 池子里的键尾
_KIND_KEY = {"克入": "keru", "泄气": "xieqi", "主克客": "zhuke", "mixed": "mixed"}

# 主导关系 → 该找哪类图标举例（保证说理与举例一致）
_EXAMPLE_RULE = {
    "克入": lambda icon_wx, gw: classify.KE.get(icon_wx) == gw,
    "泄气": lambda icon_wx, gw: classify.SHENG.get(gw) == icon_wx,
    "主克客": lambda icon_wx, gw: classify.KE.get(gw) == icon_wx,
}


def _q(names: list[str], limit: int = 3) -> str:
    picked = ["「%s」" % n for n in names[:limit]]
    if len(picked) == 1:
        return picked[0]
    if len(picked) == 2:
        return "%s和%s" % (picked[0], picked[1])
    return "%s、%s和%s" % (picked[0], picked[1], picked[2])


def _nature(key: str) -> str:
    for k, v in _NATURE:
        if k in key:
            return v
    return "局面的顺逆"


def _action(key: str) -> str:
    for k, v in _ACTION:
        if k in key:
            return v
    return "动手改一改"


def _clutter_kind(clutter: list[dict]) -> str:
    return classify.clutter_kind(clutter)


def _dominant(rel: dict) -> str:
    if rel["克入"] >= max(rel["泄气"], rel["主克客"]) and rel["克入"]:
        return "克入"
    if rel["泄气"] >= max(rel["克入"], rel["主克客"]) and rel["泄气"]:
        return "泄气"
    if rel["主克客"]:
        return "主克客"
    return "mixed"


def _num(v) -> str:
    """19.0 → "19"，9.5 → "9.5"。分数带小数的场合统一走这里。"""
    return "%g" % round(float(v), 1)


def compose(result: dict) -> list[str]:
    st = result["stats"]
    score = result["score"]
    grade = result["grade"]
    total = st["total"]
    occupied = st["occupied"]
    dist = st["dist"]
    left, right = st["left"], st["right"]
    hall, center = st["hall"], st["center"]
    align = st["align_ratio"]
    top_dir = result.get("orientation", 180)
    orient_txt = _ORIENT.get(top_dir, "上方朝向角 %d°" % top_dir)

    aria = [p for p in st["palace_detail"] if p["count"]]
    worst = sorted(aria, key=lambda p: p["net"])[0] if aria else None
    best = max(aria, key=lambda p: p["net"]) if aria else None
    paras: list[str] = []

    seed = prose_pool.seed(result)

    def pk(key: str, off: int, **kw) -> str:
        """按桌面指纹 + 段偏移取一条变体。

        偏移各不相同，是为了避免各段都取到「第 0 条」——那样读起来像平行句式。
        同一张盘指纹固定，所以每次打开看到的仍是同一版。
        """
        tpl = prose_pool.pick(key, seed + off)
        if not tpl:
            return ""
        try:
            return tpl.format(**kw)
        except (KeyError, IndexError, ValueError):
            return tpl

    # ================= 一、总起 =================
    # 断语阈值与 fengshui.GRADES 对齐（90/75/60/45），免得文案与评级打架
    if score >= 90:
        lead = pk("lead_90", 0)
    elif score >= 75:
        lead = pk("lead_75", 1)
    elif score >= 60:
        lead = pk("lead_60", 2)
    elif score >= 45:
        lead = pk("lead_45", 3)
    else:
        lead = pk("lead_0", 4)

    if total <= 15:
        scale = pk("scale_15", 5, total=total)
    elif total <= 30:
        scale = pk("scale_30", 6, total=total)
    elif total <= 40:
        scale = pk("scale_40", 7, total=total)
    elif total <= 60:
        scale = pk("scale_60", 8, total=total)
    else:
        scale = pk("scale_99", 9, total=total)

    frame = pk("intro_frame", 10, orient=orient_txt, occupied=occupied,
               score=score, grade=grade)

    urgents = result["urgent"]
    if len(urgents) >= 2:
        tail = pk("urgent_2", 11, key1=urgents[0]["key"],
                  key2=urgents[1]["key"],
                  n1=_nature(urgents[0]["key"]),
                  n2=_nature(urgents[1]["key"]))
    elif len(urgents) == 1:
        tail = pk("urgent_1", 12, key1=urgents[0]["key"],
                  n1=_nature(urgents[0]["key"]))
    else:
        tail = pk("urgent_0", 13)

    p1 = scale + lead + frame + tail
    if top_dir != 180:
        p1 += pk("orient_custom", 14)
    paras.append(p1)

    # ================= 二、中宫 =================
    if center == 0:
        if total <= 20:
            body = pk("center0_body_small", 20)
            ctail = pk("center0_tail_small", 21)
        elif total <= 40:
            body = pk("center0_body_mid", 22)
            ctail = pk("center0_tail_mid", 23)
        else:
            body = pk("center0_body_big", 24)
            ctail = pk("center0_tail_big", 25)
    elif center == 1:
        body = pk("center1_body", 26)
        ctail = pk("center1_tail", 27)
    elif center <= 3:
        body = pk("center2_body", 28, center=center)
        ctail = pk("center2_tail", 29)
    else:
        body = pk("center4_body", 30, center=center)
        ctail = pk("center4_tail", 31)
    paras.append("先说中宫。" + body + ctail)

    # ================= 三、明堂 =================
    if hall == 0:
        p3 = pk("hall0", 35)
    elif hall <= 4:
        p3 = pk("hall4", 36, hall=hall)
    elif hall <= 9:
        p3 = pk("hall9", 37, hall=hall)
    elif hall <= 14:
        p3 = pk("hall14", 38, hall=hall)
    else:
        p3 = pk("hall15", 39, hall=hall)
    paras.append(p3)

    # ================= 四、四象与聚散 =================
    if right > left:
        diff = right - left
        if diff <= 3:
            p4 = pk("sides_r3", 40, left=left, right=right)
        elif diff <= 10:
            p4 = pk("sides_r10", 41, left=left, right=right)
        else:
            p4 = pk("sides_r99", 42, left=left, right=right)
    elif left and right and left / max(1, right) > 5:
        p4 = pk("sides_l5", 43, left=left, right=right)
    elif left == 0 and right == 0:
        p4 = pk("sides_both0", 44)
    elif left and not right:
        p4 = pk("sides_lonly", 45, left=left)
    elif left / max(1, right) >= 2:
        p4 = pk("sides_l2", 46, left=left, right=right)
    else:
        p4 = pk("sides_lmild", 47, left=left, right=right)

    if align >= 0.95:
        p4 += pk("align95", 48, align=round(align * 100))
    elif align >= 0.8:
        p4 += pk("align80", 49, align=round(align * 100))
    elif align >= 0.6:
        p4 += pk("align60", 50, align=round(align * 100))
    else:
        p4 += pk("align0", 51, align=round(align * 100))

    # 空宫：把中宫算进「共几宫空着」，这样与总起的「占了几宫」加起来正好九宫
    n_empty = len(st["empty"])
    if n_empty == 0 and center != 0:
        p4 += pk("empty0", 52)
    else:
        names = [e.split("宫")[0] for e in st["empty"]]
        if center == 0:
            names = names + ["中"]
            n_all = n_empty + 1
        else:
            n_all = n_empty
        names_txt = "、".join(n + "宫" for n in names)
        if n_empty == 0:
            names_txt = "中宫"
        if n_all <= 2:
            p4 += pk("empty2", 53, names=names_txt, n_empty=n_all,
                     saying=PALACE_SAYING.get(names[0], "那一方之气便虚"))
        else:
            p4 += pk("emptymany", 54, names=names_txt, n_empty=n_all,
                     saying=PALACE_SAYING.get(names[0], "那几方之气皆虚"))
    paras.append(p4)

    # ================= 五、五行 =================
    top_w = max(classify.WUXING_ORDER, key=lambda w: dist[w])
    share = dist[top_w] / max(1, total)
    zero_w = [w for w in classify.WUXING_ORDER if dist[w] == 0]

    p5 = pk("wux_head", 60, total=total,
            dist="、".join("%s %d 个" % (w, dist[w])
                           for w in classify.WUXING_ORDER))

    if share >= 0.5:
        p5 += pk("wux_share50", 61, top=top_w, say=WUXING_SAYING[top_w],
                 noun=WUXING_NOUN[top_w])
    elif share >= 0.4:
        p5 += pk("wux_share40", 62, top=top_w, say=WUXING_SAYING[top_w],
                 noun=WUXING_NOUN[top_w])
    elif share >= 0.3:
        p5 += pk("wux_share30", 63, top=top_w, say=WUXING_SAYING[top_w])
    else:
        p5 += pk("wux_even", 64, top=top_w, top_n=dist[top_w],
                 say=WUXING_SAYING[top_w])

    if not zero_w:
        p5 += pk("wux_zero0", 65)
    elif len(zero_w) == 1:
        p5 += pk("wux_zero1", 66, zw=zero_w[0])
    else:
        p5 += pk("wux_zeromany", 67, zw="、".join(zero_w))

    if worst and worst["net"] < 0:
        bad = (worst["rel"]["克入"] + worst["rel"]["泄气"]
               + worst["rel"]["主克客"])
        gw = worst["wuxing"]
        kind = _dominant(worst["rel"])
        say = PALACE_SAYING.get(worst["gua"], "本宫")

        p5 += pk("wux_worst", 68, gua=worst["gua"], count=worst["count"],
                 bad=bad, net=("%.1f" % worst["net"]))
        p5 += pk("wux_kind_" + _KIND_KEY.get(kind, "mixed"), 69,
                 say=say, gw=gw)

        rule = _EXAMPLE_RULE.get(kind)
        cands = [i for i in worst["icons"] if rule(i["wuxing"], gw)] if rule else []
        if not cands:
            cands = worst["icons"]
        if cands:
            p5 += pk("wux_ex_" + _KIND_KEY.get(kind, "mixed"), 70,
                     names=_q([i["name"] for i in cands], 2),
                     iwx=cands[0]["wuxing"], gw=gw)
    elif best:
        p5 += pk("wux_best", 71, gua=best["gua"],
                 net=("%+.1f" % best["net"]),
                 saying=PALACE_SAYING.get(best["gua"], ""))
    paras.append(p5)

    # ================= 六、杂物 =================
    clutter = st["clutter"]
    if not clutter:
        p6 = pk("clutter_none", 80)
    else:
        names = [c["name"] for c in sorted(clutter, key=lambda c: -c["weight"])]
        kind = _clutter_kind(clutter)
        p6 = pk("clutter_head", 81, n=len(clutter), names=_q(names, 3))
        if len(names) > 3:
            p6 = p6.rstrip("。") + "，" + pk("clutter_more", 82)
        p6 += pk("clutter_" + kind, 83)
    paras.append(p6)

    # ================= 七、顺手度 =================
    # 这一段 2026-10-27 新加。20 分是七项里与杂物、生克并列的大项，
    # 也是唯一谈「用起来累不累」的一项，不写就是漏项。
    cf = st.get("comfort") or {}
    cscore = cf.get("score", 0.0)
    cst = cf.get("stats", {}) or {}
    ckw = dict(score=_num(cscore),
               hot_n=cst.get("hot_n", 0),
               common=cst.get("common", 0),
               archive=cst.get("archive", 0),
               cold_n=cst.get("cold_n", 0),
               cover=cst.get("cover", 0),
               busiest=cst.get("busiest", 0),
               center_n=cst.get("center_n", 0))
    if cscore >= 17:
        p_c = pk("comfort_high", 88, **ckw)
    elif cscore >= 12:
        p_c = pk("comfort_mid", 89, **ckw)
    else:
        p_c = pk("comfort_low", 90, **ckw)
    if p_c:
        paras.append(p_c)

    # ================= 八、收束 =================
    acts = [u for u in urgents if u["level"] == "忌"]
    if acts:
        steps = [_action(u["key"]) for u in acts[:3]]
        p7 = pk("act_intro", 95)
        if len(steps) == 1:
            p7 += pk("act_step1", 96, s1=steps[0])
        elif len(steps) == 2:
            p7 += pk("act_step2", 97, s1=steps[0], s2=steps[1])
        else:
            p7 += pk("act_step3", 98, s1=steps[0], s2=steps[1], s3=steps[2])
        if score >= 75:
            p7 += pk("act_score75", 99)
        elif score >= 60:
            p7 += pk("act_score60", 100)
        else:
            p7 += pk("act_score0", 101)
        p7 += pk("act_noneed", 102)
    else:
        p7 = pk("act_nothing", 103)

    if score >= 90:
        p7 += pk("end_90", 104)
    elif score >= 60:
        p7 += pk("end_75", 105)
    else:
        p7 += pk("end_0", 106)
    paras.append(p7)

    return paras


def plain_text(result: dict) -> str:
    return "\n\n".join(compose(result))
