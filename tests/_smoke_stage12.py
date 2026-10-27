# -*- coding: utf-8 -*-
"""阶段十三冒烟：诊断说法池（每分支多组同义、每次分析随机）。

覆盖范围随批次增长：本测试只断言"池子里已有的分支"，未覆盖的分支走旧文案也不算错。
第二批：四象 9 分支 + 形态 7 分支（形态顶替了已废弃的「聚散」）。
"""
import json
import sys
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import classify  # noqa: E402
import fengshui  # noqa: E402
import phrases  # noqa: E402
import phrases_pool  # noqa: E402

DESC_PREFIX = ("axis.", "balance.", "corner.", "density.", "cluster.",
               "bands.", "mix.", "synth.")

print("[1] 池子：判断类 ≥10 组、述类 ≥4 组，模板都能填")

sizes = phrases_pool.sizes()
assert sizes, "池子是空的"
short = {k: v for k, v in sizes.items()
         if v < (4 if k.startswith(DESC_PREFIX) else 10)}
assert not short, "分支组数不足：%s" % short
jud = [k for k in sizes if not k.startswith(DESC_PREFIX)]
shu = [k for k in sizes if k.startswith(DESC_PREFIX)]
print("[ok] %d 个分支（判断 %d ×10、述 %d ×4），共 %d 组"
      % (len(sizes), len(jud), len(shu), sum(sizes.values())))

SAMPLES = {
    "center.empty.low": dict(total=8),
    "center.empty.mid": dict(total=30),
    "center.empty.high": dict(total=60),
    "center.press.one": dict(n=1, names="甲、乙", first="甲",
                             target="坎宫（北）"),
    "center.press.small": dict(n=3, names="甲、乙、丙", first="甲",
                               target="坎宫（北）"),
    "center.press.big": dict(n=5, names="甲、乙、丙", first="甲",
                             target="坎宫（北）"),
    "hall.block.light": dict(n=6, gua="离", avg=2.0, ratio=3.0, move_n=3,
                             first="甲", target="兑宫（西）"),
    "hall.block.mid": dict(n=12, gua="离", avg=2.0, ratio=6.0, move_n=6,
                           first="甲", target="兑宫（西）"),
    "hall.block.heavy": dict(n=18, gua="离", avg=2.0, ratio=9.0, move_n=8,
                             first="甲", target="兑宫（西）"),
    "hall.open.none": dict(gua="离", n=0),
    "hall.open.some": dict(gua="离", n=2),
    # ---- 四象
    "sides.baihu.light": dict(nl=20, nr=23, diff=3, sample="甲"),
    "sides.baihu.mid": dict(nl=18, nr=25, diff=7, sample="甲"),
    "sides.baihu.heavy": dict(nl=10, nr=26, diff=16, sample="甲"),
    "sides.qinglong.strong": dict(nl=24, nr=4, ratio=6.0),
    "sides.qinglong.alone": dict(nl=30, nr=2, ratio=15.0),
    "sides.both_empty": dict(total=46),
    "sides.good.no_right": dict(nl=22, nr=0, ratio=22.0),
    "sides.good.left_wide": dict(nl=24, nr=8, ratio=3.0),
    "sides.good.balanced": dict(nl=14, nr=11, ratio=1.3),
    # ---- 形态（ev/zone_txt 由 phrases.form* 拼好后传进来）
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
                          ev="6 宫有图标，88% 落在整齐网格上；盘心一带压着 9 个"),
    "form.bad.align": dict(occupied=7, pct=41, zone_n=1, empty_n=1,
                           zone_txt="盘心压着 1 个",
                           ev="7 宫有图标，41% 落在整齐网格上；盘心一带压着 1 个"),
    "form.bad.flow": dict(occupied=3, pct=100, zone_n=0, empty_n=5,
                          zone_txt="盘心空着",
                          ev="3 宫有图标，100% 落在整齐网格上"),
    # ---- 杂物
    "clutter.dirty": dict(n=5, cap=7, names="「甲」「乙」「丙」",
                          kind_word="安装包"),
    "clutter.clean": dict(),
    # ---- 生克
    "wuxing.block": dict(gua="离", gw="火", count=9, bad=4, net_txt="-2.5",
                         kind_word="客克主", kind_tip="物反过来克宫",
                         kind_ad="把克本宫的那几类移出本宫",
                         names="「甲」「乙」", icon_wx="水"),
    "wuxing.ok.positive": dict(net_txt="+2.6"),
    "wuxing.ok.neutral": dict(net_txt="-0.2"),
    # ---- 偏枯
    "bianque.missing": dict(w="木", total=46, w_role="文思",
                            w_miss_ad="添一两件文书类入盘"),
    "bianque.full": dict(w="木", n=20, share_pct="43%", w_role="文思",
                         w_risk="文思过盛而落地不足",
                         w_full_ad="移走一部分文书类"),
    # ---- 述类：中轴 / 重心 / 四隅 / 疏密
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
    # ---- 述类：成墙与孤岛
    "cluster.both": dict(wall="左侧有 3 列连成一道墙", island="右下有一处孤岛"),
    "cluster.wall": dict(wall="左侧有 3 列连成一道墙", island=""),
    "cluster.island": dict(wall="", island="右下有一处孤岛"),
    # ---- 述类：三才
    "bands.no_root": dict(tian=30, ren=16, di=0),
    "bands.sky_heavy": dict(tian=30, ren=10, di=6),
    "bands.earth_heavy": dict(tian=6, ren=10, di=30),
    "bands.even": dict(tian=16, ren=15, di=15),
    # ---- 述类：器类构成
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
    SAMPLES[_k] = dict(hall_n=12, occupied=7, zero_w="木")
