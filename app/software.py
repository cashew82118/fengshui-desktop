# -*- coding: utf-8 -*-
"""常用软件五行名录（阶段三·追加）

判定原则（按"这个软件让你做什么"分类）：
    木：写、算、记、码、建模工程 —— 文思生发
    火：看、听、玩、剪、修图、渲染 —— 显象耗神
    土：压缩、文件管理、镜像、备份 —— 承载堆积
    金：系统、安全、驱动、硬件、远控、输入法 —— 器物决断
    水：浏览器、网盘、通讯、下载、加速、邮件 —— 流动通达

匹配规则（三级，防假阳性）：
    1. 全 ASCII 关键词 → 必须**词边界**命中（含驼峰边界），
       否则 "edge" 会命中 "knowledge"、"ea" 会命中 "idea"。
    2. 含中文关键词 → 直接子串命中（中文名足够独特）。
    3. 一律大小写不敏感。
"""
from __future__ import annotations

# fmt: off
SOFTWARE: dict[str, list[str]] = {
    # ---------------- 木：文字、代码、表格、知识、工程建模 ----------------
    "木": [
        "wps", "office", "word", "excel", "powerpoint", "visio", "onenote",
        "access", "金山文档", "腾讯文档", "石墨", "语雀", "幕布", "飞书文档",
        "impress", "writer", "libreoffice", "openoffice",
        "印象笔记", "为知笔记", "有道云笔记", "notion", "obsidian", "typora",
        "marktext", "logseq", "joplin", "trilium", "思源笔记", "专注笔记",
        "xmind", "mindmaster", "processon", "mindmanager", "亿图", "draw.io",
        "vscode", "visual studio", "jetbrains", "intellij", "idea", "pycharm",
        "webstorm", "clion", "goland", "rider", "datagrip", "android studio",
        "eclipse", "sublime", "atom", "vim", "neovim", "emacs", "notepad++",
        "notepad", "ultraedit", "editor", "nano", "brackets", "codepen",
        "git", "github", "gitlab", "gitee", "sourcetree", "fork", "tortoisegit",
        "jupyter", "anaconda", "miniconda", "spyder", "rstudio", "matlab",
        "mathematica", "maple", "spss", "stata", "sas", "eviews", "lingo",
        "latex", "texlive", "miktex", "overleaf", "texstudio",
        "cajviewer", "知网", "zotero", "endnote", "mendeley", "calibre",
        "autocad", "cad", "solidworks", "catia", "ug", "creo", "revit",
        "sketchup", "rhino", "ansys", "comsol", "abaqus", "keil", "quartus",
        "arduino", "proteus", "multisim", "labview", "altium", "嘉立创",
        "postman", "apifox", "navicat", "dbeaver", "redis", "mysql",
        "xshell", "putty", "mobaxterm", "winscp", "filezilla",
        "acrobat", "pdf", "workbuddy", "cc switch", "cursor", "trae",
        # —— 追补（2026-10-24）：开发链路 / AI 对话 / 学习 / EDA / 数据库
        "node", "npm", "yarn", "pnpm", "webpack", "vite", "babel", "eslint",
        "svn", "jenkins", "docker",
        "kubernetes", "kubectl", "insomnia", "charles", "fiddler",
        "wireshark", "httpcanary", "gradle", "maven", "cmake", "make",
        "gcc", "gdb", "llvm", "clang", "javac", 
        
        "devc", "devcpp", "codeblocks", "qt creator",
        "chatgpt", "claude", "gemini", "copilot", "deepseek", "kimi",
        "通义千问", "通义", "豆包", "文心一言", "文心", "讯飞星火", "星火",
        "智谱", "月之暗面", "openai api", "ollama", "lm studio",
        "anki", "quizlet", "quarto", "vscodium", "texmaker", "zettlr",
        "onlyoffice", "有道词典",
        "超星", "学习通", "雨课堂", "中国大学mooc", "慕课",
        "caj", 
        "geogebra", "simpputer",
        "vivado", "modelsim", "iar", "cubemx",
        "altium designer", "kicad", 
        "ug nx", "nx", "inventor",
        "天正", "广联达",
        "foxit", "福昕", "sumatrapdf", "pdf24", "pdfgear", "pdffactory",
        "postgresql", "postgres", "mongodb", "sqlite",
        "sqlserver", "oracle", "达梦",
    ],
    # ---------------- 火：视觉、音视频、游戏、娱乐 ----------------
    "火": [
        "photoshop", "illustrator", "indesign", "lightroom", "premiere",
        "after effects", "audition", "davinci",
        "resolve", "剪映", "capcut", "vegas", "会声会影", "绘声绘影",
        "blender", "3dsmax", "maya", "cinema4d", "zbrush", "substance",
        "figma", "sketch", "adobe xd", "axure", "墨刀", "canva", "稿定",
        "创客贴", "美图秀秀", "光影魔术手", "darktable", "pureref",
        "potplayer", "vlc", "mpv", "kmplayer", "暴风影音", "qq影音",
        "迅雷影音", "mpc-hc", "foobar2000", "aimp",
        "网易云音乐", "qq音乐", "酷狗", "酷我", "spotify", "itunes",
        "千千静听", "喜马拉雅", "咪咕音乐",
        "爱奇艺", "优酷", "腾讯视频", "芒果tv", "bilibili", "哔哩哔哩",
        "抖音", "快手", "微博视频", "youtube", "netflix",
        "musicbee", "winamp",
        "steam", "epic", "暴雪", "battle.net", "wegame", "uplay", "ubisoft",
        "origin", "ea", "gog", "itch", "网易游戏", "米哈游", "playnite",
        "三角洲", "无畏契约", "原神", "崩坏", "永劫", "英雄联盟",
        "cs2", "apex", "valorant", "dota", "minecraft",
        "我的世界", "泰拉瑞亚", "星露谷",         "黑神话", "只狼", "艾尔登",
        "魔兽争霸", "红色警戒", "帝国时代", "植物大战僵尸",
        "赛博朋克", "gta", "荒野大镖客", "死亡搁浅", "巫师", "上古卷轴",
        "辐射", "战地", "使命召唤", "彩虹六号", "守望先锋", "炉石",
        "云顶", "穿越火线", "地下城", "梦幻西游", "剑网",
        "天涯明月刀", "逆水寒", "剑灵", "永劫无间", "幻兽帕鲁", "双人成行",
        "losslesscut", "dlss",
        # —— 追补（2026-10-24）：渲染 / 音频 DAW / 录屏直播 / 游戏 / AI 绘画
        "vray", "keyshot", "octane", "redshift", "arnold", "corona",
        "lumion", "twinmotion", "enscape", "d5 render", 
        "3ds max", "cinema 4d", "c4d", "houdini",
        "substance painter", "marvelous designer",
        "unity hub", "unreal editor", "unreal", "UE", "godot",
        "premiere pro", "davinci resolve",
        "vegas pro", "edius", "final cut", "剪映专业版", 
        "cubase", "nuendo", "flstudio", "fl studio", "ableton", "live",
        "studio one", "presonus", "reaper", "pro tools", "logic pro",
        "audacity", "录音", "混音",
        "obs studio", "bandicam", "action", "mirillis", "xsplit",
        "streamlabs", "vmix", "斗鱼直播", "斗鱼", "虎牙直播", "虎牙",
        "哔哩哔哩直播姬", "直播姬", "抖音直播伴侣", "直播伴侣",
        "steam client", "ea app", "ubisoft connect",
        "epic games", "战网", "xbox",
        "rust", "瓦罗兰特", "csgo", 
        "dota 2", "lol客户端", "dnf",
        "魔兽世界", "崩坏：星穹铁道", "星穹铁道", "崩坏3",
        "terraria",
        "midjourney", "stable diffusion", "comfyui",
        "webui", "novelai", "runway", "pika", "可灵", "即梦", "海螺",
        "通义万相", "文心一格", "豆包·剪映",
    ],
    # ---------------- 土：压缩、文件管理、镜像、备份 ----------------
    "土": [
        "7-zip", "7zip", "winrar", "bandizip", "好压", "快压", "2345好压",
        "winzip", "peazip", "360压缩", "快压压缩", "nanazip",
        "everything", "listary", "total commander", "火柴", "utools",
        "quicklook", "fences", "腾讯桌面整理", "桌面整理", "deskgo",
        "diskgenius", "分区助手", "傲梅", "ghost", "微pe", "大白菜",
        "老毛桃", "优启通", "rufus", "ultraiso", "软碟通", "ventoy",
        "balenaetcher", "win32diskimager",
        "驱动精灵", "驱动人生", "360驱动", "snappy driver",
        # —— 追补（2026-10-24）：虚拟机 / 磁盘备份 / 文件管理 / 镜像刻录 / 包管理
        "vmware", "virtualbox", "hyperv", "hyper-v", "parallels",
        "qemu", "genymotion", "mumu", "mumuvemu", "雷电模拟器", "夜神模拟器",
        "逍遥模拟器", "蓝叠", "bluestacks", "安卓模拟器",
        "acronis", "true image", "hasleo", "easyuefi", 
        "freefilesync", "goodsync", "second copy", "同步盘",
        "aomei", "miniTool",
        "directory opus", "directoryopus", "qdir", "clover", "xyplorer",
        "totalcommander", "tc", "onecommander",
        "files app", "multrin", "酷呆桌面", "coodesker",
        "poweriso", "imgburn", "daemon tools",
        "etcher", "wepe",
        "scoop", "chocolatey", "winget", "homebrew",
        "沙盘", "sandboxie", "影子系统", "shadow defender",
        "onedrive", "坚果云", "nextcloud", "syncthing", "resilio",
    ],
    # ---------------- 金：系统、安全、驱动、硬件、远控、输入法 ----------------
    "金": [
        "火绒", "360安全卫士", "360杀毒", "腾讯电脑管家", "金山毒霸",
        "迈克菲", "mcafee", "卡巴斯基", "kaspersky", "nod32", "eset",
        "avast", "avira", "bitdefender", "malwarebytes", "火绒安全",
        "ccleaner", "软媒魔方", "geek uninstaller", "revo uninstaller",
        "iobit", "advanced systemcare", "driver booster", "wise care",
        "aida64", "cpu-z", "gpu-z", "crystaldiskinfo", "crystaldiskmark",
        "as ssd", "hwinfo", "hwmonitor", "msi afterburner", "鲁大师",
        "图吧工具箱", "furmark", "3dmark", "cinebench",
        "向日葵", "todesk", "anydesk", "teamviewer", "rustdesk", "parsec",
        "远程桌面", "vnc", "mstsc",
        "搜狗输入法", "qq输入法", "百度输入法", "微软拼音", "讯飞输入法",
        "微信输入法", "小狼毫", "rime", "手心输入法",
        "autohotkey", "按键精灵", "鼠标连点", "quicker",
        "nvidia", "geforce", "amd", "radeon", "intel", "realtek",
        "声卡驱动", "网卡驱动", "显卡驱动", "键盘驱动", "罗技", "logitech",
        "razer", "雷蛇", "雷柏", "rapoo", "凌豹", "樱桃", "cherry",
        "双飞燕", "达尔优", "黑爵", "狼蛛", "牧马人",
        "格式工厂", "handbrake", "ffmpeg", "小丸工具箱", "mediainfo",
        "定时关机", "一键关屏", "任务计划", "ncmdump",
        # —— 追补（2026-10-24）：系统工具 / 硬件检测 / RGB 外设 / 桌面改造
        "procexp", "procmon", "autoruns", "process lasso", "dism++",
        "dism", "sfc", "msconfig", "regedit", "registry finder",
        "wox", 
        
        "hdtune", "hdtune pro", "victoria", 
        "occt", "prime95",
        "aida", "ryzen master",
        "ryzenmaster", "xtu", 
        "afterburner", "memtest", "linpack",
        "openrgb", "signalrgb", "corsair icue", "icue", "razer synapse",
        "synapse", "logitech g hub", "ghub", "armoury crate",
        "armoury", "dragon center", "灯效",
        "startallback", "startisback", "windhawk", "eartrumpet",
        "powertoys", "translucenttb", "nilesoft", "shell", "7+ taskbar",
        "tweaker", "optimizer", "privacy", 
        "bulk rename", "rename", "everything64",
    ],
    # ---------------- 水：浏览器、网盘、通讯、下载、加速、邮件 ----------------
    "水": [
        "chrome", "edge", "firefox", "opera", "brave", "vivaldi", "safari",
        "360浏览器", "qq浏览器", "搜狗浏览器", "uc浏览器",
        "傲游浏览器", "maxthon",
        "2345浏览器", "猎豹浏览器", "世界之窗",
        "pale moon", "seamonkey", "slimjet", "midori",
        "百度网盘", "阿里云盘", "夸克网盘", "115", "天翼云盘", "微云",
        "pikpak",
        "dropbox", "google drive", "mega", "亿方云",
        "seafile", "icloud",
        "迅雷", "idm", "motrix", "aria2", "qbittorrent", "utorrent",
        "比特彗星", "bitcomet", "电驴", "emule", "free download manager",
        "微信", "wechat", "qq", "tim", "钉钉", "飞书", "企业微信",
        "腾讯会议", "zoom", "teams", "skype", "telegram", "discord",
        "slack", "whatsapp", "line", "signal", "element",
        "知乎", "豆瓣", "贴吧", "微博", "twitter", "facebook", "instagram",
        "邮箱", "foxmail", "thunderbird", "outlook", "gmail", "网易邮箱",
        "qq邮箱", "mail", "网易邮箱大师", "em client", "mailbird",
        "clash", "v2ray", "shadowsocks", "加速器", "uu加速器", "雷神",
        "迅游", "奇游", "网易uu", "小黑盒加速器", "sakurafrp", "frp",
        "花生壳", "蒲公英", "tailscale", "zerotier", "wireguard", "openvpn",
        "黑盒语音", "小黑盒", "steam++", "watt toolkit", "sunshine",
        "localsend", "磁力",
        # —— 追补（2026-10-24）：浏览器分支 / 组网 / 中转网盘 / 电商出行 / 资讯
        "librewolf", "waterfox", "thorium", "torbrowser", "tor browser",
        "arc browser", "sigmaos",
        "ucbrowser", "华为浏览器",
        "clash verge", "clashverge", "clash for windows", "nekoray",
        "nekobox", "mihomo", "v2rayn", "netch", "sstap",
        "easyconnect", "aTrust", "深信服", 
        "frpc", "nps", 
        "terabox", "百度网盘企业版", "文叔叔", "奶牛快传", "空中传", "_send_",
        "abdm", "imFile", "file centipede", "filecxx",
        "淘宝", "京东", "苏宁易购", "唯品会",
        "携程", "去哪儿", "飞猪", "12306", "铁路12306",
        "rclone", "gopeed", "fluent reader", "rssguard",
        "今日头条", "澎湃新闻", "网易新闻", "腾讯新闻", "新浪新闻",
        "jdownloader", "protonvpn", "得到",
        "steamtools", 
    ],
}
# fmt: on

