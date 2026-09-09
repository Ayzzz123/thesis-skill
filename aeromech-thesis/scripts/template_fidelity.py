# -*- coding: utf-8 -*-
"""template_fidelity.py — Template Fidelity 通用原语（aeromech-thesis v1.1.0）

双模式：TEMPLATE_FIDELITY（有可编辑学校 Word 模板，原始 DOCX 为母版）
        FORMAT_RECONSTRUCTION（无模板，规范解析+重建）。

内容：模式选择、母版复制/修剪、sectPr 页码防重启、页脚/页眉、封面字段填值、
      模板风格段落/标题/题注、md 内容解析（题注跨空行、表格分隔保护）。

用法：项目层 build_docx_<project>.py 引用本模块；禁止把项目内容硬编码进本文件。
"""
import os
import re
import shutil

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

try:
    import docx_engine as E
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    import docx_engine as E

MODE_TEMPLATE_FIDELITY = "template_fidelity"
MODE_FORMAT_RECONSTRUCTION = "format_reconstruction"
SCHOOL_EXTS = (".docx", ".dotx")


# ---------------- 模式选择 ----------------
def select_docx_mode(school_dir):
    """school_dir 下存在可编辑 Word 模板 -> TEMPLATE_FIDELITY；否则 FORMAT_RECONSTRUCTION。
    返回 (mode, template_path_or_None)。"""
    if school_dir and os.path.isdir(school_dir):
        for fn in sorted(os.listdir(school_dir)):
            low = fn.lower()
            if low.endswith(SCHOOL_EXTS) and not low.startswith("~$"):
                return MODE_TEMPLATE_FIDELITY, os.path.join(school_dir, fn)
    return MODE_FORMAT_RECONSTRUCTION, None


def document_generation_record(mode, template_file=None):
    """写 state.yaml document_generation 字段的字典（由 Master 合并进 state）。"""
    return {"mode": mode, "template_file": template_file or None}


# ---------------- sectPr 页码防重启 ----------------
def clear_pgnum(sec):
    sp = sec._sectPr
    el = sp.find(qn("w:pgNumType"))
    if el is not None:
        sp.remove(el)


def set_pgnum(sec, fmt=None, start=None):
    sp = sec._sectPr
    el = sp.find(qn("w:pgNumType"))
    if el is None:
        el = OxmlElement("w:pgNumType")
        sp.append(el)
    if fmt:
        el.set(qn("w:fmt"), fmt)
    if start is not None:
        el.set(qn("w:start"), str(start))


def add_section_continue(doc, fmt=None):
    """新建节并延续页码：清除继承的 start，显式给 fmt（不带 start）。
    修复 python-docx add_section 复制上一节 pgNumType(start=1) 导致页码重开的缺陷。"""
    doc.add_section(WD_SECTION.NEW_PAGE)
    sec = doc.sections[-1]
    clear_pgnum(sec)
    if fmt:
        set_pgnum(sec, fmt=fmt)
    return sec


def footer_page_field(sec, size=9, cn="宋体"):
    sec.footer.is_linked_to_previous = False
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    E.set_font(run, cn, size)


def header_text(sec, text, size=9, cn="宋体"):
    sec.header.is_linked_to_previous = False
    p = sec.header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    E.set_font(run, cn, size)


def toc_field_para(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = r'TOC \o "1-3" \h \z \u'
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t"); t.text = "（目录：排版占位，将在 Word 中更新域后生成）"
    f3 = OxmlElement("w:fldChar"); f3.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2); run._r.append(t); run._r.append(f3)
    return p


# ---------------- 母版修剪 ----------------
def open_master(template_path, out_path):
    """复制原始模板为交付副本并打开。返回 Document。模板文件只读。"""
    shutil.copy(template_path, out_path)
    return Document(out_path)


def body_element_list(doc):
    return list(doc.element.body.iterchildren())


def first_sectpr_anchor_after(doc, element):
    """返回 element 之后第一个含 pPr/sectPr 的段落元素（节结束锚点）。"""
    seen = False
    for child in body_element_list(doc):
        if child is element:
            seen = True
            continue
        if not seen:
            continue
        if child.tag == qn("w:p"):
            pPr = child.find(qn("w:pPr"))
            if pPr is not None and pPr.find(qn("w:sectPr")) is not None:
                return child
    return None


