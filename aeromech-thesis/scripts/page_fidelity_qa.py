# -*- coding: utf-8 -*-
"""page_fidelity_qa.py — 页级保真 QA（HF/AF/AT/RF），thesis-test-4.0 交付验证用。
用法: python page_fidelity_qa.py --docx <final.docx> --pdf <final.pdf> [--template-pdf <tpl.pdf>] --out <dir>
"""
import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self, title="Page Fidelity QA (HF/AF/AT/RF)"):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "page-fidelity-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = [f"# {title}", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def norm(s):
    return s.replace(" ", "").replace("\u3000", "").replace("\n", "")


def check_header(rep, doc_pdf, tpl_pdf=None):
    import pymupdf as fitz
    doc = fitz.open(doc_pdf)
    first_body = None
    for i in range(len(doc)):
        if "飞机主轮刹车系统是完成着陆滑跑减速" in doc[i].get_text():
            first_body = i
            break
    if first_body is None:
        rep.add("HF-01 正文页眉文字", False, "未定位正文起始页")
        return
    pages = list(range(first_body, len(doc)))
    missing_txt = []
    for i in pages:
        found = False
        for b in doc[i].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                if l["bbox"][1] < 110:
                    if "南京农业大学本科毕业论文（设计）" in "".join(s["text"] for s in l["spans"]):
                        found = True
        if not found:
            missing_txt.append(i + 1)
    rep.add("HF-01 正文页眉文字", not missing_txt,
            f"正文 {pages[0]+1}-{pages[-1]+1} 页全部含页眉文字" if not missing_txt
            else f"缺页眉文字页: {missing_txt}")

    def top_rule(page):
        for dr in page.get_drawings():
            r = dr["rect"]
            if r.y1 < 100 and r.height < 3 and r.width > 300:
                return (round(r.x0, 1), round(r.x1, 1), round(r.y0, 1), round(r.height, 2))
        return None

    rules = [(i + 1, top_rule(doc[i])) for i in pages]
    missing_rule = [p for p, r in rules if r is None]
    tpl_ref = None
    if tpl_pdf and os.path.exists(tpl_pdf):
        tdoc = fitz.open(tpl_pdf)
        for i in range(len(tdoc)):
            if i >= 5:
                tpl_ref = top_rule(tdoc[i])
                break
    rep.add("HF-02 正文页眉横线", not missing_rule,
            (f"全部 {len(pages)} 页存在横线" + (f"；模板参考={tpl_ref}" if tpl_ref else ""))
            if not missing_rule else f"缺横线页: {missing_rule}")
    # 分方向核验（BUG-016~019：横向宽表节页眉横线=横向版心宽，与纵向页分组核验）
    grp = {"纵向": [], "横向": []}
    for pgno, r in rules:
        if r is None:
            continue
        p_ = doc[pgno - 1]
        gname = "横向" if p_.rect.width > p_.rect.height else "纵向"
        grp[gname].append((r[0], r[1], r[2]))
    problems, detail_parts = [], []
    for gname in ("纵向", "横向"):
        gs = grp[gname]
        if not gs:
            continue
        ys_g = [x[2] for x in gs]
        ws_g = [x[1] - x[0] for x in gs]
        y_spread = max(ys_g) - min(ys_g)
        w_spread = max(ws_g) - min(ws_g)
        ok_g = y_spread < 2 and w_spread < 10
        if gname == "纵向" and tpl_ref:
            dy = abs(sum(ys_g) / len(ys_g) - tpl_ref[2])
            dw = abs(sum(ws_g) / len(ws_g) - (tpl_ref[1] - tpl_ref[0]))
            ok_g = ok_g and dy < 3 and dw < 10
            detail_parts.append(f"纵向{len(gs)}页 y偏移{dy:.1f}pt 宽差{dw:.1f}pt 波动{y_spread:.1f}pt")
        else:
            detail_parts.append(f"{gname}{len(gs)}页 均宽{sum(ws_g)/len(ws_g):.1f}pt 波动{y_spread:.1f}pt")
        if not ok_g:
            problems.append(gname)
    ok3 = bool(grp["纵向"] or grp["横向"]) and not problems
    rep.add("HF-03 横线位置一致", ok3, "；".join(detail_parts) if detail_parts else "无横线")
    ys_all = [r[2] for _, r in rules if r]
    rep.add("HF-04 横线连续性", len(missing_rule) == 0 and len(ys_all) == len(pages),
            f"{len(ys_all)}/{len(pages)} 页有横线")


