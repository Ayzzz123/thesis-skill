# -*- coding: utf-8 -*-
"""cover_fill_qa.py — 封面填充值居中 QA（COVER-FILL-01~14，BUG-023 沉淀）

COVER_FILL_CENTERING：填入原始模板横线槽位的内容，必须在该横线有效区间内水平居中
（相对字段自身横线居中，非页面居中）。
用法: python cover_fill_qa.py --template-pdf <tpl.pdf> --pdf <final.pdf> --out <dir>
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
        path = os.path.join(self.out_dir, "cover-fill-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# Cover Fill QA（COVER-FILL-01~14）", ""]
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


def anchor(spans, token, min_sz=0.0):
    ordered = sorted(spans, key=lambda z: (z["y0"], z["x0"]))
    for s in ordered:
        if s["t"].startswith(token) and s["sz"] >= min_sz:
            return s
    for s in ordered:
        if token in s["t"] and s["sz"] >= min_sz:
            return s
    return None


def center_x(bb):
    return (bb[0] + bb[2]) / 2.0


def match_lines(a, b, tol=2.0):
    used = set()
    for (ax0, ax1, ay) in a:
        best = None
        for k, (bx0, bx1, by) in enumerate(b):
            if k in used:
                continue
            if max(abs(ax0 - bx0), abs(ax1 - bx1), abs(ay - by)) <= tol:
                best = k
                break
        if best is None:
            return False
        used.add(best)
    return True


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

    # 题目：第一横线带内的文字（值）
    line1 = nl[0] if nl else None
    title_bb = None
    if line1:
        spans = [s for s in ns
                 if (line1[2] - 14 <= s["y0"] <= line1[2] + 14) and s["x0"] >= line1[0] - 1.5]
        if spans:
            title_bb = (min(s["x0"] for s in spans), min(s["y0"] for s in spans),
                        max(s["x1"] for s in spans), max(s["y1"] for s in spans))

    # 专业：从行 span 提取值再定位
    major_bb = None
    major_row = anchor(ns, "专")
    major_line = None
    if major_row:
        val = major_row["t"].split(":")[-1].split("：")[-1].strip()
        if val:
            rects = np_.search_for(val)
            if rects:
                major_bb = (min(r.x0 for r in rects), min(r.y0 for r in rects),
                            max(r.x1 for r in rects), max(r.y1 for r in rects))
                for (lx0, lx1, ly) in nl:
                    if abs(ly - major_bb[3]) <= 8:
                        major_line = (lx0, lx1, ly)
                        break

    dev_title = dev_major = None
    # COVER-FILL-01 题目在横线有效区间内
    ok01 = bool(title_bb and line1) and title_bb[0] >= line1[0] - 1.5 and title_bb[2] <= line1[1] + 1.5
    rep.add("COVER-FILL-01 题目在横线有效区间内", ok01,
            f"文字 [{title_bb[0]:.1f},{title_bb[2]:.1f}] 位于横线 [{line1[0]:.1f},{line1[1]:.1f}] 之内"
            if title_bb and line1 else "未定位")
    # COVER-FILL-02 题目水平居中
    if title_bb and line1:
        line1_c = (line1[0] + line1[1]) / 2.0
        dev_title = abs(center_x(title_bb) - line1_c)
    rep.add("COVER-FILL-02 题目水平居中", dev_title is not None and dev_title <= 2.0,
            f"横线中心={line1_c:.2f}pt；文字中心={center_x(title_bb):.2f}pt；"
            f"偏差={dev_title:.2f}pt（≤2）"
            if title_bb and line1 else "未定位")
    # COVER-FILL-03 专业在横线有效区间内
    ok03 = bool(major_bb and major_line) and major_bb[0] >= major_line[0] - 1.5 \
        and major_bb[2] <= major_line[1] + 1.5
    rep.add("COVER-FILL-03 专业在横线有效区间内", ok03,
            f"文字 [{major_bb[0]:.1f},{major_bb[2]:.1f}] 位于横线 [{major_line[0]:.1f},{major_line[1]:.1f}] 之内"
            if major_bb and major_line else "未定位")
    # COVER-FILL-04 专业水平居中
    if major_bb and major_line:
        major_line_c = (major_line[0] + major_line[1]) / 2.0
        dev_major = abs(center_x(major_bb) - major_line_c)
    rep.add("COVER-FILL-04 专业水平居中", dev_major is not None and dev_major <= 2.0,
            f"横线中心={major_line_c:.2f}pt；文字中心={center_x(major_bb):.2f}pt；"
            f"偏差={dev_major:.2f}pt（≤2）" if major_bb and major_line else "未定位")

    # COVER-FILL-05~09 空槽保留（姓/学号/学院/指导教师段/职称段：无填入值）
    def seg_of(row_t, kind):
        after_colon = row_t.split(":")[-1].split("：")[-1]
        if kind == "advisor":
            return after_colon.split("职称")[0]
        if kind == "post":
            return row_t.split("职称")[-1] if "职称" in row_t else ""
        return after_colon

    slot_defs = [("05", "姓名", "姓", "plain"),
                 ("06", "学号", "号", "plain"),
                 ("07", "学院", "院", "plain"),
                 ("08", "指导教师", "指导教师", "advisor"),
                 ("09", "职称", "指导教师", "post")]
    for code, name, token, kind in slot_defs:
        row = anchor(ns, token)
        if not row:
            rep.add(f"COVER-FILL-{code} {name}槽保留", False, "未定位该行")
            continue
        leftover = seg_of(row["t"], kind).strip()
        rep.add(f"COVER-FILL-{code} {name}槽保留", leftover == "",
                "槽内无填入值（标签行原样保留）" if leftover == "" else f"存在内容: {leftover[:12]!r}")
    # COVER-FILL-10 日期槽保留（与模板日期行同位）
    t_date = anchor(ts, "20")
    n_date = anchor(ns, "20")
    if t_date and n_date:
        dd = max(abs(t_date["x0"] - n_date["x0"]), abs(t_date["y0"] - n_date["y0"]))
        rep.add("COVER-FILL-10 日期槽保留", dd <= 2.0, f"与模板同位（位移 {dd:.1f}pt ≤2，无填入值）")
    else:
        rep.add("COVER-FILL-10 日期槽保留", False, "未定位日期行")

    # COVER-FILL-11 不新增横线 / COVER-FILL-12 不删除原横线
    rep.add("COVER-FILL-11 不新增横线", len(nl) == len(tl) and match_lines(nl, tl),
            f"横线数 成品={len(nl)} 模板={len(tl)}，成品全部可回溯模板")
    rep.add("COVER-FILL-12 不删除原横线", len(nl) == len(tl) and match_lines(tl, nl),
            f"横线数 成品={len(nl)} 模板={len(tl)}，模板原横线全部保留")

    # COVER-FILL-13 填充值中心点与横线中心点偏差≤2pt
    devs = [x for x in (dev_title, dev_major) if x is not None]
    ok13 = len(devs) == 2 and max(devs) <= 2.0
    rep.add("COVER-FILL-13 填充值中心偏差≤2pt", ok13,
            f"题目 {dev_title:.2f}pt / 专业 {dev_major:.2f}pt（均 ≤2）" if ok13
            else f"题目 {dev_title} / 专业 {dev_major}")

    # COVER-FILL-14 PDF视觉检查（渲染差异 + 居中项复验）
    import numpy as np
    from PIL import Image
    r_t = tp.get_pixmap(dpi=150)
    r_n = np_.get_pixmap(dpi=150)
    a = np.array(Image.frombytes("RGB", (r_t.width, r_t.height), r_t.samples).convert("L"), dtype=np.int16)
    b = np.array(Image.frombytes("RGB", (r_n.width, r_n.height), r_n.samples).convert("L"), dtype=np.int16)
    if a.shape == b.shape:
        diff = float((np.abs(a - b) > 40).mean())
        ok14 = diff <= 0.04 and (dev_title is not None and dev_title <= 2.0) \
            and (dev_major is not None and dev_major <= 2.0)
        rep.add("COVER-FILL-14 PDF视觉检查通过", ok14,
                f"像素差异 {diff*100:.2f}%（≤4%）且两项居中偏差 ≤2pt")
    else:
        rep.add("COVER-FILL-14 PDF视觉检查通过", False, "页面尺寸不一致")

    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
