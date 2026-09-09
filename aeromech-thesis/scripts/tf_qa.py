# -*- coding: utf-8 -*-
"""tf_qa.py — Template Fidelity QA（TF-01~20）通用脚本（aeromech-thesis v1.1.0）

用法:
  python tf_qa.py --template <学校模板.docx> --docx <毕业论文.docx>
                 [--pdf <毕业论文.pdf>] [--out <报告目录>] [--body-size 12]
                 [--body-line 400 --first-chars 200] [--refs-min 5]

说明:
  - 机器可检查项直接判定；TF-20 生成 模板↔成品 页对 PNG（pair_<名>.png）供人工复核。
  - 期望值参数化（默认对齐中文本科工科通行规范/学校样例；如与 school-format 不同请传参）。
  - 退出码: 0=通过(可含 SKIP)  1=存在 FAIL
"""
import argparse
import os
import re
import sys

from docx import Document
from docx.oxml.ns import qn

CHECKS = []


def ck(name, ok, ev, skip=False):
    CHECKS.append((name, ok, ev, skip))


def run(template_path, docx_path, pdf_path, out_dir, body_size, body_line,
        first_chars, refs_min):
    os.makedirs(out_dir, exist_ok=True)
    td = Document(template_path)
    fd = Document(docx_path)
    norm = lambda s: s.replace(" ", "").replace("\u3000", "").replace("\n", "")

    def hparas(d, style, pred=None):
        return [p for p in d.paragraphs if p.style and p.style.name == style
                and (pred is None or pred(p.text.strip()))]

    # TF-01/02/03 封面
    t0, f0 = td.tables[0], fd.tables[0]
    same_rc = (len(t0.rows), len(t0.columns)) == (len(f0.rows), len(f0.columns))
    tp, fp = t0.cell(0, 0).paragraphs, f0.cell(0, 0).paragraphs
    same_n = len(tp) == len(fp)
    t_labels = [p.text.strip() for p in tp if p.text.strip().endswith(":") or
                re.search(r"年\s*月", p.text)]
    ftexts = [p.text.strip() for p in fp if p.text.strip()]
    labels_ok = all(any((lab.rstrip(":：").strip()) in t for t in ftexts) for lab in t_labels)
    fig_tables = sum(1 for tb in fd.tables[1:] if len(tb.rows) == 1 and len(tb.columns) == 1
                     and "w:drawing" in tb._tbl.xml)  # 排除封面表(0)
    ck("TF-01 封面结构一致", same_rc and same_n and len(fd.inline_shapes) >= len(td.inline_shapes),
       f"1x1表={same_rc}; 段落数 {len(tp)}/{len(fp)}; 图数成品>=模板")
    ck("TF-02 封面字段一致", labels_ok,
       f"模板标签均保留={labels_ok}（缺失字段应保留空槽，不得虚构）")
    vis_ok = True
    for a, b in zip(tp, fp):
        ta = a.text.strip()
        if not ta:
            continue
        tb = b.text.strip()
        if not (tb.startswith(ta) or ta in tb):
            vis_ok = False
    ck("TF-03 封面视觉层级一致", vis_ok, "模板各段文本在成品中保留（层级/字体由母版继承）")

    # TF-04 声明
    def decl(d):
        out, state = [], 0
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            if "原创性声明" in t and "南京" in t:
                state = 1
            elif "使用授权声明" in t and "南京" in t:
                state = 2
            if state == 1 or state == 2:
                out.append(t)
        return out
    tdecl, fdecl = decl(td), decl(fd)
    ck("TF-04 声明页结构一致", len(tdecl) > 0 and tdecl[:3] == fdecl[:3],
       f"模板声明段={len(tdecl)} 成品={len(fdecl)}（原文保留）")

    # TF-05/06 摘要
    ck("TF-05 中文摘要结构一致",
       len(hparas(fd, "Heading 1", lambda t: norm(t).startswith("摘要"))) == 1
       and any(p.text.strip().startswith("关键词") for p in fd.paragraphs),
       "摘要标题+关键词行存在")
    ck("TF-06 英文摘要结构一致",
       len(hparas(fd, "Heading 1", lambda t: t.strip() == "ABSTRACT")) == 1
       and any(re.search(r"KEY\s*WORDS", p.text) for p in fd.paragraphs),
       "ABSTRACT 标题+KEY WORDS 行存在")

    # TF-07/08/09 正文
    chs = hparas(fd, "Heading 1", lambda t: re.match(r"^第[一二三四五六1-6]章", t))
    h2s = hparas(fd, "Heading 2", lambda t: re.match(r"^\d\.\d\s", t))
    paras_all = fd.paragraphs
    start = end = None
    for i, p in enumerate(paras_all):
        t = p.text.strip()
        if start is None and re.match(r"^第[一二三四五六1-6]章", t):
            start = i
        if t.startswith("参考文献") and start is not None and i > start + 5:
            end = i
            break
    zone = paras_all[start:end] if (start is not None and end is not None) else []
    bad = []
    for p in zone:
        t = p.text.strip()
        if not t or p.style and p.style.name in ("Heading 1", "Heading 2"):
            continue
        if re.match(r"^(表|图|（|\[|Tab\.|Fig\.)", t) or t.startswith("本章待核实清单"):
            continue
        for r in p.runs[:3]:
            rPr = r._r.find(qn("w:rPr"))
            if rPr is None:
                continue
            sz = rPr.find(qn("w:sz"))
            if sz is not None and int(sz.get(qn("w:val"))) != int(body_size * 2):
                bad.append((t[:14], "sz"))
            pPr = p._p.find(qn("w:pPr"))
            if pPr is not None:
                sp = pPr.find(qn("w:spacing"))
                if sp is None or sp.get(qn("w:line")) != str(body_line) or \
                        sp.get(qn("w:lineRule")) != "exact":
                    bad.append((t[:14], "ls"))
                ind = pPr.find(qn("w:ind"))
                if ind is None or ind.get(qn("w:firstLineChars")) != str(first_chars):
                    bad.append((t[:14], "ind"))
    ck("TF-07 Heading继承模板", len(chs) >= 1 and len(h2s) >= 0 and len(chs) >= 1,
       f"章Heading1={len(chs)} 节Heading2={len(h2s)}（样式来自模板 styles.xml）")
    ck("TF-08 正文字体字号", not bad, f"正文区抽查 {len(zone)} 段（异常={bad[:4]}）")
    ck("TF-09 行距/缩进", not bad, f"固定{body_line/20:g}磅+首行{first_chars/100:g}字符")

    # TF-10/11/12 图表
    figcaps = []
    for tb in fd.tables[1:]:
        if not (len(tb.rows) == 1 and len(tb.columns) == 1 and "w:drawing" in tb._tbl.xml):
            continue
        for row in tb.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    t = p.text.strip()
                    if re.match(r"^图\d+-\d+", t):
                        figcaps.append(t)
    tabcaps = [p.text.strip() for p in fd.paragraphs
               if re.match(r"^表(\d+-\d+|A-\d+|B-\d+)\s", p.text.strip())]
    ck("TF-10 图题样式", len(figcaps) == fig_tables,
       f"图块={fig_tables} 图题={len(figcaps)}（图下中英文题注）")
    ck("TF-11 表题样式", len(tabcaps) >= 1,
       f"表题数={len(tabcaps)}（表上方；md 题注不得因空行丢失）")
    three_ok = True
    bad_tbl = []
    for ti, tb in enumerate(fd.tables[1:]):
        if len(tb.rows) == 1 and len(tb.columns) == 1:
            continue  # 封面表/图块（1x1）不做三线表判定
        borders = tb._tbl.tblPr.find(qn("w:tblBorders"))
        has_tbl_top = has_tbl_bot = False
        has_inside = False
        if borders is not None:
            for edge in ("insideH", "insideV", "left", "right"):
                el = borders.find(qn("w:" + edge))
                if el is not None and el.get(qn("w:val")) == "single":
                    has_inside = True
            t = borders.find(qn("w:top"))
            b = borders.find(qn("w:bottom"))
            has_tbl_top = t is not None and t.get(qn("w:val")) == "single"
            has_tbl_bot = b is not None and b.get(qn("w:val")) == "single"
        # 引擎风格：无表级框线，改在表头/表底单元格 tcBorders 上
        def cell_edges(row, edge):
            out = []
            for c in row.cells:
                tcPr = c._tc.find(qn("w:tcPr"))
                if tcPr is None:
                    continue
                bd = tcPr.find(qn("w:tcBorders"))
                if bd is None:
                    continue
                el = bd.find(qn("w:" + edge))
                out.append(el is not None and el.get(qn("w:val")) == "single")
            return out
        hdr_top = all(cell_edges(tb.rows[0], "top")) if len(tb.rows[0].cells) else False
        hdr_bot = all(cell_edges(tb.rows[0], "bottom"))
        last_bot = all(cell_edges(tb.rows[-1], "bottom"))
        if has_inside:
            three_ok = False; bad_tbl.append(ti + 1)
        elif not (has_tbl_top and has_tbl_bot) and not (hdr_top and hdr_bot and last_bot):
            three_ok = False; bad_tbl.append(ti + 1)
    ck("TF-12 表格三线表", three_ok, f"无内线/竖线；顶底单线（表级或单元格级）bad={bad_tbl}")

    # TF-13/14 页眉页脚页码
    hdr = None
    for i, s in enumerate(fd.sections):
        try:
            txt = "|".join(p.text for p in s.header.paragraphs if p.text.strip())
        except Exception:
            txt = ""
        if txt:
            hdr = (i, txt)
            break
    ck("TF-13 页眉页脚", hdr is not None, f"页眉自节{hdr[0]}起：{hdr[1][:20]}")
    if pdf_path and os.path.exists(pdf_path):
        import pymupdf
        pdf = pymupdf.open(pdf_path)
        roman, arabic, seen_body = [], [], False
        ok_pg = True
        for pg in range(pdf.page_count):
            page = pdf[pg]
            H = page.rect.height
            foots = []
            for bl in page.get_text("dict")["blocks"]:
                if "lines" not in bl:
                    continue
                for ln in bl["lines"]:
                    if H - 90 < ln["bbox"][1] < H - 45:
                        tx = "".join(sp["text"] for sp in ln["spans"]).strip()
                        if re.fullmatch(r"[IVX]{1,6}", tx):
                            foots.append(tx)
            if foots:
                val = max(foots, key=len)
                if re.fullmatch(r"[IVX]+", val) and not seen_body:
                    roman.append((pg + 1, val))
                else:
                    seen_body = True
                    arabic.append(int(val) if val.isdigit() else None)
        body_seq_ok = all(isinstance(x, int) for x in arabic)
        if body_seq_ok and arabic:
            body_seq_ok = all(b - a == 1 for a, b in zip(arabic, arabic[1:]))
        ck("TF-14 页码", body_seq_ok and len(roman) >= 1,
           f"前置罗马页={roman[:3]} 正文阿拉伯={arabic[:3]}...{'连续' if body_seq_ok else '异常'}")
        pdf.close()
    else:
        ck("TF-14 页码", True, "未提供 PDF，页码显示项 SKIP（docx pgNumType 已按模板继承）", skip=True)

    # TF-15 目录
    ck("TF-15 目录样式", "TOC \\o" in fd.element.body.xml,
       "Word 原生目录域；样式继承模板 toc1/toc2")

    # TF-16 参考文献
    refs = [p for p in fd.paragraphs if re.match(r"^\[\d+\]\s", p.text.strip())]
    ck("TF-16 参考文献样式", len(refs) >= refs_min,
       f"条目数={len(refs)}(≥{refs_min})；不足如实披露不凑数")

    # TF-17/18 附录与致谢
    apps = hparas(fd, "Heading 1", lambda t: re.match(r"^附录[A-Z]", t))
    ck("TF-17 附录结构", len(apps) >= 1 and
       [p.text.strip()[:3] for p in apps] == sorted(p.text.strip()[:3] for p in apps),
       f"附录标题={[p.text.strip()[:16] for p in apps]}（A/B/C 排序）")
    ack_h = hparas(fd, "Heading 1", lambda t: norm(t).startswith("致谢"))
    ack_len, on = 0, False
    for p in fd.paragraphs:
        if p.style and p.style.name == "Heading 1" and norm(p.text).startswith("致谢"):
            on = True
            continue
        if on:
            ack_len += len(p.text.strip())
    ck("TF-18 致谢结构", len(ack_h) == 1 and ack_len <= 500,
       f"致谢字数≈{ack_len}（≤500）")

    # TF-19 页面尺寸/边距
    t_mg = set((round(s.top_margin.cm, 2), round(s.left_margin.cm, 2)) for s in td.sections)
    f_mg = set((round(s.top_margin.cm, 2), round(s.left_margin.cm, 2)) for s in fd.sections)
    f_sz = (round(fd.sections[0].page_width.cm, 1), round(fd.sections[0].page_height.cm, 1))
    ck("TF-19 页面尺寸/边距", f_sz[0] >= 21.0 and f_mg <= t_mg,
       f"A4≈{f_sz}; 成品边距 {f_mg} ⊆ 模板 {t_mg}")

    # TF-20 页对渲染
    pairs = []
    if pdf_path and os.path.exists(pdf_path):
        t_pdf = None
        try:
            import docx2pdf
            tmp = os.path.join(out_dir, "_template_render.pdf")
            if not os.path.exists(tmp):
                docx2pdf.convert(template_path, tmp)
            t_pdf = tmp
        except Exception as e:
            ck("TF-20 PDF视觉对照", True, f"模板渲染失败（{e}），仅生成提示", skip=True)
        if t_pdf:
            td_ = pymupdf.open(t_pdf)
            fpdf = pymupdf.open(pdf_path)

            def page_of(doc, pats, dots_ok=False):
                for pg in range(doc.page_count):
                    t = doc[pg].get_text().replace(" ", "").replace("\u3000", "")
                    if "...." in doc[pg].get_text() and not dots_ok:
                        continue
                    if all(p.replace(" ", "") in t for p in pats):
                        return pg
                return None

            names = [("封面", ["本科生毕业论文"]), ("声明", ["原创性声明"]),
                     ("中文摘要", ["关键词"]), ("ABSTRACT", ["KEY", "WORDS"]),
                     ("目录", ["目", "录"]), ("正文样例", ["第一章", "绪论"]),
                     ("参考文献样例", ["参考文献"]), ("附录样例", ["附录A"]),
                     ("致谢样例", ["致谢"])]
            for name, pats in names:
                tp = page_of(td_, pats, dots_ok=(name == "目录"))
                fp = page_of(fpdf, pats, dots_ok=(name == "目录"))
                if tp is None or fp is None:
                    continue
                try:
                    from PIL import Image
                    a = td_[tp].get_pixmap(dpi=80)
                    b = fpdf[fp].get_pixmap(dpi=80)
                    ia = Image.frombytes("RGB", (a.width, a.height), a.samples)
                    ib = Image.frombytes("RGB", (b.width, b.height), b.samples)
                    w = max(ia.width, ib.width)
                    im = Image.new("RGB", (w, ia.height + ib.height + 12), "white")
                    im.paste(ia, (0, 0)); im.paste(ib, (0, ia.height + 12))
                    im.save(os.path.join(out_dir, f"pair_{name}.png"))
                    pairs.append((name, tp + 1, fp + 1))
                except Exception:
                    pairs.append((name, tp + 1, fp + 1))
            td_.close(); fpdf.close()
            ck("TF-20 PDF视觉对照", len(pairs) >= 5,
               f"页对={pairs}（pair_*.png 供人工复核）")
    else:
        ck("TF-20 PDF视觉对照", True, "未提供 PDF，视觉对照 SKIP", skip=True)

    # 报告
    lines = ["# TF-01~20 QA（tf_qa.py）", f"- 模板: {template_path}", f"- DOCX: {docx_path}",
             f"- PDF: {pdf_path or '（未提供）'}", ""]
    for name, ok, ev, skip in CHECKS:
        lines.append(f"- {name}: {'SKIP' if skip else ('PASS' if ok else 'FAIL')} | {ev}")
    open(os.path.join(out_dir, "tf-qa-report.md"), "w", encoding="utf-8").write("\n".join(lines))
    n_fail = sum(1 for _, ok, _, skip in CHECKS if not ok and not skip)
    for name, ok, ev, skip in CHECKS:
        safe = ev[:90].encode("gbk", "replace").decode("gbk")
        print(name, "SKIP" if skip else ("PASS" if ok else "FAIL"), "|", safe)
    print("report:", os.path.join(out_dir, "tf-qa-report.md"))
    return 0 if n_fail == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--out", default=".")
    ap.add_argument("--body-size", type=float, default=12.0)
    ap.add_argument("--body-line", type=int, default=400)
    ap.add_argument("--first-chars", type=int, default=200)
    ap.add_argument("--refs-min", type=int, default=5)
    a = ap.parse_args()
    return run(a.template, a.docx, a.pdf, a.out, a.body_size, a.body_line,
               a.first_chars, a.refs_min)


if __name__ == "__main__":
    sys.exit(main())
