# -*- coding: utf-8 -*-
"""五行归类引擎（阶段三）

判定优先级（自上而下，命中即停）：
    0. 用户覆盖层   ← 阶段九。显式指定的归属压过一切内置规则（含白名单）
    1. 系统项白名单
    2. 安装包判定  ← 必须在语义之前：1.5GB 的 android-studio 安装包
                       不能因为名字里有 "studio" 就被当成文思之木
    3. 语义词典（按名称关键词）
    4. 扩展名基础表
    5. 兜底 → 金
颜色只影响"强度系数"，永不改变五行归属。
"""
from __future__ import annotations

import rules
import software

WUXING_ORDER = ["木", "火", "土", "金", "水"]

# 相生：木→火→土→金→水→木
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
# 相克：木克土、土克水、水克火、火克金、金克木
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# ---------------------------------------------------------------- 1. 白名单

# 名称 → (五行, 说明)
WHITELIST = {
    "此电脑": ("金", "系统器物"),
    "网络": ("金", "系统器物"),
    "控制面板": ("金", "系统器物"),
    "回收站": ("土", "承载纳垢，聚秽之所"),
}

# ---------------------------------------------------------------- 2. 安装包

_INSTALLER_HINTS = (
    "setup", "installer", "install", "whql", "dch", ".msi",
    "desktop-win", "-x64", "_x64", "amd64", "win10", "win11",
)


def is_installer(name: str, ext: str) -> bool:
    if ext not in (".exe", ".msi"):
        return False
    n = name.lower()
    if any(h in n for h in _INSTALLER_HINTS):
        return True
    # android-studio-quail3-windows.exe 这类："-windows.exe" 结尾
    return n.endswith("-windows.exe") or n.endswith("windows.exe")


# ---------------------------------------------------------------- 3. 语义词典

# (关键词元组, 五行, 理由) —— 顺序有意义，先命中者生效
SEMANTIC = [
    (("加速", "vpn", "代理", "clash", "frp", "梯子", "机场"), "水", "通关流动"),
    (("云盘", "网盘", "坚果云", "同步", "下载", "磁力", "种子"), "水", "流动聚散"),
    (("浏览器", "chrome", "edge", "firefox"), "水", "通达"),
    (("语音", "会议", "聊天", "微信"), "水", "沟通往来"),
    (("游戏", "影音", "播放器", "剪辑", "剪映", "resolve", "potplayer",
      "爆米花", "抖音", "快手", "哔哩", "b站", "爱奇艺", "优酷", "steam",
      "三角洲", "无畏契约", "原神", "永劫", "英雄联盟", "cs2", "apex",
      "valorant", "epic", "battle.net"),
     "火", "显象耗神"),
    (("笔记", "文档", "稿", "代码", "code", "studio"), "木", "文思生长"),
    (("驱动", "管理器", "控制", "工具", "助手", "键盘", "格式",
      "定时", "关机", "清理", "卸载"), "金", "器物决断"),
]

# ---------------------------------------------------------------- 4. 扩展名表

EXT_WUXING = {
    ".doc": "木", ".docx": "木", ".txt": "木", ".md": "木", ".pdf": "木",
    ".xls": "木", ".xlsx": "木", ".csv": "木", ".ppt": "木", ".pptx": "木",
    ".py": "木", ".js": "木", ".json": "木", ".html": "木", ".css": "木",
    ".mp4": "火", ".mkv": "火", ".avi": "火", ".mov": "火", ".mp3": "火",
    ".flac": "火", ".wav": "火", ".jpg": "火", ".jpeg": "火", ".png": "火",
    ".gif": "火", ".psd": "火",
    ".zip": "土", ".rar": "土", ".7z": "土",
    ".lnk": "金", ".exe": "金", ".vbs": "金", ".bat": "金",
    ".url": "水",
}

SOURCE_LABEL = {
    "user": "自定义添加",
    "system": "系统项白名单",
    "installer": "安装包判定",
    "software": "软件名录",
    "semantic": "语义词典",
    "ext": "扩展名",
    "dir": "文件夹承载",
    "virtual": "系统虚拟项",
    "fallback": "兜底",
}

# ---------------------------------------------------------------- 类别谓词
# 「优先文昌」「优先财库」两档推演用：某图标属不属于这一类。
# 口径：语义词典的理由 > 扩展名/名称关键词 > 五行来源（木＝文思、金＝器物）。

DOC_EXT = {".doc", ".docx", ".txt", ".md", ".pdf", ".xls", ".xlsx",
           ".csv", ".ppt", ".pptx", ".rtf", ".epub", ".py", ".js",
           ".json", ".html", ".css"}
DOC_WORDS = ("笔记", "文档", "稿", "代码", "code", "studio", "word",
             "excel", "powerpoint", "课本", "教材", "论文", "写作",
             "阅读", "词典", "课程", "学习", "anki", "obsidian",
             "notion", "typora", "onenote", "evernote", "印象笔记",
             "记事本", "便签", "书")
TOOL_WORDS = ("工具", "管理", "控制", "驱动", "助手", "设置", "清理",
              "卸载", "压缩", "解压", "杀毒", "安全", "监控", "管家",
              "分区", "备份", "命令", "终端", "控制台", "任务",
              "注册表", "服务", "driver", "manager", "control", "tool",
              "clean", "uninstall", "backup", "cmd", "terminal",
              "console")


