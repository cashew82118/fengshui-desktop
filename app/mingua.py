# -*- coding: utf-8 -*-
"""命卦推演（阶段十）

纯函数模块：输入公历生日与性别，输出
    干支年柱、纳音、命卦（八宅）、东西四命、四吉四凶方位、本命文昌位，
    以及「对着当前桌面」的对照说明。

规则与口径：
    - 干支／生肖以「立春」分年。立春日查 1900–2099 逐年表
      （按十年一组抄录自天气后报《二十四节气：立春时间》，测试抽查校准），
      立春前出生按上一年算。
    - 命卦数：男 (11 - 年份 mod 9) mod 9，女 (年份 + 4) mod 9（余 0 记 9）；
      余 5 男作坤、女作艮。与公开对照表十年份 × 男女交叉核对（见测试）。
    - 四吉（生气／天医／延年／伏位）四凶（绝命／五鬼／六煞／祸害）
      按《大游年歌》从命卦顺推，八星互为对称。
    - 本命文昌按出生年干：甲巳 乙午 丙申 丁酉 戊申 己酉 庚亥 辛子 壬寅 癸卯。
只读不写；任何非法输入返回 None，绝不抛异常。
"""
from __future__ import annotations

import datetime

# ---------------------------------------------------------------- 常量表

# 后天数 → 卦
NUM2GUA = {1: "坎", 2: "坤", 3: "震", 4: "巽", 6: "乾", 7: "兑",
           8: "艮", 9: "离"}

# 卦 → 方位（后天八卦定式）
GUA_DIR = {"坎": "北", "坤": "西南", "震": "东", "巽": "东南",
           "乾": "西北", "兑": "西", "艮": "东北", "离": "南"}

EAST = ("坎", "离", "震", "巽")            # 东四命
WEST = ("乾", "坤", "艮", "兑")            # 西四命

GOOD_ORDER = ("生气", "天医", "延年", "伏位")
BAD_ORDER = ("绝命", "五鬼", "六煞", "祸害")

# 大游年歌：从本卦出发，按圆序（乾坎艮震巽离坤兑）走其余七宫，
# 每宫配一字（生=生气 天=天医 延=延年 六=六煞 祸=祸害 五=五鬼 绝=绝命）。
_CIRCLE = ("乾", "坎", "艮", "震", "巽", "离", "坤", "兑")
_SONG = {
    "乾": "六天五祸绝延生",
    "坎": "五天生延绝祸六",
    "艮": "六绝祸生延天五",
    "震": "延生祸绝五天六",
    "巽": "天五六祸生绝延",
    "离": "六五绝延祸生天",
    "坤": "天延绝生祸五六",
    "兑": "生祸延绝六五天",
}
_STAR_FULL = {"生": "生气", "天": "天医", "延": "延年", "六": "六煞",
              "祸": "祸害", "五": "五鬼", "绝": "绝命"}

YOU_NIAN: dict[str, dict[str, str]] = {}
for _g in _CIRCLE:
    _i = _CIRCLE.index(_g)
    _t: dict[str, str] = {_g: "伏位"}
    for _k in range(7):
        _t[_CIRCLE[(_i + 1 + _k) % 8]] = _STAR_FULL[_SONG[_g][_k]]
    YOU_NIAN[_g] = _t

# 本命文昌：年干 → (地支, 方位, 卦)
WENCHANG = {
    "甲": ("巳", "东南", "巽"), "乙": ("午", "南", "离"),
    "丙": ("申", "西南", "坤"), "丁": ("酉", "西", "兑"),
    "戊": ("申", "西南", "坤"), "己": ("酉", "西", "兑"),
    "庚": ("亥", "西北", "乾"), "辛": ("子", "北", "坎"),
    "壬": ("寅", "东北", "艮"), "癸": ("卯", "东", "震"),
}

_STEMS = "甲乙丙丁戊己庚辛壬癸"
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

# 纳音（六十甲子，两两一组）
_NAYIN = (
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金",
    "山头火", "涧下水", "城头土", "白蜡金", "杨柳木",
    "泉中水", "屋上土", "霹雳火", "松柏木", "长流水",
    "沙中金", "山下火", "平地木", "壁上土", "金箔金",
    "覆灯火", "天河水", "大驿土", "钗钏金", "桑柘木",
    "大溪水", "沙中土", "天上火", "石榴木", "大海水",
)

# 1900–2099 逐年立春日（2 月第几天）。按十年一组抄录，
# 抽查 1952=5、2017=3、2021=3、2026=4、2096=4 等锚点（见测试）。
_LICHUN = (
    "4444555555"    # 1900–1909
    "5554455445"    # 1910–1919
    "5445544554"    # 1920–1929
    "4554455445"    # 1930–1939
    "5445544445"    # 1940–1949
    "4454444544"    # 1950–1959
    "5444544445"    # 1960–1969
    "4454444544"    # 1970–1979
    "5444444444"    # 1980–1989
    "4444444444"    # 1990–1999
    "4444444444"    # 2000–2009
    "4444444344"    # 2010–2019
    "4344434443"    # 2020–2029
    "4443444344"    # 2030–2039
    "4344434443"    # 2040–2049
    "3443344334"    # 2050–2059
    "4334433443"    # 2060–2069
    "3443344334"    # 2070–2079
    "4333433334"    # 2080–2089
    "3343334333"    # 2090–2099
)
assert len(_LICHUN) == 200


