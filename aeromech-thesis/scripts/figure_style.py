# -*- coding: utf-8 -*-
"""figure_style.py — v1.6.5 Academic Visual System 单一来源（Single Source of Truth）

整个 figure system（figkit / providers / QA / golden samples）的样式常量与度量函数
一律取自本模块；**禁止其他 figure 模块散写 HEX / 字号 / 线宽 / 边距**
（tests/v1_6_5 有源码扫描断言 STY-INT-01 强制）。

色值非拍脑袋：经三轮量化验证固化（2026-09-17，见 docs/v1.6.5/02 + 本模块 validate_palette()）：
  - text on 任意填充底 WCAG ≥4.5（实测 9.9–14.8）
  - 描边色 on fill/bg ≥3.0（非文本要素；neutral 只用于 bg 描边）
  - 相邻填充区域灰度分离 ≥0.12（fill vs tint 0.135–0.193；tint vs bg 0.288–0.345）
  - 饱和度 ≤0.45（中性族）；语义强调色 ≤0.55（accent 0.50 / risk 0.48）
  - 层级区分（故障树 Top/Gate/BE、AND/OR）靠 描边+文字+字重 三重编码，
    不依赖颜色 → 黑白打印可辨（§三 要求）。

用法：
  from figure_style import (COLOR_PALETTE, SEMANTIC_COLORS, TYPOGRAPHY, LINE_STYLES,
  SPACING, FIGURE_SIZE_PRESETS, get_semantic_color, get_text_style, get_figure_size,
  apply_academic_style, contrast_ratio, grayscale_delta, saturation, hue_of,
  validate_palette)
"""
import re

# ---------------- A. Color ----------------
COLOR_PALETTE = {
    # 中性族（低饱和冷灰蓝；饱和度均 ≤0.45）
    "bg":        "#FFFFFF",   # 画布/论文白底
    "fill":      "#E8EEF3",   # 常规节点/柱体底
    "fill_alt":  "#F5F8FA",   # 次级底（斑马纹/分组带）
    "primary":   "#33607F",   # 主结构描边/主系列（S=0.43）
    "secondary": "#5B7C99",  # 次结构描边/次系列
    "neutral":   "#7E8D9A",  # 弱结构（仅白底描边：on bg=3.41）
    "text":      "#1F2933",   # 全部文字（近黑）
    "line":      "#3A4A57",   # 连线/箭头
    "grid":      "#DCE2E7",   # 网格/辅助细线
    "muted":     "#6B7A88",   # 注释/note 文字
    # 语义强调族（只作描边或浅 tint 底；每图 ≤1 语义用途）
    "accent":       "#B5663D",  # 强调结果/关键对象（赭橙）
    "accent_tint":  "#E7D2BD",
    "risk":         "#9E4337",  # 故障/风险（暗砖红）
    "risk_tint":    "#E5CFC9",
    "success":      "#4F7A5B",  # 正常/有效（灰绿）
    "success_tint": "#CFE0D2",
}
# warning 与 accent 同值（语义别名，避免色相膨胀）
COLOR_PALETTE["warning"] = COLOR_PALETTE["accent"]

# 语义映射：角色 → (描边, 填充, 文字)。同一语义跨图恒定（VIS-06 机检依据）。
SEMANTIC_COLORS = {
    "top_event":      ("primary", "fill", "text"),      # 故障树顶事件
    "gate":           ("secondary", "fill", "text"),   # 中间事件/门
    "basic_event":    ("neutral", "bg", "text"),       # 底事件（白底+灰描边）
    "main_flow":      ("primary", "fill", "text"),     # 技术路线主干
    "stage":          ("secondary", "fill_alt", "text"),
    "series_main":    ("primary", "primary", "text"),  # 统计主系列（柱/线）
    "series_alt":     ("secondary", "secondary", "text"),
    "series_muted":   ("neutral", "neutral", "text"),
    "highlight":      ("accent", "accent_tint", "text"),   # 强调结果（每图≤1）
    "risk":           ("risk", "risk_tint", "text"),       # 故障/风险强调
    "valid":          ("success", "success_tint", "text"), # 正常/通过
    "annotation":     ("muted", "bg", "muted"),
    "connector":      ("line", None, "text"),
    "grid":           ("grid", None, "muted"),
}

