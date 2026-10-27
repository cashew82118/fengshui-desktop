# -*- coding: utf-8 -*-
"""诊断文案库（阶段三·第二批扩容）

把「现象 / 理 / 改」三处文案从算法里拆出来，按**程度分档**各写 2–3 种。
同一档位内不写同义句——每一句都换了一个观察角度：
    现象：换计量方式（个数 / 倍数 / 占比）
    理  ：换说理侧重（气机 / 人事 / 时序）
    改  ：换具体动作（移到哪 / 删掉 / 归档 / 别再加）

算法只负责给档位，文案只负责说人话。
"""
from __future__ import annotations

import random

import classify
import phrases_pool


def _pick(options: list[str], idx: int = 0) -> str:
    """随机取一句同义说法。

    `idx` 保留只为兼容旧调用（原来按数据取模，等于"哪句话取决于图标个数"）；
    现在改成随机：同一张桌面每分析一次就换一种说法。
    诊断文案在 analyze() 里只生成一次，所以一次分析之内卡片文字是稳定的。
    """
    if not options:
        return ""
    return random.choice(options)


# ---------------------------------------------------------------- 中宫

def center_empty(total: int) -> tuple[str, str, str]:
    key = ("center.empty.low" if total <= 20 else
           "center.empty.mid" if total <= 40 else "center.empty.high")
    hit = phrases_pool.pick(key, total=total)
    if hit:
        return hit
    if total <= 20:
        return (
            "盘之正中一格空着，一个图标也没有",
            "中宫是气之枢纽，宜虚。虚则八方之气得以往来，"
            "实则一物塞中、八方皆滞。",
            "保持空着即可。东西少的时候最容易守住这一格。",
        )
    if total <= 40:
        return (
            "中宫（盘之正中一格）无图标，气枢通透",
            "中宫宜虚不宜实。它空着，诸事才有回旋的余地。",
            "不必刻意补东西进去。中宫宁可空着，也别为了对称摆点什么。",
        )
    return (
        "中宫一格全空，图标都在外圈",
        "图标越多，越容易把正中糊满；你能留住这一格，是气局还有主次。",
        "守住这一格。以后新建的文件别顺手丢在正中。",
    )


def center_press(n: int, names: str, first: str,
                 target: str) -> tuple[str, str, str]:
    key = ("center.press.one" if n == 1 else
           "center.press.small" if n <= 3 else "center.press.big")
    hit = phrases_pool.pick(key, n=n, names=names, first=first,
                            target=target)
    if hit:
        return hit
    if n == 1:
        return (
            "中宫（盘之正中）只有 1 个图标：%s" % names,
            _pick([
                "只一件，看着无伤，可它偏偏落在气枢上——八方之气都得绕它走。",
                "中宫宜虚，一件也算实。气枢被一件东西钉住，事情就容易在同一个地方反复。",
            ], n % 2),
            "把「%s」移到%s，中宫即空。只挪一件，代价最小。" % (first, target),
        )
    if n <= 3:
        return (
            _pick([
                "中宫内有 %d 个图标：%s" % (n, names),
                "盘之正中压着 %d 个：%s，已成小堆" % (n, names),
            ], n % 2),
            _pick([
                "中宫为气之枢纽，宜虚不宜实。三件以内还不算堵死，但气已经不顺了。",
                "如同一张案台正中摞了东西——取用都得绕手，久了就懒得动。",
            ], n % 2),
            "把「%s」先移出中宫，%s较合；剩下的几件也顺手挪走。" % (first, target),
        )
    return (
        "中宫内有 %d 个图标，把中路封死了：%s" % (n, names),
        _pick([
            "中宫一塞，八方之气无处交汇。这不是量的问题，是位置的问题。",
            "气枢被彻底占满，全局就没有转圜的余地——事事都像在挤。",
        ], n % 2),
        "先动「%s」，挪到%s。中宫必须清空，别的都可以缓。" % (first, target),
    )


# ---------------------------------------------------------------- 明堂

def hall_block(n: int, gua: str, avg: float, ratio: float,
               move_n: int, first: str, target: str) -> tuple[str, str, str]:
    key = ("hall.block.light" if n <= 9 else
           "hall.block.mid" if n <= 14 else "hall.block.heavy")
    hit = phrases_pool.pick(key, n=n, gua=gua, avg=avg, ratio=ratio,
                            move_n=move_n, first=first, target=target)
    if hit:
        return hit
    if n <= 9:
        return (
            _pick([
                "%s宫（上方正中·明堂）有 %d 个图标，为全盘单宫均值的 %.1f 倍"
                % (gua, n, ratio),
                "明堂一格落了 %d 个图标，密度已是均值的 %.1f 倍" % (n, ratio),
            ], n % 2),
            _pick([
                "朱雀为明堂，主前程出路，宜开阔虚朗。半堵不堵最难受——不是过不去，是总要侧身。",
                "明堂宜虚。堆到七八个，就像案头正前方摞了半叠没拆的信，抬手总要碰一下。",
            ], n % 2),
            "先移走 %d 个，从「%s」开始，挪到%s。" % (move_n, first, target),
        )
    if n <= 14:
        return (
            _pick([
                "%s宫（上方正中·明堂）堆了 %d 个图标，是全盘最挤的一处，均值 %.1f 倍"
                % (gua, n, ratio),
                "明堂一格 %d 个图标，已明显高于其余各宫（均值 %.1f 倍）" % (n, ratio),
            ], n % 2),
            _pick([
                "明堂主前路。堵在这里，事情就推不动——不是没力气，是路窄。",
                "朱雀位塞满，主的是谋事多而落地少；想得开，走不出去。",
            ], n % 2),
            "至少移走 %d 个。「%s」可先去%s，其余按此理类推。" % (move_n, first, target),
        )
    return (
        "%s宫（上方正中·明堂）几乎填满，共计 %d 个图标，均值 %.1f 倍"
        % (gua, n, ratio),
        _pick([
            "明堂是朱雀之位，主前程与出路。前方塞成这样，等于出门就撞墙。",
            "这一格到了这个密度，已经不是明堂，是仓库。气进不来，也出不去。",
        ], n % 2),
        "先清出 %d 个空位。「%s」挪去%s最省事，剩下的分批往外圈散。" % (move_n, first, target),
    )


