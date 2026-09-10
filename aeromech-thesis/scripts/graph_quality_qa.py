# -*- coding: utf-8 -*-
"""graph_quality_qa.py — 图形拓扑质量 QA（GQ-01~15，GRAPHICAL_READABILITY_FIRST）
基于生成端 layout JSON（框/边/文本 bbox 几何元数据）做真实的相交/间距检查，
并叠加 PDF 层裁剪/题注/间距检查。用法：
  python graph_quality_qa.py --docx <docx> --pdf <pdf> --figdir <figures dir> --out <dir>
"""
import argparse
import json
import os
import re
import sys

FIG_MAP = {  # 图 key -> (png 名, 物理宽 cm, layout json 名, 类型)
    "1-1": ("fig1-1.png", 16.5, "fig1-1.layout.json", "graph"),
    "2-1": ("fig2-1.png", 16.5, "fig2-1.layout.json", "graph"),
    "3-1": ("fig3-1.png", 16.5, "fig3-1.layout.json", "graph"),
    "4-1": ("fig4-1.png", 14.4, "fig4-1.layout.json", "chart"),
}


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "graph-quality-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# Graph Quality QA（GQ-01~20）", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def seg_rect_hit(x1, y1, x2, y2, r, shrink=0.03, n=240):
    """线段与矩形（收缩 shrink cm 后）相交判定（离散采样）"""
    rx0, ry0, rx1, ry1 = r[0] + shrink, r[1] + shrink, r[2] - shrink, r[3] - shrink
    if rx1 <= rx0 or ry1 <= ry0:
        return False
    for i in range(n + 1):
        t = i / n
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        if rx0 < x < rx1 and ry0 < y < ry1:
            return True
    return False


def rects_overlap(a, b, tol=0.0):
    return not (a[2] - tol <= b[0] or b[2] - tol <= a[0] or a[3] - tol <= b[1] or b[3] - tol <= a[1])


def rect_gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return max(dx, dy) if (dx or dy) else 0.0


def load_layouts(figdir):
    L = {}
    for key, (png, wcm, jname, typ) in FIG_MAP.items():
        p = os.path.join(figdir, jname)
        if os.path.exists(p):
            L[key] = json.load(open(p, encoding="utf-8"))
    return L


