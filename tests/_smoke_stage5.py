# -*- coding: utf-8 -*-
"""阶段五冒烟测试：推演只算不改、结果更优、界面切换。全程不显示窗口。"""
import copy
import json
import sys
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import fengshui  # noqa: E402
import project  # noqa: E402

RAW = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json").read_text(encoding="utf-8"))


def fresh():
    return json.loads(json.dumps(RAW))


# ---------------- 1. 只算不改 ----------------
lay = fresh()
snap = copy.deepcopy(lay)
before = fengshui.analyze(lay, 180)
new, moves = project.project(lay, 180)
after = fengshui.analyze(new, 180)

assert all(a["x"] == b["x"] and a["y"] == b["y"]
           for a, b in zip(snap["icons"], lay["icons"])), "原布局被改动了！"
print("[ok] 推演未改动原布局（%d 个图标坐标逐一比对）" % len(lay["icons"]))

assert len(new["icons"]) == len(lay["icons"]), "推演后图标数量变了"
assert sum(1 for i in new["icons"] if i["row"] == 1 and i["col"] == 1) == 0, \
    "推演后中宫仍有图标"
print("[ok] 图标数量不变，中宫已清空")

assert after["stats"]["hall"] <= project.HALL_CAP, "明堂超限"
print("[ok] 明堂 %d 个（上限 %d）" % (after["stats"]["hall"], project.HALL_CAP))

assert after["stats"]["align_ratio"] >= 0.99, \
    "推演后对齐度掉了：%.2f" % after["stats"]["align_ratio"]
print("[ok] 推演后仍 100% 对齐网格")

assert after["score"] >= before["score"], \
    "推演后分数反而降了：%d -> %d" % (before["score"], after["score"])
print("[ok] 分数 %d -> %d（+%d），移动 %d 个"
      % (before["score"], after["score"], after["score"] - before["score"],
         len(moves)))

# 顺手原则：不许把图标扔到远处，也不许摊满九宫
far = [m for m in moves
       if abs(m["to"][0] - m["from"][0]) + abs(m["to"][1] - m["from"][1]) > 2]
assert not far, "有图标被挪太远（不顺手）：%s" % [m["name"] for m in far]
print("[ok] 移动距离均 ≤2 宫（最远不会跑到对角）")

assert after["stats"]["occupied"] <= 8, "推演把图标摊满了九宫：%d 宫" % after["stats"]["occupied"]
print("[ok] 占 %d 宫（未做九宫均摊）" % after["stats"]["occupied"])

# 只补空位：原有未移动的图标坐标必须原样
moved_names = {m["name"] for m in moves}
untouched = [(a, b) for a, b in zip(snap["icons"], new["icons"])
             if a["name"] not in moved_names]
assert all(a["x"] == b["x"] and a["y"] == b["y"] for a, b in untouched), \
    "没被移动的图标也被挪了"
print("[ok] 未移动的 %d 个图标坐标原样保留" % len(untouched))

# ---------------- 2. 各朝向都能推演 ----------------
for ang in (0, 90, 180, 225, 315):
    l = fresh()
    b = fengshui.analyze(l, ang)
    nl, mv = project.project(l, ang)
    a = fengshui.analyze(nl, ang)
    assert a["stats"]["hall"] <= project.HALL_CAP
    assert sum(1 for i in nl["icons"] if i["row"] == 1 and i["col"] == 1) == 0
    assert 0 <= a["score"] <= 100
print("[ok] 五个朝向推演均正常")

# ---------------- 3. 空桌面不崩 ----------------
empty = fresh()
empty["icons"] = []
try:
    project.project(empty, 180)
except Exception as exc:                     # noqa: BLE001
    raise AssertionError("空桌面推演报错：%s" % exc)
print("[ok] 空桌面推演不崩溃")

# ---------------- 4. 界面切换 ----------------
from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402

enable_dpi_awareness()
root = tk.Tk()
root.withdraw()
app = app_main.App(root)
app.analyze()                # 启动闸门：测试里显式触发分析
root.update_idletasks()
root.update()

assert app.mode == "now"
assert app.mode_lbl.cget("text").startswith("现状"), "现状档没有功能说明"
app.set_mode("proj")
root.update_idletasks()
assert app.mode == "proj" and app.proj_result is not None
assert app.score_lbl.cget("text") == str(app.proj_result["score"])
assert "最小调整" in app.mode_lbl.cget("text")
print("[ok] 最小调整：%s 分 ／ 说明「%s」"
      % (app.score_lbl.cget("text"), app.mode_lbl.cget("text")[:24]))

app.set_mode("repack")
root.update_idletasks()
assert app.mode == "repack" and app.rep_result is not None
assert app.score_lbl.cget("text") == str(app.rep_result["score"])
assert "全部重排" in app.mode_lbl.cget("text")
assert app.rep_result["stats"]["zone_n"] <= app.result["stats"]["zone_n"] + 1
print("[ok] 全部重排：%s 分 ／ 中庭图标 %d 个"
      % (app.score_lbl.cget("text"), app.rep_result["stats"]["zone_n"]))

app.set_mode("now")
root.update_idletasks()
assert app.mode == "now"
assert app.score_lbl.cget("text") == str(app.result["score"])
print("[ok] 切回现状：%s 分" % app.score_lbl.cget("text"))
root.destroy()

print("\n阶段五冒烟测试全部通过")