def lichun_day(year: int) -> int:
    """该年立春是 2 月几号（3/4/5）。年份越界返回 4（默认值）。"""
    if 1900 <= year <= 2099:
        return int(_LICHUN[year - 1900])
    return 4


def ganzhi(year: int) -> str:
    """干支年柱（含立春分年请先在 compute 里换算有效年份）。"""
    i = (year - 4) % 60
    return _STEMS[i % 10] + _BRANCHES[i % 12]


def nayin(year: int) -> tuple[str, str]:
    """年柱纳音 → (名称, 五行)。"""
    name = _NAYIN[((year - 4) % 60) // 2]
    return name, name[-1]


def _gua_num(year: int, gender: str) -> int:
    """命卦数（1–9，5 按性别折成坤/艮之前的原始数）。"""
    if gender == "男":
        n = (11 - year % 9) % 9
    else:
        n = (year + 4) % 9
    return n or 9


def _num2gua(n: int, gender: str) -> str:
    if n == 5:
        return "坤" if gender == "男" else "艮"
    return NUM2GUA[n]


def compute(year: int, month: int, day: int, gender: str) -> dict | None:
    """主入口：公历生日 + 性别 → 全量命主信息。非法输入返回 None。"""
    if gender not in ("男", "女"):
        return None
    try:
        datetime.date(year, month, day)
    except (TypeError, ValueError):
        return None
    if not 1900 <= year <= 2099:
        return None

    shifted = month < 2 or (month == 2 and day < lichun_day(year))
    y_eff = year - 1 if shifted else year

    num = _gua_num(y_eff, gender)
    gua = _num2gua(num, gender)
    group = "东四命" if gua in EAST else "西四命"

    table = YOU_NIAN[gua]
    good = [(s, g, GUA_DIR[g]) for s in GOOD_ORDER for g, star in
            table.items() if star == s]
    bad = [(s, g, GUA_DIR[g]) for s in BAD_ORDER for g, star in
           table.items() if star == s]

    gz = ganzhi(y_eff)
    ny, ny_wx = nayin(y_eff)
    stem = gz[0]
    wc_branch, wc_dir, wc_gua = WENCHANG[stem]

    return {
        "year": year, "month": month, "day": day, "gender": gender,
        "shifted": shifted, "y_eff": y_eff,
        "ganzhi": gz, "nayin": ny, "nayin_wuxing": ny_wx,
        "num": num, "gua": gua, "group": group,
        "good": good, "bad": bad,
        "wenchang_branch": wc_branch, "wenchang_gua": wc_gua,
        "wenchang_dir": wc_dir,
    }


# ---------------------------------------------------------------- 桌面对照

def _cell_of(grid: list, gua: str) -> tuple[int, int] | None:
    for r in range(3):
        for c in range(3):
            info = grid[r][c]
            if info and info["gua"] == gua:
                return (r, c)
    return None


def desktop_notes(info: dict, grid: list,
                  items: dict | None = None,
                  is_doc=None) -> list[str]:
    """对着当前桌面（顶北 180 度）说几句人话。

    items: {(row,col): [图标名]}；is_doc: 判断文书类的回调（可选）。
    最多 5 条，吉方先说、凶方后说。
    """
    items = items or {}
    notes: list[str] = []

    # 吉方：生气/天医/延年 空着是浪费
    for star, gua, d in info["good"][:3]:
        cell = _cell_of(grid, gua)
        if cell is None:
            continue
        names = items.get(cell, [])
        if not names:
            notes.append("吉方「%s」%s宫（%s）空着——最想推进的事，"
                         "可以把常用图标放过去。" % (star, gua, d))
        if len(notes) >= 3:
            break

    # 凶方：堆得多就点出来
    for star, gua, d in info["bad"]:
        cell = _cell_of(grid, gua)
        if cell is None:
            continue
        names = items.get(cell, [])
        if len(names) >= 4:
            notes.append("凶方「%s」%s宫（%s）堆了 %d 个（%s…），"
                         "建议清一清。" % (star, gua, d, len(names),
                                          "、".join(names[:2])))
        if len(notes) >= 5:
            break

    # 本命文昌
    cell = _cell_of(grid, info["wenchang_gua"])
    if cell is not None:
        names = items.get(cell, [])
        if not names:
            notes.append("本命文昌在%s宫（%s），空着——文书、笔记、"
                         "学习类搬过来正合适。"
                         % (info["wenchang_gua"], info["wenchang_dir"]))
        elif is_doc and any(is_doc({"name": n, "ext": "", "kind": "file"})
                            for n in names[:12]):
            notes.append("本命文昌（%s宫·%s）已有文书类图标，位置用得对。"
                         % (info["wenchang_gua"], info["wenchang_dir"]))
        else:
            notes.append("本命文昌在%s宫（%s），当前放的不是文书类；"
                         "条件允许可以换一换。"
                         % (info["wenchang_gua"], info["wenchang_dir"]))

    return notes[:5]