def hall_open(gua: str, n: int) -> tuple[str, str, str]:
    hit = phrases_pool.pick("hall.open.none" if n == 0 else "hall.open.some",
                            gua=gua, n=n)
    if hit:
        return hit
    if n == 0:
        return (
            "%s宫（明堂）空无一物，前方通透" % gua,
            "明堂得虚，气行无阻，主出路通达。多数人第一个图标就落在这里，你没有。",
            "保持上方正中留白，这是这张盘最值钱的地方。",
        )
    return (
        _pick([
            "%s宫（明堂）仅 %d 个图标，尚在虚的范围" % (gua, n),
            "明堂一格 %d 个，未成壅塞" % n,
        ], n % 2),
        _pick([
            "明堂宜开阔。这个数目还留着余地，前路是通的。",
            "朱雀位不挤，主谋事有出口；再多几个就到临界了。",
        ], n % 2),
        "不必动。只是别让这里继续增加到六七个以上。",
    )


# ---------------------------------------------------------------- 四象

def sides_baihu(n_l: int, n_r: int, diff: int, sample: str) -> tuple[str, str, str]:
    key = ("sides.baihu.light" if diff <= 3 else
           "sides.baihu.mid" if diff <= 10 else "sides.baihu.heavy")
    hit = phrases_pool.pick(key, nl=n_l, nr=n_r, diff=diff, sample=sample)
    if hit:
        return hit
    if diff <= 3:
        return (
            "左侧（青龙）%d 个，右侧（白虎）%d 个，右边略重 %d 个" % (n_l, n_r, diff),
            _pick([
                "差得不多，但形法讲「不怕青龙高万丈，就怕白虎抬头望」——"
                "右边压过左边，主的是旁枝之事多、口舌从侧边来。",
                "四象以左为尊。右边多出几个不算大碍，属苗头，早收早好。",
            ], diff % 2),
            "把右侧一两个挪回左半即可，不必大动。",
        )
    if diff <= 10:
        return (
            "左侧（青龙）%d 个，右侧（白虎）%d 个，右重于左 %d 个" % (n_l, n_r, diff),
            _pick([
                "青龙主进、主贵，白虎主守、主是非。白虎抬头，多是人事上耗神，"
                "事情不从正门来。",
                "右重左轻，主的是替人奔忙、自身的事反倒往后排。",
            ], diff % 2),
            "把「%s」这类挪回左侧，让青龙重新压住。" % sample,
        )
    return (
        "左侧（青龙）%d 个，右侧（白虎）%d 个，白虎重压青龙" % (n_l, n_r),
        _pick([
            "这是明显的失衡。老话说就怕白虎抬头望，到这个程度，主身不由己。",
            "白虎过旺，是非从外而来；青龙受制，主位坐不稳。",
        ], diff % 2),
        "先把右侧靠外的几件移走，尤其是「%s」这类；腾出左半的空间。" % sample,
    )


def sides_qinglong(n_l: int, n_r: int, ratio: float) -> tuple[str, str, str]:
    hit = phrases_pool.pick(
        "sides.qinglong.strong" if ratio <= 8 else "sides.qinglong.alone",
        nl=n_l, nr=n_r, ratio=ratio)
    if hit:
        return hit
    if ratio <= 8:
        return (
            "左侧（青龙）%d 个，右侧（白虎）仅 %d 个，比值 %.1f" % (n_l, n_r, ratio),
            "青龙得势本是吉象，但这个比例已经过了——左边挤、右边空，"
            "主事必躬亲、无人分担。",
            "把左下角几个移到右下，让白虎有物可守。",
        )
    return (
        "左侧（青龙）%d 个，右侧（白虎）仅 %d 个，几近独旺" % (n_l, n_r),
        "白虎全虚，等于没有人替你守后方。青龙再旺，一个人也撑不住两头。",
        "右下角留几个常用之物，不必多，两三个即可成势。",
    )


def sides_both_empty(total: int = 0) -> tuple[str, str, str]:
    hit = phrases_pool.pick("sides.both_empty", total=total)
    if hit:
        return hit
    return (
        "左右两侧均无图标，全部聚在中带",
        "四象贵在左右有护。两侧全空，格局局促，像人站着却两臂无处放。",
        "把中带的图标分几个到左右，先成象，再谈吉凶。",
    )


def sides_good(n_l: int, n_r: int, ratio: float) -> tuple[str, str, str]:
    key = ("sides.good.no_right" if n_r == 0 else
           "sides.good.left_wide" if ratio >= 2 else "sides.good.balanced")
    hit = phrases_pool.pick(key, nl=n_l, nr=n_r, ratio=ratio)
    if hit:
        return hit
    if n_r == 0:
        return (
            "左侧（青龙）%d 个，右白虎一个也无" % n_l,
            "青龙独旺、白虎全缺，主你担得起事，却少人相帮；守得住，却也闷。",
            "右下留两三个常用之物，既是分流，也是给自己留个后手。",
        )
    if ratio >= 2:
        return (
            "左侧（青龙）%d 个，右侧（白虎）%d 个，左胜右而差距明显" % (n_l, n_r),
            "青龙宜动宜高、白虎宜静宜低。主位坐得住、进退有据，"
            "只是左边略挤，收着点更好。",
            "维持现状即可；若再往左添，就该往外圈散一散了。",
        )
    return (
        "左侧（青龙）%d 个，右侧（白虎）%d 个，左胜右而不过" % (n_l, n_r),
        _pick([
            "不怕青龙高万丈，就怕白虎抬头望。左重右轻而不失衡，是形法里想要的次序。",
            "两边都有、左略胜，主位稳当，进退有据。",
        ], n_l % 2),
        "维持现状，右侧不再增加即可。",
    )


# ---------------------------------------------------------------- 聚散（已废弃）

# 注意：下面三个 spread_* 是「聚散」还是独立卡片时的遗留。2026-10-25 全项目检索确认
# **零调用**（聚散已并入「形态」卡片，文案见 phrases.form / form_good / form_mild）。
# 文案池不给它们写；保留函数只是防外部引用，新项目可直接删。

