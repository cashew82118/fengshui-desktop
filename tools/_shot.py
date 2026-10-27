# -*- coding: utf-8 -*-
"""离屏截图工具（开发自用）

用途：验证界面排版时，把窗口渲染成 BMP 再查看，**全程不显示在你屏幕上**：
把主窗放到屏幕外（+4000+4000）并设 alpha=0，再用 GDI PrintWindow 抓位图。

用法：
    python _shot.py settings   → reports/_settings.bmp
    python _shot.py main       → reports/_main.bmp
    python _shot.py owner      → reports/_owner.bmp
    python _shot.py moves      → reports/_moves.bmp（需先切到推演档）
"""
import ctypes
import os
import struct
import sys
import time
import tkinter as tk
from ctypes import wintypes as wt
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import json  # noqa: E402

from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402

enable_dpi_awareness()

# SHOT_FIXTURE=1：用 tests/fixtures 的脱敏布局替代真实桌面。
# 用来截「可以公开发布」的 README 截图——整张图渲染的都是示例图标名，
# 不会把真实桌面文件名带出去（2026-10-27 加）。
if os.environ.get("SHOT_FIXTURE"):
    _fx = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json")
                     .read_text(encoding="utf-8"))
    app_main.read_layout = lambda: (_fx, [])


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

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                    ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                    ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]

    row = ((w * 3 + 3) // 4) * 4
    bi = BMIH(ctypes.sizeof(BMIH), w, h, 1, 24, 0, row * h, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(row * h)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<2sIHHI", b"BM", 14 + 40 + len(buf), 0, 0, 54))
        fh.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                             len(buf), 0, 0, 0, 0))
        fh.write(buf.raw)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    print("PrintWindow=%s %dx%d → %s" % (ok, w, h, path))


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else "settings"
    # 可用环境变量临时换主题/字号核对（截图完把 prefs 还原，不动用户设置）
    #   SHOT_THEME=ink SHOT_FONT=3 python _shot.py hist
    pfile = ROOT / "data" / "prefs.json"
    psnap = pfile.read_text(encoding="utf-8") if pfile.exists() else None
    root = tk.Tk()
    root.geometry("+4000+4000")          # 屏幕外
    root.attributes("-alpha", 0.0)       # 再保险：全透明
    app = app_main.App(root)
    want_theme = os.environ.get("SHOT_THEME", "").strip()
    if want_theme:
        app.set_theme(want_theme)
    want_font = os.environ.get("SHOT_FONT", "").strip()
    if want_font.isdigit():
        app.bump_font(int(want_font) - app.fs_i)
    root.update_idletasks()
    root.update()

    if what == "main":
        app.analyze()
    elif what == "owner":
        app.birth = {"y": 1990, "m": 6, "d": 15, "g": "男"}
        app._recalc_owner()
        app._top("owner")
        app.analyze()
    elif what == "moves":
        app.analyze()
        app.set_mode("wenchang")
    elif what == "hist":
        app.analyze()
        app._top("hist")
    elif what == "ai":
        app.birth = {"y": 1990, "m": 6, "d": 15, "g": "男"}
        app._recalc_owner()
        app.analyze()
        app._top("ai")
    elif what == "prose":
        app.analyze()
        app._top("judge")
        app._tab("prose")
    elif what == "pericon":                    # 全折叠态
        app.analyze()
        app._tab("pericon")
    elif what == "pericon2":                   # 展开一宫 + 一件
        app.analyze()
        app._tab("pericon")
        app._picon_open.add(0)
        app._picon_icon_open.add("0:0")
        app._fill_pericon()
    elif what == "prose":
        app.analyze()
        app._top("judge")
        app._tab("prose")
    elif what == "pericon":                    # 全折叠态
        app.analyze()
        app._tab("pericon")
    elif what == "pericon2":                   # 展开一宫 + 一件
        app.analyze()
        app._tab("pericon")
        app._picon_open.add(0)
        app._picon_icon_open.add("0:0")
        app._fill_pericon()
    elif what == "aihelp":
        app.analyze()
        app._top("ai")
        app._ai_help()
    else:
        app.open_settings()

    for _ in range(80):
        root.update()
        time.sleep(0.01)

    if what == "settings":
        win = app.settings_panel
    elif what in ("pericon", "pericon2", "prose"):
        win = root
    elif what == "aihelp":
        win = app.ai_help_win
    elif what == "moves":
        app._open_moves()
        for _ in range(20):
            root.update()
            time.sleep(0.01)
        win = app.moves_win
    else:
        win = root

    try:
        grab(int(win.wm_frame(), 16), ROOT / "reports" / ("_%s.bmp" % what))
    finally:
        # 还原用户设置必须放 finally：之前写在 destroy 之后，
        # 脚本一旦异常退出就把 SHOT_THEME / SHOT_FONT 留在 prefs 里（2026-10-27 踩过）
        try:
            root.destroy()
        except tk.TclError:
            pass
        if psnap is not None:
            pfile.write_text(psnap, encoding="utf-8")
        elif pfile.exists():
            pfile.unlink()


if __name__ == "__main__":
    main()
