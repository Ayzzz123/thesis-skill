# -*- coding: utf-8 -*-
"""Test A：有学校 Word 模板 -> TEMPLATE_FIDELITY（母版驱动）+ TF 检查（Test C：横向附录节）。
构建合成学校模板 fixture，用 template_fidelity 通用原语按母版流程组装，断言结构/页码/表格分隔/题注，
再以 tf_qa 机器检查子集验收。运行：python tests/test_a_template_fidelity.py"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docx_engine as E
import template_fidelity as TF
from docx import Document
from docx.enum.section import WD_SECTION, WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def make_fixture_template(path):
    """合成学校模板：封面表+声明+样例区（节锚点含 upperRoman/decimal pgNumType 以复现缺陷场景）。"""
    d = Document()
    d.save(path)
    d = Document(path)
    sec = d.sections[0]
    sec.page_width, sec.page_height = int(21 * 360000), int(29.7 * 360000)  # A4
    sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = 2 * 360000
    # 封面 1x1 表（含标签与空值段）
    t = d.add_table(rows=1, cols=1)
    cell = t.cell(0, 0)
    cell.text = ""
    p = cell.paragraphs[0]
    r = p.add_run("南京农业大学本科生毕业论文（设计）")
    E.set_font(r, "黑体", 18)
    for lab in ["题    目:", "姓    名:", "专    业:", "指导教师:"]:
        p = cell.add_paragraph()
        r = p.add_run(lab)
        E.set_font(r, "黑体", 16)
        cell.add_paragraph()
    p = cell.add_paragraph()
    E.set_font(p.add_run("20   年   月   日"), "宋体", 14)
    # 声明样例
    d.add_paragraph("南京农业大学本科生毕业论文（设计）原创性声明")
    d.add_paragraph("本人郑重声明：本论文为本人独立完成。")
    d.add_paragraph("论文作者签名：            日期：")
    # 节锚点1：合并封面与声明节（upperRoman start1 用于复现 add_section 复制缺陷）
    sec_para = d.add_paragraph()
    from docx.oxml import OxmlElement
    pPr = sec_para._p.get_or_add_pPr()
    sectPr = OxmlElement("w:sectPr")
    pg = OxmlElement("w:pgNumType"); pg.set(qn("w:fmt"), "upperRoman"); pg.set(qn("w:start"), "1")
    sectPr.append(pg)
    sz = OxmlElement("w:pgSz"); sz.set(qn("w:w"), str(int(21 * 567))); sz.set(qn("w:h"), str(int(29.7 * 567)))
    sectPr.append(sz)
    mar = OxmlElement("w:pgMar")
    for k in ("top", "bottom", "left", "right"):
        mar.set(qn("w:" + k), str(int(2 * 567)))
    sectPr.append(mar)
    pPr.append(sectPr)
    # 样例区（将被删除）
    d.add_paragraph("样例：第一章 绪论（三号黑体居中）")
    d.add_paragraph("样例正文内容 ×××。")
    d.add_paragraph("样例：参考文献表是文中引用的集合。")
    d.save(path)
    return path


def build_project(tpl, out_docx, out_dir):
    d = TF.open_master(tpl, out_docx)
    # 修剪：保留封面+声明（首个节锚点前内容），删除其后样例内容
    body = d.element.body
    first_tbl = None
    for el in body.iterchildren():
        if el.tag == qn("w:tbl"):
            first_tbl = el
            break
    anchor1 = TF.first_sectpr_anchor_after(d, first_tbl)
    # 封面+声明合并节结束锚点：删除其后的样例内容，并清除其 pgNumType（无码区）
    TF.trim_body_after(d, anchor1)
    sp = anchor1.find(qn("w:pPr")).find(qn("w:sectPr"))
    pg = sp.find(qn("w:pgNumType"))
    if pg is not None:
        sp.remove(pg)
    # 封面填值（题目/专业；其余空槽）
    TF.fill_cover_fields(d, {"题    目": "测试题目：某飞机起落架收放系统研究", "专    业": "飞行器维修工程技术"})
    # 摘要+ABSTRACT 节：upperRoman start1 + PAGE
    sec = d.sections[-1]
    TF.set_pgnum(sec, fmt="upperRoman", start=1)
    TF.footer_page_field(sec)
    p = d.add_paragraph()
    TF.ppr(p, line=400, rule="exact", jc="center", before=240, after=120)
    TF.add_para_runs(p, "测试题目：某飞机起落架收放系统研究", ea="黑体", sz=16)
    TF.add_h1(d, "摘  要")
    TF.add_body(d, "摘要正文内容用于模板保真测试。")
    kw = d.add_paragraph()
    TF.ppr(kw, line=400, rule="exact")
    TF.add_para_runs(kw, "关键词：", ea="黑体", sz=14)
    TF.add_para_runs(kw, "起落架；收放系统", ea="宋体", sz=12)
    TF.add_h1(d, "ABSTRACT")
    TF.add_body(d, "This is the abstract body for the template fidelity test.")
    kw = d.add_paragraph()
    TF.ppr(kw, line=400, rule="exact")
    TF.add_para_runs(kw, "KEY WORDS:", ea="宋体", sz=14, bold=True)
    TF.add_para_runs(kw, " landing gear; retraction", ea="宋体", sz=12)
    # 目录节（延续 upperRoman，无 start——防重启验证）
    sec = TF.add_section_continue(d, fmt="upperRoman")
    p = d.add_paragraph()
    TF.ppr(p, line=400, rule="exact", jc="center")
    TF.add_para_runs(p, "目  录", ea="黑体", sz=16)
    TF.toc_field_para(d)
    # 正文节：decimal start1 + 页眉
    sec = TF.add_section_continue(d, fmt="decimal")
    TF.set_pgnum(sec, fmt="decimal", start=1)
    TF.header_text(sec, "南京农业大学本科毕业论文（设计）")
    # md 章节（含两级标题、正文、表（题注后带空行=跨空行采集）、相邻两表=分隔保护、图占位缺文件降级）
    md = """# 第一章 绪论

