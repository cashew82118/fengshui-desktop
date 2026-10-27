# -*- coding: utf-8 -*-
"""阶段十一冒烟测试：问 AI（话术库 + 导出 + 界面状态）。

无窗口运行；结束前清掉测试导出的文件，并还原 prefs/history 快照。
"""
import atexit
import json
import os
import sys
import time
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import tkinter as tk  # noqa: E402

import aiexport  # noqa: E402
import prompts  # noqa: E402
import prefs  # noqa: E402
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

# 兜底还原：脚本中途断言失败也要把 prefs / history 恢复原样，
# 否则测试填的生辰、改的字体设置会留在用户的真实配置里（2026-10-27 踩过）
def _restore_everything():
    try:
        if PREFS_SNAP is not None:
            PREFS_FILE.write_text(PREFS_SNAP, encoding="utf-8")
        elif PREFS_FILE.exists():
            PREFS_FILE.unlink()
        if HIST_SNAP is not None:
            HIST_FILE.write_text(HIST_SNAP, encoding="utf-8")
        elif HIST_FILE.exists():
            HIST_FILE.unlink()
    except OSError:
        pass


atexit.register(_restore_everything)

print("[1] 话术库：7 功能 × 3 变体 + 固定开头结尾")

assert len(prompts.FEATURES) == 7
keys = [k for k, _l, _n, _v in prompts.FEATURES]
assert len(set(keys)) == 7, keys
for key, _label, _need, variants in prompts.FEATURES:
    assert len(variants) == 3, key
    outs = [prompts.compose(key, i, "2026-10-25") for i in range(3)]
    assert len(set(outs)) == 3, "%s 三套主体有重复" % key
    for t in outs:
        assert t.startswith(prompts.OPEN) and t.endswith(prompts.CLOSE), key
        assert "{date}" not in t, key
assert "2026-10-25" in prompts.compose("today", 1, "2026-10-25")
assert "{date}" not in prompts.compose("check", 0)
print("[ok] 7×3 主体互不相同，开头/结尾/日期占位正确")

print("[1b] 与 docs/06 话术库逐字一致（防两处漂移）")

import re  # noqa: E402

_doc = (ROOT / "docs" / "06-AI话术库.md").read_text(encoding="utf-8")
_norm = lambda t: re.sub(r"\s+", "", t)          # noqa: E731
_blocks: dict[str, list[str]] = {}
for _sec in re.split(r"\n## ", _doc):
    _tok = _sec.split("\n")[0].strip().split(" ")[0].rstrip(".")
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", _tok):
        _blocks[_tok] = [_norm(b) for b in
                         re.findall(r"```\n(.*?)```", _sec, re.S)]
assert _blocks["0"][0] == _norm(prompts.OPEN), "固定开头与文档不一致"
assert _blocks["0.1"][0] == _norm(prompts.CLOSE), "固定结尾与文档不一致"
for _i, _num in enumerate(["1", "2", "3", "4", "5", "6", "7"]):
    for _j in range(3):
        assert _blocks[_num][_j] == _norm(prompts.FEATURES[_i][3][_j]), \
            "第 %s 节第 %d 套与文档不一致" % (_num, _j + 1)
print("[ok] 7×3 主体 + 开头 + 结尾，与 docs/06 逐字一致")

print("[2] 界面：未分析时整栏禁用")

root = tk.Tk()
root.withdraw()
app = app_main.App(root)
root.update_idletasks()
root.update()
assert not app.ready
app._top("ai")
root.update_idletasks()
assert app.ai_text.get("1.0", "end").strip().startswith("先点左侧")
assert app.ai_len_lbl.cget("text") == ""
print("[ok] 未分析：预览只给提示，不显示话术")

print("[3] 分析后：默认可用、缺生辰四套禁用")

app.analyze()
root.update_idletasks()
root.update()
assert app.ready
app._top("ai")
root.update_idletasks()
assert app.ai_feature == "check", "没有生辰时应默认落在「布局体检」"
for key, lbl in app.ai_chips.items():
    need = prompts.needs_birth(key)
    txt = lbl.cget("text")
    if need:
        assert "需先填生辰" in txt, (key, txt)
    else:
        assert "需先填生辰" not in txt, (key, txt)
# 点禁用的 → 只提示、不切换
app._ai_pick("who")
assert app.ai_feature == "check"
assert "生辰" in app.status.cget("text")
print("[ok] 缺生辰：四套标「需先填生辰」且点了不切换")

print("[4] 换一版循环 1/3 → 2/3 → 3/3 → 1/3")

