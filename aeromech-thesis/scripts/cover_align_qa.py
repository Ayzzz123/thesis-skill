# -*- coding: utf-8 -*-
"""cover_align_qa.py — 封面字段对齐 QA（COVER-ALIGN-01~16，BUG-021 沉淀）

对照"模板首页 PDF"与"交付 PDF 首页"逐项核验：校徽/校名/主标题/题目标签与文字-横线关系/
各字段基线/日期/左右对齐/垂直间距/无额外横线/无字段漂移/整体视觉一致。
用法: python cover_align_qa.py --template-pdf <tpl.pdf> --pdf <final.pdf> --out <dir>
退出码: 0=全部 PASS
"""
import argparse
import os
import sys


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "cover-align-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# Cover Alignment QA（COVER-ALIGN-01~16）", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def spans_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t:
                    out.append({"x0": s["bbox"][0], "y0": s["bbox"][1], "x1": s["bbox"][2],
                                "y1": s["bbox"][3], "t": t, "sz": round(s["size"], 1)})
    return out


def lines_of(page):
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.height < 2.5 and r.width > 30:
            out.append((round(r.x0, 1), round(r.x1, 1), round(r.y0, 1)))
    return sorted(out, key=lambda z: z[2])


def images_of(page):
    out = []
    for im in page.get_images(full=True):
        for r in page.get_image_rects(im[0]):
            out.append((round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)))
    return sorted(out, key=lambda z: (z[1], z[0]))


def anchor(spans, token, min_sz=0.0):
    ordered = sorted(spans, key=lambda z: (z["y0"], z["x0"]))
    for s in ordered:
        if s["t"].startswith(token) and s["sz"] >= min_sz:
            return s
    for s in ordered:
        if token in s["t"] and s["sz"] >= min_sz:
            return s
    return None