# ---------------- B. Typography ----------------
# 字号=生成时 pt；有效字号=×(显示宽/生成宽)，VIS-03/GQ-09 按 ≥9pt 底线判。
TYPOGRAPHY = {
    "family_cjk": "SimHei",            # 中文（黑体族，与论文宋体正文区分但全图系统一）
    "family_latin": "Times New Roman",  # 西文/数字（与正文配套）
    "fallback_chain": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
    "scale": {                          # 字阶（生成 pt；full_width 显示缩放 0.873 后
                                        # 最小档 XS 有效=10.5×0.873≈9.17 ≥9.0 底线）
        "XL": 14.0,   # 图内主标题/顶事件
        "L": 12.5,    # 节点主标签/轴标题
        "M": 11.5,    # 常规节点/刻度
        "S": 11.0,    # 图例/数值标签
        "XS": 10.5,   # 注释/note（有效≈9.2pt，底线 9.0，SKILL 18.3）
    },
    "min_effective_pt": 9.0,
    "caption_pt": 10.5,                 # 题注（docx 层，宋体，与表题统一）
}

def get_text_style(role="M"):
    """返回 {family_cjk, family_latin, size, min_effective}；role ∈ scale 键。"""
    sc = TYPOGRAPHY["scale"]
    if role not in sc:
        raise KeyError(f"未知字阶 {role!r}（可用 {sorted(sc)}）")
    return {"family_cjk": TYPOGRAPHY["family_cjk"],
            "family_latin": TYPOGRAPHY["family_latin"],
            "size": sc[role], "min_effective": TYPOGRAPHY["min_effective_pt"]}

# ---------------- E. Line ----------------
LINE_STYLES = {
    "width": 1.1,            # 常规连线 pt
    "width_emphasis": 1.6,   # 强调路径
    "color": COLOR_PALETTE["line"],
    "arrow_mutation": 12,
    "dash_cycle": (4.0, 2.4),
    "series_dashes": ["solid", "dashed", "dotted", "dashdot"],  # 线型双编码（灰度可辨）
    "series_markers": ["o", "s", "^", "D"],
}

# ---------------- C/D. Spacing & Geometry ----------------
SPACING = {
    "node_pad_x": 0.25, "node_pad_y": 0.14,      # cm
    "gap_h": 0.55, "gap_v": 0.70,                # 同层/层间最小距
    "figure_margin": 0.45,                        # 图内四周留白
    "label_pad": 0.08,                            # 文本距框边安全区
    "legend_gap": 0.15, "annotation_offset": 0.2,
    "connector_clearance": 0.06,                  # 连线距文本/框安全区
    "max_nodes": 12, "max_ink_ratio": 0.45, "max_text_coverage": 0.55,
}

# ---------------- H. Figure Size ----------------
# 版心 16.5cm（A4 中飞院实测）；生成宽=显示宽/缩放，保证有效字号。
FIGURE_SIZE_PRESETS = {
    "full_width":  {"gen_w_cm": 16.5, "display_w_cm": 14.4, "max_h_cm": 9.5},
    "half_width":  {"gen_w_cm": 11.0, "display_w_cm": 9.6, "max_h_cm": 8.0},
    "tall":        {"gen_w_cm": 12.5, "display_w_cm": 11.0, "max_h_cm": 12.5},
    "dpi": 220,
    "aspect_range": (0.6, 2.2),
}

