# -*- coding: utf-8 -*-
"""
毕业论文 DOCX 组装器（aeromech-thesis v1.0.0 delivery stabilization）
用法: python build_docx.py [project_root]    （THESIS_OUT 环境变量可覆盖输出名）

v4+ 已验证版式规则：
1. FigureBlock：图片+图题无边框 1 列表格 + cantSplit → 不可跨页
2. IMAGE_AUTO_SCALE：按宽高比/类型自适应（PAGE_FLOW_OPTIMIZER 高度分级）
3. TABLE_HEADER_REPEAT：tblHeader XML
4. TABLE_ROW_KEEP_TOGETHER：行 cantSplit
5. TABLE_PAGE_BALANCE：附录大表紧凑化避免孤立尾行
6. HEADING_KEEP_WITH_NEXT：标题 keepNext
7. AbstractBlock：摘要标题分页控制（Abstract page_break_before，避免短语级跨页断裂）
"""
import os
import sys
import re
from PIL import Image

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/29603/Desktop/thesis-skill/thesis-test-1.0"
A = os.path.join(ROOT, ".aeromech", "artifacts")
CH = os.path.join(A, "chapters")
FIG = os.path.join(A, "figures", "final")
OUT = os.environ.get("THESIS_OUT", os.path.join(ROOT, "毕业论文.docx"))

F_BODY, F_HEAD = "宋体", "黑体"
doc = Document()

# 页面可用宽度（A4 纵向 21cm − 左边距3 − 右边距2.5 = 15.5cm；横向见 setup_section）
PAGE_WIDTH_LANDSCAPE_CM = 25.7   # 29.7 − 2×2.0
BODY_WIDTH_PORTRAIT_CM = 15.5    # 21.0 − 3.0 − 2.5

# 图片类型 → 期望宽度（cm，占正文宽度比例换算后取 min）
IMAGE_WIDTH_RULES = {
    "mermaid_flowchart": 0.80,   # 纵向流程图：按高度约束再收紧
    "mermaid_system": 0.85,
    "matplotlib_stat": 0.90,
    "fta_tree": 0.88,
    "default": 0.85,
}
MAX_FIGURE_HEIGHT_CM = 16.0      # 图+题注整块高度预算上限（页面可用高 24.7cm 内）

def set_font(run, cn=F_BODY, size=12, bold=False, color=None):
    run.font.name = "Times New Roman"
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Times New Roman")
    rfonts.set(qn("w:hAnsi"), "Times New Roman")
    rfonts.set(qn("w:eastAsia"), cn)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color

def para(text="", size=12, cn=F_BODY, bold=False, align=None, indent=None,
         space_after=0, line=1.5, keep_with_next=False):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing = line
    pf.space_after = Pt(space_after)
    if indent is not None:
        pf.first_line_indent = Cm(indent)
    if keep_with_next:
        pf.keep_with_next = True
    if text:
        parts = re.split(r"\*\*(.+?)\*\*", text)
        for i, seg in enumerate(parts):
            if not seg:
                continue
            run = p.add_run(seg)
            set_font(run, cn, size, bold or (i % 2 == 1))
    return p

HEAD_SIZES = {1: 16, 2: 14, 3: 12}

def heading(text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(18 if level == 1 else 12)
    pf.space_after = Pt(12 if level == 1 else 6)
    if level == 1:
        pf.page_break_before = True
    pf.keep_with_next = True          # HEADING_KEEP_WITH_NEXT
    pf.keep_together = True
    run = p.add_run(text)
    set_font(run, F_HEAD, HEAD_SIZES[level], bold=False, color=RGBColor(0, 0, 0))
    return p

def setup_section(sec, landscape=False):
    if landscape:
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
        sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)
        sec.left_margin = Cm(2.0); sec.right_margin = Cm(2.0)
    else:
        sec.top_margin = Cm(2.5); sec.bottom_margin = Cm(2.5)
        sec.left_margin = Cm(3.0); sec.right_margin = Cm(2.5)
    # 注意：不在此处调用 add_page_number。
    # 新 section 的 footer 默认 linked to previous，若每节都加 PAGE 字段，
    # 会在共享 footer part 中累积多个字段 → 每页输出 888/101010 重复页码。

def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    set_font(run, F_BODY, 9)

setup_section(doc.sections[0])
add_page_number(doc.sections[0])   # 页码字段只添加一次，后续 section 继承

# ---------------- XML helpers ----------------
def row_cant_split(row):
    """行不可跨页拆分"""
    trPr = row._tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    trPr.append(cant)

def row_repeat_header(row):
    """跨页时重复此行作为表头"""
    trPr = row._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)

