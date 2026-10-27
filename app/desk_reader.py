# -*- coding: utf-8 -*-
"""桌面图标读取模块（阶段一）

职责：把桌面图标的真实位置与名称读成结构化数据。
铁律：只读。不调用任何 SET/PUT 类消息，不移动、不重命名、不删除任何东西。

技术要点见 docs/02-技术方案.md 第 2 节：
    Progman -> SHELLDLL_DefView -> SysListView32，WorkerW 回退
    LVM_GETITEMPOSITION 取位置，LVM_GETITEMTEXTW 取名称
    跨进程：OpenProcess + VirtualAllocEx + ReadProcessMemory
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import unicodedata
from ctypes import wintypes as wt
from datetime import datetime
from pathlib import Path
import paths

# ---------------------------------------------------------------- 常量

LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_GETITEMTEXTW = LVM_FIRST + 115
LVIF_TEXT = 0x0001

PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

SMTO_BLOCK = 0x0001
SMTO_ABORTIFHUNG = 0x0002
SEND_TIMEOUT_MS = 1000

SPI_ICONHORIZONTALSPACING = 0x000D
SPI_ICONVERTICALSPACING = 0x000C

ERROR_ACCESS_DENIED = 5
ERROR_TIMEOUT = 1460

# 已知扩展名（用于"名称里自带扩展名"的判断）
KNOWN_EXTS = {
    ".lnk", ".exe", ".url", ".txt", ".md", ".doc", ".docx", ".pdf", ".xls",
    ".xlsx", ".csv", ".ppt", ".pptx", ".zip", ".rar", ".7z", ".mp4", ".mkv",
    ".avi", ".mov", ".mp3", ".flac", ".wav", ".jpg", ".jpeg", ".png", ".gif",
    ".psd", ".py", ".js", ".json", ".html", ".css", ".vbs", ".bat", ".ini",
}

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
user32.SendMessageTimeoutW.argtypes = [
    wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
    ctypes.POINTER(ctypes.c_size_t),
]
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowExW.restype = wt.HWND
user32.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
user32.SystemParametersInfoW.argtypes = [wt.UINT, wt.UINT, ctypes.c_void_p, wt.UINT]
user32.SystemParametersInfoW.restype = wt.BOOL

kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD,
]
kernel32.VirtualFreeEx.restype = wt.BOOL
kernel32.VirtualFreeEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
kernel32.ReadProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.CloseHandle.argtypes = [wt.HANDLE]


class LVITEMW(ctypes.Structure):
    """x64 下 sizeof == 88。字段顺序不能动。"""
    _fields_ = [
        ("mask", wt.UINT), ("iItem", ctypes.c_int), ("iSubItem", ctypes.c_int),
        ("state", wt.UINT), ("stateMask", wt.UINT),
        ("pszText", ctypes.c_void_p), ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int), ("lParam", ctypes.c_void_p),
        ("iIndent", ctypes.c_int), ("iGroupId", ctypes.c_int),
        ("cColumns", wt.UINT), ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p), ("iGroup", ctypes.c_int),
    ]


# ---------------------------------------------------------------- 基础工具

def enable_dpi_awareness() -> bool:
    """进程级声明 per-monitor v2，保证拿到的坐标是物理像素。

    必须在创建任何窗口之前调用。失败时退回旧 API，再失败就静默继续
    （坐标会被系统虚拟化，但分析用的是归一化比例，仍可用）。
    """
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == (HANDLE)-4
        ctx = ctypes.c_void_p(0xFFFFFFFFFFFFFFFC)
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = wt.BOOL
        if user32.SetProcessDpiAwarenessContext(ctx):
            return True
    except Exception:
        pass
    try:
        return bool(user32.SetProcessDPIAware())
    except Exception:
        return False


def _send(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
    """带超时的同步消息，避免 Explorer 繁忙时卡死。"""
    result = ctypes.c_size_t(0)
    ok = user32.SendMessageTimeoutW(
        hwnd, msg, wparam, lparam,
        SMTO_BLOCK | SMTO_ABORTIFHUNG, SEND_TIMEOUT_MS, ctypes.byref(result),
    )
    if not ok:
        err = ctypes.get_last_error()
        if err == ERROR_TIMEOUT:
            raise TimeoutError("桌面窗口无响应（超时 %dms）" % SEND_TIMEOUT_MS)
        raise OSError("发送消息失败，错误码 %d" % err)
    return result.value


def _sys_icon_spacing() -> tuple[int, int]:
    """系统设置里的图标间距，作为单元格尺寸的兜底估计。"""
    h = ctypes.c_int(0)
    v = ctypes.c_int(0)
    user32.SystemParametersInfoW(SPI_ICONHORIZONTALSPACING, 0, ctypes.byref(h), 0)
    user32.SystemParametersInfoW(SPI_ICONVERTICALSPACING, 0, ctypes.byref(v), 0)
    return (h.value or 75, v.value or 75)


# ---------------------------------------------------------------- 定位

def _find_listview() -> tuple[int, list[str]]:
    """返回 (SysListView32 句柄, 警告列表)。"""
    warnings: list[str] = []
    progman = user32.FindWindowW("Progman", None)
    defview = 0
    if progman:
        defview = user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None)

    if not defview:
        # Win11 部分版本把 DefView 挂到 WorkerW 下
        warnings.append("Progman 下未找到 SHELLDLL_DefView，已回退遍历 WorkerW")
        found: list[int] = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def _cb(hwnd, _lparam):
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, buf, 64)
            if buf.value == "WorkerW":
                dv = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
                if dv:
                    found.append(dv)
                    return False
            return True

        user32.EnumWindows(ctypes.cast(_cb, ctypes.c_void_p), 0)
        if found:
            defview = found[0]

    if not defview:
        return 0, warnings + ["未检测到标准 Windows 桌面（SHELLDLL_DefView）"]

    lv = user32.FindWindowExW(defview, 0, "SysListView32", None)
    if not lv:
        return 0, warnings + ["桌面下未找到图标列表控件（SysListView32）"]
    return lv, warnings


# ---------------------------------------------------------------- 名称 → 扩展名

# 索引条目 = (扩展名, 是否文件夹, 完整路径)
_Rec = tuple[str, bool, str]


def _build_name_index() -> tuple[dict[str, list[_Rec]], dict[str, list[_Rec]]]:
    """枚举桌面目录，建立 完整名→条目、词干→[条目] 两张索引。

    文件夹的扩展名强制为空：否则 `OK自动任务v1.1` 会被 `Path.suffix`
    当成 `.1` 扩展名的文件，阶段三归类会跟着错。
    """
    full: dict[str, list[_Rec]] = {}
    stem: dict[str, list[_Rec]] = {}
    dirs = []
    for env in ("USERPROFILE", "PUBLIC"):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / "Desktop")
    for d in dirs:
        try:
            if not d.is_dir():
                continue
            with os.scandir(d) as it:
                for entry in it:
                    p = Path(entry.name)
                    try:
                        is_dir = entry.is_dir()
                    except OSError:
                        is_dir = False
                    ext = "" if is_dir else p.suffix.lower()
                    rec: _Rec = (ext, is_dir, entry.path)
                    full.setdefault(entry.name.lower(), []).append(rec)
                    stem.setdefault(p.stem.lower(), []).append(rec)
        except OSError:
            continue
    return full, stem


def _resolve_kind(name: str, index: tuple[dict, dict]
                  ) -> tuple[str, bool, str | None, bool]:
    """解析图标名对应的文件信息。

    返回 (扩展名, 是否文件夹, 完整路径, 是否低置信)。
    扩展名为空且不是文件夹 → 系统虚拟项（此电脑/回收站等）。
    """
    full, stem = index
    low = name.strip().lower()
    if not low:
        return "", False, None, True

    if low in full:
        recs = full[low]
        ext, is_dir, path = recs[0]
        return ext, is_dir, path, len(recs) > 1

    suffix = Path(low).suffix
    if suffix in KNOWN_EXTS:
        # 名称已带扩展名（本机已开启"显示文件扩展名"）
        recs = stem.get(Path(low).stem.lower(), [])
        return suffix, False, (recs[0][2] if recs else None), False

    recs = stem.get(low, [])
    if recs:
        # 隐藏了扩展名的快捷方式会走到这里；同名词干优先取 .lnk
        lnk = [r for r in recs if r[0] == ".lnk"]
        rec = lnk[0] if lnk else recs[0]
        return rec[0], rec[1], rec[2], len(recs) > 1

    return "", False, None, False


# ---------------------------------------------------------------- 单元格尺寸

def _derive_cell(sizes: list[tuple[int, int]],
                 axis: int) -> tuple[int, bool]:
    """由坐标差推导单元格尺寸。返回 (尺寸, 是否为估算值)。"""
    values = sorted({p[axis] for p in sizes})
    deltas = [b - a for a, b in zip(values, values[1:]) if b - a > 0]
    if deltas:
        return min(deltas), False
    return 0, True


# ---------------------------------------------------------------- 主流程

def read_layout() -> tuple[dict, list[str]]:
    """读取桌面布局。

    返回 (layout, warnings)。layout 结构见 docs/02-技术方案.md 第 4 节。
    失败时抛 RuntimeError，由调用方决定如何提示。
    """
    enable_dpi_awareness()      # 幂等：已声明过则无效返回，不会报错
    warnings: list[str] = []
    lv, w = _find_listview()
    warnings.extend(w)
    if not lv:
        raise RuntimeError("；".join(warnings) or "未找到桌面图标列表")

    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(lv, ctypes.byref(pid))

    hproc = kernel32.OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
        False, pid.value,
    )
    if not hproc:
        err = ctypes.get_last_error()
        if err == ERROR_ACCESS_DENIED:
            raise RuntimeError(
                "无法读取 Explorer 进程（拒绝访问）。"
                "请勿以管理员身份运行本程序。"
            )
        raise RuntimeError("无法打开 Explorer 进程，错误码 %d" % err)

    remote = None
    try:
        remote = kernel32.VirtualAllocEx(
            hproc, None, 8192, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not remote:
            raise RuntimeError("远程内存分配失败，错误码 %d" % ctypes.get_last_error())

        count = _send(lv, LVM_GETITEMCOUNT, 0, 0)
        if count <= 0:
            warnings.append("桌面图标数为 0")

        rect = wt.RECT()
        user32.GetClientRect(lv, ctypes.byref(rect))
        canvas_w = rect.right - rect.left
        canvas_h = rect.bottom - rect.top
        if canvas_w <= 0 or canvas_h <= 0:
            raise RuntimeError("桌面列表控件尺寸异常：%dx%d" % (canvas_w, canvas_h))

        read = ctypes.c_size_t(0)
        text_offset = ctypes.sizeof(LVITEMW)
        buf = ctypes.create_unicode_buffer(260)
        raw: list[dict] = []

        for i in range(count):
            try:
                _send(lv, LVM_GETITEMPOSITION, i, remote)
            except (TimeoutError, OSError) as exc:
                warnings.append("第 %d 个图标位置读取失败：%s" % (i, exc))
                continue
            pt = (ctypes.c_long * 2)()
            kernel32.ReadProcessMemory(hproc, remote, ctypes.byref(pt), 8,
                                       ctypes.byref(read))
            x, y = pt[0], pt[1]

            item = LVITEMW()
            item.mask = LVIF_TEXT
            item.iItem = i
            item.iSubItem = 0
            item.pszText = ctypes.c_void_p(remote + text_offset)
            item.cchTextMax = 259
            kernel32.WriteProcessMemory(hproc, remote, ctypes.byref(item),
                                       ctypes.sizeof(item), ctypes.byref(read))
            ctypes.memset(buf, 0, ctypes.sizeof(buf))
            try:
                _send(lv, LVM_GETITEMTEXTW, i, remote)
            except (TimeoutError, OSError) as exc:
                warnings.append("第 %d 个图标名称读取失败：%s" % (i, exc))
                continue
            kernel32.ReadProcessMemory(hproc, remote + text_offset,
                                       ctypes.byref(buf), ctypes.sizeof(buf),
                                       ctypes.byref(read))
            raw.append({"index": i, "name": buf.value, "x": x, "y": y})
    finally:
        if remote:
            kernel32.VirtualFreeEx(hproc, remote, 0, MEM_RELEASE)
        kernel32.CloseHandle(hproc)

    # --- 单元格尺寸 ---
    coords = [(r["x"], r["y"]) for r in raw]
    cell_w, est_x = _derive_cell(coords, 0)
    cell_h, est_y = _derive_cell(coords, 1)
    sys_w, sys_h = _sys_icon_spacing()
    if est_x or not cell_w:
        cell_w = sys_w
    if est_y or not cell_h:
        cell_h = sys_h
    cell_estimated = est_x or est_y
    if cell_estimated:
        warnings.append("单元格尺寸由系统设置估算（%dx%d），仅影响绘制不影响分析"
                        % (cell_w, cell_h))

    # --- 扩展名与归一化坐标 ---
    index = _build_name_index()
    icons: list[dict] = []
    n_dir = n_virtual = 0
    out_of_range = 0
    for r in raw:
        ext, is_dir, path, low_conf = _resolve_kind(r["name"], index)
        if is_dir:
            kind = "dir"
            n_dir += 1
        elif ext or path:
            kind = "file"
        else:
            kind = "virtual"
            n_virtual += 1
        raw_cx = (r["x"] + cell_w / 2.0) / canvas_w
        raw_cy = (r["y"] + cell_h / 2.0) / canvas_h
        # DPI 未声明时，GetClientRect 会给虚拟化尺寸，而坐标是物理像素，
        # 相除后越界。这里必须抓出来，否则宫位会静默算错。
        if raw_cx > 1.002 or raw_cy > 1.002 or raw_cx < -0.002 or raw_cy < -0.002:
            out_of_range += 1
        cx = min(1.0, max(0.0, raw_cx))
        cy = min(1.0, max(0.0, raw_cy))
        col = min(2, max(0, int(cx * 3)))
        row = min(2, max(0, int(cy * 3)))
        icons.append({
            "index": r["index"], "name": r["name"], "kind": kind,
            "ext": ext, "path": path,
            "x": r["x"], "y": r["y"],
            "cx": round(cx, 6), "cy": round(cy, 6),
            "row": row, "col": col,
            "low_confidence": low_conf,
        })

    if n_virtual:
        warnings.append("%d 个系统虚拟项（无对应文件）：%s" % (
            n_virtual,
            "、".join(it["name"] for it in icons if it["kind"] == "virtual")))

    if out_of_range:
        warnings.append(
            "有 %d 个图标坐标超出画布，宫位判断可能不准："
            "多半是本进程未声明 DPI 感知（缩放非 100% 时会发生）"
            % out_of_range)

    layout = {
        "canvas": [canvas_w, canvas_h],
        "cell": [cell_w, cell_h],
        "cell_estimated": cell_estimated,
        "read_at": datetime.now().isoformat(timespec="seconds"),
        "explorer_pid": pid.value,
        "icons": icons,
        "warnings": warnings,
    }
    return layout, warnings


# ---------------------------------------------------------------- 调试入口

def _w(s: str) -> int:
    """按东亚字符宽度算显示宽度。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _w(s))


