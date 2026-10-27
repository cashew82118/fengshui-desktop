# -*- coding: utf-8 -*-
"""把可开源的部分同步到 `开源/`。

为什么需要它：开发目录里混着个人数据（data/ exports/ reports/）和构建产物，
不能整个丢进仓库；而源码在开发时又要随时改。所以留一份 `开源/` 作为发布副本，
改完代码跑一次本脚本即可，不用手工挑文件。

**只覆盖源码与文档，不碰 `开源/README.md`、`LICENSE`、`.gitignore`**——
那三份是发布物自己的门面，不该被开发目录覆盖。

用法：
    py -3 tools/_sync_open.py           # 实际同步
    py -3 tools/_sync_open.py --check   # 只报告差异，不写
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "开源"

# 整目录复制的部分
DIRS = ("app", "docs", "tests", "tools")
# 启动脚本**不参与同步**：开发目录的 bat 写死了本机 python 路径
# （开发机写的是本机 python 的绝对路径），发布版必须用 py 启动器才行。
# 两份各自维护，宁可手工改两次，也不要把绝对路径发出去。
FILES: tuple[str, ...] = ()

SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".bmp", ".png", ".exe"}

# 个别文件单独排除：_expand_apply.py 依赖 data/_expand_01.tsv，
# 那批中间文件早就删了，留着是死代码，不进发布包（开发目录仍保留备查）。
EXCLUDE_REL = {"tools/_expand_apply.py"}


def _iter_files(src: Path):
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIX:
            continue
        if p.relative_to(ROOT).as_posix() in EXCLUDE_REL:
            continue
        yield p


def main() -> int:
    check_only = "--check" in sys.argv
    if not DST.exists():
        print("开源/ 不存在，先建目录")
        if not check_only:
            DST.mkdir(parents=True)

    copied = same = 0
    for d in DIRS:
        src_dir = ROOT / d
        if not src_dir.is_dir():
            continue
        for src in _iter_files(src_dir):
            rel = src.relative_to(ROOT)
            dst = DST / rel
            if dst.exists() and filecmp.cmp(src, dst, shallow=False):
                same += 1
                continue
            if check_only:
                print("差异：%s" % rel)
                copied += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1

    for name in FILES:
        src = ROOT / name
        if not src.exists():
            continue
        dst = DST / name
        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            same += 1
            continue
        if check_only:
            print("差异：%s" % name)
            copied += 1
            continue
        shutil.copy2(src, dst)
        copied += 1

    verb = "待同步" if check_only else "已同步"
    print("%s %d 个文件，%d 个本来一致" % (verb, copied, same))
    if not check_only:
        total = sum(1 for p in DST.rglob("*") if p.is_file())
        print("开源/ 现有 %d 个文件" % total)
        print("提醒：data/ exports/ reports/ release/ build/ 永不进开源包")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