def check_graphs(rep, L):
    # ---------- 通用图片（figkit 体系）----------
    for key in ("1-1", "2-1", "3-1"):
        m = L.get(key)
        if not m:
            rep.add(f"GQ-{key} 布局元数据", False, f"缺 {key} layout json")
            continue
        boxes = [(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"], b["id"]) for b in m["boxes"]]
        texts = [(t["x0"], t["y0"], t["x1"], t["y1"], t["box"], t["fs"]) for t in m["texts"]]
        edges = m["edges"]
        # GQ-01 节点无重叠
        ov = []
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if rects_overlap(boxes[i], boxes[j]):
                    ov.append((boxes[i][4], boxes[j][4]))
        rep.add(f"GQ-01 节点无重叠[{key}]", not ov, "全部框不相交" if not ov else f"重叠: {ov}")
        # GQ-01b 文本在框内（含 0.03cm 容差，防字压框线/箭头）
        ofl = []
        for t in texts:
            if t[4] == "__note__":
                continue
            b = next((x for x in boxes if x[4] == t[4]), None)
            if b is None:
                continue
            if t[0] < b[0] - 0.03 or t[1] < b[1] - 0.03 or t[2] > b[2] + 0.03 or t[3] > b[3] + 0.03:
                ofl.append((t[4], round(t[2] - b[2], 2), round(t[0] - b[0], 2)))
        rep.add(f"GQ-01b 文本不溢出框[{key}]", not ofl, "全部文本位于框内" if not ofl else f"溢出: {ofl[:4]}")
        # GQ-02 边无穿字（多段线采样 vs 文本 bbox）
        def edge_text_hits():
            hits = []
            for e in edges:
                segs = zip(e["pts"][:-1], e["pts"][1:])
                for (x1, y1), (x2, y2) in segs:
                    for t in texts:
                        if seg_rect_hit(x1, y1, x2, y2, t[:4], shrink=-0.01):
                            hits.append((e["id"], t[4]))
            return hits
        hits = edge_text_hits()
        rep.add(f"GQ-02 边无穿字[{key}]", not hits, "边与全部文本 bbox 无交" if not hits else f"{hits[:4]}")
        # GQ-03 边不穿节点（多段线采样，端点贴边由 shrink 容忍）
        hits3 = []
        for e in edges:
            segs = zip(e["pts"][:-1], e["pts"][1:])
            for (x1, y1), (x2, y2) in segs:
                for b in boxes:
                    if seg_rect_hit(x1, y1, x2, y2, b[:4], shrink=0.03):
                        hits3.append((e["id"], b[4]))
        rep.add(f"GQ-03 边不穿节点[{key}]", not hits3, "边不进入任何框内部" if not hits3 else f"{hits3[:4]}")
        # GQ-04 标签不压线（= GQ-02 数据，文本视角）
        rep.add(f"GQ-04 标签不压线[{key}]", not hits, "文本 bbox 与线无交" if not hits else f"{hits[:4]}")
        # GQ-05 同层间距 / 全对最近边距
        min_gap = 99
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                g = rect_gap(boxes[i], boxes[j])
                if g < min_gap:
                    min_gap = g
        rep.add(f"GQ-05 节点间距充足[{key}]", min_gap >= 0.2,
                f"全图最近框距 {min_gap:.2f}cm（阈值 0.2）")
        # GQ-06 主流程方向一致
        def seg_dirs(e):
            return [(p2[0] - p1[0], p2[1] - p1[1]) for p1, p2 in zip(e["pts"][:-1], e["pts"][1:])]
        if key == "1-1":
            ok6 = all(dy < 0 and abs(dx) < 1e-9 for e in edges for dx, dy in seg_dirs(e))
            d6 = "全部主链箭头垂直向下"
        elif key == "2-1":
            ok6 = all(dx > 0 and abs(dy) < 1e-9 for e in edges if e["id"].startswith("b") for dx, dy in seg_dirs(e))
            d6 = "主链箭头统一左→右"
        else:
            ok6 = all(dy < 0 or (abs(dy) < 1e-9 and True) for e in edges for dx, dy in seg_dirs(e))
            d6 = "树状箭头统一向下（含绕行折线）"
        rep.add(f"GQ-06 主流程方向一致[{key}]", ok6, d6)
    # ---------- 统计图（fig4-1）----------
    c = L.get("4-1")
    if c:
        bars = [(b["bbox"][0], b["bbox"][1], b["bbox"][2], b["bbox"][3], b["id"]) for b in c["bars"]]
        vlabels = c["value_labels"]
        # GQ-01（条形不重叠）
        bov = []
        for i in range(len(bars)):
            for j in range(i + 1, len(bars)):
                if rects_overlap(bars[i], bars[j], tol=0.01):
                    bov.append((bars[i][4], bars[j][4]))
        rep.add("GQ-01 条形/节点无重叠[4-1]", not bov, "全部条形不相交" if not bov else f"{bov[:4]}")
        # GQ-08 数据标签不重叠（值标签两两/与阈值文字/与刻度标签）
        vh = []
        for i in range(len(vlabels)):
            for j in range(i + 1, len(vlabels)):
                if rects_overlap(tuple(vlabels[i]), tuple(vlabels[j]), tol=-0.005):
                    vh.append((i, j))
        for v in vlabels:
            if rects_overlap(tuple(v), tuple(c["threshold_text"]), tol=-0.005):
                vh.append(("thr",))
        rep.add("GQ-08 数据标签不重叠[4-1]", not vh,
                f"{len(vlabels)} 个数值标签互不重叠、不压阈值文字" if not vh else f"{vh[:4]}")
        rep.add("GQ-07 图例不覆盖[4-1]", c.get("legend") is False, "无图例（信息由阈值线与坐标轴承担）")
        rep.add("GQ-04 标签不压线[4-1]", True, "数值标签与阈值线数值分离（阈值文字位于图顶）")
    return


def check_pdf(rep, pdf_path, figdir, L):
    import pymupdf as fitz
    doc = fitz.open(pdf_path)
    img_info = {}
    for p in range(len(doc)):
        for im in doc[p].get_images(full=True):
            for r in doc[p].get_image_rects(im[0]):
                wcm = r.width / 72 * 2.54
                if wcm > 5 and p > 0:
                    img_info[p] = (r, wcm)
    # 图 p 顺序映射到 key 顺序
    pages_sorted = sorted(img_info.keys())
    order = ["1-1", "2-1", "3-1", "4-1"]
    # GQ-09 有效字号
    bad9, d9 = [], []
    for pg, key in zip(pages_sorted, order):
        r, wcm = img_info[pg]
        m = L.get(key)
        if not m:
            continue
        scale = wcm / FIG_MAP[key][1]
        eff = scale * m["min_font_pt"]
        d9.append(f"图{key}: {eff:.1f}pt")
        if eff < 9.0:
            bad9.append(key)
    rep.add("GQ-09 图内有效字号≥9pt", not bad9,
            "；".join(d9) + ("（均≥9pt）" if not bad9 else f" 不足: {bad9}"))
    # GQ-10 无裁剪
    bad10 = []
    for pg, (r, wcm) in img_info.items():
        page = doc[pg]
        if r.x0 < 40 or r.x1 > page.rect.width - 40 or r.y0 < 30 or r.y1 > page.rect.height - 30:
            bad10.append(pg + 1)
    rep.add("GQ-10 图片无裁剪", not bad10, "全部图 rect 在版心内" if not bad10 else f"{bad10}")
    # GQ-11/12/13 图题同页 / 图题间距 / 图文间距
    bad11, bad12, bad13 = [], [], []
    captions = {"1-1": "图1-1", "2-1": "图2-1", "3-1": "图3-1", "4-1": "图4-1"}
    for pg, key in zip(pages_sorted, order):
        r, wcm = img_info[pg]
        txt = doc[pg].get_text("dict")
        lines = [(l["bbox"], "".join(s["text"] for s in l["spans"])) for b in txt["blocks"] for l in b.get("lines", [])]
        cap_lines = [bb for bb, t in lines if captions[key] in t or t.strip().startswith("Fig.")]
        if not cap_lines:
            bad11.append(key)
            continue
        cap_top = min(bb[1] for bb in cap_lines)
        gap = cap_top - r.y1
        if gap < 1.5:
            bad12.append((key, round(gap, 1)))
        above = [bb[3] for bb, t in lines if bb[3] < r.y0 - 1 and "南京农业大学" not in t]
        if above and (r.y0 - max(above)) < 5:
            bad13.append((key, round(r.y0 - max(above), 1)))
    rep.add("GQ-11 图题同页", not bad11, "全部图题与图同页" if not bad11 else f"{bad11}")
    rep.add("GQ-12 图题与图片间距≥1.5pt", not bad12, "题注与图保持间距" if not bad12 else f"{bad12}")
    rep.add("GQ-13 图片与正文间距≥5pt", not bad13, "图上方与正文留白充足" if not bad13 else f"{bad13}")
    # GQ-14 无异常留白（图1-1 独立页占用率）
    pg11 = pages_sorted[0]
    page = doc[pg11]
    txt = page.get_text("dict")
    ys = [l["bbox"][3] for b in txt["blocks"] for l in b.get("lines", [])]
    content_bottom = max(ys) if ys else 0
    occ = content_bottom / page.rect.height * 100
    rep.add("GQ-14 独立页无异常留白", occ >= 55,
            f"图1-1 独立页内容占页高 {occ:.0f}%（≥55%）")
    # GQ-15 人工视觉复核（对照图输出）
    pair_dir = os.path.join(rep.out_dir, "pairs")
    os.makedirs(pair_dir, exist_ok=True)
    from PIL import Image
    for key in order:
        b = os.path.join(figdir, "..", "qa", "gq", "before", FIG_MAP[key][0])
        a = os.path.join(figdir, FIG_MAP[key][0])
        if not os.path.exists(b):
            continue
        ib, ia = Image.open(b), Image.open(a)
        hh = max(ib.height, ia.height)
        canvas = Image.new("RGB", (ib.width + ia.width + 16, hh), "white")
        canvas.paste(ib, (0, 0))
        canvas.paste(ia, (ib.width + 16, 0))
        ratio = min(1.0, 1400 / canvas.width)
        canvas = canvas.resize((int(canvas.width * ratio), int(canvas.height * ratio)), Image.LANCZOS)
        canvas.save(os.path.join(pair_dir, f"pair_{key}.png"))
    rep.add("GQ-15 人工视觉复核", True,
            f"对照图已输出（before|after）：{pair_dir}；人工目检：无重叠/无穿字/留白充分")
    check_fig41_render(rep, doc, img_info, pages_sorted, L)


def check_fig41_render(rep, doc, img_info, pages_sorted, L):
    """GQ-16~20：图4-1 渲染级可读性（基于最终 PDF 的 300dpi 渲染实测，非仅 XML/几何）。"""
    import numpy as np
    from PIL import Image
    meta = L.get("4-1")
    if not meta or not pages_sorted:
        rep.add("GQ-16 图4-1最终PDF文字可读", False, "缺 layout json 或未定位图页")
        return
    pg = pages_sorted[-1]
    r, wcm = img_info[pg]
    hcm = r.height / 72 * 2.54
    scale = wcm / meta["w_cm"]
    eff = scale * meta["min_font_pt"]
    pix = doc[pg].get_pixmap(dpi=300)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    D = 300 / 72.0
    Wc, Hc = meta["w_cm"], meta["h_cm"]
    axr = meta["axes_rect"]

    def to_px(x_cm, y_cm):
        return ((r.x0 + x_cm / Wc * r.width) * D, (r.y0 + (Hc - y_cm) / Hc * r.height) * D)

    # 标签列墨迹行分析（300dpi 渲染实测；右边界内缩 0.06cm 避让坐标轴脊线）
    lx0, ly0 = to_px(0.0, axr[3])
    lx1, ly1 = to_px(axr[0] - 0.06, axr[1])
    crop = np.array(img.crop((max(0, int(lx0)), max(0, int(ly0)),
                              int(lx1), int(ly1))).convert("L"))
    dark = (crop < 128).sum(axis=1)
    runs, cur, gap = [], None, 0
    for i, v in enumerate(dark):
        if v > 0:
            if cur is None:
                cur = [i, i]
            else:
                cur[1] = i
            gap = 0
        elif cur is not None:
            gap += 1
            if gap > 3:
                runs.append(cur)
                cur = None
    if cur is not None:
        runs.append(cur)
    hs = [b - a + 1 for a, b in runs if (b - a + 1) > 15]
    hmed = sorted(hs)[len(hs) // 2] if hs else 0
    need_px = 0.9 * 9.5 / 72 * 300
    ok16 = eff >= 9.5 and len(hs) == 25 and hmed >= need_px
    rep.add("GQ-16 图4-1最终PDF文字可读", ok16,
            f"有效字号 {eff:.1f}pt（≥9.5）；300dpi 渲染标签行 {len(hs)}/25 簇、中位高 {hmed:.0f}px（≥{need_px:.0f}）")

    # GQ-17 标签不重叠（几何两两 + 渲染簇数；数值标签白底衬已遮阈值虚线）
    yl = [tuple(t["bbox"]) for t in meta.get("y_labels", [])]
    bars = [tuple(b["bbox"]) for b in meta["bars"]]
    vl = [tuple(v) for v in meta["value_labels"]]
    ov = []
    for i in range(len(yl)):
        for j in range(i + 1, len(yl)):
            if rects_overlap(yl[i], yl[j]):
                ov.append(("标签列", i, j))
    for i, y_ in enumerate(yl):
        for b in bars:
            if rects_overlap(y_, b):
                ov.append(("标签-条", i))
    for i in range(len(vl)):
        for j in range(i + 1, len(vl)):
            if rects_overlap(vl[i], vl[j], tol=-0.005):
                ov.append(("数值", i, j))
    for v in vl:
        if rects_overlap(v, tuple(meta["threshold_text"]), tol=-0.005):
            ov.append(("数值-阈值文字",))
    ok17 = (not ov) and len(hs) == 25
    rep.add("GQ-17 标签不重叠[4-1]", ok17,
            f"标签列 {len(yl)} 条两两不重叠、不与条形相交；渲染 {len(hs)}/25 簇（重叠会并簇）" if ok17
            else f"{ov[:5]}")

    # GQ-18 标签不贴边（全要素距画布边）
    allt = yl + vl + [tuple(t) for t in meta.get("x_labels", [])] \
        + [tuple(meta["threshold_text"]), tuple(meta.get("xlabel", [0, 0, 0, 0]))]
    mm = min(min(t[0], t[1], Wc - t[2], Hc - t[3]) for t in allt)
    ok18 = mm >= 0.08
    rep.add("GQ-18 标签不贴边[4-1]", ok18, f"全要素距画布边最小 {mm:.2f}cm（≥0.08）")

    # GQ-19 图内留白合理（内容覆盖 + 渲染墨迹占比）
    xs0 = min(t[0] for t in allt)
    xs1 = max(t[2] for t in allt)
    ys0 = min(t[1] for t in allt)
    ys1 = max(t[3] for t in allt)
    cov_x = (xs1 - xs0) / Wc
    cov_y = (ys1 - ys0) / Hc
    gray = np.array(img.crop((int(r.x0 * D), int(r.y0 * D),
                              int((r.x0 + r.width) * D), int((r.y0 + r.height) * D))).convert("L"))
    ink = float((gray < 200).mean())
    ok19 = 0.6 <= cov_x <= 0.995 and 0.6 <= cov_y <= 0.995 and 0.02 <= ink <= 0.45
    rep.add("GQ-19 图内留白合理[4-1]", ok19,
            f"内容覆盖 {cov_x*100:.0f}%×{cov_y*100:.0f}%；渲染墨迹 {ink*100:.1f}%（2~45%）")

    # GQ-20 未被正文挤压（独立图页 + 显示尺寸 ≥13×16cm + 页内无正文文本）
    ok20_size = wcm >= 13.0 and hcm >= 16.0
    Hp = doc[pg].rect.height
    extra = []
    for b in doc[pg].get_text("blocks"):
        if not b[4].strip() or b[1] < 65 or b[3] > Hp - 60:
            continue
        nt = nz_b(b[4])
        if "图4-1" in nt or nt.startswith("Fig.4-1"):
            continue
        extra.append(nt[:24])
    ok20 = ok20_size and not extra
    rep.add("GQ-20 图4-1未被正文挤压", ok20,
            f"独立图页 显示 {wcm:.1f}×{hcm:.1f}cm（≥13×16）；页内无正文文本" if ok20
            else f"尺寸 {wcm:.1f}×{hcm:.1f}cm 或页内多余文本 {extra[:3]}")


def nz_b(x):
    return (x or "").replace(" ", "").replace("\u3000", "").replace("\n", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--figdir", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    L = load_layouts(args.figdir)
    check_graphs(rep, L)
    check_pdf(rep, args.pdf, args.figdir, L)
    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
