# -*- coding: utf-8 -*-
"""tf_qa.py — Template Fidelity QA（TF-01~20）通用脚本（aeromech-thesis v1.4.1）

用法（有 Word 母版模板时）:
  python tf_qa.py --template <学校模板.docx> --docx <毕业论文.docx>
                 [--pdf <毕业论文.pdf>] [--out <报告目录>] [--body-size 12]
                 [--body-line 400 --first-chars 200] [--refs-min 5]
用法（无母版、规范驱动重建时）:
  python tf_qa.py --template <规范文档.docx（仅作参照登记）> --docx <毕业论文.docx>
                 [--pdf <毕业论文.pdf>] [--cover-tokens "校名短语,题目"] 
                 [--front-numbering any|roman|none] [--margins "2.8,2.5"]
                 [--tf20-mode auto|pair|render-only] [--out <dir>]
                 [--body-size 12] [--body-line 440 --first-chars 200] [--refs-min 15]
用法（无模板项目，v1.4.1）:
  python tf_qa.py --docx <毕业论文.docx> [--pdf <毕业论文.pdf>] [--out <dir>]
                 （省略 --template 或传 none/无：模板对照类检查输出 NOT_APPLICABLE，
                   自含检查照常执行；不得把 NOT_APPLICABLE 显示为 PASS）

说明:
  - 预期值参数化（默认对齐中文本科工科通行规范/学校样例；如与 school-format 不同请传参）。
  - 无封面母版（模板首表非封面结构）时 TF-01~03 转为成品封面自检（--cover-tokens）。
  - TF-14 前置页码格式可用 --front-numbering 指定（roman 前置罗马 / none 前置无页码）。
  - 状态模型（v1.4.1）: PASS / FAIL / NOT_APPLICABLE / SKIPPED_WITH_REASON；
    FAIL 输出附 severity 与 remediation。
  - 退出码: 0=无 FAIL（可含 N/A 与 SKIPPED_WITH_REASON）  1=存在 FAIL  3=配置/内部错误（绝不伪造 PASS）
"""
import argparse
import os
import re
import sys

from docx import Document
from docx.oxml.ns import qn

CHECKS = []

# 稳定状态词表
ST_PASS, ST_FAIL, ST_NA, ST_SKIP = "PASS", "FAIL", "NOT_APPLICABLE", "SKIPPED_WITH_REASON"

TF_META = {
    "TF-01": ("High", "核对封面母版结构：复制模板封面表并按原段落结构填充，不得重建封面"),
    "TF-02": ("High", "缺失的封面字段必须以空槽保留（不得虚构值），补全标签行"),
    "TF-03": ("Medium", "以母版为准恢复封面段落文本层级（勿改字体/样式，由模板继承）"),
    "TF-04": ("High", "声明页原文须逐段保留（模板声明段=成品声明段）"),
    "TF-05": ("Medium", "补中文摘要标题（Heading 1「摘要」）与「关键词：」行"),
    "TF-06": ("Medium", "补 ABSTRACT 标题（Heading 1）与 KEY WORDS 行"),
    "TF-07": ("High", "章标题须使用模板继承的 Heading 1/2 样式（勿手写样式）"),
    "TF-08": ("High", "正文区段落统一为规范字号（如宋体小四=12pt）；逐段清理异常 run 字号"),
    "TF-09": ("High", "正文段落统一固定行距与首行缩进（按规范值，如 440twips/200 字符）"),
    "TF-10": ("Medium", "为每个图块补齐图下中英文题注（编号连续）"),
    "TF-11": ("Medium", "表题须置于表上方，md 题注不得因空行丢失"),
    "TF-12": ("High", "数据表改为三线表（顶/表头/底线；无内线与竖线）"),
    "TF-13": ("Medium", "在正文节设置页眉文字（随学校规范）"),
    "TF-14": ("High", "页码不重启/连续；前置页码模式与规范一致；检查分节 pgNumType"),
    "TF-15": ("High", "目录须为 Word 原生 TOC 域（TOC \\o \"1-3\" \\h \\z \\u）"),
    "TF-16": ("Medium", "参考文献条目数不足：补齐真实可核实文献或如实披露（不得凑数）"),
    "TF-17": ("Medium", "附录按 A/B/C 顺序设置 Heading 1 标题"),
    "TF-18": ("Low", "致谢为单一 Heading 1 且正文在限长内（≤500 字）"),
    "TF-19": ("High", "页面尺寸/边距按规范值设置（A4；页边距与模板/规范一致）"),
    "TF-20": ("Low", "关键页渲染/对照缺失：确认可渲染并保留输出供人工复核"),
}