def no_border_table(t):
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        borders.append(el)
    tblPr.append(borders)

def set_cell_margins_table(t, cm=0.08):
    tblPr = t._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(int(cm * 567)))  # 1cm ≈ 567 twips
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)

def row_height_atleast(row, cm):
    trPr = row._tr.get_or_add_trPr()
    trH = OxmlElement("w:trHeight")
    trH.set(qn("w:val"), str(int(cm * 567)))
    trH.set(qn("w:hRule"), "atLeast")
    trPr.append(trH)

# ---------------- 表格工具（v4）----------------
def parse_md_table(lines, i):
    header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
    j = i + 1
    while j < len(lines) and re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[j]):
        j += 1
    rows = []
    while j < len(lines) and lines[j].strip().startswith("|"):
        rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
        j += 1
    return header, rows, j

def clean_cell(t):
    return t.replace("**", "").replace("`", "").strip()

def cell_borders(cell, edges):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge, sz in edges.items():
        el = OxmlElement(f"w:{edge}")
        if sz:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(sz))
            el.set(qn("w:color"), "000000")
        else:
            el.set(qn("w:val"), "nil")
        borders.append(el)
    tcPr.append(borders)

def add_table(header, rows, font_size=10.5, header_cn=F_HEAD,
              repeat_header=True, row_keep=True, compact=False,
              landscape=False, col_weights=None):
    """通用表格：表头重复(tblHeader) + 行不拆分(cantSplit) + 可选紧凑模式"""
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    no_border_table(t)
    set_cell_margins_table(t, 0.04 if compact else 0.1)

    # 可用宽度
    usable = PAGE_WIDTH_LANDSCAPE_CM if landscape else BODY_WIDTH_PORTRAIT_CM
    if col_weights is None:
        col_weights = [1.0] * len(header)
    total_w = sum(col_weights)
    widths = [usable * w / total_w for w in col_weights]

    # 表头
    hc = t.cell(0, 0)
    p = hc.paragraphs[0]
    run = p.add_run(clean_cell(header[0]))
    set_font(run, header_cn, font_size)
    # 简化：先统一设置后再单独逐 cell
    for ci, h in enumerate(header):
        c = t.cell(0, ci); c.text = ""
        p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(clean_cell(h))
        set_font(run, header_cn, font_size)
        cell_borders(c, {"top": 12, "bottom": 6, "left": None, "right": None})
        c.width = Cm(widths[ci])
    if repeat_header:
        row_repeat_header(t.rows[0])
    if row_keep:
        row_cant_split(t.rows[0])

    # 数据行
    for ri, row in enumerate(rows):
        if row_keep:
            row_cant_split(t.rows[ri + 1])
        for ci in range(len(header)):
            c = t.cell(ri + 1, ci); c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0 if compact else 1.15
            if compact:
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
            run = p.add_run(clean_cell(row[ci] if ci < len(row) else ""))
            set_font(run, F_BODY, font_size)
            cell_borders(c, {"left": None, "right": None, "top": None, "bottom": None})
            if ri == len(rows) - 1:
                cell_borders(c, {"bottom": 12})
            c.width = Cm(widths[ci])
    return t