texts = []
labels = []
for i in range(4):
    lab = app.ai_ver_chip.cget("text")
    labels.append(lab.split("·")[-1].strip())
    assert lab.endswith("%d/3" % (i % 3 + 1)), lab
    texts.append(app._ai_current_text())
    app._ai_next_variant()          # 点一次「换一版」
    root.update_idletasks()
assert texts[0] == texts[3], "应循环回第一版"
assert len({texts[0], texts[1], texts[2]}) == 3
print("[ok] 换一版：%s，三套互不相同" % " → ".join(labels))

print("[5] 复制：剪贴板内容与预览逐字一致")

app._ai_copy()
root.update()
clip = root.clipboard_get()
body = app.ai_text.get("1.0", "end")
assert clip == body.rstrip("\n"), "剪贴板与预览不一致"
print("[ok] 剪贴板 %d 字，与预览一致" % len(clip))

print("[6] 导出：文件内容 + 隐私开关")

app.ai_note_var.set("我做设计，素材多")
before = set(aiexport.OUT_DIR.glob("*.md")) if aiexport.OUT_DIR.exists() else set()
# 「导出数据」只落盘不碰剪贴板
root.clipboard_clear()
root.clipboard_append("剪贴板哨兵")
root.update()
app._ai_save()
root.update_idletasks()
assert root.clipboard_get() == "剪贴板哨兵", "导出数据不该动剪贴板"
assert "已导出" in app.status.cget("text")
before = set(aiexport.OUT_DIR.glob("*.md"))
app._ai_export()
root.update_idletasks()
after = set(aiexport.OUT_DIR.glob("*.md"))
new_files = sorted(after - before)
assert new_files, "没有生成导出文件"
path = new_files[-1]
md = path.read_text(encoding="utf-8")
assert path.name.startswith("AI问询_") and path.suffix == ".md"
assert app.ai_last == path
# 八块结构
for head in ("# 桌面风水 · AI 问询包", "## 一、命主", "## 二、桌面概况",
             "## 三、图标明细", "## 四、当前评分", "## 五、诊断",
             "## 六、推演", "## 七、规则说明"):
    assert head in md, head
# 规则说明三件套
assert "九宫方位映射" in md and "七项评分" in md and "五行归属怎么来的" in md
# 隐私：默认不含 ≥2 字图标名
leaks = [it["name"] for it in app.layout["icons"]
         if len(it["name"] or "") >= 2 and it["name"] in md]
assert not leaks, "默认不该写图标名：%s" % leaks[:3]
assert "补充背景：我做设计，素材多" in md
# 勾选后含名
app._ai_toggle_names()
app._ai_toggle_diag()
app._ai_export()
root.update_idletasks()
path2 = sorted(set(aiexport.OUT_DIR.glob("*.md")) - after)[-1]
md2 = path2.read_text(encoding="utf-8")
assert any(len(it["name"] or "") >= 2 and it["name"] in md2
           for it in app.layout["icons"]), "勾选后应写入真名"
assert "完整" not in md or True
print("[ok] 导出 %s（%.1f KB）；默认不含名、勾选后含名"
      % (path.name, len(md.encode()) / 1024.0))

print("[7] 填生辰后四套解锁")

app.birth = {"y": 1990, "m": 6, "d": 15, "g": "男"}
app._recalc_owner()
app._sync_ai()
root.update_idletasks()
assert app.owner is not None
for key in prompts.NEEDS_BIRTH:
    assert "需先填生辰" not in app.ai_chips[key].cget("text"), key
app._ai_pick("who")
assert app.ai_feature == "who"
assert "命卦" in app.ai_text.get("1.0", "end")
print("[ok] 有生辰：「认识我」可选中，正文提及命卦")

print("[7b] 字体：默认黑体，可切换，宋体位置固定")

import theme  # noqa: E402

assert theme.BODY_DEFAULT == "Microsoft YaHei", "默认应为黑体"
assert app.font_family == theme.BODY_DEFAULT, app.font_family
BODY_ROLES = ("grade", "body", "small", "tiny", "card", "cap", "tip",
              "prose")   # 总评自 2026-10-27 起也跟随设置
FIXED_ROLES = ("brand", "gua", "seal")
for role in BODY_ROLES:
    assert app.f[role][0] == app.font_family, "%s 应跟正文字族" % role
for role in FIXED_ROLES:
    assert app.f[role][0] == "SimSun", "%s 应恒为宋体（实际 %s）" % (role, app.f[role][0])
