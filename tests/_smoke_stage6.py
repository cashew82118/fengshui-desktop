# -*- coding: utf-8 -*-
"""阶段六冒烟测试：主题、字号、动效、分栏、缩放。全程不显示窗口。

动效测试用「强制 _can_anim=True + 抽事件循环」的方式跑，
真实运行时窗口可见才动画，无窗口测试里所有数值直接到位。
"""
import json
import sys
import time
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import render  # noqa: E402
import theme  # noqa: E402

# 测试会触发扫描，进而写历史；先存一份，结束时还原，别污染真实记录
HIST_FILE = ROOT / "data" / "history.jsonl"
HIST_SNAP = HIST_FILE.read_text(encoding="utf-8") if HIST_FILE.exists() else None

RAW = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json").read_text(encoding="utf-8"))
N = len(RAW["icons"])

root = tk.Tk()
root.withdraw()
canvas = tk.Canvas(root, width=900, height=620)


def pump(n: int = 90) -> None:
    for _ in range(n):
        try:
            root.update()
        except tk.TclError:
            return
        time.sleep(0.003)


def pump_until(cond, secs: float = 2.0) -> bool:
    """抽事件循环直到条件成立（动画是按真实时间跑的）。"""
    end = time.time() + secs
    while time.time() < end:
        try:
            root.update()
        except tk.TclError:
            return False
        if cond():
            return True
        time.sleep(0.005)
    return False


# ---------------- 1. 四套主题都能画 ----------------
print("[..] 四套主题绘图")
for key in theme.ORDER:
    th = theme.get(key)
    hits = render.draw_board(canvas, RAW, 180, 900, 620, th=th,
                             fonts=theme.fonts(1.0))
    assert len(hits) == N, "%s 主题命中框 %d != %d" % (th["label"], len(hits), N)
    assert canvas.cget("bg") == th["board"], "%s 主题盘底未生效" % th["label"]
    assert len(canvas.find_all()) > N, "%s 主题元素过少" % th["label"]
print("[ok] 宣纸/青瓷/晚照/墨夜 四套主题均绘制正常（各 %d 个命中框）" % N)

# ---------------- 1.5 宫底必须真有染色 ----------------
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _dist(a: str, b: str) -> float:
    x, y = _rgb(a), _rgb(b)
    return sum((x[i] - y[i]) ** 2 for i in range(3)) ** 0.5


for key in theme.ORDER:
    th = theme.get(key)
    for n in (1, 6, 12):
        f = render.cell_fill(th, n)
        assert f, "%s 主题 %d 个图标的宫底为空" % (th["label"], n)
        assert f.lower() != th["board"].lower(),             "%s 主题 %d 个图标：宫底被底色冲掉了（%s）" % (th["label"], n, f)
    assert render.cell_fill(th, 0, True).lower() == th["center_empty"].lower(), \
        "%s 主题的中宫空底色不对" % th["label"]
    assert render.cell_fill(th, 0, False) == "", "空宫不该填色"
print("[ok] 四套主题宫底均有染色，中宫空保留暖色")

_th = theme.get("paper")
light = render.cell_fill(_th, 12, False, 0.0)
full = render.cell_fill(_th, 12, False, 1.0)
assert light != full, "入场首末帧宫底没有变化"
assert _dist(light, _th["board"]) < _dist(full, _th["board"]), \
    "入场首帧应更接近底色，实为 %s → %s" % (light, full)
print("[ok] 入场由浅到深：%s → %s" % (light, full))

# 画面上不能有任何一格被涂成底色
render.draw_board(canvas, RAW, 180, 900, 620, th=_th, fonts=theme.fonts(1.0))
fills = [canvas.itemcget(i, "fill") for i in canvas.find_all()
         if canvas.type(i) == "rectangle"]
tinted = [f for f in fills if f]
assert tinted, "画面上没有任何染色的宫底"
assert all(f.lower() != _th["board"].lower() for f in tinted), \
    "有宫底被涂成了底色：%s" % [f for f in tinted if f.lower() == _th["board"].lower()]
print("[ok] 画面上 %d 个宫底全部带染色，无一被底色冲白" % len(tinted))

