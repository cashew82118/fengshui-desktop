# -*- coding: utf-8 -*-
"""主题与字号（纯数据，不依赖 tkinter）

四套主题：宣纸（暖白·默认）、青瓷（冷绿灰）、晚照（暖赭）、墨夜（暗色）。
每套都包含界面与盘面所需的**全部**颜色，切换主题只换这一张表；
render.py 与 main.py 里不再出现任何写死的色值。

对比度按 WCAG 实测（见 docs/03-设计规范.md 2.1）：
正文 ≥ 7:1，次文字与弱文字 ≥ 4.5:1。墨夜主题单独校过一遍。
"""
from __future__ import annotations

THEMES: dict[str, dict] = {
    # ---------------------------------------------------------- 宣纸
    "paper": {
        "label": "宣纸",
        "dark": False,
        "bg": "#FAF8F3", "card": "#FEFDFB", "sunk": "#F1ECE1",
        "hover": "#F7F2E8", "ink": "#23221F", "sub": "#4F4E49",
        "weak": "#6B6961", "line": "#E3DED1", "line_outer": "#D9D3C4",
        "accent": "#8A3B12", "seal": "#9C2B24",
        "board": "#FEFDFB", "cell_tint": "#E8A33D", "center_empty": "#F8F1DF",
        "scroll": "#EDE8DC", "sel": "#EFE9DC", "track": "#EDE7DA",
        "wuxing": {"木": "#3B6D11", "火": "#A32D2D", "土": "#854F0B",
                   "金": "#5F5E5A", "水": "#185FA5"},
        "level": {"忌": "#9C2B24", "平": "#5F5E5A", "吉": "#3B6D11",
                  "述": "#6B6961"},
        "grade": {"high": "#3B6D11", "mid": "#8A3B12", "low": "#9C2B24"},
        # 分图标五级色：得位→合宜→受制→耗散→相冲，绿到红过渡
        "tone5": {"best": "#2F6B11", "good": "#7A9A1E", "mid": "#8A5A12",
                  "weak": "#C4631A", "bad": "#8E2318"},
    },
    # ---------------------------------------------------------- 青瓷
    "celadon": {
        "label": "青瓷",
        "dark": False,
        "bg": "#F1F5F2", "card": "#FBFDFA", "sunk": "#E2ECE5",
        "hover": "#E9F2EC", "ink": "#1B2721", "sub": "#3E5147",
        "weak": "#54685D", "line": "#D3E0D7", "line_outer": "#BFD2C6",
        "accent": "#1B6650", "seal": "#9C2B24",
        "board": "#FBFDFA", "cell_tint": "#8CC0A2", "center_empty": "#E7F2EA",
        "scroll": "#DFEAE3", "sel": "#DCEBE2", "track": "#E1ECE6",
        "wuxing": {"木": "#2F6B1A", "火": "#A0302A", "土": "#7A5714",
                   "金": "#46544C", "水": "#195C8C"},
        "level": {"忌": "#A0302A", "平": "#46544C", "吉": "#2F6B1A",
                  "述": "#54685D"},
        "grade": {"high": "#2F6B1A", "mid": "#1B6650", "low": "#A0302A"},
        "tone5": {"best": "#2A6B1A", "good": "#6E8F1E", "mid": "#7A5714",
                  "weak": "#B4611A", "bad": "#8E2318"},
    },
    # ---------------------------------------------------------- 晚照
    "dusk": {
        "label": "晚照",
        "dark": False,
        "bg": "#FAF3ED", "card": "#FFFCF9", "sunk": "#F2E5DA",
        "hover": "#F8EDE3", "ink": "#2A1F19", "sub": "#523F37",
        "weak": "#6A584F", "line": "#EAD8CB", "line_outer": "#DBC4B4",
        "accent": "#8F4A26", "seal": "#A8322A",
        "board": "#FFFCF9", "cell_tint": "#DFA477", "center_empty": "#F9E9DC",
        "scroll": "#F0E0D3", "sel": "#F5E5D8", "track": "#F1E3D7",
        "wuxing": {"木": "#3A6A19", "火": "#A62C25", "土": "#84510E",
                   "金": "#574D46", "水": "#1B5985"},
        "level": {"忌": "#A62C25", "平": "#574D46", "吉": "#3A6A19",
                  "述": "#6A584F"},
        "grade": {"high": "#3A6A19", "mid": "#8F4A26", "low": "#A62C25"},
        "tone5": {"best": "#2E6A16", "good": "#7A8A18", "mid": "#8F4A12",
                  "weak": "#B95A16", "bad": "#8E2318"},
    },
    # ---------------------------------------------------------- 墨夜
    "ink": {
        "label": "墨夜",
        "dark": True,
        "bg": "#15181A", "card": "#1C2022", "sunk": "#23282A",
        "hover": "#252B2E", "ink": "#E8E5DE", "sub": "#B4B0A7",
        "weak": "#918D85", "line": "#2C3235", "line_outer": "#3A4145",
        "accent": "#D18A5E", "seal": "#B23A31",
        "board": "#191D1F", "cell_tint": "#C08A48", "center_empty": "#1F2521",
        "scroll": "#242A2C", "sel": "#2E3538", "track": "#262C2E",
        "wuxing": {"木": "#7FB047", "火": "#DD5F55", "土": "#C9924B",
                   "金": "#ACACA2", "水": "#5E9FD8"},
        "level": {"忌": "#E0675C", "平": "#ACACA2", "吉": "#86B94F",
                  "述": "#918D85"},
        "grade": {"high": "#86B94F", "mid": "#D18A5E", "low": "#E0675C"},
        "tone5": {"best": "#8FC24F", "good": "#D8D24E", "mid": "#D99A4E",
                  "weak": "#E08150", "bad": "#E85F55"},
    },
}

