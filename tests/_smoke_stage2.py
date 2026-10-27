# -*- coding: utf-8 -*-
"""阶段二冒烟测试：验证方位旋转与绘制结构，不显示任何窗口。

root.withdraw() 保证屏幕上不会出现任何界面。
"""
import json
import sys
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import render  # noqa: E402

layout = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json").read_text(encoding="utf-8"))

# ---------------- 1. 方位旋转 ----------------
g = render.palace_grid(180)          # 坐北朝南
expect = [["巽", "离", "坤"], ["震", None, "兑"], ["艮", "坎", "乾"]]
got = [[c["gua"] if c else None for c in row] for row in g]
assert got == expect, "坐北朝南九宫布局错误: %s" % got
print("[ok] 坐北朝南  ->", got)

g2 = render.palace_grid(90)          # 上方朝东
got2 = [[c["gua"] if c else None for c in row] for row in g2]
assert got2[0][1] == "震", "上方朝东时上中应为震，实为 %s" % got2[0][1]
assert got2[1][0] == "坎", "上方朝东时左中应为坎（北），实为 %s" % got2[1][0]
assert got2[2][0] == "乾", "上方朝东时左下应为乾（西北），实为 %s" % got2[2][0]
print("[ok] 上方朝东  ->", got2)

# 五行必须跟着卦走
assert g2[0][1]["wuxing"] == "木" and g2[2][2]["wuxing"] == "土"
print("[ok] 五行随卦旋转")

# 八个方位都要能生成完整九宫，不重不漏
for ang, label in render.ORIENT_CHOICES:
    grid = render.palace_grid(ang)
    flat = [c["gua"] for row in grid for c in row if c]
    assert len(flat) == 8 and len(set(flat)) == 8, "%s 宫位重复: %s" % (label, flat)
print("[ok] 八个朝向均生成完整不重复的八卦盘")

# ---------------- 2. 绘制结构 ----------------
root = tk.Tk()
root.withdraw()                       # 关键：不显示窗口
canvas = tk.Canvas(root, width=620, height=430)
hits = render.draw_board(canvas, layout, 180, 620, 430)

n_icon = len(layout["icons"])
assert len(hits) == n_icon, "命中框数量 %d != 图标数 %d" % (len(hits), n_icon)
print("[ok] 图标方块与命中框 %d 个" % len(hits))

items = canvas.find_all()
print("[ok] 画布元素总数 %d" % len(items))

for it in items:
    bb = canvas.bbox(it)
    assert bb is not None, "存在无边界元素"
    assert bb[0] >= -8 and bb[2] <= 638, "元素越界: %s" % (bb,)
    assert bb[1] >= -8 and bb[3] <= 448, "元素越界: %s" % (bb,)
print("[ok] 所有元素都在画布内")

# 中宫无图标时应出现"中宫空 · 吉"
texts = []
for it in items:
    if canvas.type(it) == "text":
        texts.append(canvas.itemcget(it, "text"))
assert any("中宫空" in t for t in texts), "中宫为空但未标注"
print("[ok] 中宫空标注正确")

# 换朝向后重绘，元素数应稳定
before = len(items)
hits2 = render.draw_board(canvas, layout, 270, 620, 430)
assert len(hits2) == n_icon
print("[ok] 切换朝向后重绘正常（%d -> %d 个元素）" % (before, len(canvas.find_all())))

# 缩放到最小窗口也不应报错
render.draw_board(canvas, layout, 180, 320, 240)
print("[ok] 小窗口下绘制不报错")

root.destroy()

# ---------------- 3. 完整窗口构造（仍然不显示） ----------------
import main as app_main  # noqa: E402

root2 = tk.Tk()
root2.withdraw()
app = app_main.App(root2)
app.analyze()                # 启动闸门：测试里显式触发分析
root2.update_idletasks()
root2.update()
assert app.layout is not None, "窗口初始化后未拿到布局: %s" % app.error
assert len(app.hits) == len(app.layout["icons"]), \
    "窗口内命中框数量不对: %d" % len(app.hits)
print("[ok] 完整窗口构造成功，命中框 %d 个" % len(app.hits))

# 切换朝向后窗口层面也应重绘
app.orient_var.set(render.ORIENT_CHOICES[2][1])
app._on_orient(None)
root2.update_idletasks()
assert len(app.hits) == len(app.layout["icons"])
print("[ok] 窗口层切换朝向正常")
root2.destroy()

print("\n阶段二冒烟测试全部通过")
