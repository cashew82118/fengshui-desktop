# -*- coding: utf-8 -*-
"""第二轮阶段 6/7/8 冒烟测试：启动闸门、四选项卡、设置浮层。全程不显示窗口。"""
import sys
import time
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import theme  # noqa: E402
import render  # noqa: E402
from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402
import history  # noqa: E402

HIST_FILE = ROOT / "data" / "history.jsonl"
HIST_SNAP = HIST_FILE.read_text(encoding="utf-8") if HIST_FILE.exists() else None

enable_dpi_awareness()
root = tk.Tk()
root.withdraw()


def pump(ms: float = 0.05) -> None:
    end = time.time() + ms
    while time.time() < end:
        try:
            root.update()
        except tk.TclError:
            return
        time.sleep(0.004)


# ---------------- 1. 启动闸门：构造不读不算 ----------------
app = app_main.App(root)
root.update_idletasks()
root.update()

assert app.ready is False, "构造后 ready 应为 False"
assert app.layout is None, "构造后不应读取桌面"
assert app.result is None
assert app.score_lbl.cget("text") == "—", "未分析时分数应是 —"
assert "尚未分析" in app.grade_lbl.cget("text"), "未分析时断语应提示"
assert app.btn_export.instate(["disabled"]), "导出报告未置灰"
# 「导出给 AI」已并入问 AI 栏，顶栏不该再有这个按钮
assert not hasattr(app, "btn_export_ai"), "顶栏「导出给 AI」应已移除"
assert hasattr(app, "ai_export_chip"), "问 AI 栏应有导出按钮"

# 盘上是空盘 + 开始分析按钮
tags = {app.board.itemcget(i, "tags") for i in app.board.find_all()}
assert any("startbtn" in t for t in tags), "盘中央没有「开始分析」按钮"
assert app._btn_hit is not None
print("[ok] 启动闸门：不读不算，盘中央有「开始分析」，导出全部置灰")

# ---------------- 2. 点击才开始分析 ----------------
app.analyze()
root.update_idletasks()
root.update()
assert app.ready is True
assert app.layout is not None and app.result is not None
assert app.score_lbl.cget("text") == str(app.result["score"]), "分析后分数没显示"
assert app.btn_export.instate(["!disabled"]), "分析后导出报告仍置灰"
assert len(app.hits) == len(app.layout["icons"]), "分析后盘没画出来"
assert len(app.gear.find_all()) >= 3, "齿轮初始没有画出来（要等悬停）"
assert app.box2.winfo_children()[0] is app.topbar, "选项卡栏不在右栏最顶"
assert str(app.pane_judge) in str(app.score_lbl), "分数卡不在断语栏内"
assert app.cards.winfo_children(), "分析后默认分条没有内容"
print("[ok] 点击后开始分析：%d 分，%d 个图标；齿轮初始可见、"
      "选项卡在最顶、分条默认有内容"
      % (app.result["score"], len(app.layout["icons"])))

# ---------------- 3. 四个一级选项卡 ----------------
for key in ("owner", "ai", "hist", "judge"):
    app._top(key)
    root.update_idletasks()
    assert app.top_tab == key
    panes = {"judge": app.pane_judge, "owner": app.pane_owner,
             "ai": app.pane_ai, "hist": app.pane_hist}
    assert panes[key].winfo_manager() == "pack", "切到 %s 失败" % key
app._top("owner")
kids = app.pane_owner.winfo_children()
assert kids, "命主页是空的（应有占位说明）"
app._top("ai")
kids = app.pane_ai.winfo_children()
assert kids, "问 AI 页是空的（应有占位说明）"
app._top("judge")
assert app.pane_judge.winfo_manager() == "pack"
print("[ok] 四个一级选项卡互切正常，命主/问 AI 有占位说明")

# 二级页签只在断语栏里
app._tab("prose")
assert app.sub_tab == "prose" and app.pane_prose.winfo_manager() == "pack"
# 总评排版：tag 驱动、颜色全走主题、不注入全角空格缩进
# 总评自 2026-10-27 起跟随「设置 → 字体」，不再固定宋体
assert app.f["prose"][0] in str(app.prose_text.cget("font")), \
    "总评字体应跟随正文字族：%s" % app.prose_text.cget("font")