def d(a, b):
    return abs(a - b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template-pdf", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    import pymupdf as fitz
    tpl = fitz.open(args.template_pdf)
    now = fitz.open(args.pdf)
    tp, np_ = tpl[0], now[0]
    ts, ns = spans_of(tp), spans_of(np_)
    tl, nl = lines_of(tp), lines_of(np_)
    ti, ni = images_of(tp), images_of(np_)

    # COVER-ALIGN-01/02 校徽 / 校名（图片位置与尺寸）
    ok1 = ok2 = len(ti) >= 2 and len(ni) >= 2
    d1 = d2 = ""
    if ok1:
        for z in range(2):
            dx = d(ti[z][0], ni[z][0]); dy = d(ti[z][1], ni[z][1])
            dw = d(ti[z][2] - ti[z][0], ni[z][2] - ni[z][0]); dh = d(ti[z][3] - ti[z][1], ni[z][3] - ni[z][1])
            good = max(dx, dy, dw, dh) <= 2.0
            if z == 0:
                ok1, d1 = good, f"校徽 偏移 dx={dx:.1f} dy={dy:.1f}pt 尺寸差 {dw:.1f}/{dh:.1f}pt"
            else:
                ok2, d2 = good, f"校名 偏移 dx={dx:.1f} dy={dy:.1f}pt 尺寸差 {dw:.1f}/{dh:.1f}pt"
    rep.add("COVER-ALIGN-01 校徽位置", ok1, d1 or f"模板图数={len(ti)} 成品图数={len(ni)}")
    rep.add("COVER-ALIGN-02 校名字样位置", ok2, d2 or "图片数不足")

    # COVER-ALIGN-03 主标题位置
    t_big = anchor(ts, "本科生毕业论文", 20)
    n_big = anchor(ns, "本科生毕业论文", 20)
    if t_big and n_big:
        dd = max(d(t_big["x0"], n_big["x0"]), d(t_big["y0"], n_big["y0"]), d(t_big["x1"], n_big["x1"]))
        rep.add("COVER-ALIGN-03 主标题位置", dd <= 3.0,
                f"位移 {dd:.1f}pt（≤3）")
    else:
        rep.add("COVER-ALIGN-03 主标题位置", False, "未定位主标题")

    # COVER-ALIGN-04 题目标签位置
    t_lab = anchor(ts, "题", 12)
    n_lab = anchor(ns, "题", 12)
    if t_lab and n_lab:
        dd = max(d(t_lab["x0"], n_lab["x0"]), d(t_lab["y0"], n_lab["y0"]))
        rep.add("COVER-ALIGN-04 题目标签位置", dd <= 2.0, f"位移 {dd:.1f}pt（≤2）")
    else:
        rep.add("COVER-ALIGN-04 题目标签位置", False, "未定位题目标签")

    # COVER-ALIGN-05 题目文字与原横线关系
    line1 = tl[0] if tl else None
    title_spans = []
    if line1:
        title_spans = [s for s in ns
                       if (line1[2] - 14 <= s["y0"] <= line1[2] + 14) and s["x0"] >= line1[0] - 1.5]
    if title_spans and line1:
        ys = [s["y1"] for s in title_spans]
        one_line = (max(ys) - min(ys)) <= 3.0
        x0 = min(s["x0"] for s in title_spans)
        x1 = max(s["x1"] for s in title_spans)
        on_line = abs(max(ys) - line1[2]) <= 5.0
        inside = (x0 >= line1[0] - 1.5) and (x1 <= line1[1] + 3.0)
        line2 = tl[1] if len(tl) > 1 else None
        no_text_row2 = True
        if line2:
            no_text_row2 = not [s for s in ns if line2[2] - 8 <= s["y0"] <= line2[2] + 18]
        ok5 = one_line and on_line and inside and no_text_row2
        rep.add("COVER-ALIGN-05 题目文字与原横线关系", ok5,
                f"单行={one_line} 落线差={abs(max(ys)-line1[2]):.1f}pt 线内={inside} 续行无字={no_text_row2}")
    else:
        rep.add("COVER-ALIGN-05 题目文字与原横线关系", False, "未在第一横线上定位到题目文字")

    # COVER-ALIGN-06~10 各字段基线（标签起点 x0/y0 与模板一致）
    field_anchors = [("06", "姓", "姓名"), ("07", "号", "学号"), ("08", "院", "学院"),
                     ("09", "专", "专业"), ("10", "指导教师", "指导教师")]
    for code, token, name in field_anchors:
        t_a = anchor(ts, token)
        n_a = anchor(ns, token)
        if t_a and n_a:
            dd = max(d(t_a["x0"], n_a["x0"]), d(t_a["y0"], n_a["y0"]))
            rep.add(f"COVER-ALIGN-{code} {name}字段基线", dd <= 2.0, f"位移 {dd:.1f}pt（≤2）")
        else:
            rep.add(f"COVER-ALIGN-{code} {name}字段基线", False, "未定位")

    # COVER-ALIGN-11 日期位置
    t_d = anchor(ts, "20")
    n_d = anchor(ns, "20")
    if t_d and n_d:
        dd = max(d(t_d["x0"], n_d["x0"]), d(t_d["y0"], n_d["y0"]))
        rep.add("COVER-ALIGN-11 日期位置", dd <= 2.0, f"位移 {dd:.1f}pt（≤2）")
    else:
        rep.add("COVER-ALIGN-11 日期位置", False, "未定位日期行")

    # COVER-ALIGN-12 字段左右对齐（各字段行尾与模板一致；专业值落线；标签 x0 无漂移）
    ok12, d12 = True, []
    for token in ("姓", "号", "院", "专", "指导教师"):
        t_a, n_a = anchor(ts, token), anchor(ns, token)
        if t_a and n_a:
            dd = abs(t_a["x1"] - n_a["x1"])
            if dd > 3.0:
                ok12 = False
                d12.append(f"{token} 行尾差 {dd:.1f}pt")
    n_major = [s for s in ns if "飞行器维修工程技术" in s["t"]]
    if tl and nl and n_major:
        my = max(s["y1"] for s in n_major)
        n_line = None
        for (lx0, lx1, ly) in nl:
            if abs(ly - my) <= 6:
                n_line = (lx0, lx1, ly)
                break
        t_ref = None
        if n_line:
            for (lx0, lx1, ly) in tl:
                if abs(ly - n_line[2]) <= 6:
                    t_ref = (lx0, lx1)
                    break
        if n_line and t_ref:
            dd = max(abs(n_line[0] - t_ref[0]), abs(n_line[1] - t_ref[1]))
            if dd > 3.0:
                ok12 = False
                d12.append(f"专业行横线 x0/x1 与模板差 {dd:.1f}pt")
        else:
            ok12 = False
            d12.append("专业行横线未匹配")
    else:
        ok12 = False
        d12.append("未定位专业值")
    rep.add("COVER-ALIGN-12 字段左右对齐", ok12, "；".join(d12) if d12 else "全部字段行尾与模板一致")

    # COVER-ALIGN-13 字段间垂直间距（各横线 y 间距与模板一致）
    if len(tl) == len(nl):
        gaps_t = [tl[i + 1][2] - tl[i][2] for i in range(len(tl) - 1)]
        gaps_n = [nl[i + 1][2] - nl[i][2] for i in range(len(nl) - 1)]
        worst = max(abs(a - b) for a, b in zip(gaps_t, gaps_n))
        rep.add("COVER-ALIGN-13 字段间垂直间距", worst <= 2.0, f"最大间距差 {worst:.1f}pt（≤2）")
    else:
        rep.add("COVER-ALIGN-13 字段间垂直间距", False, f"横线数不一致 模板={len(tl)} 成品={len(nl)}")

    # COVER-ALIGN-14 无额外横线（数量一致且逐条可匹配）
    def match_lines(a, b, tol=2.0):
        used = set()
        for (ax0, ax1, ay) in a:
            best = None
            for k, (bx0, bx1, by) in enumerate(b):
                if k in used:
                    continue
                if max(d(ax0, bx0), d(ax1, bx1), d(ay, by)) <= tol:
                    best = k
                    break
            if best is None:
                return False
            used.add(best)
        return True

    rep.add("COVER-ALIGN-14 无额外横线", len(tl) == len(nl),
            f"横线数 模板={len(tl)} 成品={len(nl)}（等量且均为原横线）")
    rep.add("COVER-ALIGN-15 无字段漂移", match_lines(tl, nl),
            "全部原横线在成品中逐条匹配（x0/x1/y 偏差 ≤2pt）")

    # COVER-ALIGN-16 PDF视觉与模板一致（渲染级）
    import numpy as np
    from PIL import Image
    r_t = tp.get_pixmap(dpi=150)
    r_n = np_.get_pixmap(dpi=150)
    a = np.array(Image.frombytes("RGB", (r_t.width, r_t.height), r_t.samples).convert("L"), dtype=np.int16)
    b = np.array(Image.frombytes("RGB", (r_n.width, r_n.height), r_n.samples).convert("L"), dtype=np.int16)
    if a.shape == b.shape:
        diff = (np.abs(a - b) > 40).mean()
        rep.add("COVER-ALIGN-16 PDF视觉与模板一致", diff <= 0.04,
                f"像素差异 {diff*100:.2f}%（≤4%，含填入的题目/专业文字）")
    else:
        rep.add("COVER-ALIGN-16 PDF视觉与模板一致", False, "页面尺寸不一致")

    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
