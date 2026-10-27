# -*- coding: utf-8 -*-
"""阶段十冒烟测试：命主（生辰、命卦、四吉四凶、盘上标记、定向推演两档）。

无窗口运行（withdraw），不弹任何真窗口；
结束前还原 prefs.json / history.jsonl 快照，不污染真实数据。
"""
import json
import sys
import time
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import tkinter as tk  # noqa: E402

import classify  # noqa: E402
import mingua  # noqa: E402
import prefs  # noqa: E402
import project  # noqa: E402
import render  # noqa: E402
from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402

enable_dpi_awareness()

HIST_FILE = ROOT / "data" / "history.jsonl"
HIST_SNAP = HIST_FILE.read_text(encoding="utf-8") if HIST_FILE.exists() else None
PREFS_FILE = prefs.PATH
PREFS_SNAP = PREFS_FILE.read_text(encoding="utf-8") if PREFS_FILE.exists() else None
# 快照里若残留上次中断写入的 birth，先剥掉——测试必须从「未填生辰」起步
if PREFS_SNAP:
    try:
        _d = json.loads(PREFS_SNAP)
        if _d.pop("birth", None) is not None:
            PREFS_FILE.write_text(json.dumps(_d, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
            PREFS_SNAP = PREFS_FILE.read_text(encoding="utf-8")
    except ValueError:
        pass

print("[1] 数据层：命卦算法与公开表对齐")

expect = {(1970, "男"): "震", (1970, "女"): "震", (1985, "男"): "乾",
          (1985, "女"): "离", (1990, "男"): "坎", (1990, "女"): "艮",
          (2000, "男"): "离", (2000, "女"): "乾", (2010, "男"): "艮",
          (2010, "女"): "兑"}
for (y, g), want in expect.items():
    got = mingua.compute(y, 6, 15, g)["gua"]
    assert got == want, (y, g, got, want)
print("[ok] 10 组命卦（五年份 × 男女）与公开表全对齐")

r = mingua.compute(1990, 6, 15, "男")
assert (r["ganzhi"], r["nayin"], r["nayin_wuxing"], r["gua"], r["group"]) == \
    ("庚午", "路旁土", "土", "坎", "东四命"), r
assert len(r["good"]) == 4 and len(r["bad"]) == 4
assert r["wenchang_gua"] == "乾" and r["wenchang_dir"] == "西北"
print("[ok] 1990-06-15 男：庚午 路旁土 坎命东四命，文昌乾宫西北")

assert mingua.compute(1990, 1, 20, "男")["y_eff"] == 1989
assert mingua.compute(2017, 2, 2, "男")["y_eff"] == 2016
assert mingua.compute(2017, 2, 3, "男")["y_eff"] == 2017   # 立春当天入新年
E = set(mingua.EAST)
for gua, t in mingua.YOU_NIAN.items():
    g4 = {g for g, s in t.items() if s in mingua.GOOD_ORDER}
    b4 = {g for g, s in t.items() if s in mingua.BAD_ORDER}
    assert len(g4 | b4) == 8 and not (g4 & b4), gua
    if gua in E:
        assert g4 == E and b4 == set(mingua.GUA_DIR) - E, gua
    else:
        assert b4 == E and g4 == set(mingua.GUA_DIR) - E, gua
for bad in [(0, 1, 1, "男"), (1990, 2, 30, "男"), (1990, 13, 1, "男"),
            ("x", 1, 1, "男"), (1990, 1, 1, "X"), (2100, 1, 1, "男")]:
    assert mingua.compute(*bad) is None, bad
print("[ok] 立春分年边界、东西四分组自洽、非法输入全拒")

print("[2] 窗口层：未填生辰 → 表单；填生辰 → 命主栏与标记")

root = tk.Tk()
root.withdraw()
app = app_main.App(root)
root.update_idletasks()
root.update()

assert app.birth is None and app.owner is None
assert app.marks_on is True
app._top("owner")
root.update_idletasks()
assert hasattr(app, "owner_entries") and hasattr(app, "owner_scroll")
assert app.owner_msg is not None
# 未填时两档被拒
app.analyze()
root.update_idletasks()
root.update()
app.set_mode("wenchang")
assert app.mode == "wenchang" and app.wc_result is not None, \
    "没生辰也应能进文昌档（回退巽宫）"
assert app._wenchang_gua() == "巽", app._wenchang_gua()
assert "巽宫" in app.mode_lbl.cget("text")
app.set_mode("caiku")
assert app.mode == "caiku" and app.ck_result is not None
assert app._caiku_gua() == "乾", app._caiku_gua()
assert "乾宫" in app.mode_lbl.cget("text")
print("[ok] 未填生辰：文昌回退巽宫、财库回退乾宫，不再被挡")

# 填生辰（1990-06-15 男）
app.owner_entries["y"].delete(0, "end")
app.owner_entries["m"].delete(0, "end")
app.owner_entries["d"].delete(0, "end")
app.owner_entries["y"].insert(0, "1990")
app.owner_entries["m"].insert(0, "6")
app.owner_entries["d"].insert(0, "15")
app._owner_set_gender("男")
app._owner_save()
root.update_idletasks()
root.update()
assert app.owner and app.owner["gua"] == "坎"
assert app.birth == {"y": 1990, "m": 6, "d": 15, "g": "男"}
saved = prefs.load()
assert saved["birth"] == app.birth, "生辰应落盘"
marks = app._marks()
assert marks and len(marks) == 8
assert all(marks[g] == "good" for _s, g, _d in app.owner["good"])
print("[ok] 保存生效：坎命已记、落盘、盘上 8 宫有标记")

print("[2b] 朝向记忆：选过就记住，重启不丢")

label_east = dict((a, lb) for a, lb in render.ORIENT_CHOICES)[90]
app.orient_var.set(label_east)
app._on_orient(None)
root.update_idletasks()
assert app.top_dir == 90, app.top_dir
assert prefs.load()["orient"] == 90, "朝向应落盘"

root2 = tk.Tk()
root2.withdraw()
app2 = app_main.App(root2)
root2.update_idletasks()
assert app2.top_dir == 90, "重启后朝向应沿用（实际 %s）" % app2.top_dir
assert app2.orient_text == label_east, app2.orient_text
assert app2.orient_var.get() == label_east, "下拉框应显示上次选的那一项"
# 构造时挂了揭示动画定时器；销毁前把待触发的 after 全部取消，
# 否则 destroy 后回调会抛「invalid command name ...<lambda>」污染输出
try:
    for _aid in root2.tk.splitlist(root2.tk.call("after", "info")):
        root2.after_cancel(_aid)
except tk.TclError:
    pass
root2.destroy()

# 坏值不许把盘转歪
raw = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
raw["orient"] = 999
PREFS_FILE.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
assert prefs.load()["orient"] == 180, "非法角度应退回默认"
print("[ok] 朝向 90° 已记住、重启沿用、坏值回退 180°")

print("[3] 盘上标记开关与渲染")

app.toggle_marks()
assert app._marks() is None and app.marks_on is False
app.toggle_marks()
assert app._marks() is not None
app._draw(1.0)                      # 带 marks 真跑一次绘制
root.update_idletasks()
assert app.hits, "带标记绘制后命中框不应为空"
print("[ok] 标记可开关；draw_board(marks=...) 正常出图")

print("[4] 命主栏信息渲染 + 桌面对照")

app._top("owner")
root.update_idletasks()


def all_texts(w):
    out = []
    try:
        out.append(str(w.cget("text")))
    except (tk.TclError, AttributeError):
        pass
    for c in w.winfo_children():
        out.extend(all_texts(c))
    return out


texts = all_texts(app.owner_body)
assert any("坎命" in t and "东四命" in t for t in texts), "应显示命卦与分组"
assert any("对你偏助的一方" in t for t in texts)
assert any("与你相冲的一方" in t for t in texts)
assert any("本命文昌" in t for t in texts)
notes = [t for t in texts if t.startswith("· ")]
assert notes, "分析后应有桌面对照条目"
print("[ok] 命主栏四吉四凶两列 + 本命文昌 + 桌面对照 %d 条" % len(notes))

print("[5] 定向推演两档：优先文昌 / 优先财库")

app.set_mode("wenchang")
root.update_idletasks()
root.update()
assert app.mode == "wenchang" and app.wc_result is not None
lay, res, mvs = app._scene()
assert lay is app.wc_layout and res is app.wc_result
grid = __import__("palace").palace_grid(app.top_dir)
tcell = project._find_gua(grid, app.owner["wenchang_gua"])
incell = [it for it in lay["icons"] if (it["row"], it["col"]) == tcell]
assert incell and all(classify.is_doc(it) for it in incell), \
    "文昌宫应全是文书类"
assert not [it for it in lay["icons"] if (it["row"], it["col"]) == (1, 1)], \
    "中宫必须空"
assert "文昌" in app.mode_lbl.cget("text")
print("[ok] 优先文昌：移 %d 个 → %d 分（%d → %+d），目标宫纯文书"
      % (len(mvs), res["score"], app.result["score"],
         res["score"] - app.result["score"]))

app.set_mode("caiku")
root.update_idletasks()
root.update()
assert app.mode == "caiku" and app.ck_result is not None
lay2, res2, mvs2 = app._scene()
t2 = project._find_gua(grid, app.owner["good"][0][1])
incell2 = [it for it in lay2["icons"] if (it["row"], it["col"]) == t2]
assert incell2 and all(classify.is_tool(it) for it in incell2), \
    "生气宫应全是工具类"
assert "财库" in app.mode_lbl.cget("text")
print("[ok] 优先财库：目标生气宫纯工具，中宫空")

# 移动清单：按钮只在推演档出现，清单条数与场景一致
assert app.move_chip.winfo_manager() == "pack", "推演档应出现「移动清单」"
assert str(len(mvs2)) in app.move_chip.cget("text"), app.move_chip.cget("text")
app._open_moves()
root.update_idletasks()
assert app.moves_win is not None and not app.moves_win.winfo_ismapped(), \
    "withdraw 下清单弹窗不得真显示"
rows = app.moves_tree.get_children()
assert len(rows) == len(mvs2), "清单条数不符：%d vs %d" % (len(rows), len(mvs2))
first = app.moves_tree.item(rows[0], "values")
assert first[0] and first[1] and first[2], first
app._moves_close()
assert app.moves_win is None
app.set_mode("now")
root.update_idletasks()
assert app.move_chip.winfo_manager() == "", "回现状后清单入口应收起"
print("[ok] 移动清单：%d 条、含从/到、回现状自动收起" % len(rows))

# 改生辰使两档作废
app.set_mode("now")
app._top("owner")
app._owner_edit()
root.update_idletasks()
app.owner_entries["y"].delete(0, "end")
app.owner_entries["y"].insert(0, "2000")
app._owner_set_gender("女")
app._owner_save()
root.update_idletasks()
assert app.owner["gua"] == "乾", app.owner["gua"]
assert app.mode == "now", "生辰变更后定向档应作废回现状"
print("[ok] 修改生辰：命卦重算（乾命），两档定向推演已作废")

print("[6] 清空生辰（确认框自动应答）+ 坏生辰拒绝")

orig_ask = app_main.messagebox.askyesno
app_main.messagebox.askyesno = lambda *a, **k: False
app._owner_clear()
assert app.owner is not None, "选「否」不应清空"
app_main.messagebox.askyesno = lambda *a, **k: True
app._owner_clear()
assert app.owner is None and app.birth is None
assert app._marks() is None
assert prefs.load()["birth"] is None
app_main.messagebox.askyesno = orig_ask

app._top("owner")
app.owner_entries["y"].insert(0, "1990")
app.owner_entries["m"].insert(0, "2")
app.owner_entries["d"].insert(0, "31")
app._owner_save()
assert "不存在" in app.owner_msg.cget("text"), "2/31 应被拒"
app._owner_cancel()
print("[ok] 确认后才清空；2/31 这类日期被拒绝")

root.destroy()

if PREFS_SNAP is None:
    if PREFS_FILE.exists():
        PREFS_FILE.unlink()
else:
    PREFS_FILE.write_text(PREFS_SNAP, encoding="utf-8")
if HIST_SNAP is None:
    if HIST_FILE.exists():
        HIST_FILE.unlink()
else:
    HIST_FILE.write_text(HIST_SNAP, encoding="utf-8")
print("[ok] 已还原 prefs.json 与历史记录，测试未污染真实数据")

print("\n阶段十冒烟测试全部通过")