def spread_empty(occupied: int, empty_n: int, empty_names: list[str]) -> tuple[str, str, str]:
    shown = "、".join(empty_names[:3])
    if empty_n <= 3:
        return (
            "全盘 %d 宫有图标，%d 宫偏空：%s" % (occupied, empty_n, shown),
            "气贵周流。空一两宫只是略薄，不算病；但那一方之事会缺个落脚处。",
            "把外圈的两三个图标挪过去，令宫中皆有其物。",
        )
    if empty_n <= 4:
        return (
            "全盘仅 %d 宫有图标，%d 宫全空：%s" % (occupied, empty_n, shown),
            "九宫空去近半，气只在一隅打转。对应之事皆无所依托，久了会觉得"
            "有些方面怎么推都推不动。",
            "把图标分散到 %s，不必挤在两三处。" % shown,
        )
    return (
        "全盘只有 %d 宫有图标，%d 宫全空：%s" % (occupied, empty_n, shown),
        "空宫过半，等于把半张棋盘让出去。气不周流，主局面偏枯。",
        "先往 %s 各放一两件，把棋盘摆开，再谈别的。" % shown,
    )


def spread_messy(align_ratio: float, occupied: int) -> tuple[str, str, str]:
    pct = round(align_ratio * 100)
    if align_ratio >= 0.6:
        return (
            "仅 %d%% 的图标落在整齐网格上，%d 宫有图标" % (pct, occupied),
            "整则气顺，乱则气散。大体成行、边上几个歪着，只是不利索，不算乱。",
            "开「对齐到网格」，把手拖过的几个归位即可。",
        )
    return (
        "只有 %d%% 的图标落在网格上，其余随手拖放" % pct,
        "参差散落，看的时候眼睛没处落，心神也就难定。形法以整为顺。",
        "先开「对齐到网格」让它们排齐，再考虑要不要分类分区。",
    )


def spread_good(occupied: int, align_ratio: float) -> tuple[str, str, str]:
    pct = round(align_ratio * 100)
    if pct >= 100:
        return (
            "%d 宫有图标，全部 %d%% 落在整齐网格上" % (occupied, pct),
            "整则气顺。成行成列而不塞，是聚散得宜。",
            "保持成行成列，不必追求对称。",
        )
    return (
        "%d 宫有图标，%d%% 落在整齐网格上" % (occupied, pct),
        "大体成行，秩序尚可。气顺则事简。",
        "保持现状即可。",
    )


# ---------------------------------------------------------------- 杂物

# 池子用：把 kind 翻译成人话，免得十组文案各写一遍分支
_CLUTTER_WORD = {
    "installer": "安装包",
    "nameless": "没起名的临时件",
    "longname": "名字超长的文件",
    "dup": "重复的快捷方式",
    "mixed": "各类杂物",
}

_CLUTTER_TEXT = {
    "installer": (
        "占份量最多的是安装包——装完就该走的东西，还留在盘上",
        "形法里叫「器未成形」：占着位置，却已经没用了。",
        "安装完的包直接删，不心疼；真要留档，归进一个文件夹再走。",
    ),
    "nameless": (
        "多数是「新建」这类无主之物，连名字都没起",
        "连想做什么都还没定，就先占了一块地方——这是最典型的滞留之气。",
        "这类九成是空壳，逐个看过，删掉不损失什么。",
    ),
    "longname": (
        "最显眼的是名目冗长之物，名字长到一行放不下",
        "在盘上就是一团糊：看不清，也就不想动它，久了成了固定的堵点。",
        "归个档，换个短名。名字短了，才拿得起来。",
    ),
    "dup": (
        "有几件重复命名的快捷方式，同一件事有两个入口",
        "气分两路，则两路都不旺。多一个入口，不是方便，是分神。",
        "删掉多余那个，留一个。",
    ),
    "mixed": (
        "品类杂陈：既有未化的器，也有无主之物，还有名目冗长的",
        "形法以洁净为要。这些东西不占多大地方，却天天在眼前晃；"
        "久了壅塞的不是桌面，是心志。",
        "不必一次清完，先挑最旧、最不认识的那一件动手。",
    ),
}

_CLUTTER_TEXT_ALT = {
    "installer": (
        "堆着臃肿的安装包",
        "土主承载，过则成滞。安装包是土里最沉的那种——已经用过了，却还在压着。",
        "能删就删；不能删的，移出桌面。",
    ),
    "nameless": (
        "散着几件临时命名的无主之物",
        "无主之物最耗神：每次扫过去都要判断一次「这是什么」，一天几十次。",
        "归档或删除。留着的成本比删掉高得多。",
    ),
    "longname": (
        "有一件名目极长，横跨两三格",
        "形长则气散。名字太长，气就沿着名字散掉了，聚不到一处。",
        "改个短名，或整个收进文件夹。",
    ),
    "dup": (
        "同一件事有两个入口",
        "两处入口，两处都要看一眼，气就分了两路。",
        "保留常用的那个，另一个删掉。",
    ),
    "mixed": (
        "杂七杂八积了几件",
        "洁净则气清。杂物不是脏，是「还没决定」——每一件都是一个悬着的念头。",
        "定个规矩：桌面只放本周要用的，其余归档。",
    ),
}


def clutter_dirty(n: int, kind: str, names: list[str], cap: int) -> tuple[str, str, str]:
    hit = phrases_pool.pick("clutter.dirty", n=n, cap=cap,
                            names=_qlist(names, 3),
                            kind_word=_CLUTTER_WORD.get(kind, "各类杂物"))
    if hit:
        return hit
    ev_first, pr_first, ad_first = _CLUTTER_TEXT.get(kind, _CLUTTER_TEXT["mixed"])
    ev_alt, pr_alt, ad_alt = _CLUTTER_TEXT_ALT.get(kind, _CLUTTER_TEXT_ALT["mixed"])
    idx = n % 2
    evidence = _pick([
        "共 %d 件杂物，扣 %d 分：%s" % (n, cap, _qlist(names, 3)),
        "查出 %d 件杂物，扣 %d 分：%s" % (n, cap, _qlist(names, 3)),
    ], idx)
    desc = _pick([ev_first, ev_alt], idx)
    principle = _pick([pr_first, pr_alt], idx)
    advice = _pick([ad_first, ad_alt], idx)
    return evidence, desc + "。" + principle, advice