def get_figure_size(preset="full_width"):
    if preset not in FIGURE_SIZE_PRESETS:
        raise KeyError(f"未知尺寸预设 {preset!r}")
    p = FIGURE_SIZE_PRESETS[preset]
    if preset == "dpi":
        return p
    scale = p["display_w_cm"] / p["gen_w_cm"]
    return {**p, "scale": scale}

# ---------------- I. Figure Types ----------------
FIGURE_TYPES = {
    "fault_tree":      {"max_nodes": 12, "max_gates": 6, "layers": 3,
                        "critical": ["and_or_noncolor_encoding", "no_crossing",
                                     "layers_complete"]},
    "flow":            {"max_nodes": 12, "direction": "vertical"},
    "tech_route":      {"max_nodes": 14, "direction": "vertical"},
    "stat_bar":        {"max_categories": 10, "critical": ["y_axis_zero",
                                                           "single_hue_fill"]},
    "stat_line":       {"max_series": 4, "critical": ["no_y_truncation"]},
    "decision_matrix": {"max_cells": 16, "critical": ["shared_scale"]},
    "architecture":    {"max_nodes": 14, "layers": 4},
    "comparison":      {"critical": ["shared_scale"]},
    "framework":       {"max_nodes": 14, "critical": ["nodes_subset_registry"]},
}

# ---------------- 度量纯函数（QA 与固化验证共用） ----------------
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def _chan(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def luminance(hex_color):
    r, g, b = _rgb(hex_color)
    return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)

def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def grayscale_delta(a, b):
    return abs(luminance(a) - luminance(b))

def saturation(hex_color):
    r, g, b = [c / 255.0 for c in _rgb(hex_color)]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return 0.0
    return (mx - mn) / (1 - abs(mx + mn - 1)) if (mx + mn) < 1 else (mx - mn) / (2 - mx - mn)

def hue_of(hex_color):
    import colorsys
    r, g, b = [c / 255.0 for c in _rgb(hex_color)]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return round(h * 360), round(s, 2), round(v, 2)

# 固化阈值（与 04-VIS spec 同源；validate_palette 与 VIS-QA 共用）
STYLE_THRESHOLDS = {
    "text_on_fill_min": 4.5,       # WCAG 正文
    "border_on_bg_min": 3.0,       # 非文本要素
    "adjacent_fill_gray_min": 0.12,  # 相邻填充区域灰度分离
    "saturation_max_neutral": 0.45,
    "saturation_max_accent": 0.55,
    "hue_budget_fills": 3,
}

def validate_palette():
    """对 COLOR_PALETTE 跑全部固化阈值，返回违规清单（空=通过）。
    任何调色板改动必须此函数返回 [] 才允许固化（§三：不达标不得直接固化）。"""
    P, T = COLOR_PALETTE, STYLE_THRESHOLDS
    bad = []
    for fill in ("fill", "fill_alt", "accent_tint", "risk_tint", "success_tint"):
        if contrast_ratio(P["text"], P[fill]) < T["text_on_fill_min"]:
            bad.append(f"text on {fill} {contrast_ratio(P['text'], P[fill]):.2f}"
                       f"<{T['text_on_fill_min']}")
    for border in ("primary", "secondary", "line", "accent", "risk", "success", "muted"):
        if contrast_ratio(P[border], P["fill"]) < T["border_on_bg_min"]:
            bad.append(f"{border} on fill {contrast_ratio(P[border], P['fill']):.2f}"
                       f"<{T['border_on_bg_min']}")
    if contrast_ratio(P["neutral"], P["bg"]) < T["border_on_bg_min"]:
        bad.append("neutral on bg <3.0（只允许白底描边）")
    for tint in ("accent_tint", "risk_tint", "success_tint"):
        if grayscale_delta(P["fill"], P[tint]) < T["adjacent_fill_gray_min"]:
            bad.append(f"fill vs {tint} gray {grayscale_delta(P['fill'], P[tint]):.3f}"
                       f"<{T['adjacent_fill_gray_min']}")
    # fill 必须与白底可分（否则"节点有底"退化为无底——COL-04 负例暴露的盲区）
    if grayscale_delta(P["fill"], P["bg"]) < T["adjacent_fill_gray_min"]:
        bad.append(f"fill vs bg gray {grayscale_delta(P['fill'], P['bg']):.3f}"
                   f"<{T['adjacent_fill_gray_min']}（填充底与白底不可分）")
    for k in ("fill", "fill_alt", "primary", "secondary", "neutral", "text",
              "line", "grid", "muted", "success", "success_tint"):
        if saturation(P[k]) > T["saturation_max_neutral"]:
            bad.append(f"{k} saturation {saturation(P[k]):.2f}>{T['saturation_max_neutral']}")
    for k in ("accent", "risk", "accent_tint", "risk_tint"):
        if saturation(P[k]) > T["saturation_max_accent"]:
            bad.append(f"{k} saturation {saturation(P[k]):.2f}>{T['saturation_max_accent']}")
    return bad


