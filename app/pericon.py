# -*- coding: utf-8 -*-
"""分图标判定（阶段 D）

把「这张盘」拆到「这一格里的这一个东西」：每个图标单独给一句判断、一句理、一句改。

口径只有一条，**不另造**：复用 `fengshui.relation()` 的五行生克，
免得「分条说相安、分图标说相克」自相矛盾。

文案规模：9 宫 × 5 行 = 45 种组合；每种组合 5 条变体（`REL_SENT` 每类 5 条），
配 9 条宫位性格（`GUA_DESC`）与按关系给的改法（`ADVICE`）。
单条 20–30 字，与全文案风格一致。

纯函数：只算不写盘、不碰界面。
"""
from __future__ import annotations

import random

import classify
import fengshui
from palace import palace_grid

# 宫位性格：一句话说清这个宫「管什么」，插进「理」里
GUA_DESC = {
    "巽": "巽宫属木，主沟通、文书、消息通达，是「进出」的一格。",
    "离": "离宫属火，主名声、显露、被看见，也是整张盘的明堂。",
    "坤": "坤宫属土，主承载、积累、后勤，厚重而不轻动。",
    "震": "震宫属木，主启动、行动、发起，是「动起来」的一格。",
    "兑": "兑宫属金，主表达、交易、口舌，也主欢愉。",
    "艮": "艮宫属土，主停顿、界限、收束，进可攻退可守的角落。",
    "坎": "坎宫属水，主思虑、储藏、暗中流动，也是「坐」的位置。",
    "乾": "乾宫属金，主决断、权威、长辈与规则，宜放要事。",
    "中": "中宫不属八卦，是整张盘的轴心，最忌压东西。",
}

# 关系 → (适配分, 短判断, 五级色 key)
REL_VERDICT = {
    "生入": (88, "得位", "best"),
    "比和": (75, "合宜", "good"),
    "主克客": (48, "受制", "mid"),
    "泄气": (35, "耗散", "weak"),
    "克入": (18, "相冲", "bad"),
}

# 五级判定图例：界面与报告最下方都用这一份，一句话说清它到底什么意思。
# 顺序从好到坏，颜色取 theme 的 tone5，跟着主题变。
LEGEND = (
    ("best", "得位", "这件东西在养这一宫（生入），放得其所"),
    ("good", "合宜", "同气相求（比和），不冲不耗，也不额外帮忙"),
    ("mid", "受制", "这一宫的五行克它（主克客），用起来总差一层"),
    ("weak", "耗散", "这一宫的气被它抽走（泄气），越用越虚"),
    ("bad", "相冲", "它在压这一宫（克入），最该挪走"),
)

# 关系 → 5 条同义说法（占位：{iwx} 图标五行、{gwx} 宫位五行、{gua} 宫名）
REL_SENT = {
    "生入": (
        "它是{iwx}，{gua}宫属{gwx}，{iwx}生{gwx}——这东西在养这一宫，放得其所。",
        "{iwx}气往{gwx}里走，等于给{gua}宫续了力，这一格会因为它在而更活。",
        "在{gua}宫摆一件{iwx}的东西，正好补上这一宫缺的那口气。",
        "{gua}宫本来就要{gwx}气，{iwx}生{gwx}，它是来帮忙的，不是来占地方的。",
        "这一件的五行顺着一路生过去，{gua}宫收得住，放在这里算是用对了地方。",
    ),
    "比和": (
        "它是{iwx}，{gua}宫也是{gwx}，同气相求，不冲不耗。",
        "{iwx}与{gwx}同属一类，放在{gua}宫等于自己人待在自家屋里。",
        "同气的一件东西放在{gua}宫，稳当，也谈不上增益。",
        "{gua}宫要的就是{gwx}，这件正好是{iwx}，气味相投。",
        "不克不生，纯是同类。放在这里不出错，但也不会额外帮上什么。",
    ),
    "主克客": (
        "它是{iwx}，{gua}宫的{gwx}克{iwx}，这东西在这里是被压着用的。",
        "{gwx}克{iwx}，宫强物弱。它待得住，但用得不会太顺。",
        "在{gua}宫放一件{iwx}的东西，等于让它常年受制于{gwx}。",
        "{gua}宫的{gwx}压住{iwx}，功能还在，只是每次用都觉得隔了一层。",
        "不是不能放，是放了要费点劲才能用上——宫在克它。",
    ),
    "泄气": (
        "它是{iwx}，{gua}宫的{gwx}生{iwx}，这一格的气被它一点点抽走。",
        "{gwx}生{iwx}，宫在给它喂力。偶尔用没事，常驻就是耗。",
        "这件{iwx}的东西放在{gua}宫，等于让整格一直在往外供。",
        "{gua}宫的气顺到{iwx}上去了，用得越勤，这一格越虚。",
        "它本身没错，只是位置不对：宫位一直在养它，久了自己会空。",
    ),
    "克入": (
        "它是{iwx}，{iwx}克{gua}宫的{gwx}，这一格被它顶着。",
        "{iwx}克{gwx}，物强宫弱。放在这里，是它压着这一格。",
        "在{gua}宫摆一件{iwx}的东西，等于让宫位挨了一下，越常用越明显。",
        "{gua}宫本来就靠{gwx}立着，来了个克{gwx}的{iwx}，气就散了。",
        "这是最不该留的一类：它在这儿，这一格就一直不舒展。",
    ),
}