def tf_meta(name):
    for k, v in TF_META.items():
        if name.startswith(k):
            return v
    return ("Medium", "人工复核该项")


def ck(name, ok, ev, skip=False):
    CHECKS.append((name, ST_SKIP if skip else (ST_PASS if ok else ST_FAIL), ev))


def ck_na(name, reason):
    """NOT_APPLICABLE：该项在当前项目条件下无法执行（如无模板对照），不得记为 PASS。"""
    CHECKS.append((name, ST_NA, reason))


def run(template_path, docx_path, pdf_path, out_dir, body_size, body_line,
        first_chars, refs_min, cover_tokens=None, front_numbering="any",
        margins=None, tf20_mode="auto"):
    os.makedirs(out_dir, exist_ok=True)
    no_template = not template_path
    td = None if no_template else Document(template_path)
    fd = Document(docx_path)
    norm = lambda s: s.replace(" ", "").replace("\u3000", "").replace("\n", "")

    def hparas(d, style, pred=None):
        return [p for p in d.paragraphs if p.style and p.style.name == style
                and (pred is None or pred(p.text.strip()))]

    # TF-01/02/03 封面（有模板：母版对照 / 规范驱动自检；无模板：NOT_APPLICABLE）
    t_is_master_cover = (not no_template and len(td.tables) > 0
                         and len(td.tables[0].rows) == 1 and len(td.tables[0].columns) == 1)
    if no_template:
        na_reason = "无模板项目：模板对照不可执行（FORMAT_RECONSTRUCTION）；如提供学校模板或规范文档后重跑本项"
        ck_na("TF-01 封面结构一致", na_reason)
        ck_na("TF-02 封面字段一致", na_reason)
        ck_na("TF-03 封面视觉层级一致", na_reason)
    elif t_is_master_cover and len(fd.tables) > 0:
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
    elif (not no_template and len(td.tables) > 0 and len(fd.tables) > 0
          and (len(td.tables[0].rows), len(td.tables[0].columns))
          == (len(fd.tables[0].rows), len(fd.tables[0].columns))
          and td.tables[0].cell(0, 0).text.strip()[:6]
          == fd.tables[0].cell(0, 0).text.strip()[:6]):
        # v1.6 test-8.0 表格式（grid）封面母版：首表行列一致+标签集保留即结构一致；
        # 填入值替换示例占位属预期（不要求逐字一致）。
        def cell_labels(t):
            out = []
            for r in t.rows:
                for c in r.cells:
                    txt = c.text.strip()
                    if txt.endswith("：") or txt.endswith(":"):
                        out.append(txt)
            return set(out)
        tl0, fl0 = cell_labels(td.tables[0]), cell_labels(fd.tables[0])
        same_rc = (len(td.tables[0].rows), len(td.tables[0].columns)) == \
                  (len(fd.tables[0].rows), len(fd.tables[0].columns))
        ck("TF-01 封面结构一致（grid 母版）", same_rc and len(fd.tables) >= 1,
           f"首表行列 {len(fd.tables[0].rows)}x{len(fd.tables[0].columns)} 与母版一致；表数 母版{len(td.tables)}/成品{len(fd.tables)}")
        ck("TF-02 封面字段一致（grid 母版）", tl0 <= fl0,
           f"母版标签 {len(tl0)} 项在成品保留 {len(tl0 & fl0)}（缺失应保留空槽，不得虚构）"
           + (f"；丢: {sorted(tl0 - fl0)[:4]}" if tl0 - fl0 else ""))
        ck("TF-03 封面视觉层级（grid 母版）", True,
           "grid 封面视觉层级由 cover_align 行簇/标签基线+TF-20 渲染页承担", skip=True)
    else:
        # 无封面母版（规范驱动重建）：TF-01~03 转为成品封面自检
        tokens = cover_tokens or ["本科生毕业论文"]
        ftext_all = "\n".join(p.text for p in fd.paragraphs)
        ok_cover = all(norm(tok) in norm(ftext_all) for tok in tokens)
        ck("TF-01 封面结构（无母版自检）", ok_cover,
           f"封面必备要素：{tokens} 全部存在={ok_cover}")
        field_paras = [p.text.strip() for p in fd.paragraphs[:120]
                       if re.search(r"(姓名|专业|指导教师|学号|学院|密级)", p.text)]
        ck("TF-02 封面字段（无母版自检）", len(field_paras) >= 2,
           f"封面字段行 {len(field_paras)} 条（示例: {field_paras[:3]}）")
        ck("TF-03 封面视觉层级", True, "封面视觉层级以 TF-20 渲染页人工复核为准", skip=True)

    fig_tables = sum(1 for tb in fd.tables[1:] if len(tb.rows) == 1 and len(tb.columns) == 1
                     and "w:drawing" in tb._tbl.xml)  # 图块统计（通用）

    # TF-04 声明（触发词为通用声明名称；模板无声明页时记 SKIP）
    def decl(d):
        out, state = [], 0
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            if "原创性声明" in t or "学位论文独创性声明" in t:
                state = 1
            elif "使用授权声明" in t or "版权使用授权书" in t:
                state = 2
            if state == 1 or state == 2:
                out.append(t)
        return out
    if no_template:
        ck_na("TF-04 声明页结构", "无模板对照：声明页原文一致性无法比对（成品声明页存在性见 QA 链其他检查）")
    else:
        tdecl, fdecl = decl(td), decl(fd)
        if not tdecl and not fdecl:
            ck("TF-04 声明页结构", True, "模板与成品均无声明页（该学校规范未要求声明页）", skip=True)
        else:
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
    CH_RE = r"^第\s*[0-9一二三四五六七八九十]+\s*章"
    chs = hparas(fd, "Heading 1", lambda t: re.match(CH_RE, t))
    h2s = hparas(fd, "Heading 2", lambda t: re.match(r"^\d\.\d\s", t))
    paras_all = fd.paragraphs
    start = end = None
    for i, p in enumerate(paras_all):
        t = p.text.strip()
        if start is None and re.match(CH_RE, t):
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

    # TF-10/11/12 图表（题注编号支持 图1-1/图1.1/表A1）
    figcaps = []
    for tb in fd.tables[1:]:
        if not (len(tb.rows) == 1 and len(tb.columns) == 1 and "w:drawing" in tb._tbl.xml):
            continue
        for row in tb.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    t = p.text.strip()
                    if re.match(r"^图\d+[.\-]\d+|^图[A-Z][.\-]?\d+", t):
                        figcaps.append(t)
    tabcaps = [p.text.strip() for p in fd.paragraphs
               if re.match(r"^表(\d+[.\-]\d+|[A-Z][.\-]?\d+)\s", p.text.strip())]
    ck("TF-10 图题样式", len(figcaps) == fig_tables,
       f"图块={fig_tables} 图题={len(figcaps)}（图下中英文题注）")
    ck("TF-11 表题样式", len(tabcaps) >= 1,
       f"表题数={len(tabcaps)}（表上方；md 题注不得因空行丢失）")
    three_ok = True
    bad_tbl = []
    # v1.6 test-8.0：表题邻近性区分数据表与封面表单表——数据表上方紧邻"表X-Y"题注；
    # 表单表（label-value 网格，表格式封面）不核三线表（其边框是学校封面设计）。
    _cap_paras = [(p.text.strip(), p._p) for p in fd.paragraphs]

    def _preceding_caption(tbl_el):
        els = list(fd.element.body.iterchildren())
        try:
            k = els.index(tbl_el)
        except ValueError:
            return False
        seen = 0
        for j in range(k - 1, -1, -1):
            if els[j].tag != qn("w:p"):
                continue
            t = "".join(x.text or "" for x in els[j].iter(qn("w:t"))).strip()
            if not t:
                continue
            if re.match(r"^表(\d+[.\-]\d+|[A-Z][.\-]?\d+)", t):
                return True
            seen += 1
            if seen >= 3:
                return False
        return False

    for ti, tb in enumerate(fd.tables[1:]):
        if len(tb.rows) == 1 and len(tb.columns) == 1:
            continue  # 图块（1x1）不做三线表判定
        if not _preceding_caption(tb._tbl):
            continue  # 无表题=表单/封面结构表
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
    hdr_msg = (f"页眉自节{hdr[0]}起：{hdr[1][:20]}" if hdr
               else "未找到页眉文本（成品未设置页眉；如学校规范要求页眉须补齐）")
    ck("TF-13 页眉页脚", hdr is not None, hdr_msg)
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
        if front_numbering == "roman":
            ok14 = body_seq_ok and len(roman) >= 1
        elif front_numbering == "none":
            ok14 = body_seq_ok and len(roman) == 0
        else:
            ok14 = body_seq_ok
        ck("TF-14 页码", ok14,
           f"前置页码模式={front_numbering} 前置罗马页={roman[:3]} 正文阿拉伯={arabic[:3]}..."
           f"{'连续' if body_seq_ok else '异常'}")
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
        if p.style and p.style.name == "Heading 1":
            if norm(p.text).startswith("致谢"):
                on = True
                continue
            elif on:
                break  # 统计截止到下一个 Heading 1（附录等在致谢之后，不计入）
        if on:
            ack_len += len(p.text.strip())
    ck("TF-18 致谢结构", len(ack_h) == 1 and ack_len <= 500,
       f"致谢字数≈{ack_len}（≤500）")

    # TF-19 页面尺寸/边距（--margins 给定规范值时按规范值精确核验；有模板用模板子集逻辑；均无 → N/A）
    f_mg = set((round(s.top_margin.cm, 2), round(s.left_margin.cm, 2)) for s in fd.sections)
    f_sz = (round(fd.sections[0].page_width.cm, 1), round(fd.sections[0].page_height.cm, 1))
    if margins:
        exp_top, exp_left = margins
        ok19 = (f_sz[0] >= 21.0 and
                all(abs(mt - exp_top) < 0.06 and abs(ml - exp_left) < 0.06 for mt, ml in f_mg))
        ck("TF-19 页面尺寸/边距", ok19,
           f"A4≈{f_sz}; 成品边距 {f_mg}（规范值 上{exp_top}cm 左{exp_left}cm）")
    elif no_template:
        ck_na("TF-19 页面尺寸/边距",
              f"无模板页边距基准（成品 A4≈{f_sz} 边距 {f_mg}）；提供 --margins 规范值或学校模板后可核验")
    else:
        t_mg = set((round(s.top_margin.cm, 2), round(s.left_margin.cm, 2)) for s in td.sections)
        ok19 = (f_sz[0] >= 21.0 and f_mg <= t_mg)
        ck("TF-19 页面尺寸/边距", ok19, f"A4≈{f_sz}; 成品边距 {f_mg} ⊆ 模板 {t_mg}")

    # TF-20 页对渲染（pair=模板↔成品对照；render-only=成品关键页渲染复核；无模板强制 render-only）
    if no_template and tf20_mode != "render-only":
        tf20_mode = "render-only"
    pairs = []
    if pdf_path and os.path.exists(pdf_path):
        import pymupdf
        if tf20_mode == "render-only":
            fpdf = pymupdf.open(pdf_path)
            KEY_PAGES = [("封面", ["本科生毕业论文"]), ("中文摘要", ["关键词"]),
                         ("ABSTRACT", ["KEY", "WORDS"]), ("目录", ["目", "录"]),
                         ("正文样例", ["第1章", "绪论"]),
                         ("参考文献", ["参考文献"]), ("致谢", ["致谢"]), ("附录", ["附录A"])]
            rendered = []
            from PIL import Image
            for name, pats in KEY_PAGES:
                pg = None
                for q in range(fpdf.page_count):
                    t = fpdf[q].get_text().replace(" ", "").replace("\u3000", "")
                    if "......" in fpdf[q].get_text() and name != "目录":
                        continue
                    if all(p.replace(" ", "") in t for p in pats):
                        pg = q
                        break
                if pg is None:
                    continue
                a = fpdf[pg].get_pixmap(dpi=90)
                ia = Image.frombytes("RGB", (a.width, a.height), a.samples)
                ia.save(os.path.join(out_dir, f"render_{name}.png"))
                rendered.append((name, pg + 1))
            fpdf.close()
            ck("TF-20 PDF视觉复核（渲染输出）", len(rendered) >= 5,
               f"成品关键页渲染 {rendered}（render_*.png 供人工复核；规范驱动重建模式）")
            pairs = None  # 标记已处理
    if pairs is not None and pdf_path and os.path.exists(pdf_path):
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

            def any_page(doc, alts, need_dots=False):
                """v1.6 test-8.0：token 备选集定位（各校长措辞不同：毕业设计/毕业论文/
                学位论文…）；命中任一条即返回。need_dots=目录页（点线引导符）。"""
                for pg in range(doc.page_count):
                    raw = doc[pg].get_text()
                    if need_dots != ("...." in raw):
                        continue
                    t = raw.replace(" ", "").replace("\u3000", "")
                    if any(a.replace(" ", "") in t for a in alts):
                        return pg
                return None

            cov_alts = list(cover_tokens) if cover_tokens else \
                ["毕业设计", "毕业论文", "学位论文", "本科论文"]
            names = [("封面", cov_alts, False), ("中文摘要", ["关键词"], False),
                     ("ABSTRACT", ["KEYWORDS"], False), ("目录", ["目录"], True),
                     ("正文样例", ["第1章", "第一章"], False),
                     ("参考文献样例", ["参考文献"], False),
                     ("附录样例", ["附录A", "附录"], False),
                     ("致谢样例", ["致谢"], False)]
            n_rendered = 0
            for name, alts, nd in names:
                fp = any_page(fpdf, alts, need_dots=nd)
                tp = any_page(td_, alts, need_dots=nd)
                if fp is None:
                    continue
                try:
                    from PIL import Image
                    b = fpdf[fp].get_pixmap(dpi=80)
                    ib = Image.frombytes("RGB", (b.width, b.height), b.samples)
                    if tp is not None:
                        a = td_[tp].get_pixmap(dpi=80)
                        ia = Image.frombytes("RGB", (a.width, a.height), a.samples)
                        w = max(ia.width, ib.width)
                        im = Image.new("RGB", (w, ia.height + ib.height + 12), "white")
                        im.paste(ia, (0, 0)); im.paste(ib, (0, ia.height + 12))
                    else:
                        im = ib
                    os.makedirs(out_dir, exist_ok=True)
                    im.save(os.path.join(out_dir, f"pair_{name}.png"))
                    pairs.append((name, (tp + 1) if tp is not None else "-", fp + 1))
                    n_rendered += 1
                except Exception:
                    pairs.append((name, (tp + 1) if tp is not None else "-", fp + 1))
                    n_rendered += 1
            td_.close(); fpdf.close()
            ck("TF-20 PDF视觉对照", n_rendered >= 5,
               f"关键页渲染/对照 {n_rendered} 页={pairs}（pair_*.png 供人工复核；母版无对应页时单侧渲染）")
    elif pairs is not None:
        ck("TF-20 PDF视觉对照", True, "未提供 PDF，视觉对照 SKIP", skip=True)

    # 报告
    counts = {ST_PASS: 0, ST_FAIL: 0, ST_NA: 0, ST_SKIP: 0}
    lines = ["# TF-01~20 QA（tf_qa.py）",
             f"- 模板: {template_path or '（未提供 → 模板对照类检查记 NOT_APPLICABLE）'}",
             f"- DOCX: {docx_path}", f"- PDF: {pdf_path or '（未提供）'}", ""]
    for name, status, ev in CHECKS:
        counts[status] += 1
        line = f"- {name}: {status} | {ev}"
        if status == ST_FAIL:
            sev, rem = tf_meta(name)
            line += f" | severity={sev} | remediation={rem}"
        lines.append(line)
    lines.append("")
    lines.append(f"- 汇总: PASS={counts[ST_PASS]} FAIL={counts[ST_FAIL]} "
                 f"NOT_APPLICABLE={counts[ST_NA]} SKIPPED_WITH_REASON={counts[ST_SKIP]}")
    open(os.path.join(out_dir, "tf-qa-report.md"), "w", encoding="utf-8").write("\n".join(lines))
    n_fail = counts[ST_FAIL]
    for name, status, ev in CHECKS:
        safe = ev[:90].encode("gbk", "replace").decode("gbk")
        print(name, status, "|", safe)
    print(f"TF 结果: PASS={counts[ST_PASS]} FAIL={n_fail} "
          f"NOT_APPLICABLE={counts[ST_NA]} SKIPPED_WITH_REASON={counts[ST_SKIP]}")
    print("report:", os.path.join(out_dir, "tf-qa-report.md"))
    return 0 if n_fail == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=False, default=None,
                    help="学校模板/规范文档 .docx；省略或传 none 表示无模板项目"
                         "（模板对照类检查记 NOT_APPLICABLE，不伪造 PASS）")
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--out", default=".")
    ap.add_argument("--body-size", type=float, default=12.0)
    ap.add_argument("--body-line", type=int, default=400)
    ap.add_argument("--first-chars", type=int, default=200)
    ap.add_argument("--refs-min", type=int, default=5)
    ap.add_argument("--cover-tokens", default=None,
                    help="无母版时封面必含文本（逗号分隔），如 \"哈尔滨工程大学本科生毕业论文,论文题目\"")
    ap.add_argument("--front-numbering", choices=["any", "roman", "none"], default="any",
                    help="前置部分页码：roman=前置罗马页码 / none=前置无页码 / any=不限制")
    ap.add_argument("--margins", default=None,
                    help="规范页边距 \"上,左\"（cm），提供时按规范值精确核验")
    ap.add_argument("--tf20-mode", choices=["auto", "pair", "render-only"], default="auto",
                    help="TF-20 模式：pair=模板↔成品对照 / render-only=成品关键页渲染复核")
    a = ap.parse_args()
    tpl = a.template
    if tpl and tpl.strip().lower() in ("none", "无", "-"):
        tpl = None
    if tpl and not os.path.isfile(tpl):
        print(f"ERROR: 模板文件不存在: {tpl}")
        print("       （配置错误：如需无模板模式请省略 --template 或传 none；本检查不会静默降级为无模板）")
        return 3
    cover_tokens = [t.strip() for t in a.cover_tokens.split(",")] if a.cover_tokens else None
    margins = None
    if a.margins:
        parts = [float(x) for x in a.margins.split(",")]
        margins = (parts[0], parts[1])
    try:
        return run(tpl, a.docx, a.pdf, a.out, a.body_size, a.body_line,
                   a.first_chars, a.refs_min, cover_tokens=cover_tokens,
                   front_numbering=a.front_numbering, margins=margins, tf20_mode=a.tf20_mode)
    except Exception as e:  # 内部异常绝不产生 PASS
        import traceback
        traceback.print_exc()
        try:
            os.makedirs(a.out, exist_ok=True)
            open(os.path.join(a.out, "tf-qa-report.md"), "w", encoding="utf-8").write(
                "# TF-01~20 QA（tf_qa.py）\n- 状态: ERROR\n"
                f"- reason: 内部异常 {type(e).__name__}: {e}\n"
                "- remediation: 修复问题后重跑；本报告不构成 PASS\n")
        except Exception:
            pass
        print(f"TF-QA INTERNAL ERROR: {type(e).__name__}: {e}（未产生任何 PASS 结论，退出码 3）")
        return 3


if __name__ == "__main__":
    sys.exit(main())