def _qlist(names: list[str], limit: int = 3) -> str:
    picked = ["「%s」" % n for n in names[:limit]]
    return "、".join(picked)


def clutter_clean() -> tuple[str, str, str]:
    hit = phrases_pool.pick("clutter.clean")
    if hit:
        return hit
    return (
        "未检出无主文件、安装包滞留或超长名目",
        "洁净则气清，气清则事简。桌面干净的人，做事多半也不拖。",
        "保持。每月扫一眼即可。",
    )


# ---------------------------------------------------------------- 生克

# 池子用的三张短表：kind → 人话／一句原理／一句动作
_WX_WORD = {"克入": "客克主", "泄气": "泄气",
            "主克客": "主克客", "mixed": "克泄混杂"}
_WX_TIP = {
    "克入": "物反过来克宫，是客克主——外面的事一直在吃你的底",
    "泄气": "宫气往外生，是泄——事都成了，人却空了",
    "主克客": "宫位压着物，能管住，但要一直管",
    "mixed": "克、泄各半，没有主次，这一宫的气是乱的",
}
_WX_AD = {
    "克入": "把克本宫的那几类移出本宫",
    "泄气": "本宫少放这一类，减一半气就收得住",
    "主克客": "减到一两件即可，别让本宫一直在管人",
    "mixed": "先挑最刺眼的两件挪走，把局面简化",
}

_WUXING_BLOCK = {
    "克入": (
        "物反过来克宫，这叫客克主，是最耗的一种——外面的事一直在吃你的底",
        "克入者，客强主弱。看着都在运转，其实是你在被消耗。",
        "把这些物挪出本宫；宫位之气守住了，事才做得久。",
    ),
    "泄气": (
        "宫气往外生，这叫泄——看着无事，实则在漏，精力使出去收不回来",
        "泄气不显，最难察觉。事都成了，人却空了。",
        "本宫不宜多放这一类；减一半，气就收得住。",
    ),
    "主克客": (
        "宫位压着物，虽能制住，却也费力——属于管得住的麻烦",
        "主克客者，能管，但一直在管。耗的是耐性。",
        "不必全清，减到一两件即可，别让本宫一直在管人。",
    ),
    "mixed": (
        "克、泄各占一半，没有主次，这一宫的气是乱的",
        "有克有泄而无主，等于同时被吃、被漏——最费解，也最难改。",
        "先挑最刺眼的两件挪走，把局面简化，再看主次。",
    ),
}

_WUXING_BLOCK_ALT = {
    "克入": (
        "这一宫以克入为主，客强于主",
        "克入久则主位虚。你在这件事上一直是被推着走的。",
        "把克本宫的那几类移走，主位才坐得稳。",
    ),
    "泄气": (
        "这一宫以泄气为主，气往外流",
        "泄而不聚，主谋多成少。生出去的比收回来的多。",
        "减量，或者换成本宫所喜之物。",
    ),
    "主克客": (
        "这一宫以主克客为主，管得住但费劲",
        "克得住不是本事，不用克才是。",
        "能移走就移走，别留一堆要你管的东西。",
    ),
    "mixed": (
        "这一宫克泄混杂，未见主次",
        "气无主则乱，乱则事倍功半。",
        "做减法：先清到只剩三件以里，再论生克。",
    ),
}


def wuxing_block(gua: str, gw: str, count: int, bad: int, net: float,
                 kind: str, n_l: int, icon_names: list[str],
                 icon_wx: str) -> tuple[str, str, str]:
    hit = phrases_pool.pick(
        "wuxing.block", gua=gua, gw=gw, count=count, bad=bad,
        net_txt="%+.1f" % net, kind_word=_WX_WORD.get(kind, "克泄混杂"),
        kind_tip=_WX_TIP.get(kind, _WX_TIP["mixed"]),
        kind_ad=_WX_AD.get(kind, _WX_AD["mixed"]),
        names=_qlist(icon_names, 2), icon_wx=icon_wx)
    if hit:
        return hit
    ev = _pick([
        "%s宫（属%s）%d 个图标中 %d 个与宫位相碍，净气 %.1f"
        % (gua, gw, count, bad, net),
        "%s宫（%s）共 %d 件，%d 件克泄本宫，净气 %+.1f"
        % (gua, gw, count, bad, net),
    ], n_l)
    pr = _pick([_WUXING_BLOCK[kind][0], _WUXING_BLOCK_ALT[kind][0]], n_l)
    pr2 = _pick([_WUXING_BLOCK[kind][1], _WUXING_BLOCK_ALT[kind][1]], n_l)
    ad = _pick([_WUXING_BLOCK[kind][2], _WUXING_BLOCK_ALT[kind][2]], n_l)
    detail = _example_line(kind, gw, icon_names, icon_wx)
    return ev + "。" + detail, pr + "。" + pr2, ad


def _example_line(kind: str, gw: str, names: list[str], icon_wx: str) -> str:
    q = _qlist(names, 2)
    if kind == "克入":
        return "譬如%s，属%s，%s克%s，正克本宫之气。" % (q, icon_wx, icon_wx, gw)
    if kind == "泄气":
        return "譬如%s，属%s，本宫%s气外生%s，就这么散了出去。" % (q, icon_wx, gw, icon_wx)
    if kind == "主克客":
        return "譬如%s，属%s，本宫%s克它，虽压得住也占心思。" % (q, icon_wx, gw)
    return "譬如%s，属%s，落在%s宫里气就不顺。" % (q, icon_wx, gw)


def wuxing_ok(net: float) -> tuple[str, str, str]:
    hit = phrases_pool.pick(
        "wuxing.ok.positive" if net > 0 else "wuxing.ok.neutral",
        net_txt="%+.1f" % net)
    if hit:
        return hit
    if net > 0:
        return (
            "各宫未见克入或泄气，净气 %+.1f，是生入为主" % net,
            "物各归其位，气各安其宫。生入多于克泄，主顺遂。",
            "保持。往后添东西时，看一眼五行归属即可。",
        )
    return (
        "各宫未见明显克入或泄气，净气 %+.1f" % net,
        "没有明显相碍，气机平顺。这是难得的底子。",
        "保持。",
    )


# ---------------------------------------------------------------- 五行偏枯

