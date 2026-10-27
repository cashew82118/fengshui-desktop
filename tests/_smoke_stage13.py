# -*- coding: utf-8 -*-
"""阶段十三冒烟测试：总评文案池（七项口径 + 5 变体）

只读不写：不碰 prefs / history，纯函数级别验证。

查五件事：
  1. 每个分支都恰好 5 条变体
  2. 同一分支内 5 条字数相当（极差 ≤ 12 字，长句骨架放宽到 16）
  3. 同一张桌面反复生成，文字完全一致（指纹稳定，不会刷新一次换一张脸）
  4. 极端桌面不抛异常、不留 `{占位符}`、段数固定 8、七项名齐全
  5. 顺手度低分时，总评确实谈顺手，且不退回兜底词「局面的顺逆」
"""
import copy
import re
import sys
from pathlib import Path

# 脚本住在 tests/ 或 tools/ 下，工程根是上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import json  # noqa: E402

import fengshui  # noqa: E402
import prose  # noqa: E402
import prose_pool  # noqa: E402

# 用 project 内的脱敏夹具，不读真实桌面——测试要可复现，也不该依赖谁的桌面
LAYOUT = json.loads((ROOT / "tests" / "fixtures" / "layout_sample.json")
                    .read_text(encoding="utf-8"))

# ---------------- 1. 分支与变体数量 ----------------
print("[1] 分支数与变体数")
sizes = prose_pool.sizes()
assert len(sizes) >= 85, "分支太少：%d" % len(sizes)
bad = {k: n for k, n in sizes.items() if n != 5}
assert not bad, "这些分支不是 5 条变体：%s" % bad
print("[ok] %d 个分支，每个 5 条变体，共 %d 条"
      % (len(sizes), sum(sizes.values())))

# ---------------- 2. 同一分支内字数相当 ----------------
print("[2] 变体字数相当")
wide = []
for k, items in prose_pool.POOL.items():
    if k == "clutter_mixed":          # 别名，与 clutter_other 同一份
        continue
    lens = [len(re.sub(r"\{[a-z_0-9]+\}", "X", t)) for t in items]
    limit = 16 if k == "intro_frame" else 12   # 骨架句本身长，按比例放宽
    if max(lens) - min(lens) > limit:
        wide.append((k, lens))
assert not wide, "字数差过大：%s" % wide
print("[ok] 88 个分支的 5 条变体，极差都不超过 12 字（骨架句 16）")

# ---------------- 3. 指纹稳定 ----------------
print("[3] 同一张桌面反复生成")
res = fengshui.analyze(LAYOUT, 180)
a = prose.compose(res)
b = prose.compose(res)
assert a == b, "同一份结果两次生成不一致（指纹不稳定）"
print("[ok] 两次生成逐段完全相同，共 %d 字" % sum(len(p) for p in a))

# ---------------- 4. 极端桌面不崩 ----------------
print("[4] 极端桌面")
base_icon = LAYOUT["icons"][0]


def build(rows_cols):
    icons = []
    for i, (r, c) in enumerate(rows_cols):
        it = copy.deepcopy(base_icon)
        it["name"] = "测试%d" % i
        it["row"], it["col"] = r, c
        icons.append(it)
    lay = dict(LAYOUT)
    lay["icons"] = icons
    return lay


CASES = {
    "空桌面": [],
    "全在中宫": [(1, 1)] * 20,
    "全在底行": [(2, i % 3) for i in range(20)],
    "全在左列": [(i % 3, 0) for i in range(24)],
    "只右列": [(i % 3, 2) for i in range(12)],
    "满九宫": [(r, c) for r in range(3) for c in range(3) for _ in range(6)],
}
for name, rc in CASES.items():
    r2 = fengshui.analyze(build(rc), 180)
    ps = prose.compose(r2)
    text = "".join(ps)
    assert "{" not in text and "}" not in text, "%s：留下占位符 %s" % (
        name, re.findall(r"\{[^}]*\}", text)[:3])
    assert len(ps) == 8, "%s：段数应为 8，实际 %d" % (name, len(ps))
    for w in ("中宫", "明堂", "四象", "形态", "杂物", "生克", "顺手"):
        assert w in ps[0], "%s：总起没提到「%s」" % (name, w)
    assert all(p.strip() for p in ps), "%s：有空白段" % name
print("[ok] %d 种极端桌面：无占位符残留、8 段、七项名齐全"
      % len(CASES))

# ---------------- 5. 顺手度真的被谈到了 ----------------
print("[5] 顺手度进总评")
# 造一个「顺手度低」的桌面：常用堆中宫、归档物占顺手位
hard = []
for i in range(22):
    it = copy.deepcopy(base_icon)
    it["name"] = "常用%d" % i
    it["row"], it["col"] = 1, 1
    hard.append(it)
for i, ext in enumerate((".torrent", ".zip", ".msi", ".exe", ".rar")):
    it = copy.deepcopy(base_icon)
    it["name"] = "包%d%s" % (i, ext)
    it["ext"] = ext.lstrip(".")
    it["row"], it["col"] = 0, i % 3
    hard.append(it)
lay_h = dict(LAYOUT)
lay_h["icons"] = hard
res_h = fengshui.analyze(lay_h, 180)
assert res_h["sections"]["comfort"]["score"] < 17, \
    "构造的桌面顺手度应该偏低：%s" % res_h["sections"]["comfort"]["score"]
ps_h = prose.compose(res_h)
text_h = "".join(ps_h)
assert "顺手" in text_h, "顺手度低却全文没提顺手"
assert "局面的顺逆" not in text_h, "出现了兜底词，说明 _NATURE 缺键"
assert "动手改一改" not in text_h, "出现了兜底动作，说明 _ACTION 缺键"
print("[ok] 顺手 %s/20 时，总评提到顺手，且无兜底词"
      % res_h["sections"]["comfort"]["score"])

print("\n阶段十三冒烟测试全部通过")
