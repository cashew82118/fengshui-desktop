# -*- coding: utf-8 -*-
"""运行时路径：源码运行与打包 exe 都指向同一处。

打包成 onefile 后 `__file__` 落在临时解压目录（_MEIPASS 或 _internal），
如果还按 `__file__.parent.parent` 算，data/ 与 exports/ 会写进临时目录，
程序一关全没了。所以这里统一以「exe 所在目录」为基准。

源码运行时仍以项目根为基准，行为不变。
"""
from __future__ import annotations

import sys
from pathlib import Path


def _base() -> Path:
    if getattr(sys, "frozen", False):
        # 打包后：exe 所在目录（onefile 的临时目录不算）
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE = _base()
DATA = BASE / "data"
SNAPSHOTS = DATA / "snapshots"
EXPORTS = BASE / "exports"
REPORTS = BASE / "reports"

FROZEN = bool(getattr(sys, "frozen", False))


def ensure() -> None:
    """首次运行把目录建好（exe 旁边一开始不会有这些空目录）。"""
    for d in (DATA, SNAPSHOTS, EXPORTS, REPORTS):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            # 只读目录（如放在 Program Files）不该让程序起不来
            pass