ORDER = ["paper", "celadon", "dusk", "ink"]


def get(name: str) -> dict:
    return THEMES.get(name) or THEMES["paper"]


def label_of(name: str) -> str:
    return get(name)["label"]


def by_label(label: str) -> str:
    for key, th in THEMES.items():
        if th["label"] == label:
            return key
    return "paper"


# ---------------------------------------------------------------- 字体
#
# 2026-10-27：正文字族做成**可切换**，设置里选，选择存进 prefs。
#   grade / body / small / tiny / card / cap / tip 七个角色用 BODY_SLOT 占位，
#   实际族名由 fonts(body=...) 传入；
#   brand / prose / gua / seal 恒为宋体（用户明确「本来就是宋体的部分保留宋体」），
#   score / num 恒为 Georgia 数字。
BODY_SLOT = "@body"
BODY_DEFAULT = "Microsoft YaHei"     # 默认黑体（用户 2026-10-27 指定）
BODY_FALLBACK = "Microsoft YaHei"    # 选的字体本机没有时退到这里

# 设置里可选的正文字体。标签给人看，族名给 tkinter。
# 括号里是小字实测结论（9pt）：Windows 只给少数几款做了内嵌点阵，
# 其余靠抗锯齿，说明文字会发虚——不是 bug，选之前先知道。
BODY_CHOICES: list[tuple[str, str, str]] = [
    ("黑体", "Microsoft YaHei", "小字清楚"),
    ("宋体", "SimSun", "小字最锐利"),
    ("新宋体", "NSimSun", "同宋体"),
    ("华文中宋", "STZhongsong", "小字略虚"),
    ("华文宋体", "STSong", "小字虚"),
    ("仿宋", "FangSong", "小字虚"),
    ("华文仿宋", "STFangsong", "小字虚"),
    ("楷体", "KaiTi", "小字虚"),
    ("华文楷体", "STKaiti", "小字虚"),
    ("隶书", "LiSu", "小字糊"),
    ("华文隶书", "STLiti", "小字糊"),
    ("华文行楷", "STXingkai", "小字糊"),
    ("华文新魏", "STXinwei", "小字糊"),
]