# ---------------- 2. 四档字号 ----------------
print("[..] 四档字号绘图")
last = 0
for i, (name, scale) in enumerate(theme.FONT_STEPS):
    f = theme.fonts(scale)
    assert abs(theme.scale_of(f) - scale) < 0.03, \
        "倍率反推偏差过大：%s vs %.2f" % (theme.scale_of(f), scale)
    hits = render.draw_board(canvas, RAW, 180, 900, 620,
                             th=theme.get("paper"), fonts=f)
    assert len(hits) == N
    n_items = len(canvas.find_all())
    print("     %-3s ×%.2f  字号 %2d/%2d/%2d  元素 %d"
          % (name, scale, f["tiny"][1], f["small"][1], f["score"][1], n_items))
    last = n_items
assert last > 0
print("[ok] 四档字号均可绘制，字号随倍率放大")

# ---------------- 3. 揭示动画分帧 ----------------
print("[..] 揭示动画分帧")
counts = []
for t in (0.0, 0.2, 0.45, 0.7, 1.0):
    h = render.draw_board(canvas, RAW, 180, 900, 620,
                          th=theme.get("paper"), fonts=theme.fonts(1.0),
                          reveal=t)
    counts.append(len(canvas.find_all()))
assert counts[-1] > counts[0], "揭示到 1.0 时元素没有增加"
assert len(render.draw_board(canvas, RAW, 180, 900, 620, reveal=1.0)) == N
print("[ok] 揭示进度 0→1 元素递增：%s，末帧命中框 %d" % (counts, N))

# ---------------- 4. 盘随窗口缩放 ----------------
print("[..] 盘随窗口缩放")
w1, h1 = render.fit_board(600, 420, (2560, 1440))[2:4]
w2, h2 = render.fit_board(1200, 900, (2560, 1440))[2:4]
assert w2 > w1 and h2 > h1, "窗口变大时盘没有变大：%s -> %s" % ((w1, h1), (w2, h2))
assert abs((w1 / h1) - (w2 / h2)) < 0.02, "缩放后长宽比失真"
# 字号变大时盘要给上下文字让位
w3 = render.fit_board(1200, 900, (2560, 1440), fs=1.27)[2]
assert w3 <= w2, "字号变大后盘没有让出空间"
print("[ok] 600×420 → %.0f×%.0f，1200×900 → %.0f×%.0f，比例 %.3f 保持"
      % (w1, h1, w2, h2, w2 / h2))

# ---------------- 5. 窗口层：主题 / 字号 / 动效 / 分栏 ----------------
from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402
import prefs  # noqa: E402

enable_dpi_awareness()
root2 = tk.Tk()
root2.withdraw()
root2.geometry("1280x820")   # 真实窗口尺寸：隐藏窗口默认几何会把盘压扁，动效断言就失真
app = app_main.App(root2)
app.analyze()                # 启动闸门：测试里显式触发分析
root2.update_idletasks()
root2.update()
assert app.result is not None
NL = len(app.layout["icons"])          # 实时桌面可能已经和快照不同

for key in theme.ORDER:
    app.set_theme(key)
    root2.update_idletasks()
    root2.update()
    assert app.theme_name == key
    assert app.root.cget("bg") == theme.get(key)["bg"], "%s 窗口底色未换" % key
    assert len(app.hits) == NL, "%s 主题下命中框数不对：%d" % (key, len(app.hits))
    assert app.score_lbl.cget("text") == str(app.result["score"]), \
        "%s 主题下分数显示不对" % key
print("[ok] 四套主题在窗口内切换正常，分数与盘面均保持")

# 重建不许泄漏框架：旧顶栏若没销毁，每换一次主题就吃掉 36px，盘会被越压越扁
_kids = len(root2.winfo_children())
_h0 = app.body.winfo_height()
for _ in range(3):
    app._rebuild()
root2.update_idletasks()
root2.update()
assert len(root2.winfo_children()) == _kids, \
    "重建后 root 子件增多：%d → %d" % (_kids, len(root2.winfo_children()))
assert abs(app.body.winfo_height() - _h0) <= 2, \
    "重建后盘面高度漂移：%d → %d" % (_h0, app.body.winfo_height())
print("[ok] 连续重建 3 次：不泄漏框架，盘面高度稳定")