# 关系 → 改法
ADVICE = {
    "生入": (
        "留着。它在这一格是加分项，不用动。",
        "可以留。若哪天要腾地方，它是最后该挪的。",
    ),
    "比和": (
        "留着也行。真要调，优先动别的，不用在它身上费劲。",
        "不必特意处理。它不添乱，也不帮忙。",
    ),
    "主克客": (
        "能挪就挪去生它的宫（{target}），挪不动就少在这格停留。",
        "不急。下次整理时顺手放到{target}，用起来会顺一些。",
    ),
    "泄气": (
        "建议挪走：{target}能接住它的气，别让它一直耗着{gua}宫。",
        "这一件最值得动。搬到{target}，两边都轻松。",
    ),
    "克入": (
        "优先挪走。{target}受得住它，留在这里只会一直顶着{gua}宫。",
        "它是这一格的主要负担。挪到{target}，这一格立刻松快。",
    ),
}

# 中宫有图标：不套生克，直接判最忌。5 条变体，让反复打开不至于一模一样。
CENTER_SENT = (
    "正中一格放了东西，这一格本该空着——它挡的是视线的落点，也是手最容易误点的地方。",
    "中宫是全盘的轴心，四维都从这里起算。轴心被占，四周的方位就容易判歪。",
    "这一件压在正中，等于给整张盘定了个歪的重心：看哪一格都像偏。",
    "方寸之间最忌堵心。中宫那一格空着，视线才有落脚的地方。",
    "中宫空，是这一套里最不需要理由的一条。有东西在，就先把它挪开。",
)
CENTER_ADVICE = (
    "挪去任意一个空宫的四角方向即可，中宫留空比放什么都强。",
    "先把它挪到下方或四角，空出来的那一格不用补任何东西。",
    "挑一个空着的宫放过去，中宫保持空——这是唯一不用权衡的一步。",
)


def _pick(options, idx: int = 0):
    """按图标在宫内的序号取变体。

    不用 random：同一次分析里两次打开要看到同样的字，
    而「每次分析换一句」由外层（analyze）负责。
    """
    if not options:
        return ""
    return options[idx % len(options)]


def build(layout: dict, result: dict) -> list[dict]:
    """按宫分组，输出每个图标的判定。

    返回 [{cell, gua, dir, wuxing, count, avg, level, icons: [...]}, ...]，
    顺序固定为九宫（左上→右下），空宫不返回。
    """
    top = result.get("orientation", 180)
    grid = palace_grid(top)
    # counts 必须是完整的 9 个键：fengshui.pick_target() 会按下标查空宫，
    # 缺键会 KeyError（踩过）
    counts = {(r, c): 0 for r in range(3) for c in range(3)}
    cells: dict[tuple, list] = {}
    for it in layout.get("icons", []):
        rc = (it["row"], it["col"])
        counts[rc] += 1
        cells.setdefault(rc, []).append(it)

    out: list[dict] = []
    for r in range(3):
        for c in range(3):
            items = cells.get((r, c))
            if not items:
                continue
            info = grid[r][c]
            is_center = (r, c) == (1, 1)
            gua = info["gua"] if info else "中"
            gw = info["wuxing"] if info else "土"
            rows = []
            for i, it in enumerate(items):
                iwx = it.get("wuxing") or "金"
                if is_center:
                    rel, w = "克入", -1.0
                    score, verdict, tone = 10, "最忌", "bad"
                    sent = _pick(CENTER_SENT, i)
                    adv = _pick(CENTER_ADVICE, i)
                else:
                    rel, w = fengshui.relation(iwx, gw)
                    score, verdict, tone = REL_VERDICT[rel]
                    sent = _pick(REL_SENT[rel], i).format(
                        iwx=iwx, gwx=gw, gua=gua)
                    target = fengshui.pick_target(it, grid, counts)
                    adv = _pick(ADVICE[rel], i).format(
                        gua=gua, target=target)
                rows.append({
                    "name": it.get("name", ""),
                    "wuxing": iwx,
                    "rel": rel,
                    "rel_score": w,
                    "score": score,
                    "verdict": verdict,
                    "tone": tone,
                    "evidence": sent,
                    "principle": ("中宫是轴心，四维都从这里起。"
                                  if is_center else GUA_DESC[gua]),
                    "advice": adv,
                })
            avg = round(sum(x["score"] for x in rows) / len(rows))
            if is_center:
                level = "忌"
            elif avg >= 70:
                level = "吉"
            elif avg >= 45:
                level = "平"
            else:
                level = "忌"
            out.append({
                "cell": (r, c),
                "gua": gua,
                "dir": info["dir"] if info else "中央",
                "wuxing": gw,
                "count": len(rows),
                "avg": avg,
                "level": level,
                "center": is_center,
                "icons": rows,
            })
    return out


def summary_line(group: dict) -> str:
    """宫位行的摘要：`离宫 · 南 · 10 个 · 忌 · 平均 32`"""
    if group["center"]:
        return "中宫 · %d 个 · 最忌" % group["count"]
    return "%s宫 · %s · %d 个 · %s · 平均 %d" % (
        group["gua"], group["dir"], group["count"], group["level"],
        group["avg"])