BODY_LABELS = {fam: label for label, fam, _tip in BODY_CHOICES}
BODY_TIPS = {fam: tip for _label, fam, tip in BODY_CHOICES}
BODY_BY_LABEL = {label: fam for label, fam, _tip in BODY_CHOICES}


def body_label(fam: str) -> str:
    """族名 → 下拉框显示的文字（找不到就用默认项）。"""
    return BODY_LABELS.get(fam, BODY_CHOICES[0][0])


def body_family(label: str) -> str:
    """下拉框文字 → 族名（找不到就回默认）。"""
    return BODY_BY_LABEL.get(label, BODY_DEFAULT)


def body_tip(fam: str) -> str:
    """这个字体在小字上的实测表现，显示在设置面板里，选之前先知道。"""
    return BODY_TIPS.get(fam, "")

# 角色 → (字族, 基准字号, 字重)
#
# 2026-10-26：黑体全改衬线体。
# 2026-10-27：仿宋 → 楷体 → **宋体**（定稿）。三者行高一致（9pt 都是 12），
#   但只有宋体在 9pt 有点阵、笔画锐利；仿宋与楷体在这个尺寸发虚。
#   至此界面正文全部宋体，只剩数字用 Georgia。
# 三条实测结论，别再踩：
# 1) 楷体/仿宋 8pt 横画只有 1px，浅底上断线；9pt 才站得住。故 tiny 也是 9pt，
#    层级改由颜色（ink/sub/weak）承担，不靠字号差。
# 2) 楷体/仿宋的 linespace 天生比雅黑小 5px（9pt：12 vs 17），换字体后**行距会变紧**。
#    控件高度靠 pady 补，多行文本的闷只能靠加深字色、拆段落缓解。
# 3) 楷体没有真粗体，Tk 的 bold 是"描粗"合成，笔画会被糊掉 → 小标题不加粗，
#    靠字号（13/11）+ 颜色拉层级。
FONT_ROLES: dict[str, tuple] = {
    "brand": ("SimSun", 17, "bold"),
    "score": ("Georgia", 40, "bold"),
    "grade": (BODY_SLOT, 13),
    "body": (BODY_SLOT, 10),
    "small": (BODY_SLOT, 9),
    "tiny": (BODY_SLOT, 9),
    "card": (BODY_SLOT, 11),
    "prose": (BODY_SLOT, 12),           # 总评跟随设置（2026-10-27 用户指定）
    "gua": ("SimSun", 14),
    "cap": (BODY_SLOT, 9),
    "tip": (BODY_SLOT, 9),
    "seal": ("SimSun", 12),
    "num": ("Georgia", 11),
}

# (界面文案, 倍率)
FONT_STEPS = [("小", 0.90), ("标准", 1.00), ("大", 1.13), ("特大", 1.27)]
DEFAULT_STEP = 1


def fonts(scale: float = 1.0, body: str | None = None) -> dict[str, tuple]:
    """按倍率生成整套字体元组。字号向下取整，最小 7。

    body 是正文字族（来自 prefs），None 用默认黑体。
    固定宋体 / 固定数字的角色不受它影响。
    """
    fam_body = body or BODY_DEFAULT
    out: dict[str, tuple] = {}
    for key, spec in FONT_ROLES.items():
        fam = fam_body if spec[0] == BODY_SLOT else spec[0]
        size = spec[1]
        rest = spec[2:]
        out[key] = (fam, max(7, int(round(size * scale))), *rest)
    return out


def step_scale(index: int) -> float:
    index = min(max(0, int(index)), len(FONT_STEPS) - 1)
    return FONT_STEPS[index][1]


def step_label(index: int) -> str:
    index = min(max(0, int(index)), len(FONT_STEPS) - 1)
    return FONT_STEPS[index][0]


def scale_of(font_map: dict[str, tuple]) -> float:
    """从字体表反推倍率，供绘制层算留白用。

    用基准最大的一号字（总分数字）反推，取整误差最小。
    """
    base = FONT_ROLES["score"][1]
    return font_map["score"][1] / base if base else 1.0