assert app.prose_text.cget("fg") == theme.get(app.theme_name)["ink"], \
    "正文字色应为主题 ink"
pt = int(str(app.prose_text.cget("font")).rsplit(" ", 1)[1])
ppx = max(12, int(round(pt * 4.0 / 3.0)))
para = int(app.prose_text.tag_cget("body", "lmargin1"))
assert para == 2 * ppx, "首行缩进应为 2em（%dpx），实为 %s" % (2 * ppx, para)
assert int(app.prose_text.tag_cget("body", "spacing2")) >= 4, "正文行距未配置"
assert int(app.prose_text.tag_cget("body", "spacing3")) >= 10, "段后距未配置"
assert not app.prose_text.get("1.0", "end").strip().startswith("　　"), \
    "缩进应走 lmargin1 tag，不再注入全角空格"
# 限宽：传入假事件宽度（withdraw 下 winfo_width 恒为 1，测不了真实宽度）
import types  # noqa: E402


def padl_of():
    px = app.prose_body.pack_info()["padx"]
    return px[0] if isinstance(px, tuple) else px


app._prose_fit(types.SimpleNamespace(width=1000))
assert padl_of() == 24 + (1000 - 48 - 640) // 2, "限宽未生效：padx=%s" % (padl_of(),)
app._prose_fit(types.SimpleNamespace(width=400))
assert padl_of() == 24, "窄面板应回到 24px 基础留白"
app._tab("cards")
assert app.pane_cards.winfo_manager() == "pack"
print("[ok] 断语栏二级页签正常；总评为 tag 排版（2em 缩进 / 行高 / 段距 14px / 限宽）")

# ---------------- 4. 设置：Windows 原生弹窗（Toplevel） ----------------
app.open_settings()
root.update_idletasks()
assert app._gear_open is True
p = app.settings_panel
assert isinstance(p, tk.Toplevel), "设置应是 Toplevel 原生弹窗"
# withdraw 测试环境：open_settings 不得 deiconify（否则测试会在屏幕上弹真窗口）
assert not p.winfo_ismapped(), "主窗口 withdraw 时设置弹窗不该显示"
assert len(app.gear.find_all()) >= 3, "齿轮没有画出来"
print("[ok] 设置为 Toplevel 原生弹窗；withdraw 下不弹真窗口、状态照常记账")

# 浮层开着也能换主题，且浮层不消失
app.set_theme("ink")
root.update_idletasks()
root.update()
assert app._gear_open is True, "换主题后浮层被关掉了"
assert app.root.cget("bg") == theme.get("ink")["bg"]
app.set_theme("paper")
root.update_idletasks()
assert app._gear_open is True
print("[ok] 浮层开着换主题/字号，实时生效且浮层保持")

app.bump_font(1)
root.update_idletasks()
assert app._gear_open is True
app.bump_font(-1)
root.update_idletasks()
print("[ok] 浮层里调字号正常")

app.close_settings()
root.update_idletasks()
assert app._gear_open is False
assert not app.settings_panel.winfo_ismapped(), "设置弹窗没有收起"
print("[ok] 设置弹窗关闭")

# 关闭必须无条件安全：状态没开、从没 grab 过，调用也不能出错（防悬空模态）
app._gear_open = False
app.close_settings()
assert app._gear_open is False
print("[ok] close_settings 未打开时调用也安全（grab 防悬空）")

# 动效开关（控件已迁入浮层，逻辑仍要工作）
before = app.anim_on
app.toggle_anim()
assert app.anim_on is not before
app.toggle_anim()
assert app.anim_on is before
print("[ok] 动效开关仍可用（控件已迁到浮层）")

# ---------------- 5. 闸门下朝向切换不炸 ----------------
app.orient_var.set("上方朝东")
app._on_orient(None)
root.update_idletasks()
assert app.top_dir == 90
app.orient_var.set("上方朝南 · 坐北朝南")
app._on_orient(None)
root.update_idletasks()
print("[ok] 未分析的空盘上切朝向不报错（但不会算分）")

root.destroy()

if HIST_SNAP is None:
    HIST_FILE.unlink(missing_ok=True)
else:
    HIST_FILE.write_text(HIST_SNAP, encoding="utf-8")
print("[ok] 已还原历史记录，测试未污染真实数据")

print("\n阶段 6/7/8 冒烟测试全部通过")
