# -*- coding: utf-8 -*-
"""阶段三冒烟测试：归类、生克、评分对账、窗口构造。全程不显示窗口。"""
import json
import sys
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import classify  # noqa: E402
import fengshui  # noqa: E402

RAW = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json").read_text(encoding="utf-8"))


def fresh():
    return json.loads(json.dumps(RAW))


# ---------------- 1. 归类规则 ----------------
cases = [
    ({"name": "xx-setup.exe", "ext": ".exe", "kind": "file"}, "土", "安装包→土"),
    ({"name": "android-studio-quail3-windows.exe", "ext": ".exe", "kind": "file"},
     "土", "安装包优先于语义(studio)"),
    ({"name": "某文件夹", "ext": "", "kind": "dir"}, "土", "文件夹→土"),
    ({"name": "[x] loot", "ext": ".url", "kind": "file"}, "水", ".url→水"),
    ({"name": "笔记.txt", "ext": ".txt", "kind": "file"}, "木", ".txt→木"),
    ({"name": "电影.mp4", "ext": ".mp4", "kind": "file"}, "火", ".mp4→火"),
    ({"name": "某加速器", "ext": ".lnk", "kind": "file"}, "水", "加速器→水"),
    ({"name": "回收站", "ext": "", "kind": "virtual"}, "土", "回收站→土"),
    ({"name": "此电脑", "ext": "", "kind": "virtual"}, "金", "此电脑→金"),
    ({"name": "无名", "ext": "", "kind": "virtual"}, "金", "未知虚拟项→金"),
]
for icon, want, why in cases:
    got = classify.classify(icon)[0]
    assert got == want, "%s 期望 %s 实际 %s" % (why, want, got)
print("[ok] 归类规则 %d 条全部通过" % len(cases))

# ---------------- 2. 生克关系 ----------------
rel_cases = [
    ("水", "木", "生入"), ("木", "土", "克入"), ("木", "水", "泄气"),
    ("木", "木", "比和"), ("木", "金", "主克客"),
]
for iw, pw, want in rel_cases:
    got = fengshui.relation(iw, pw)[0]
    assert got == want, "%s 对 %s 应为 %s，实为 %s" % (iw, pw, want, got)
print("[ok] 生克关系 %d 条全部通过" % len(rel_cases))

# ---------------- 3. 评分对账 ----------------
for ang in (180, 90, 225, 0):
    res = fengshui.analyze(fresh(), ang)
    assert 0 <= res["score"] <= 100
    assert len(res["sections"]) == 7, "七项评分缺失"
    sub = sum(s["max"] - s["score"] for s in res["sections"].values())
    assert abs(sub - res["deduct_total"]) < 0.05, "分项与合计对不上"
    assert abs(100 - res["deduct_total"] - res["score"]) <= 1, "总分对账失败"
    for d in res["diagnoses"]:
        assert d["evidence"].strip(), "[%s] 缺现象" % d["key"]
        assert d["principle"].strip(), "[%s] 缺原理" % d["key"]
        assert d["advice"].strip(), "[%s] 缺改法" % d["key"]
        assert d["level"] in ("忌", "平", "吉", "述")
    assert res["stats"]["occupied"] + len(res["stats"]["empty"]) == 8, \
        "八宫（不含中宫）划分不平"
print("[ok] 四个朝向的评分对账、四要素齐全")

res = fengshui.analyze(fresh(), 180)
print("     总分 %d ｜ %s" % (res["score"], res["grade"]))
for s in res["sections"].values():
    print("     %s %.1f/%d" % (s["name"], s["score"], s["max"]))

# ---------------- 4. 中宫为空时必须是满分 ----------------
assert res["stats"]["center"] == 0
assert res["sections"]["center"]["score"] == res["sections"]["center"]["max"], \
    "中宫空却没给满分"
assert sum(s["max"] for s in res["sections"].values()) == 100, \
    "七项满分合计应为 100"
print("[ok] 中宫空 → 满分；七项满分合计 100")

# ---------------- 4b. 顺手度：边界必须能被扣到 ----------------
def _mk(name, row, col, kind="file", ext="lnk"):
    return {"name": name, "row": row, "col": col, "kind": kind, "ext": ext}


def _pack(icons, clutter=None):
    cells = {(r, c): [] for r in range(3) for c in range(3)}
    for it in icons:
        cells[(it["row"], it["col"])].append(it)
    counts = {k: len(v) for k, v in cells.items()}
    return fengshui.comfort(icons, cells, counts, clutter or [])


# ① 中宫堆三个 → 扣满 5
cf = _pack([_mk("a", 1, 1), _mk("b", 1, 1), _mk("c", 1, 1),
            _mk("d", 0, 0)])
assert cf["subs"]["center"] == -5.0, cf["subs"]
# ② 某宫挤过 12 → 开始扣（13 个图标同宫）
assert _pack([_mk("x%d" % i, 0, 1) for i in range(13)])["subs"]["crowd"] == -1.0
# ③ 归档物全在顺手位 → 冷区 0 分
tor = [_mk("a.torrent", 0, 0, ext="torrent"), _mk("b.zip", 0, 1, ext="zip")]
assert _pack(tor)["subs"]["cold"] == 0.0
# ④ 归档物全在底边 → 冷区满分
tor2 = [_mk("a.torrent", 2, 0, ext="torrent"), _mk("b.zip", 2, 1, ext="zip")]
assert _pack(tor2)["subs"]["cold"] == 4.0
# ⑤ 左右两列全空 → 四象扣 6
lay_side = fresh()
for i, it in enumerate(lay_side["icons"]):
    it["cx"] = 0.5
