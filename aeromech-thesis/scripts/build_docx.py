# -*- coding: utf-8 -*-
"""
毕业论文 DOCX 组装器 — FORMAT_RECONSTRUCTION 参考实现骨架（aeromech-thesis）
用法: python build_docx.py <project_root>    （THESIS_OUT 环境变量可覆盖输出名）

定位说明（v1.1.0 起）：
  - 本文件是"旧路径"参考骨架，仅供 FORMAT_RECONSTRUCTION 场景与旧项目兼容参考。
  - 新项目请在项目目录内编写 build_docx_<project>.py（引用 docx_engine/template_fidelity 通用层），
    不要把项目内容硬编码进本文件。
  - 全部项目内容（封面字段/图表计划/表格题注/附录）从项目内可选配置
    `<project_root>/.aeromech/build-config.json` 读取；缺省时使用中性占位内容。
    配置示例（全部字段可选）：
      {
        "cover_title_lines": ["【论文题目】"],
        "cover_meta": ["专业：【专业】", "作者：【姓名】"],
        "figure_plan": [["图1", "ch1.md", "见图1", "fig1.png", "图1 【图题】", "default"]],
        "table_captions": {"1": "表1 【表题】"},
        "chapter_files": ["ch1.md", "ch2.md"],
        "appendix_a_title": "附录A 【附录表】",
        "appendix_a_md": "analysis/appendix-table.md",
        "appendix_a_header": ["列1", "列2"],
        "ack_text": "【致谢】"
      }

v4+ 已验证版式规则（保留）：
1. FigureBlock：图片+图题无边框 1 列表格 + cantSplit → 不可跨页
2. IMAGE_AUTO_SCALE：按宽高比/类型自适应（PAGE_FLOW_OPTIMIZER 高度分级）
3. TABLE_HEADER_REPEAT：tblHeader XML
4. TABLE_ROW_KEEP_TOGETHER：行 cantSplit
5. TABLE_PAGE_BALANCE：附录大表紧凑化避免孤立尾行
6. HEADING_KEEP_WITH_NEXT：标题 keepNext
7. AbstractBlock：摘要标题分页控制（Abstract page_break_before，避免短语级跨页断裂）
"""
import json
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

if len(sys.argv) < 2:
    print("用法: python build_docx.py <project_root>  （项目根目录，须含 .aeromech/artifacts）")
    print("提示: 正式交付请优先使用 template_fidelity 通用原语与项目层 build_docx_<project>.py；")
    print("      本脚本为 FORMAT_RECONSTRUCTION 参考骨架，项目内容经 .aeromech/build-config.json 注入。")
    sys.exit(2)
ROOT = sys.argv[1]
A = os.path.join(ROOT, ".aeromech", "artifacts")
CH = os.path.join(A, "chapters")
FIG = os.path.join(A, "figures", "final")
OUT = os.environ.get("THESIS_OUT", os.path.join(ROOT, "毕业论文.docx"))


def load_build_config(root):
    """项目内容配置（可选）。缺失时返回中性占位默认值——不得内置任何具体项目内容。"""
    defaults = {
        "cover_title_lines": ["【论文题目】（请在 build-config.json 中提供）"],
        "cover_meta": [],
        "figure_plan": [],
        "table_captions": {},
        "chapter_files": [],
        "appendix_a_title": "附录A 【附录数据表】",
        "appendix_a_md": "",
        "appendix_a_header": [],
        "ack_text": "【致谢内容待作者提供】",
        "references_note": "",
        "literature_md": "literature.md",
    }
    cfg_path = os.path.join(root, ".aeromech", "build-config.json")
    if os.path.isfile(cfg_path):
        try:
            user_cfg = json.load(open(cfg_path, encoding="utf-8"))
            defaults.update({k: v for k, v in user_cfg.items() if v not in (None, "", [])})
        except Exception as e:
            print(f"[build-config] 读取失败（使用缺省占位）：{e}")
    return defaults


CFG = load_build_config(ROOT)

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

TABLE_CAPTIONS = {int(k): v for k, v in (CFG.get("table_captions") or {}).items()}

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

FIGURE_PLAN = [tuple(x) for x in (CFG.get("figure_plan") or [])]

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

# ================= 1. 封面（内容来自 build-config.json；缺省占位） =================
for _ in range(3):
    para()
for tl in (CFG.get("cover_title_lines") or ["【论文题目】"]):
    para(tl, size=22, cn=F_HEAD, align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(2):
    para()
for label in (CFG.get("cover_meta") or ["专业：【专业】", "作者：【姓名】", "指导教师：【姓名】"]):
    para(label, size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)

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
chapter_files = CFG.get("chapter_files") or (
    sorted(f for f in os.listdir(CH) if re.match(r"^ch\d+\.md$", f)) if os.path.isdir(CH) else [])
for chf in chapter_files:
    table_counter = render_body(chapter_lines(os.path.join(CH, chf)),
                                table_counter, inserted, chf)

# ================= 5. 参考文献（条目来自 literature.md 登记表；与正文 [L#] 登记号对应） =================
heading("参考文献", 1)
if CFG.get("references_note"):
    para(CFG["references_note"], size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)
lit_path = os.path.join(A, CFG.get("literature_md", "literature.md"))
if os.path.isfile(lit_path):
    lit_text = open(lit_path, encoding="utf-8").read()
    for ln in lit_text.split("\n"):
        if ln.strip().startswith("| L"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 7:
                para(f"{c[0]} {c[2]} — {c[3]}，{c[4]}，{c[5]}。（{c[6]}）", size=10.5, space_after=2)

# ================= 6. 致谢 =================
heading("致谢", 1)
para(CFG.get("ack_text", "【致谢内容待作者提供】"),
     size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.74)

# ================= 7. 附录（内容来自 build-config.json；缺省时跳过） =================
app_md = CFG.get("appendix_a_md") or ""
app_path = os.path.join(A, app_md) if app_md else ""
if app_path and os.path.isfile(app_path):
    land = doc.add_section()
    land.footer.is_linked_to_previous = True   # 继承第一节点页码
    setup_section(land, landscape=True)
    heading(CFG.get("appendix_a_title", "附录A 【附录数据表】"), 1)
    app_rows = []
    app_header = CFG.get("appendix_a_header") or []
    for ln in open(app_path, encoding="utf-8").read().split("\n"):
        if ln.strip().startswith("|"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if any(c) and not all(set(x) <= set("-: ") for x in c):
                app_rows.append(c)
    if app_rows and not app_header:
        app_header, app_rows = app_rows[0], app_rows[1:]
    if app_rows:
        add_table(app_header, app_rows, font_size=8.0, repeat_header=True,
                  row_keep=True, compact=True, landscape=True)
        print(f"[build] 附录A 数据表行数 = {len(app_rows)}（TABLE_PAGE_BALANCE）")

doc.save(OUT)
print("DOCX saved:", OUT)
print("正文表格数:", table_counter, "| 正文嵌入图:", len(inserted),
      "| 已插入:", sorted(k[0] for k in inserted), "| 缺图:", [k[0] for k in FIGURE_PLAN if k not in inserted])
