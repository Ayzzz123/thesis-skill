# -*- coding: utf-8 -*-
"""make_golden_samples.py — v1.6.5 §十三：生成 4 类 golden figure samples

目的：视觉系统基线（style/palette/typography/layout 一致性参照 + 视觉回归输入）。
样张内容全部为**演示性合成数据**（与任何真实论文无关；模拟标签如实标注），
版式严格守 figure_style.SPACING（边距/间距/字阶/语义色）——golden 必须自身
通过 figure_visual_qa（无 FAIL），否则不得作为基线。

运行：python tests/v1_6_5/make_golden_samples.py
输出：tests/v1_6_5/golden/*.png + *.layout.json + golden-manifest.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import figure_style as ST
import figkit

for _fp in [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]:
    try:
        font_manager.fontManager.addfont(_fp)
    except Exception:
        pass
OUT = os.path.join(HERE, "golden")
os.makedirs(OUT, exist_ok=True)
M = ST.SPACING["figure_margin"]          # 0.45cm 边距（VIS-07）
W = 16.5


def fault_tree():
    """T = (A∨B) ∨ (C∧D)：三层、左右平衡、E*绕行改内部路由。"""
    f = figkit.Fig(9.2)
    top = (W / 2 - 2.0, 7.3, 4.0, 1.0)
    g1 = (2.6, 4.9, 3.6, 1.0)
    g2 = (10.3, 4.9, 3.6, 1.0)
    f.box("T", *top, ["T 系统功能丧失"], role="top_event", layer=2)
    f.box("G1", *g1, ["G1 动力中断（OR）"], role="gate", layer=1)
    f.box("G2", *g2, ["G2 传输保压失效", "（AND）"], role="gate", layer=1)
    be_y, be_h, be_w = 2.6, 1.0, 3.3
    xs = [M, M + 4.1, M + 8.2, M + 12.3]   # 4×3.3 宽 + 0.8 间隙，左右对称
    f.box("A", xs[0], be_y, be_w, be_h, ["A 主泵磨损内泄"], role="basic_event", layer=0)
    f.box("B", xs[1], be_y, be_w, be_h, ["B 备用电机故障"], role="basic_event", layer=0)
    f.box("C", xs[2], be_y, be_w, be_h, ["C 选择阀卡滞"], role="basic_event", layer=0)
    f.box("D", xs[3], be_y, be_w, be_h, ["D 蓄压瓶破裂"], role="basic_event", layer=0)
    GAP = 0.07
    def edge(p, c):
        px, py, pw, ph = p; cx, cy, cw, ch = c
        f.arrow(f"{cx:.0f}", px + pw / 2, py - GAP, cx + cw / 2, cy + ch + GAP)
    edge(top, g1); edge(top, g2); edge(g1, (xs[0], be_y, be_w, be_h))
    edge(g1, (xs[1], be_y, be_w, be_h)); edge(g2, (xs[2], be_y, be_w, be_h))
    edge(g2, (xs[3], be_y, be_w, be_h))
    f.note("【示意图·合成逻辑】仅演示版式规范，非任何真实机型模型", M + 0.02, M + 0.14, fs=ST.TYPOGRAPHY["scale"]["XS"])
    f.save(OUT, "golden_fault_tree", min_font=ST.TYPOGRAPHY["scale"]["M"])


def stat_bar():
    """柱状 golden：minimal（仅左/底 spine）、单色系、柱顶数值、y 轴从 0。"""
    P = ST.COLOR_PALETTE
    S = ST.TYPOGRAPHY["scale"]
    data = [("MC-1", 35), ("MC-2", 23), ("MC-3", 14), ("MC-4", 12), ("MC-5", 19), ("MC-6", 17)]
    f = figkit.Fig(9.0)
    axr = (M + 0.9, M + 0.95, W - M - 0.3, 7.4)   # axes_rect cm（左界留刻度带/下界留轴标题带）
    ax = f.ax
    vmax = 40.0
    # 左/底 spine（minimal：无顶/右框）
    ax.plot([axr[0], axr[0]], [axr[1], axr[3]], lw=1.1, color=P["line"])
    ax.plot([axr[0], axr[2]], [axr[1], axr[1]], lw=1.1, color=P["line"])
    ylab, bars = [], []
    for v in range(0, 41, 10):
        y = axr[1] + v / vmax * (axr[3] - axr[1])
        ax.plot([axr[0] - 0.06, axr[0]], [y] * 2, lw=0.8, color=P["line"])
        t = ax.text(axr[0] - 0.18, y, str(v), ha="right", va="center",
                    fontsize=S["M"], family=ST.TYPOGRAPHY["family_cjk"], color=P["text"])
        f._text_records.append(("__note__", t, S["M"]))
        ylab.append({"bbox": [0, 0, 0, 0]})   # 占位，save 后回填
    slots = (axr[2] - axr[0]) / len(data)
    xlabels = []
    for i, (k, n) in enumerate(data):
        cx = axr[0] + (i + 0.5) * slots
        top_y = axr[1] + n / vmax * (axr[3] - axr[1])
        ax.add_patch(plt.Rectangle((cx - 0.62, axr[1]), 1.24, top_y - axr[1],
                     facecolor=P["fill"], edgecolor=P["primary"], lw=1.0))
        bars.append({"id": k, "bbox": [round(cx - 0.62, 3), round(axr[1], 3),
                                       round(cx + 0.62, 3), round(top_y, 3)],
                     "color": P["primary"], "value": n})
        t = ax.text(cx, top_y + 0.16, str(n), ha="center", va="bottom",
                    fontsize=S["S"], family=ST.TYPOGRAPHY["family_cjk"], color=P["text"])
        f._text_records.append(("__note__", t, S["S"]))
        t2 = ax.text(cx, axr[1] - 0.34, k, ha="center", va="top",
                     fontsize=S["S"], family=ST.TYPOGRAPHY["family_cjk"], color=P["text"])
        f._text_records.append(("__note__", t2, S["S"]))
    ax.text((axr[0] + axr[2]) / 2, M + 0.42, "类别（演示口径）", ha="center", va="top",
            fontsize=S["M"], family=ST.TYPOGRAPHY["family_cjk"], color=P["text"])
    f.note("【假设/模拟·仅演示方法】构造数据，不代表真实统计", M + 0.02, 7.95, fs=S["XS"])
    f.save(OUT, "golden_stat_bar", min_font=S["S"],
           extra_meta={"axes_rect": [round(v, 3) for v in axr], "bars": bars})


def tech_route():
    """技术路线 golden：单列主链 5 框 + 等距垂直箭头。"""
    f = figkit.Fig(9.0)
    steps = ["系统抽象【假设】", "故障树建模", "最小割集求解", "检查序列映射", "策略决策矩阵"]
    bw, bh = 6.0, 1.0
    x = W / 2 - bw / 2
    ys = [7.4 - i * 1.62 for i in range(len(steps))]
    for i, (s, y) in enumerate(zip(steps, ys)):
        f.box(f"S{i+1}", x, y, bw, bh, [f"{i+1} {s}"],
              role="main_flow" if i == 0 else "stage", layer=len(ys) - i)
        if i < len(steps) - 1:
            f.arrow(f"e{i+1}", W / 2, y - 0.07, W / 2, ys[i + 1] + bh + 0.07)
    f.note("【示意图·合成流程】仅演示版式规范", M + 0.02, M + 0.14, fs=ST.TYPOGRAPHY["scale"]["XS"])
    f.save(OUT, "golden_tech_route", min_font=ST.TYPOGRAPHY["scale"]["M"])


def stat_line():
    """折线 golden：左/底 spine、双系列（线型+标记双编码，不靠颜色区分）、y 轴从 0。"""
    P = ST.COLOR_PALETTE
    S = ST.TYPOGRAPHY["scale"]
    f = figkit.Fig(9.0)
    axr = (M + 0.9, M + 0.95, W - M - 0.3, 7.4)
    ax = f.ax
    ax.plot([axr[0], axr[0]], [axr[1], axr[3]], lw=1.1, color=P["line"])
    ax.plot([axr[0], axr[2]], [axr[1], axr[1]], lw=1.1, color=P["line"])
    xs = [0, 200, 400, 600, 800, 1000]
    s1 = [1.0, 0.86, 0.71, 0.55, 0.42, 0.30]      # 演示曲线 A
    s2 = [1.0, 0.92, 0.83, 0.72, 0.60, 0.48]      # 演示曲线 B
    def to_xy(i, v):
        x = axr[0] + xs[i] / 1000 * (axr[2] - axr[0])
        y = axr[1] + v * (axr[3] - axr[1])
        return x, y
    lines_meta = []
    for sid, series, ls, mk, role in (("A", s1, "-", "o", "series_main"),
                                       ("B", s2, "--", "s", "series_alt")):
        pts = [to_xy(i, v) for i, v in enumerate(series)]
        col = ST.get_semantic_color(role, "stroke")
        f.polyline(f"L{sid}", pts, color=col, ls=ls, marker=mk)
        lines_meta.append({"id": f"line_{sid}", "color": col, "dash": ls,
                           "marker": mk, "points": [[round(x, 2), round(y, 2)] for x, y in pts]})
        lx, ly = pts[-2]
        t = ax.text(lx, ly + 0.28, f"系列{sid}", ha="center", va="bottom",
                    fontsize=S["S"], family=ST.TYPOGRAPHY["family_cjk"], color=P["text"])
        f._text_records.append(("__note__", t, S["S"]))
    ax.text((axr[0] + axr[2]) / 2, M + 0.42, "时间（演示单位）", ha="center", va="top",
            fontsize=S["M"], family=ST.TYPOGRAPHY["family_cjk"], color=P["text"])
    f.note("【假设/模拟·仅演示方法】构造曲线，不代表真实数据", M + 0.02, 7.95, fs=S["XS"])
    f.save(OUT, "golden_stat_line", min_font=S["S"],
           extra_meta={"axes_rect": [round(v, 3) for v in axr], "lines": lines_meta})


def main():
    fault_tree(); stat_bar(); tech_route(); stat_line()
    manifest = {"version": "v1.6.5", "style_source": "figure_style",
                "samples": [
                    {"name": "golden_fault_tree", "type": "fault_tree"},
                    {"name": "golden_stat_bar", "type": "stat_bar"},
                    {"name": "golden_tech_route", "type": "tech_route"},
                    {"name": "golden_stat_line", "type": "stat_line"}]}
    with open(os.path.join(OUT, "golden-manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print("golden samples written to", OUT)


if __name__ == "__main__":
    main()