for key in sizes:
    assert key in SAMPLES, "新增分支 %s 没给测试样本" % key

for key, kw in SAMPLES.items():
    seen = set()
    # 抽 200 次：10 组里漏 1 组的概率 (0.9)^200 ≈ 7e-10，可以忽略；
    # 原来抽 80 次时约 2% 概率漏一组（80 个分支累计），会偶发误报。
    for _ in range(200):
        hit = phrases_pool.pick(key, **kw)
        assert hit, key
        # 局之总象只出两句（断语 + 理），第三段本来就是空
        segs = hit[:2] if key.startswith("synth.") else hit
        assert all(s.strip() for s in segs), (key, hit)
        assert "{" not in "".join(hit), "模板占位符没填干净：%s" % (hit,)
        # names 本身已带「」，模板再包一层就会出现「「甲」」这种双引号
        assert not any("「「" in t or "」」" in t for t in hit), \
            "引号嵌套：%s" % (hit,)
        seen.add(hit)
    assert len(seen) == sizes[key], \
        "%s 抽了 200 次只出现 %d 种（应 %d）" % (key, len(seen), sizes[key])
print("[ok] 每分支 200 次抽取都覆盖全部组数，占位符无残留")

print("[2] 端到端：同一张桌面，多次分析说法会变")

lay = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json")
                 .read_text(encoding="utf-8"))
classify.apply_wuxing(lay)

WANT = ("中宫空", "中宫受压", "明堂壅塞", "明堂开阔", "白虎抬头",
        "青龙过旺", "青龙得势", "左右皆空", "形态得宜", "形态小瑕",
        "中庭受压", "排列散乱", "气不周流", "杂物压盘", "五行相碍",
        # 述类：不打分，只描述
        "中轴观", "重心观", "四隅观", "宫内疏密", "成墙与孤岛",
        "三才", "器类构成", "局之总象")
texts = {}
for _ in range(10):
    res = fengshui.analyze(lay, 180)
    for d in res["diagnoses"]:
        if d["key"] in WANT:
            texts.setdefault(d["key"], set()).add(d["evidence"])
assert texts, "这张桌面没触发判断类诊断，换一张再测"
changed = {k: len(v) for k, v in texts.items()}
assert any(n > 1 for n in changed.values()), \
    "10 次分析说法完全没变：%s" % changed
SHU_KEYS = ("中轴观", "重心观", "四隅观", "宫内疏密",
            "成墙与孤岛", "三才", "器类构成", "局之总象")
shu_changed = {k: n for k, n in changed.items() if k in SHU_KEYS}
assert any(n > 1 for n in shu_changed.values()), \
    "述类 10 次分析说法没变：%s" % shu_changed
print("[ok] 判断类有变化：%s"
      % {k: n for k, n in changed.items() if k not in SHU_KEYS})
print("[ok] 述类有变化：%s" % shu_changed)

print("[3] 四象/形态：池子里的分支确实被走通了")

# 直接调函数而不是 pick：确认接线正确（命中池子时会计数增加）
sides = {phrases.sides_good(24, 8, 3.0)[0] for _ in range(20)}
assert len(sides) > 1, "青龙得势没走池子（20 次只出一种）"
evs = {phrases.form_good(1.0, 7, 0, 46)[0] for _ in range(20)}
assert len(evs) > 1, "形态得宜没走池子（20 次只出一种）"
print("[ok] 青龙得势 %d 种 / 形态得宜 %d 种（各 20 次）" % (len(sides), len(evs)))

# 桌面未触发的分支（洁净 / 偏枯 / 生克相安）直接调函数验证接线
for name, fn, kw in (
        ("盘面洁净", phrases.clutter_clean, {}),
        ("缺木", phrases.bianque_missing, dict(w="木", total=46)),
        ("木过旺", phrases.bianque_full, dict(w="木", n=20, share=0.43)),
        ("生克相安(+)", phrases.wuxing_ok, dict(net=2.6)),
        ("生克相安(0)", phrases.wuxing_ok, dict(net=-0.2)),
        ("中轴观", phrases.axis_note, dict(axis_n=6, total=46)),
        ("重心观", phrases.balance_note, dict(off=0.27, gx=0.3, gy=0.35)),
        ("四隅观", phrases.corner_note,
         dict(empty_corners=1, corner_names=["乾宫（右下·金）"])),
        ("宫内疏密", phrases.density_note, dict(gua="艮", n=6, frac=0.06)),
        ("成墙与孤岛", phrases.cluster_note,
         dict(wall_desc="左侧有墙", island_desc="")),
        ("三才", phrases.three_bands, dict(tian=30, ren=10, di=6)),
        ("器类构成", phrases.kind_mix,
         dict(n_file=37, n_dir=4, n_virtual=5)),
):
    got = {fn(**kw)[0] for _ in range(20)}
    assert len(got) > 1, "%s 没走池子（20 次只出一种）" % name
    print("     %s %d 种" % (name, len(got)))

print("[4] 未覆盖的分支仍走旧文案（回落不报错）")

assert phrases_pool.pick("no.such.branch") is None
for _ in range(5):
    ev, pr, ad = phrases.clutter_dirty(4, "installer", ["甲", "乙"], 6)
    assert ev and pr and ad
print("[ok] 未进池的分支回落正常")

print("\n阶段十三冒烟测试全部通过")