# 池子用：五行 → 主什么／缺了怎么补／多了什么后果／怎么减
_WX_ROLE = {"木": "文思", "火": "显象", "土": "承载", "金": "器物", "水": "流动"}
_WX_MISS_AD = {
    "木": "添一两件文书、笔记类入盘", "火": "添一两件影音图像类入盘",
    "土": "添一两个文件夹归置", "金": "添一两件工具类快捷方式",
    "水": "添一两个链接或云端入口",
}
_WX_FULL_AD = {
    "木": "移走一部分文书类", "火": "移走一部分影音图像类",
    "土": "移走一部分安装包与素材夹", "金": "移走一部分工具类",
    "水": "移走一部分链接与云端入口",
}
_WX_RISK = {
    "木": "文思过盛而落地不足", "火": "显象过盛而耗神",
    "土": "堆积过重而气滞", "金": "器物过盛而失轻重",
    "水": "流动过盛而聚不住",
}

_ZERO_TEXT = {
    "木": ("全盘无属木之物，文思一路无以为继", "添一两件文书、笔记类入盘。"),
    "火": ("全盘无属火之物，显象一路几近于无", "添一两件影音图像类入盘即可。"),
    "土": ("全盘无属土之物，承载一路空虚", "添一两个文件夹归置，土气自生。"),
    "金": ("全盘无属金之物，器物一路缺位", "添一两件工具类快捷方式。"),
    "水": ("全盘无属水之物，流动一路不通", "添一两个链接或云端入口。"),
}

_FULL_TEXT = {
    "木": ("属木之物的占全盘太多，文思过盛而落地不足", "移走一部分文书类。"),
    "火": ("属火之物的占全盘太多，显象过盛而耗神", "移走一部分影音图像类。"),
    "土": ("属土之物的占全盘太多，堆积过重而气滞", "移走一部分安装包与素材夹。"),
    "金": ("属金之物的占全盘太多，器物过盛而失轻重", "移走一部分工具类。"),
    "水": ("属水之物的占全盘太多，流动过盛而聚不住", "移走一部分链接与云端入口。"),
}


def bianque_missing(w: str, total: int) -> tuple[str, str, str]:
    hit = phrases_pool.pick("bianque.missing", w=w, total=total,
                            w_role=_WX_ROLE.get(w, "这一路"),
                            w_miss_ad=_WX_MISS_AD.get(w, "添一两件相应之物"))
    if hit:
        return hit
    hint, ad = _ZERO_TEXT[w]
    return (
        _pick([
            "全盘 %d 个图标，无一个属%s" % (total, w),
            "%d 件之中，属%s者一件也无" % (total, w),
        ], total % 2),
        "%s。五行贵流通，一行全缺则局有所偏，然非必凶。" % hint,
        "若想补%s气，%s不必刻意，添上就够。" % (w, ad),
    )


def bianque_full(w: str, n: int, share: float) -> tuple[str, str, str]:
    hit = phrases_pool.pick(
        "bianque.full", w=w, n=n, share_pct="%.0f%%" % (share * 100),
        w_role=_WX_ROLE.get(w, "这一路"),
        w_risk=_WX_RISK.get(w, "一行独旺而它行受制"),
        w_full_ad=_WX_FULL_AD.get(w, "移走一部分同类"))
    if hit:
        return hit
    hint, ad = _FULL_TEXT[w]
    return (
        _pick([
            "属%s的图标 %d 个，占全盘 %.0f%%" % (w, n, share * 100),
            "%s类共 %d 件，已占 %.0f%%" % (w, n, share * 100),
        ], n % 2),
        "%s。一行独旺则它行受制，旺者未必吉，过则成滞。" % hint,
        ad + "令五行复归均平，不必清空。",
    )


SOURCE_NOTE = classify.SOURCE_LABEL


# ---------------------------------------------------------------- 形态（含新维度）

def _form_kw(align_ratio: float, occupied: int, zone_n: int,
             total: int) -> dict:
    """形态三项的公共占位符值（池子与旧文案共用同一套口径）。"""
    return {
        "occupied": occupied,
        "pct": round(align_ratio * 100),
        "zone_n": zone_n,
        "zone_txt": ("盘心空着" if zone_n == 0 else "盘心压着 %d 个" % zone_n),
        # 中宫本就宜空，空宫只数外八宫
        "empty_n": max(0, 8 - occupied),
    }


def form(align_ratio: float, occupied: int, zone_n: int, total: int,
         worst: str) -> tuple[str, str, str]:
    """形态诊断（计分部分：对齐／周流／中庭留白）。中轴与重心另有独立条目。"""
    pct = round(zone_n / total * 100) if total else 0
    kw = _form_kw(align_ratio, occupied, zone_n, total)
    kw["ev"] = "%d 宫有图标，%d%% 落在整齐网格上" % (
        occupied, round(align_ratio * 100))
    if zone_n:
        kw["ev"] += "；盘心一带压着 %d 个（占 %d%%）" % (zone_n, pct)
    hit = phrases_pool.pick(
        {"zone": "form.bad.zone", "align": "form.bad.align"}
        .get(worst, "form.bad.flow"), **kw)
    if hit:
        return hit
    ev = "%d 宫有图标，%d%% 落在整齐网格上" % (occupied, round(align_ratio * 100))
    if zone_n:
        ev += "；盘心一带压着 %d 个（占 %d%%）" % (zone_n, pct)

    if worst == "zone":
        pr = _pick([
            "盘心一带被占，四周反而空着。桌面该是「外实内虚」——"
            "四周有落处，中间空出来露壁纸；中心一堆，眼睛没处放，手也没处落。",
            "中庭是留白的地方，不是堆放的地方。中间一塞，整张盘就没了疏密。",
        ], zone_n % 2)
        ad = "把盘心那几个往外圈挪，贴着屏幕边排——中间空出来，反而好看也好找。"
    elif worst == "align":
        pr = _pick([
            "整则气顺，乱则气散。参差散落，看的时候眼睛没处落，心神也难定。",
            "不成行不成列，气就没有轨道可循，只能乱撞。",
        ], occupied % 2)
        ad = "开「对齐到网格」，把手拖过的几个归位。"
    else:
        pr = _pick([
            "气贵周流。只占几宫，等于把半张棋盘让出去，那几方之事皆无依托。",
            "宫空则气不至。空得多了，遇事只能拿现成的那几样去顶。",
        ], occupied % 2)
        ad = "把外圈的两三个图标挪到空宫，令宫中皆有其物。"
    return ev, pr, ad


