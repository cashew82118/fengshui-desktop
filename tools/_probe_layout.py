# -*- coding: utf-8 -*-
"""
探针：验证能否只读地拿到桌面图标的真实坐标与名称。
无界面、不弹窗、不联网、不修改任何东西。
"""
import ctypes
import sys
from ctypes import wintypes as wt

# ---------- DPI 感知（保证坐标是物理像素） ----------
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowExW.restype = wt.HWND
user32.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_GETITEMSPACING = LVM_FIRST + 51
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


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wt.UINT), ("iItem", ctypes.c_int), ("iSubItem", ctypes.c_int),
        ("state", wt.UINT), ("stateMask", wt.UINT),
        ("pszText", ctypes.c_void_p), ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int), ("lParam", ctypes.c_void_p),
        ("iIndent", ctypes.c_int), ("iGroupId", ctypes.c_int),
        ("cColumns", wt.UINT), ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p), ("iGroup", ctypes.c_int),
    ]


def find_desktop_listview():
    """定位桌面图标所在的 SysListView32"""
    progman = user32.FindWindowW("Progman", None)
    defview = 0
    if progman:
        defview = user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None)
    if not defview:
        found = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def enum_cb(hwnd, lparam):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value == "WorkerW":
                dv = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
                if dv:
                    found.append(dv)
                    return False
            return True

        user32.EnumWindows(enum_cb, 0)
        if found:
            defview = found[0]
    if not defview:
        return 0
    return user32.FindWindowExW(defview, 0, "SysListView32", None)


def read_layout():
    lv = find_desktop_listview()
    if not lv:
        return None, "找不到桌面图标列表（可能不是标准 Explorer 桌面）"

    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(lv, ctypes.byref(pid))

    hproc = kernel32.OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
        False, pid.value)
    if not hproc:
        return None, "打开 Explorer 进程失败（错误码 %d）" % ctypes.get_last_error()

    remote = kernel32.VirtualAllocEx(hproc, None, 8192, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not remote:
        return None, "远程内存分配失败（错误码 %d）" % ctypes.get_last_error()

    n = user32.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)
    read = ctypes.c_size_t(0)

    # 网格间距
    pt = (ctypes.c_long * 2)()
    user32.SendMessageW(lv, LVM_GETITEMSPACING, 0, remote)
    kernel32.ReadProcessMemory(hproc, remote, ctypes.byref(pt), 8, ctypes.byref(read))
    spacing_x, spacing_y = pt[0], pt[1]

    rect = wt.RECT()
    user32.GetClientRect(lv, ctypes.byref(rect))
    list_w, list_h = rect.right - rect.left, rect.bottom - rect.top

    items = []
    text_offset = ctypes.sizeof(LVITEMW)
    buf = ctypes.create_unicode_buffer(260)

    for i in range(n):
        # --- 位置 ---
        if not user32.SendMessageW(lv, LVM_GETITEMPOSITION, i, remote):
            continue
        p = (ctypes.c_long * 2)()
        kernel32.ReadProcessMemory(hproc, remote, ctypes.byref(p), 8, ctypes.byref(read))
        x, y = p[0], p[1]

        # --- 名称 ---
        item = LVITEMW()
        item.mask = LVIF_TEXT
        item.iItem = i
        item.iSubItem = 0
        item.pszText = ctypes.c_void_p(remote + text_offset)
        item.cchTextMax = 259
        kernel32.WriteProcessMemory(hproc, remote, ctypes.byref(item),
                                    ctypes.sizeof(item), ctypes.byref(read))
        ctypes.memset(buf, 0, ctypes.sizeof(buf))
        user32.SendMessageW(lv, LVM_GETITEMTEXTW, i, remote)
        kernel32.ReadProcessMemory(hproc, remote + text_offset, ctypes.byref(buf),
                                   ctypes.sizeof(buf), ctypes.byref(read))
        items.append({"index": i, "name": buf.value, "x": x, "y": y})

    kernel32.VirtualFreeEx(hproc, remote, 0, MEM_RELEASE)
    kernel32.CloseHandle(hproc)

    meta = {"count": n, "spacing": (spacing_x, spacing_y),
            "canvas": (list_w, list_h), "pid": pid.value}
    return (items, meta), None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result, err = read_layout()
    if err:
        print("[失败]", err)
        sys.exit(1)
    items, meta = result
    print("[成功] 读到 %d 个桌面图标" % meta["count"])
    print("  网格间距: %d x %d px" % meta["spacing"])
    print("  工作区尺寸: %d x %d px" % meta["canvas"])
    print("  Explorer PID: %d" % meta["pid"])
    print("  LVITEMW 结构大小: %d bytes" % ctypes.sizeof(LVITEMW))
    print("-" * 60)
    for it in items:
        print("  %2d  (%5d,%5d)  %s" % (it["index"], it["x"], it["y"], it["name"]))
    print("-" * 60)
    xs = [it["x"] for it in items]
    ys = [it["y"] for it in items]
    if items:
        print("  横向范围: %d ~ %d   纵向范围: %d ~ %d" % (min(xs), max(xs), min(ys), max(ys)))
        # 是否严格落在网格上（判断有没有开自动排列）
        sx, sy = meta["spacing"]
        if sx and sy:
            on_grid = sum(1 for it in items if it["x"] % sx == 0 and it["y"] % sy == 0)
            print("  严格落在网格上的图标: %d / %d" % (on_grid, len(items)))
