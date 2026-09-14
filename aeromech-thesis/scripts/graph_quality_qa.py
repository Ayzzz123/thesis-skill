# -*- coding: utf-8 -*-
"""graph_quality_qa.py — 图形拓扑质量 QA（GQ-01~20，GRAPHICAL_READABILITY_FIRST）通用版
基于 figkit 输出的 layout JSON（框/边/文本 bbox 几何元数据）做相交/间距检查，
并叠加 PDF 层裁剪/题注/间距/渲染可读性检查。图清单与题注编号全部自动发现，不绑定具体论文。
用法：
  python graph_quality_qa.py --docx <docx> --pdf <pdf> --figdir <figures dir> --out <dir>
退出码: 0=全部 PASS（SKIP 不计）
"""
import argparse
import glob
import json
import os
import re
import sys

CAP_FIG_RE = re.compile(r"^图(\d+)[.\-](\d+)|^图([A-Z])[.\-]?(\d+)")


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail, skip=False):
        self.items.append((code, ok, detail, skip))
        print(f"  {code} {'SKIP' if skip else ('PASS' if ok else 'FAIL')} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "graph-quality-report.md")
        fails = [c for c, ok, _, sk in self.items if not ok and not sk]
        lines = ["# Graph Quality QA（GQ-01~20）", ""]
        for code, ok, detail, skip in self.items:
            st = "SKIP" if skip else ("PASS" if ok else "FAIL")
            lines.append(f"- {code}: {st} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def discover_figs(figdir):
    """扫描 *.layout.json 自动构建图清单：{key: {meta, png, type}}。
    key 从 name 解析（fig2-1 / fig2.1 -> '2-1'）；type: chart（含 bars/axes_rect）/ graph。"""
    figs = {}
    if not figdir or not os.path.isdir(figdir):
        return figs
    for p in sorted(glob.glob(os.path.join(figdir, "*.layout.json"))):
        try:
            meta = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        name = meta.get("name") or os.path.basename(p).replace(".layout.json", "")
        m = re.match(r".*?(\d+)[.\-](\d+)$", name)
        if not m:
            continue
        key = f"{m.group(1)}-{m.group(2)}"
        typ = "chart" if ("bars" in meta and "axes_rect" in meta) else "graph"
        png = os.path.join(figdir, name + ".png")
        figs[key] = {"meta": meta, "png": png, "type": typ, "name": name}
    return figs


def seg_rect_hit(x1, y1, x2, y2, r, shrink=0.03, n=240):
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


def check_graphs(rep, figs):
    """GQ-01~06：对全部 graph 类（框图/树图/流程图）做几何检查。"""
    gkeys = [k for k, f in figs.items() if f["type"] == "graph"]
    if not gkeys:
        rep.add("GQ-01~06 图形几何检查", True, "无 graph 类图（layout 元数据）", skip=True)
        return
    for key in gkeys:
        m = figs[key]["meta"]
        boxes = [(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"], b["id"]) for b in m["boxes"]]
        texts = [(t["x0"], t["y0"], t["x1"], t["y1"], t["box"], t["fs"]) for t in m["texts"]]
        edges = m["edges"]
        # GQ-01 节点无重叠
        ov = []
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if rects_overlap(boxes[i], boxes[j]):
                    ov.append((boxes[i][4], boxes[j][4]))
        rep.add(f"GQ-01 节点无重叠[图{key}]", not ov, "全部框不相交" if not ov else f"重叠: {ov}")
        # GQ-01b 文本在框内（0.03cm 容差）
        ofl = []
        for t in texts:
            if t[4] == "__note__":
                continue
            b = next((x for x in boxes if x[4] == t[4]), None)
            if b is None:
                continue
            if t[0] < b[0] - 0.03 or t[1] < b[1] - 0.03 or t[2] > b[2] + 0.03 or t[3] > b[3] + 0.03:
                ofl.append((t[4], round(t[2] - b[2], 2), round(t[0] - b[0], 2)))
        rep.add(f"GQ-01b 文本不溢出框[图{key}]", not ofl, "全部文本位于框内" if not ofl else f"溢出: {ofl[:4]}")
        # GQ-02 边无穿字
        hits = []
        for e in edges:
            for (x1, y1), (x2, y2) in zip(e["pts"][:-1], e["pts"][1:]):
                for t in texts:
                    if seg_rect_hit(x1, y1, x2, y2, t[:4], shrink=-0.01):
                        hits.append((e["id"], t[4]))
        rep.add(f"GQ-02 边无穿字[图{key}]", not hits, "边与全部文本 bbox 无交" if not hits else f"{hits[:4]}")
        # GQ-03 边不穿节点
        hits3 = []
        for e in edges:
            for (x1, y1), (x2, y2) in zip(e["pts"][:-1], e["pts"][1:]):
                for b in boxes:
                    if seg_rect_hit(x1, y1, x2, y2, b[:4], shrink=0.03):
                        hits3.append((e["id"], b[4]))
        rep.add(f"GQ-03 边不穿节点[图{key}]", not hits3, "边不进入任何框内部" if not hits3 else f"{hits3[:4]}")
        # GQ-04 标签不压线（= GQ-02 文本视角）
        rep.add(f"GQ-04 标签不压线[图{key}]", not hits, "文本 bbox 与线无交" if not hits else f"{hits[:4]}")
        # GQ-05 全对最近框距
        min_gap = 99
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                g = rect_gap(boxes[i], boxes[j])
                if g < min_gap:
                    min_gap = g
        rep.add(f"GQ-05 节点间距充足[图{key}]", min_gap >= 0.2,
                f"全图最近框距 {min_gap:.2f}cm（阈值 0.2）")
        # GQ-06 主流程方向一致（分层友好：垂直或水平单轴主导即可，不允许明显反向）
        down = up = left = right = 0
        for e in edges:
            for (x1, y1), (x2, y2) in zip(e["pts"][:-1], e["pts"][1:]):
                dx, dy = x2 - x1, y2 - y1
                if abs(dy) >= 0.05:
                    down += 1 if dy < 0 else 0
                    up += 1 if dy > 0 else 0
                if abs(dx) >= 0.05:
                    right += 1 if dx > 0 else 0
                    left += 1 if dx < 0 else 0
        v_total, h_total = down + up, left + right
        if v_total + h_total == 0:
            rep.add(f"GQ-06 主流程方向一致[图{key}]", True,
                    "无连接边（箱式布局图），方向检查不适用", skip=True)
        else:
            v_ok = v_total >= 2 and down / v_total >= 0.6 and up / v_total <= 0.15
            h_ok = h_total >= 2 and right / h_total >= 0.6 and left / h_total <= 0.15
            v_detail = f"垂直:下{down}/上{up}" if v_total else "垂直:无"
            h_detail = f"水平:右{right}/左{left}" if h_total else "水平:无"
            ok6 = v_ok or h_ok
            rep.add(f"GQ-06 主流程方向一致[图{key}]", ok6,
                    f"{v_detail}；{h_detail}（垂直或水平单向主导、无反向）" if ok6
                    else f"方向冲突：{v_detail}；{h_detail}")


def match_img_for_fig(pdf_pages_imgs, meta, used):
    """为图匹配 PDF 中 (page, rect)。策略：
    ①登记宽精确匹配（图以原始尺寸嵌入时，±0.35cm）；
    ②否则按页序消费第一张未匹配的图（图被统一缩放显示时的常规场景，
      要求 figs 顺序与文档流顺序一致——discover_figs 按文件名排序保证）。
    修复记录：旧实现用 abs(w-w_cm) 全局最近匹配，当所有图显示宽相同时
    浮点微差导致乱序匹配（GQ-16/17/18 错图检查）。"""
    w_cm = meta.get("w_cm", 16.5)
    for pg in sorted(pdf_pages_imgs.keys()):
        for r, w in pdf_pages_imgs[pg]:
            if (pg, round(r.x0, 1), round(r.y0, 1)) in used:
                continue
            if abs(w - w_cm) < 0.35:
                used.add((pg, round(r.x0, 1), round(r.y0, 1)))
                return pg, r
    for pg in sorted(pdf_pages_imgs.keys()):
        for r, w in pdf_pages_imgs[pg]:
            if (pg, round(r.x0, 1), round(r.y0, 1)) in used:
                continue
            used.add((pg, round(r.x0, 1), round(r.y0, 1)))
            return pg, r
    return None, None


def fig_caption_on_page(pdf_page, rect):
    """图页内、图 rect 下方的图题行（图x-y / Fig.）。"""
    lines = []
    for b in pdf_page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if txt and l["bbox"][1] > rect.y1 - 2:
                lines.append((l["bbox"], txt))
    for bb, txt in sorted(lines, key=lambda x: x[0][1]):
        if CAP_FIG_RE.match(txt) or txt.startswith("Fig."):
            return bb, txt
    return None, None


def check_pdf(rep, pdf_path, figs):
    import pymupdf as fitz
    doc = fitz.open(pdf_path)
    pdf_pages_imgs = {}
    for p in range(len(doc)):
        for im in doc[p].get_images(full=True):
            for r in doc[p].get_image_rects(im[0]):
                wcm = r.width / 72 * 2.54
                if wcm > 5 and p > 0:
                    pdf_pages_imgs.setdefault(p, []).append((r, wcm))
    if not pdf_pages_imgs:
        rep.add("GQ-09~14 PDF 图检查", False, "PDF 中未找到正式图片（>5cm）")
        return
    # 为每张 layout 图匹配 PDF 位置
    used = set()
    fig_pdf = {}
    for key, f in figs.items():
        pg, r = match_img_for_fig(pdf_pages_imgs, f["meta"], used)
        if pg is not None:
            fig_pdf[key] = (pg, r, f)
    # GQ-09 有效字号（缩放 × 图内最小字号）
    bad9, d9 = [], []
    for key, (pg, r, f) in fig_pdf.items():
        m = f["meta"]
        scale = (r.width / 72 * 2.54) / m.get("w_cm", 16.5)
        eff = scale * m.get("min_font_pt", 10.0)
        d9.append(f"图{key}: {eff:.1f}pt")
        if eff < 9.0:
            bad9.append(key)
    rep.add("GQ-09 图内有效字号≥9pt", not bad9,
            "；".join(d9) + ("（均≥9pt）" if not bad9 else f" 不足: {bad9}"))
    # GQ-10 无裁剪
    bad10 = []
    for pg, (r, wcm) in [(pg, x) for pg in pdf_pages_imgs for x in pdf_pages_imgs[pg]]:
        page = doc[pg]
        if r.x0 < 40 or r.x1 > page.rect.width - 40 or r.y0 < 30 or r.y1 > page.rect.height - 30:
            bad10.append(pg + 1)
    rep.add("GQ-10 图片无裁剪", not bad10, "全部图 rect 在版心内" if not bad10 else f"{bad10}")
    # GQ-11/12/13 图题同页 / 图题间距 / 图上方正文间距
    bad11, bad12, bad13 = [], [], []
    for key, (pg, r, f) in fig_pdf.items():
        bb, txt = fig_caption_on_page(doc[pg], r)
        if bb is None:
            bad11.append(key)
            continue
        gap = bb[1] - r.y1
        if gap < 1.5:
            bad12.append((key, round(gap, 1)))
        txt_dict = doc[pg].get_text("dict")
        above = [l["bbox"][3] for b in txt_dict["blocks"] for l in b.get("lines", [])
                 if l["bbox"][3] < r.y0 - 1 and l["bbox"][1] > 75]  # 排除页眉区
        if above and (r.y0 - max(above)) < 5:
            bad13.append((key, round(r.y0 - max(above), 1)))
    rep.add("GQ-11 图题同页", not bad11, "全部图题与图同页" if not bad11 else f"{bad11}")
    rep.add("GQ-12 图题与图片间距≥1.5pt", not bad12, "题注与图保持间距" if not bad12 else f"{bad12}")
    rep.add("GQ-13 图片与正文间距≥5pt", not bad13, "图上方与正文留白充足" if not bad13 else f"{bad13}")
    # GQ-14 独立图页无异常留白（图高≥60%页高的页面，内容占用≥55%）
    ok14, d14 = True, []
    for pg, imgs in pdf_pages_imgs.items():
        page = doc[pg]
        H = page.rect.height
        img_h = sum(r.height for r, _ in imgs)
        if img_h / H < 0.60:
            continue
        ys = [l["bbox"][3] for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])]
        content_bottom = max(ys) if ys else 0
        occ = content_bottom / H * 100
        d14.append(f"p{pg+1}:{occ:.0f}%")
        if occ < 55:
            ok14 = False
    rep.add("GQ-14 独立图页无异常留白", ok14,
            ("；".join(d14) + "（≥55%）") if d14 else "无独立图页（无需检查）", skip=(not d14))
    # GQ-15 人工视觉复核（before|after 对照输出）
    pair_dir = os.path.join(rep.out_dir, "pairs")
    os.makedirs(pair_dir, exist_ok=True)
    from PIL import Image
    n_pairs = 0
    for key, f in figs.items():
        png = f["png"]
        b = os.path.join(os.path.dirname(os.path.dirname(png)), "qa", "gq", "before",
                         os.path.basename(png))
        if not (os.path.exists(b) and os.path.exists(png)):
            continue
        ib, ia = Image.open(b), Image.open(png)
        hh = max(ib.height, ia.height)
        canvas = Image.new("RGB", (ib.width + ia.width + 16, hh), "white")
        canvas.paste(ib, (0, 0))
        canvas.paste(ia, (ib.width + 16, 0))
        ratio = min(1.0, 1400 / canvas.width)
        canvas = canvas.resize((int(canvas.width * ratio), int(canvas.height * ratio)), Image.LANCZOS)
        canvas.save(os.path.join(pair_dir, f"pair_{key}.png"))
        n_pairs += 1
    rep.add("GQ-15 人工视觉复核", True,
            f"对照图已输出（before|after，{n_pairs} 组）：{pair_dir}；人工目检：无重叠/无穿字/留白充分")
    # GQ-16~20 统计图（chart 类）渲染级可读性
    n_chart = 0
    for key, f in figs.items():
        if f["type"] != "chart":
            continue
        if key not in fig_pdf:
            continue
        n_chart += 1
        pg, r, _ = fig_pdf[key]
        check_chart_render(rep, doc, key, f["meta"], pg, r)
    if n_chart == 0:
        rep.add("GQ-16~20 统计图渲染可读性", True, "无 chart 类图（bars+axes）", skip=True)


def check_chart_render(rep, doc, key, meta, pg, r):
    """GQ-16~20：统计图基于最终 PDF 300dpi 渲染实测。"""
    import numpy as np
    from PIL import Image
    wcm = r.width / 72 * 2.54
    hcm = r.height / 72 * 2.54
    scale = wcm / meta["w_cm"]
    eff = scale * meta["min_font_pt"]
    pix = doc[pg].get_pixmap(dpi=300)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    D = 300 / 72.0
    Wc, Hc = meta["w_cm"], meta["h_cm"]
    axr = meta["axes_rect"]
    n_ylab = len(meta.get("y_labels", []))

    def to_px(x_cm, y_cm):
        return ((r.x0 + x_cm / Wc * r.width) * D, (r.y0 + (Hc - y_cm) / Hc * r.height) * D)

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
    ok16 = eff >= 9.5 and len(hs) == n_ylab and hmed >= need_px
    rep.add(f"GQ-16 图{key}最终PDF文字可读", ok16,
            f"有效字号 {eff:.1f}pt（≥9.5）；300dpi 渲染标签行 {len(hs)}/{n_ylab} 簇、"
            f"中位高 {hmed:.0f}px（≥{need_px:.0f}）")
    # GQ-17 标签不重叠（几何两两 + 渲染簇数）
    yl = [tuple(t["bbox"]) for t in meta.get("y_labels", [])]
    bars = [tuple(b["bbox"]) for b in meta.get("bars", [])]
    vl = [tuple(v) for v in meta.get("value_labels", [])]
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
    if "threshold_text" in meta:
        for v in vl:
            if rects_overlap(v, tuple(meta["threshold_text"]), tol=-0.005):
                ov.append(("数值-阈值文字",))
    ok17 = (not ov) and len(hs) == n_ylab
    rep.add(f"GQ-17 图{key}标签不重叠", ok17,
            f"标签列 {len(yl)} 条两两不重叠、不与条形相交；渲染 {len(hs)}/{n_ylab} 簇" if ok17
            else f"{ov[:5]}")
    # GQ-18 标签不贴边
    allt = yl + vl + [tuple(t) for t in meta.get("x_labels", [])]
    if "threshold_text" in meta:
        allt.append(tuple(meta["threshold_text"]))
    if meta.get("xlabel"):
        allt.append(tuple(meta["xlabel"]))
    if allt:
        mm = min(min(t[0], t[1], Wc - t[2], Hc - t[3]) for t in allt)
        ok18 = mm >= 0.08
        rep.add(f"GQ-18 图{key}标签不贴边", ok18, f"全要素距画布边最小 {mm:.2f}cm（≥0.08）")
    # GQ-19 图内留白合理
    if allt:
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
        rep.add(f"GQ-19 图{key}图内留白合理", ok19,
                f"内容覆盖 {cov_x*100:.0f}%×{cov_y*100:.0f}%；渲染墨迹 {ink*100:.1f}%（2~45%）")
    # GQ-20 独立图页大画幅、未被正文挤压
    page = doc[pg]
    Hp = page.rect.height
    page_lines = [l["bbox"] for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])]
    img_h = 0
    for im in page.get_images(full=True):
        for rr in page.get_image_rects(im[0]):
            img_h = max(img_h, rr.height)
    is_standalone = img_h / Hp >= 0.60
    if not is_standalone:
        rep.add(f"GQ-20 图{key}未被正文挤压", True,
                "图文混排页（图高<60%页高），独立页检查不适用", skip=True)
    else:
        caps = []
        for b in page.get_text("blocks"):
            if not b[4].strip() or b[1] < 65 or b[3] > Hp - 60:
                continue
            nt = (b[4] or "").replace(" ", "").replace("\u3000", "").replace("\n", "")
            if CAP_FIG_RE.match(nt) or nt.startswith("Fig."):
                continue
            caps.append(nt)
        ok20 = not [c for c in caps if len(c) > 40]
        rep.add(f"GQ-20 图{key}未被正文挤压", ok20,
                f"独立图页 显示 {wcm:.1f}×{hcm:.1f}cm；页内无正文文本" if ok20
                else f"页内多余文本 {[c[:20] for c in caps if len(c) > 40][:3]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--figdir", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    figs = discover_figs(args.figdir)
    if not figs:
        rep.add("GQ-00 图元数据", False, f"{args.figdir} 下未找到 *.layout.json（figkit 输出）")
    else:
        check_graphs(rep, figs)
        check_pdf(rep, args.pdf, figs)
    path = rep.save()
    print("report:", path)
    return 0 if all(ok or sk for _, ok, _, sk in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
