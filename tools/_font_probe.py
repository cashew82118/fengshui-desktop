# -*- coding: utf-8 -*-
"""字体对比探针（开发自用）

把候选字体渲染成一张对比图，并量化「糊度」。全程离屏：
窗口放到 +4000+4000 且 alpha=0，再用 GDI PrintWindow 抓位图，屏幕上不会出现。

糊度 = 文本区域里「中间灰度」像素的占比（0–255 中 40–215 之间的比例）。
    · 带内嵌点阵的字体（宋体/仿宋/楷体在 9pt）非黑即白，中间灰很少 → 锐利
    · 纯 TTF 抗锯齿（华文系列、隶书、行楷）边缘是一圈渐变灰 → 发虚
这个比值不能代替眼睛，但能解释「为什么糊」。

用法：
    python _font_probe.py          → reports/_fonts.png + 控制台糊度表
"""
import ctypes
import struct
import sys
import time
import tkinter as tk
from ctypes import wintypes as wt
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from desk_reader import enable_dpi_awareness  # noqa: E402

enable_dpi_awareness()

# (字体族, 标签) —— 只放本机扫到的古风候选 + 一个黑体基准
FONTS = [
    ("SimSun", "宋体（当前）"),
    ("NSimSun", "新宋体"),
    ("STSong", "华文宋体"),
    ("STZhongsong", "华文中宋"),
    ("FangSong", "仿宋"),
    ("STFangsong", "华文仿宋"),
    ("KaiTi", "楷体"),
    ("STKaiti", "华文楷体"),
    ("LiSu", "隶书"),
    ("STLiti", "华文隶书"),
    ("STXingkai", "华文行楷"),
    ("STXinwei", "华文新魏"),
    ("Microsoft YaHei", "微软雅黑（旧版基准）"),
]

HEAD = "桌面风水 · 离宫 南 · 67 分"
BODY = "明堂一格 10 个，占全盘密度之首（1.9 倍）。挪去乾宫，凑齐 6 个再回看。"
PADX, ROW_H, TOP = 14, 78, 46


def grab(hwnd: int, path: Path) -> None:
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)
    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                    ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                    ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]
    bi = BMI()
    bi.biSize = 40
    bi.biWidth = w
    bi.biHeight = h   # 正数 = bottom-up，与下面 BMP 头声明一致，否则图会上下颠倒
    bi.biPlanes = 1
    bi.biBitCount = 24
    stride = (w * 3 + 3) // 4 * 4
    buf = ctypes.create_string_buffer(stride * h)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<2sIHHI", b"BM", 14 + 40 + len(buf), 0, 0, 54))
        fh.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                             len(buf), 0, 0, 0, 0))
        fh.write(buf.raw)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    print("PrintWindow=%s %dx%d → %s" % (ok, w, h, path.name))


def main() -> None:
    w = 880
    h = TOP + ROW_H * len(FONTS) + 16
    root = tk.Tk()
    root.title("font probe")
    root.geometry("%dx%d+4000+4000" % (w, h))
    root.attributes("-alpha", 0.0)
    root.configure(bg="#FEFDFB")

    cv = tk.Canvas(root, width=w, height=h, bg="#FEFDFB", highlightthickness=0)
    cv.pack()
    cv.create_text(PADX, 16, text="同一句话，12 种古风字体 + 1 个黑体基准"
                                  "（上：13pt 标题样；下：9pt 正文样）",
                   anchor="w", fill="#4F4E49", font=("SimSun", 10))
    for i, (fam, label) in enumerate(FONTS):
        y = TOP + i * ROW_H
        cv.create_line(PADX, y - 8, w - PADX, y - 8, fill="#E3DED1")
        cv.create_text(PADX, y + 4, text=label, anchor="nw",
                       fill="#6B6961", font=("SimSun", 9))
        cv.create_text(PADX + 168, y, text=HEAD, anchor="nw",
                       fill="#23221F", font=(fam, 13))
        cv.create_text(PADX + 168, y + 30, text=BODY, anchor="nw",
                       fill="#4F4E49", font=(fam, 9))

    root.update_idletasks()
    for _ in range(60):
        root.update()
        time.sleep(0.01)
    out = ROOT / "reports" / "_fonts.bmp"
    grab(int(root.wm_frame(), 16), out)
    root.destroy()

    # ---- 量化糊度
    from PIL import Image
    im = Image.open(out).convert("L")
    print("\n%-14s %-10s %s" % ("字体", "糊度", "9pt 中间灰占比（越低越锐利）"))
    rows = []
    for i, (fam, label) in enumerate(FONTS):
        y = TOP + i * ROW_H + 28
        box = im.crop((PADX + 168, y, w - PADX, y + 26))
        px = list(box.getdata())
        ink = [p for p in px if p < 230]
        if not ink:
            continue
        mid = sum(1 for p in ink if 40 < p < 215) / len(ink)
        rows.append((mid, fam, label))
    for mid, fam, label in sorted(rows):
        bar = "█" * int(mid * 40)
        print("%-14s %5.1f%%  %s  %s" % (fam, mid * 100, bar, label))
    Image.open(out).save(ROOT / "reports" / "_fonts.png")
    print("\n对比图 → reports/_fonts.png")


if __name__ == "__main__":
    main()