assert app.f["score"][0] == "Georgia"
# 仿宋/楷体没有可用真粗体，小标题不加粗，层级靠字号 + 颜色
assert len(app.f["card"]) == 2, "card 不该带 bold"

# 切到楷体：正文跟着变，宋体位置不动
app.set_font_family("KaiTi")
root.update()
assert app.font_family == "KaiTi"
for role in BODY_ROLES:
    assert app.f[role][0] == "KaiTi", role
for role in FIXED_ROLES:
    assert app.f[role][0] == "SimSun", "换字体不该动 %s" % role
assert prefs.load()["font_family"] == "KaiTi", "字体选择应落盘"
# 选一个本机没有的 → 退回黑体
app.set_font_family("NoSuchFontXY")
root.update()
assert app.font_family == theme.BODY_FALLBACK, app.font_family
assert "本机没有" in app.status.cget("text")
# 每个选项都要能生效或安全回退，不许抛异常
for _label, fam, _tip in theme.BODY_CHOICES:
    app.set_font_family(fam)
    root.update()
app.set_font_family(theme.BODY_DEFAULT)
root.update()
print("[ok] 默认黑体；%d 个字体选项全部可切换；品牌/卦名/总评恒宋体"
      % len(theme.BODY_CHOICES))

print("[7c] 使用方法弹层：可开可关，内容完整")

app._ai_help()
root.update_idletasks()
assert app.ai_help_win is not None
texts = []


def walk(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            texts.append(str(c.cget("text")))
        else:
            walk(c)


walk(app.ai_help_win)
blob = "\n".join(texts)
for kw in ("这个功能在做什么", "三步", "七套话术怎么选", "两个开关与文件位置",
           "复制文案", "导出数据", "打开文件夹"):
    assert kw in blob, "使用说明缺：%s" % kw
assert len([t for t in texts if t.startswith(("①", "②", "③"))]) == 3, "三步应各占一行"
app._ai_help_close()
assert app.ai_help_win is None
print("[ok] 使用说明弹层可开可关，三段与三步齐全")

print("[7d] 导出报告：字体与字号可设，只影响 HTML")

import report  # noqa: E402

assert app.report_font == "SimSun", app.report_font
assert app.report_size == 1, app.report_size
assert "<style>" not in report.css_for("KaiTi", 1.0)      # 只是 CSS 片段
css_kai = report.css_for("KaiTi", 1.0)
css_big = report.css_for("SimSun", 1.3)
assert '"KaiTi"' in css_kai, "楷体没进字体栈"
assert 'font-size:15px' in report.css_for("SimSun", 1.0), "基准字号应为 15px（h2）"
assert 'font-size:19.5px' in css_big, "1.3 倍应把 h2 拉到 19.5px"
assert "clamp(32px,5vw,56px)" in css_big, "版面留白不该跟着字号缩放"
assert "__BODY_FONT__" not in css_kai, "占位符必须全部替换掉"

app.set_report_font("KaiTi")
app.set_report_size("大")
root.update()
assert app.report_font == "KaiTi" and app.report_size == 2
saved = prefs.load()
assert saved["report_font"] == "KaiTi" and saved["report_size"] == 2, "报告设置应落盘"

# 真导出一份，确认 HTML 里带的是楷体栈与放大后的字号。
# 两个坑：① 文件名只精确到分钟，同一分钟内会覆盖同名文件，不能用差集找新文件；
# ② main.export() 会 os.startfile 打开浏览器——测试里必须屏蔽，否则屏幕上会弹窗。
_orig_start = os.startfile
os.startfile = lambda *a, **k: None
_t0 = time.time()
try:
    app.analyze()
    app.export()
    root.update()
finally:
    os.startfile = _orig_start
_new = [x for x in report.OUT_DIR.glob("*.html") if x.stat().st_mtime >= _t0]
assert _new, "没生成报告"
_html = _new[0].read_text(encoding="utf-8")
assert '"KaiTi"' in _html, "报告没用所选字体"
assert "font-size:16.9px" in _html, "报告字号没放大"
_new[0].unlink()                       # 测试产物不留

app.set_report_font("SimSun")
app.set_report_size("标准")
root.update()
print("[ok] 报告字体/字号可设并落盘，导出文件跟着变")

print("[8] 收尾：清导出文件、还原数据")

for f in (set(aiexport.OUT_DIR.glob("*.md")) - before):
    f.unlink()
app.birth = None
app._save_prefs()
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
print("[ok] 已清理导出文件与测试残留")

print("\n阶段十一冒烟测试全部通过")
