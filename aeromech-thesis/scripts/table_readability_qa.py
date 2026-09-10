# -*- coding: utf-8 -*-
"""table_readability_qa.py — 表可读性 QA（TR-01~14，BUG-016~019 沉淀）

表4-1~4-4（FMEA 宽表）逐表核验：A4 横向节 / 正文字号≥9pt / 列宽按分析列优先 /
无一字一行 / 原因与影响列可正常成句 / S·O·D·RPN 保持紧凑 / 题注同页 / 长表表头重复 / 无裁剪。
用法: python table_readability_qa.py --docx <final.docx> --pdf <final.pdf> --out <dir>
退出码: 0=全部 PASS
"""
import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn

TARGETS = ["4-1", "4-2", "4-3", "4-4"]
BODY_LANDSCAPE_CM = 25.7
MAIN_COLS = [2, 3, 4, 5, 6, 7]           # 功能/故障模式/故障原因/局部影响/最终影响/检测防护
CANSENT_COLS = {4: "故障原因", 5: "局部影响", 6: "最终影响", 7: "检测防护"}
COMPACT_COLS = [8, 9, 10, 11]            # S/O/D/RPN


def nz(x):
    return (x or "").replace(" ", "").replace("\u3000", "").replace("\n", "")


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "table-readability-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# Table Readability QA（TR-01~14）", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def section_orientation_map(doc):
    """返回 body 子元素索引 -> 所在节方向（'L'/'P'）。"""
    body = doc.element.body
    els = list(body.iterchildren())
    sect_at = []  # (index, sectPr)
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

    # 收集表4-1~4-4：题注/表头签名/列宽/字号/数据行文本
    tables = {}
    for i, el in enumerate(els):
        if el.tag != qn("w:tbl"):
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
                if re.match(r"^表[0-9AB]-\d+", t):
                    cap_cn = t
                    break
                if t and not t.startswith("Tab."):
                    break
            j -= 1
            steps += 1
        m = re.match(r"^表((?:\d+|[AB])-\d+)", cap_cn)
        if not m or m.group(1) not in TARGETS:
            continue
        key = m.group(1)
        hdr_cells = ["".join(x.text or "" for x in tc.iter(qn("w:t"))) for tc in rows[0].findall(qn("w:tc"))]
        sig = nz(hdr_cells[0]) + (nz(hdr_cells[1]) if len(hdr_cells) > 1 else "")
        widths = []
        for ci, tc in enumerate(rows[1].findall(qn("w:tc"))):
            try:
                tcw = tc.find(qn("w:tcPr")).find(qn("w:tcW"))
                w_tw = int(tcw.get(qn("w:w")))
                widths.append(w_tw / 1440.0 * 2.54)
            except Exception:
                widths.append(-1)
        # 字号：数据行所有 run
        fs_main, all_fs = [], []
        compact_texts = []
        for ri in range(1, len(rows)):
            cells = rows[ri].findall(qn("w:tc"))
            for ci, tc in enumerate(cells):
                txt = "".join(x.text or "" for x in tc.iter(qn("w:t")))
                for r_el in tc.iter(qn("w:r")):
                    sz = r_el.find(qn("w:rPr"))
                    szel = sz.find(qn("w:sz")) if sz is not None else None
                    if szel is not None:
                        v = int(szel.get(qn("w:val"))) / 2.0
                        all_fs.append(v)
                        if ci in MAIN_COLS:
                            fs_main.append(v)
                if ci in COMPACT_COLS:
                    compact_texts.append(nz(txt))
        first_row_txt = nz("".join(x.text or "" for x in rows[1].iter(qn("w:t"))))[:14]
        last_row_txt = nz("".join(x.text or "" for x in rows[-1].iter(qn("w:t"))))[:14]
        tables[key] = {
            "cap_cn": cap_cn, "cap_sig": nz(cap_cn)[:14], "en_key": "Tab." + key,
            "sig": sig[:10], "widths": widths, "fs_main": fs_main, "fs_all": all_fs,
            "compact_texts": compact_texts, "orient": omap.get(i, "P"),
            "first": first_row_txt, "last": last_row_txt, "seq": i,
        }

    tsort = sorted(tables.items(), key=lambda kv: kv[1]["seq"])
    seq_anchor = 0

    def locate_pages(t):
        nonlocal seq_anchor
        p_cap = p_en = p_hdr = p_first = p_last = None
        for q in range(seq_anchor, len(pages_nz)):
            if t["cap_sig"] in pages_nz[q] and "......" not in pdf[q].get_text():
                p_cap = q
                break
        if p_cap is None:
            return None
        for q in range(max(0, p_cap - 1), len(pages_nz)):
            if nz(t["en_key"]) in pages_nz[q]:
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

    per_table = []
    for key, t in tsort:
        loc = locate_pages(t)
        t["pages"] = loc
        per_table.append((key, t))

    # TR-01~04 逐表可读（横向 / 字号 / 列宽分配 / 无裁剪总宽）
    tr_bad = {}
    for key, t in per_table:
        issues = []
        if t["orient"] != "L":
            issues.append("非横向节")
        fsm = min(t["fs_main"]) if t["fs_main"] else 0
        if fsm < 9.0:
            issues.append(f"主列字号{fsm}pt<9")
        wsum = sum(w for w in t["widths"] if w > 0)
        if wsum > BODY_LANDSCAPE_CM + 0.15:
            issues.append(f"总宽{wsum:.1f}cm>{BODY_LANDSCAPE_CM}")
        ws = [round(w, 2) for w in t["widths"]]
        detail = f"横向 主列{fsm}pt 列宽{ws} 总宽{wsum:.1f}cm"
        rep.add(f"TR-{int(key[-1]):02d} 表{key}实际正文可读", not issues, detail if not issues else "；".join(issues))
        if issues:
            tr_bad[key] = issues

    # TR-05 主要文字列平均字号≥9pt
    all_main = [v for _, t in per_table for v in t["fs_main"]]
    avg = sum(all_main) / len(all_main) if all_main else 0
    rep.add("TR-05 主要文字列平均字号≥9pt", avg >= 9.0, f"主列平均 {avg:.2f}pt（≥9）")

    # TR-06 无一字一行异常（主列可容纳字数估算 ≥6 字/行）
    def chars_per_line(width_cm, fs):
        cw = fs * 0.03528
        return int((width_cm - 0.2) / cw) if width_cm > 0 else 0

    t6_bad, cpl_min = [], 99
    for key, t in per_table:
        fsm = min(t["fs_main"]) if t["fs_main"] else 10
        for ci in MAIN_COLS:
            cpl = chars_per_line(t["widths"][ci], fsm)
            cpl_min = min(cpl_min, cpl)
            if cpl < 6:
                t6_bad.append((key, ci, cpl))
    rep.add("TR-06 无一字一行异常", not t6_bad, f"主列最少可容 {cpl_min} 字/行（≥6）" if not t6_bad else f"{t6_bad}")

    # TR-07~10 原因/局部影响/最终影响/检测防护 列可正常成句（宽≥2.6cm 且 ≥8 字/行）
    for ci, name in CANSENT_COLS.items():
        bad, dmin = [], 99
        for key, t in per_table:
            fsm = min(t["fs_main"]) if t["fs_main"] else 10
            w = t["widths"][ci]
            cpl = chars_per_line(w, fsm)
            dmin = min(dmin, cpl)
            if w < 2.6 or cpl < 8:
                bad.append((key, round(w, 2), cpl))
        rep.add(f"TR-{6 + list(CANSENT_COLS).index(ci) + 1:02d} {name}列可正常成句",
                not bad, f"列宽≥2.6cm 且 ≥8 字/行（最小 {dmin} 字/行）" if not bad else f"{bad}")

    # TR-11 S/O/D/RPN 列保持紧凑（≤1.2cm 且内容为数字）
    t11_bad, wmax, badcell = [], 0, []
    for key, t in per_table:
        for ci in COMPACT_COLS:
            w = t["widths"][ci]
            wmax = max(wmax, w)
            if w > 1.2:
                t11_bad.append((key, ci, round(w, 2)))
        for txt in t["compact_texts"]:
            if txt and not re.fullmatch(r"\d{1,3}", txt):
                badcell.append((key, txt[:6]))
    ok11 = not t11_bad and not badcell
    rep.add("TR-11 S/O/D/RPN列保持紧凑", ok11,
            f"列宽≤1.2cm（最大 {wmax:.2f}cm）且内容为数字" if ok11 else f"{t11_bad[:4]} {badcell[:4]}")

    # TR-12 表题与表头同页（横向表）
    t12_bad, t12_d = [], []
    for key, t in per_table:
        loc = t["pages"]
        if not loc:
            t12_bad.append((key, "未定位"))
            continue
        p_cap, p_en, p_hdr, _, _ = loc
        t12_d.append(f"表{key}:题p{p_cap+1}/英p{(p_en or 0)+1}/头p{(p_hdr or 0)+1}")
        if not (p_cap == p_en == p_hdr):
            t12_bad.append((key, "题注-表头跨页"))
    rep.add("TR-12 表题与表头同页", not t12_bad, "；".join(t12_d) if not t12_bad else f"{t12_bad}")

    # TR-13 长表表头重复（跨页表每页含表头签名）
    t13_bad = []
    for key, t in per_table:
        loc = t["pages"]
        if not loc:
            continue
        _, _, p_hdr, p_first, p_last = loc
        if p_first is not None and p_last is not None and p_first != p_last:
            if not all(t["sig"] in pages_nz[q] for q in range(p_first + 1, p_last + 1)):
                t13_bad.append((key, f"p{p_first+1}~p{p_last+1}"))
    rep.add("TR-13 长表表头重复", not t13_bad,
            "四表均为单页横向（表头天然重复无跨页）" if not t13_bad else f"{t13_bad}")

    # TR-14 无裁剪（表格线/文字在版心内）
    t14_bad = []
    for key, t in per_table:
        loc = t["pages"]
        if not loc or loc[0] is None:
            continue
        pg = pdf[loc[0]]
        for b in pg.get_text("blocks"):
            if b[4].strip() and (b[2] > pg.rect.width - 40 or b[0] < 40):
                t14_bad.append((key, "文本越界", round(b[2], 1)))
        for d_ in pg.get_drawings():
            r_ = d_["rect"]
            if r_.x1 > pg.rect.width - 40 or r_.x0 < 40:
                t14_bad.append((key, "线条越界", round(r_.x1, 1)))
    rep.add("TR-14 无裁剪", not t14_bad, "表格文本/线条均在版心内" if not t14_bad else f"{t14_bad[:4]}")

    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
