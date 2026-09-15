# -*- coding: utf-8 -*-
"""tests/v1_6/_fixtures.py — v1.6 编排层测试夹具

提供：tempfile 项目（.aeromech + materials + 可选 docx 模板/样文/PDF 规范）。
不依赖任何具体题目/学校/测试项目。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import thesis_state as TS  # noqa: E402


def make_project(path, stage="S1", with_template=True, with_samples=False,
                 with_pdf_spec=False, title="", paper_type=None):
    """初始化一个最小合法项目；返回 root。"""
    os.makedirs(path, exist_ok=True)
    root = os.path.abspath(path)
    TS.main([root, "init"])
    if stage != "S1":
        st, _ = TS.load_state(root)
        st["stage"]["current"] = stage
        TS.save_state(root, st)
    school = os.path.join(root, "materials", "school")
    os.makedirs(school, exist_ok=True)
    if with_template:
        _write_docx(os.path.join(school, "本科毕业论文模板.docx"),
                    margins=(2.5, 2.5, 3.0, 2.5), body_pt=12, h1=16, h2=14)
    if with_pdf_spec:
        with open(os.path.join(school, "格式要求.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 smoke\n%%EOF")
    if with_samples:
        sd = os.path.join(root, "materials", "samples")
        os.makedirs(sd, exist_ok=True)
        _write_docx(os.path.join(sd, "往届论文.docx"),
                    margins=(2.0, 2.0, 2.0, 2.0), body_pt=10.5, h1=15, h2=13)
    if title or paper_type:
        st, _ = TS.load_state(root)
        st["project"]["title"] = title
        st["project"]["paper_type"] = paper_type
        TS.save_state(root, st)
    return root


def _write_docx(path, margins, body_pt, h1, h2):
    from docx import Document
    from docx.shared import Pt, Cm
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.top_margin, s.bottom_margin, s.left_margin, s.right_margin = [Cm(x) for x in margins]
    n = d.styles["Normal"]
    n.font.name = "Times New Roman"
    n.font.size = Pt(body_pt)
    d.styles["Heading 1"].font.size = Pt(h1)
    d.styles["Heading 2"].font.size = Pt(h2)
    d.add_paragraph("正文样例行")
    d.save(path)


def write_text(root, rel, content="x\n"):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p