def check_abstract(rep, doc_pdf):
    import pymupdf as fitz
    doc = fitz.open(doc_pdf)
    N = min(8, len(doc))
    en_title = "FAULT MODE AND EFFECTS ANALYSIS OF THE B737NG MAIN WHEEL BRAKE SYSTEM"
    cn_abs_page = en_title_page = None
    for i in range(N):
        raw = doc[i].get_text()
        t = norm(raw)
        is_toc = ("目  录" in raw) or ("目录" in norm(raw) and "......" in raw)
        if norm("摘  要") in t and cn_abs_page is None and not is_toc:
            cn_abs_page = i
        if norm(en_title) in t and not is_toc:
            en_title_page = i
    ok1 = cn_abs_page is not None
    cn_t = norm(doc[cn_abs_page].get_text()) if cn_abs_page is not None else ""
    ok1 = ok1 and ("ABSTRACT" not in cn_t) and (norm(en_title) not in cn_t)
    rep.add("AF-01 中文摘要独立页", ok1,
            f"中文摘要页=第 {cn_abs_page+1 if cn_abs_page is not None else '?'} 页（不含英题/ABSTRACT）")
    ok2 = cn_abs_page is not None and en_title_page is not None and en_title_page != cn_abs_page \
        and norm(en_title) not in cn_t
    rep.add("AF-02 英文题目位于英文摘要页", ok2,
            f"英文题目页=第 {en_title_page+1 if en_title_page is not None else '?'} 页")
    abs_page = None
    for i in range(N):
        raw = doc[i].get_text()
        if "ABSTRACT" in raw and "目  录" not in raw and "......" not in raw:
            abs_page = i
            break
    ok3 = abs_page is not None and en_title_page is not None and abs_page == en_title_page
    if abs_page is not None:
        ok3 = ok3 and ("The main wheel brake system" in doc[abs_page].get_text())
    rep.add("AF-03 ABSTRACT 位置", ok3,
            f"ABSTRACT 页=第 {abs_page+1 if abs_page is not None else '?'} 页（与英题同页且含正文）")
    kw_page = None
    for i in range(N):
        if "KEY WORDS" in doc[i].get_text():
            kw_page = i
            break
    ok4 = kw_page is not None and abs_page is not None and kw_page in (abs_page, abs_page + 1)
    if kw_page is not None:
        ok4 = ok4 and ("brake" in doc[kw_page].get_text().lower())
    rep.add("AF-04 KEY WORDS 位置", ok4,
            f"KEY WORDS 页=第 {kw_page+1 if kw_page is not None else '?'} 页（不孤立）")