def form_good(align_ratio: float, occupied: int, zone_n: int,
              total: int) -> tuple[str, str, str]:
    ev = "%d 宫有图标，%d%% 落网格" % (occupied, round(align_ratio * 100))
    if zone_n == 0:
        ev += "，盘心一片干净"
    elif zone_n:
        ev += "，盘心仅 %d 个" % zone_n
    kw = _form_kw(align_ratio, occupied, zone_n, total)
    kw["ev"] = ev
    hit = phrases_pool.pick("form.good", **kw)
    if hit:
        return hit
    return (ev,
            "四周有物、中间空着，成行成列而不塞——这就是形法说的「外实内虚」，"
            "既有落处，又有回旋。",
            "保持。往后加图标时，别往盘心长就行。")


def _lean_dir(gx: float, gy: float) -> str:
    h = "左" if gx < 0.5 else "右"
    v = "上" if gy < 0.5 else "下"
    if abs(gx - 0.5) < 0.06:
        return v
    if abs(gy - 0.5) < 0.06:
        return h
    # 中文习惯「左上／右下」，横在前；原来返回「上左」读着别扭
    return h + v


def form_mild(align_ratio: float, occupied: int, zone_n: int, total: int,
              worst: str) -> tuple[str, str, str]:
    """形态大体得宜，只有一处略欠——不能拿「得宜」当结论，也不能当忌说。"""
    ev = "%d 宫有图标，%d%% 落网格" % (occupied, round(align_ratio * 100))
    if zone_n:
        ev += "，盘心压着 %d 个" % zone_n
    kw = _form_kw(align_ratio, occupied, zone_n, total)
    kw["ev"] = ev
    hit = phrases_pool.pick(
        {"zone": "form.mild.zone", "align": "form.mild.align"}
        .get(worst, "form.mild.flow"), **kw)
    if hit:
        return hit

    if worst == "zone":
        return (ev,
                "大体齐整，只是盘心还压着几个。往外挪一挪就顺眼了。",
                "把盘心那几个贴到最近的外圈，中间就空出来了。")
    if worst == "align":
        return (ev,
                "大体成行，只几个歪着。整则气顺，歪几个只是不利索。",
                "补开「对齐到网格」，把拖过的几个归位。")
    return (ev,
            "格局铺得开，只是空的宫略多。宫空则那一方之事薄，不算大碍。",
            "顺手把两三个图标挪到空宫，气就更周流了。")
def axis_note(axis_n: int, total: int) -> tuple[str, str, str]:
    ratio = axis_n / max(1, total)
    hit = phrases_pool.pick(
        "axis.none" if axis_n == 0 else
        ("axis.light" if ratio < 0.08 else "axis.heavy"),
        axis_n=axis_n, total=total,
        axis_pct="%.0f%%" % (ratio * 100))
    if hit:
        return hit
    if axis_n == 0:
        return (
            "屏幕正中的竖向空带未被占用",
            "中轴是视野的主心骨。轴上空着，看东西才不费劲。",
            "保持中轴清空。",
        )
    ratio = axis_n / max(1, total)
    if ratio < 0.08:
        return (
            "中轴上落着 %d 个图标" % axis_n,
            "轴上有物，视线每次扫过都先撞一下。数量不多，属小碍。",
            "把中轴那几个挪到两侧，一格的代价换一条通途。",
        )
    return (
        "中轴上压着 %d 个图标，占全盘 %.0f%%" % (axis_n, ratio * 100),
        "中轴受压，主自身的位置被外物占着——不是没地方，是正中间被堵了。",
        "清空屏幕中间那条竖带，这是最快见效的一处。",
    )


def balance_note(off: float, gx: float, gy: float) -> tuple[str, str, str]:
    d = _lean_dir(gx, gy)
    hit = phrases_pool.pick(
        "balance.center" if off < 0.08 else
        ("balance.light" if off < 0.18 else "balance.heavy"),
        off="%.2f" % off, dir=d)
    if hit:
        return hit
    if off < 0.08:
        return (
            "图标重心距盘心 %.2f，几在正中" % off,
            "重心稳，则事有根。这是不显眼但实在的好处。",
            "不必调。",
        )
    if off < 0.18:
        return (
            "图标重心偏%s，距盘心 %.2f" % (d, off),
            "略偏而已。人坐着看会下意识往另一侧找平衡，久了肩颈先累。",
            "往反方向补两三个，或把%s侧移掉几个。" % d,
        )
    return (
        "图标重心偏%s，距盘心达 %.2f" % (d, off),
        "重心偏得厉害，全局头重脚轻。形法贵稳，偏则做事总要先找平衡。",
        "不必重排，把%s侧最外那一列整体往中间挪一格即可。" % d,
    )


def corner_note(empty_corners: int, corner_names: list[str]) -> tuple[str, str, str]:
    hit = phrases_pool.pick(
        "corner.full" if empty_corners == 0 else
        ("corner.part" if empty_corners <= 2 else "corner.empty"),
        corner_n=empty_corners, names="、".join(corner_names))
    if hit:
        return hit
    if empty_corners == 0:
        return (
            "四隅皆有物，局有四维",
            "四角为四维，隅中有物则局有根基，退有可守。",
            "不必动。",
        )
    if empty_corners <= 2:
        return (
            "四隅之中，%s空着" % "、".join(corner_names),
            "四隅主根基与退路。空一两角无妨，只那一方之事略显薄。",
            "不必刻意补，若正好有该归于那一方的物件，放过去即可。",
        )
    return (
        "四隅全空，%s 都无图标" % "、".join(corner_names),
        "四隅全虚，局就没有四维。四角空虚者，做事有进无守，"
        "来得快也散得快。",
        "往两个对角各放一两件，先把四维立起来。",
    )


# ---------------------------------------------------------------- 第二批观察

