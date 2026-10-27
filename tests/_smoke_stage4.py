# -*- coding: utf-8 -*-
"""阶段四冒烟测试：HTML 报告、历史记录、离线自检。不显示窗口、不打开浏览器。"""
import json
import re
import sys
import tkinter as tk
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import fengshui  # noqa: E402
import history  # noqa: E402
import report  # noqa: E402

HIST_FILE = ROOT / "data" / "history.jsonl"
HIST_SNAP = HIST_FILE.read_text(encoding="utf-8") if HIST_FILE.exists() else None

RAW = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json").read_text(encoding="utf-8"))
layout = json.loads(json.dumps(RAW))
res = fengshui.analyze(layout, 180)

# ---------------- 1. HTML 报告 ----------------
html_text = report.build_html(layout, res, prev={"t": "2026-10-24T00:40:00", "score": 50})

assert html_text.startswith("<!DOCTYPE html>")
assert "桌面风水" in html_text
assert str(res["score"]) in html_text
assert "中宫空" in html_text or "中宫" in html_text
assert "五行" in html_text and "八角" not in html_text
print("[ok] HTML 结构完整，%d 字节" % len(html_text.encode("utf-8")))

# 离线自检：不许有外链、脚本、图片引用
bad = []
if "<script" in html_text.lower():
    bad.append("<script>")
if re.search(r'https?://(?!www\.w3\.org/2000/svg)', html_text):
    bad.append("外部 URL")
if re.search(r'<(img|link|iframe)\b', html_text, re.I):
    bad.append("外链标签")
if "@import" in html_text or "url(" in html_text.lower():
    bad.append("CSS 外链")
assert not bad, "发现离线违规：%s" % bad
print("[ok] 无脚本、无外链、无图片引用（仅 SVG 命名空间除外）")

# 交互自检：报告里每块盘都要能悬停看名称（4 块盘 × 图标数）
n_icon = len(layout["icons"])
assert html_text.count('class="ic"') == n_icon * 4, \
    "图标分组数量不对：%d" % html_text.count('class="ic"')
assert html_text.count('class="tip"') == n_icon * 4, \
    "提示文本数量不对：%d" % html_text.count('class="tip"')
import html as _html
sample = _html.escape(layout["icons"][0]["name"])
assert ">%s</text>" % sample in html_text, "提示里没有图标名"
for must in ("@keyframes", ".ic:hover .tip{opacity:1}", "prefers-reduced-motion",
             ".tip{display:none}"):
    assert must in html_text, "报告缺少交互样式：%s" % must
print("[ok] 悬停提示 %d 处，动效纯 CSS、打印与减动效下自动关闭" % (n_icon * 4))

# 关键内容抽查
for must in ("理　", "改　", "对账", "未上传任何数据", "未修改桌面"):
    assert must in html_text, "报告缺少：%s" % must
print("[ok] 四要素、对账、免责声明齐全")

# ---------------- 2. 历史记录 ----------------
before = len(history.read_all())
history.append(res["score"], res["grade"], [0] * 9, res["stats"]["total"])
after = history.read_all()
assert len(after) >= before
rec = after[-1]
assert set(rec) == {"t", "score", "grade", "total", "counts",
                    "rubric"}, "历史字段不符: %s" % set(rec)
assert rec["rubric"] == history.RUBRIC, "口径版本应记成 %s" % history.RUBRIC
# 旧记录没有 rubric 字段时按 1 处理（趋势图靠这个画分界线）
assert history.rubric_of({"score": 80}) == 1
assert history.rubric_of(rec) == history.RUBRIC
assert "name" not in json.dumps(rec, ensure_ascii=False), "历史里混进了文件名"
print("[ok] 历史追加成功，字段只有 %s，无文件名" % sorted(set(rec)))

# ---------------- 3. 导出文件 ----------------
path = report.export(layout, res, prev=None)
assert path.exists() and path.suffix == ".html"
text2 = path.read_text(encoding="utf-8")
assert "<!DOCTYPE html>" in text2
print("[ok] 导出文件 %s（%.1f KB）" % (path.name, path.stat().st_size / 1024))

# ---------------- 4. 窗口：导出按钮与历史行 ----------------
import main as app_main  # noqa: E402
from desk_reader import enable_dpi_awareness  # noqa: E402

enable_dpi_awareness()        # 必须先声明，否则 125% 缩放下宫位会算错
root = tk.Tk()
root.withdraw()
app = app_main.App(root)
app.analyze()                # 启动闸门：测试里显式触发分析
root.update_idletasks()
root.update()
assert app.result is not None
assert app.prev_lbl.cget("text"), "历史行未渲染"
assert app.prose_text.get("1.0", "end").strip(), "总评为空"
app._tab("prose")
assert app.pane_prose.winfo_manager() == "pack", "切到总评失败"
app._tab("cards")
assert app.pane_cards.winfo_manager() == "pack", "切回分条失败"
assert not any("超出画布" in w for w in app.layout["warnings"]), \
    "DPI 未声明导致坐标越界：%s" % app.layout["warnings"]
assert sum(app.result["stats"]["counts"].values()) == app.result["stats"]["total"], \
    "九宫计数之和与图标总数不符"
print("[ok] 窗口历史行：%s" % app.prev_lbl.cget("text"))
print("[ok] 总评 %d 字，分条/总评切换正常"
      % len(app.prose_text.get("1.0", "end").strip()))
print("[ok] 无坐标越界警告，DPI 声明生效")
root.destroy()

if HIST_SNAP is None:
    HIST_FILE.unlink(missing_ok=True)
else:
    HIST_FILE.write_text(HIST_SNAP, encoding="utf-8")
print("[ok] 已还原历史记录")

print("\n阶段四冒烟测试全部通过")
