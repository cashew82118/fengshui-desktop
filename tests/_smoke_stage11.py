# -*- coding: utf-8 -*-
"""阶段十二冒烟测试：桌面快照（保存 / 日历 / 查看）+ 问 AI 入口合并。

无窗口运行；结束前删掉本次测试写入的快照（只删测试期间新增的），
并还原 prefs/history 快照。
"""
import calendar
import datetime
import json
import sys
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import tkinter as tk  # noqa: E402

import prefs  # noqa: E402
import snapshots  # noqa: E402
from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402

enable_dpi_awareness()

HIST_FILE = ROOT / "data" / "history.jsonl"
HIST_SNAP = HIST_FILE.read_text(encoding="utf-8") if HIST_FILE.exists() else None
PREFS_FILE = prefs.PATH
PREFS_SNAP = PREFS_FILE.read_text(encoding="utf-8") if PREFS_FILE.exists() else None
if PREFS_SNAP:
    try:
        _d = json.loads(PREFS_SNAP)
        if _d.pop("birth", None) is not None:
            PREFS_FILE.write_text(json.dumps(_d, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
            PREFS_SNAP = PREFS_FILE.read_text(encoding="utf-8")
    except ValueError:
        pass

SNAP_BEFORE = {p.name for p in snapshots.DIR.glob("snap_*.json")} \
    if snapshots.DIR.exists() else set()

print("[1] 数据层：保存 / 读取 / 按日分组 / 不存路径")

root = tk.Tk()
root.withdraw()
app = app_main.App(root)
root.update_idletasks()
root.update()
app.analyze()
root.update_idletasks()
assert app.ready

path = snapshots.save(app.result, app.layout, app.top_dir, app.orient_text)
assert path.exists() and path.name.startswith("snap_") and path.suffix == ".json"
snap = snapshots.load(path)
assert snap and snap["score"] == app.result["score"]
assert len(snap["icons"]) == len(app.layout["icons"])
assert snap["canvas"] == list(app.layout["canvas"])
assert snap["cell"] == list(app.layout["cell"])
assert snap["top_dir"] == app.top_dir
assert set(("x", "y", "row", "col", "wuxing", "name")) <= set(snap["icons"][0])
assert "path" not in snap["icons"][0], "快照不该保存图标全路径"
assert snap["sections"], "应存六项得分"

lay = snapshots.to_layout(snap)
assert lay["canvas"] == tuple(app.layout["canvas"])
assert len(lay["icons"]) == len(app.layout["icons"])

days = snapshots.by_day()
today = datetime.date.today().isoformat()
assert today in days, days.keys()
assert any(r["path"] == path for r in days[today])
recs = snapshots.list_all()
assert recs[0]["t"] >= recs[-1]["t"], "索引应按时间倒序"
assert len(recs) == snapshots.count()
print("[ok] 快照字段完整（%d 图标）、不存路径、按日分组正确" % len(snap["icons"]))

print("[2] 界面：保存按钮 → 日历 → 当日列表 → 查看弹窗")

app._top("hist")
root.update_idletasks()
root.update()
assert "月" in app.cal_title.cget("text"), app.cal_title.cget("text")
n_before = snapshots.count()

app._snap_save()
root.update_idletasks()
root.update()
assert snapshots.count() == n_before + 1, "保存后快照数应 +1"
assert app.snap_day == today, app.snap_day
assert "共" in app.snap_count_lbl.cget("text")
# 日历上今天这一格一定是主色（有快照）
assert app.snap_day in snapshots.by_day()

app._snap_view(path)
root.update_idletasks()
assert app.snap_win is not None
assert not app.snap_win.winfo_ismapped(), "withdraw 下查看弹窗不得真显示"
app._snap_close()
assert app.snap_win is None

# 切换月份再切回来
y0, m0 = app.cal_ym
app._cal_shift(-1)
root.update_idletasks()
assert app.cal_ym != [y0, m0]
app._cal_shift(1)
root.update_idletasks()
assert app.cal_ym == [y0, m0]
print("[ok] 保存 → 选中今天；查看弹窗可开关；月份可翻页")

print("[2b] 日历：任意日期可点 / 有快照的日期带圆点 / 选中态可见")


def cells():
    """取出日历里所有「日期格」：(Frame, 子 Label 列表)。"""
    out = []
    for w in app.cal_grid.winfo_children():
        if isinstance(w, tk.Frame):
            kids = [c for c in w.winfo_children() if isinstance(c, tk.Label)]
            if kids:
                out.append((w, kids))
    return out


def key_of(cell):
    gi = cell.grid_info()
    r, c = int(gi["row"]), int(gi["column"])
    y, m = app.cal_ym
    return "%04d-%02d-%02d" % (y, m, calendar.monthcalendar(y, m)[r - 1][c])


day_key = snapshots.by_day()
grid = cells()
assert len(grid) >= 28, "一个月至少 28 个日期格，实际 %d" % len(grid)
for cell, kids in grid:
    assert cell.bind("<Button-1>"), "每个日期格都要能点（不只今天）"
    assert str(cell.cget("cursor")) == "hand2", "日期格光标应为手型"
    k = key_of(cell)
    dot = kids[-1].cget("text")
    assert (dot == "•") == (k in day_key), "圆点应与是否有快照一致：%s" % k
print("[ok] %d 个日期格全部可点，圆点标记与数据一致" % len(grid))

# 点一个没存过快照的日期
empty_key = None
for cell, _kids in grid:
    if key_of(cell) not in day_key:
        empty_key, empty_cell = key_of(cell), cell
        break
assert empty_key, "本月每天都有快照，无法测空白日"
empty_cell.event_generate("<Button-1>")
root.update_idletasks()
root.update()
if app.snap_day != empty_key:          # 隐藏窗口下事件可能不派发，退化为直接调用
    app._snap_pick(empty_key)
assert app.snap_day == empty_key, app.snap_day
def all_labels(widget):
    """递归取某容器下所有 Label 的文本（Frame 里套 Label 也能取到）。"""
    out = []
    for w in widget.winfo_children():
        if isinstance(w, tk.Label):
            out.append(str(w.cget("text")))
        else:
            out += all_labels(w)
    return out


texts = all_labels(app.snap_list)
assert any("没存过" in t for t in texts), texts
assert any("月" in t and "日" in t for t in texts), "列表要有日期标题：%s" % texts

# 选中态：主色双线框；今天：浅描边
for cell, _kids in cells():
    k = key_of(cell)
    if k == app.snap_day:
        assert cell.cget("highlightbackground") == app.th["accent"], "选中格应主色描边"
        assert int(cell.cget("highlightthickness")) == 2
    elif k == datetime.date.today().isoformat():
        assert int(cell.cget("highlightthickness")) == 1
print("[ok] 空白日可点、列表给出提示、选中格描边可见")

# 再点回有快照的那天，列表要恢复
has_key = sorted(day_key)[-1]
app._snap_pick(has_key)
root.update_idletasks()
assert app.snap_day == has_key
flat = []
for w in app.snap_list.winfo_children():
    if isinstance(w, tk.Label):
        flat.append(str(w.cget("text")))
    elif isinstance(w, tk.Frame):
        flat += [str(c.cget("text")) for c in w.winfo_children()
                 if isinstance(c, tk.Label)]
assert any("分" in t for t in flat), flat
print("[ok] 点回有快照的日期，列表恢复")

print("[3] 同一天多张 → 「看全部」清单")

# 再存一张（同一天），应出现「另有 N 张」
app._snap_save()
root.update_idletasks()
day_recs = snapshots.by_day()[today]
assert len(day_recs) >= 2
app._snap_day_list()
root.update_idletasks()
labels = [w.cget("text") for w in app.snap_list.winfo_children()
          if isinstance(w, tk.Label)]
if len(day_recs) > 3:
    assert any("看全部" in t for t in labels), labels
app._snap_day_all()
root.update_idletasks()
assert app.snap_win is not None and not app.snap_win.winfo_ismapped()
app._snap_close()
print("[ok] 当天 %d 张，清单入口正常" % len(day_recs))

print("[4] 未分析时保存被拒；趋势图不炸")

app.ready = False
app._snap_save()
assert "先点左侧" in app.status.cget("text")
app.ready = True
app._draw_hist(1.0, size=(400, 96))     # 指定尺寸，避免隐藏窗口宽度为 1
app._draw_hist(0.4, size=(400, 96))
print("[ok] 未分析拒绝保存；趋势图两种进度都能画")

print("[5] 入口合并：顶栏无「导出给 AI」")

assert not hasattr(app, "btn_export_ai")
assert app.ai_export_chip.cget("text") == "导出并复制"
app._top("ai")
root.update_idletasks()
assert app.pane_ai.winfo_manager() == "pack"
print("[ok] 顶栏按钮已移除，问 AI 栏内导出仍在")

print("[6] 收尾：只删测试新增的快照")

root.destroy()
for p in list(snapshots.DIR.glob("snap_*.json")):
    if p.name not in SNAP_BEFORE:
        try:
            p.unlink()
        except OSError:
            pass
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
print("[ok] 已清理测试快照 %d 个" % (snapshots.count() - len(SNAP_BEFORE)))

print("\n阶段十二冒烟测试全部通过")