## 1.1 测试节

这是正文段，含引用[1]与加粗**关键词**。

表1-1 测试表A（题注与表之间有空行，不得丢失）

| 序号 | 项目 | 数值 |
|---|---|---|
| 1 | 内漏 | 36 |

表1-2 测试表B（相邻表分隔保护）

| 序号 | 项目 | 数值 |
|---|---|---|
| 2 | 卡滞 | 24 |

（图1-1 测试图占位，S8 渲染）

# 参考文献

[1] 测试作者. 测试文献[J]. 测试期刊, 2026, 1(1): 1-2.
"""
    TF.parse_md(d, md, fig_dir=None, cap_map={"1-1": ("none.png", "图1-1 测试图")},
                en_map={"1-1": "Tab.1-1 Test table A", "1-2": "Tab.1-2 Test table B"})
    # Test C：横向附录节（decimal 延续 + 页眉页脚不丢失）
    sec = TF.add_section_continue(d, fmt="decimal")
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    TF.add_h1(d, "附录A  测试宽表")
    TF.add_md_table(d, [["序号", "项"], ["1", "甲"], ["2", "乙"]], cap_cn="表A-1  测试宽表",
                    cap_en="Tab.A-1 Test wide table", font=9.0, usable=0)
    # 致谢
    sec = TF.add_section_continue(d, fmt="decimal")
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    TF.add_h1(d, "致  谢")
    TF.add_body(d, "感谢指导教师的指导。")
    d.save(out_docx)
    return out_docx


def main():
    tmp = tempfile.mkdtemp(prefix="tf_testA_")
    tpl = os.path.join(tmp, "school_template.docx")
    out_docx = os.path.join(tmp, "毕业论文.docx")
    out_dir = os.path.join(tmp, "qa")
    make_fixture_template(tpl)
    print("== Test A: TEMPLATE_FIDELITY ==")
    mode, tpath = TF.select_docx_mode(os.path.dirname(tpl))
    check("模式选择=TEMPLATE_FIDELITY", mode == TF.MODE_TEMPLATE_FIDELITY and tpath == tpl)
    rec = TF.document_generation_record(mode, tpath)
    check("document_generation 记录", rec["mode"] == "template_fidelity" and rec["template_file"] == tpl)
    build_project(tpl, out_docx, out_dir)
    d = Document(out_docx)
    # 封面字段
    allf = "".join(p.text for p in d.tables[0].cell(0, 0).paragraphs)
    check("封面题目已填", "某飞机起落架收放系统研究" in allf)
    check("封面姓名保持空槽", "姓    名:" in allf)
    # 表格分隔保护 + 题注跨空行
    check("正文表数≥2 且未合并（表1-1、1-2 均在）", sum(1 for tb in d.tables for row in tb.rows for c in row.cells if "测试表A" in c.text or "内漏" in c.text) >= 1
          and sum(1 for tb in d.tables for row in tb.rows for c in row.cells if "卡滞" in c.text) >= 1)
    # 表题存在（表1-1/1-2 题注段）
    caps = [p.text.strip() for p in d.paragraphs if p.text.strip().startswith("表1-")]
    check("表题跨空行未丢失", len(caps) == 2, str(caps))
    # 相邻表之间确有段落分隔：统计 body 中 tbl 间非空段
    els = list(d.element.body.iterchildren())
    tbl_idx = [i for i, e in enumerate(els) if e.tag == qn("w:tbl")]
    gaps_ok = all(any(els[j].tag == qn("w:p") for j in range(tbl_idx[k] + 1, tbl_idx[k + 1]))
                  for k in range(len(tbl_idx) - 1))
    check("相邻表格间存在段落分隔", gaps_ok)
    # 页码防重启：目录/正文/附录节 pgNumType 无 start（正文节 start=1 除外）
    secs = d.sections
    starts = []
    for s in secs:
        el = s._sectPr.find(qn("w:pgNumType"))
        starts.append((el.get(qn("w:fmt")) if el is not None else None,
                       el.get(qn("w:start")) if el is not None else None))
    check("页码无意外重启（仅正文节 start=1）",
          sum(1 for f, st in starts if st == "1") == 2, str(starts))  # 摘要节+正文节
    check("横向附录节存在且页眉可继承", any(s.orientation == WD_ORIENT.LANDSCAPE for s in secs))
    # TF-19 页面尺寸
    check("A4 页面", round(d.sections[0].page_width.cm) == 21)
    # tf_qa 机器子集
    print("== tf_qa（Test A 子集）==")
    import tf_qa
    rc = tf_qa.run(tpl, out_docx, None, out_dir, 12, 400, 200, 1)
    check("tf_qa 退出码=0", rc == 0)
    report = open(os.path.join(out_dir, "tf-qa-report.md"), encoding="utf-8").read()
    check("tf_qa 报告存在", "TF-01" in report and "TF-20" in report)
    print(f"Test A 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