# 换主题不该打乱朝向与页签（重建界面的经典副作用）
ALT = render.ORIENT_CHOICES[4]
app.orient_var.set(ALT[1])
app._on_orient(None)
app._tab("prose")
root2.update_idletasks()
app.set_theme("dusk")
root2.update_idletasks()
root2.update()
assert app.orient_text == ALT[1], "换主题后朝向被重置：%s" % app.orient_text
assert app.orient_var.get() == ALT[1], "换主题后下拉框显示不对"
assert app.top_dir == ALT[0], "换主题后推演用的朝向不对：%s" % app.top_dir
assert app.sub_tab == "prose" and app.top_tab == "judge" \
       and app.pane_prose.winfo_manager() == "pack", \
    "换主题后页签被打回分条"
print("[ok] 换主题保留朝向（%s）与页签（总评）" % ALT[1])
app.set_theme("paper")
app._tab("cards")
app.orient_var.set(render.ORIENT_CHOICES[0][1])
app._on_orient(None)
root2.update_idletasks()

# 字号四档，逐档放大后分数标签字号确实变大
for _ in range(len(theme.FONT_STEPS) + 2):
    app.bump_font(-1)
root2.update_idletasks()
assert app.fs_i == 0, "字号未夹紧到最小档：%d" % app.fs_i
sizes = []
for _ in range(len(theme.FONT_STEPS) - 1):
    app.bump_font(1)
    root2.update_idletasks()
    sizes.append(app.score_lbl.cget("font"))
assert len(set(map(str, sizes))) == len(sizes), "字号没有随档位变化：%s" % sizes
for _ in range(len(theme.FONT_STEPS) * 2):
    app.bump_font(-1)
assert app.fs_i == 0, "字号未夹紧在下限：%d" % app.fs_i
app.bump_font(1)
assert app.fs_i == 1
print("[ok] 字号四档可调，档位夹紧在 0–3，回落到标准档")

# 分栏拖动
app.split = 0.50
app._apply_split()
app.body.update_idletasks()
assert abs(float(app.left.place_info()["relwidth"]) - 0.50) < 1e-6
app._reset_split()
assert abs(app.split - 0.62) < 1e-6
print("[ok] 左右分栏可拖动，双击复位到 62%")

# 偏好已落盘
saved = json.loads((ROOT / "data" / "prefs.json").read_text(encoding="utf-8"))
assert saved["theme"] == app.theme_name and saved["font"] == app.fs_i
print("[ok] 偏好写入 data/prefs.json：%s" % saved)

# ---------------- 6. 动效跑通（强制成可见状态） ----------------
print("[..] 动效")
app.anim_on = True                          # 不受上次测试残留影响
app._can_anim = lambda: bool(app.anim_on)   # 无窗口测试里手动放行（仍尊重开关）
app._score_shown = 0
app._animate_reveal(160)
assert pump_until(lambda: not app.revealing and len(app.hits) == NL), \
    "揭示动画结束后命中框不全：%d" % len(app.hits)

target = app.result["score"]
app._score_shown = 0
app._set_score(target)
# 滚动期间逐帧采样：字号与分数盒子尺寸都必须恒定。
# 曾经这里挂着一个「落定脉冲」——滚完把 40 号改成 36 号、再用 220ms 长回去。
# Tk 没有 transform，只能靠改字号模拟缩放，结果就是数字猛缩一下再鼓起来，
# 看着像卡了一下（2026-10-27 用户报，已删除）。这条断言钉住它别再回来。
_fonts, _boxes = set(), set()
_end = time.time() + 2.0
while time.time() < _end:
    _fonts.add(str(app.score_lbl.cget("font")))
    _boxes.add((app.scbox.winfo_width(), app.scbox.winfo_height()))
    if app.score_lbl.cget("text") == str(target):
        break
    root.update()
    time.sleep(0.006)
assert app.score_lbl.cget("text") == str(target), \
    "分数滚动未落到 %d，停在 %s" % (target, app.score_lbl.cget("text"))
assert len(_fonts) == 1, "滚动期间字号变了：%s" % sorted(_fonts)
assert len(_boxes) == 1, "滚动期间分数盒子尺寸变了：%s" % _boxes
assert not hasattr(app, "_pulse_score"), "落定脉冲不该再加回来（会使数字猛缩一下）"
print("[ok] 揭示动画收尾 %d 个命中框；分数从 0 滚到 %d，字号与盒子全程不变"
      % (len(app.hits), target))

