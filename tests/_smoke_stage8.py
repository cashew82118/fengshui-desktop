# -*- coding: utf-8 -*-
"""阶段九冒烟测试：五行对应表编辑器（独立弹窗）+ 滚动防御。

无窗口运行（withdraw），不弹任何真窗口；
结束前还原 rules.json / history.jsonl 快照，不污染真实数据。
"""
import json
import sys
import types
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import tkinter as tk  # noqa: E402

import theme  # noqa: E402
import classify  # noqa: E402
import rules  # noqa: E402
import software  # noqa: E402
from desk_reader import enable_dpi_awareness  # noqa: E402
import main as app_main  # noqa: E402

enable_dpi_awareness()

HIST_FILE = ROOT / "data" / "history.jsonl"
HIST_SNAP = HIST_FILE.read_text(encoding="utf-8") if HIST_FILE.exists() else None
RULES_FILE = rules.PATH
RULES_SNAP = RULES_FILE.read_text(encoding="utf-8") if RULES_FILE.exists() else None

print("[1] 数据层：classify 接入覆盖层")

rules.reset()


def cls(name, ext="", kind="file"):
    return classify.classify({"name": name, "ext": ext, "kind": kind})


probe = "LosslessCut.exe - 快捷方式"
before = cls(probe, ".lnk")[0]
rules.set_rule("software", "LosslessCut", "木")
wx, src, why = cls(probe, ".lnk")
assert (wx, src) == ("木", "user"), (wx, src, why)
rules.reset()
assert cls(probe, ".lnk")[0] == before, "恢复默认后应回到内置判定"
print("[ok] 覆盖生效且可恢复（内置基准：%s）" % before)

ok, _ = rules.set_rule("software", "  ", "木")
assert not ok, "空键必须拒绝"
ok, _ = rules.set_rule("software", "X", "光")
assert not ok, "非法五行必须拒绝"
rules.set_rule("ext", "ABC", "木")
assert ".abc" in rules.load()["ext"], "ext 键应补点并小写"
rules.reset()
print("[ok] 非法输入拒绝、ext 键规范化")

print("[2] 窗口层：闸门 → 分析 → 编辑器弹窗（记账不弹真窗）")

root = tk.Tk()
root.withdraw()
app = app_main.App(root)
root.update_idletasks()
root.update()

app.analyze()
root.update_idletasks()
root.update()
assert app.ready and app.result

app.open_settings()
root.update_idletasks()
assert app._gear_open and isinstance(app.settings_panel, tk.Toplevel)
assert not app.settings_panel.winfo_ismapped(), "withdraw 下不得弹真窗口"

app._rule_editor_open()
root.update_idletasks()
assert app.rule_win is not None and isinstance(app.rule_win, tk.Toplevel)
assert not app.rule_win.winfo_ismapped(), "编辑器在 withdraw 下不得显示"

all_rows = app._rule_rows_all()
builtin_n = sum(1 for r in all_rows if not r["user"])
assert builtin_n >= 800, "内置条目数不对：%d" % builtin_n
assert len(app.rule_tree.get_children()) == len(all_rows), "列表未全部载入"
tables_seen = {app.rule_tree.set(i, "table") for i in app.rule_tree.get_children()}
assert tables_seen == {"软件名", "关键词", "扩展名"}, tables_seen
print("[ok] 编辑器载入全部对应：%d 条（内置 %d）" % (len(all_rows), builtin_n))

# 弹窗栈：换主题销毁重建后，编辑器原样恢复
app.set_theme("ink")
root.update_idletasks()
root.update()
assert app.rule_win is not None and not app.rule_win.winfo_ismapped(), \
    "换主题后编辑器应销毁重建且保持隐藏"
assert app._gear_open is True
app.set_theme("paper")
root.update_idletasks()
assert app.rule_win is not None
# 关闭与重开（withdraw 下只是状态与窗口映射切换，不弹真窗）
app._rule_editor_close()
assert not app.rule_win.winfo_ismapped()
app._rule_win_show()
assert not app.rule_win.winfo_ismapped(), "withdraw 下 show 不得真显示"
print("[ok] 换主题后编辑器原样恢复；关闭/重开生命周期正常")

print("[3] 搜索过滤")

app.rule_search_var.set("steam")
n_filtered = len(app.rule_tree.get_children())
assert 0 < n_filtered < len(all_rows), "搜索未过滤：%d" % n_filtered
for iid in app.rule_tree.get_children():
    assert "steam" in app.rule_tree.set(iid, "key").lower(), iid
print("[ok] 搜索「steam」→ %d 条，全部含关键词" % n_filtered)

print("[4] 修改：内置条目写入覆盖，立即生效")