def caption(text, keep_with_next=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.3
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(10)
    if keep_with_next:
        p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_font(run, F_BODY, 10.5)
    return p

TABLE_CAPTIONS = {
    1: "表1 收放系统候选故障模式清单（30 条，含来源状态）",
    2: "表2 S/O/D 评分锚点表（十档文字定义）【方法设定】",
    3: "表3 FMEA 分析表（浓缩版 30 条；完整分析链见附录A）",
    4: "表4 演示排序 Top12（S/O/D/RPN）【假设/模拟·仅演示方法】",
    5: "表5 常规维修检查策略概览（通用框架；机型任务【待核实】）",
    6: "表6 关键故障模式→维修策略建议（框架性；未经验证）",
}

# ---------------- 图片块（FigureBlock：无边框表格容器）----------------
def calc_image_width_cm(png, img_type="default", landscape=False):
    usable = PAGE_WIDTH_LANDSCAPE_CM if landscape else BODY_WIDTH_PORTRAIT_CM
    ratio = IMAGE_WIDTH_RULES.get(img_type, IMAGE_WIDTH_RULES["default"])
    w_target = usable * ratio
    try:
        with Image.open(png) as im:
            pw, ph = im.size
            aspect = pw / ph
    except Exception:
        aspect = 1.0
    # PAGE_FLOW_OPTIMIZER：高度分级约束，避免大图独占页面挤压正文流
    # 常规图（框图/统计图/故障树）上限 11.0cm → 一页可容纳图+正文，正文自然连续
    # 超高窄图（roadmap，aspect<0.4）上限 15.0cm（窄图适宜纵贯，缩小会牺牲文字）
    if aspect < 0.4:
        fig_h_limit = 12.5 if not landscape else 12.0
    else:
        fig_h_limit = 9.5 if not landscape else 10.0
    w_by_h = fig_h_limit * aspect
    w = min(w_target, w_by_h)
    # 保护下限仅对"不超高"的图有效；aspect < 0.4 的高图一律以高度约束为准
    if aspect >= 0.4:
        if aspect >= 1.0:
            w = max(w, 7.5)
        else:
            w = max(w, 6.0)
    return min(w, usable)

def figure_block(png, fig_caption, img_type="default", anchor_el=None, landscape=False):
    """
    FigureBlock：把 图片+图题 放进 1 行 1 列无边框表格，行 cantSplit。
    Word 分页时整行作为一个整体，无法拆分 → 图片与题注必在同页。
    返回表格 XML 元素（供 addnext 插入）。
    """
    png_path = os.path.join(FIG, png)
    w_cm = calc_image_width_cm(png_path, img_type, landscape)

    tb = doc.add_table(rows=1, cols=1)
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    no_border_table(tb)
    set_cell_margins_table(tb, 0.05)
    row_cant_split(tb.rows[0])
    tb.rows[0].height = Cm(0.1)  # placeholder
    row_height_atleast(tb.rows[0], 0.1)
    cell = tb.cell(0, 0)
    cell.width = Cm(w_cm)

    # 图片段（居中）
    p_img = cell.paragraphs[0]
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.keep_together = True
    run = p_img.add_run()
    run.add_picture(png_path, width=Cm(w_cm))

    # 图题段（同一单元格内，随行 cantSplit 整体移动）
    p_cap = cell.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.line_spacing = 1.3
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(6)
    cr = p_cap.add_run(fig_caption)
    set_font(cr, F_BODY, 10.5)

    tbl_el = tb._tbl
    if anchor_el is not None:
        anchor_el.addnext(tbl_el)
    return tbl_el

FIGURE_PLAN = [
    ("图1", "ch1.md", "见图1", "fig1_route.png", "图1 论文技术路线图", "mermaid_flowchart"),
    ("图2", "ch2.md", "如图2所示", "fig2_system.png", "图2 起落架收放系统组成与接口框图（典型构型）", "mermaid_system"),
    ("图3", "ch3.md", "见图3", "fig3_funcdecomp.png", "图3 起落架收放系统功能分解图", "mermaid_system"),
    ("图4", "ch4.md", "见图4", "fig4_pareto.png", "图4 FMEA 演示数据 RPN 帕累托图【假设/模拟·仅演示方法】", "matplotlib_stat"),
    ("图5", "ch4.md", "与图5", "fig5_somatrix.png", "图5 FMEA 演示数据 S-O 风险矩阵【假设/模拟·仅演示方法】", "matplotlib_stat"),
    ("图6", "ch5.md", "（图6", "fig6_fta.png", "图6 着陆构型建立失效故障树（演示级·定性）", "fta_tree"),
]

# ---------------- 章节正文提取 ----------------
def chapter_lines(filepath):
    text = open(filepath, encoding="utf-8").read()
    lines = text.split("\n")
    end = len(lines)
    for i, ln in enumerate(lines):
        if ln.startswith("## 本章"):
            end = i
            break
    for j in range(end - 1, -1, -1):
        if lines[j].strip() == "---":
            end = j
            break
    return [ln for ln in lines[:end] if not ln.strip().startswith(">")]

def grab_section(lines, h2):
    out, on = [], False
    for ln in lines:
        if ln.startswith("## " + h2):
            on = True
            continue
        if on and ln.startswith("## "):
            break
        if on:
            out.append(ln)
    return out

# ================= 1. 封面 =================
for _ in range(3):
    para()
para("毕业论文（测试稿）", size=22, cn=F_HEAD, align=WD_ALIGN_PARAGRAPH.CENTER)
para("基于FMEA的民用飞机起落架收放系统", size=22, cn=F_HEAD, align=WD_ALIGN_PARAGRAPH.CENTER)
para("故障模式与维修策略研究", size=22, cn=F_HEAD, align=WD_ALIGN_PARAGRAPH.CENTER)
para()
p = para("【测试稿 · 演示交付 · 非提交终稿】", size=14, cn=F_HEAD,
         align=WD_ALIGN_PARAGRAPH.CENTER)
p.runs[0].font.color.rgb = RGBColor(0xC0, 0, 0)
for _ in range(2):
    para()
for label in ["专业：飞行器维修工程技术（本科）", "学历层次：本科",
              "作者：（测试稿 · 待补）", "指导教师：（测试稿 · 待补）",
              "完成日期：2026-09-08",
              "格式：通用工科论文默认格式（No-School-Template Mode，学校模板待提供）"]:
    para(label, size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)
for _ in range(2):
    para()
para("说明：本文件为 aeromech-thesis 全流程能力测试的交付测试稿。文中评分与排序等量化内容均为"
     "【假设/模拟·仅演示方法】演示数据，不代表任何真实机队或维修单位数据；【待核实】条目在取得"
     "全文/受控资料前不得作为事实引用；本稿不构成可直接提交的毕业论文终稿。",
     size=10.5)

# ================= 2. 摘要 / Abstract =================
# AbstractBlock 局部版式：中文摘要页与英文 Abstract 页独立；英文段启用 keep/widow 控制，
# 避免并列短语（up-lock / down-lock）被页面边界拆开；字号与行距不变
zh, en = grab_section(chapter_lines(os.path.join(CH, "ch0-front.md")), "摘要"), \
         grab_section(chapter_lines(os.path.join(CH, "ch0-front.md")), "Abstract")

def emit_front(lines, kw_label, keep_lines=False):
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("**关键词") or s.startswith("**Keywords"):
            rest = re.sub(r"^\*\*(关键词|Keywords)\*\*[:：]?\s*", "", s)
            p = para(kw_label + rest, size=12, indent=0.74)
            if keep_lines:
                p.paragraph_format.keep_together = True
            continue
        p = para(s, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
        if keep_lines:
            p.paragraph_format.keep_together = True
            p.paragraph_format.widow_control = True

def h1_no_break(text, page_break=False):
    p = doc.add_paragraph(style="Heading 1")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(12)
    pf.space_after = Pt(10)
    pf.keep_with_next = True
    if page_break:
        pf.page_break_before = True
    run = p.add_run(text)
    set_font(run, F_HEAD, 16, bold=False, color=RGBColor(0, 0, 0))
    return p

h1_no_break("摘  要")
emit_front(zh, "关键词：")
h1_no_break("Abstract", page_break=True)
emit_front(en, "Keywords: ", keep_lines=True)

# ================= 3. 目录（真实 Word TOC 域）================
heading("目  录", 1)
toc_p = doc.add_paragraph()
run = toc_p.add_run()
f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
it.text = 'TOC \\o "1-3" \\h \\z \\u'
f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "separate")
t = OxmlElement("w:t"); t.text = "（目录将在 Word 中更新域后生成）"
f3 = OxmlElement("w:fldChar"); f3.set(qn("w:fldCharType"), "end")
run._r.append(f1); run._r.append(it); run._r.append(f2); run._r.append(t); run._r.append(f3)

# ================= 4. 正文六章 =================
def col_weights_for(header):
    """智能列宽权重：长文本列更宽，数值/短码列窄"""
    weights = []
    for h in header:
        hl = clean_cell(h)
        if any(kw in hl for kw in ["S", "O", "D", "RPN", "编号", "FM", "分值"]):
            weights.append(0.55)
        elif len(hl) >= 8:
            weights.append(1.6)
        else:
            weights.append(1.0)
    return weights

def render_body(lines, table_counter, inserted, chf):
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s or s.startswith("```"):
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            txt = m.group(2).strip()
            if level == 1 and not re.match(r"^第[一二三四五六七八九十\d]+章", txt):
                heading(txt, 1)
            elif level == 1:
                heading(txt, 1)
            else:
                heading(txt, 2 if level == 2 else 3)
            i += 1
            continue
        if s.startswith("|"):
            header, rows, ni = parse_md_table(lines, i)
            table_counter += 1
            # 表题段 keepWithNext 与表格绑定
            caption(TABLE_CAPTIONS[table_counter], keep_with_next=True)
            add_table(header, rows, repeat_header=True, row_keep=True,
                      col_weights=col_weights_for(header))
            i = ni
            continue
        p = para(s, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
        cursor = p._p
        for figno, chfile, marker, png, cap, img_type in FIGURE_PLAN:
            key = (figno, chfile)
            if chfile == chf and key not in inserted and marker in s:
                # 在正文段落后插入 FigureBlock（无边框表格）
                figure_block(png, cap, img_type, anchor_el=cursor)
                inserted[key] = True
        i += 1
    return table_counter

table_counter = 0
inserted = {}
for chf in ["ch1.md", "ch2.md", "ch3.md", "ch4.md", "ch5.md", "ch6.md"]:
    table_counter = render_body(chapter_lines(os.path.join(CH, chf)),
                                table_counter, inserted, chf)

# ================= 5. 参考文献 =================
heading("参考文献", 1)
para("说明：本文为测试稿，正文引用采用 [L#] 登记号，与下列条目一一对应。当前无全文实读"
     "文献（全文实读=0），正式参考文献表将在全文获取并核实后按 GB/T 7714 生成；下列条目为已检索到"
     "的真实条目（题录级），已核验/待核验状态如实标注，不含任何虚构条目。",
     size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
lit_text = open(os.path.join(A, "literature.md"), encoding="utf-8").read()
for ln in lit_text.split("\n"):
    if ln.strip().startswith("| L"):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        mark = c[6].replace("已核验", "已核验（存在性/元数据级）").replace("检索到·未核验", "检索到·未核验")
        para(f"{c[0]} {c[2]} — {c[3]}，{c[4]}，{c[5]}。（{mark}）", size=10.5, space_after=2)

# ================= 6. 致谢 =================
heading("致谢", 1)
para("（测试稿占位：致谢内容需作者提供真实个人信息后补写，本稿不虚构致谢对象与经历。）",
     size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)

# ================= 7. 附录 =================
# 附录A 横向页 + FMEA 完整表（紧凑模式 + 表头重复 + 行不拆分 + 分页平衡）
land = doc.add_section()
land.footer.is_linked_to_previous = True   # 继承第一节点页码
setup_section(land, landscape=True)
heading("附录A 收放系统 FMEA 分析表（完整版，与 S5 工程分析表同源）", 1)
para("说明：下表为 30 条候选模式的分析表（结构同 S5 工程分析表；评分与演示 RPN 见正文表2/表4）。"
     "来源状态：已有证据 0 条 / 待核实 7 条 / 工程推演 23 条。",
     size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
fmea_text = open(os.path.join(A, "analysis", "fmea-table.md"), encoding="utf-8").read()
fmea_rows = []
for ln in fmea_text.split("\n"):
    if ln.strip().startswith("| FM"):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) >= 10:
            fmea_rows.append([c[0], c[1], c[3], c[4], c[5], c[6], c[7], c[8], c[9]])

# 分页平衡：附录A 30行 必须压进 2 个横向页（每页 ≥15 行）
# 8.5pt 实测 13+16+1 → 第3页孤立 FM30；改用 7.5pt + 紧凑行距
f_size = 7.5

add_table(
    ["编号", "层级·部件", "故障模式", "候选原因", "局部影响", "上层影响",
     "最终影响", "通用检测手段", "来源状态"],
    fmea_rows, font_size=f_size, repeat_header=True, row_keep=True,
    compact=True, landscape=True,
    col_weights=[0.7, 1.1, 1.4, 1.6, 1.1, 1.1, 1.2, 1.2, 0.8],
)
print(f"[v4] 附录A 字号自适应 = {f_size}pt（TABLE_PAGE_BALANCE）")

# 附录B 纵向页
port2 = doc.add_section()
port2.footer.is_linked_to_previous = True  # 继承页码
setup_section(port2)
heading("附录B 评分记录与演示数据分析【假设/模拟·仅演示方法】", 1)
para("1. 评分口径：正文表2 十档锚点为本文采用口径【方法设定】；两轮独立评分与敏感性检验为主观性"
     "控制措施（正文 4.1.2）。", size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
para("2. 演示数据：30 条构造评分存于 demo_fmea_ratings.csv；RPN 由 Python 独立重算并经质量检查"
     "（缺失/重复/越界/RPN 不符均为 0，计算审计 CALC-001 含输入与脚本校验值），与 S5 分析表"
     "一致性核验 12/12。以下图表仅为演示数据流程测试结果，不代表任何真实机队统计。",
     size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
p1 = para("演示数据 S/O/D/RPN 分布见图A-1，敏感性分析见图A-2。", size=10.5,
          align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
figure_block("figA1_distributions.png",
             "图A-1 演示数据 S/O/D/RPN 分布图【假设/模拟·仅演示方法】",
             "matplotlib_stat", anchor_el=p1._p)
p2 = para()
figure_block("figA2_sensitivity.png",
             "图A-2 敏感性分析：Top12 对 O/D ±1 扰动的 RPN 位移【假设/模拟·仅演示方法】",
             "matplotlib_stat", anchor_el=p2._p)

doc.save(OUT)
print("DOCX saved:", OUT)
print("正文表格数:", table_counter, "| 正文嵌入图:", len(inserted),
      "| 已插入:", sorted(k[0] for k in inserted), "| 缺图:", [k[0] for k in FIGURE_PLAN if k not in inserted])