app._animate_bars()
pump_until(lambda: len(app.bars.find_all()) > N)
assert app.bars.find_all(), "评分条未绘出"
print("[ok] 评分条生长动画绘出 %d 个元素" % len(app.bars.find_all()))

app.set_mode("proj")
assert pump_until(lambda: not app.revealing and len(app.hits) == NL)
app.set_mode("now")
assert pump_until(lambda: app.score_lbl.cget("text") == str(target))
print("[ok] 切换档位带动画，最终回到现状 %s 分" % app.score_lbl.cget("text"))

# 悬停放大 + 提示框（等揭示动画彻底走完，图元才稳定）
assert pump_until(lambda: not app.revealing)
pump(15)
hit = app.hits[0]
assert app.board.coords(hit["id"]), "命中框对应的图元已失效"


def icon_w() -> float:
    bb = app.board.bbox(hit["id"])
    return (bb[2] - bb[0]) if bb else -1.0


app._grow_icon(hit, True)
assert pump_until(lambda: abs(icon_w() - hit["box"] * 1.55) < 3.0), \
    "悬停未放大到位：%.1f（应为 %.1f）" % (icon_w(), hit["box"] * 1.55)
app._show_tip(hit, 100, 100)
assert pump_until(lambda: bool(app.board.find_withtag("tip"))), "提示框未出现"
app._tip_target = hit        # 正常路径由 _on_motion 维护，这里手工补上
app._clear_tip()
assert pump_until(lambda: not app.board.find_withtag("tip")), "提示框未清除"
assert pump_until(lambda: abs(icon_w() - hit["box"]) < 3.0), "图标未缩回原尺寸"
print("[ok] 图标悬停放大到 1.55 倍并缩回，提示框淡入淡出正常")

# ---------------- 7. 圆角方块 / 宫格高亮 / 点击涟漪 ----------------
pts = render.rr_points(100, 100, 10)
assert len(pts) == (render.RR_SEG + 1) * 4 * 2, "圆角顶点数不对"
assert abs(min(pts[0::2]) - 90) < 0.01 and abs(max(pts[0::2]) - 110) < 0.01
assert not any(abs(x - 90) < 0.3 and abs(y - 90) < 0.3
               for x, y in zip(pts[0::2], pts[1::2])), "四角没有被削圆"