res_side = fengshui.analyze(lay_side, 180)
assert res_side["sections"]["sides"]["score"] == 6, res_side["sections"]["sides"]
# ⑥ 顺手度总分恒在 0–20
assert 0 <= cf["score"] <= 20
print("[ok] 顺手度：中宫扣满、过挤扣分、归档冷区、四象左右全空，边界都成立")

# ---------------- 4c. 分图标：逐件判定，口径必须与生克一致 ----------------
import pericon  # noqa: E402

_lay = fresh()
_res = fengshui.analyze(_lay, 180)
groups = pericon.build(_lay, _res)
assert groups, "分图标不能为空"
assert sum(g["count"] for g in groups) == len(_lay["icons"]), \
    "每个图标都该归到某一宫"
for g in groups:
    assert 0 <= g["avg"] <= 100, g["avg"]
    assert g["level"] in ("吉", "平", "忌")
    for ic in g["icons"]:
        assert ic["evidence"] and ic["principle"] and ic["advice"]
        assert 15 <= len(ic["evidence"]) <= 80, ic["evidence"]
        if g["center"]:
            assert ic["verdict"] == "最忌"
        else:
            rel, w = fengshui.relation(ic["wuxing"], g["wuxing"])
            assert ic["rel"] == rel, "分图标与生克口径不一致：%s vs %s" % (
                ic["rel"], rel)
            assert abs(ic["rel_score"] - w) < 1e-9
# 摘要行格式
line = pericon.summary_line(groups[0])
assert "宫" in line or "中宫" in line, line
# 4d. 五级判定与图例：颜色必须来自主题，不能写死
import theme as _theme  # noqa: E402

assert len(pericon.LEGEND) == 5, "图例应有五个状态"
for _k in _theme.ORDER:
    _t5 = _theme.get(_k)["tone5"]
    assert set(_t5) == {"best", "good", "mid", "weak", "bad"}, _k
    for _tone, _name, _desc in pericon.LEGEND:
        assert _tone in _t5, "%s 主题缺 %s 色" % (_k, _tone)
for _g in groups:
    for _ic in _g["icons"]:
        assert _ic["tone"] in ("best", "good", "mid", "weak", "bad"), _ic
        assert _ic["verdict"] in [n for _t, n, _d in pericon.LEGEND] + ["最忌"]
print("[ok] 五级判定：%d 个状态 × 4 套主题色齐备，每件图标都带 tone"
      % len(pericon.LEGEND))

print("[ok] 分图标：%d 宫 %d 件全覆盖，关系口径与 fengshui.relation 一致"
      % (len(groups), sum(g["count"] for g in groups)))

# ---------------- 5. 空宫不含中宫 ----------------
assert all("中宫" not in e for e in res["stats"]["empty"]), "空宫列表混入了中宫"
print("[ok] 空宫列表已排除中宫")

# ---------------- 6. 全部图标都有五行 ----------------
lay5 = fresh()
fengshui.analyze(lay5, 180)          # analyze 会就地写入 wuxing
for it in lay5["icons"]:
    assert it["wuxing"] in "木火土金水", "图标 %s 无五行" % it["name"]
print("[ok] 全部 %d 个图标均有五行归属" % len(lay5["icons"]))

# ---------------- 7. 窗口整体构造 ----------------
import main as app_main  # noqa: E402

root = tk.Tk()
root.withdraw()
app = app_main.App(root)
app.analyze()                # 启动闸门：测试里显式触发分析
root.update_idletasks()
root.update()
assert app.result is not None
assert len(app.hits) == len(app.layout["icons"])
print("[ok] 窗口构造成功：%d 个命中框，%d 条诊断"
      % (len(app.hits), len(app.result["diagnoses"])))

app.orient_var.set(render_label := __import__("render").ORIENT_CHOICES[2][1])
app._on_orient(None)
root.update_idletasks()
assert app.result is not None
print("[ok] 切换朝向后重算正常")

# ---------------- 8b. 分图标页：两级折叠能开能合 ----------------
app2 = app_main.App(root)
root.update()
app2.analyze()
root.update()
app2._tab("pericon")
root.update()
assert app2.sub_tab == "pericon"
assert len(app2._picon_groups) > 0
n0 = len(app2.picon_body.winfo_children())
assert n0 > 0, "分图标页没渲染"
# 展开第一宫 → 内容容器被 pack
_c0 = app2.picon_body.winfo_children()[0]
_before = len(_c0.winfo_children()[0].winfo_children())
app2._picon_open.add(0)
app2._fill_pericon()
root.update()
_c0 = app2.picon_body.winfo_children()[0]
_content = [w for w in _c0.winfo_children() if w.winfo_manager()]
assert len(_content) >= 2, "展开后应出现内容容器"
print("[ok] 分图标页：默认折叠、展开第一宫后有图标行")
root.destroy()

print("\n阶段三冒烟测试全部通过")
