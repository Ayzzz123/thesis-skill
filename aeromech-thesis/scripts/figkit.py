# -*- coding: utf-8 -*-
"""figkit.py — 论文示意图绘制工具包（GRAPHICAL_READABILITY_FIRST → ACADEMIC_VISUAL_QUALITY_FIRST）
输出 PNG + layout JSON（框/边/文本 bbox，厘米坐标），供 graph_quality_qa 做几何检查、
figure_visual_qa 做视觉检查。

v1.6.5：样式单一来源——所有颜色/字号/线宽/边距取自 figure_style，figkit 自身不再散写 HEX。
box/box2 新增 role=（语义角色，取自 SEMANTIC_COLORS）；fc/ec/fs_* 保留为兼容覆盖参数
（旧脚本可继续显式传入），但默认值一律来自 figure_style。"""
import os
import json
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figure_style as ST

for _fp in [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]:
    try:
        font_manager.fontManager.addfont(_fp)
    except Exception:
        pass
plt.rcParams["font.sans-serif"] = ST.TYPOGRAPHY["fallback_chain"]
plt.rcParams["axes.unicode_minus"] = False
F_CN = ST.TYPOGRAPHY["family_cjk"]
W = ST.FIGURE_SIZE_PRESETS["full_width"]["gen_w_cm"]
_SC = ST.TYPOGRAPHY["scale"]


