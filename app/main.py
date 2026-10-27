# -*- coding: utf-8 -*-
"""主窗口

三档视图：现状 ／ 最小调整 ／ 全部重排。
前两档是"照着能做"的，最后一档是"看效果"的——每档上方都有一句功能说明。

外观：四套主题（宣纸／青瓷／晚照／墨夜）× 四档字号，偏好存在 data/prefs.json。
动效：宫格点亮 → 图标弹出 → 文字淡入；分数滚动；评分条生长；页签指示条滑动；
      图标悬停放大、提示框淡入；左右分栏可拖动。
      动效可一键关闭（右上角「动效」），关闭后所有数值立即到位。
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
import traceback
import tkinter.font as tkfont
from tkinter import ttk

import calendar
import datetime

import aiexport
import classify
import fengshui
import history
import mingua
import pericon
import palace
import paths
import prefs
import project
import prompts
import prose
import render
import report
import rules
import snapshots
import software
import theme
from tkinter import messagebox
from desk_reader import enable_dpi_awareness, read_layout

MODES = [("now", "现状"), ("proj", "最小调整"),
         ("repack", "全部重排"), ("wenchang", "优先文昌"),
         ("caiku", "优先财库")]

# 一级选项卡（key, 文案）
TOP_TABS = [("judge", "断语"), ("owner", "命主"), ("ai", "问 AI"),
            ("hist", "历史")]

# 七套话术各适合什么场景（「使用方法」弹层用，key 与 prompts.FEATURES 对应）
AI_USE_DESC = {
    "who": "我是什么取向、该往哪使劲",
    "today": "今天该推进还是该守",
    "wuxing": "某一行太旺或缺，想调平衡",
    "wenchang": "考试、论文、学习这类事",
    "caiku": "理钱、谈收入、攒钱",
    "check": "只想看桌面布局有没有硬伤",
    "review": "让 AI 挑刺、核对这份报告本身",
}

# 总评正文限宽：面板过宽时两侧对称加留白，行长不超过此值（外层另有 24px 基础留白）
PROSE_MAX_W = 640

# 未分析时评分条的七项（与 fengshui 同名同满分，仅用于画空槽）
# 未分析时评分条画七条空槽。满分与 fengshui 一致：
# 六项风水压到 80，另加「顺手」20（2026-10-27）。
EMPTY_SECTIONS = [("中宫", 12), ("明堂", 12), ("四象", 12), ("形态", 12),
                  ("杂物", 16), ("生克", 16), ("顺手", 20)]


def _ease_out(t: float) -> float:
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out(t: float) -> float:
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _smoothstep(t: float) -> float:
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return t * t * (3 - 2 * t)


def _clamp01(v: float) -> float:
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def _frames(dur_ms: int) -> int:
    """按 60fps 折算帧数。原来 26ms 一帧（38fps）会看出顿挫。"""
    return max(8, int(round(dur_ms / 16.0)))


def _fmt_time(t: str) -> str:
    """'2026-10-24T03:01:00' → '10-24 03:01'。"""
    s = str(t or "").replace("T", " ")
    return s[5:16] if len(s) >= 16 else s


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.layout: dict | None = None
        self.result: dict | None = None
        self.prev: dict | None = None
        self.error = ""
        self.hits: list[dict] = []
        self._tip_target = None
        self._cell_key = None
        self._pending = False
        self._orient_label = {}
        self.sub_tab = "cards"
        self.mode = "now"
        self.proj_layout: dict | None = None
        self.proj_result: dict | None = None
        self.moves: list[dict] = []
        self.rep_layout: dict | None = None
        self.rep_result: dict | None = None
        self.rep_moves: list[dict] = []
        self.split = 0.62
        self.ready = False                 # 启动闸门：点了「开始分析」才为真
        self._analyzed_once = False
        self.top_tab = "judge"             # 一级选项卡
        self.sub_tab = "cards"             # 断语里的二级页签
        self._gear_open = False
        self._btn_hit: dict | None = None  # 空盘中央按钮的命中框
        self._tok: dict[str, int] = {}
        self._score_shown = 0
        self.revealing = False
        self._hist_recs: list[dict] = []
        self._frames: list = []

        p = prefs.load()
        self.theme_name = p["theme"]
        self.fs_i = p["font"]
        self.anim_on = p["anim"]
        self.birth = p["birth"]             # {y,m,d,g} 或 None
        self.marks_on = p["marks"]           # 盘上标四吉四凶（可关）
        # 朝向记住上次选的：存角度（0/45/…/315），界面文案由角度反查，
        # 这样以后改文案措辞也不会把老配置读丢。
        self.top_dir = p["orient"]
        self._orient_texts = {ang: lb for ang, lb in render.ORIENT_CHOICES}
        self.orient_text = self._orient_texts.get(
            self.top_dir, render.ORIENT_CHOICES[0][1])
        self.th = theme.get(self.theme_name)
        # 正文字族：prefs 里选的，本机没有就退回黑体（不让 tk 静默回落宋体）
        self.font_family = self._resolve_body(p["font_family"])
        self.f = theme.fonts(theme.step_scale(self.fs_i), self.font_family)
        # 导出报告单独一套字体字号（只影响 HTML，不影响界面，改完不必重建）
        self.report_font = p["report_font"]
        self.report_size = p["report_size"]

        root.title("桌面风水 · 布局分析")
        root.geometry("1440x920")
        root.minsize(1180, 780)
        root.configure(bg=self.th["bg"])

        self._style()
        self._build()
        # 启动闸门：这里不读桌面、不算分。只把空盘和空状态铺好，等用户点按钮。
        self.prev = history.last()
        self._sync_ready()
        self._update_mode_text()
        self._refresh_right()
        self._draw(1.0)
        # 构造时窗口还没映射，winfo_viewable 为假、动画会被跳过。
        # 等窗口出现后再补一次入场动画。
        self.root.after(120, lambda: self._animate_reveal(320))

    # ------------------------------------------------------------ 动效基础

    def _bump(self, name: str) -> int:
        """递增令牌。回调里比对令牌，过期帧自动作废。"""
        self._tok[name] = self._tok.get(name, 0) + 1
        return self._tok[name]

    def _can_anim(self) -> bool:
        """窗口不可见（如无窗口冒烟测试）时不动画，直接把结果放到位。"""
        try:
            return bool(self.anim_on) and bool(self.root.winfo_viewable())
        except tk.TclError:
            return False

    def _fs(self) -> float:
        return theme.step_scale(self.fs_i)

    def _fade_in(self, color: str, p: float, base: str | None = None) -> str:
        """把 color 从底色**淡入**。p=0 时与底色完全相同（不可见），p=1 就是 color。

        注意 render._mix(fg, bg, a) 里 a 是 fg 的权重——参数顺序极易写反，
        淡入淡出方向错一次就是"闪一下"或者"越来越实然后消失"。所以统一走这个函数。
        """
        return render._mix(color, base or self.th["board"], _clamp01(p))

    # ------------------------------------------------------------ 外观

    def _style(self) -> None:
        th = self.th
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TCombobox", fieldbackground=th["card"],
                     background=th["card"], foreground=th["ink"],
                     bordercolor=th["line"], arrowcolor=th["sub"],
                     selectbackground=th["card"], selectforeground=th["ink"])
        st.map("TCombobox", fieldbackground=[("readonly", th["card"])],
               foreground=[("readonly", th["ink"])])
        st.configure("TButton", background=th["card"], foreground=th["ink"],
                     bordercolor=th["line"], relief="flat", padding=(13, 5),
                     font=self.f["small"])
        st.map("TButton", background=[("active", th["hover"])],
               bordercolor=[("focus", th["accent"])])
        st.configure("TScrollbar", background=th["scroll"],
                     troughcolor=th["card"], bordercolor=th["card"],
                     arrowcolor=th["sub"])

    def _chip(self, parent, text: str, cmd, pad: int = 8):
        """小方块按钮：可点、有悬停与按下反馈。"""
        th = self.th
        lbl = tk.Label(parent, text=text, bg=th["card"], fg=th["sub"],
                       font=self.f["small"], padx=pad, pady=2, cursor="hand2",
                       highlightthickness=1, highlightbackground=th["line"])

        state = {"hover": False}

        def paint() -> None:
            """按当前是否悬停重画：悬停淡底＋主色字，否则回到卡片底色。"""
            try:
                lbl.configure(
                    bg=th["hover"] if state["hover"] else th["card"],
                    fg=th["accent"] if state["hover"] else th["sub"],
                    highlightbackground=th["accent"] if state["hover"]
                    else th["line"])
            except tk.TclError:
                pass

        def press(_e=None):
            # 按下只加深一档、描边转主色；不再把底色刷成近白色
            try:
                lbl.configure(bg=th["sel"], highlightbackground=th["accent"])
            except tk.TclError:
                pass
            self.root.after(130, paint)

        lbl.bind("<Button-1>", lambda _e: (press(), cmd()))
        lbl.bind("<Enter>", lambda _e: (state.update(hover=True), paint()))
        lbl.bind("<Leave>", lambda _e: (state.update(hover=False), paint()))
        return lbl

    def _check(self, parent, text: str, cmd):
        """复选项：小方框 + 淡字，无边框无底色。

        刻意做得比按钮轻——原来用 _chip 画，和「导出」并排时看着就是第三个按钮，
        分不清哪个是动作、哪个是开关。
        """
        th = self.th
        lbl = tk.Label(parent, text="☐ " + text, bg=th["card"], fg=th["weak"],
                       font=self.f["small"], cursor="hand2")
        lbl.bind("<Button-1>", lambda _e: cmd())
        lbl.bind("<Enter>", lambda _e: lbl.configure(fg=th["accent"]))
        lbl.bind("<Leave>", lambda _e: lbl.configure(fg=th["weak"]))
        return lbl

    # ------------------------------------------------------------ 骨架

    def _build(self) -> None:
        th, f = self.th, self.f
        fs = self._fs()

        # 顶栏单行：外观设置已迁进齿轮浮层，这里只留身份与主操作。
        hdr = tk.Frame(self.root, bg=th["bg"])
        hdr.pack(side="top", fill="x", padx=20, pady=(11, 0))
        top = tk.Frame(hdr, bg=th["bg"])
        top.pack(fill="x")

        # --- 右侧（从右往左建）：齿轮 → 导出给 AI → 导出报告
        self.gear = tk.Canvas(top, width=28, height=28, bg=th["bg"],
                              highlightthickness=0, cursor="hand2")
        self.gear.pack(side="right", padx=(12, 0), pady=(2, 0))
        self.gear.bind("<Button-1>", lambda _e: self.toggle_settings())
        self.gear.bind("<Enter>", lambda _e: self._draw_gear(True))
        self.gear.bind("<Leave>", lambda _e: self._draw_gear(False))
        self._draw_gear(False)           # 修：初始就要画出来，不是悬停才出现

        # 「导出给 AI」已并入问 AI 栏（栏内「导出并复制」），顶栏只留导出报告
        self.btn_export = ttk.Button(top, text="导出报告", command=self.export)
        self.btn_export.pack(side="right")

        # --- 左侧：品牌、朝向、推演档
        tk.Label(top, text="桌面风水", bg=th["bg"], fg=th["accent"],
                 font=f["brand"]).pack(side="left")

        seal_px = int(26 * fs)
        seal = tk.Canvas(top, width=seal_px, height=seal_px, bg=th["bg"],
                         highlightthickness=0)
        seal.create_rectangle(0, 0, seal_px - 1, seal_px - 1,
                              fill=th["seal"], outline="")
        seal.create_text(seal_px / 2.0, seal_px / 2.0, text="風",
                         fill=th["card"], font=f["seal"])
        seal.pack(side="left", padx=(9, 0), pady=(2, 0))

        tk.Label(top, text="　朝向", bg=th["bg"], fg=th["sub"],
                 font=f["body"]).pack(side="left", padx=(16, 6))

        # 朝向沿用上次选择：重建界面不该把朝向打回默认
        self.orient_var = tk.StringVar(value=self.orient_text)
        for ang, label in render.ORIENT_CHOICES:
            self._orient_label[label] = ang
        box = ttk.Combobox(top, textvariable=self.orient_var, state="readonly",
                           values=[c[1] for c in render.ORIENT_CHOICES],
                           width=17, font=f["small"])
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", self._on_orient)

        self.seg = tk.Frame(top, bg=th["sunk"])
        self.seg.pack(side="left", padx=(18, 0))
        self.seg_labels: dict[str, tk.Label] = {}
        for key, text in MODES:
            lbl = tk.Label(self.seg, text=text, bg=th["sunk"], fg=th["sub"],
                           font=f["small"], padx=13, pady=4, cursor="hand2")
            lbl.pack(side="left", padx=1, pady=1)
            lbl.bind("<Button-1>", lambda _e, k=key: self.set_mode(k))
            lbl.bind("<Enter>", lambda _e, k=key: self._seg_hover(k, True))
            lbl.bind("<Leave>", lambda _e, k=key: self._seg_hover(k, False))
            self.seg_labels[key] = lbl
        self.seg_ind = tk.Frame(self.seg, bg=th["accent"], height=2)
        self.seg_ind.place(x=1, y=1, width=10, height=2)

        # --- 主体
        body = tk.Frame(self.root, bg=th["bg"])
        body.pack(side="top", fill="both", expand=True, padx=20, pady=(8, 0))
        self.body = body

        left = tk.Frame(body, bg=th["bg"])
        right = tk.Frame(body, bg=th["bg"])
        splitter = tk.Frame(body, bg=th["bg"], cursor="sb_h_double_arrow")
        self.left, self.right, self.splitter = left, right, splitter
        self._apply_split()
        splitter.bind("<Button-1>", self._split_start)
        splitter.bind("<B1-Motion>", self._split_drag)
        splitter.bind("<Double-Button-1>", lambda _e: self._reset_split())
        splitter.bind("<Enter>",
                      lambda _e: splitter.configure(bg=th["line"]))
        splitter.bind("<Leave>",
                      lambda _e: splitter.configure(bg=th["bg"]))

        # --- 左：模式说明 + 重新分析 + 盘
        # 注意：变量名不能叫 hdr——_build 末尾的 _frames 登记用的是顶栏 hdr，
        # 重名会把「换肤重建时要销毁的框架」指向这里，旧顶栏就会一直留着。
        lhdr = tk.Frame(left, bg=th["bg"])
        lhdr.pack(side="top", fill="x", padx=(4, 10), pady=(0, 6))
        # 说明块：浅底 + 左侧一条主色细线。原来整段文字直接浮在背景上，
        # 跟盘面贴在一起分不清谁是谁。
        mbox = tk.Frame(lhdr, bg=th["sunk"])
        mbox.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Frame(mbox, bg=th["accent"], width=2).pack(side="left", fill="y")
        self.mode_lbl = tk.Label(mbox, text="", bg=th["sunk"], fg=th["sub"],
                                 font=f["small"], anchor="w", justify="left",
                                 wraplength=500, padx=10, pady=5)
        self.mode_lbl.pack(side="left", fill="x", expand=True)
        # 首次分析前不显示（盘中央已有大按钮）；之后常驻，随时重扫。
        self.re_chip = tk.Label(lhdr, text="重新分析 ↻", bg=th["bg"],
                                fg=th["weak"], font=f["small"],
                                cursor="hand2", padx=2)
        self.re_chip.bind("<Button-1>", lambda _e: self.analyze())
        self.re_chip.bind("<Enter>",
                          lambda _e: self.re_chip.configure(fg=th["accent"]))
        self.re_chip.bind("<Leave>",
                          lambda _e: self.re_chip.configure(fg=th["weak"]))
        # 只有推演档（非「现状」）且确有移动时才出现，点了看挪哪些
        self.move_chip = tk.Label(lhdr, text="移动清单", bg=th["bg"],
                                  fg=th["weak"], font=f["small"],
                                  cursor="hand2", padx=2)
        self.move_chip.bind("<Button-1>", lambda _e: self._open_moves())
        self.move_chip.bind("<Enter>",
                            lambda _e: self.move_chip.configure(fg=th["accent"]))
        self.move_chip.bind("<Leave>",
                            lambda _e: self.move_chip.configure(fg=th["weak"]))

        self.board = tk.Canvas(left, bg=th["board"], highlightthickness=0)
        self.board.pack(side="top", fill="both", expand=True)
        self.board.bind("<Configure>", self._on_resize)
        self.board.bind("<Motion>", self._on_motion)
        self.board.bind("<Button-1>", self._on_click)
        self.board.bind("<Leave>", lambda _e: self._on_leave())

        # --- 右：一级选项卡在最顶，选项卡里装"除盘之外的所有内容"
        box2 = tk.Frame(right, bg=th["bg"])
        box2.pack(fill="both", expand=True)
        self.box2 = box2

        tbar = tk.Frame(box2, bg=th["bg"], height=int(30 + 8 * fs))
        tbar.pack(fill="x", pady=(0, 6))
        tbar.pack_propagate(False)
        self.topbar = tbar
        self.top_labels: dict[str, tk.Label] = {}
        for i, (key, text) in enumerate(TOP_TABS):
            active = key == self.top_tab
            lbl = tk.Label(tbar, text=text, bg=th["bg"],
                           fg=th["accent"] if active else th["weak"],
                           font=f["grade"] if active else f["small"],
                           cursor="hand2")
            lbl.pack(side="left", padx=(0 if i == 0 else 20, 0))
            lbl.bind("<Button-1>", lambda _e, k=key: self._top(k))
            self.top_labels[key] = lbl
        self.topline = tk.Frame(tbar, bg=th["accent"], height=2)
        self.topline.place(x=0, y=tbar.winfo_reqheight() - 4, width=10, height=2)
        self.root.after_idle(lambda: self._move_topline(False))

        # --- 断语页：分数卡 + 评分条 + 二级页签（分条 / 总评）
        self.pane_judge = tk.Frame(box2, bg=th["bg"])

        head = tk.Frame(self.pane_judge, bg=th["card"],
                        highlightbackground=th["line"], highlightthickness=1)
        head.pack(fill="x", pady=(0, 9))
        hpad = tk.Frame(head, bg=th["card"])
        hpad.pack(fill="x", padx=16, pady=(10, 10))

        row = tk.Frame(hpad, bg=th["card"])
        row.pack(fill="x")
        # 分数用 Georgia 40 号：比例字体里不同数字的渲染高度不一样（「8」有上下 overshoot），
        # 滚动动画逐帧换数字时外层会一涨一缩，看起来像抽了一下（2026-10-27 用户报）。
        # 这里给分数固定一个盒子：宽按最长的「100」算、高按字体行高算，
        # 数字怎么变盒子都不动，右边的评级也就不会跟着左右跳。
        _sf = tkfont.Font(root=self.root, font=f["score"])
        _sc_w = _sf.measure("88") + 8          # 先按两位数留位
        _sc_h = _sf.metrics("linespace") + 24
        self.root.tk.call("font", "delete", _sf.name)
        self.scbox = tk.Frame(row, bg=th["card"], width=_sc_w, height=_sc_h)
        self.scbox.pack(side="left")
        self.scbox.pack_propagate(False)
        self.score_lbl = tk.Label(self.scbox, text="—", bg=th["card"],
                                  fg=th["ink"], font=f["score"], anchor="w")
        self.score_lbl.pack(fill="both", expand=True)
        self.grade_lbl = tk.Label(row, text="", bg=th["card"], fg=th["sub"],
                                  font=f["grade"])
        self.grade_lbl.pack(side="left", padx=(12, 0),
                            pady=(int(16 * fs), 0))
        self.summary_lbl = tk.Label(hpad, text="", bg=th["card"], fg=th["sub"],
                                    font=f["small"], anchor="w", justify="left",
                                    wraplength=400)
        self.summary_lbl.pack(fill="x", pady=(2, 8))

        self.bars = tk.Canvas(hpad, height=int(120 * fs), bg=th["card"],
                              highlightthickness=0)
        self.bars.pack(fill="x")
        self.ledger = tk.Label(hpad, text="", bg=th["card"], fg=th["weak"],
                               font=f["tiny"], anchor="w")
        self.ledger.pack(fill="x", pady=(4, 0))
        self.prev_lbl = tk.Label(hpad, text="", bg=th["card"], fg=th["weak"],
                                 font=f["tiny"], anchor="w")
        self.prev_lbl.pack(fill="x")

        sbar = tk.Frame(self.pane_judge, bg=th["bg"],
                        height=int(20 + 6 * fs))
        sbar.pack(fill="x", pady=(0, 0))
        sbar.pack_propagate(False)
        self.subbar = sbar
        self.tab_cards = tk.Label(sbar, text="分条", bg=th["bg"],
                                  fg=th["accent"], font=f["card"],
                                  cursor="hand2")
        self.tab_cards.pack(side="left", padx=(2, 14))
        self.tab_pericon = tk.Label(sbar, text="分图标", bg=th["bg"],
                                    fg=th["weak"], font=f["small"],
                                    cursor="hand2")
        self.tab_pericon.pack(side="left", padx=(0, 14))
        self.tab_prose = tk.Label(sbar, text="总评", bg=th["bg"],
                                  fg=th["weak"], font=f["small"],
                                  cursor="hand2")
        self.tab_prose.pack(side="left")
        for key, lbl in (("cards", self.tab_cards),
                         ("pericon", self.tab_pericon),
                         ("prose", self.tab_prose)):
            lbl.bind("<Button-1>", lambda _e, k=key: self._tab(k))

        self.pane_cards = tk.Frame(self.pane_judge, bg=th["card"],
                                   highlightbackground=th["line"],
                                   highlightthickness=1)
        self.scroll = tk.Canvas(self.pane_cards, bg=th["card"],
                                highlightthickness=0)
        scbar = ttk.Scrollbar(self.pane_cards, orient="vertical",
                              command=self.scroll.yview)
        self.scroll.configure(yscrollcommand=scbar.set)
        scbar.pack(side="right", fill="y")
        self.scroll.pack(side="left", fill="both", expand=True)
        self.cards = tk.Frame(self.scroll, bg=th["card"])
        self._cards_win = self.scroll.create_window((0, 0), window=self.cards,
                                                    anchor="nw")
        self.cards.bind("<Configure>", self._on_cards_configure)
        self.scroll.bind("<Configure>",
                         lambda e: self.scroll.itemconfigure(self._cards_win,
                                                             width=e.width))

        # --- 分图标页：九宫两级折叠（宫 → 图标 → 三段）
        self.pane_pericon = tk.Frame(self.pane_judge, bg=th["card"],
                                     highlightbackground=th["line"],
                                     highlightthickness=1)
        # 图例固定在底部（side=bottom 先 pack），滚动区吃剩下的空间
        self.picon_legend = tk.Frame(self.pane_pericon, bg=th["card"])
        self.picon_legend.pack(side="bottom", fill="x")
        self.picon_top = tk.Frame(self.pane_pericon, bg=th["card"])
        self.picon_top.pack(side="top", fill="both", expand=True)
        self.picon_scroll = tk.Canvas(self.picon_top, bg=th["card"],
                                      highlightthickness=0)
        pcbar = ttk.Scrollbar(self.picon_top, orient="vertical",
                              command=self.picon_scroll.yview)
        self.picon_scroll.configure(yscrollcommand=pcbar.set)
        pcbar.pack(side="right", fill="y")
        self.picon_scroll.pack(side="left", fill="both", expand=True)
        self.picon_body = tk.Frame(self.picon_scroll, bg=th["card"])
        self._picon_win = self.picon_scroll.create_window(
            (0, 0), window=self.picon_body, anchor="nw")
        self.picon_body.bind("<Configure>", self._on_picon_configure)
        self.picon_scroll.bind(
            "<Configure>",
            lambda e: self.picon_scroll.itemconfigure(self._picon_win,
                                                      width=e.width))
        self._picon_groups = []
        self._picon_open = set()      # 已展开的宫（索引）
        self._picon_icon_open = set()  # 已展开的图标 ("gi:ii")
        self._build_picon_legend()

        # --- 总评页：题头／摘要条／分节正文，全靠字号与留白分层（无卡片、无描边）
        self.pane_prose = tk.Frame(self.pane_judge, bg=th["card"])
        self.prose_body = tk.Frame(self.pane_prose, bg=th["card"])
        self.prose_body.pack(fill="both", expand=True, padx=24, pady=18)

        phead = tk.Frame(self.prose_body, bg=th["card"])
        phead.pack(fill="x")
        tk.Label(phead, text="总评", bg=th["card"], fg=th["ink"],
                 font=(f["prose"][0], f["prose"][1] + 4)).pack(side="left")
        self.prose_meta = tk.Label(phead, text="", bg=th["card"],
                                   fg=th["weak"], font=f["tiny"])
        self.prose_meta.pack(side="right", pady=(7, 0))
        tk.Frame(self.prose_body, bg=th["line"], height=1).pack(
            fill="x", pady=(7, 0))

        # 摘要条：分数（大号 Georgia）+ 评级 + 一句话。未分析时整条收起。
        self.prose_strip = tk.Frame(self.prose_body, bg=th["card"])
        s_left = tk.Frame(self.prose_strip, bg=th["card"])
        s_left.pack(side="left", anchor="n")
        self.prose_score = tk.Label(s_left, text="", bg=th["card"],
                                    fg=th["accent"], font=f["score"])
        self.prose_score.pack(side="left")
        tk.Label(s_left, text="/100", bg=th["card"], fg=th["weak"],
                 font=f["tiny"]).pack(side="left", anchor="s", pady=(0, 10))
        s_right = tk.Frame(self.prose_strip, bg=th["card"])
        s_right.pack(side="left", fill="x", expand=True, padx=(18, 0),
                     pady=(9, 0))
        self.prose_grade = tk.Label(s_right, text="", bg=th["card"],
                                    fg=th["ink"], font=f["grade"], anchor="w")
        self.prose_grade.pack(fill="x")
        self.prose_line = tk.Label(s_right, text="", bg=th["card"],
                                   fg=th["sub"], font=f["small"], anchor="w")
        self.prose_line.pack(fill="x", pady=(3, 0))

        prose_wrap = tk.Frame(self.prose_body, bg=th["card"])
        prose_wrap.pack(fill="both", expand=True, pady=(12, 0))
        # 中文用 wrap="char"：wrap="word" 会把「·」「，」这类标点当成断行点，
        # 结果是行尾参差、逗号跑到行首（2026-10-27 最大化截图发现）。
        # 中文本来就可以逐字断行，char 反而更整齐。
        self.prose_text = tk.Text(prose_wrap, wrap="char", bg=th["card"],
                                  fg=th["ink"], font=f["prose"], bd=0,
                                  highlightthickness=0, cursor="arrow",
                                  selectbackground=th["sel"],
                                  selectforeground=th["ink"],
                                  insertbackground=th["ink"])
        psbar = ttk.Scrollbar(prose_wrap, orient="vertical",
                              command=self.prose_text.yview)
        self.prose_text.configure(yscrollcommand=psbar.set)
        psbar.pack(side="right", fill="y")
        self.prose_text.pack(side="left", fill="both", expand=True)

        # 排版：lead 稍大一档领起；sect 小字宽字距作节题；body 首行缩进 2em、
        # 行间 spacing2=7、段后 12；close 用次色收尾，前置一枚分隔点。
        ppx = max(12, int(round(f["prose"][1] * 4.0 / 3.0)))   # pt → px
        self.prose_text.tag_configure(
            "cap", font=(f["prose"][0], f["prose"][1] * 2),
            foreground=th["accent"],
            spacing1=2)
        self.prose_text.tag_configure(
            "lead", font=(f["prose"][0], f["prose"][1] + 1), spacing2=8,
            spacing3=18)
        self.prose_text.tag_configure(
            "body", lmargin1=2 * ppx, spacing2=9, spacing3=14)
        self.prose_text.tag_configure(
            "dot", font=f["cap"], foreground=th["weak"], justify="center",
            spacing1=14, spacing3=14)
        self.prose_text.tag_configure(
            "close", lmargin1=2 * ppx, spacing2=9, spacing3=6,
            foreground=th["sub"])
        self.pane_prose.bind("<Configure>", self._prose_fit)

        # --- 历史页
        self.pane_hist = tk.Frame(box2, bg=th["bg"])
        hcard = tk.Frame(self.pane_hist, bg=th["card"],
                         highlightbackground=th["line"], highlightthickness=1)
        hcard.pack(fill="both", expand=True)
        self.hist_sum = tk.Label(hcard, text="", bg=th["card"],
                                 fg=th["sub"], font=f["tiny"], anchor="w",
                                 justify="left", wraplength=380)
        self.hist_sum.pack(fill="x", padx=14, pady=(8, 0))

        # 三模块底色略有差异（同主题的三档近似色，天然联动）：
        # 趋势图 sunk（下沉）/ 快照与日历 card（主卡）/ 全部记录 bg（最暗，像档案区）
        self.hist_chart = tk.Canvas(hcard, height=int(96 * fs),
                                    bg=th["sunk"], highlightthickness=0)
        self.hist_chart.pack(fill="x", padx=8, pady=(4, 2))
        self.hist_chart.bind("<Configure>", lambda _e: self._draw_hist(1.0))

        # --- 桌面快照：保存按钮 + 日历 + 当日列表（趋势图留在上方常驻）
        tk.Frame(hcard, bg=th["line"], height=1).pack(fill="x", padx=14,
                                                      pady=(6, 0))
        srow = tk.Frame(hcard, bg=th["card"])
        srow.pack(fill="x", padx=14, pady=(6, 0))
        tk.Label(srow, text="桌面快照", bg=th["card"], fg=th["sub"],
                 font=f["small"]).pack(side="left")
        self.snap_btn = self._chip(srow, "保存本次分析", self._snap_save, pad=8)
        self.snap_btn.pack(side="left", padx=(8, 0))
        self.snap_count_lbl = tk.Label(srow, text="", bg=th["card"],
                                       fg=th["weak"], font=f["tiny"])
        self.snap_count_lbl.pack(side="right")

        crow = tk.Frame(hcard, bg=th["card"])
        crow.pack(fill="x", padx=14, pady=(4, 0))
        self.cal_prev = tk.Label(crow, text="‹", bg=th["card"], fg=th["weak"],
                                 font=f["card"], cursor="hand2", padx=6)
        self.cal_prev.pack(side="left")
        self.cal_title = tk.Label(crow, text="", bg=th["card"], fg=th["ink"],
                                  font=f["small"])
        self.cal_title.pack(side="left", expand=True)
        self.cal_next = tk.Label(crow, text="›", bg=th["card"], fg=th["weak"],
                                 font=f["card"], cursor="hand2", padx=6)
        self.cal_next.pack(side="right")
        self.cal_prev.bind("<Button-1>", lambda _e: self._cal_shift(-1))
        self.cal_next.bind("<Button-1>", lambda _e: self._cal_shift(1))
        for w in (self.cal_prev, self.cal_next):
            w.bind("<Enter>", lambda _e, x=w: x.configure(fg=th["accent"]))
            w.bind("<Leave>", lambda _e, x=w: x.configure(fg=th["weak"]))

        self.cal_grid = tk.Frame(hcard, bg=th["card"])
        self.cal_grid.pack(fill="x", padx=12, pady=(2, 0))
        self.snap_list = tk.Frame(hcard, bg=th["card"])
        self.snap_list.pack(fill="x", padx=14, pady=(2, 4))

        # --- 全部分析记录（只存数字，滚动区）
        tk.Frame(hcard, bg=th["line"], height=1).pack(fill="x", padx=14)
        tk.Label(hcard, text="全部分析记录", bg=th["bg"], fg=th["weak"],
                 font=f["tiny"], anchor="w").pack(fill="x", padx=14,
                                                  pady=(4, 0))
        hwrap = tk.Frame(hcard, bg=th["bg"])
        hwrap.pack(fill="both", expand=True)
        self.hist_scroll = tk.Canvas(hwrap, bg=th["bg"], highlightthickness=0)
        hsbar = ttk.Scrollbar(hwrap, orient="vertical",
                              command=self.hist_scroll.yview)
        self.hist_scroll.configure(yscrollcommand=hsbar.set)
        hsbar.pack(side="right", fill="y")
        self.hist_scroll.pack(side="left", fill="both", expand=True)
        self.hist_rows = tk.Frame(self.hist_scroll, bg=th["bg"])
        self._hist_win = self.hist_scroll.create_window((0, 0),
                                                        window=self.hist_rows,
                                                        anchor="nw")
        self.hist_rows.bind(
            "<Configure>",
            lambda _e: self.hist_scroll.configure(
                scrollregion=self.hist_scroll.bbox("all")))
        self.hist_scroll.bind(
            "<Configure>",
            lambda e: self.hist_scroll.itemconfigure(self._hist_win,
                                                     width=e.width))

        # --- 命主页（阶段 10）
        self.pane_owner = tk.Frame(box2, bg=th["card"])
        self._build_owner()

        # --- 问 AI 页（阶段 11 填充内容）
        self.pane_ai = tk.Frame(box2, bg=th["card"])
        self._build_ai()

        self.pane_judge.pack(fill="both", expand=True)
        self._tab(self.sub_tab)          # 修：默认分条要有内容，不能等切一次页签
        self._build_settings_panel()
        self.root.bind_all("<MouseWheel>", self._on_wheel)

        # --- 状态栏
        bar = tk.Frame(self.root, bg=th["bg"])
        bar.pack(side="bottom", fill="x", padx=22, pady=(4, 8))
        self.status = tk.Label(bar, text="", bg=th["bg"], fg=th["weak"],
                               font=f["tiny"], anchor="w")
        self.status.pack(side="left")

        self._frames = [hdr, body, bar]

    # ------------------------------------------------------------ 分栏

    def _apply_split(self) -> None:
        gap = 0.008
        x = self.split
        self.left.place(relx=0.0, rely=0.0, relwidth=x, relheight=1.0)
        self.splitter.place(relx=x, rely=0.0, relwidth=gap, relheight=1.0)
        self.right.place(relx=x + gap, rely=0.0, relwidth=1 - x - gap,
                         relheight=1.0)

    def _split_start(self, _e) -> None:
        self._dragging = True

    def _split_drag(self, event) -> None:
        if not self.body.winfo_width():
            return
        rel = (event.x_root - self.body.winfo_rootx()) / self.body.winfo_width()
        self.split = min(0.80, max(0.34, rel))
        self._apply_split()

    def _reset_split(self) -> None:
        self.split = 0.62
        self._apply_split()

    # ------------------------------------------------------------ 主题与字号

    def _resolve_body(self, fam: str) -> str:
        """确认这个字族本机能用，不能用就退回黑体。

        tkinter 遇到不存在的字族**不报错**，只会静默回落到「宋体」，
        所以必须用 actual("family") 看它最终解析成什么。
        注意 actual 返回的是**中文名**（"SimSun" → "宋体"），不能用英文族名比对；
        SimSun 自己就返回「宋体」，是唯一需要特判的。
        """
        if fam == theme.BODY_FALLBACK:
            return fam
        try:
            probe = tkfont.Font(root=self.root, family=fam, size=12)
            got = str(probe.actual("family"))
            self.root.tk.call("font", "delete", probe.name)
        except tk.TclError:
            return theme.BODY_FALLBACK
        if got == "宋体" and fam != "SimSun":
            return theme.BODY_FALLBACK
        return fam

    def _save_prefs(self) -> None:
        prefs.save({"theme": self.theme_name, "font": self.fs_i,
                    "anim": self.anim_on, "birth": self.birth,
                    "marks": self.marks_on, "orient": self.top_dir,
                    "font_family": self.font_family,
                    "report_font": self.report_font,
                    "report_size": self.report_size})

    def set_theme(self, name: str) -> None:
        if name == self.theme_name:
            return
        was_open = self._gear_open
        was_editor = getattr(self, "rule_win", None) is not None
        self.close_settings()
        self.theme_name = name
        self.th = theme.get(name)
        self._save_prefs()
        self._rebuild()
        if was_open:
            self.open_settings()
        if was_editor:                    # 编辑器开着换主题 → 原样重开
            self._rule_editor_open()

    def set_font_family(self, fam: str) -> None:
        """换正文字族：只动正文/小标题/说明，宋体位置（品牌、卦名、总评、印章）不动。"""
        want = fam
        fam = self._resolve_body(fam)
        if fam == self.font_family:
            return
        was_open = self._gear_open
        was_editor = getattr(self, "rule_win", None) is not None
        self.close_settings()
        self.font_family = fam
        self.f = theme.fonts(theme.step_scale(self.fs_i), fam)
        self._save_prefs()
        self._rebuild()
        if was_open:
            self.open_settings()
        if was_editor:
            self._rule_editor_open()
        if want != fam:
            self.status.configure(
                text="本机没有 %s，已改用黑体。换一台装了它的电脑再选。" % want)

    def set_report_font(self, fam: str) -> None:
        """只改导出报告的字体，界面不动，因此不用重建。"""
        if fam == self.report_font:
            return
        self.report_font = fam
        self._save_prefs()
        self.status.configure(
            text="导出报告字体改为「%s」，下次导出时生效。"
                 % theme.body_label(fam))

    def set_report_size(self, label: str) -> None:
        """报告字号：按中文标签取档位，整页等比缩放。"""
        names = [lab for lab, _m in theme.FONT_STEPS]
        if label not in names:
            return
        idx = names.index(label)
        if idx == self.report_size:
            return
        self.report_size = idx
        self._save_prefs()
        self.status.configure(
            text="导出报告字号改为「%s」，下次导出时生效。" % label)

    def bump_font(self, delta: int) -> None:
        idx = min(max(0, self.fs_i + delta), len(theme.FONT_STEPS) - 1)
        if idx == self.fs_i:
            return
        was_open = self._gear_open
        was_editor = getattr(self, "rule_win", None) is not None
        self.close_settings()
        self.fs_i = idx
        self.f = theme.fonts(theme.step_scale(idx), self.font_family)
        self._save_prefs()
        self._rebuild()
        if was_open:
            self.open_settings()
        if was_editor:
            self._rule_editor_open()

    def toggle_anim(self) -> None:
        self.anim_on = not self.anim_on
        self._save_prefs()
        try:
            self.anim_chip.configure(
                text="动效 · 开" if self.anim_on else "动效 · 关")
        except (AttributeError, tk.TclError):
            pass
        if not self.anim_on:
            for k in ("reveal", "score", "bars", "tip"):
                self._bump(k)
            self._draw(reveal=1.0)
            self._refresh_right()
            self._move_topline(False)

    def toggle_marks(self) -> None:
        """盘上四吉四凶角标：可关（有人嫌花）。未填生辰时本就无标记。"""
        self.marks_on = not self.marks_on
        self._save_prefs()
        try:
            self.marks_chip.configure(
                text="四吉四凶 · 开" if self.marks_on else "四吉四凶 · 关")
        except (tk.TclError, AttributeError):
            pass
        self._draw(1.0)
        note = "命主：盘上%s四吉四凶标记" % ("显示" if self.marks_on else "隐藏")
        if not self.owner:
            note += "（还没填生辰，填了才会标）"
        self.status.configure(text=note)

    def _rebuild(self) -> None:
        """换主题或字号后重建界面。数据留在内存里，不重新扫描桌面。"""
        for k in list(self._tok):
            self._bump(k)
        for w in self._frames:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._frames = []
        try:
            self.root.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        self.root.configure(bg=self.th["bg"])
        self._score_shown = 0
        self._moves_close()           # 清单弹窗也随重建关掉（内容已过期）
        self._snap_close()
        self._ai_help_close()         # 使用说明是旧字号/旧配色，一并关掉
        self._style()
        self._build()
        self._sync_seg()              # 重建后要还原当前推演档位的高亮
        if self.top_tab == "judge":
            if self.sub_tab != "cards":
                self._tab(self.sub_tab)     # 还原二级页签
        else:
            self._top(self.top_tab)         # 还原一级选项卡
        self._sync_ready()
        self._refresh_right()
        self._update_mode_text()
        self._animate_reveal()

    # ------------------------------------------------------------ 分段控件

    def _seg_hover(self, key: str, on: bool) -> None:
        if key == self.mode:
            return
        self.seg_labels[key].configure(
            bg=self.th["hover"] if on else self.th["sunk"])

    def _sync_seg(self) -> None:
        for key, _ in MODES:
            lbl = self.seg_labels[key]
            active = key == self.mode
            lbl.configure(bg=self.th["card"] if active else self.th["sunk"],
                          fg=self.th["accent"] if active
                          else self.th["sub"],
                          font=self.f["card"] if active else self.f["small"])
        self._slide_seg()

    def _slide_seg(self, animate: bool = True, _tries: int = 0) -> None:
        lbl = self.seg_labels.get(self.mode)
        if lbl is None:
            return
        try:
            self.seg.update_idletasks()
            x, w = lbl.winfo_x(), lbl.winfo_width()
            y = max(0, self.seg.winfo_height() - 2)
        except tk.TclError:
            return
        if w <= 1:
            if _tries < 20:          # 控件还没布局好，稍等再试；有上限，不无限重试
                self.root.after(50, lambda: self._slide_seg(animate,
                                                            _tries + 1))
            return
        tok = self._bump("seg")
        info = self.seg_ind.place_info()
        try:
            cur = float(info.get("x", x) or x)
        except (TypeError, ValueError):
            cur = float(x)
        if not animate or not self._can_anim() or abs(cur - x) < 0.5:
            self.seg_ind.place(x=x, y=y, width=w, height=2)
            return
        steps = _frames(240)

        def step(i: int) -> None:
            if self._tok.get("seg") != tok:
                return
            p = _ease_in_out(i / steps)
            self.seg_ind.place(x=cur + (x - cur) * p, y=y, width=w, height=2)
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    # ------------------------------------------------------------ 数据

    def _scene(self) -> tuple[dict | None, dict | None, list[dict]]:
        if self.mode == "proj" and self.proj_result:
            return self.proj_layout, self.proj_result, self.moves
        if self.mode == "repack" and self.rep_result:
            return self.rep_layout, self.rep_result, self.rep_moves
        if self.mode == "wenchang" and self.wc_result:
            return self.wc_layout, self.wc_result, self.wc_moves
        if self.mode == "caiku" and self.ck_result:
            return self.ck_layout, self.ck_result, self.ck_moves
        return self.layout, self.result, []

    def analyze(self, animate: bool = True) -> None:
        """启动闸门：只有用户点「开始分析」才会走到这里。

        读桌面 → 分析 → 写历史 → 重绘。历史只在此处写，构造时绝不写。
        """
        self.ready = False
        self.prev = history.last()
        self.mode = "now"
        self.proj_layout = self.proj_result = None
        self.rep_layout = self.rep_result = None
        self.moves, self.rep_moves = [], []
        self.wc_layout = self.wc_result = None
        self.ck_layout = self.ck_result = None
        try:
            self.layout, warnings = read_layout()
            self.error = ""
            msg = "已读取 %d 个图标 · 画布 %d×%d" % (
                len(self.layout["icons"]), self.layout["canvas"][0],
                self.layout["canvas"][1])
            if warnings:
                msg += " · " + "；".join(warnings)
        except RuntimeError as exc:
            self.layout = None
            self.result = None
            self.error = str(exc)
            msg = self.error
        self.status.configure(text=msg)
        self._analyze()
        self.ready = bool(self.layout) and self.result is not None
        self._analyzed_once = self._analyzed_once or self.ready
        if self.ready:
            counts = [0] * 9
            for it in self.layout["icons"]:
                counts[it["row"] * 3 + it["col"]] += 1
            history.append(self.result["score"], self.result["grade"], counts,
                           self.result["stats"]["total"])
        self._score_shown = 0
        self._sync_seg()
        self._sync_ready()
        self._sync_moves()
        self._sync_ai()
        self._update_mode_text()
        self._refresh_right()            # ready 状态变了，右栏要重刷
        if animate:
            self._animate_reveal()
        else:
            self._draw(1.0)
        if self.top_tab == "hist":       # 刚追加过一条，列表要跟着变
            self._fill_history()
            self._snap_refresh()

    # ------------------------------------------------------------ 问 AI（阶段 11）

    AI_HINT = ("文件里已带评分规则，AI 不需要猜。如果它的结论里没有出现文件中的数字，"
               "多半是没读——换「审稿」再试一次。")

    def _build_ai(self) -> None:
        th, f = self.th, self.f
        self.ai_feature = "who" if self.owner else "check"
        self.ai_variant = 0
        self.ai_names = False
        self.ai_diag = False
        self.ai_last = None

        wrap = tk.Frame(self.pane_ai, bg=th["card"])
        wrap.pack(fill="both", expand=True)
        pad = tk.Frame(wrap, bg=th["card"])
        pad.pack(fill="both", expand=True, padx=18, pady=(14, 0))

        hrow = tk.Frame(pad, bg=th["card"])
        hrow.pack(fill="x")
        tk.Label(hrow, text="这份文件给任何 AI 都能读，已附评分规则，它不用猜。",
                 bg=th["card"], fg=th["sub"], font=f["small"],
                 anchor="w").pack(side="left")
        self.ai_help_chip = self._chip(hrow, "使用方法", self._ai_help, pad=8)
        self.ai_help_chip.pack(side="right")
        tk.Label(pad, text="先选一套话术，复制文案粘进对话框，再把导出的文件一起发过去。",
                 bg=th["card"], fg=th["weak"], font=f["tiny"],
                 anchor="w").pack(fill="x", pady=(2, 8))

        # --- 七选一（分两行，免得挤）
        self.ai_chips: dict[str, tk.Label] = {}
        for row_keys in (prompts.FEATURES[:4], prompts.FEATURES[4:]):
            row = tk.Frame(pad, bg=th["card"])
            row.pack(fill="x", pady=(0, 4))
            for key, label, _need, _v in row_keys:
                lbl = tk.Label(row, text=label, bg=th["card"], fg=th["sub"],
                               font=f["small"], padx=9, pady=3,
                               cursor="hand2", highlightthickness=1,
                               highlightbackground=th["line"])
                lbl.pack(side="left", padx=(0, 6))
                lbl.bind("<Button-1>", lambda _e, k=key: self._ai_pick(k))
                lbl.bind("<Enter>", lambda _e, k=key: self._ai_hover(k, True))
                lbl.bind("<Leave>", lambda _e, k=key: self._ai_hover(k, False))
                self.ai_chips[key] = lbl

        # --- 预览（只读，可选中复制）
        pv = tk.Frame(pad, bg=th["card"])
        pv.pack(fill="both", expand=True, pady=(8, 6))
        # height 是**最小行数**：Text 默认 24 行，会把下面几行挤出可视区
        # （实测：底部「上次导出」被截、11.6 提示整行消失）。给 7 行，
        # 剩下的靠 expand 撑满。
        self.ai_text = tk.Text(pv, wrap="word", bg=th["sunk"], fg=th["ink"],
                               font=f["small"], bd=0, highlightthickness=0,
                               height=7, padx=12, pady=10, cursor="arrow",
                               selectbackground=th["sel"],
                               selectforeground=th["ink"],
                               insertbackground=th["ink"])
        sb = ttk.Scrollbar(pv, orient="vertical", command=self.ai_text.yview)
        self.ai_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.ai_text.pack(side="left", fill="both", expand=True)

        # --- 操作行
        acts = tk.Frame(pad, bg=th["card"])
        acts.pack(fill="x", pady=(0, 6))
        self.ai_ver_chip = self._chip(acts, "换一版 · 1/3",
                                      self._ai_next_variant, pad=9)
        self.ai_ver_chip.pack(side="left")
        self.ai_copy_chip = self._chip(acts, "复制文案", self._ai_copy, pad=9)
        self.ai_copy_chip.pack(side="left", padx=(8, 0))
        self.ai_save_chip = self._chip(acts, "导出数据", self._ai_save, pad=9)
        self.ai_save_chip.pack(side="left", padx=(8, 0))
        self.ai_export_chip = self._chip(acts, "导出并复制", self._ai_export,
                                         pad=9)
        self.ai_export_chip.pack(side="left", padx=(8, 0))
        self.ai_len_lbl = tk.Label(acts, text="", bg=th["card"], fg=th["weak"],
                                   font=f["tiny"])
        self.ai_len_lbl.pack(side="right")

        # --- 选项（小方框样式，刻意不做得像按钮）
        opts = tk.Frame(pad, bg=th["card"])
        opts.pack(fill="x", pady=(2, 8))
        tn = tk.Label(opts, text="导出选项", bg=th["card"], fg=th["weak"],
                      font=f["tiny"])
        tn.pack(side="left", padx=(0, 10))
        self.ai_name_chip = self._check(opts, "含图标文件名",
                                        self._ai_toggle_names)
        self.ai_name_chip.pack(side="left")
        self.ai_diag_chip = self._check(opts, "含完整诊断",
                                        self._ai_toggle_diag)
        self.ai_diag_chip.pack(side="left", padx=(12, 0))
        tk.Label(opts, text="名称默认不写入文件", bg=th["card"], fg=th["weak"],
                 font=f["tiny"]).pack(side="left", padx=(10, 0))

        # --- 补充背景
        nrow = tk.Frame(pad, bg=th["card"])
        nrow.pack(fill="x", pady=(0, 6))
        tk.Label(nrow, text="补充背景", bg=th["card"], fg=th["sub"],
                 font=f["small"]).pack(side="left", padx=(0, 6))
        self.ai_note_var = tk.StringVar()
        ent = tk.Entry(nrow, textvariable=self.ai_note_var, bg=th["card"],
                       fg=th["ink"], font=f["small"], highlightthickness=1,
                       highlightbackground=th["line"],
                       highlightcolor=th["accent"],
                       insertbackground=th["ink"])
        ent.pack(side="left", fill="x", expand=True, ipady=2)

        # --- 上次导出
        frow = tk.Frame(pad, bg=th["card"])
        frow.pack(fill="x")
        self.ai_path_lbl = tk.Label(frow, text="上次导出：—", bg=th["card"],
                                    fg=th["weak"], font=f["tiny"], anchor="w")
        self.ai_path_lbl.pack(side="left")
        self.ai_open_btn = tk.Label(frow, text="打开文件夹", bg=th["card"],
                                    fg=th["weak"], font=f["tiny"],
                                    cursor="hand2")
        self.ai_open_btn.pack(side="right")
        self.ai_open_btn.bind("<Button-1>", lambda _e: self._ai_open_dir())
        self.ai_open_btn.bind("<Enter>",
                              lambda _e: self.ai_open_btn.configure(
                                  fg=th["accent"]))
        self.ai_open_btn.bind("<Leave>",
                              lambda _e: self.ai_open_btn.configure(
                                  fg=th["weak"]))

        self.ai_hint_lbl = tk.Label(self.pane_ai, text=self.AI_HINT,
                                    bg=th["card"], fg=th["weak"],
                                    font=f["tiny"], anchor="w", justify="left",
                                    wraplength=520)
        self.ai_hint_lbl.pack(fill="x", padx=18, pady=(2, 10))
        # 换行宽度跟着栏宽走，否则窄栏会把最后两字挤到下一行
        self.pane_ai.bind(
            "<Configure>",
            lambda e: self.ai_hint_lbl.configure(
                wraplength=max(240, e.width - 40)))
        self._sync_ai()

    # ---------------- 问 AI：状态与渲染

    def _ai_can_use(self, key: str) -> bool:
        if not (self.ready and self.result):
            return False
        if prompts.needs_birth(key) and not self.owner:
            return False
        return True

    def _ai_hover(self, key: str, on: bool) -> None:
        lbl = self.ai_chips.get(key)
        if lbl is None or not self._ai_can_use(key) or key == self.ai_feature:
            return
        try:
            lbl.configure(fg=self.th["accent"] if on else self.th["sub"])
        except tk.TclError:
            pass

    def _sync_ai(self) -> None:
        """整体可用性 + 七个 chip 的三种状态（选中／可用／禁用）。"""
        if not hasattr(self, "ai_chips"):
            return
        th, f = self.th, self.f
        ready = bool(self.ready and self.result)
        for key, lbl in self.ai_chips.items():
            can = self._ai_can_use(key)
            sel = key == self.ai_feature
            try:
                if sel and can:
                    lbl.configure(fg=th["accent"], font=f["card"],
                                  highlightbackground=th["accent"],
                                  cursor="hand2")
                elif can:
                    lbl.configure(fg=th["sub"], font=f["small"],
                                  highlightbackground=th["line"], cursor="hand2")
                else:
                    lbl.configure(fg=th["weak"], font=f["small"],
                                  highlightbackground=th["line"], cursor="arrow")
            except tk.TclError:
                pass
        self.ai_text.configure(state="normal")
        self.ai_text.delete("1.0", "end")
        if not ready:
            self.ai_text.insert("end", "先点左侧「开始分析」，这里才有话术可预览。")
            self.ai_text.configure(state="disabled")
            self.ai_len_lbl.configure(text="")
            for c in (self.ai_copy_chip, self.ai_save_chip,
                      self.ai_export_chip, self.ai_ver_chip):
                c.configure(fg=th["weak"], cursor="arrow")
            self._ai_sync_missing()
            return
        # 当前功能若因缺生辰不可用，自动退回「布局体检」
        if not self._ai_can_use(self.ai_feature):
            self.ai_feature = "check"
            self.ai_variant = 0
        text = self._ai_current_text()
        self.ai_text.insert("end", text)
        self.ai_text.configure(state="disabled")
        self.ai_len_lbl.configure(text="%d 字" % len(text))
        self.ai_ver_chip.configure(
            text="换一版 · %d/%d" % (self.ai_variant + 1, prompts.VARIANT_N))
        for c in (self.ai_copy_chip, self.ai_save_chip,
                  self.ai_export_chip, self.ai_ver_chip):
            c.configure(fg=th["sub"], cursor="hand2")
        self.ai_name_chip.configure(
            text=("☑ 含图标文件名" if self.ai_names else "☐ 含图标文件名"))
        self.ai_diag_chip.configure(
            text=("☑ 含完整诊断" if self.ai_diag else "☐ 含完整诊断"))
        self._ai_sync_missing()

    def _ai_sync_missing(self) -> None:
        """缺生辰的四套在文案后缀标明——只标一次，别越堆越长。"""
        for key, lbl in self.ai_chips.items():
            base = prompts.label(key)
            if prompts.needs_birth(key) and not self.owner:
                lbl.configure(text=base + " · 需先填生辰")
            else:
                lbl.configure(text=base)

    def _ai_pick(self, key: str) -> None:
        if not self._ai_can_use(key):
            if not (self.ready and self.result):
                self.status.configure(text="先点左侧「开始分析」。")
            else:
                self.status.configure(
                    text="「%s」需要先填生辰——去命主栏填一次即可。"
                         % prompts.label(key))
            return
        self.ai_feature = key
        self.ai_variant = 0
        self._sync_ai()

    def _ai_next_variant(self) -> None:
        if not (self.ready and self.result):
            return
        self.ai_variant = (self.ai_variant + 1) % prompts.VARIANT_N
        self._sync_ai()

    def _ai_toggle_names(self) -> None:
        self.ai_names = not self.ai_names
        self._sync_ai()

    def _ai_toggle_diag(self) -> None:
        self.ai_diag = not self.ai_diag
        self._sync_ai()

    def _ai_current_text(self) -> str:
        return prompts.compose(self.ai_feature, self.ai_variant)

    def _ai_copy(self) -> None:
        if not (self.ready and self.result):
            return
        text = self._ai_current_text()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
        except tk.TclError:
            self.status.configure(text="复制失败：剪贴板被别的程序占用。")
            return
        self.status.configure(text="已复制整篇话术（%d 字），粘进对话框就行。"
                                   % len(text))

    def _ai_save(self) -> None:
        """只落文件，不动剪贴板。"""
        self._ai_export(copy=False)

    def _ai_export(self, copy: bool = True) -> None:
        if not (self.ready and self.result):
            return
        top = self._orient_label.get(self.orient_var.get(), 180)
        try:
            md = aiexport.build(self.result, self.layout, self.owner, top,
                                self.orient_text, include_names=self.ai_names,
                                include_diag=self.ai_diag,
                                note=self.ai_note_var.get())
            path = aiexport.write(md)
        except OSError as exc:
            self.status.configure(text="导出失败：%s" % exc)
            return
        self.ai_last = path
        self.ai_path_lbl.configure(text="上次导出：%s" % self._ai_rel(path))
        if not copy:
            self.status.configure(
                text="已导出 %s（%.1f KB）——文件在 exports 里。"
                     % (self._ai_rel(path), len(md.encode("utf-8")) / 1024.0))
            return
        self._ai_copy()
        self.status.configure(
            text="已导出 %s（%.1f KB）并复制话术——把文件拖进对话框一起发。"
                 % (self._ai_rel(path), len(md.encode("utf-8")) / 1024.0))

    def _ai_rel(self, path) -> str:
        try:
            return str(path.relative_to(aiexport.ROOT))
        except ValueError:
            return str(path)

    def _ai_open_dir(self) -> None:
        target = (self.ai_last.parent if self.ai_last else aiexport.OUT_DIR)
        try:
            target.mkdir(parents=True, exist_ok=True)
            os.startfile(str(target))          # 只有用户点击才执行
        except (OSError, AttributeError) as exc:
            self.status.configure(text="打不开文件夹：%s" % exc)

    # ---------------- 问 AI：使用方法弹层

    def _ai_help(self) -> None:
        """说清这个功能干什么、三步怎么走、文件去哪了。非模态，可边看边操作。"""
        self._ai_help_close()                   # 换过主题就重开一份新的
        th, f = self.th, self.f
        win = tk.Toplevel(self.root)
        self.ai_help_win = win
        win.withdraw()
        win.title("问 AI · 使用方法")
        win.transient(self.root)
        win.configure(bg=th["card"])
        win.protocol("WM_DELETE_WINDOW", self._ai_help_close)
        win.bind("<Escape>", lambda _e: self._ai_help_close())

        pad = tk.Frame(win, bg=th["card"])
        pad.pack(fill="both", expand=True, padx=20, pady=(16, 0))

        tk.Label(pad, text="这个功能在做什么", bg=th["card"], fg=th["ink"],
                 font=f["grade"], anchor="w").pack(fill="x")
        self._help_para(
            pad, "把这次分析打包成一份纯文本文件：每个图标的名称（可选）、坐标、"
                 "所在宫位、五行判定，七项评分，以及每一条诊断的理由和改法。"
                 "AI 读了它就能直接给意见，不用你复述桌面长什么样。")

        tk.Label(pad, text="三步", bg=th["card"], fg=th["ink"],
                 font=f["card"], anchor="w").pack(fill="x", pady=(12, 2))
        self._help_lines(pad, (
            "① 上面七个里选一个",
            "② 点「复制文案」，粘进对话框",
            "③ 点「导出数据」，把生成的文件拖进同一个对话框发过去",
        ))

        tk.Label(pad, text="七套话术怎么选", bg=th["card"], fg=th["ink"],
                 font=f["card"], anchor="w").pack(fill="x", pady=(12, 4))
        grid = tk.Frame(pad, bg=th["card"])
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        for i, (key, label, need, _v) in enumerate(prompts.FEATURES):
            tk.Label(grid, text=label, bg=th["card"], fg=th["ink"],
                     font=f["small"], anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=1)
            tip = AI_USE_DESC.get(key, "") + ("（需先填生辰）" if need else "")
            tk.Label(grid, text=tip, bg=th["card"], fg=th["sub"],
                     font=f["tiny"], anchor="w", justify="left",
                     wraplength=390).grid(row=i, column=1, sticky="w", pady=1)

        tk.Label(pad, text="两个开关与文件位置", bg=th["card"], fg=th["ink"],
                 font=f["card"], anchor="w").pack(fill="x", pady=(12, 2))
        self._help_lines(pad, (
            "含图标文件名：默认关。开了会把真实文件名写进文件，"
            "AI 才能指名道姓说「把那两个微信挪走」；不放心就一直关着。",
            "含完整诊断：默认关。开了附上每条诊断的现象、理由、改法全文，"
            "文件更长，但 AI 说得更具体。",
            "导出的文件都在 exports 文件夹，点页面底部「打开文件夹」就能看到。",
        ))

        foot = tk.Frame(win, bg=th["card"])
        foot.pack(fill="x", padx=20, pady=(10, 14))
        tk.Label(foot, text="AI 是按文件里的规则推的，没真看过你的桌面，结论当参考。",
                 bg=th["card"], fg=th["weak"],
                 font=f["tiny"]).pack(side="left")
        self._chip(foot, "知道了", self._ai_help_close,
                   pad=10).pack(side="right")

        win.update_idletasks()
        w = 580
        h = min(720, max(360, win.winfo_reqheight()))
        if self.root.winfo_viewable():
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            win.geometry("%dx%d+%d+%d" % (w, h, rx + max(0, (rw - w) // 2),
                                          ry + max(0, (rh - h) // 3)))
            win.deiconify()
            win.lift()
            win.wait_visibility()
            win.focus_force()

    def _help_para(self, parent, text: str) -> None:
        """弹层里的一段说明：小字、左对齐、按栏宽折行。"""
        tk.Label(parent, text=text, bg=self.th["card"], fg=self.th["sub"],
                 font=self.f["small"], anchor="w", justify="left",
                 wraplength=520).pack(fill="x", pady=(2, 0))

    def _help_lines(self, parent, lines) -> None:
        """逐条一行一条 Label。

        仿宋的行高只有 12px（雅黑 17），把三条塞进一个 Label 的多行里会挤成一团，
        拆开各自带 pady 才看得出是三条。
        """
        for ln in lines:
            tk.Label(parent, text=ln, bg=self.th["card"], fg=self.th["sub"],
                     font=self.f["small"], anchor="w", justify="left",
                     wraplength=520).pack(fill="x", pady=(2, 0))

    def _ai_help_close(self) -> None:
        win = getattr(self, "ai_help_win", None)
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass
            self.ai_help_win = None

    # ------------------------------------------------------------ 移动清单

    def _cell_label(self, rc) -> str:
        """(row,col) → 「坎宫 北」；中宫单独说。"""
        try:
            r, c = rc
        except (TypeError, ValueError):
            return "—"
        if (r, c) == (1, 1):
            return "中宫"
        info = palace.palace_grid(self.top_dir)[r][c]
        return "%s宫 %s" % (info["gua"], info["dir"]) if info else "—"

    def _sync_moves(self) -> None:
        """「移动清单 N」只在推演档且确实有移动时出现。"""
        chip = getattr(self, "move_chip", None)
        if chip is None:
            return
        try:
            moves = self._scene()[2] if (self.ready and self.mode != "now") else []
            if moves:
                chip.configure(text="移动清单 · %d" % len(moves))
                chip.pack(side="right", padx=(12, 0))
            else:
                chip.pack_forget()
        except tk.TclError:
            pass
        self._fit_mode_lbl()

    def _open_moves(self) -> None:
        """当前档位的移动清单弹窗：图标 / 从 / 到 / 缘由。非模态，可对着盘看。"""
        moves = self._scene()[2] if self.ready else []
        if not moves:
            self.status.configure(text="当前档位没有移动，或还没分析。")
            return
        self._moves_close()                 # 重开即换一份新的
        th, f = self.th, self.f
        win = tk.Toplevel(self.root)
        self.moves_win = win
        win.withdraw()
        win.title("移动清单 · %d 个" % len(moves))
        win.transient(self.root)
        win.configure(bg=th["card"])
        win.protocol("WM_DELETE_WINDOW", self._moves_close)
        win.bind("<Escape>", lambda _e: self._moves_close())

        head = tk.Frame(win, bg=th["card"])
        head.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(head, text="照着挪就行：从右列拖到目标位置即可，程序不会动你的桌面。",
                 bg=th["card"], fg=th["sub"], font=f["tiny"],
                 justify="left", wraplength=520).pack(anchor="w")

        mid = tk.Frame(win, bg=th["card"])
        mid.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        cols = ("name", "src", "dst", "why")
        self.moves_tree = ttk.Treeview(mid, columns=cols, show="headings",
                                       selectmode="browse")
        for cid, text, w, anchor in (("name", "图标", 250, "w"),
                                     ("src", "从", 110, "center"),
                                     ("dst", "到", 110, "center"),
                                     ("why", "缘由", 90, "center")):
            self.moves_tree.heading(cid, text=text)
            self.moves_tree.column(cid, width=w, anchor=anchor, stretch=True)
        sb = ttk.Scrollbar(mid, orient="vertical",
                           command=self.moves_tree.yview)
        self.moves_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.moves_tree.pack(side="left", fill="both", expand=True)
        for mv in moves:
            self.moves_tree.insert("", "end", values=(
                mv["name"], self._cell_label(mv["from"]),
                self._cell_label(mv["to"]), mv.get("why", "")))

        foot = tk.Frame(win, bg=th["card"])
        foot.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(foot, text="共 %d 个 · 本清单只是建议" % len(moves),
                 bg=th["card"], fg=th["weak"], font=f["tiny"]).pack(side="left")
        self._chip(foot, "关闭", self._moves_close, pad=10).pack(side="right")

        if self.root.winfo_viewable():
            win.update_idletasks()
            w, h = 620, 560
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            win.geometry("%dx%d+%d+%d" % (w, h, rx + max(0, (rw - w) // 2),
                                          ry + max(0, (rh - h) // 3)))
            win.deiconify()
            win.lift()
            win.wait_visibility()
            win.focus_force()

    def _moves_close(self) -> None:
        win = getattr(self, "moves_win", None)
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass
            self.moves_win = None

    def _sync_ready(self) -> None:
        """导出类按钮跟着闸门走。ttk 的启用态用 state 标志，不是 configure。"""
        flags = ["!disabled"] if self.ready else ["disabled"]
        for btn in (getattr(self, "btn_export", None),
                    getattr(self, "btn_export_ai", None)):
            if btn is None:
                continue
            try:
                btn.state(flags)
            except tk.TclError:
                pass
        chip = getattr(self, "re_chip", None)
        if chip is not None:
            try:
                if self._analyzed_once:
                    chip.pack(side="right", padx=(12, 0))
                else:
                    chip.pack_forget()
            except tk.TclError:
                pass
            self._fit_mode_lbl()        # chip 占位变了，说明块要重新折行

    def _analyze(self) -> None:
        if not self.layout:
            self.result = None
            self._refresh_right()
            return
        top = self._orient_label.get(self.orient_var.get(), 180)
        self.top_dir = top
        self.result = fengshui.analyze(self.layout, top)
        self._refresh_right()

    def _wenchang_gua(self) -> str:
        """文昌落点：填了生辰用本命文昌；没填用巽宫（文昌总位）。"""
        return self.owner["wenchang_gua"] if self.owner else "巽"

    def _caiku_gua(self) -> str:
        """财库落点：填了生辰用生气位（生气主财源）；没填用乾宫。"""
        return self.owner["good"][0][1] if self.owner else "乾"

    def set_mode(self, mode: str) -> None:
        if not self.result or not self.layout:
            return
        if mode == "proj" and self.proj_result is None:
            self.proj_layout, self.moves = project.project(self.layout,
                                                           self.top_dir)
            self.proj_result = fengshui.analyze(self.proj_layout, self.top_dir)
        if mode == "repack" and self.rep_result is None:
            self.rep_layout, self.rep_moves = project.repack(self.layout,
                                                             self.top_dir)
            self.rep_result = fengshui.analyze(self.rep_layout, self.top_dir)
        if mode == "wenchang" and self.wc_result is None:
            self.wc_layout, self.wc_moves = project.focus(
                self.layout, self.top_dir, self._wenchang_gua(),
                classify.is_doc, "归入文昌位")
            self.wc_result = fengshui.analyze(self.wc_layout, self.top_dir)
        if mode == "caiku" and self.ck_result is None:
            self.ck_layout, self.ck_moves = project.focus(
                self.layout, self.top_dir, self._caiku_gua(),
                classify.is_tool, "归入财库")
            self.ck_result = fengshui.analyze(self.ck_layout, self.top_dir)
        self.mode = mode
        self._sync_seg()
        self._sync_moves()
        self._update_mode_text()
        self._refresh_right()
        self._animate_reveal()

    def _update_mode_text(self) -> None:
        if not self.ready or not self.result:
            self.mode_lbl.configure(
                text="尚未分析：点盘中央的「开始分析」读取桌面。"
                     "只读，不移动、不重命名任何图标，也不上传。")
            return
        now = self.result["score"]
        if self.mode == "proj" and self.proj_result:
            t = ("最小调整（可照着做）：只挪明堂溢出与中宫里的图标，其余一动不动，"
                 "挪完就是这张盘。移 %d 个 → %d 分（+%d）。"
                 % (len(self.moves), self.proj_result["score"],
                    self.proj_result["score"] - now))
        elif self.mode == "repack" and self.rep_result:
            t = ("全部重排（只看效果）：把 %d 个图标按「外实内虚」重新摆一遍，"
                 "四周贴边、中间留空。%d → %d 分。真要这样，得手动挪几十次。"
                 % (self.result["stats"]["total"], now, self.rep_result["score"]))
        elif self.mode == "wenchang" and self.wc_result:
            gua = self._wenchang_gua()
            where = ("本命文昌位 %s宫（%s）" % (gua, mingua.GUA_DIR[gua])
                     if self.owner else
                     "巽宫（东南）——巽为文昌总位，填了生辰会换成本命的")
            t = ("优先文昌（可照着做）：把文书、笔记、学习类集中到%s。"
                 "移 %d 个 → %d 分（%+d）；比「最小调整」动得多，这是代价。"
                 "点「移动清单」看具体挪哪些。"
                 % (where, len(self.wc_moves), self.wc_result["score"],
                    self.wc_result["score"] - now))
            if project._find_gua(palace.palace_grid(self.top_dir), gua) == (0, 1):
                t += "（文昌位正落明堂，这一格最多留 4 个，其余不动。）"
        elif self.mode == "caiku" and self.ck_result:
            gua = self._caiku_gua()
            where = ("生气位 %s宫（%s）——生气主财源" % (gua, mingua.GUA_DIR[gua])
                     if self.owner else
                     "乾宫（西北）——乾为财库，填了生辰会换成本命生气位")
            t = ("优先财库（可照着做）：把工具、管理、生产力类集中到%s。"
                 "移 %d 个 → %d 分（%+d）；比「最小调整」动得多，这是代价。"
                 "点「移动清单」看具体挪哪些。"
                 % (where, len(self.ck_moves), self.ck_result["score"],
                    self.ck_result["score"] - now))
        else:
            t = ("现状：你桌面的真实样子，按实际坐标绘制。只读，不改动任何东西。"
                 "满分 100，当前 %d 分。" % now)
        self.mode_lbl.configure(text=t)

    def export_ai(self) -> None:
        """顶栏「导出给 AI」：直接按当前选项导出并复制话术，同时切到问 AI 栏。"""
        self._top("ai")
        if not (self.ready and self.result):
            self.status.configure(text="先点左侧「开始分析」，再导出给 AI。")
            return
        self._ai_export()

    def export(self) -> None:
        if not self.ready or not self.result or not self.layout:
            self.status.configure(text="没有可导出的结果")
            return
        try:
            path = report.export(self.layout, self.result, self.prev,
                                 font=self.report_font,
                                 scale=theme.step_scale(self.report_size))
        except OSError as exc:
            self.status.configure(text="导出失败：%s" % exc)
            return
        self.status.configure(text="已导出：%s" % path)
        try:
            os.startfile(str(path))          # noqa: S606 用户主动点击才打开
        except OSError:
            pass

    # ------------------------------------------------------------ 右栏

    def _refresh_right(self) -> None:
        self._fill_prose()
        _lay, res, _moves = self._scene()
        if not res or not self.ready:
            # 未分析（或读取失败）的空状态：分数破折号、六条空槽、一张提示卡
            self._bump("score")
            self._score_shown = 0
            self.score_lbl.configure(text="—", font=self.f["score"],
                                     fg=self.th["ink"])
            self.grade_lbl.configure(
                text="尚未分析" if not self.ready else "", fg=self.th["weak"])
            self.summary_lbl.configure(
                text=(self.error if self.error else
                      "点左侧「开始分析」读取桌面图标位置。只读，不移动、"
                      "不重命名任何东西，也不上传。"))
            self.ledger.configure(text="")
            self.prev_lbl.configure(
                text=("上次 %s 分 · %s" % (self.prev.get("score", 0),
                                          _fmt_time(self.prev.get("t", "")))
                      if self.prev else ""))
            self._draw_bars(0.0)
            for w in self.cards.winfo_children():
                w.destroy()
            self._empty_cards()
            return
        # 按最终分数的位数定好分数区宽度：滚动动画期间数字在变（0→81），
        # 宽度不能跟着变，否则评级会左右跳。等宽放在这里调一次。
        try:
            _fn = tkfont.Font(root=self.root, font=self.f["score"])
            _sample = ("100" if res["score"] >= 100
                       else ("88" if res["score"] >= 10 else "8"))
            self.scbox.configure(width=_fn.measure(_sample) + 8)
            self.root.tk.call("font", "delete", _fn.name)
        except (tk.TclError, AttributeError):
            pass
        self._set_score(res["score"])
        self.grade_lbl.configure(text=res["grade"],
                                 fg=self.th["grade"].get(
                                     "high" if res["score"] >= 80 else
                                     ("mid" if res["score"] >= 60 else "low"),
                                     self.th["sub"]))
        self.summary_lbl.configure(text=res["summary"])
        self.ledger.configure(text="对账：100 − 扣分 %.1f = %d"
                                   % (res["deduct_total"], res["score"]))
        if self.mode == "now":
            if self.prev:
                diff = res["score"] - int(self.prev.get("score", res["score"]))
                sign = (("＋%d" % diff) if diff > 0
                        else (str(diff) if diff < 0 else "持平"))
                self.prev_lbl.configure(
                    text="上次 %d 分（%s）· %s"
                         % (self.prev.get("score", 0), sign,
                            str(self.prev.get("t", "")).replace("T", " ")[:16]))
            else:
                self.prev_lbl.configure(text="首次记录")
        else:
            self.prev_lbl.configure(text="推演为虚拟计算，不写入历史")
        self._animate_bars()
        self._fill_cards(res)
        self._picon_groups = []      # 结果变了，分图标页下次打开时重建
        if self.top_tab == "hist":
            self._fill_history()

    def _empty_cards(self) -> None:
        """未分析时「断语」栏里的占位卡片。"""
        th, f = self.th, self.f
        card = tk.Frame(self.cards, bg=th["card"])
        card.pack(fill="x")
        tk.Frame(card, bg=th["line"], width=2).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=th["card"])
        inner.pack(side="left", fill="both", expand=True,
                   padx=(11, 10), pady=(9, 10))
        tk.Label(inner, text="还没有诊断", bg=th["card"], fg=th["ink"],
                 font=f["card"], anchor="w").pack(fill="x")
        tk.Label(inner,
                 text="分析之后，这里会出现逐条诊断：现象 → 理 → 改。"
                      "每条都带具体的图标名与目标宫位。",
                 bg=th["card"], fg=th["sub"], font=f["tiny"], anchor="w",
                 justify="left", wraplength=330).pack(fill="x", pady=(4, 0))

    def _set_score(self, target: int) -> None:
        """分数滚动（650ms，缓出）。滚完轻微放大一下，像落定的数字。"""
        tok = self._bump("score")
        start = self._score_shown
        if not self._can_anim() or start == target:
            self._score_shown = target
            self.score_lbl.configure(text=str(target), fg=self.th["ink"])
            return
        steps = _frames(650)

        def step(i: int) -> None:
            if self._tok.get("score") != tok:
                return
            p = _ease_out(i / steps)
            v = int(round(start + (target - start) * p))
            self._score_shown = v
            ch = min(1.0, p * 1.6)
            self.score_lbl.configure(
                text=str(v), fg=self._fade_in(self.th["ink"], ch, self.th["accent"]))
            if i < steps:
                self.root.after(16, step, i + 1)
            else:
                # 落定时只把颜色定住，**不做字号脉冲**。
                # 原来这里从 90% 缩到 100%（改字号模拟缩放），但 Tk 里改字号是
                # 一步跳到 36 号再长回 40 号——滚动刚一结束数字就猛缩一下，
                # 看着像卡顿（2026-10-27 用户报）。Tk 没有 transform 能力，
                # 「轻微放大」这个效果本质上做不干净，索性去掉：
                # 滚动过程本身就是从淡色到浓色，落定感已经够了。
                self._score_shown = target
                self.score_lbl.configure(text=str(target), fg=self.th["ink"])

        step(1)

    def _animate_bars(self) -> None:
        tok = self._bump("bars")
        if not self._can_anim():
            self._draw_bars(1.0)
            return
        steps = _frames(780)

        def step(i: int) -> None:
            if self._tok.get("bars") != tok:
                return
            self._draw_bars(_ease_out(i / steps))
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    def _draw_bars(self, progress: float = 1.0) -> None:
        c = self.bars
        c.delete("all")
        _lay, res, _mv = self._scene()
        fs = self._fs()
        row_h = max(15, int(19 * fs))
        rows = len(res["sections"]) if (res and self.ready) else len(EMPTY_SECTIONS)
        c.configure(height=row_h * rows + 6)
        w = max(260, c.winfo_width())
        y = 3
        if res and self.ready:
            sections = list(res["sections"].values())
        else:
            sections = [{"name": n, "score": 0, "max": m}
                        for n, m in EMPTY_SECTIONS]
        for i, s in enumerate(sections):
            ratio = s["score"] / s["max"] if s["max"] else 0
            p = _clamp01((progress - i * 0.08) / 0.6)
            c.create_text(0, y, text=s["name"], anchor="nw", fill=self.th["sub"],
                          font=self.f["tiny"])
            bx = 42
            bw = max(40, w - 132)
            c.create_rectangle(bx, y + 2, bx + bw, y + 8,
                               fill=self.th["track"], outline="")
            color = (self.th["grade"]["high"] if ratio >= 0.8
                     else (self.th["grade"]["mid"] if ratio >= 0.5
                           else self.th["grade"]["low"]))
            if p > 0:
                c.create_rectangle(bx, y + 2, bx + max(2, bw * ratio * p),
                                   y + 8, fill=color, outline="")
            c.create_text(w, y,
                          text=("%g/%g" % (s["score"], s["max"])
                                if (res and self.ready) else "—/%g" % s["max"]),
                          anchor="ne", fill=self.th["weak"],
                          font=self.f["tip"])
            y += row_h

    def _on_cards_configure(self, _e) -> None:
        """内容不足一屏时显式清空 scrollregion——保证滚动条禁用、滚轮无效。
        （未分析时只有一张提示卡，之前 region 仍被设成内容高度，
        在窗口矮或 DPI 变化的时序下会出现"空内容也能向上滑"。）"""
        content = self.cards.winfo_reqheight()
        if content <= max(1, self.scroll.winfo_height()):
            self.scroll.configure(scrollregion="")
            return
        self.scroll.configure(scrollregion=self.scroll.bbox("all"))

    def _on_wheel(self, event) -> None:
        if self.top_tab == "owner":
            target = self.owner_scroll
        elif self.sub_tab == "pericon" and self.top_tab == "judge":
            target = self.picon_scroll
        elif self.top_tab == "ai" or self.sub_tab == "prose":
            target = self.prose_text if self.sub_tab == "prose" else self.hist_scroll
        elif self.top_tab == "hist":
            target = self.hist_scroll
        else:
            target = self.scroll
        move = -event.delta / 120.0      # 视口移动量：向上滚为负
        # 边界钳制：内容不足一屏或在顶/底时不再发送，
        # 杜绝"没多少内容还能上下滑"的空滚。
        first, last = target.yview()
        if (move < 0 and first <= 0.0) or (move > 0 and last >= 1.0):
            return
        target.yview_scroll(int(move), "units")

    def _prose_fit(self, event=None) -> None:
        """总评内容限宽：面板比 PROSE_MAX_W+48 还宽时，左侧对称补留白。

        宽度优先取 <Configure> 事件（已映射时准确），否则取 winfo_width
        （withdraw/未映射时为 1，自然回落到 24px 基础留白）。
        """
        try:
            w = event.width if event is not None else self.pane_prose.winfo_width()
            # 左右必须对称：原来只给左边补 (w-48-MAX)/2、右边留 24，
            # 结果内容块被推到右边、贴着右边缘（2026-10-27 用户报）。
            pad = 24 + max(0, (w - 48 - PROSE_MAX_W) // 2)
            self.prose_body.pack_configure(padx=(pad, pad), pady=18)
        except (tk.TclError, AttributeError):
            pass

    # 总评按段角色排版：首段领起（首字下沉）→ 中段正文 → 收束。

    def _fill_prose(self) -> None:
        t = self.prose_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        if self.result and self.ready:
            paras = [p.strip() for p in prose.compose(self.result) if p.strip()]
            n = sum(len(p) for p in paras)
            sc = self.result["score"]
            self.prose_score.configure(text=str(sc))
            self.prose_grade.configure(
                text=self.result["grade"],
                fg=self.th["grade"]["high" if sc >= 85 else
                                  ("mid" if sc >= 60 else "low")])
            self.prose_line.configure(text=self.result.get("summary", ""))
            self.prose_strip.pack(fill="x", pady=(12, 0))
            if paras:
                # 首字下沉：只放大第一个字，仍是同一段文章，不改结构
                t.insert("end", paras[0][0], ("cap",))
                t.insert("end", paras[0][1:] + "\n", ("lead",))
                for p in paras[1:-1]:
                    t.insert("end", p + "\n", ("body",))
                if len(paras) > 1:
                    t.insert("end", "·   ·   ·\n", ("dot",))
                    t.insert("end", paras[-1], ("close",))
            self.prose_meta.configure(text="约 %d 字 · 由本次分析生成" % n)
        else:
            self.prose_meta.configure(text="")
            self.prose_strip.pack_forget()
            t.insert("end", "分析之后，这里是一篇整体的总评：六段，约一千字，"
                            "把这张盘的格局、问题与改法连成一段话讲完。\n",
                     ("lead",))
            t.insert("end", "先点左侧「开始分析」。", ("body",))
        t.configure(state="disabled")

    # ------------------------------------------------------------ 选项卡

    def _top(self, name: str) -> None:
        """一级选项卡：断语 / 命主 / 问 AI / 历史。"""
        self.top_tab = name
        panes = {"judge": self.pane_judge, "owner": self.pane_owner,
                 "ai": self.pane_ai, "hist": self.pane_hist}
        for pane in panes.values():
            pane.pack_forget()
        panes[name].pack(fill="both", expand=True)
        for key, lbl in self.top_labels.items():
            active = key == name
            lbl.configure(fg=self.th["accent"] if active else self.th["weak"],
                          font=self.f["grade"] if active else self.f["small"])
        if name == "hist":
            self._fill_history()
            self._snap_refresh()
        elif name == "owner" and hasattr(self, "owner_body"):
            self._fill_owner()
        elif name == "ai":
            self._sync_ai()
        self._move_topline(True)

    def _tab(self, name: str) -> None:
        """断语栏内的二级页签：分条 / 分图标 / 总评。"""
        self.sub_tab = name
        panes = {"cards": self.pane_cards, "pericon": self.pane_pericon,
                 "prose": self.pane_prose}
        for pane in panes.values():
            pane.pack_forget()
        panes.get(name, self.pane_cards).pack(fill="both", expand=True)
        for key, lbl in (("cards", self.tab_cards),
                         ("pericon", self.tab_pericon),
                         ("prose", self.tab_prose)):
            active = key == name
            lbl.configure(fg=self.th["accent"] if active else self.th["weak"],
                          font=self.f["card"] if active else self.f["small"])
        if name == "pericon":
            self._fill_pericon()
        if self.top_tab != "judge":
            self._top("judge")

    def _placeholder(self, parent, title: str, desc: str, tag: str) -> None:
        """还没实现的栏：说清这里将来放什么。"""
        th, f = self.th, self.f
        wrap = tk.Frame(parent, bg=th["card"])
        wrap.place(relx=0.5, rely=0.42, anchor="center")
        tk.Label(wrap, text=title, bg=th["card"], fg=th["ink"],
                 font=f["grade"]).pack(pady=(0, 6))
        tk.Label(wrap, text=desc, bg=th["card"], fg=th["sub"], font=f["small"],
                 wraplength=360, justify="left").pack()
        chip = tk.Label(wrap, text=tag, bg=th["card"], fg=th["accent"],
                        font=f["tiny"], padx=8, pady=1,
                        highlightthickness=1,
                        highlightbackground=th["line"])
        chip.pack(pady=(10, 0))

    # ------------------------------------------------------------ 齿轮与设置

    def _draw_gear(self, active: bool = False) -> None:
        """Canvas 画一个齿轮：外圈 + 内圈 + 八根齿线。不依赖字体图标。"""
        import math
        th = self.th
        c = self.gear
        col = th["accent"] if active else th["weak"]
        c.delete("all")
        cx = cy = 14.0
        c.create_oval(cx - 7.6, cy - 7.6, cx + 7.6, cy + 7.6,
                      outline=col, width=1.4)
        c.create_oval(cx - 3.2, cy - 3.2, cx + 3.2, cy + 3.2,
                      outline=col, width=1.4)
        for i in range(8):
            a = math.radians(i * 45)
            c.create_line(cx + math.cos(a) * 8.4, cy + math.sin(a) * 8.4,
                          cx + math.cos(a) * 11.2, cy + math.sin(a) * 11.2,
                          fill=col, width=1.6)

    def _build_settings_panel(self) -> None:
        th, f = self.th, self.f
        rw = getattr(self, "rule_win", None)          # 编辑器弹窗一并重建
        if rw is not None:
            try:
                rw.destroy()
            except tk.TclError:
                pass
            self.rule_win = None
        if getattr(self, "settings_panel", None) is not None:
            try:
                self.settings_panel.destroy()
            except tk.TclError:
                pass
        # Windows 原生弹窗：系统边框由 OS 画，不需要自制阴影与描边。
        # 构造后立即 withdraw，open_settings 才 deiconify（测试环境不弹真窗口）。
        panel = tk.Toplevel(self.root)
        panel.withdraw()
        panel.title("设置")
        panel.transient(self.root)
        panel.resizable(False, False)
        panel.configure(bg=th["card"])
        panel.protocol("WM_DELETE_WINDOW", self.close_settings)
        panel.bind("<Escape>", lambda _e: self.close_settings())
        self.settings_panel = panel
        pad = tk.Frame(panel, bg=th["card"])
        pad.pack(fill="both", expand=True, padx=16, pady=(12, 12))

        # 标签列按**像素**定宽。不能用 width=5：那是按「字符平均宽」算的，
        # 一个汉字远宽于平均值，四字标签（盘上标记）会被裁掉末字、紧贴右侧控件，
        # 看起来像被那个方块压住了（2026-10-25 用户反馈，截图确认）。
        _fw = tkfont.Font(family=f["small"][0], size=f["small"][1])
        lab_w = max(_fw.measure(t) for t in ("主题", "字体", "字号", "动效", "盘上标记",
                           "报告字体", "报告字号")) + 8
        lab_h = _fw.metrics("linespace") + 2

        def row_label(row, text: str) -> None:
            box = tk.Frame(row, bg=th["card"], width=lab_w, height=lab_h)
            box.pack(side="left")
            box.pack_propagate(False)
            tk.Label(box, text=text, bg=th["card"], fg=th["sub"],
                     anchor="w", font=f["small"]).pack(fill="both",
                                                       expand=True)

        tk.Label(pad, text="设置", bg=th["card"], fg=th["accent"],
                 font=f["grade"]).pack(anchor="w")
        tk.Label(pad, text="外观", bg=th["card"], fg=th["sub"],
                 font=f["tiny"]).pack(anchor="w", pady=(10, 4))

        r1 = tk.Frame(pad, bg=th["card"])
        r1.pack(fill="x", pady=2)
        row_label(r1, "主题")
        self.theme_var = tk.StringVar(value=theme.label_of(self.theme_name))
        tbox = ttk.Combobox(r1, textvariable=self.theme_var, state="readonly",
                            values=[theme.get(k)["label"] for k in theme.ORDER],
                            width=8, font=f["small"])
        tbox.pack(side="left")
        tbox.bind("<<ComboboxSelected>>",
                  lambda _e: self.set_theme(theme.by_label(self.theme_var.get())))

        r1b = tk.Frame(pad, bg=th["card"])
        r1b.pack(fill="x", pady=2)
        row_label(r1b, "字体")
        self.ff_var = tk.StringVar(value=theme.body_label(self.font_family))
        fbox = ttk.Combobox(r1b, textvariable=self.ff_var, state="readonly",
                            values=[lab for lab, _f, _t in theme.BODY_CHOICES],
                            width=12, font=f["small"])
        fbox.pack(side="left")
        fbox.bind("<<ComboboxSelected>>",
                  lambda _e: self.set_font_family(
                      theme.body_family(self.ff_var.get())))
        # 选之前先知道这个字体的小字表现（9pt 有没有点阵）
        tk.Label(r1b, text=theme.body_tip(self.font_family), bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left", padx=(8, 0))

        r2 = tk.Frame(pad, bg=th["card"])
        r2.pack(fill="x", pady=2)
        row_label(r2, "字号")
        self._chip(r2, "A−", lambda: self.bump_font(-1), pad=6).pack(side="left")
        self.font_lbl = tk.Label(r2, text=theme.step_label(self.fs_i),
                                 bg=th["card"], fg=th["ink"],
                                 font=f["small"], width=4)
        self.font_lbl.pack(side="left")
        self._chip(r2, "A＋", lambda: self.bump_font(1), pad=6).pack(side="left")

        r3 = tk.Frame(pad, bg=th["card"])
        r3.pack(fill="x", pady=2)
        row_label(r3, "动效")
        self.anim_chip = self._chip(
            r3, "动效 · 开" if self.anim_on else "动效 · 关", self.toggle_anim)
        self.anim_chip.pack(side="left")

        r4 = tk.Frame(pad, bg=th["card"])
        r4.pack(fill="x", pady=2)
        row_label(r4, "盘上标记")
        self.marks_chip = self._chip(
            r4, "四吉四凶 · 开" if self.marks_on else "四吉四凶 · 关",
            self.toggle_marks)
        self.marks_chip.pack(side="left")
        tk.Label(r4, text="填了生辰才显示", bg=th["card"], fg=th["weak"],
                 font=f["tiny"]).pack(side="left", padx=(8, 0))

        # --- 导出报告：单独一套字体与字号，只影响导出的 HTML
        tk.Frame(pad, bg=th["line"], height=1).pack(fill="x", pady=(12, 0))
        tk.Label(pad, text="导出报告", bg=th["card"], fg=th["sub"],
                 font=f["tiny"]).pack(anchor="w", pady=(6, 2))

        r5 = tk.Frame(pad, bg=th["card"])
        r5.pack(fill="x", pady=2)
        row_label(r5, "报告字体")
        self.rf_var = tk.StringVar(value=theme.body_label(self.report_font))
        rbox = ttk.Combobox(r5, textvariable=self.rf_var, state="readonly",
                            values=[lab for lab, _f2, _t2 in theme.BODY_CHOICES],
                            width=12, font=f["small"])
        rbox.pack(side="left")
        rbox.bind("<<ComboboxSelected>>",
                  lambda _e: self.set_report_font(
                      theme.body_family(self.rf_var.get())))
        tk.Label(r5, text="浏览器里看，和界面字体分开设", bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left", padx=(8, 0))

        r6 = tk.Frame(pad, bg=th["card"])
        r6.pack(fill="x", pady=2)
        row_label(r6, "报告字号")
        self.rs_var = tk.StringVar(value=theme.step_label(self.report_size))
        sbox = ttk.Combobox(r6, textvariable=self.rs_var, state="readonly",
                            values=[lab for lab, _m in theme.FONT_STEPS],
                            width=6, font=f["small"])
        sbox.pack(side="left")
        sbox.bind("<<ComboboxSelected>>",
                  lambda _e: self.set_report_size(self.rs_var.get()))
        tk.Label(r6, text="整页等比缩放，改完下次导出生效", bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left", padx=(8, 0))

        # --- 五行对应表：入口在设置，编辑器独立弹窗（可搜索全部内置+覆盖）
        rrow = tk.Frame(pad, bg=th["card"])
        rrow.pack(fill="x", pady=(16, 0))
        tk.Label(rrow, text="五行对应表", bg=th["card"], fg=th["sub"],
                 font=f["small"], anchor="w").pack(side="left")
        tk.Label(rrow, text="内置与覆盖一览，可搜索、改、增、删",
                 bg=th["card"], fg=th["weak"], font=f["tiny"]).pack(
            side="left", padx=(10, 0))
        self._chip(rrow, "编辑对应表…", self._rule_editor_open,
                   pad=10).pack(side="right")

        foot = tk.Frame(pad, bg=th["card"])
        foot.pack(side="bottom", fill="x", pady=(14, 0))
        self._chip(foot, "关闭", self.close_settings, pad=12).pack(side="right")
        tk.Label(foot, text="纯本地读取 · 不上传", bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left")

    def toggle_settings(self) -> None:
        if self._gear_open:
            self.close_settings()
        else:
            self.open_settings()

    def open_settings(self) -> None:
        if self._gear_open:
            return
        p = self.settings_panel
        if not self.root.winfo_viewable():
            # 主窗口不可见（冒烟测试 withdraw）：只记账，不弹真窗口，
            # 否则测试会在用户屏幕上弹出设置窗——这是红线。
            self._gear_open = True
            self._draw_gear(True)
            return
        self._gear_open = True
        self._draw_gear(True)
        try:
            p.update_idletasks()
            w = max(420, p.winfo_reqwidth())
            h = p.winfo_reqheight()
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            x = rx + max(0, (rw - w) // 2)
            y = ry + max(0, (rh - h) // 3)
            p.geometry("%dx%d+%d+%d" % (w, h, x, y))
            p.deiconify()
            p.lift()                     # Toplevel 不会自动盖过主窗，必须显式抬
            p.wait_visibility()          # deiconify 是异步的：grab 前必须等映射完成
            p.grab_set()                 # 窗口可见后 grab 才合法，否则报 grab failed
            p.focus_force()              # focus_set 对新映射窗口可能不生效
        except tk.TclError:
            # 任何一步失败都必须回滚，绝不能留下"状态开着、窗口不见、grab 悬空"
            # 的组合——那正是主窗假死的原因。
            self._gear_open = False
            self._draw_gear(False)
            try:
                p.grab_release()
                p.withdraw()
            except tk.TclError:
                pass

    def close_settings(self) -> None:
        # 不看 _gear_open 也能安全调：必须无条件松 grab，防悬空模态假死
        p = getattr(self, "settings_panel", None)
        if p is not None:
            try:
                p.grab_release()
                p.withdraw()
            except tk.TclError:
                pass
        self._gear_open = False
        self._draw_gear(False)

    # ------------------------------------------------------------ 五行对应表编辑器（阶段 9）

    RULE_TABLE_LABEL = {"software": "软件名", "keyword": "关键词", "ext": "扩展名"}

    def _rule_rows_all(self) -> list[dict]:
        """合并内置三张表与用户覆盖，供编辑器列表展示。

        返回 [{table, key, wuxing, user}]，键唯一（同表同键以覆盖为准）。
        """
        merged: dict[tuple[str, str], dict] = {}
        for wx, words in software.SOFTWARE.items():
            for w in words:
                merged[("software", w)] = {
                    "table": "software", "key": w, "wuxing": wx,
                    "user": False}
        for words, wx, _why in classify.SEMANTIC:
            for w in words:
                merged.setdefault(("keyword", w), {
                    "table": "keyword", "key": w, "wuxing": wx,
                    "user": False})
        for e, wx in classify.EXT_WUXING.items():
            merged.setdefault(("ext", e), {
                "table": "ext", "key": e, "wuxing": wx, "user": False})
        for table, kv in rules.load().items():
            for k, wx in kv.items():
                merged[(table, k)] = {
                    "table": table, "key": k, "wuxing": wx, "user": True}
        out = sorted(merged.values(),
                     key=lambda r: (not r["user"], r["table"], r["key"].lower()))
        return out

    # -- 对话框栈：设置与编辑器共用一份应用模态 grab，谁在最前谁持有。
    #    否则设置弹窗的 grab 会劫持全部输入，编辑器弹了也点不到（2026-10-24 实测）。

    def _release_settings_grab(self) -> None:
        if self._gear_open and self.root.winfo_viewable():
            try:
                self.settings_panel.grab_release()
            except tk.TclError:
                pass

    def _regrab_settings(self) -> None:
        """编辑器关闭后，若设置弹窗还开着，把 grab 还给它。"""
        if self._gear_open and self.root.winfo_viewable():
            try:
                self.settings_panel.wait_visibility()
                self.settings_panel.grab_set()
            except tk.TclError:
                pass

    def _rule_editor_open(self) -> None:
        """独立编辑器弹窗：顶部搜索，下方全部对应，可改/增/删。"""
        if getattr(self, "rule_win", None) is not None:
            self._rule_win_show()
            return
        th, f = self.th, self.f
        win = tk.Toplevel(self.root)
        self.rule_win = win
        win.withdraw()
        win.title("五行对应表")
        win.transient(self.root)
        win.configure(bg=th["card"])
        win.protocol("WM_DELETE_WINDOW", self._rule_editor_close)
        win.bind("<Escape>", lambda _e: self._rule_editor_close())

        top = tk.Frame(win, bg=th["card"])
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="搜索", bg=th["card"], fg=th["sub"],
                 font=f["small"]).pack(side="left")
        self.rule_search_var = tk.StringVar()
        ent = tk.Entry(top, textvariable=self.rule_search_var, bg=th["card"],
                       fg=th["ink"], font=f["small"], highlightthickness=1,
                       highlightbackground=th["line"],
                       highlightcolor=th["accent"],
                       insertbackground=th["ink"])
        ent.pack(side="left", fill="x", expand=True, padx=(8, 10), ipady=2)
        self.rule_search_var.trace_add("write", lambda *_: self._rule_fill())
        self.rule_total_lbl = tk.Label(top, text="", bg=th["card"],
                                       fg=th["weak"], font=f["tiny"])
        self.rule_total_lbl.pack(side="right")

        mid = tk.Frame(win, bg=th["card"])
        mid.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        cols = ("key", "wx", "table", "src")
        self.rule_tree = ttk.Treeview(
            mid, columns=cols, show="headings", selectmode="browse")
        for cid, text, w, anchor in (
                ("key", "名称 / 关键词 / 扩展名", 300, "w"),
                ("wx", "五行", 52, "center"),
                ("table", "类别", 70, "center"),
                ("src", "来源", 70, "center")):
            self.rule_tree.heading(cid, text=text)
            self.rule_tree.column(cid, width=w, anchor=anchor, stretch=True)
        self.rule_tree.tag_configure("user", foreground=th["accent"])
        tsbar = ttk.Scrollbar(mid, orient="vertical",
                              command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=tsbar.set)
        tsbar.pack(side="right", fill="y")
        self.rule_tree.pack(side="left", fill="both", expand=True)
        self.rule_tree.bind("<<TreeviewSelect>>", self._rule_on_select)

        # 操作条：改 / 删
        act = tk.Frame(win, bg=th["card"])
        act.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(act, text="选中条目改为", bg=th["card"], fg=th["sub"],
                 font=f["small"]).pack(side="left")
        self.rule_edit_var = tk.StringVar(value=classify.WUXING_ORDER[0])
        ttk.Combobox(act, textvariable=self.rule_edit_var, state="readonly",
                     values=list(classify.WUXING_ORDER), width=3,
                     font=f["small"]).pack(side="left", padx=(6, 6))
        self._chip(act, "应用修改", self._rule_apply, pad=8).pack(side="left")
        self._chip(act, "删除选中", self._rule_del_sel, pad=8).pack(
            side="left", padx=(10, 0))
        tk.Label(act, text="内置条目不可删，只能覆盖", bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left", padx=(12, 0))

        # 添加条：类别 + 键 + 五行
        add = tk.Frame(win, bg=th["card"])
        add.pack(fill="x", padx=14, pady=(2, 4))
        tk.Label(add, text="新增", bg=th["card"], fg=th["sub"],
                 font=f["small"]).pack(side="left")
        self.rule_new_table = tk.StringVar(value="software")
        ttk.Combobox(add, textvariable=self.rule_new_table, state="readonly",
                     values=list(self.RULE_TABLE_LABEL), width=7,
                     font=f["small"]).pack(side="left", padx=(6, 6))
        self.rule_new_key = tk.Entry(add, bg=th["card"], fg=th["ink"],
                                     font=f["small"], highlightthickness=1,
                                     highlightbackground=th["line"],
                                     highlightcolor=th["accent"],
                                     insertbackground=th["ink"])
        self.rule_new_key.pack(side="left", fill="x", expand=True, ipady=2)
        self.rule_new_wx = tk.StringVar(value=classify.WUXING_ORDER[0])
        ttk.Combobox(add, textvariable=self.rule_new_wx, state="readonly",
                     values=list(classify.WUXING_ORDER), width=3,
                     font=f["small"]).pack(side="left", padx=(6, 6))
        self._chip(add, "添加", self._rule_add_new, pad=8).pack(side="left")

        foot = tk.Frame(win, bg=th["card"])
        foot.pack(fill="x", padx=14, pady=(2, 12))
        self._chip(foot, "恢复默认", self._rule_reset, pad=8).pack(side="left")
        tk.Label(foot, text="删除全部覆盖，回到内置表", bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left", padx=(8, 0))
        self._chip(foot, "关闭", self._rule_editor_close, pad=10).pack(
            side="right")
        self._rule_fill()
        if self.root.winfo_viewable():
            self._release_settings_grab()   # grab 移交给编辑器
            win.update_idletasks()
            w, h = 620, 640
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            win.geometry("%dx%d+%d+%d" % (w, h, rx + max(0, (rw - w) // 2),
                                          ry + max(0, (rh - h) // 3)))
            win.deiconify()
            win.lift()                      # 抬到设置弹窗之上
            win.wait_visibility()
            win.grab_set()
            win.focus_force()

    def _rule_win_show(self) -> None:
        if self.root.winfo_viewable():
            self._release_settings_grab()
            self.rule_win.deiconify()
            self.rule_win.lift()
            self.rule_win.wait_visibility()
            self.rule_win.grab_set()
            self.rule_win.focus_force()

    def _rule_editor_close(self) -> None:
        win = getattr(self, "rule_win", None)
        if win is not None:
            try:
                win.grab_release()
                win.withdraw()
            except tk.TclError:
                pass
            self._regrab_settings()         # 设置还开着就把 grab 还给它

    def _rule_fill(self) -> None:
        """按搜索词重建列表。过滤只匹配键，大小写不敏感。"""
        q = self.rule_search_var.get().strip().lower()
        tree = self.rule_tree
        tree.delete(*tree.get_children())
        rows = self._rule_rows_all()
        n = 0
        for r in rows:
            if q and q not in r["key"].lower():
                continue
            tree.insert("", "end", iid="%s|%s" % (r["table"], r["key"]),
                        values=(r["key"], r["wuxing"],
                                self.RULE_TABLE_LABEL[r["table"]],
                                "自定义添加" if r["user"] else "内置"),
                        tags=("user",) if r["user"] else ())
            n += 1
        self.rule_total_lbl.configure(text="%d / %d 条" % (n, len(rows)))

    def _rule_sel_row(self) -> dict | None:
        sel = self.rule_tree.selection()
        if not sel:
            return None
        table, key = sel[0].split("|", 1)
        for r in self._rule_rows_all():
            if r["table"] == table and r["key"] == key:
                return r
        return None

    def _rule_on_select(self, _e=None) -> None:
        r = self._rule_sel_row()
        if r:
            self.rule_edit_var.set(r["wuxing"])

    def _rule_apply(self) -> None:
        r = self._rule_sel_row()
        if not r:
            self.status.configure(text="五行对应表：先在列表里选中一条")
            return
        wx = self.rule_edit_var.get()
        ok, msg = rules.set_rule(r["table"], r["key"], wx)
        if not ok:
            self.status.configure(text="五行对应表：" + msg)
            return
        self._rule_fill()
        self._rules_recalc()
        self.status.configure(text="五行对应表：「%s」→%s，已重算" % (r["key"], wx))

    def _rule_del_sel(self) -> None:
        r = self._rule_sel_row()
        if not r:
            self.status.configure(text="五行对应表：先在列表里选中一条")
            return
        if not r["user"]:
            self.status.configure(
                text="五行对应表：「%s」是内置条目，不能删除，只能覆盖" % r["key"])
            return
        rules.remove_rule(r["table"], r["key"])
        self._rule_fill()
        self._rules_recalc()
        self.status.configure(text="五行对应表：已删除「%s」并重算" % r["key"])

    def _rule_add_new(self) -> None:
        table = self.rule_new_table.get()
        ok, msg = rules.set_rule(table, self.rule_new_key.get(),
                                 self.rule_new_wx.get())
        if not ok:
            self.status.configure(text="五行对应表：" + msg)
            return
        self.rule_new_key.delete(0, "end")
        self._rule_fill()
        self._rules_recalc()
        self.status.configure(text="五行对应表：已添加覆盖并重算")

    def _rule_reset(self) -> None:
        if not messagebox.askyesno("恢复默认", "删除全部自定义对应，回到内置表？"):
            return
        rules.reset()
        self._rule_fill()
        self._rules_recalc()
        self.status.configure(text="五行对应表：已恢复内置表")

    def _rules_recalc(self) -> None:
        """覆盖变更后重算（不重读桌面、不写历史）。未分析时只等下次分析。"""
        if not (self.ready and self.layout):
            return
        self._analyze()
        self._update_mode_text()
        self._draw(1.0)

    # ------------------------------------------------------------ 命主（阶段 10）

    def _build_owner(self) -> None:
        """命主栏：可滚动容器，内容由 _fill_owner 按是否已填渲染。"""
        th = self.th
        wrap = tk.Frame(self.pane_owner, bg=th["card"])
        wrap.pack(fill="both", expand=True)
        self.owner_scroll = tk.Canvas(wrap, bg=th["card"],
                                      highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.owner_scroll.yview)
        self.owner_scroll.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.owner_scroll.pack(side="left", fill="both", expand=True)
        self.owner_body = tk.Frame(self.owner_scroll, bg=th["card"])
        self._owner_win = self.owner_scroll.create_window(
            (0, 0), window=self.owner_body, anchor="nw")
        self.owner_body.bind("<Configure>", self._on_owner_configure)
        self.owner_scroll.bind(
            "<Configure>",
            lambda e: self.owner_scroll.itemconfigure(self._owner_win,
                                                      width=e.width))
        self.owner: dict | None = None
        self._owner_form = False          # 是否处于编辑态
        self._recalc_owner()

    def _on_owner_configure(self, _e) -> None:
        """内容不足一屏时清 region——「没多少内容还能滑」的防御（同阶段 9）。"""
        bbox = self.owner_scroll.bbox("all")
        if bbox and (bbox[3] - bbox[1]) <= self.owner_scroll.winfo_height():
            self.owner_scroll.configure(scrollregion="")
        else:
            self.owner_scroll.configure(scrollregion=bbox or "")

    def _recalc_owner(self) -> None:
        """按 self.birth 重算命主信息，并重画命主栏与盘面标记。"""
        b = self.birth
        self.owner = None
        if b:
            self.owner = mingua.compute(b["y"], b["m"], b["d"], b["g"])
            if self.owner is None:        # 存了但算不出（坏数据）
                self.birth = None
                self._save_prefs()
        self._fill_owner()

    def _marks(self) -> dict[str, str] | None:
        """盘上四吉四凶角标：{卦名: good/bad}。关掉或未填生辰时 None。"""
        if not self.marks_on or not self.owner:
            return None
        m: dict[str, str] = {}
        for _star, gua, _dir in self.owner["good"]:
            m[gua] = "good"
        for _star, gua, _dir in self.owner["bad"]:
            m[gua] = "bad"
        return m or None

    def _owner_cell_items(self) -> dict:
        """当前盘面每宫放了什么：{(row,col): [图标名]}。"""
        lay = self.layout or {}
        out: dict = {}
        for it in lay.get("icons", []):
            out.setdefault((it["row"], it["col"]), []).append(it["name"])
        return out

    # ---------------- 命主栏渲染

    def _fill_owner(self) -> None:
        th, f = self.th, self.f
        if not hasattr(self, "owner_body"):
            return
        for w in self.owner_body.winfo_children():
            w.destroy()
        pad = tk.Frame(self.owner_body, bg=th["card"])
        pad.pack(fill="both", expand=True, padx=18, pady=16)
        if self._owner_form or not self.owner:
            self._owner_render_form(pad)
        else:
            self._owner_render_info(pad)
        tk.Label(pad, text="命卦与纳音仅作参考，不构成对个人运势的判断。",
                 bg=th["card"], fg=th["weak"], font=f["tiny"],
                 justify="left", wraplength=380).pack(anchor="w", pady=(18, 0))
        self.owner_body.update_idletasks()
        self._on_owner_configure(None)

    def _owner_render_form(self, pad) -> None:
        """未填（或点「修改生辰」）时的表单。"""
        th, f = self.th, self.f
        b = self.birth or {}
        editing = self._owner_form
        tk.Label(pad, text="修改生辰" if editing else "填一次生辰",
                 bg=th["card"], fg=th["ink"], font=f["card"],
                 anchor="w").pack(anchor="w")
        tk.Label(pad, text="只存本机，不联网、不上传；可随时清空。"
                           "立春前出生按上一年算。",
                 bg=th["card"], fg=th["sub"], font=f["tiny"],
                 justify="left", wraplength=380).pack(anchor="w", pady=(4, 0))

        row = tk.Frame(pad, bg=th["card"])
        row.pack(anchor="w", pady=(16, 0))
        self.owner_entries: dict[str, tk.Entry] = {}
        for key, label, width in (("y", "年", 6), ("m", "月", 4),
                                  ("d", "日", 4)):
            tk.Label(row, text=label, bg=th["card"], fg=th["sub"],
                     font=f["small"]).pack(side="left")
            e = tk.Entry(row, bg=th["card"], fg=th["ink"], width=width,
                         font=f["small"], highlightthickness=1,
                         highlightbackground=th["line"],
                         highlightcolor=th["accent"],
                         insertbackground=th["ink"])
            e.pack(side="left", padx=(4, 12), ipady=2)
            if b.get(key):
                e.insert(0, str(b[key]))
            self.owner_entries[key] = e

        grow = tk.Frame(pad, bg=th["card"])
        grow.pack(anchor="w", pady=(12, 0))
        tk.Label(grow, text="性别", bg=th["card"], fg=th["sub"],
                 font=f["small"]).pack(side="left")
        self.owner_gender = tk.StringVar(value=b.get("g", "男"))
        self.owner_gender_chips: dict[str, tk.Label] = {}
        for g in ("男", "女"):
            chip = self._chip(grow, g,
                              lambda _e, gg=g: self._owner_set_gender(gg),
                              pad=10)
            chip.pack(side="left", padx=(8, 0))
            self.owner_gender_chips[g] = chip
        self._owner_sync_gender()

        acts = tk.Frame(pad, bg=th["card"])
        acts.pack(anchor="w", pady=(16, 0))
        self._chip(acts, "保存", self._owner_save, pad=10).pack(side="left")
        if editing and self.owner:
            self._chip(acts, "取消", self._owner_cancel, pad=10).pack(
                side="left", padx=(10, 0))
        self.owner_msg = tk.Label(pad, text="", bg=th["card"],
                                  fg=th["seal"], font=f["tiny"],
                                  justify="left", wraplength=380)
        self.owner_msg.pack(anchor="w", pady=(10, 0))

    def _owner_set_gender(self, g: str) -> None:
        self.owner_gender.set(g)
        self._owner_sync_gender()

    def _owner_sync_gender(self) -> None:
        th, f = self.th, self.f
        cur = self.owner_gender.get()
        for g, chip in self.owner_gender_chips.items():
            on = g == cur
            chip.configure(fg=th["accent"] if on else th["weak"],
                           font=f["card"] if on else f["small"],
                           highlightbackground=th["accent"] if on
                           else th["line"])

    def _owner_save(self) -> None:
        raw = {k: e.get().strip() for k, e in self.owner_entries.items()}
        if not all(raw.values()):
            self.owner_msg.configure(text="年、月、日都要填。")
            return
        try:
            y, m, d = int(raw["y"]), int(raw["m"]), int(raw["d"])
        except ValueError:
            self.owner_msg.configure(
                text="年、月、日都填数字，比如 1990 6 15。")
            return
        info = mingua.compute(y, m, d, self.owner_gender.get())
        if info is None:
            self.owner_msg.configure(
                text="这个日期看起来不存在，或超出可算范围（1900–2099）。")
            return
        self.birth = {"y": y, "m": m, "d": d, "g": self.owner_gender.get()}
        self._save_prefs()
        self._owner_form = False
        self._recalc_owner()
        self._invalidate_modes()
        self._sync_ai()
        self._draw(1.0)                   # 盘上标记随之出现
        self.status.configure(text="命主：%s命（%s）已记下"
                                   % (info["gua"], info["group"]))

    def _owner_cancel(self) -> None:
        self._owner_form = False
        self._fill_owner()

    def _owner_edit(self) -> None:
        self._owner_form = True
        self._fill_owner()

    def _owner_clear(self) -> None:
        if not messagebox.askyesno(
                "清空生辰", "删除本机保存的生辰？命主栏回到填写引导，"
                            "盘上四吉四凶标记也会去掉。"):
            return
        self.birth = None
        self._save_prefs()
        self._owner_form = False
        self._recalc_owner()
        self._invalidate_modes()
        self._sync_ai()
        self._draw(1.0)
        self.status.configure(text="命主：已清空生辰")

    def _owner_render_info(self, pad) -> None:
        """已填生辰：基本信息 → 四吉四凶 → 本命文昌 → 当前桌面 → 操作。"""
        th, f = self.th, self.f
        o = self.owner
        tk.Label(pad, text="%04d-%02d-%02d · %s · %s命（%s）· 纳音：%s"
                 % (o["year"], o["month"], o["day"], o["gender"], o["gua"],
                    o["group"], o["nayin"]),
                 bg=th["card"], fg=th["ink"], font=f["card"],
                 justify="left", wraplength=380).pack(anchor="w")
        sub = "年柱 %s · 命主五行 %s" % (o["ganzhi"], o["nayin_wuxing"])
        if o["shifted"]:
            sub += " · 立春前出生，按 %d 年算" % o["y_eff"]
        tk.Label(pad, text=sub, bg=th["card"], fg=th["sub"], font=f["tiny"],
                 justify="left", wraplength=380).pack(anchor="w", pady=(4, 0))

        two = tk.Frame(pad, bg=th["card"])
        two.pack(fill="x", pady=(16, 0))
        for title, rows, color in (
                ("对你偏助的一方", o["good"], th["level"]["吉"]),
                ("与你相冲的一方", o["bad"], th["level"]["忌"])):
            col = tk.Frame(two, bg=th["card"])
            col.pack(side="left", fill="both", expand=True, anchor="n")
            tk.Frame(col, bg=color, height=2).pack(fill="x")
            tk.Label(col, text=title, bg=th["card"], fg=color,
                     font=f["small"]).pack(anchor="w", pady=(4, 6))
            for star, gua, d in rows:
                tk.Label(col, text="%s　%s宫 %s" % (star, gua, d),
                         bg=th["card"], fg=th["ink"], font=f["tiny"],
                         anchor="w").pack(anchor="w", pady=1)

        wc = tk.Frame(pad, bg=th["card"])
        wc.pack(fill="x", pady=(16, 0))
        tk.Label(wc, text="本命文昌：%s宫（%s）"
                 % (o["wenchang_gua"], o["wenchang_dir"]),
                 bg=th["card"], fg=th["ink"], font=f["small"]).pack(anchor="w")
        tk.Label(wc, text="「优先文昌」推演以此为准——文书、笔记、学习类"
                          "落到这一方。",
                 bg=th["card"], fg=th["weak"], font=f["tiny"],
                 justify="left", wraplength=380).pack(anchor="w", pady=(2, 0))

        tk.Frame(pad, bg=th["line"], height=1).pack(fill="x", pady=(16, 0))
        # 小节标题：字号与正文（small 9pt）拉开，用 card 11pt + ink 色
        tk.Label(pad, text="对着当前桌面", bg=th["card"], fg=th["ink"],
                 font=f["card"]).pack(anchor="w", pady=(10, 4))
        if not self.ready:
            tk.Label(pad, text="先点左侧「开始分析」，这里会说出吉方空不空、"
                               "凶方放了什么。",
                     bg=th["card"], fg=th["weak"], font=f["tiny"],
                     justify="left", wraplength=380).pack(anchor="w")
        else:
            notes = mingua.desktop_notes(o, palace.palace_grid(self.top_dir),
                                         self._owner_cell_items(),
                                         classify.is_doc)
            for n in notes:
                tk.Label(pad, text="· " + n, bg=th["card"], fg=th["sub"],
                         font=f["tiny"], justify="left",
                         wraplength=380).pack(anchor="w", pady=(0, 5))

        acts = tk.Frame(pad, bg=th["card"])
        acts.pack(anchor="w", pady=(16, 0))
        self._chip(acts, "修改生辰", self._owner_edit, pad=10).pack(side="left")
        self._chip(acts, "清空生辰", self._owner_clear, pad=10).pack(
            side="left", padx=(10, 0))

    def _invalidate_modes(self) -> None:
        """生辰变了：两档定向推演作废，切回现状。"""
        self.wc_layout = self.wc_result = None
        self.ck_layout = self.ck_result = None
        if self.mode in ("wenchang", "caiku"):
            self.set_mode("now")

    # ------------------------------------------------------------ 历史

    # ------------------------------------------------------------ 桌面快照（日历）

    def _snap_init(self) -> None:
        """跨重建保留：当前月份与选中日期只初始化一次。"""
        if not hasattr(self, "cal_ym"):
            today = datetime.date.today()
            self.cal_ym = [today.year, today.month]
            self.snap_day = None
            self.snap_win = None

    def _snap_refresh(self) -> None:
        if not hasattr(self, "cal_grid"):
            return
        self._snap_init()
        today = datetime.date.today()
        days = snapshots.by_day()
        total = sum(len(v) for v in days.values())
        self.snap_count_lbl.configure(
            text=("共 %d 张 · 只在本机" % total) if total else "还没有保存过")
        if self.snap_day is None:
            if days:
                self.snap_day = sorted(days)[-1]
                try:
                    d0 = datetime.date.fromisoformat(self.snap_day)
                    self.cal_ym = [d0.year, d0.month]   # 直接翻到最近有记录那月
                except ValueError:
                    pass
            else:
                self.snap_day = today.isoformat()
        self._render_calendar(days, today)
        self._snap_day_list(days)

    def _render_calendar(self, days: dict, today: "datetime.date") -> None:
        th, f = self.th, self.f
        for w in self.cal_grid.winfo_children():
            w.destroy()
        y, m = self.cal_ym
        ym = "%04d-%02d" % (y, m)
        n_month = sum(1 for k in days if k.startswith(ym))
        self.cal_title.configure(
            text="%d 年 %d 月" % (y, m) +
                 ("　· %d 天有记录" % n_month if n_month else "　· 无记录"))
        for i, wd in enumerate(("一", "二", "三", "四", "五", "六", "日")):
            tk.Label(self.cal_grid, text=wd, bg=th["card"], fg=th["weak"],
                     font=f["tiny"]).grid(row=0, column=i, sticky="nsew")
            self.cal_grid.columnconfigure(i, weight=1)
        tkey = today.isoformat()
        for r, week in enumerate(calendar.monthcalendar(y, m), start=1):
            for c, d in enumerate(week):
                if not d:
                    tk.Label(self.cal_grid, text="", bg=th["card"]).grid(
                        row=r, column=c)
                    continue
                key = "%04d-%02d-%02d" % (y, m, d)
                has = key in days
                sel = key == self.snap_day
                is_today = key == tkey
                # 底色只表示「这天存过快照」；选中靠边框，两种标记不打架
                bg = th["sunk"] if has else th["card"]
                fg = th["accent"] if has else th["sub"]
                if sel:
                    hl, ht = th["accent"], 2      # 选中：主色双线框
                elif is_today:
                    hl, ht = th["line_outer"], 1  # 今天：浅描边
                else:
                    hl, ht = bg, 1
                cell = tk.Frame(self.cal_grid, bg=bg, cursor="hand2",
                                highlightthickness=ht,
                                highlightbackground=hl, highlightcolor=hl)
                cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
                tk.Label(cell, text=str(d), bg=bg, fg=fg,
                         font=f["body"] if has else f["small"],
                         cursor="hand2").pack(pady=(1, 1))
                # 圆点：有快照才亮，兼做「这天存过、能点开」的提示。
                # 用 place 叠在数字右侧，不占行高（否则日历会顶掉下方列表）
                dot = tk.Label(cell, text="•" if has else "",
                               bg=bg, fg=th["seal"], font=f["small"],
                               cursor="hand2")
                dot.place(relx=0.80, rely=0.52, anchor="center")
                for w in (cell,) + tuple(cell.winfo_children()):
                    w.bind("<Button-1>", lambda _e, k=key: self._snap_pick(k))

    def _snap_pick(self, key: str) -> None:
        self.snap_day = key
        self._snap_refresh()

    def _cal_shift(self, delta: int) -> None:
        self._snap_init()
        y, m = self.cal_ym
        m += delta
        if m < 1:
            y, m = y - 1, 12
        elif m > 12:
            y, m = y + 1, 1
        self.cal_ym = [y, m]
        self._snap_refresh()

    def _snap_day_list(self, days: dict | None = None) -> None:
        th, f = self.th, self.f
        if not hasattr(self, "snap_list"):
            return
        days = days if days is not None else snapshots.by_day()
        for w in self.snap_list.winfo_children():
            w.destroy()
        recs = days.get(self.snap_day or "", [])
        # 日期标题：翻到别的月份时也知道下面这几行是哪天的
        head = ""
        if self.snap_day:
            try:
                d0 = datetime.date.fromisoformat(self.snap_day)
                head = "%d 月 %d 日" % (d0.month, d0.day)
                if self.snap_day == datetime.date.today().isoformat():
                    head += "（今天）"
            except ValueError:
                head = self.snap_day
        if head:
            hrow = tk.Frame(self.snap_list, bg=th["card"])
            hrow.pack(fill="x")
            tk.Label(hrow, text=head, bg=th["card"], fg=th["sub"],
                     font=f["tiny"], anchor="w").pack(side="left")
            tk.Label(hrow, text=("%d 张" % len(recs)) if recs else "无",
                     bg=th["card"], fg=th["weak"], font=f["tiny"],
                     anchor="e").pack(side="right")
        if not recs:
            tk.Label(self.snap_list,
                     text="这一天没存过快照。分析完点「保存本次分析」，"
                          "日历上就会亮起圆点。",
                     bg=th["card"], fg=th["weak"], font=f["tiny"],
                     anchor="w", justify="left",
                     wraplength=380).pack(fill="x")
            return
        for rec in recs[:3]:
            row = tk.Frame(self.snap_list, bg=th["card"], cursor="hand2")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=rec["t"].strftime("%H:%M"), bg=th["card"],
                     fg=th["weak"], font=f["tiny"], width=6,
                     anchor="w").pack(side="left")
            tk.Label(row, text="%s 分" % rec["score"], bg=th["card"],
                     fg=th["ink"], font=f["card"]).pack(side="left")
            tk.Label(row, text="　" + str(rec["grade"] or ""), bg=th["card"],
                     fg=th["sub"], font=f["tiny"]).pack(side="left")
            tk.Label(row, text="查看 ›", bg=th["card"], fg=th["weak"],
                     font=f["tiny"]).pack(side="right")
            for w in row.winfo_children():
                w.bind("<Button-1>",
                       lambda _e, p=rec["path"]: self._snap_view(p))
            row.bind("<Button-1>", lambda _e, p=rec["path"]: self._snap_view(p))
        if len(recs) > 3:
            more = tk.Label(self.snap_list,
                            text="另有 %d 张 · 点开看全部 ›" % (len(recs) - 3),
                            bg=th["card"], fg=th["weak"], font=f["tiny"],
                            anchor="w", cursor="hand2")
            more.pack(fill="x")
            more.bind("<Button-1>", lambda _e: self._snap_day_all())
            more.bind("<Enter>", lambda _e: more.configure(fg=th["accent"]))
            more.bind("<Leave>", lambda _e: more.configure(fg=th["weak"]))

    def _snap_day_all(self) -> None:
        """某天保存了多张：列全，点一条看盘面。"""
        th, f = self.th, self.f
        recs = snapshots.by_day().get(self.snap_day or "", [])
        if not recs:
            return
        self._snap_close()
        win = tk.Toplevel(self.root)
        self.snap_win = win
        win.withdraw()
        win.title("%s · %d 张快照" % (self.snap_day, len(recs)))
        win.transient(self.root)
        win.configure(bg=th["card"])
        win.protocol("WM_DELETE_WINDOW", self._snap_close)
        win.bind("<Escape>", lambda _e: self._snap_close())
        tk.Label(win, text="点一条看当次盘面", bg=th["card"], fg=th["sub"],
                 font=f["tiny"], anchor="w").pack(fill="x", padx=16,
                                                  pady=(12, 4))
        box = tk.Frame(win, bg=th["card"])
        box.pack(fill="both", expand=True, padx=16)
        for rec in recs:
            row = tk.Frame(box, bg=th["card"], cursor="hand2")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=rec["t"].strftime("%H:%M:%S"), bg=th["card"],
                     fg=th["weak"], font=f["tiny"], width=9,
                     anchor="w").pack(side="left")
            tk.Label(row, text="%s 分" % rec["score"], bg=th["card"],
                     fg=th["ink"], font=f["card"]).pack(side="left")
            tk.Label(row, text="　" + str(rec["grade"] or ""), bg=th["card"],
                     fg=th["sub"], font=f["tiny"]).pack(side="left")
            tk.Label(row, text="查看 ›", bg=th["card"], fg=th["weak"],
                     font=f["tiny"]).pack(side="right")
            for w in row.winfo_children():
                w.bind("<Button-1>",
                       lambda _e, p=rec["path"]: self._snap_view(p))
            row.bind("<Button-1>",
                     lambda _e, p=rec["path"]: self._snap_view(p))
        foot = tk.Frame(win, bg=th["card"])
        foot.pack(fill="x", padx=16, pady=(4, 12))
        self._chip(foot, "关闭", self._snap_close, pad=10).pack(side="right")
        if self.root.winfo_viewable():
            win.update_idletasks()
            w, h = 380, 120 + 30 * min(12, len(recs))
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            win.geometry("%dx%d+%d+%d" % (w, h, rx + max(0, (rw - w) // 2),
                                          ry + max(0, (rh - h) // 3)))
            win.deiconify()
            win.lift()
            win.wait_visibility()
            win.focus_force()

    def _snap_save(self) -> None:
        if not (self.ready and self.result and self.layout):
            self.status.configure(text="先点左侧「开始分析」，再保存快照。")
            return
        try:
            path = snapshots.save(self.result, self.layout, self.top_dir,
                                  self.orient_text)
        except OSError as exc:
            self.status.configure(text="快照保存失败：%s" % exc)
            return
        today = datetime.date.today()
        self.cal_ym = [today.year, today.month]
        self.snap_day = today.isoformat()
        self._snap_refresh()
        self.status.configure(
            text="已保存快照 %s（%d 个图标 · %s 分），日历上今天已点亮圆点。"
                 % (path.name, len(self.layout.get("icons", [])),
                    self.result.get("score")))

    def _snap_view(self, path) -> None:
        snap = snapshots.load(path)
        if not snap:
            self.status.configure(text="这张快照读不出来（文件可能损坏）。")
            return
        self._snap_close()
        th, f = self.th, self.f
        win = tk.Toplevel(self.root)
        self.snap_win = win
        win.withdraw()
        win.title("快照 · %s" % snap.get("t", ""))
        win.transient(self.root)
        win.configure(bg=th["card"])
        win.protocol("WM_DELETE_WINDOW", self._snap_close)
        win.bind("<Escape>", lambda _e: self._snap_close())

        head = tk.Frame(win, bg=th["card"])
        head.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(head, text="%s" % str(snap.get("t", "")).replace("T", " "),
                 bg=th["card"], fg=th["ink"], font=f["card"]).pack(side="left")
        tk.Label(head, text="%s 分 · %s"
                 % (snap.get("score"), snap.get("grade", "")),
                 bg=th["card"], fg=th["accent"], font=f["card"]).pack(
            side="right")

        board = tk.Canvas(win, bg=th["board"], highlightthickness=0,
                          height=int(360 * self._fs() / 1.0))
        board.pack(fill="both", expand=True, padx=16, pady=(2, 6))

        lay = snapshots.to_layout(snap)
        top = int(snap.get("top_dir", 180))
        try:
            render.draw_board(board, lay, top,
                              max(360, self.pane_hist.winfo_width() - 60),
                              360, th=th, fonts=f)
        except (ValueError, KeyError):
            board.create_text(180, 120, text="这张快照的盘面画不出来",
                              fill=th["weak"], font=f["small"])

        info = tk.Text(win, height=7, wrap="word", bg=th["card"],
                       fg=th["sub"], font=f["tiny"], bd=0,
                       highlightthickness=0, padx=16, cursor="arrow",
                       selectbackground=th["sel"],
                       selectforeground=th["ink"])
        info.pack(fill="x", padx=0, pady=(0, 6))
        lines = []
        for key, sec in (snap.get("sections") or {}).items():
            lines.append("%s %.1f/%s" % (sec.get("name", key),
                                         sec.get("score") or 0, sec.get("max")))
        info.insert("end", "七项：" + " ｜ ".join(lines) + "\n")
        try:
            res = fengshui.analyze(lay, top)
            for d in (res.get("diagnoses") or [])[:3]:
                info.insert("end", "· %s：%s → %s\n"
                            % (d["key"], d["evidence"], d["advice"]))
        except (ValueError, KeyError):
            pass
        info.configure(state="disabled")

        foot = tk.Frame(win, bg=th["card"])
        foot.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(foot, text="快照只存在本机 data/snapshots/", bg=th["card"],
                 fg=th["weak"], font=f["tiny"]).pack(side="left")
        self._chip(foot, "关闭", self._snap_close, pad=10).pack(side="right")

        if self.root.winfo_viewable():
            win.update_idletasks()
            w, h = 680, 700
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            win.geometry("%dx%d+%d+%d" % (w, h, rx + max(0, (rw - w) // 2),
                                          ry + max(0, (rh - h) // 3)))
            win.deiconify()
            win.lift()
            win.wait_visibility()
            win.focus_force()

    def _snap_close(self) -> None:
        win = getattr(self, "snap_win", None)
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass
            self.snap_win = None

    def _fill_history(self) -> None:
        th, f = self.th, self.f
        recs = history.read_all()
        self._hist_recs = recs
        for w in self.hist_rows.winfo_children():
            w.destroy()

        if not recs:
            self.hist_sum.configure(
                text="还没有记录。点「重新扫描」就会写下第一条——每次扫描只记"
                     "时间、分数、断语和九宫计数，不记文件名。")
            self.hist_chart.delete("all")
            return

        scores = [r.get("score", 0) for r in recs]
        self.hist_sum.configure(
            text="共 %d 次记录（最多保留 %d 条）　最高 %d ／ 最低 %d ／ 最近 %s"
                 "　·　只存数字，不存文件名%s"
                 % (len(recs), history.MAX_LINES, max(scores), min(scores),
                    _fmt_time(recs[-1].get("t", "")),
                    "　·　右侧为新口径"
                    if any(history.rubric_of(r) >= history.RUBRIC for r in recs)
                    and any(history.rubric_of(r) < history.RUBRIC for r in recs)
                    else ""))
        self._animate_hist()

        # 明细：最新在上，最多 40 条
        pairs = [(recs[i], recs[i - 1] if i else None)
                 for i in range(len(recs) - 1, -1, -1)]
        for idx, (rec, prev) in enumerate(pairs[:40]):
            row = tk.Frame(self.hist_rows, bg=th["bg"])
            row.pack(fill="x")
            tk.Label(row, text=_fmt_time(rec.get("t", "")), bg=th["bg"],
                     fg=th["weak"], font=f["tiny"], width=12,
                     anchor="w").pack(side="left", padx=(14, 0), pady=4)
            tk.Label(row, text=str(rec.get("score", "—")), bg=th["bg"],
                     fg=th["ink"], font=f["card"], width=4,
                     anchor="e").pack(side="left")
            tk.Label(row, text="　" + str(rec.get("grade", "")), bg=th["bg"],
                     fg=th["sub"], font=f["tiny"], anchor="w").pack(side="left")

            counts = rec.get("counts") or [0] * 9
            tk.Label(row, text="%s 个 · %d 宫"
                              % (rec.get("total", 0),
                                 sum(1 for c in counts if c)),
                     bg=th["bg"], fg=th["weak"], font=f["tiny"]).pack(
                side="right", padx=(0, 12))
            if prev:
                d = rec.get("score", 0) - prev.get("score", 0)
                txt = "持平" if d == 0 else ("＋%d" % d if d > 0 else str(d))
                col = (th["level"]["吉"] if d > 0
                       else (th["level"]["忌"] if d < 0 else th["weak"]))
                tk.Label(row, text=txt, bg=th["bg"], fg=col,
                         font=f["tiny"], width=5, anchor="e").pack(
                    side="right", padx=(0, 6))
            if idx < min(len(pairs), 40) - 1:
                tk.Frame(self.hist_rows, bg=th["line"], height=1).pack(
                    fill="x", padx=(14, 0))

    def _animate_hist(self) -> None:
        tok = self._bump("hist")
        if not self._can_anim():
            self._draw_hist(1.0)
            return
        steps = _frames(620)

        def step(i: int) -> None:
            if self._tok.get("hist") != tok:
                return
            self._draw_hist(_ease_out(i / steps))
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    def _draw_hist(self, progress: float = 1.0,
                   size: tuple[int, int] | None = None) -> None:
        """分数趋势。纵轴按本次数据自适应，否则 60–80 的变化会压成一条直线。

        `size` 仅供测试指定画布尺寸——无窗口时 winfo_width 恒为 1。
        """
        c = self.hist_chart
        c.delete("all")
        recs = getattr(self, "_hist_recs", [])
        w, h = size or (c.winfo_width(), c.winfo_height())
        if not recs or w < 80 or h < 40:
            return
        tail = recs[-40:]
        scores = [r.get("score", 0) for r in tail]
        n = len(scores)
        th = self.th

        lo, hi = min(scores), max(scores)
        if hi - lo < 12:
            mid = (hi + lo) / 2.0
            lo, hi = mid - 6, mid + 6
        lo = max(0, lo - 2)
        hi = min(100, hi + 2)
        if hi - lo < 8:
            hi = min(100, lo + 8)

        # 右侧留白要容得下刻度字（8pt 两位数字约 14px），原来 26 太紧会贴边
        pad_l, pad_r, pad_t, pad_b = 10, 34, 10, 12
        pw = max(1.0, w - pad_l - pad_r)
        ph = max(1.0, h - pad_t - pad_b)

        def xy(i: float, v: float) -> tuple[float, float]:
            return (pad_l + pw * (i / max(1, n - 1)),
                    pad_t + ph * (1 - (v - lo) / (hi - lo)))

        for v in (hi, (hi + lo) / 2.0, lo):
            _, y = xy(0, v)
            c.create_line(pad_l, y, w - pad_r, y, fill=th["line"], width=1)
            c.create_text(w - pad_r + 7, y, text="%d" % round(v), anchor="w",
                          fill=th["weak"], font=self.f["tiny"])

        # 评分口径变更的分界线：改规则那天，前面的分数和后面的不可比。
        # 画一条竖虚线标出来，否则用户会以为自己的桌面突然变好了。
        cut = next((i for i, r in enumerate(tail)
                    if history.rubric_of(r) >= history.RUBRIC), None)
        if cut:
            cx, _yy = xy(cut, lo)
            # 图里只画线、不写字：折线正好走在顶部，文字压上去糊成一片。
            # 说明放在摘要行末尾（见 _fill_history），那里是空行。
            c.create_line(cx, pad_t, cx, pad_t + ph,
                          fill=th["line_outer"], dash=(3, 3))

        pts = [xy(i, v) for i, v in enumerate(scores)]
        shown = progress * (n - 1)
        seg: list[tuple[float, float]] = []
        for i, (x, y) in enumerate(pts):
            if i <= shown:
                seg.append((x, y))
            elif i > 0 and shown > i - 1:
                t = shown - (i - 1)
                seg.append((pts[i - 1][0] + (x - pts[i - 1][0]) * t,
                            pts[i - 1][1] + (y - pts[i - 1][1]) * t))
                break
            else:
                break

        if len(seg) >= 2:
            flat = [v for p in seg for v in p]
            c.create_line(*flat, fill=th["accent"], width=1.6)
        for i, (x, y) in enumerate(seg):
            last = i == len(seg) - 1
            r = 3.2 if last else 1.9
            c.create_oval(x - r, y - r, x + r, y + r, fill=th["accent"],
                          outline="")
        if n > 1 and progress >= 0.999:
            x, y = pts[-1]
            c.create_text(x, y - 11, text=str(scores[-1]), anchor="e",
                          fill=th["accent"], font=self.f["tiny"])
        if n == 1 and seg:
            x, y = seg[0]
            c.create_text(x, y - 11, text=str(scores[0]), anchor="w",
                          fill=th["accent"], font=self.f["tiny"])

    def _move_topline(self, animate: bool = True, _tries: int = 0) -> None:
        lbl = self.top_labels.get(self.top_tab)
        if lbl is None:
            return
        try:
            self.topbar.update_idletasks()
            x, w = lbl.winfo_x(), lbl.winfo_width()
            y = max(0, self.topbar.winfo_height() - 2)
        except tk.TclError:
            return
        if w <= 1:
            if _tries < 20:
                self.root.after(50, lambda: self._move_topline(animate,
                                                               _tries + 1))
            return
        tok = self._bump("topline")
        info = self.topline.place_info()
        try:
            cur = float(info.get("x", x) or x)
        except (TypeError, ValueError):
            cur = float(x)
        if not animate or not self._can_anim() or abs(cur - x) < 0.5:
            self.topline.place(x=x, y=y, width=w, height=2)
            return
        steps = _frames(220)

        def step(i: int) -> None:
            if self._tok.get("topline") != tok:
                return
            p = _ease_in_out(i / steps)
            self.topline.place(x=cur + (x - cur) * p, y=y, width=w, height=2)
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    def _fill_cards(self, res: dict) -> None:
        """逐条插入诊断卡：每条比前一条晚 28ms 出现，像列表在往下长。"""
        tok = self._bump("cards")
        for w in self.cards.winfo_children():
            w.destroy()
        wrap = max(240, int(self.scroll.winfo_width()) - 60)
        limit = 12          # 见 docs/03-设计规范.md 7.3
        shown = res["diagnoses"][:limit]
        rest = len(res["diagnoses"]) - len(shown)

        def make(idx: int) -> None:
            self._make_card(shown[idx], idx, len(shown), wrap)
            if idx == len(shown) - 1 and rest > 0:
                tk.Label(self.cards, text="另有 %d 条，见导出报告" % rest,
                         bg=self.th["card"], fg=self.th["weak"],
                         font=self.f["tiny"], anchor="w").pack(
                    fill="x", padx=16, pady=(12, 14))
            self._on_cards_configure(None)

        if not self._can_anim() or not shown:
            for i in range(len(shown)):
                make(i)
            return

        def step(i: int) -> None:
            if self._tok.get("cards") != tok:
                return
            if i < len(shown):
                make(i)
                self.root.after(28, step, i + 1)

        step(0)

    def _make_card(self, d: dict, idx: int, total: int, wrap: int) -> None:
        th, f = self.th, self.f
        color = th["level"].get(d["level"], th["sub"])
        card = tk.Frame(self.cards, bg=th["card"])
        card.pack(fill="x")

        tk.Frame(card, bg=color, width=2).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=th["card"])
        inner.pack(side="left", fill="both", expand=True,
                   padx=(11, 10), pady=(9, 8))

        head = tk.Frame(inner, bg=th["card"])
        head.pack(fill="x")
        tk.Label(head, text=d["level"], bg=th["card"], fg=color,
                 font=f["card"]).pack(side="left")
        tk.Label(head, text="　" + d["key"], bg=th["card"], fg=th["ink"],
                 font=f["card"]).pack(side="left")
        if d["max"]:
            tag = ("扣 %g" % d["deduct"]) if d["deduct"] else "满分"
            tk.Label(head, text=tag, bg=th["card"], fg=color,
                     font=f["tiny"]).pack(side="right")

        # 仿宋的行高比雅黑小一截（9pt：12 vs 17），段间 pady 往上补一点，
        # 否则三条连着看像挤在一起。
        tk.Label(inner, text=d["evidence"], bg=th["card"], fg=th["sub"],
                 font=f["tiny"], wraplength=wrap, justify="left",
                 anchor="w").pack(fill="x", pady=(4, 4))
        tk.Label(inner, text="理　" + d["principle"], bg=th["card"],
                 fg=th["ink"], font=f["tiny"], wraplength=wrap,
                 justify="left", anchor="w").pack(fill="x", pady=(0, 4))
        tk.Label(inner, text="改　" + d["advice"], bg=th["card"],
                 fg=th["accent"], font=f["tiny"], wraplength=wrap,
                 justify="left", anchor="w").pack(fill="x")

        if idx < total - 1:
            tk.Frame(self.cards, bg=th["line"], height=1).pack(
                fill="x", padx=(14, 0))

    # ------------------------------------------------------------ 分图标

    def _on_picon_configure(self, _e=None) -> None:
        """内容不足一屏时清空 scrollregion（同分条页的处理）。"""
        try:
            content = self.picon_body.winfo_reqheight()
            view = max(1, self.picon_scroll.winfo_height())
        except tk.TclError:
            return
        if content <= view:
            self.picon_scroll.configure(scrollregion="")
        else:
            self.picon_scroll.configure(
                scrollregion=self.picon_scroll.bbox("all"))

    def _build_picon_legend(self) -> None:
        """判定图例：五种状态各一句话，颜色跟着主题的 tone5 走。"""
        th, f = self.th, self.f
        box = self.picon_legend
        for w in box.winfo_children():
            w.destroy()
        tk.Frame(box, bg=th["line"], height=1).pack(fill="x")
        inner = tk.Frame(box, bg=th["card"])
        inner.pack(fill="x", padx=14, pady=(6, 8))
        tk.Label(inner, text="判定的意思", bg=th["card"], fg=th["sub"],
                 font=f["tiny"]).pack(anchor="w", pady=(0, 2))
        for tone, name, desc in pericon.LEGEND:
            row = tk.Frame(inner, bg=th["card"])
            row.pack(fill="x", pady=(1, 0))
            tk.Label(row, text="●", bg=th["card"], fg=th["tone5"][tone],
                     font=f["tiny"]).pack(side="left", padx=(0, 4))
            tk.Label(row, text=name, bg=th["card"], fg=th["tone5"][tone],
                     font=f["tiny"], width=4, anchor="w").pack(side="left")
            tk.Label(row, text=desc, bg=th["card"], fg=th["weak"],
                     font=f["tiny"], anchor="w").pack(side="left")

    def _reveal_boxes(self, boxes) -> None:
        """三段逐条弹出（12ms 一条）。动效关掉时一次性到位。"""
        if not self._can_anim():
            for b in boxes:
                b.pack(fill="x", pady=(2, 0))
            self._on_picon_configure()
            return
        tok = self._bump("picon")

        def step(i: int) -> None:
            if self._tok.get("picon") != tok:
                return
            if i < len(boxes):
                boxes[i].pack(fill="x", pady=(2, 0))
                self._on_picon_configure()
                self.root.after(12, step, i + 1)
            else:
                self._on_picon_configure()

        step(0)

    def _picon_open_group(self, content, rows, arrow, gi: int,
                          animate: bool = True) -> None:
        """展开一宫：容器先立住，图标行一条条往下长（14ms 一条）。"""
        content.pack(fill="x", padx=(32, 12), pady=(0, 6))
        self._picon_open.add(gi)
        arrow.configure(text="▾")

        def put(r: dict) -> None:
            r["line"].pack(fill="x", pady=(2, 0))
            if r["key"] in self._picon_icon_open:
                r["detail"].pack(after=r["line"], fill="x", padx=(18, 0),
                                 pady=(2, 6))
                for b in r["boxes"]:
                    b.pack(fill="x", pady=(2, 0))

        if not animate or not self._can_anim() or not rows:
            for r in rows:
                put(r)
            self._on_picon_configure()
            return
        tok = self._bump("picon")

        def step(i: int) -> None:
            if self._tok.get("picon") != tok:
                return
            if i < len(rows):
                put(rows[i])
                self._on_picon_configure()
                self.root.after(14, step, i + 1)
            else:
                self._on_picon_configure()

        step(0)

    def _picon_close_group(self, content, rows, arrow, gi: int) -> None:
        """折叠一宫：倒着收（10ms 一条），最后把容器摘掉。"""
        self._picon_open.discard(gi)
        arrow.configure(text="▸")

        def take(r: dict) -> None:
            r["detail"].pack_forget()
            for b in r["boxes"]:
                b.pack_forget()
            r["line"].pack_forget()

        if not self._can_anim() or not rows:
            for r in rows:
                take(r)
            content.pack_forget()
            self._on_picon_configure()
            return
        tok = self._bump("picon")

        def step(i: int) -> None:
            if self._tok.get("picon") != tok:
                return
            if i >= 0:
                take(rows[i])
                self._on_picon_configure()
                self.root.after(10, step, i - 1)
            else:
                content.pack_forget()
                self._on_picon_configure()

        step(len(rows) - 1)

    def _fill_pericon(self) -> None:
        """九宫两级折叠：宫 → 图标 → 三段。

        默认全折叠，只露宫位摘要。46 个图标全展开是 46×4 个 Label，
        一次建完再切页签会明显卡顿，所以图标行在第一次展开该宫时才建。
        """
        th, f = self.th, self.f
        for w in self.picon_body.winfo_children():
            w.destroy()
        if not (self.ready and self.result and self.layout):
            tk.Label(self.picon_body,
                     text="先点左侧「开始分析」，这里才有逐图标的判定。",
                     bg=th["card"], fg=th["weak"],
                     font=f["small"]).pack(pady=40)
            self._on_picon_configure()
            return
        if not self._picon_groups:
            self._picon_groups = pericon.build(self.layout, self.result)
        # 宽度要在 pack 生效之后才准：直接读会拿到 1，wrap 被保底值顶死，
        # 于是 20 字的句子被硬折成两行（2026-10-27 截图发现）。
        self.picon_scroll.update_idletasks()
        sw = int(self.picon_scroll.winfo_width())
        if sw <= 1:
            sw = int(self.pane_pericon.winfo_width()) or 380
        wrap = max(240, sw - 56)

        for gi, g in enumerate(self._picon_groups):
            row = tk.Frame(self.picon_body, bg=th["card"])
            row.pack(fill="x")
            head = tk.Frame(row, bg=th["card"], cursor="hand2")
            head.pack(fill="x", padx=(14, 12), pady=(8, 7))
            arrow = tk.Label(head, text="▸", bg=th["card"], fg=th["weak"],
                             font=f["tiny"], width=2, anchor="w",
                             cursor="hand2")
            arrow.pack(side="left")
            if g["center"]:
                head_txt = "中宫 · %d 个" % g["count"]
            else:
                head_txt = "%s宫 · %s · %d 个 · 平均 %d" % (
                    g["gua"], g["dir"], g["count"], g["avg"])
            tk.Label(head, text=head_txt, bg=th["card"], fg=th["ink"],
                     font=f["small"], anchor="w",
                     cursor="hand2").pack(side="left")
            lv_color = {"吉": th["grade"]["high"], "平": th["grade"]["mid"],
                        "忌": th["grade"]["low"]}.get(g["level"], th["sub"])
            lv_txt = "宜空" if g["center"] else g["level"]
            tk.Label(head, text="　" + lv_txt, bg=th["card"], fg=lv_color,
                     font=f["tiny"], cursor="hand2").pack(side="left")

            content = tk.Frame(row, bg=th["card"])
            state = {"built": False, "rows": []}

            def toggle(_e=None, gi=gi, g=g, content=content, arrow=arrow,
                       state=state, animate=True):
                if not state["built"]:
                    state["rows"] = self._build_picon_rows(content, gi, g, wrap)
                    state["built"] = True
                if content.winfo_manager():
                    self._picon_close_group(content, state["rows"], arrow, gi)
                else:
                    self._picon_open_group(content, state["rows"], arrow, gi,
                                           animate=animate)

            for w in [head] + list(head.winfo_children()):
                w.bind("<Button-1>", toggle)

            tk.Frame(self.picon_body, bg=th["line"], height=1).pack(
                fill="x", padx=(14, 0))
            if gi in self._picon_open:      # 切页签回来保持展开，但不再播动画
                toggle(animate=False)
        self._on_picon_configure()

    def _build_picon_rows(self, parent, gi: int, g: dict, wrap: int) -> list:
        """建一个宫里的图标行；每条再点开是「现／理／改」三段。

        返回 [{"key":…, "line":…, "detail":…, "boxes":[…]}], 供展开/折叠动画
        逐条 pack / pack_forget。
        """
        th, f = self.th, self.f
        rows: list[dict] = []
        for ii, ic in enumerate(g["icons"]):
            key = "%d:%d" % (gi, ii)
            color = th["tone5"].get(ic["tone"], th["sub"])
            line = tk.Frame(parent, bg=th["card"], cursor="hand2")
            nm = ic["name"] if len(ic["name"]) <= 26 else ic["name"][:25] + "…"
            tk.Label(line, text=nm, bg=th["card"], fg=th["ink"],
                     font=f["small"], anchor="w",
                     cursor="hand2").pack(side="left")
            tk.Label(line, text="　%s · %s" % (ic["wuxing"], ic["rel"]),
                     bg=th["card"], fg=th["sub"], font=f["tiny"],
                     cursor="hand2").pack(side="left")
            tk.Label(line, text=ic["verdict"], bg=th["card"], fg=color,
                     font=f["tiny"], cursor="hand2").pack(side="right")

            detail = tk.Frame(parent, bg=th["card"])
            boxes = []
            for tag, text, fg in (("现", ic["evidence"], th["sub"]),
                                  ("理", ic["principle"], th["ink"]),
                                  ("改", ic["advice"], th["accent"])):
                box = tk.Frame(detail, bg=th["card"])
                boxes.append(box)
                tk.Label(box, text=tag, bg=th["card"], fg=th["weak"],
                         font=f["tiny"], width=2, anchor="nw").pack(side="left")
                tk.Label(box, text=text, bg=th["card"], fg=fg,
                         font=f["tiny"], wraplength=wrap, justify="left",
                         anchor="w").pack(side="left", fill="x", expand=True)

            r = {"key": key, "line": line, "detail": detail, "boxes": boxes}

            def toggle_icon(_e=None, r=r):
                d = r["detail"]
                if d.winfo_manager():
                    for b in r["boxes"]:
                        b.pack_forget()
                    d.pack_forget()
                    self._picon_icon_open.discard(r["key"])
                    self._on_picon_configure()
                else:
                    # after=line：不然会追加到后面那些图标行之后
                    d.pack(after=r["line"], fill="x", padx=(18, 0),
                           pady=(2, 6))
                    self._picon_icon_open.add(r["key"])
                    self._reveal_boxes(r["boxes"])

            for w in [line] + list(line.winfo_children()):
                w.bind("<Button-1>", toggle_icon)
            rows.append(r)
        return rows

    # ------------------------------------------------------------ 绘制

    def _draw(self, reveal: float = 1.0) -> None:
        self.hits = []
        self._tip_target = None
        self._cell_key = None
        self.board.delete("tip")
        self.board.delete("cellhl")
        self.board.delete("ripple")
        w = max(200, self.board.winfo_width())
        h = max(160, self.board.winfo_height())
        lay, _res, _mv = self._scene()
        if not self.ready or not lay:
            # 启动闸门：空盘 + 中央按钮
            if self.error:
                self.board.delete("all")
                self.board.create_text(w / 2, h / 2,
                                       text="读取失败\n\n%s" % self.error,
                                       fill=self.th["seal"],
                                       font=self.f["body"], justify="center")
                self._btn_hit = None
                return
            label = "重新分析" if self._analyzed_once else "开始分析"
            self._btn_hit = render.draw_empty(self.board, w, h, self.th, self.f,
                                              label=label)
            return
        self._btn_hit = None
        top = self._orient_label.get(self.orient_var.get(), 180)
        self.hits = render.draw_board(self.board, lay, top, w, h,
                                      th=self.th, fonts=self.f, reveal=reveal, marks=self._marks())

    def _animate_reveal(self, dur: int = 900) -> None:
        """整体揭示。进度线性推进，缓动交给绘制层——那里分了三段各自的曲线，
        全局再叠一层缓动会让前半段发闷、后半段抢。"""
        tok = self._bump("reveal")
        self.revealing = True
        if not self._can_anim():
            self._draw(1.0)
            self.revealing = False
            return
        steps = _frames(dur)

        def step(i: int) -> None:
            if self._tok.get("reveal") != tok:
                self.revealing = False
                return
            self._draw(i / steps)
            if i < steps:
                self.root.after(16, step, i + 1)
            else:
                self._draw(1.0)
                self.revealing = False

        step(1)

    def _on_resize(self, _event) -> None:
        if self._pending:
            return
        self._pending = True
        self.root.after_idle(self._resize_done)

    def _fit_mode_lbl(self) -> None:
        """说明书块的折行宽度：盘宽 − 内边距 − 右侧两颗 chip 的实际占位。

        必须**在 chip pack 之后**重算。首次分析前 chip 不存在，那时算出来的宽度
        偏大，chip 一出现就会压到文字上（2026-10-27 换宋体后实测压字）。
        用 winfo_manager() 判断而不是 ismapped()：pack 过就算占位，
        哪怕这一帧还没映射出来。
        """
        try:
            bw = self.board.winfo_width() or self.left.winfo_width()
        except tk.TclError:
            return
        if not bw:
            return
        used = 0
        for w in (getattr(self, "re_chip", None), getattr(self, "move_chip", None)):
            if w is None:
                continue
            try:
                if w.winfo_manager():
                    used += w.winfo_reqwidth()
            except tk.TclError:
                pass
        self.mode_lbl.configure(wraplength=max(240, bw - 66 - used))

    def _resize_done(self) -> None:
        self._pending = False
        self._fit_mode_lbl()
        self.summary_lbl.configure(
            wraplength=max(220, self.right.winfo_width() - 44))
        self._draw(1.0)
        self._draw_bars(1.0)
        self._move_topline(False)

    def _on_orient(self, _event) -> None:
        self.orient_text = self.orient_var.get()
        # 先落盘再重算：下一次启动直接沿用，不必重新选
        self.top_dir = self._orient_label.get(self.orient_text, self.top_dir)
        self._save_prefs()
        self.mode = "now"
        self.proj_layout = self.proj_result = None
        self.rep_layout = self.rep_result = None
        self.moves, self.rep_moves = [], []
        self.wc_layout = self.wc_result = None
        self.ck_layout = self.ck_result = None
        self._sync_seg()
        self._analyze()
        self._update_mode_text()
        self._animate_reveal(620)

    # ------------------------------------------------------------ 悬停

    def _clear_tip(self) -> None:
        self._bump("tip")
        self.board.delete("tip")
        if self._tip_target is not None:
            self._grow_icon(self._tip_target, False)
        self._tip_target = None

    def _on_leave(self) -> None:
        self._clear_tip()
        self._cell_key = None
        self._bump("cell")
        self.board.delete("cellhl")
        try:
            self.board.configure(cursor="")
        except tk.TclError:
            pass

    def _grow_icon(self, hit: dict, grow: bool) -> None:
        """图标悬停放大/复原。只改这一个图元的顶点，不重绘整盘。"""
        item = hit.get("id")
        if item is None:
            return
        key = "grow%d" % hit["index"]
        tok = self._bump(key)
        bb = self.board.bbox(item)
        if not bb:
            return
        cur = (bb[2] - bb[0]) / 2.0
        target = hit["box"] * (1.55 if grow else 1.0) / 2.0
        cx, cy = hit["cx"], hit["cy"]

        def paint(half: float, wide: bool) -> None:
            try:
                self.board.coords(item, *render.rr_points(cx, cy, half))
                self.board.itemconfigure(
                    item, outline=self.th["accent"] if wide else "",
                    width=1 if wide else 0)
            except tk.TclError:
                pass

        if not self._can_anim() or abs(cur - target) < 0.4:
            paint(target, grow)
            return
        steps = _frames(170 if grow else 140)

        def step(i: int) -> None:
            if self._tok.get(key) != tok:
                return
            p = _ease_out(i / steps)
            paint(cur + (target - cur) * p, grow)
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    def _show_tip(self, hit: dict, px: int, py: int) -> None:
        tok = self._bump("tip")
        th = self.th
        bw, bh = self.board.winfo_width(), self.board.winfo_height()
        x = min(px + 16, max(20, bw - 220))
        y = min(py + 14, max(20, bh - 96))
        txt = self.board.create_text(x, y, text=hit["text"], anchor="nw",
                                     fill=th["card"], font=self.f["tip"],
                                     justify="left", tags="tip")
        bbox = self.board.bbox(txt)
        rect = None
        if bbox:
            rect = self.board.create_rectangle(
                bbox[0] - 8, bbox[1] - 6, bbox[2] + 8, bbox[3] + 6,
                fill=th["card"], outline=th["card"], tags="tip")
            self.board.tag_lower(rect, txt)
        if not self._can_anim():
            self.board.itemconfigure(txt, fill=th["ink"])
            if rect:
                self.board.itemconfigure(rect, outline=th["line"])
            return
        steps = _frames(190)

        def step(i: int) -> None:
            if self._tok.get("tip") != tok:
                return
            p = _ease_out(i / steps)
            off = 6 * (1 - p)
            self.board.coords(txt, x + off, y + off)
            if rect and bbox:
                self.board.coords(rect, bbox[0] - 8 + off, bbox[1] - 6 + off,
                                  bbox[2] + 8 + off, bbox[3] + 6 + off)
            self.board.itemconfigure(
                txt, fill=self._fade_in(th["ink"], p, th["card"]))
            if rect:
                self.board.itemconfigure(
                    rect, outline=self._fade_in(th["line"], p, th["card"]))
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    # ------------------------------------------------------------ 宫格高亮

    def _hover_cell(self, px: int, py: int) -> None:
        """鼠标所在的那一宫描边淡入。离开即消失。"""
        lay, _res, _mv = self._scene()
        found = None
        if lay:
            bw = self.board.winfo_width()
            bh = self.board.winfo_height()
            for r in range(3):
                for c in range(3):
                    x0, y0, x1, y1 = render.cell_box(lay, bw, bh, self.f, r, c)
                    if x0 <= px <= x1 and y0 <= py <= y1:
                        found = (r, c, x0, y0, x1, y1)
                        break
                if found:
                    break
        key = found[:2] if found else None
        if key == self._cell_key:
            return
        self._cell_key = key
        self._bump("cell")
        self.board.delete("cellhl")
        if not found:
            return
        _r, _c, x0, y0, x1, y1 = found
        rid = self.board.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1,
                                          outline=self.th["board"], width=1,
                                          tags="cellhl")
        try:
            self.board.tag_lower(rid, "ic")     # 压在图标之下，不挡住名称
        except tk.TclError:
            pass
        if not self._can_anim():
            self.board.itemconfigure(rid, outline=self.th["accent"])
            return
        tok = self._tok.get("cell")
        steps = _frames(150)

        def step(i: int) -> None:
            if self._tok.get("cell") != tok:
                return
            p = _ease_out(i / steps)
            self.board.itemconfigure(rid,
                                     outline=self._fade_in(self.th["accent"], p))
            if i < steps:
                self.root.after(16, step, i + 1)

        step(1)

    # ------------------------------------------------------------ 点击涟漪

    def _ripple_color(self, p: float) -> str:
        """涟漪的描边色：前 15% 保持主色，之后退回底色（即淡出）。"""
        fade = _clamp01((p - 0.15) / 0.85)
        return self._fade_in(self.th["accent"], 1.0 - fade)

    def _ripple(self, hit: dict) -> None:
        """点图标：一圈圆角方框自内向外扩散，后半程淡去。

        图元只建一次、逐帧换顶点与颜色。每帧删了重建会闪，
        而且颜色方向写反就成了"越来越实、然后突然消失"。
        """
        if not self._can_anim():
            return
        tok = self._bump("ripple")
        self.board.delete("ripple")
        cx, cy = hit["cx"], hit["cy"]
        base = hit["box"] * 0.62
        steps = _frames(560)
        try:
            ring = self.board.create_polygon(
                render.rr_points(cx, cy, base), fill="",
                outline=self.th["accent"], width=2, tags="ripple")
        except tk.TclError:
            return

        def step(i: int) -> None:
            if self._tok.get("ripple") != tok:
                return
            p = i / steps
            r = base + hit["box"] * 2.9 * _ease_out(p)
            # 前 15% 保持完全可见，之后线性淡到底色；
            # _fade_in(color, 1-fade) 表示"从 color 退回底色"。
            fade = _clamp01((p - 0.15) / 0.85)
            try:
                self.board.coords(ring, *render.rr_points(cx, cy, r))
                self.board.itemconfigure(
                    ring, outline=self._ripple_color(p),
                    width=max(0.8, 2.2 - 1.4 * fade))
            except tk.TclError:
                return
            if i < steps:
                self.root.after(16, step, i + 1)
            else:
                self.board.delete("ripple")

        step(1)

    def _on_click(self, event) -> None:
        if not self.ready:
            b = self._btn_hit
            if b and b["x0"] <= event.x <= b["x1"] and b["y0"] <= event.y <= b["y1"]:
                self.analyze()
            return
        for h in self.hits:
            if h["x0"] <= event.x <= h["x1"] and h["y0"] <= event.y <= h["y1"]:
                self._ripple(h)
                if self._tip_target is not h:      # 与悬停共用状态，避免卡在放大态
                    if self._tip_target is not None:
                        self._grow_icon(self._tip_target, False)
                    self._tip_target = h
                    self._grow_icon(h, True)
                    self._show_tip(h, event.x, event.y)
                break

    def _on_motion(self, event) -> None:
        if self.revealing:        # 揭示动画期间图元每帧重建，不做悬停
            return
        if not self.ready:
            b = self._btn_hit
            over = bool(b and b["x0"] <= event.x <= b["x1"]
                        and b["y0"] <= event.y <= b["y1"])
            try:
                self.board.configure(cursor="hand2" if over else "")
            except tk.TclError:
                pass
            return
        self._hover_cell(event.x, event.y)
        target = None
        for h in self.hits:
            if h["x0"] <= event.x <= h["x1"] and h["y0"] <= event.y <= h["y1"]:
                target = h
                break

        # 鼠标滑到提示框上时目标变空——那不是"离开图标"，不能把提示收掉，
        # 否则提示框必然"闪一下就没"。
        if target is None and self._tip_target is not None:
            bb = self.board.bbox("tip")
            if bb and (bb[0] - 6 <= event.x <= bb[2] + 6
                       and bb[1] - 6 <= event.y <= bb[3] + 6):
                return

        if target is not self._tip_target:
            self.board.delete("tip")
            self._bump("tip")
            if self._tip_target is not None:
                self._grow_icon(self._tip_target, False)
            self._tip_target = target
            try:
                self.board.configure(cursor="hand2" if target else "")
            except tk.TclError:
                pass
        if target is None:
            return
        if not self.board.find_withtag("tip"):
            self._grow_icon(target, True)
            self._show_tip(target, event.x, event.y)


def main() -> int:
    paths.ensure()          # exe 旁边首次运行要建 data/ 与 exports/
    # 打包后的自检：--selftest 只建界面、写一份结果就退，**不弹窗**
    # （exe 是 windowed，没有控制台，所以结果写文件）
    self_test = "--selftest" in sys.argv
    enable_dpi_awareness()
    root = tk.Tk()
    if self_test:
        root.withdraw()
    try:
        app = App(root)
    except Exception:
        if self_test:
            (paths.BASE / "_selftest.txt").write_text(
                "FAIL 构建界面\n" + traceback.format_exc(), encoding="utf-8")
            return 1
        raise
    if self_test:
        lines = [
            "OK",
            "frozen=%s" % paths.FROZEN,
            "exe=%s" % sys.executable,
            "base=%s" % paths.BASE,
            "data=%s" % paths.DATA.is_dir(),
            "exports=%s" % paths.EXPORTS.is_dir(),
            "ready=%s" % getattr(app, "ready", None),
            "theme=%s" % getattr(app, "theme_name", "?"),
            "cards=%d" % len(getattr(app, "cards", []).winfo_children()),
        ]
        if "--deep" in sys.argv:      # 再走一遍真实读盘 + 打分
            before = (history.FILE.read_text(encoding="utf-8")
                      if history.FILE.exists() else "")
            try:
                app.analyze()
                res = getattr(app, "result", None) or {}
                lay = getattr(app, "layout", None) or {}
                lines.append("analyze=ok score=%s" % res.get("score"))
                lines.append("grade=%s" % res.get("grade"))
                lines.append("icons=%d" % len(lay.get("icons", [])))
                lines.append("diagnoses=%d" % len(res.get("diagnoses", [])))
            except Exception:
                lines.append("analyze=FAIL\n" + traceback.format_exc())
            finally:
                # 自检不污染历史
                try:
                    if before:
                        history.FILE.write_text(before, encoding="utf-8")
                    elif history.FILE.exists():
                        history.FILE.unlink()      # 原来没有就别留空文件
                except OSError:
                    pass
        (paths.BASE / "_selftest.txt").write_text("\n".join(lines),
                                                 encoding="utf-8")
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