assert app.board.type(hit["id"]) == "polygon", "图标不是圆角多边形"
print("[ok] 图标为圆角多边形（%d 个顶点），四角已削圆" % (len(pts) // 2))

h0 = app.hits[0]
app._hover_cell(int(h0["cx"]), int(h0["cy"]))
assert pump_until(lambda: bool(app.board.find_withtag("cellhl")), 1.0), \
    "宫格悬停高亮未出现"
app._on_leave()
assert not app.board.find_withtag("cellhl"), "离开后高亮未清除"

app._ripple(h0)
assert pump_until(lambda: bool(app.board.find_withtag("ripple")), 0.6), \
    "点击涟漪未出现"
assert pump_until(lambda: not app.board.find_withtag("ripple"), 2.0), \
    "涟漪未自行消失"
print("[ok] 宫格悬停高亮、点击涟漪扩散后自动消失")

# ---------------- 8. 淡入方向 / 提示框不许被挤掉 ----------------
import types

board_c = theme.get(app.theme_name)["board"].lower()
accent_c = app.th["accent"].lower()
assert app._fade_in(accent_c, 0.0) == board_c, "淡入起点应等于底色"
assert app._fade_in(accent_c, 1.0) == accent_c, "淡入终点应等于本色"
assert app._fade_in(accent_c, 0.5) not in (board_c, accent_c)
assert app._ripple_color(0.0) == accent_c, "涟漪起手应是主色"
assert app._ripple_color(1.0) == board_c, "涟漪收尾应退回底色（淡出）"
assert app._ripple_color(0.5) not in (board_c, accent_c)
print("[ok] 淡入从底色起、到本色止；涟漪起手主色、收尾淡出")

h1 = app.hits[0]
app._on_motion(types.SimpleNamespace(x=int(h1["cx"]), y=int(h1["cy"])))
assert pump_until(lambda: bool(app.board.find_withtag("tip")), 1.0), "提示未出现"
pump(120)
bb = app.board.bbox("tip")
assert bb, "提示框没有边界"
assert app.board.find_withtag("tip"), "提示框淡入过程中自己消失了"


def over_icon(x: int, y: int) -> bool:
    return any(h["x0"] <= x <= h["x1"] and h["y0"] <= y <= h["y1"]
               for h in app.hits)


pt = None
for tx in range(int(bb[0]) + 4, max(int(bb[0]) + 5, int(bb[2]) - 2), 4):
    for ty in range(int(bb[1]) + 4, max(int(bb[1]) + 5, int(bb[3]) - 2), 4):
        if not over_icon(tx, ty):
            pt = (tx, ty)
            break
    if pt:
        break
assert pt, "提示框周围找不到空白点"
app._on_motion(types.SimpleNamespace(x=pt[0], y=pt[1]))
pump(80)
assert app.board.find_withtag("tip"), "鼠标滑到提示框上，提示就被收掉了"

app._on_motion(types.SimpleNamespace(x=3, y=3))
assert not app.board.find_withtag("tip"), "离开图标后提示未清除"
print("[ok] 提示框滑上去不会被收掉，离开才清除")

# ---------------- 9. 历史页：入口、摘要、趋势图、明细 ----------------
import history as hist_mod  # noqa: E402

app._top("hist")
root2.update_idletasks()
root2.update()
assert app.top_tab == "hist" and app.pane_hist.winfo_manager() == "pack", \
    "切不到历史页"
assert app.pane_judge.winfo_manager() in ("", None), "历史页打开时断语栏没收起"

recs = hist_mod.read_all()
assert recs, "历史没有记录"
sumtxt = app.hist_sum.cget("text")
for must in ("次记录", "最高", "最低", "不存文件名"):
    assert must in sumtxt, "历史摘要缺少「%s」：%s" % (must, sumtxt)
rows = [w for w in app.hist_rows.winfo_children()
        if w.winfo_class() == "Frame"]
assert rows, "历史明细没有行"
print("[ok] 历史页：%s" % sumtxt.split("　·　")[0])

app._draw_hist(1.0, size=(440, 96))
els = app.hist_chart.find_all()
assert len(els) >= 5, "趋势图没画出来：%d 个元素" % len(els)
kinds = {app.hist_chart.type(i) for i in els}
assert "line" in kinds and "oval" in kinds, "趋势图缺少折线或数据点"
if len(recs) >= 3:
    app._draw_hist(0.0, size=(440, 96))
    assert len(app.hist_chart.find_all()) < len(els), "走势图没有逐段展开"
app._draw_hist(1.0, size=(440, 96))
print("[ok] 趋势图 %d 个元素（折线／点／刻度），%d 条记录" % (len(els), len(recs)))

app._top("judge")
app._tab("cards")
assert app.top_tab == "judge" and app.pane_cards.winfo_manager() == "pack", \
    "切回断语失败"
print("[ok] 四栏互切正常")

# 动效关闭后数值立即到位
app.toggle_anim()
root2.update_idletasks()
assert app.anim_on is False
app._score_shown = 0
app._set_score(target)
assert app.score_lbl.cget("text") == str(target), "关掉动效后分数没有立即到位"
app.bump_font(1)
root2.update_idletasks()
root2.update()
assert app.score_lbl.cget("text") == str(app.result["score"])
print("[ok] 关闭动效后分数立即到位，重建界面后仍正确")

if not app.anim_on:
    app.toggle_anim()
assert app.anim_on is True
root2.destroy()

# 恢复初始状态：删掉测试写入的偏好，用户首次启动仍走默认（宣纸/标准/动效开）
(ROOT / "data" / "prefs.json").unlink(missing_ok=True)
print("[ok] 已清理测试写入的偏好，首次启动回到默认主题")

if HIST_SNAP is None:
    HIST_FILE.unlink(missing_ok=True)
else:
    HIST_FILE.write_text(HIST_SNAP, encoding="utf-8")
print("[ok] 已还原历史记录，测试未污染真实数据")

print("\n阶段六冒烟测试全部通过")
