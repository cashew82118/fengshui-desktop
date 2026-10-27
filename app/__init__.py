# -*- coding: utf-8 -*-
"""桌面风水分析器 · 应用包

分层铁律（见 docs/02-技术方案.md 第 5 节）：
    只有 desk_reader 允许直接调用 win32 API，其余模块必须是纯函数。
"""