def density_note(gua: str, n: int, frac: float) -> tuple[str, str, str]:
    """宫内疏密：该宫虽有物，却只占了本宫一小块。"""
    hit = phrases_pool.pick(
        "density.wide" if frac >= 0.45 else
        ("density.half" if frac >= 0.25 else "density.corner"),
        gua=gua, n=n, frac_pct="%.0f%%" % (frac * 100))
    if hit:
        return hit
    if frac >= 0.45:
        return (
            "%s宫 %d 个图标，铺占本宫约 %.0f%% 的面积" % (gua, n, frac * 100),
            "宫中有物而铺得开，气便走得匀。这是不显眼的好处。",
            "不必动。",
        )
    if frac >= 0.25:
        return (
            "%s宫 %d 个图标，只占了本宫约 %.0f%% 的面积" % (gua, n, frac * 100),
            "物聚于宫中一隅。这一宫算是有了主，可余处仍虚，气只到一半。",
            "若正好有该归这一方的物件，往外摊开半格即可。",
        )
    return (
        "%s宫 %d 个图标，全挤在本宫约 %.0f%% 的一角" % (gua, n, frac * 100),
        "宫是有了，气没进满。好比一间屋子只在门口堆了东西，里面仍是空的——"
        "看着有人住，其实没用起来。",
        "把这一宫的图标散开，占满中间三分之二，气才立得住。",
    )


def cluster_note(wall_desc: str, island_desc: str) -> tuple[str, str, str]:
    """簇分析：成墙与孤岛。"""
    if wall_desc or island_desc:
        hit = phrases_pool.pick(
            "cluster.both" if (wall_desc and island_desc) else
            ("cluster.wall" if wall_desc else "cluster.island"),
            wall=wall_desc, island=island_desc)
        if hit:
            return hit
    if wall_desc and island_desc:
        return (
            "%s；另有%s" % (wall_desc, island_desc),
            "墙则气不能穿，岛则气无所依。一边堵一边散，全局就没有一段是顺的。",
            "先拆墙（把成墙那几列各自让出一列空档），再收岛（把孤立的归到近处）。",
        )
    if wall_desc:
        return (
            wall_desc,
            "连成一片即成墙。墙一起，气就穿不过去，只能从墙外绕——"
            "绕得远了，事就慢。",
            "在墙中间让出一列空档，气有了门，两侧也都活了。",
        )
    if island_desc:
        return (
            island_desc,
            "孤岛看似清爽，实则气无所依。散得太开，就聚不住。",
            "把孤立的几件并到最近的一片里去，不必整齐，先聚起来。",
        )
    return ("", "", "")


def three_bands(tian: int, ren: int, di: int) -> tuple[str, str, str]:
    """三才：上为天（愿景）、中为人（日常）、下为地（根基）。"""
    total = max(1, tian + ren + di)
    ev = "上带（天）%d 个，中带（人）%d 个，下带（地）%d 个" % (tian, ren, di)
    if tian + ren + di == 0:
        return ("", "", "")
    hit = phrases_pool.pick(
        "bands.no_root" if di == 0 else
        ("bands.sky_heavy" if tian > di * 2 else
         ("bands.earth_heavy" if di > tian * 2 else "bands.even")),
        tian=tian, ren=ren, di=di, total=tian + ren + di)
    if hit:
        return hit
    if di == 0:
        return (
            ev,
            "下带一个也无，等于无根。天再高，人再忙，底下没有东西托着——"
            "这是最虚的一种格局。",
            "往下带放三五个最常用、最基础的东西，先把根立住。",
        )
    if tian > di * 2:
        return (
            ev,
            "天重地轻，头重脚轻。上带主愿景与念头，下带主根基与旧事；"
            "念头多而根基薄，想得多、落得少。",
            "把上带的一批往下带挪，或干脆清掉——想法太多时，减比加有用。",
        )
    if di > tian * 2:
        return (
            ev,
            "地重天轻，根厚而念少。稳是稳的，只是上面空着，缺个往前看的位置。",
            "不必大改；若近期有事要谋，往上带放一两件相关的。",
        )
    return (
        ev,
        "三才大致均分，天不压地、地不埋人。这是难得的匀。",
        "保持。",
    )


def kind_mix(n_file: int, n_dir: int, n_virtual: int) -> tuple[str, str, str]:
    """图标类型构成：散件多还是归拢多。"""
    n = n_file + n_dir
    ev = "文件 %d 个、文件夹 %d 个、系统项 %d 个" % (n_file, n_dir, n_virtual)
    if n == 0:
        return (ev, "盘上几乎只有系统项，谈不上整理。", "先放几个自己常用的。")
    ratio = n_dir / n
    kw = dict(n_file=n_file, n_dir=n_dir, n_virtual=n_virtual,
              dir_pct="%.0f%%" % (ratio * 100))
    if n == 0:
        hit = phrases_pool.pick("mix.system_only", **kw)
    elif ratio == 0 and n_file >= 8:
        hit = phrases_pool.pick("mix.no_dir", **kw)
    elif ratio < 0.15 and n_file >= 8:
        hit = phrases_pool.pick("mix.few_dir", **kw)
    elif ratio > 0.5:
        hit = phrases_pool.pick("mix.dir_heavy", **kw)
    else:
        hit = phrases_pool.pick("mix.half", **kw)
    if hit:
        return hit
    if ratio == 0 and n_file >= 8:
        return (
            ev,
            "一件文件夹也没有，全是散件。散件是「还没决定放哪」的东西——"
            "它们不是没整理，是压根没被归类过。",
            "先建三五个文件夹（工作／素材／工具／归档），把一半散件塞进去。",
        )
    if ratio < 0.15 and n_file >= 8:
        return (
            ev,
            "文件夹极少，散件占绝大多数。这类盘看着没几样，实则每一样都要单独记。",
            "按用途归几个夹子，剩下的留在盘上也就不乱了。",
        )
    if ratio > 0.5:
        return (
            ev,
            "以文件夹为主，善于归拢。收得住，是好事；只是别再往夹子里无限塞。",
            "保持。每隔一两月翻一翻最深的那几个夹子。",
        )
    return (
        ev,
        "散件与文件夹参半，属于边走边整的状态。",
        "继续；把最上面那几件散件顺手归位就好。",
    )