def trim_body_after(doc, anchor, keep_final_sectpr=True):
    """删除 anchor 之后、body 级 sectPr 之前的所有内容（样例区），保留结构部件。
    anchor 段落本身保留（作为前一节的结束锚点）。返回删除元素数。"""
    body = doc.element.body
    final_sect = None
    for el in body.iterchildren():
        if el.tag == qn("w:sectPr"):
            final_sect = el
            break
    removed = 0
    seen = False
    for el in list(body.iterchildren()):
        if el is anchor:
            seen = True
            continue
        if seen and el is not final_sect:
            body.remove(el)
            removed += 1
    return removed


def remove_anchor_paragraph(doc, anchor):
    """删除中间节锚点段落（用于把两个模板节合并为一个内容节）。"""
    doc.element.body.remove(anchor)


# ---------------- 封面字段填值 ----------------
def fill_cover_fields(doc, values):
    """values: {模板标签前缀: 值}；在首个 1x1 表格内定位标签段并填值。
    优先使用标签后第一个空段；无空段则在同一段末尾追加。缺失字段保持空槽。"""
    if not doc.tables:
        return {}
    cell = doc.tables[0].cell(0, 0)
    paras = cell.paragraphs
    filled = {}
    for label, value in values.items():
        if value is None or str(value).strip() == "":
            continue
        for i, p in enumerate(paras):
            if label in p.text:
                if i + 1 < len(paras) and not paras[i + 1].text.strip():
                    target = paras[i + 1]
                else:
                    target = p
                run = target.add_run(str(value))
                E.set_font(run, "宋体", 14)
                filled[label] = str(value)
                break
    return filled


# ---------------- 模板风格段落 ----------------
def ppr(p, line=400, rule="exact", before=None, after=None, jc=None,
        first=None, firstChars=None, keep_next=False, page_break=False, outline=None):
    pPr = p._p.get_or_add_pPr()
    sp = pPr.find(qn("w:spacing"))
    if sp is None:
        sp = OxmlElement("w:spacing"); pPr.append(sp)
    if line is not None:
        sp.set(qn("w:line"), str(line)); sp.set(qn("w:lineRule"), rule)
    if before is not None:
        sp.set(qn("w:before"), str(before))
    if after is not None:
        sp.set(qn("w:after"), str(after))
    if jc is not None:
        j = OxmlElement("w:jc"); j.set(qn("w:val"), jc); pPr.append(j)
    if first is not None or firstChars is not None:
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind"); pPr.append(ind)
        if first is not None:
            ind.set(qn("w:firstLine"), str(first))
        if firstChars is not None:
            ind.set(qn("w:firstLineChars"), str(firstChars))
    if keep_next:
        pPr.append(OxmlElement("w:keepNext"))
    if page_break:
        pb = OxmlElement("w:pageBreakBefore"); pPr.append(pb)
    if outline is not None:
        ol = OxmlElement("w:outlineLvl"); ol.set(qn("w:val"), str(outline)); pPr.append(ol)
    return pPr