def check_appendix_tables(rep, docx_path, doc_pdf):
    import pymupdf as fitz
    d = docx.Document(docx_path)
    paras = d.paragraphs
    start = None
    app_el = None
    for i, p in enumerate(paras):
        if p.style.name == "Heading 1" and p.text.strip().startswith("附录A"):
            start = i
            app_el = p._p
            break
    app_paras = paras[start:] if start is not None else []
    body = d.element.body
    tbl_in_app = []
    seen_app = False
    for el in body.iterchildren():
        if el is app_el:
            seen_app = True
            continue
        if seen_app and el.tag == qn("w:tbl"):
            tbl_in_app.append(el)
    doc = fitz.open(doc_pdf)
    bad_pages = []
    for i in range(len(doc)):
        t = doc[i].get_text()
        if "|" in t:
            bad_pages.append((i + 1, "竖线"))
        if re.search(r"^\s*-{2,}\s*$", t, re.M):
            bad_pages.append((i + 1, "---"))
    rep.add("AT-01 无 Markdown 残留", not bad_pages,
            "全 PDF 无竖线与分隔符残留" if not bad_pages else f"残留页: {bad_pages}")
    bad2 = []
    for ti, tel in enumerate(tbl_in_app):
        for tc in tel.iter(qn("w:tc")):
            tcPr = tc.find(qn("w:tcPr"))
            if tcPr is not None:
                borders = tcPr.find(qn("w:tcBorders"))
                if borders is not None:
                    for side in ("left", "right", "insideH", "insideV"):
                        el = borders.find(qn("w:" + side))
                        if el is not None and el.get(qn("w:val")) not in (None, "none", "nil"):
                            bad2.append((ti, side))
    rep.add("AT-02 三线表", len(tbl_in_app) == 3 and not bad2,
            f"附录表 {len(tbl_in_app)} 张；内/竖边框={bad2 or '无'}")
    single = total = 0
    for tel in tbl_in_app:
        for tr in tel.findall(qn("w:tr")):
            for tc in tr.findall(qn("w:tc")):
                txt = "".join(x.text or "" for x in tc.iter(qn("w:t"))).strip()
                han = re.findall(r"[一-鿿]", txt)
                total += 1
                if len(txt) <= 1 and han:
                    single += 1
    ratio = single / total if total else 1
    rep.add("AT-03 中文正常排版", ratio < 0.05,
            f"中文单字符单元格占比 {ratio*100:.1f}%（<5%，逐字拆列检测；数值列不误伤）")
    heads_ok = bool(tbl_in_app)
    for tel in tbl_in_app:
        tr = tel.findall(qn("w:tr"))
        if not tr:
            heads_ok = False
            continue
        cells = ["".join(x.text or "" for x in tc.iter(qn("w:t"))).strip()
                 for tc in tr[0].findall(qn("w:tc"))]
        if cells != ["分值", "判据描述"]:
            heads_ok = False
    rep.add("AT-04 表头正确", heads_ok, f"表头=['分值','判据描述'] × {len(tbl_in_app)} 张")
    caps = [p.text.strip() for p in app_paras if p.text.strip()]
    has_cn = all(any(c.startswith(f"表A-{k}") for c in caps) for k in (1, 2, 3))
    has_en = all(any(f"Tab. A-{k}" in c for c in caps) for k in (1, 2, 3))
    rep.add("AT-05 表题中英文完整", has_cn and has_en, f"中文题={has_cn} 英文题={has_en}")


def check_references(rep, docx_path):
    d = docx.Document(docx_path)
    paras = d.paragraphs
    ref_start = None
    for i, p in enumerate(paras):
        if p.text.strip() == "参考文献":
            ref_start = i
    if ref_start is None:
        rep.add("RF-01 参考文献数量", False, "未找到参考文献标题")
        return
    refs = []
    for p in paras[ref_start + 1:]:
        t = p.text.strip()
        m = re.match(r"^\[(\d+)\]\s*(.+)$", t)
        if m:
            refs.append((int(m.group(1)), m.group(2)))
        elif t.startswith("致"):
            break
    n = len(refs)
    rep.add("RF-01 参考文献数量", n >= 15, f"条目数={n}（要求≥15）")
    foreign = 0
    for num, txt in refs:
        han = len(re.findall(r"[\u4e00-\u9fff]", txt))
        alpha = len(re.findall(r"[A-Za-z]", txt))
        if han <= 6 and alpha >= 20:
            foreign += 1
    rep.add("RF-02 外文文献数量", foreign >= 5, f"外文条目={foreign}（要求≥5）")
    nums = [num for num, _ in refs]
    ok3 = nums == list(range(1, n + 1))
    rep.add("RF-03 引用编号连续", ok3, "编号 1..%d 连续" % n if ok3 else f"编号异常: {nums}")
    cited = set()
    for p in paras:
        if p.text.strip() == "参考文献":
            break
        for r in p.runs:
            rPr = r._r.find(qn("w:rPr"))
            if rPr is None:
                continue
            va = rPr.find(qn("w:vertAlign"))
            if va is not None and va.get(qn("w:val")) == "superscript":
                for num in re.findall(r"\[(\d+)\]", r.text):
                    cited.add(int(num))
    missing_cite = sorted(set(range(1, n + 1)) - cited)
    extra_cite = sorted(cited - set(range(1, n + 1)))
    ok4 = not missing_cite and not extra_cite
    rep.add("RF-04 文内引用与文献一一对应", ok4,
            f"被引 {len(cited)}/{n}" + (f"；未被引用: {missing_cite}" if missing_cite else "")
            + (f"；越界引用: {extra_cite}" if extra_cite else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--template-pdf", default=None)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    check_header(rep, args.pdf, args.template_pdf)
    check_abstract(rep, args.pdf)
    check_appendix_tables(rep, args.docx, args.pdf)
    check_references(rep, args.docx)
    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())

