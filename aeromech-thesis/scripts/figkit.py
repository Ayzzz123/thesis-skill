# -*- coding: utf-8 -*-
"""figkit.py — 论文示意图绘制工具包（GRAPHICAL_READABILITY_FIRST）
输出 PNG + layout JSON（框/边/文本 bbox，厘米坐标），供 graph_quality_qa 做几何检查。"""
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

for _fp in [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]:
    try:
        font_manager.fontManager.addfont(_fp)
    except Exception:
        pass
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
F_CN = "SimHei"
W = 16.5


class Fig:
    def __init__(self, h_cm, dpi=220):
        self.h = h_cm
        self.dpi = dpi
        self.fig = plt.figure(figsize=(W / 2.54, h_cm / 2.54), dpi=dpi)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(0, h_cm)
        self.ax.axis("off")
        self.boxes = []
        self.edges = []
        self.texts = []

    def box(self, bid, x, y, w, h, lines, fs_main=11, fs_sub=10, layer=None, fc="#eef2fa"):
        ax = self.ax
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.02,rounding_size=0.10",
                     facecolor=fc, edgecolor="#4a6fa5", lw=1.0))
        tb = None
        if len(lines) == 1:
            tb = ax.text(x + w / 2, y + h / 2, lines[0], ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color="#1a1a1a")
        else:
            tb = ax.text(x + w / 2, y + h / 2, "\n".join(lines), ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color="#1a1a1a", linespacing=1.5)
        self.boxes.append({"id": bid, "x": x, "y": y, "w": w, "h": h,
                           "layer": layer, "text": "\n".join(lines)})
        self._text_records = getattr(self, "_text_records", [])
        self._text_records.append((bid, tb, fs_main))
        return (x, y, w, h)

    def box2(self, bid, x, y, w, h, main, sub=None, fs_main=11, fs_sub=9.5,
             layer=None, fc="#eef2fa"):
        """主+副双级文本框（副文本略小），两段文本分别记录 bbox 供几何检查。"""
        ax = self.ax
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.02,rounding_size=0.10",
                     facecolor=fc, edgecolor="#4a6fa5", lw=1.0))
        self._text_records = getattr(self, "_text_records", [])
        if sub:
            t1 = ax.text(x + w / 2, y + h * 0.66, main, ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color="#1a1a1a")
            t2 = ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
                         fontsize=fs_sub, family=F_CN, color="#333333")
            self._text_records.append((bid, t1, fs_main))
            self._text_records.append((bid, t2, fs_sub))
        else:
            t1 = ax.text(x + w / 2, y + h / 2, main, ha="center", va="center",
                         fontsize=fs_main, family=F_CN, color="#1a1a1a")
            self._text_records.append((bid, t1, fs_main))
        self.boxes.append({"id": bid, "x": x, "y": y, "w": w, "h": h,
                           "layer": layer, "text": main + (("\n" + sub) if sub else "")})
        return (x, y, w, h)

    def note(self, text, x, y, fs=9.5, color="#444444"):
        tb = self.ax.text(x, y, text, fontsize=fs, family=F_CN, color=color)
        self._text_records = getattr(self, "_text_records", [])
        self._text_records.append(("__note__", tb, fs))
        return tb

    def arrow(self, eid, x1, y1, x2, y2, ls="-", lw=1.2):
        ax = self.ax
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                     mutation_scale=12, lw=lw, color="#333333", linestyle=ls,
                     shrinkA=0, shrinkB=0))
        self.edges.append({"id": eid, "pts": [[x1, y1], [x2, y2]]})

    def arrow_poly(self, eid, pts, ls="-", lw=1.2):
        """折线路由（多点），末端带箭头；用于绕行不穿节点。"""
        ax = self.ax
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs[:-1] + [pts[-1][0]], ys[:-1] + [pts[-1][1]],
                ls=ls, lw=lw, color="#333333", solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(tuple(pts[-2]), tuple(pts[-1]), arrowstyle="-|>",
                     mutation_scale=12, lw=lw, color="#333333", linestyle=ls,
                     shrinkA=0, shrinkB=0))
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
                "min_font_pt": min_font, "layers": layers or {}}
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