def is_doc(icon: dict) -> bool:
    """文书／笔记／学习类。「优先文昌」搬的就是这些。"""
    wx, src, why = classify(icon)
    if why == "文思生长":
        return True
    name = (icon.get("name") or "").lower()
    ext = (icon.get("ext") or "").lower()
    if ext in DOC_EXT or any(w in name for w in DOC_WORDS):
        return True
    return wx == "木" and src in ("software", "semantic", "ext")


def is_tool(icon: dict) -> bool:
    """工具／管理／生产力类。「优先财库」搬的就是这些。"""
    wx, src, why = classify(icon)
    if why == "器物决断":
        return True
    name = (icon.get("name") or "").lower()
    return (any(w in name for w in TOOL_WORDS)
            or (wx == "金" and src in ("software", "semantic", "ext")))


# ---------------------------------------------------------------- 主判定


def classify(icon: dict) -> tuple[str, str, str]:
    """返回 (五行, 来源键, 说明)。绝不抛异常。"""
    name = icon.get("name", "") or ""
    ext = (icon.get("ext") or "").lower()
    kind = icon.get("kind", "file")
    low = name.strip().lower()

    # 0. 用户覆盖层（阶段九）：显式指定压过一切内置规则，命中即停
    hit = rules.match(name, ext)
    if hit:
        return hit[0], "user", hit[1]

    # 1. 白名单
    hit = WHITELIST.get(name.strip())
    if hit:
        return hit[0], "system", hit[1]

    # 2. 安装包
    if is_installer(name, ext):
        return "土", "installer", "安装包，器未成形，积而未化"

    # 3. 文件夹（承载之器，不论里面装什么）
    if kind == "dir":
        return "土", "dir", "文件夹，承载堆积"

    # 4. 软件名录（精确到具体软件，优先于泛语义）
    hit = software.lookup(name)
    if hit:
        return hit[0], "software", "名录命中「%s」" % hit[1]

    # 5. 语义词典
    for words, wx, why in SEMANTIC:
        for w in words:
            if w in low:
                return wx, "semantic", why

    # 6. 扩展名
    if ext in EXT_WUXING:
        return EXT_WUXING[ext], "ext", "按扩展名归类"

    # 7. 兜底
    if kind == "virtual":
        return "金", "virtual", "未具名的系统项"
    return "金", "fallback", "未能判断，归金"


def apply_wuxing(layout: dict) -> dict:
    """就地给每个图标补上五行字段，并返回五行分布。"""
    dist = {w: 0 for w in WUXING_ORDER}
    for it in layout["icons"]:
        wx, src, why = classify(it)
        it["wuxing"] = wx
        it["wuxing_source"] = src
        it["wuxing_note"] = why
        it.setdefault("intensity", 1.0)
        dist[wx] += 1
    return dist


# ---------------------------------------------------------------- 杂物判定

CLUTTER_HINTS = ("新建", "副本", "未命名", "无标题", "copy")

# 单件杂物的分值（取最大者，不累加）
CLUTTER_WEIGHT = {
    "installer": 3,   # 安装包积于盘上
    "nameless": 3,    # 无主之物（临时命名）
    "longname": 2,    # 名目冗长
    "dup": 1,         # 重复命名的快捷方式
}
CLUTTER_CAP = 10      # 杂物项最多扣 10 分。原为 12/20 分；2026-10-27 六项压到
                      # 80 分后按 60% 折算（16 × 0.6 ≈ 9.6，取整 10）。


def clutter_items(icons: list[dict]) -> list[dict]:
    """返回杂物清单。

    同一件杂物若有多个理由，**只取最高分**，不累加——
    否则一件 1.5GB 安装包会同时吃"安装包"和"超长名"两份扣分。
    """
    out = []
    for it in icons:
        name = it.get("name", "")
        low = name.lower()
        hits: list[tuple[int, str]] = []

        if any(h in low for h in CLUTTER_HINTS):
            hits.append((CLUTTER_WEIGHT["nameless"], "无主之物，临时命名"))
        if is_installer(name, (it.get("ext") or "").lower()):
            hits.append((CLUTTER_WEIGHT["installer"], "安装包积于盘上"))
        if len(name) > 30:
            hits.append((CLUTTER_WEIGHT["longname"], "名目冗长，形同堆叠"))
        if low.endswith(" - 快捷方式"):
            hits.append((CLUTTER_WEIGHT["dup"], "重复命名的快捷方式"))

        if hits:
            hits.sort(key=lambda x: -x[0])
            out.append({"name": name, "weight": hits[0][0],
                        "reason": "、".join(h[1] for h in hits), "icon": it})
    return out


def clutter_kind(clutter: list[dict]) -> str:
    """判断杂物主导类型，供文案选句。返回 installer/nameless/longname/dup/mixed。"""
    tally = {"installer": 0, "nameless": 0, "longname": 0, "dup": 0}
    for c in clutter:
        r = c.get("reason", "")
        if "安装包" in r:
            tally["installer"] += 1
        if "无主" in r:
            tally["nameless"] += 1
        if "名目冗长" in r:
            tally["longname"] += 1
        if "重复命名" in r:
            tally["dup"] += 1
    top = max(tally, key=lambda k: tally[k])
    if tally[top] == 0:
        return "mixed"
    return top if tally[top] >= max(1, len(clutter) * 0.6) else "mixed"