# 仅供调试打印：固定坐北朝南的宫位标签（可旋转版本在 fengshui.py，阶段三实现）
_PALACE_LABEL = [
    ["巽", "离", "坤"],
    ["震", "中", "兑"],
    ["艮", "坎", "乾"],
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    enable_dpi_awareness()

    try:
        layout, warnings = read_layout()
    except RuntimeError as exc:
        print("[失败] %s" % exc)
        return 1

    icons = layout["icons"]
    print("[成功] 读到 %d 个桌面图标" % len(icons))
    print("  画布尺寸: %d x %d px" % tuple(layout["canvas"]))
    print("  单元格  : %d x %d px%s" % (
        layout["cell"][0], layout["cell"][1],
        "（估算）" if layout["cell_estimated"] else "（由坐标差推导）"))
    print("  Explorer PID: %d" % layout["explorer_pid"])

    n_file = sum(1 for it in icons if it["kind"] == "file")
    n_dir = sum(1 for it in icons if it["kind"] == "dir")
    n_virtual = sum(1 for it in icons if it["kind"] == "virtual")
    print("  构成    : 文件 %d ／ 文件夹 %d ／ 系统虚拟项 %d"
          % (n_file, n_dir, n_virtual))

    if warnings:
        print("\n[提示]")
        for w in warnings:
            print("  · %s" % w)

    _KIND_LABEL = {"file": "文", "dir": "夹", "virtual": "虚"}
    print("\n" + "-" * 92)
    print("%s %s %s %s %s %s" % (
        _pad("#", 4), _pad("宫", 4), _pad("类", 4), _pad("扩展名", 10),
        _pad("坐标", 14), _pad("置信", 6) + "名称"))
    print("-" * 92)
    for it in icons:
        palace = _PALACE_LABEL[it["row"]][it["col"]]
        print("%s %s %s %s %s %s" % (
            _pad(str(it["index"]), 4),
            _pad(palace, 4),
            _pad(_KIND_LABEL[it["kind"]], 4),
            _pad(it["ext"] or "—", 10),
            _pad("(%d,%d)" % (it["x"], it["y"]), 14),
            _pad("低" if it["low_confidence"] else "高", 6) + it["name"],
        ))
    print("-" * 92)

    # 九宫计数
    grid = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    for it in icons:
        grid[it["row"]][it["col"]] += 1
    print("\n九宫分布（坐北朝南）:")
    for r in range(3):
        print("  " + "  ".join("%s:%2d" % (_PALACE_LABEL[r][c], grid[r][c])
                               for c in range(3)))

    out = paths.DATA / "layout_debug.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(layout, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("\n已写出: %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