def get_semantic_color(role, part="stroke"):
    """part ∈ stroke/fill/text。未知角色直接报错——禁止静默兜底色。"""
    if role not in SEMANTIC_COLORS:
        raise KeyError(f"未登记的语义角色 {role!r}（可用 {sorted(SEMANTIC_COLORS)}）")
    idx = {"stroke": 0, "fill": 1, "text": 2}[part]
    v = SEMANTIC_COLORS[role][idx]
    return None if v is None else COLOR_PALETTE[v]


def apply_academic_style(matplotlib_rc=False):
    """返回统一样式 dict；matplotlib_rc=True 时同步 rcParams（字体链/字号/线宽/颜色），
    消灭 provider 各自 rcParams 漂移。"""
    style = {
        "font_family": TYPOGRAPHY["fallback_chain"],
        "font_sizes": TYPOGRAPHY["scale"],
        "line": LINE_STYLES,
        "spacing": SPACING,
        "palette": COLOR_PALETTE,
        "dpi": FIGURE_SIZE_PRESETS["dpi"],
    }
    if matplotlib_rc:
        try:
            import matplotlib
            matplotlib.rcParams.update({
                "font.sans-serif": TYPOGRAPHY["fallback_chain"],
                "font.family": "sans-serif",
                "axes.unicode_minus": False,
                "figure.dpi": FIGURE_SIZE_PRESETS["dpi"],
                "savefig.dpi": FIGURE_SIZE_PRESETS["dpi"],
                "axes.edgecolor": COLOR_PALETTE["line"],
                "axes.labelcolor": COLOR_PALETTE["text"],
                "xtick.color": COLOR_PALETTE["text"],
                "ytick.color": COLOR_PALETTE["text"],
                "grid.color": COLOR_PALETTE["grid"],
                "lines.solid_capstyle": "round",
            })
        except ImportError:
            pass
    return style


# ---------------- 源码散写扫描（STY-INT-01 用） ----------------
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")

def scan_hardcoded_styles(paths):
    """返回 [(file, line_no, snippet)]：figure 模块中散写的 HEX 字面量。
    规则：命中 #RRGGBB 即违规，除非 (a) 本模块 figure_style.py 自身、
    (b) tests/、golden 配置、(c) 该 hex 出现在注释行（strip 后以 # 开头）。
    注意：不能按 '#' split 去注释——那会连同 #RRGGBB 一起切掉，导致漏检。"""
    hits = []
    for p in paths:
        norm = p.replace("\\", "/")
        if norm.endswith("figure_style.py") or "/tests/" in norm or "golden" in norm:
            continue
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if not _HEX_RE.search(ln):
                continue
            stripped = ln.strip()
            if stripped.startswith("#"):          # 整行注释：允许（文档/说明）
                continue
            # 行内：# 前是代码且出现 hex 字面量 → 违规
            hits.append((p, i, stripped[:70]))
    return hits