iid = "software|steam"
app.rule_tree.selection_set(iid)
app.rule_tree.update()
assert app.rule_edit_var.get() == "火", "选中应同步当前五行"
app.rule_edit_var.set("木")
app._rule_apply()
root.update_idletasks()
assert rules.load()["software"].get("steam") == "木"
assert cls("Steam")[0] == "木" and cls("Steam")[1] == "user"
users = [i for i in app.rule_tree.get_children()
         if app.rule_tree.set(i, "src") == "自定义添加"]
assert len(users) == 1, "覆盖条目应在列表中标为「自定义添加」"
print("[ok] 「steam」→木（内置火被覆盖），归类即时生效")

print("[5] 删除：内置拒绝，覆盖可删")

app.rule_search_var.set("")
n_all = len(app.rule_tree.get_children())
app.rule_tree.selection_set("keyword|studio")     # 内置语义词典条目
n_before = rules.count("keyword") + rules.count("software") + rules.count("ext")
app._rule_del_sel()
assert "不能删除" in app.status.cget("text"), "内置条目删除应被拒绝"
n_after = rules.count("keyword") + rules.count("software") + rules.count("ext")
assert n_after == n_before, "内置条目不该被删"

app.rule_tree.selection_set("software|steam")     # 刚才的覆盖条目
app._rule_del_sel()
root.update_idletasks()
assert "steam" not in rules.load()["software"], "覆盖条目应被删除"
assert cls("Steam")[0] == "火" and cls("Steam")[1] == "software"
print("[ok] 内置拒绝删除；覆盖删除后回归内置判定（火）")

print("[6] 新增：选类别 + 键 + 五行")

app.rule_new_table.set("ext")
app.rule_new_key.insert(0, "abc")
app.rule_new_wx.set("火")
app._rule_add_new()
root.update_idletasks()
assert rules.load()["ext"].get(".abc") == "火"
assert cls("whatever", ".xyz") == cls("whatever", ".xyz")  # 占位防误删
assert classify.classify({"name": "w", "ext": ".abc", "kind": "file"})[0] == "火"
print("[ok] 新增扩展名覆盖 .abc → 火")

print("[7] 恢复默认（确认框自动应答）")

orig_ask = app_main.messagebox.askyesno
app_main.messagebox.askyesno = lambda *a, **k: False
app._rule_reset()
assert rules.count("ext") == 1, "选「否」不应删除"
app_main.messagebox.askyesno = lambda *a, **k: True
app._rule_reset()
assert rules.count("ext") == 0 and not rules.PATH.exists()
app_main.messagebox.askyesno = orig_ask
print("[ok] 选是才删 rules.json")

print("[8] 滚动防御：分条栏内容不足/到边界时不再滚动")

app.close_settings()
root.update_idletasks()
# 未分析状态：清空结果回到空态
app.ready = False
app.result = None
app._refresh_right()
root.update_idletasks()
app._tab("cards")
assert app.scroll.cget("scrollregion") == "", \
    "空内容应清空 scrollregion：%r" % app.scroll.cget("scrollregion")
ev = types.SimpleNamespace(delta=-120)
app._on_wheel(ev)                                  # 不报错、不动
print("[ok] 未分析：scrollregion 已清空，向上滚无效")

app.analyze()
root.update_idletasks()
root.update()
app._tab("cards")
app.scroll.yview_moveto(0.0)
root.update_idletasks()
# tkinter 约定：滚轮向上 delta=+120，向下 -120
app._on_wheel(types.SimpleNamespace(delta=120))    # 在顶向上滚
assert app.scroll.yview()[0] == 0.0, "顶部向上滚不应移动"
app.scroll.yview_moveto(1.0)
root.update_idletasks()
app._on_wheel(types.SimpleNamespace(delta=-120))   # 在底向下滚
assert app.scroll.yview()[1] >= 0.999, "底部向下滚不应移动"
app.scroll.yview_moveto(0.5)
root.update_idletasks()
app._on_wheel(types.SimpleNamespace(delta=120))    # 中段应正常滚
assert app.scroll.yview()[0] != 0.5, "中段滚动应生效"
print("[ok] 顶/底钳制生效，中段滚动正常")

print("[9] 未分析时改表不炸 + 现场还原")

app.ready = False
app._rule_add_new()                                # 键为空 → 拒绝
assert "五行对应表" in app.status.cget("text")
rules.reset()

app._rule_editor_close()
root.destroy()

if RULES_SNAP is None:
    if RULES_FILE.exists():
        RULES_FILE.unlink()
else:
    RULES_FILE.write_text(RULES_SNAP, encoding="utf-8")
if HIST_SNAP is None:
    if HIST_FILE.exists():
        HIST_FILE.unlink()
else:
    HIST_FILE.write_text(HIST_SNAP, encoding="utf-8")
print("[ok] 已还原 rules.json 与历史记录，测试未污染真实数据")

print("\n阶段九冒烟测试全部通过")
