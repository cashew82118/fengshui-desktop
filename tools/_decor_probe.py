# -*- coding: utf-8 -*-
"""装饰字体探针：看哪种古风字体在**大字**下既能看清又有味道。

小字（9pt）只有宋体/新宋体不糊，但 17pt 品牌标题、14pt 卦名、13pt 评级、
11pt 小标题这些大字号不受点阵限制。这个脚本按真实字号把候选字体排一遍。

用法：
    python _decor_probe.py   → reports/_fonts_decor.png
"""
import sys
import time
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from desk_reader import enable_dpi_awareness  # noqa: E402
from _shot import grab                        # noqa: E402

enable_dpi_awareness()

FONTS = [
    ("SimSun", "宋体（当前）"),
    ("STZhongsong", "华文中宋"),
    ("STSong", "华文宋体"),
    ("LiSu", "隶书"),
    ("STLiti", "华文隶书"),
    ("STXingkai", "华文行楷"),
    ("STXinwei", "华文新魏"),
    ("KaiTi", "楷体"),
]

# (字号, 文本) —— 与界面上真实位置对应
SAMPLES = [
    (17, "桌面风水", "品牌标题"),
    (14, "离宫 南", "九宫卦名"),
    (13, "平 · 可用待理", "总分评级"),
    (11, "明堂壅塞", "分条小标题"),
]

PADX, ROW_H, TOP, COL_W = 14, 84, 46, 210


def main() -> None:
    w = PADX * 2 + 130 + COL_W * len(SAMPLES)
    h = TOP + ROW_H * len(FONTS) + 18
    root = tk.Tk()
    root.title("decor probe")
    root.geometry("%dx%d+4000+4000" % (w, h))
    root.attributes("-alpha", 0.0)
    root.configure(bg="#FEFDFB")
    cv = tk.Canvas(root, width=w, height=h, bg="#FEFDFB", highlightthickness=0)
    cv.pack()
    cv.create_text(PADX, 16, text="同一个字，四种真实字号下各字体的样子"
                                  "（依次：品牌 17 / 卦名 14 / 评级 13 / 小标题 11）",
                   anchor="w", fill="#4F4E49", font=("SimSun", 10))
    for i, (size, _t, _label) in enumerate(SAMPLES):
        cv.create_text(PADX + 130 + i * COL_W + COL_W // 2, 34,
                       text="%dpt" % size, anchor="center",
                       fill="#8A3B12", font=("SimSun", 9))
    for r, (fam, label) in enumerate(FONTS):
        y = TOP + r * ROW_H
        cv.create_line(PADX, y - 8, w - PADX, y - 8, fill="#E3DED1")
        cv.create_text(PADX, y + 10, text=label, anchor="nw",
                       fill="#6B6961", font=("SimSun", 9))
        for i, (size, text, _lab) in enumerate(SAMPLES):
            cv.create_text(PADX + 130 + i * COL_W, y, text=text, anchor="nw",
                           fill="#23221F", font=(fam, size))
    root.update_idletasks()
    for _ in range(60):
        root.update()
        time.sleep(0.01)
    out = ROOT / "reports" / "_fonts_decor.bmp"
    grab(int(root.wm_frame(), 16), out)
    root.destroy()
    from PIL import Image
    Image.open(out).save(ROOT / "reports" / "_fonts_decor.png")
    print("→ reports/_fonts_decor.png")


if __name__ == "__main__":
    main()
