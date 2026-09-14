# -*- coding: utf-8 -*-
"""page_fidelity_qa.py — 页级保真 QA（HF/AF/AT/RF）通用版。
HF-01~04 页眉文字/横线/位置/连续性；AF-01~04 摘要页；AT-01~05 附录表；RF-01~04 参考文献。
通用化：正文起始页自动探测（首个页脚页码==1 的页），可用 --body-start-page/--body-start-marker 覆盖；
页眉固定文字用 --header-even 指定；英文题目用 --en-title 指定；附录检查按实际存在的附录动态核验。
用法: python page_fidelity_qa.py --docx <final.docx> --pdf <final.pdf>
      [--template-pdf <tpl.pdf>] [--header-even "哈尔滨工程大学本科生毕业论文"]
      [--en-title "..."] [--body-start-page N] [--out <dir>]
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

    def add(self, code, ok, detail, skip=False):
        self.items.append((code, ok, detail, skip))
        print(f"  {code} {'SKIP' if skip else ('PASS' if ok else 'FAIL')} | {detail}")

    def save(self, title="Page Fidelity QA (HF/AF/AT/RF)"):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "page-fidelity-report.md")
        fails = [c for c, ok, _, sk in self.items if not ok and not sk]
        lines = [f"# {title}", ""]
        for code, ok, detail, skip in self.items:
            st = "SKIP" if skip else ("PASS" if ok else "FAIL")
            lines.append(f"- {code}: {st} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def norm(s):
    return s.replace(" ", "").replace("\u3000", "").replace("\n", "")


def header_zone_lines(page, y_max=110):
    """页眉区（顶部 y_max 以内）的文本行。"""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            if l["bbox"][1] < y_max:
                out.append((l["bbox"], "".join(s["text"] for s in l["spans"])))
    return out


def footer_page_num(page):
    """页脚区（底部 45~90pt 内）的页码文本（无则 None）。"""
    H = page.rect.height
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            if H - 90 < l["bbox"][1] < H - 45:
                tx = "".join(s["text"] for s in l["spans"]).strip()
                if tx:
                    return tx
    return None


def find_body_start(doc, marker=None, start_page=None):
    """定位正文起始页（0-based）：显式 start_page > marker 全文命中 > 自动探测（页脚=='1'）。"""
    if start_page is not None:
        idx = int(start_page) - 1
        return idx if 0 <= idx < len(doc) else None
    if marker:
        for i in range(len(doc)):
            if marker in doc[i].get_text():
                return i
    for i in range(len(doc)):
        if footer_page_num(doc[i]) == "1":
            return i
    return None


def check_header(rep, doc_pdf, tpl_pdf=None, header_even=None,
                 body_start_marker=None, body_start_page=None):
    import pymupdf as fitz
    doc = fitz.open(doc_pdf)
    first_body = find_body_start(doc, body_start_marker, body_start_page)
    if first_body is None:
        rep.add("HF-01 正文页眉文字", False,
                "未定位正文起始页（可用 --body-start-page 或 --body-start-marker 指定）")
        return
    pages = list(range(first_body, len(doc)))
    missing_txt, bad_even = [], []
    for i in pages:
        lines = header_zone_lines(doc[i])
        txt_all = "".join(t for _, t in lines)
        if not txt_all.strip():
            missing_txt.append(i + 1)
            continue
        if header_even and (i + 1) % 2 == 0:  # 双页/偶数物理页须含固定文字
            if norm(header_even) not in norm(txt_all):
                bad_even.append(i + 1)
    ok1 = not missing_txt and not bad_even
    d1 = f"正文 {pages[0]+1}-{pages[-1]+1} 页全部含页眉文字"
    if header_even:
        d1 += f"；偶数页含「{header_even}」"
    if missing_txt:
        d1 += f"；缺页眉: {missing_txt}"
    if bad_even:
        d1 += f"；偶数页缺固定文字: {bad_even}"
    rep.add("HF-01 正文页眉文字", ok1, d1)

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
    # 分方向核验（横向页页眉横线=横向版心宽，与纵向页分组核验）
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


def check_abstract(rep, doc_pdf, en_title=None):
    import pymupdf as fitz
    doc = fitz.open(doc_pdf)
    N = min(10, len(doc))
    cn_abs_page = en_title_page = None
    for i in range(N):
        raw = doc[i].get_text()
        t = norm(raw)
        is_toc = ("目  录" in raw) or ("目录" in norm(raw) and "......" in raw)
        if norm("摘  要") in t and cn_abs_page is None and not is_toc:
            cn_abs_page = i
        if en_title and norm(en_title) in t and not is_toc:
            en_title_page = i
    ok1 = cn_abs_page is not None
    cn_t = norm(doc[cn_abs_page].get_text()) if cn_abs_page is not None else ""
    ok1 = ok1 and ("ABSTRACT" not in cn_t) and (not en_title or norm(en_title) not in cn_t)
    rep.add("AF-01 中文摘要独立页", ok1,
            f"中文摘要页=第 {cn_abs_page+1 if cn_abs_page is not None else '?'} 页（不含英题/ABSTRACT）")
    if en_title:
        ok2 = cn_abs_page is not None and en_title_page is not None and en_title_page != cn_abs_page \
            and norm(en_title) not in cn_t
        rep.add("AF-02 英文题目位于英文摘要页", ok2,
                f"英文题目页=第 {en_title_page+1 if en_title_page is not None else '?'} 页")
    else:
        rep.add("AF-02 英文题目位于英文摘要页", True,
                "未提供 --en-title，该项 SKIP（提供英文题后精确核验）", skip=True)
    abs_page = None
    for i in range(N):
        raw = doc[i].get_text()
        if "ABSTRACT" in raw and "目  录" not in raw and "......" not in raw:
            abs_page = i
            break
    if abs_page is None:
        rep.add("AF-03 ABSTRACT 位置", False, "未找到 ABSTRACT 页")
    else:
        page_txt = doc[abs_page].get_text()
        latin_words = re.findall(r"[A-Za-z]{3,}", page_txt)
        ok3 = len(latin_words) >= 30  # 英文摘要正文（≥30 个拉丁词）
        rep.add("AF-03 ABSTRACT 位置", ok3,
                f"ABSTRACT 页=第 {abs_page+1} 页（含 {len(latin_words)} 拉丁词）")
    kw_page = None
    for i in range(N):
        if "KEY WORDS" in doc[i].get_text():
            kw_page = i
            break
    ok4 = kw_page is not None and abs_page is not None and kw_page in (abs_page, abs_page + 1)
    if kw_page is not None:
        kw_txt = doc[kw_page].get_text().split("KEY WORDS", 1)[-1]
        ok4 = ok4 and len(re.findall(r"[A-Za-z]{2,}", kw_txt)) >= 2
    rep.add("AF-04 KEY WORDS 位置", ok4,
            f"KEY WORDS 页=第 {kw_page+1 if kw_page is not None else '?'} 页（不孤立）")


def check_appendix_tables(rep, docx_path, doc_pdf):
    import pymupdf as fitz
    d = docx.Document(docx_path)
    paras = d.paragraphs
    app_el = None
    for p in paras:
        if p.style.name == "Heading 1" and re.match(r"^附录[A-Z]", p.text.strip()):
            app_el = p._p
            break
    body = d.element.body
    tbl_in_app = []
    seen_app = False
    for el in body.iterchildren():
        if el is app_el:
            seen_app = True
            continue
        if seen_app and el.tag == qn("w:tbl") and "w:drawing" not in el.xml:
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
    if not tbl_in_app:
        rep.add("AT-02 三线表", True, "附录无数据表", skip=True)
    else:
        rep.add("AT-02 三线表", not bad2,
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
    if not tbl_in_app:
        rep.add("AT-03 中文正常排版", True, "附录无数据表", skip=True)
    else:
        ratio = single / total if total else 1
        rep.add("AT-03 中文正常排版", ratio < 0.05,
                f"中文单字符单元格占比 {ratio*100:.1f}%（<5%，逐字拆列检测；数值列不误伤）")
    if not tbl_in_app:
        rep.add("AT-04 表头正确", True, "附录无数据表", skip=True)
        heads_ok = True
    else:
        heads_ok = True
        for tel in tbl_in_app:
            tr = tel.findall(qn("w:tr"))
            if not tr:
                heads_ok = False
                continue
            cells = ["".join(x.text or "" for x in tc.iter(qn("w:t"))).strip()
                     for tc in tr[0].findall(qn("w:tc"))]
            if not any(cells):
                heads_ok = False
        rep.add("AT-04 表头正确", heads_ok, f"附录表 {len(tbl_in_app)} 张表头行非空")
    # AT-05 每张附录表有中文题注+英文题注（向上查找）
    if not tbl_in_app:
        rep.add("AT-05 表题中英文完整", True, "附录无数据表", skip=True)
    else:
        els = list(body.iterchildren())
        cap_ok, cap_d = True, []
        for tel in tbl_in_app:
            i = els.index(tel)
            cap_cn = cap_en = ""
            j = i - 1
            steps = 0
            while j >= 0 and steps < 4:
                if els[j].tag == qn("w:p"):
                    t = "".join(x.text or "" for x in els[j].iter(qn("w:t"))).strip()
                    if t.startswith("Tab.") and not cap_en:
                        cap_en = t
                    elif re.match(r"^表[A-Z][.\-]?\d+", t) and not cap_cn:
                        cap_cn = t
                    elif t and cap_cn and not cap_en:
                        break
                j -= 1
                steps += 1
            if not (cap_cn and cap_en):
                cap_ok = False
                cap_d.append((cap_cn[:10] or "?", cap_en[:10] or "?"))
        rep.add("AT-05 表题中英文完整", cap_ok,
                f"附录表 {len(tbl_in_app)} 张均具中英题注" if cap_ok else f"缺题: {cap_d}")


def check_references(rep, docx_path):
    d = docx.Document(docx_path)
    paras = d.paragraphs
    ref_start = None
    for i, p in enumerate(paras):
        if p.text.strip() == "参考文献":  # 精确匹配标题段，避免命中目录条目（...参考文献...43）
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
    ap.add_argument("--header-even", default=None,
                    help="偶数页（双页）页眉固定文字，如 \"哈尔滨工程大学本科生毕业论文\"")
    ap.add_argument("--en-title", default=None, help="英文题目文本（用于 AF-02/AF-03）")
    ap.add_argument("--body-start-page", type=int, default=None, help="正文起始页（1-based）")
    ap.add_argument("--body-start-marker", default=None, help="正文起始页定位文本标记")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    check_header(rep, args.pdf, args.template_pdf, header_even=args.header_even,
                 body_start_marker=args.body_start_marker, body_start_page=args.body_start_page)
    check_abstract(rep, args.pdf, en_title=args.en_title)
    check_appendix_tables(rep, args.docx, args.pdf)
    check_references(rep, args.docx)
    path = rep.save()
    print("report:", path)
    return 0 if all(ok or sk for _, ok, _, sk in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
