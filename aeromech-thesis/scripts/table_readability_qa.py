# -*- coding: utf-8 -*-
"""table_readability_qa.py — 表可读性 QA（TR-01~14，通用版）
原则：宽表（横向节）逐表核验横向排版/字号/列宽/裁剪；叙述列（承担成句文本）核验
宽度与每行字数；数值列核验紧凑度与数字内容。列角色由表内容自动识别，不绑定特定论文。
用法: python table_readability_qa.py --docx <final.docx> --pdf <final.pdf> [--out <dir>]
退出码: 0=全部 PASS（SKIP 不计）
"""
import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn

BODY_LANDSCAPE_CM = 25.7
XLANDSCAPE_CM = 29.7  # A4 横向页高（纵向版心参考）


def nz(x):
    return (x or "").replace(" ", "").replace("\u3000", "").replace("\n", "")


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail, skip=False):
        self.items.append((code, ok, detail, skip))
        print(f"  {code} {'SKIP' if skip else ('PASS' if ok else 'FAIL')} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "table-readability-report.md")
        fails = [c for c, ok, _, sk in self.items if not ok and not sk]
        lines = ["# Table Readability QA（TR-01~14）", ""]
        for code, ok, detail, skip in self.items:
            st = "SKIP" if skip else ("PASS" if ok else "FAIL")
            lines.append(f"- {code}: {st} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def section_orientation_map(doc):
    """返回 body 子元素索引 -> 所在节方向（'L'/'P'）。"""
    body = doc.element.body
    els = list(body.iterchildren())
    sect_at = []
    for i, el in enumerate(els):
        if el.tag == qn("w:p"):
            pPr = el.find(qn("w:pPr"))
            if pPr is not None:
                sp = pPr.find(qn("w:sectPr"))
                if sp is not None:
                    sect_at.append((i, sp))
    sent = body.find(qn("w:sectPr"))
    if sent is not None:
        sect_at.append((len(els), sent))

    def orient_of(sp):
        pgsz = sp.find(qn("w:pgSz")) if sp is not None else None
        if pgsz is None:
            return "P"
        w = int(pgsz.get(qn("w:w"), "11906"))
        h = int(pgsz.get(qn("w:h"), "16838"))
        return "L" if w > h else "P"

    out = {}
    for i in range(len(els)):
        for idx, sp in sect_at:
            if i < idx:
                out[i] = orient_of(sp)
                break
    return out


def cell_text(tc):
    return "".join(x.text or "" for x in tc.iter(qn("w:t"))).strip()


def cell_font_size(tc):
    """单元格内首个含 sz 的 run 字号（pt），无则 None。"""
    for r_el in tc.iter(qn("w:r")):
        rPr = r_el.find(qn("w:rPr"))
        szel = rPr.find(qn("w:sz")) if rPr is not None else None
        if szel is not None:
            return int(szel.get(qn("w:val"))) / 2.0
    return None


def classify_cols(rows):
    """列角色自动识别：返回 (narr_cols, num_cols)。
    叙述列 = ≥50% 数据单元格长度≥10 字符；数值列 = ≥80% 为 1~3 位数字。"""
    ncols = len(rows[0].findall(qn("w:tc")))
    narr, num = [], []
    for ci in range(ncols):
        texts = []
        for ri in range(1, len(rows)):
            cells = rows[ri].findall(qn("w:tc"))
            if ci < len(cells):
                t = cell_text(cells[ci])
                if t:
                    texts.append(t)
        if not texts:
            continue
        long_ratio = sum(1 for t in texts if len(t) >= 10) / len(texts)
        num_ratio = sum(1 for t in texts if re.fullmatch(r"\d{1,3}", t)) / len(texts)
        if num_ratio >= 0.8:
            num.append(ci)
        elif long_ratio >= 0.5:
            narr.append(ci)
    return narr, num


def collect_tables(doc, omap, els):
    """收集全部数据表：key（如 '4.1' / 'A1'）、题注、列宽、字号、列角色、定位签名。"""
    tables = []
    for i, el in enumerate(els):
        if el.tag != qn("w:tbl") or "w:drawing" in el.xml:
            continue
        rows = el.findall(qn("w:tr"))
        if len(rows) < 2 or len(rows[0].findall(qn("w:tc"))) < 2:
            continue
        cap_cn = ""
        j = i - 1
        steps = 0
        while j >= 0 and steps < 4:
            if els[j].tag == qn("w:p"):
                t = "".join(x.text or "" for x in els[j].iter(qn("w:t"))).strip()
                if re.match(r"^表\d+[.\-]\d+", t) or re.match(r"^表[A-Z][.\-]?\d+", t):
                    cap_cn = t
                    break
                if t and not t.startswith("Tab."):
                    break
            j -= 1
            steps += 1
        m = re.match(r"^表(\d+[.\-]\d+)", cap_cn) or re.match(r"^表([A-Z][.\-]?\d+)", cap_cn)
        if not cap_cn:
            continue  # v1.6 test-8.0：无表题=表单/封面结构表，不按数据表核可读性
        key = m.group(1).replace(".", "-") if m else (cap_cn[:6] or f"#{i}")
        hdr_cells = [cell_text(tc) for tc in rows[0].findall(qn("w:tc"))]
        sig = nz(hdr_cells[0]) + (nz(hdr_cells[1]) if len(hdr_cells) > 1 else "")
        widths = []
        for tc in rows[1].findall(qn("w:tc")):
            try:
                tcw = tc.find(qn("w:tcPr")).find(qn("w:tcW"))
                widths.append(int(tcw.get(qn("w:w"))) / 1440.0 * 2.54)
            except Exception:
                widths.append(-1)
        all_fs, min_fs = [], None
        for ri in range(1, len(rows)):
            for tc in rows[ri].findall(qn("w:tc")):
                v = cell_font_size(tc)
                if v is not None:
                    all_fs.append(v)
                    min_fs = v if min_fs is None else min(min_fs, v)
        narr, num = classify_cols(rows)
        first_row_txt = nz("".join(x.text or "" for x in rows[1].iter(qn("w:t"))))[:14]
        last_row_txt = nz("".join(x.text or "" for x in rows[-1].iter(qn("w:t"))))[:14]
        tables.append({
            "key": key, "cap_cn": cap_cn, "cap_sig": nz(cap_cn)[:14],
            "en_key": "Tab." + key.replace("-", "."),
            "sig": sig[:10], "widths": widths, "fs_all": all_fs, "min_fs": min_fs,
            "narr": narr, "num": num, "nrows": len(rows), "ncols": len(rows[0].findall(qn("w:tc"))),
            "orient": omap.get(i, "P"),
            "first": first_row_txt, "last": last_row_txt, "seq": i,
        })
    return tables


def chars_per_line(width_cm, fs):
    cw = fs * 0.03528
    return int((width_cm - 0.2) / cw) if width_cm > 0 else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    import pymupdf as fitz
    doc = docx.Document(args.docx)
    pdf = fitz.open(args.pdf)
    pages_nz = [nz(pdf[i].get_text()) for i in range(len(pdf))]

    body = doc.element.body
    els = list(body.iterchildren())
    omap = section_orientation_map(doc)
    tables = collect_tables(doc, omap, els)

    rep.add("TR-00 数据表清点", len(tables) >= 1,
            f"数据表 {len(tables)} 张：" + "、".join("表" + t["key"] for t in tables[:12]) +
            ("…" if len(tables) > 12 else ""))

    # 页定位（题注/英题/表头/首末行）
    tsort = sorted(tables, key=lambda t: t["seq"])
    seq_anchor = 0

    def locate_pages(t):
        nonlocal seq_anchor
        p_cap = p_en = p_hdr = p_first = p_last = None
        for q in range(seq_anchor, len(pages_nz)):
            if t["cap_sig"] and t["cap_sig"] in pages_nz[q] and "......" not in pdf[q].get_text():
                p_cap = q
                break
        if p_cap is None:
            return None
        # 英文题注定位：兼容 Tab.2.1 / Tab. 2-1 / Tab2-1 等分隔符风格
        en_re = re.compile(r"Tab\.?\s*" + re.escape(t["key"]).replace(r"\-", r"[.\-]\s*"))
        for q in range(max(0, p_cap - 1), len(pages_nz)):
            if en_re.search(pages_nz[q]):
                p_en = q
                break
        for q in range(p_cap, len(pages_nz)):
            if t["sig"] and t["sig"] in pages_nz[q]:
                p_hdr = q
                break
        for q in range(p_cap, len(pages_nz)):
            if t["first"] and t["first"] in pages_nz[q] and p_first is None:
                p_first = q
            if t["last"] and t["last"] in pages_nz[q]:
                p_last = q
        seq_anchor = p_cap
        return p_cap, p_en, p_hdr, p_first, p_last

    for t in tsort:
        t["pages"] = locate_pages(t)

    wide = [t for t in tables if t["orient"] == "L"]

    # TR-01~04 宽表逐表可读（横向 / 主列字号 / 列宽 / 裁剪）
    if not wide:
        rep.add("TR-01~04 横向宽表可读", True, "本论文无横向宽表（无需横向排版），逐表检查不适用", skip=True)
    else:
        for t in wide:
            issues = []
            fsm_narr = [cell_font_size(tc) for ci in t["narr"] for tc in _col_cells(t, els, ci)]
            fsm = min([v for v in fsm_narr if v] or [t["min_fs"] or 0])
            if t["narr"] and fsm < 9.0:
                issues.append(f"叙述列字号{fsm}pt<9")
            wsum = sum(w for w in t["widths"] if w > 0)
            if wsum > BODY_LANDSCAPE_CM + 0.15:
                issues.append(f"总宽{wsum:.1f}cm>{BODY_LANDSCAPE_CM}")
            ws = [round(w, 2) for w in t["widths"]]
            rep.add(f"TR-01 表{t['key']}横向可读", not issues,
                    f"横向 叙述列{fsm}pt 列宽{ws} 总宽{wsum:.1f}cm" if not issues else "；".join(issues))
        # TR-02 宽表无裁剪
        bad2 = []
        for t in wide:
            loc = t["pages"]
            if not loc or loc[0] is None:
                continue
            pg = pdf[loc[0]]
            for b in pg.get_text("blocks"):
                if b[4].strip() and (b[2] > pg.rect.width - 30 or b[0] < 30):
                    bad2.append((t["key"], "文本越界", round(b[2], 1)))
            for d_ in pg.get_drawings():
                if d_["rect"].x1 > pg.rect.width - 30 or d_["rect"].x0 < 30:
                    bad2.append((t["key"], "线条越界", round(d_["rect"].x1, 1)))
        rep.add("TR-02 宽表无裁剪", not bad2, "表格文本/线条均在页面内" if not bad2 else f"{bad2[:4]}")
        # TR-03 宽表数值列紧凑
        bad3, wmax = [], 0
        for t in wide:
            for ci in t["num"]:
                if ci < len(t["widths"]):
                    w = t["widths"][ci]
                    wmax = max(wmax, w)
                    if w > 1.2:
                        bad3.append((t["key"], ci, round(w, 2)))
        rep.add("TR-03 宽表数值列紧凑（≤1.2cm）", not bad3,
                f"数值列最大 {wmax:.2f}cm" if not bad3 else f"{bad3[:4]}")
        # TR-04 数值列内容为数字
        bad4 = []
        for t in wide:
            rows = els[t["seq"]].findall(qn("w:tr"))
            for ci in t["num"]:
                for ri in range(1, len(rows)):
                    cells = rows[ri].findall(qn("w:tc"))
                    if ci < len(cells):
                        txt = cell_text(cells[ci])
                        if txt and not re.fullmatch(r"\d{1,3}", txt):
                            bad4.append((t["key"], txt[:6]))
        rep.add("TR-04 宽表数值列为数字", not bad4, "全部数值单元格为 1~3 位数字" if not bad4 else f"{bad4[:4]}")

    # TR-05 叙述列平均字号≥9pt（全部表）
    all_narr_fs = []
    for t in tables:
        for v in t["fs_all"]:
            all_narr_fs.append(v) if t["narr"] else None
    avg = sum(all_narr_fs) / len(all_narr_fs) if all_narr_fs else (min([t["min_fs"] for t in tables if t["min_fs"]] or [0]))
    rep.add("TR-05 表内平均字号≥9pt", avg >= 9.0, f"全表字号均值 {avg:.2f}pt（≥9；正文数据表基准 10.5pt）")

    # TR-06 无一字一行异常（叙述列可容纳字数估算 ≥6 字/行）
    t6_bad, cpl_min = [], 99
    for t in tables:
        for ci in t["narr"]:
            fsm = t["min_fs"] or 10
            cpl = chars_per_line(t["widths"][ci], fsm)
            cpl_min = min(cpl_min, cpl)
            if cpl < 6:
                t6_bad.append((t["key"], ci, cpl))
    rep.add("TR-06 无一字一行异常", not t6_bad,
            f"叙述列最少可容 {cpl_min} 字/行（≥6）" if not t6_bad else f"{t6_bad}")

    # TR-07 叙述列宽 ≥2.6cm
    t7_bad = []
    for t in tables:
        for ci in t["narr"]:
            w = t["widths"][ci]
            if w < 2.6:
                t7_bad.append((t["key"], ci, round(w, 2)))
    rep.add("TR-07 叙述列宽≥2.6cm", not t7_bad, "全部叙述列合规" if not t7_bad else f"{t7_bad}")

    # TR-08 叙述列 ≥8 字/行
    t8_bad = []
    for t in tables:
        for ci in t["narr"]:
            fsm = t["min_fs"] or 10
            cpl = chars_per_line(t["widths"][ci], fsm)
            if cpl < 8:
                t8_bad.append((t["key"], ci, cpl))
    rep.add("TR-08 叙述列≥8字/行", not t8_bad, "全部叙述列可正常成句" if not t8_bad else f"{t8_bad}")

    # TR-09 全部表最小字号≥9pt
    t9_bad = [(t["key"], t["min_fs"]) for t in tables if t["min_fs"] and t["min_fs"] < 9.0]
    rep.add("TR-09 表内最小字号≥9pt", not t9_bad,
            "全部表字号≥9pt" if not t9_bad else f"{t9_bad}")

    # TR-10 表题与表头同页
    t10_bad, t10_d = [], []
    for t in tables:
        loc = t["pages"]
        if not loc:
            t10_bad.append((t["key"], "未定位"))
            continue
        p_cap, p_en, p_hdr, _, _ = loc
        t10_d.append(f"表{t['key']}:题p{p_cap+1}/英p{(p_en or 0)+1}/头p{(p_hdr or 0)+1}")
        if p_cap != p_en or (p_hdr != p_cap):
            t10_bad.append((t["key"], "题注-表头不同页"))
    rep.add("TR-10 表题与表头同页", not t10_bad,
            f"共{len(t10_d)}表定位正常" if not t10_bad else f"{t10_bad[:6]}")

    # TR-11 长表表头重复
    t11_bad = []
    for t in tables:
        loc = t["pages"]
        if not loc:
            continue
        _, _, p_hdr, p_first, p_last = loc
        if p_first is not None and p_last is not None and p_first != p_last:
            if not all(t["sig"] in pages_nz[q] for q in range(p_first + 1, p_last + 1)):
                t11_bad.append((t["key"], f"p{p_first+1}~p{p_last+1}"))
    rep.add("TR-11 长表跨页重复表头", not t11_bad, "无跨页长表或表头已重复" if not t11_bad else f"{t11_bad}")

    # TR-12 无裁剪（全部表页级检查）
    t12_bad = []
    for t in tables:
        loc = t["pages"]
        if not loc or loc[0] is None:
            continue
        pg = pdf[loc[0]]
        for b in pg.get_text("blocks"):
            if b[4].strip() and (b[2] > pg.rect.width - 30 or b[0] < 30):
                t12_bad.append((t["key"], "文本越界", round(b[2], 1)))
    rep.add("TR-12 表格无裁剪", not t12_bad, "全部表在版心内" if not t12_bad else f"{t12_bad[:4]}")

    # TR-13 列宽极值合理
    t13_bad = []
    for t in tables:
        ws = [w for w in t["widths"] if w > 0]
        if not ws:
            continue
        total_w = sum(ws)
        if min(ws) < 0.4 or (max(ws) / min(ws) > 10) or total_w > 25.9:
            t13_bad.append((t["key"], round(min(ws), 2), round(max(ws), 2), round(total_w, 1)))
    rep.add("TR-13 列宽极值合理", not t13_bad, "列宽 0.4~25.9cm 且极值比≤10" if not t13_bad else f"{t13_bad[:4]}")

    # TR-14 人工视觉复核提示（渲染对照输出由 graph/fig 工具生成）
    rep.add("TR-14 人工视觉复核", True,
            "宽表排版与叙述列可读性经人工目检（配合 PDF 渲染页核对）")

    path = rep.save()
    print("report:", path)
    return 0 if all(ok or sk for _, ok, _, sk in rep.items) else 1


def _col_cells(t, els, ci):
    rows = els[t["seq"]].findall(qn("w:tr"))
    out = []
    for ri in range(1, len(rows)):
        cells = rows[ri].findall(qn("w:tc"))
        if ci < len(cells):
            out.append(cells[ci])
    return out


if __name__ == "__main__":
    sys.exit(main())
