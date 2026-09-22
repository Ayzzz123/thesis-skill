# -*- coding: utf-8 -*-
"""template_fidelity.py — Template Fidelity 通用原语（aeromech-thesis v1.1.0；v1.3.11 增补 legacy .doc）

双模式：TEMPLATE_FIDELITY（有可编辑学校 Word 模板，原始 DOCX 为母版）
        FORMAT_RECONSTRUCTION（无模板，规范解析+重建）。

内容：模式选择、母版复制/修剪、sectPr 页码防重启、页脚/页眉、封面字段填值、
      模板风格段落/标题/题注、md 内容解析（题注跨空行、表格分隔保护）、
      legacy .doc（Word 97-2003）学校材料检测与转换（detect_legacy_docs/convert_legacy_doc）。

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
DOC_LEGACY_EXTS = (".doc",)  # Word 97-2003 OLE2，不能直接作 OOXML 母版，需先转换


# ---------------- 模式选择 ----------------
def iter_school_docs(school_dir):
    """学校资料递归发现（v1.6.5 E2E-FINDING-1 修复：目录契约与 CURRENT/FORMS/REFERENCE
    子目录布局对齐，旧扁平布局行为不变）。
    返回 [(abs_path, role)]，role ∈ {"school","forms","reference"}：
      - 顶层文件与 CURRENT/**  → "school"：可进入格式识别、可承担母版；
      - FORMS/**                → "forms"：过程表格，不作为论文格式依据/母版候选；
      - REFERENCE/**            → "reference"：参考材料，不参与当前学校格式依据。
    排序稳定（school → forms → reference，组内按完整路径排序）；~$ 临时文件跳过；
    返回 SCHOOL_EXTS（.docx/.dotx）及 .pdf/.doc（parse 的 PDF 登记与 legacy 提示
    依赖它们；母版选择仅取 SCHOOL_EXTS，由 select_docx_mode 自过滤）。"""
    if not school_dir or not os.path.isdir(school_dir):
        return []
    groups = {"school": [], "forms": [], "reference": []}
    accept = SCHOOL_EXTS + DOC_LEGACY_EXTS + (".pdf",)
    for dp, _dns, fns in os.walk(school_dir):
        rel = os.path.relpath(dp, school_dir).replace("\\", "/")
        first = rel.split("/")[0] if rel != "." else ""
        role = {"CURRENT": "school", "FORMS": "forms",
                "REFERENCE": "reference"}.get(first, "school")
        for fn in fns:
            low = fn.lower()
            if low.endswith(accept) and not fn.startswith("~$"):
                groups[role].append(os.path.join(dp, fn))
    return ([(p, "school") for p in sorted(groups["school"])] +
            [(p, "forms") for p in sorted(groups["forms"])] +
            [(p, "reference") for p in sorted(groups["reference"])])


def select_docx_mode(school_dir):
    """school_dir 的 school 角色文件中存在可编辑 OOXML Word 模板（.docx/.dotx）
    -> TEMPLATE_FIDELITY；否则 FORMAT_RECONSTRUCTION。
    注意：legacy .doc 不在识别范围（不能直接承担母版角色）——请先用
    detect_legacy_docs() 检测、convert_legacy_doc() 转换并分析转换产物性质
    （见 references/template-fidelity.md §11）。
    递归发现经 iter_school_docs（顶层与 CURRENT/；FORMS/REFERENCE 不承担母版角色）。
    返回 (mode, template_path_or_None)。"""
    if school_dir and os.path.isdir(school_dir):
        for path, role in iter_school_docs(school_dir):
            if role != "school":
                continue
            if path.lower().endswith(SCHOOL_EXTS):
                return MODE_TEMPLATE_FIDELITY, path
    return MODE_FORMAT_RECONSTRUCTION, None


CAP_TAB_RE = re.compile(r"^表\s*(\d+)[.\-－—](\d+)|^表\s*([A-Z])[.\-－—]?(\d+)")


def is_data_table(preceding_texts):
    """v1.6 test-8.0 通用判定：论文数据表 = 表上方紧邻存在中文表题（表X-Y / 表A-B，
    其下可有英文题 Tab. 行）。封面/扉页/声明/任务书等**表单表**（label-value 网格）
    无表题，不得按数据表核三线表/列宽/题注（表格式封面母版把表单当数据表=全线误判）。
    preceding_texts: 该表之前若干段文本（文档序倒序：第一段=离表最近）。"""
    for t in preceding_texts[:6]:
        s = (t or "").strip()
        if not s:
            continue
        if CAP_TAB_RE.match(s):
            return True
        if s.startswith("Tab."):
            continue  # 英文题注行：跳过，继续找中文题
        return False  # 其它任何非空文本先于题注 → 非数据表
    return False


def detect_legacy_docs(school_dir):
    """检测 school_dir 下 Word 97-2003 旧格式 .doc 材料（按魔数校验 OLE2）。
    返回文件路径列表。调用方随后应：
      ① convert_legacy_doc() 转换到工作副本（不改动原文件）；
      ② 分析转换产物性质：含封面对象树/可继承样式 -> 可作母版（登记后走 TEMPLATE_FIDELITY）；
         纯规范/文字文档 -> 解析为 school-format，走 FORMAT_RECONSTRUCTION。"""
    out = []
    if school_dir and os.path.isdir(school_dir):
        for fn in sorted(os.listdir(school_dir)):
            low = fn.lower()
            if low.endswith(DOC_LEGACY_EXTS) and not low.startswith("~$"):
                p = os.path.join(school_dir, fn)
                try:
                    with open(p, "rb") as f:
                        if f.read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                            out.append(p)
                except OSError:
                    continue
    return out


def convert_legacy_doc(src_path, out_dir, out_name=None):
    """Word COM 将 .doc（Word 97-2003）转换为 .docx 工作副本。原文件只读、不被修改。
    需要 Windows + Microsoft Word + pywin32；环境不可用时抛 RuntimeError（调用方降级处理）。
    返回转换产物绝对路径。"""
    if not os.path.isfile(src_path):
        raise FileNotFoundError(src_path)
    try:
        import win32com.client  # noqa: WPS433 (lazy import)
    except ImportError as exc:
        raise RuntimeError(
            "legacy .doc conversion requires pywin32 + Microsoft Word (pip install pywin32)"
        ) from exc
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    if out_name is None:
        out_name = os.path.splitext(os.path.basename(src_path))[0] + ".converted.docx"
    out_path = os.path.join(out_dir, out_name)
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(os.path.abspath(src_path), ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.SaveAs2(out_path, FileFormat=16)  # 16 = wdFormatXMLDocument
        finally:
            doc.Close(SaveChanges=0)
    finally:
        word.Quit()
    return out_path


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


def header_text(sec, text, size=9, cn="宋体", doc=None):
    """正文节页眉文字。v1.6 test-8.0：传入母版 Document 时套用其 "header" 段落样式
    （许多学校模板的 header 样式自带下边框横线，如中飞院规范页眉线），样式缺失才
    手设字号；不套用=页眉横线类 QA（HF-02~04）必然失败。"""
    sec.header.is_linked_to_previous = False
    p = sec.header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    applied = False
    if doc is not None:
        try:
            from docx.enum.style import WD_STYLE_TYPE
        except Exception:
            WD_STYLE_TYPE = None
        for s in doc.styles:
            try:
                nm = (s.name or "").strip().lower()
                para_type = WD_STYLE_TYPE is None or s.type == WD_STYLE_TYPE.PARAGRAPH
            except Exception:
                continue
            if nm in ("header", "页眉") and para_type:
                try:
                    p.style = s
                    applied = True
                except Exception:
                    pass
                break
    run = p.add_run(E.unescape_text(text))
    if not applied:
        E.set_font(run, cn, size)
    return p


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


def last_sectpr_anchor_before(doc, element):
    """返回 element 之前最后一个含 pPr/sectPr 的段落元素（节起始锚），无则 None。"""
    found = None
    for child in body_element_list(doc):
        if child is element:
            return found
        if child.tag == qn("w:p"):
            pPr = child.find(qn("w:pPr"))
            if pPr is not None and pPr.find(qn("w:sectPr")) is not None:
                found = child
    return None


def strip_all_pgnumtype(doc):
    """剥除正文中所有段落级 sectPr 的 pgNumType（封面/扉页不显示页码；
    内容节页码由 add_section_continue/set_pgnum 重建）。返回剥除数。"""
    from docx.oxml.ns import qn
    n = 0
    for child in body_element_list(doc):
        if child.tag == qn("w:p"):
            pPr = child.find(qn("w:pPr"))
            sp = pPr.find(qn("w:sectPr")) if pPr is not None else None
            pg = sp.find(qn("w:pgNumType")) if sp is not None else None
            if pg is not None:
                sp.remove(pg)
                n += 1
    return n


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


def trim_body_before(doc, anchor, keep_anchor=True):
    """删除 anchor 之前（不含 body 级 sectPr）的所有内容。v1.6 test-8.0：
    母版为"规范说明+封面样例"合一文档时，先剪掉封面之前的说明页区，使封面节
    成为第一节。keep_anchor=False 时锚点段本身也删除（其 sectPr 属于被剪掉的
    前一节——留着会产生一个空白首节页）。"""
    body = doc.element.body
    removed = 0
    for el in list(body.iterchildren()):
        if el is anchor:
            if not keep_anchor and el.tag != qn("w:sectPr"):
                body.remove(el)
                removed += 1
            break
        if el.tag == qn("w:sectPr"):
            continue
        body.remove(el)
        removed += 1
    return removed


def remove_anchor_paragraph(doc, anchor):
    """删除中间节锚点段落（用于把两个模板节合并为一个内容节）。"""
    doc.element.body.remove(anchor)


def strip_page_break_runs(p_el):
    """删除段落内的显式分页符 run（w:br w:type="page"）。母版节锚点段常带分页符，
    裁剪后保留锚点段会额外产生空白页；节断开本身已起新页（test-8.0 母版实测）。
    返回删除数。"""
    n = 0
    for r in list(p_el.iter(qn("w:r"))):
        for br in r.findall(qn("w:br")):
            if br.get(qn("w:type")) == "page":
                r.remove(br)
                n += 1
        if n and not r.findall(qn("w:t")) and not r.findall(qn("w:br")) \
                and not r.findall(qn("w:drawing")) and not r.findall(qn("w:pict")):
            r.getparent().remove(r)
    return n


# ---------------- 封面字段填值 ----------------
def _norm_label(s):
    return re.sub(r"[\s　:：]", "", s or "")


_PH_RE = re.compile(r"^[Xx×]{2,}\S{0,6}$|^[\sXx×]{2,}$")


def _looks_ph(txt):
    """封面值槽占位判定：整段以 X 结尾（"张 X"）或含连续 X 占位（"XXXX"/"2018XXXXXX"）。"""
    t = (txt or "").strip()
    if not t:
        return False
    return bool(re.search(r"[Xx×]{1,}\s*$", t) or re.search(r"[Xx×]{2,}", t))


def fill_cover_fields(doc, values, table_limit=None):
    """values: {模板标签: 值}。table_limit=None（v1.5 兼容）：在首个 1x1 表格内定位
    标签段并填值（标签后空段/同行追加）。
    table_limit=整数：v1.6 test-8.0 通用封面——在全部封面表（前 table_limit 张）内做
    标签归一匹配（去空白/冒号），值写入：①同行下一格含占位（X 式）→ 替换占位段保留
    首 run 格式（下划线）；②同格标签段之后首个占位/空段 → 填入；非占位静态文本不猜写
    （记未填，交付报告披露）。返回 {label: value}（已填）。"""
    if not doc.tables:
        return {}
    tables = doc.tables[:table_limit] if table_limit else doc.tables[:1]
    if table_limit:
        return _fill_cover_grid(tables, values)
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
                run = target.add_run(E.unescape_text(str(value)))
                E.set_font(run, "宋体", 14)
                filled[label] = str(value)
                break
    return filled


def _replace_placeholder_para(p, value):
    """占位段 → 值：保留首 run 格式（字体/下划线），其余 run 清空（"张 X" 跨 run 场景）。"""
    value = E.unescape_text(str(value))
    runs = p.runs
    if not runs:
        p.add_run(value)
        return True
    runs[0].text = value
    for r in runs[1:]:
        r.text = ""
    return True


def _fill_cover_grid(tables, values):
    """同一标签在多张封面表（封面页+扉页）出现时全部填充：逐表独立搜索，每表至多填一处。
    v1.6 test-8.0 通用规则（表单语义）：值槽=标签右侧同行第一个非标签格（文本归一后
    不以冒号结尾即为值槽，如 "XXXXXX"/"张 X"/"专业名称"/"XX学院"），整格重写为值并
    保留格式；右侧无值槽（单格封面表，如南京农大式"标签段+空段"）→ 标签段后首个
    占位/空段填入。契约未映射的字段不动（示例文本原样保留）。"""
    filled = {}
    known_labels = {_norm_label(k) for k in values}

    def is_label_cell(txt):
        # 表单语义：标签格以冒号结尾（"姓    名："），值格不以冒号结尾（"张 X"）
        t = (txt or "").strip()
        return t.endswith(":") or t.endswith("：")

    for label, value in values.items():
        if value is None or str(value).strip() == "":
            continue
        nl = _norm_label(label)
        for t in tables:
            hit = False
            for row in t.rows:
                cells = row.cells
                for ci, cell in enumerate(cells):
                    lab_p = next((p for p in cell.paragraphs
                                  if nl and nl in _norm_label(p.text)), None)
                    if lab_p is None:
                        continue
                    # ①右侧同行第一个非标签格 = 值槽
                    for cj in range(ci + 1, len(cells)):
                        vc = cells[cj]
                        vt = "".join(p.text for p in vc.paragraphs).strip()
                        if vt and is_label_cell(vt):
                            continue
                        paras = vc.paragraphs
                        first = next((p for p in paras if p.text.strip()), paras[0])
                        _replace_placeholder_para(first, value)
                        for p in paras:
                            if p is not first and p.text.strip():
                                for r in p.runs:
                                    r.text = ""
                        filled[label] = str(value)
                        hit = True
                        break
                    if hit:
                        break
                    # ②同格标签段之后的占位/空段（单格封面表）
                    paras = cell.paragraphs
                    for k in range(paras.index(lab_p) + 1, len(paras)):
                        p = paras[k]
                        if _looks_ph(p.text):
                            _replace_placeholder_para(p, value)
                            filled[label] = str(value)
                            hit = True
                            break
                        if not p.text.strip():
                            p.add_run(E.unescape_text(str(value)))
                            filled[label] = str(value)
                            hit = True
                            break
                    if hit:
                        break
                if hit:
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
    # v1.6 test-8.0：逐段解码 HTML/XML 实体（外部元数据源如 Crossref 的 &amp; 等）；
    # 在标记切分之后解码，避免解码结果被误当作 **/[n] 标记二次解释。
    for seg in re.split(r"(\*\*.+?\*\*|\[\d+\])", text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**"):
            run = p.add_run(E.unescape_text(seg[2:-2]))  # 剥离 Markdown 加粗标记
            rpr(run, ascii_f, ea, sz, bold=True)
        elif re.fullmatch(r"\[\d+\]", seg):
            run = p.add_run(seg)
            rpr(run, ascii_f, ea, sz, bold=bold, sup=True)
        else:
            run = p.add_run(E.unescape_text(seg))
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
    if en_text:  # 无英文题注时不留空段（v1.6：表仅中文题注场景）
        p2 = doc.add_paragraph()
        ppr(p2, line=360, rule="auto", jc="center")
        add_para_runs(p2, en_text, ea=en_ea, sz=sz)
    return p


def add_md_table(doc, rows, cap_cn=None, cap_en=None, font=10.5, usable=None):
    if cap_cn:
        caption_paras(doc, cap_cn, cap_en or "")
    header, data = rows[0], rows[1:]
    # v1.6 test-8.0：列宽按"表头+全列数据"的最长内容加权（旧实现只看表头长度：
    # 表头短但叙述内容长的列被压窄 → 一字一行/叙述列不足）。
    def col_len(ci):
        m = len(header[ci]) if ci < len(header) else 1
        for r in data:
            if ci < len(r):
                m = max(m, min(len(r[ci]), 14))  # 数据长内容封顶，防个别长格吃掉全表
        return m
    lens = [max(1, col_len(ci)) for ci in range(len(header))]
    weights = []
    for ci, ln in enumerate(lens):
        if ln <= 4:
            weights.append(0.6)
        elif ln <= 8:
            weights.append(1.0)
        elif ln <= 12:
            weights.append(1.5)
        else:
            weights.append(2.0)
    width_total = usable or (25.7 if usable == 0 else 16.5)
    if usable == 0:
        width_total = 25.7
    elif usable is None:
        width_total = 16.5
    widths = [width_total * w / sum(weights) for w in weights]
    E.add_table(doc, header, data, font_size=font, compact=(font <= 9.0), widths_cm=widths)
    return doc.tables[-1]


def parse_md(doc, md, fig_dir=None, cap_map=None, en_map=None, in_body=True,
             fig_en_map=None):
    """md 章节解析：标题/#；图占位（（图x-y …））；表题+表行（跨空行采集，题注不因空行丢失）；
    正文段落（[n] 上标引用；本章待核实清单→楷体注）。
    en_map=表英文题注（表上方 Tab. 段）；fig_en_map=图英文题注（FigureBlock 中文题下方）。"""
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
                               cap_map[key][1] if isinstance(cap_map[key], tuple) else cap_map[key],
                               fig_caption_en=(fig_en_map or {}).get(key))
            else:
                add_body(doc, s)  # 无图文件时保留占位行（诚实降级）
            i += 1
            continue
        if s.startswith("|"):
            i += 1
            continue
        m = re.match(r"^(表(\d+-\d+|A-\d+|B-\d+))[ \u3000]*", s)
        if m:
            # v1.6 test-8.0 修复：表题行后无条件采集表行渲染（旧实现要求 en_map 含该
            # 表号才渲染，英文题注缺失时表体被静默丢弃=内容丢失；en_map 现只补充英文题注）
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
                add_md_table(doc, rows, cap_cn=s, cap_en=(en_map or {}).get(m.group(2), ""),
                             font=9.0 if len(rows) > 12 else 10.5)
                i = j
                continue
            # 表题后无表行：题注按正文段落保留（不吞行）
        if in_body:
            add_body(doc, s, kai=s.startswith("本章待核实清单"))
        else:
            add_body(doc, s)
        i += 1
