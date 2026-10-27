# -*- coding: utf-8 -*-
"""字体预览器（开发自用，不影响正式程序）

打开的就是真实界面，只是多了一层「按数字键换字体」：
    1 全宋体（当前定稿）
    2 标题与卦名用华文中宋（稳一点的升级）
    3 品牌用华文行楷 + 卦名用隶书（古籍封面感）
    4 全楷体（之前试过的那版，留着对比）
    5 全华文中宋
窗口里怎么点怎么切都行，切选项卡、切主题、改字号都会保留当前字体方案。

关掉窗口即退出，不改任何配置文件。
"""
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from desk_reader import enable_dpi_awareness  # noqa: E402

enable_dpi_awareness()

import main as app_main  # noqa: E402
import theme               # noqa: E402

# 每个方案只写「跟全宋体不一样」的那几个角色，其余沿用 theme 的基准
# 只切正文字族（与「设置 → 字体」的行为一致）。正式使用请走设置面板，
# 这里只是省去点五次菜单的快速对比。
SCHEMES = [
    ("1 · 黑体（默认）", "Microsoft YaHei"),
    ("2 · 宋体", "SimSun"),
    ("3 · 楷体", "KaiTi"),
    ("4 · 华文中宋", "STZhongsong"),
    ("5 · 隶书", "LiSu"),
]


def main() -> None:
    selftest = os.environ.get("FONT_LIVE_SELFTEST") == "1"
    root = tk.Tk()
    if selftest:                        # 自测：放屏幕外 + 全透明，跑完就退
        root.geometry("+4000+4000")
        root.attributes("-alpha", 0.0)
    app = app_main.App(root)
    root.update_idletasks()
    root.update()
    app.analyze()                       # 直接读一次桌面，省得先点按钮

    def usable(fam: str) -> bool:
        """族名解析不到就退回宋体，别让某个方案把界面搞成默认字体。

        注意：tkfont 的 actual("family") 返回的是**中文名**（"STZhongsong" → "华文中宋"），
        所以不能拿英文族名去比对。这里只认一件事：解析结果是不是回落基准「宋体」。
        不存在的族名一律静默回落成宋体，正好可以当判据用。
        """
        try:
            probe = tkfont.Font(root=root, family=fam, size=12)
            got = str(probe.actual("family"))
            root.tk.call("font", "delete", probe.name)
        except tk.TclError:
            return False
        return fam == "SimSun" or got != "宋体"

    state = {"idx": 0}

    def paint(idx: int) -> None:
        """只改字体表，不重建界面。"""
        fam = SCHEMES[idx][1]
        app.f = theme.fonts(theme.step_scale(app.fs_i),
                            fam if usable(fam) else theme.BODY_FALLBACK)

    def apply(idx: int) -> None:
        state["idx"] = idx
        paint(idx)
        app._rebuild()
        tip = SCHEMES[idx][0]
        if not usable(SCHEMES[idx][1]):
            tip += "　（本机没有这个字体，已退回黑体）"
        app.status.configure(
            text="%s　—　按 1-5 换正文字体，正式版请走「设置 → 字体」" % tip)

    # 改字号会按 theme 重新生成字体表，把当前方案盖掉 → 包一层补回来
    _orig_bump = app.bump_font

    def bump(delta: int) -> None:
        _orig_bump(delta)
        paint(state["idx"])

    app.bump_font = bump

    def on_key(event) -> None:
        """数字键 1-5 换方案。输入框里打字时不抢键。"""
        try:
            focus = root.focus_get()
            cls = focus.winfo_class() if focus is not None else ""
        except (tk.TclError, AttributeError):
            cls = ""
        if cls in ("Entry", "Text", "TEntry", "TCombobox"):
            return
        ch = (event.char or "").strip()
        if ch.isdigit() and 1 <= int(ch) <= len(SCHEMES):
            apply(int(ch) - 1)

    root.bind_all("<Key>", on_key)
    root.bind("<Escape>", lambda _e: root.destroy())

    apply(0)
    if selftest:
        for i in range(len(SCHEMES)):
            apply(i)
            root.update()
            print("selftest ok: %s → brand=%s gua=%s"
                  % (SCHEMES[i][0], app.f["brand"][0], app.f["gua"][0]))
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