class Fig:
    def __init__(self, h_cm, dpi=None):
        self.h = h_cm
        self.dpi = dpi or ST.FIGURE_SIZE_PRESETS["dpi"]
        self.fig = plt.figure(figsize=(W / 2.54, h_cm / 2.54), dpi=self.dpi)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(0, h_cm)
        self.ax.axis("off")
        self.boxes = []
        self.edges = []
        self.texts = []

    @staticmethod
    def _role_colors(role, fc, ec):
        """role 优先（SEMANTIC 角色→palette key→HEX）；fc/ec 显式覆盖兼容旧调用；
        都无则默认 fill/primary。"""
        pal = ST.COLOR_PALETTE
        if role:
            s, f, _t = ST.SEMANTIC_COLORS[role]
            face = pal["bg"] if f is None else pal[f]
            edge = pal["bg"] if s is None else pal[s]
            return (fc or face), (ec or edge)
        return (fc or pal["fill"]), (ec or pal["primary"])

    def box(self, bid, x, y, w, h, lines, fs_main=None, fs_sub=None, layer=None,
            fc=None, ec=None, role=None):
        ax = self.ax
        fs_main = fs_main or _SC["M"]
        face, edge = self._role_colors(role, fc, ec)
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.02,rounding_size=0.10",
                     facecolor=face, edgecolor=edge, lw=ST.LINE_STYLES["width"]))
        tb = None
        tcol = ST.COLOR_PALETTE["text"]
        if len(lines) == 1:
            tb = ax.text(x + w / 2, y + h / 2, lines[0], ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color=tcol)
        else:
            tb = ax.text(x + w / 2, y + h / 2, "\n".join(lines), ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color=tcol, linespacing=1.5)
        self.boxes.append({"id": bid, "x": x, "y": y, "w": w, "h": h,
                           "layer": layer, "text": "\n".join(lines), "role": role,
                           "fill": face, "stroke": edge, "text_color": tcol})
        self._text_records = getattr(self, "_text_records", [])
        self._text_records.append((bid, tb, fs_main))
        return (x, y, w, h)

    def box2(self, bid, x, y, w, h, main, sub=None, fs_main=None, fs_sub=None,
             layer=None, fc=None, ec=None, role=None):
        """主+副双级文本框（副文本略小），两段文本分别记录 bbox 供几何检查。"""
        ax = self.ax
        fs_main = fs_main or _SC["M"]
        fs_sub = fs_sub or _SC["S"]
        face, edge = self._role_colors(role, fc, ec)
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.02,rounding_size=0.10",
                     facecolor=face, edgecolor=edge, lw=ST.LINE_STYLES["width"]))
        self._text_records = getattr(self, "_text_records", [])
        tcol = ST.COLOR_PALETTE["text"]
        if sub:
            t1 = ax.text(x + w / 2, y + h * 0.66, main, ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color=tcol)
            t2 = ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
                         fontsize=fs_sub, family=F_CN, color=ST.COLOR_PALETTE["muted"])
            self._text_records.append((bid, t1, fs_main))
            self._text_records.append((bid, t2, fs_sub))
        else:
            t1 = ax.text(x + w / 2, y + h / 2, main, ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color=tcol)
            self._text_records.append((bid, t1, fs_main))
        self.boxes.append({"id": bid, "x": x, "y": y, "w": w, "h": h,
                           "layer": layer, "text": main + (("\n" + sub) if sub else ""),
                           "role": role, "fill": face, "stroke": edge,
                           "text_color": tcol})
        return (x, y, w, h)

    def note(self, text, x, y, fs=None, color=None):
        tb = self.ax.text(x, y, text, fontsize=fs or _SC["XS"], family=F_CN,
                          color=color or ST.COLOR_PALETTE["muted"])
        self._text_records = getattr(self, "_text_records", [])
        self._text_records.append(("__note__", tb, fs or _SC["XS"]))
        return tb

    def arrow(self, eid, x1, y1, x2, y2, ls="-", lw=None):
        ax = self.ax
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                     mutation_scale=ST.LINE_STYLES["arrow_mutation"],
                     lw=lw or ST.LINE_STYLES["width"], color=ST.LINE_STYLES["color"],
                     linestyle=ls, shrinkA=0, shrinkB=0))
        self.edges.append({"id": eid, "pts": [[x1, y1], [x2, y2]]})

    def arrow_poly(self, eid, pts, ls="-", lw=None):
        """折线路由（多点），末端带箭头；用于绕行不穿节点。"""
        ax = self.ax
        lw = lw or ST.LINE_STYLES["width"]
        lc = ST.LINE_STYLES["color"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs[:-1] + [pts[-1][0]], ys[:-1] + [pts[-1][1]],
                ls=ls, lw=lw, color=lc, solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(tuple(pts[-2]), tuple(pts[-1]), arrowstyle="-|>",
                     mutation_scale=ST.LINE_STYLES["arrow_mutation"], lw=lw, color=lc,
                     linestyle=ls, shrinkA=0, shrinkB=0))
        self.edges.append({"id": eid, "pts": [[p[0], p[1]] for p in pts]})

    def save(self, outdir, name, min_font, layers=None):
        """渲染 PNG 并输出 layout JSON（文本 bbox 经 renderer 实测换算为 cm）。"""
        fig = self.fig
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
        dpi = self.dpi
        px2cm = 2.54 / dpi
        inv = self.ax.transData.inverted()
        texts = []
        for bid, tb, fs in getattr(self, "_text_records", []):
            bb_px = tb.get_window_extent(renderer=rend)
            (X0, Y0) = inv.transform((bb_px.x0, bb_px.y0))
            (X1, Y1) = inv.transform((bb_px.x1, bb_px.y1))
            texts.append({"box": bid, "x0": round(X0, 3), "y0": round(Y0, 3),
                          "x1": round(X1, 3), "y1": round(Y1, 3), "fs": fs})
        meta = {"name": name, "w_cm": W, "h_cm": self.h, "dpi": dpi,
                "boxes": self.boxes, "edges": self.edges, "texts": texts,
                "min_font_pt": min_font, "layers": layers or {},
                # v1.6.5：样式指纹（VIS-12 跨图一致性机检输入）——本图实际使用的
                # 字族/色板/线宽来源均为 figure_style 单一来源，指纹一致=同一视觉家族。
                "style_fingerprint": {
                    "family_cjk": ST.TYPOGRAPHY["family_cjk"],
                    "font_sizes_used": sorted({t["fs"] for t in texts}),
                    "palette_hex_used": sorted({v for b in self.boxes
                                                 for v in (b.get("fill"), b.get("stroke"))
                                                 if v} | {ST.LINE_STYLES["color"]}),
                    "line_width": ST.LINE_STYLES["width"],
                    "style_source": "figure_style",
                }}
        png = os.path.join(outdir, name + ".png")
        fig.savefig(png, dpi=dpi)
        final_dir = os.path.join(outdir, "final")
        os.makedirs(final_dir, exist_ok=True)
        fig.savefig(os.path.join(final_dir, name + ".png"), dpi=dpi)
        plt.close(fig)
        with open(os.path.join(outdir, name + ".layout.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        print(f"{name}.png saved: {W:.1f}x{self.h:.1f}cm, boxes={len(self.boxes)}, edges={len(self.edges)}")
        return png