def rpr(run, ascii_f="Times New Roman", ea="宋体", sz=12, bold=False, sup=False):
    rPr = run._r.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rPr.append(rf)
    rf.set(qn("w:ascii"), ascii_f); rf.set(qn("w:hAnsi"), ascii_f)
    rf.set(qn("w:eastAsia"), ea); rf.set(qn("w:hint"), "eastAsia")
    for tag in ("w:sz", "w:szCs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag); rPr.append(el)
        el.set(qn("w:val"), str(int(sz * 2)))
    if bold:
        rPr.append(OxmlElement("w:b"))
    if sup:
        va = OxmlElement("w:vertAlign"); va.set(qn("w:val"), "superscript"); rPr.append(va)
    return run


def add_para_runs(p, text, ascii_f="Times New Roman", ea="宋体", sz=12, bold=False):
    for seg in re.split(r"(\*\*.+?\*\*|\[\d+\])", text):
        if not seg:
            continue
        run = p.add_run(seg)
        if seg.startswith("**") and seg.endswith("**"):
            rpr(run, ascii_f, ea, sz, bold=True)
        elif re.fullmatch(r"\[\d+\]", seg):
            rpr(run, ascii_f, ea, sz, bold=bold, sup=True)
        else:
            rpr(run, ascii_f, ea, sz, bold=bold)
    return p


def add_body(doc, text, ea="宋体", sz=12, first=480, firstChars=200,
             kai=False, jc="left", line=400, rule="exact"):
    p = doc.add_paragraph()
    kw = dict(line=line, rule=rule, jc=jc)
    if firstChars:
        kw["first"] = first; kw["firstChars"] = firstChars
    ppr(p, **kw)
    add_para_runs(p, text, ea=("楷体" if kai else ea), sz=(10.5 if kai else sz))
    return p


def add_h1(doc, text, page_break=False, ea="黑体", sz=16, line=400):
    p = doc.add_paragraph(style="Heading 1")
    ppr(p, line=line, rule="exact", before=480, after=360, jc="center",
        keep_next=True, page_break=page_break)
    for r in p.runs:
        r._r.getparent().remove(r._r)
    add_para_runs(p, text, ea=ea, sz=sz)
    return p


def add_h2(doc, text, ea="黑体", sz=14, style="Heading 2"):
    try:
        p = doc.add_paragraph(style=style)
    except KeyError:
        p = doc.add_paragraph()
    ppr(p, line=400, rule="exact", jc="left", keep_next=True)
    for r in p.runs:
        r._r.getparent().remove(r._r)
    add_para_runs(p, text, ea=ea, sz=sz)
    return p


def add_h3(doc, text, ea="宋体", sz=12):
    p = doc.add_paragraph()
    ppr(p, line=400, rule="exact", jc="left", keep_next=True, outline=2)
    add_para_runs(p, text, ea=ea, sz=sz)
    return p


def caption_paras(doc, cn_text, en_text, cn_ea="黑体", en_ea="黑体", sz=10.5):
    p = doc.add_paragraph()
    ppr(p, line=360, rule="auto", jc="center", keep_next=True)
    add_para_runs(p, cn_text, ea=cn_ea, sz=sz)
    p2 = doc.add_paragraph()
    ppr(p2, line=360, rule="auto", jc="center")
    add_para_runs(p2, en_text, ea=en_ea, sz=sz)
    return p


def add_md_table(doc, rows, cap_cn=None, cap_en=None, font=10.5, usable=None):
    if cap_cn:
        caption_paras(doc, cap_cn, cap_en or "")
    header, data = rows[0], rows[1:]
    weights = []
    for h in header:
        if any(k in h for k in ("S", "O", "D", "RPN", "序号")):
            weights.append(0.5)
        elif len(h) >= 8:
            weights.append(1.5)
        else:
            weights.append(1.0)
    width_total = usable or (25.7 if usable == 0 else 16.5)
    if usable == 0:
        width_total = 25.7
    elif usable is None:
        width_total = 16.5
    widths = [width_total * w / sum(weights) for w in weights]
    E.add_table(doc, header, data, font_size=font, compact=(font <= 9.0), widths_cm=widths)
    return doc.tables[-1]


def parse_md(doc, md, fig_dir=None, cap_map=None, en_map=None, in_body=True):
    """md 章节解析：标题/#；图占位（（图x-y …））；表题+表行（跨空行采集，题注不因空行丢失）；
    正文段落（[n] 上标引用；本章待核实清单→楷体注）。"""
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        m = re.fullmatch(r"(#{1,3})\s+(.*)", s)
        if m:
            lvl = len(m.group(1))
            if in_body:
                if lvl == 1:
                    add_h1(doc, m.group(2).strip(), page_break=True)
                elif lvl == 2:
                    add_h2(doc, m.group(2).strip())
                else:
                    add_h3(doc, m.group(2).strip())
            i += 1
            continue
        m = re.match(r"^（图(\d+-\d+)[^）]*（[^）]*）[^）]*）$", s) or \
            re.match(r"^（图(\d+-\d+)[^）]*）$", s)
        if m and cap_map and m.group(1) in cap_map:
            key = m.group(1)
            fname = cap_map[key][0] if isinstance(cap_map[key], tuple) else None
            path = os.path.join(fig_dir, fname) if (fig_dir and fname) else None
            if path and os.path.exists(path):
                E.figure_block(doc, path,
                               cap_map[key][1] if isinstance(cap_map[key], tuple) else cap_map[key])
            else:
                add_body(doc, s)  # 无图文件时保留占位行（诚实降级）
            i += 1
            continue
        if s.startswith("|"):
            i += 1
            continue
        m = re.match(r"^(表(\d+-\d+|A-\d+|B-\d+))[ \u3000]*", s)
        if m and en_map and m.group(2) in en_map:
            j = i + 1
            tbl = []
            while j < len(lines):
                st = lines[j].strip()
                if st.startswith("|"):
                    tbl.append(lines[j]); j += 1
                elif st == "":
                    j += 1
                    if j < len(lines) and not lines[j].strip().startswith("|"):
                        break
                else:
                    break
            rows = []
            for ln in tbl:
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    continue
                rows.append(cells)
            if rows:
                add_md_table(doc, rows, cap_cn=s, cap_en=en_map[m.group(2)],
                             font=9.0 if len(rows) > 12 else 10.5)
            i = j
            continue
        if in_body:
            add_body(doc, s, kai=s.startswith("本章待核实清单"))
        else:
            add_body(doc, s)
        i += 1