def synthesis(center_empty: bool, hall_n: int, baihu_up: bool,
              has_clutter: bool, occupied: int, zero_w: list[str]) -> tuple[str, str]:
    """把两三条事实合起来看，给一句单独的判断。这是单看任何一条都得不到的。"""
    # 这一项只出「断语 + 理」两句，池子条目第三段恒为空
    kw = dict(hall_n=hall_n, occupied=occupied, zero_w="、".join(zero_w))
    if center_empty and hall_n >= 6:
        key = "synth.center_hall"
    elif not center_empty and hall_n <= 4:
        key = "synth.hall_open_center_full"
    elif baihu_up and has_clutter:
        key = "synth.baihu_clutter"
    elif baihu_up and zero_w:
        key = "synth.baihu_zero"
    elif center_empty and occupied <= 5 and hall_n <= 4:
        key = "synth.all_empty"
    elif has_clutter and occupied >= 6 and hall_n <= 4:
        key = "synth.hall_ok_clutter"
    elif not zero_w and center_empty and not has_clutter:
        key = "synth.best"
    elif zero_w and occupied >= 6:
        key = "synth.zero_wide"
    else:
        key = None
    if key:
        hit = phrases_pool.pick(key, **kw)
        if hit:
            return hit[0], hit[1]
    if center_empty and hall_n >= 6:
        return (
            "中宫虚而明堂塞：心是静的，路是堵的",
            "气枢留得住，说明你人不慌；可出口堵着，这份静就使不出去——"
            "属于有心而路窄，比心乱更难自察。",
        )
    if not center_empty and hall_n <= 4:
        return (
            "中宫塞而明堂通：前方是开的，你自己坐在一堆东西上",
            "外头的路并不窄，是身上带的太多。这一类不必改环境，先减自己的负担。",
        )
    if baihu_up and has_clutter:
        return (
            "白虎抬头而杂物满盘：外缘耗神，内里也不清",
            "两头一起漏。这种局面最忌讳同时动手——先清内，外头的纷扰会自己少一半。",
        )
    if baihu_up and zero_w:
        return (
            "白虎抬头而%s气全无：外面的事压过来，手里却少一件应对之物" % zero_w[0],
            "不是能力不够，是工具不凑手。补上那一类，局面立刻不同。",
        )
    if center_empty and occupied <= 5 and hall_n <= 4:
        return (
            "中宫与明堂皆虚，气路是通的",
            "可用的宫少，等于路通而人少——不堵，但也不旺。属于底子干净、尚待添置。",
        )
    if has_clutter and occupied >= 6 and hall_n <= 4:
        return (
            "明堂通而杂物多：路开着，脚边全是东西",
            "这一类最可惜——本来走得动，却被脚边绊住。清一轮就能见效，成本最低。",
        )
    if not zero_w and center_empty and not has_clutter:
        return (
            "中宫虚、五行全、杂物净：三样都占住了",
            "这是底子最好的组合。剩下的不是改，是守——守住这三样，别的差一点也无妨。",
        )
    if zero_w and occupied >= 6:
        return (
            "五行缺%s，而九宫已占 %d 宫" % ("、".join(zero_w), occupied),
            "铺得开，却偏了一路。局面大而不全，遇事总有一样拿不出来。",
        )
    return ("", "")


# ---------------------------------------------------------------- 顺手度
# 2026-10-27 新增。这一项**不用风水词**：它算的是鼠标行程与分类，
# 说「找东西少走两步」比说「气机顺」更诚实。


def comfort(c: dict) -> tuple[str, str, str, str, str]:
    """顺手度诊断。返回 (现象, 理, 改, key, level)。

    文案按得分三档，同时按「最弱的那一项」给具体动作——
    不写"建议优化布局"这种废话。
    """
    s = c["score"]
    st = c["stats"]
    subs = c["subs"]

    bits: list[str] = []
    if subs["hot"] >= 4.5:
        bits.append("常用的多在三边顺手位（顶、左、右）")
    elif subs["hot"] <= 2.0 and st["common"] >= 3:
        bits.append("常用的有 %d 个散在冷区，用一次要绕一次"
                    % (st["common"] - st["hot_n"]))
    if st["archive"]:
        if subs["cold"] >= 3.2:
            bits.append("%d 件归档物压在底边" % st["archive"])
        elif subs["cold"] <= 1.5:
            bits.append("%d 件归档物还占着顺手位" % st["archive"])
    if subs["cluster"] >= 3.0:
        bits.append("%d 个同类聚成了块" % st["cover"])
    if subs["center"] <= -2.0:
        bits.append("正中一格堆了 %d 个" % st["center_n"])
    if subs["crowd"] < 0:
        bits.append("最挤的一宫有 %d 个" % st["busiest"])

    ev = "；".join(bits) + "。" if bits else "常用与归档各在其位，没什么要挑的。"

    # 最弱的一项 → 具体动作
    weak = min(subs.items(), key=lambda kv: kv[1])[0]
    actions = {
        "hot": "把每天都要点的三五个挪到顶行或左右两列，其余往中间收。",
        "cold": "把安装包、压缩包、种子这类收进一个文件夹，或统一下沉到底边。",
        "cluster": "同类的放成一竖排（同一列连着），比散着更容易扫到。",
        "center": "正中那一格清空——那里最容易误点，也最挡壁纸。",
        "crowd": "最挤那一宫挑两三件挪去空宫，别让一格压过十个。",
    }
    ad = actions.get(weak, "先挑最常用的五个，确认它们都在手边。")

    if s >= 17:
        return (
            ev,
            "顺手这一项算的不是吉凶，是步数：常用在手边、归档在远端，"
            "每次找东西都少走一段路，这种省是每天都在兑现的。",
            "保持就行。" + (ad if weak != "hot" else ""),
            "顺手合意", "吉",
        )
    if s >= 12:
        return (
            ev,
            "整体能用，但有几处每天要多走一步。单个不碍事，累起来就是消耗——"
            "布局的好坏常常不体现在某一件上，而在重复次数最多的那条路径上。",
            ad,
            "尚可，有得调", "平",
        )
    return (
        ev,
        "常用和归档混在一起时，每次找东西都要先判断「这是哪一类」；"
        "这个判断本身最耗神，比走得远更累。",
        ad, "别手", "忌",
    )