TOTAL = sum(len(v) for v in SOFTWARE.values())


def _is_word_char(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch == "_")


def _ascii_word_hit(kw: str, name: str) -> bool:
    """词边界匹配，含驼峰边界（CodeBuddy 命中 code）。"""
    low = name.lower()
    start = 0
    while True:
        i = low.find(kw, start)
        if i < 0:
            return False
        before_ok = i == 0 or not _is_word_char(low[i - 1])
        j = i + len(kw)
        if j >= len(low):
            after_ok = True
        else:
            ch = low[j]
            after_ok = (not _is_word_char(ch)) or (
                name[j].isupper() and kw[-1].islower())
        if before_ok and after_ok:
            return True
        start = i + 1


# 公开别名：用户覆盖层（rules.py）需要同语义的词边界匹配
word_hit = _ascii_word_hit


def _build_index() -> list[tuple[str, str]]:
    """按关键词长度降序排好，保证最长命中优先。

    否则「小黑盒加速器」会被短词「小黑盒」抢走，
    「Visual Studio Code」会被「visual studio」抢走。
    """
    pairs = [(w, wx) for wx, words in SOFTWARE.items() for w in words]
    pairs.sort(key=lambda x: (-len(x[0]), x[1]))
    return pairs


_INDEX = _build_index()


def lookup(name: str) -> tuple[str, str] | None:
    """在名录中查五行。返回 (五行, 命中的关键词) 或 None。"""
    if not name:
        return None
    low = name.lower()
    for w, wx in _INDEX:
        if any(ord(c) > 127 for c in w):
            # 中英混排的关键词（如 qq音乐）必须两侧统一小写，否则会被短词抢走
            if w.lower() in low:
                return wx, w
        elif _ascii_word_hit(w, name):
            return wx, w
    return None


def stats() -> dict[str, int]:
    return {k: len(v) for k, v in SOFTWARE.items()}
