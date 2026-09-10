# -*- coding: utf-8 -*-
"""cover_fidelity.py — Cover Fidelity QA（aeromech-thesis v1.2.0，OBS-007）

封面保真检查 CF-01~20 + 封面表格 tblPr 恢复工具（Word COM 规范化防护）。
规则文档：references/cover-fidelity.md

用法:
    python cover_fidelity.py --template <tpl.docx> --template-pdf <tpl.pdf>
                             --docx <final.docx> --pdf <final.pdf> --out <dir>
    python cover_fidelity.py --restore --template <tpl.docx> --docx <final.docx>

退出码：0=全部 PASS；1=存在 FAIL；2=参数/环境错误
"""
import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn

CN_NUM = "一二三四五六七八九十"


# ---------------- 工具 ----------------
def _cell_text(tbl):
    try:
        cell = tbl.cell(0, 0)
    except Exception:
        return ""
    return "\n".join(p.text for p in cell.paragraphs)


def _drawing_count(el_xml):
    return el_xml.count("<w:drawing") + el_xml.count("<w:drawing ")


def _has_textbox(el_xml):
    return ("v:textbox" in el_xml) or ("w:txbxContent" in el_xml)


def _cover_tbl(doc):
    if not doc.tables:
        return None
    return doc.tables[0]


def _tblpr_children(tbl):
    tblPr = tbl._tbl.find(qn("w:tblPr"))
    return tblPr if tblPr is not None else None


def _pdf_page_images(page):
    out = []
    for im in page.get_images(full=True):
        xref = im[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        for r in rects:
            out.append((xref, tuple(round(v, 3) for v in (r.x0, r.y0, r.x1, r.y1))))
    return out


def _line_y(page, needle):
    """返回 PDF 页面中含 needle 的首个文本行 y；未找到返回 None"""
    d = page.get_text("dict")
    for b in d["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"])
            if needle in txt.replace(" ", "").replace("\u3000", ""):
                return l["bbox"][1]
    return None


def _page_fg_mask(page, dpi=100):
    """页面前景（非白像素）布尔掩膜（numpy bool 数组）"""
    import numpy as np
    pix = page.get_pixmap(dpi=dpi)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n >= 3:
        gray = arr[:, :, :3].mean(axis=2)
    else:
        gray = arr[:, :, 0]
    if pix.n == 4:
        alpha = arr[:, :, 3]
        return (gray < 245) | (alpha < 250)
    return gray < 245


# ---------------- tblPr 恢复 ----------------
def restore_cover_tblpr(template_path, docx_path):
    """Word COM 保存会把封面表格 tblPr 规范化（丢失 tblStyle/tblCellMar 并加 tblLook）。
    从模板封面表把 tblStyle/tblCellMar 重新注入成品封面表。返回注入的元素名列表。"""
    tpl = docx.Document(template_path)
    fin = docx.Document(docx_path)
    tt = _cover_tbl(tpl)
    ft = _cover_tbl(fin)
    if tt is None or ft is None:
        return []
    t_pr = _tblpr_children(tt)
    f_pr = _tblpr_children(ft)
    if t_pr is None or f_pr is None:
        return []
    injected = []
    for tag in ("w:tblStyle", "w:tblCellMar"):
        src = t_pr.find(qn(tag))
        if src is None:
            continue
        if f_pr.find(qn(tag)) is not None:
            continue
        if tag == "w:tblStyle":
            style_id = src.get(qn("w:val"))
            styles = tpl.styles.element
            if style_id is None or styles.find(".//" + qn("w:style") + '[@' + qn("w:styleId") + '="' + style_id + '"]') is None:
                continue  # 模板样式不存在则跳过（无效引用会损坏文档）
        new_el = src.__deepcopy__(None)
        f_pr.append(new_el)
        injected.append(tag)
    fin.save(docx_path)
    return injected


# ---------------- CF 检查 ----------------
class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self, title="Cover Fidelity QA"):
        lines = [f"# {title}", ""]
        fails = [c for c, ok, _ in self.items if not ok]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        path = os.path.join(self.out_dir, "cover-fidelity-report.md")
        os.makedirs(self.out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def run(tpl_docx, tpl_pdf, fin_docx, fin_pdf, out_dir):
    rep = Report(out_dir)
    import pymupdf as fitz
    # ---------- docx 证据 ----------
    td = docx.Document(tpl_docx)
    fd = docx.Document(fin_docx)
    t_tbl, f_tbl = _cover_tbl(td), _cover_tbl(fd)
    rep.add("CF-01 模板封面页存在", t_tbl is not None and f_tbl is not None and len(td.tables) > 0,
            f"模板首表={'有' if t_tbl else '无'} 成品首表={'有' if f_tbl else '无'}")
    if t_tbl is None or f_tbl is None:
        rep.save()
        return 1
    t_xml, f_xml = t_tbl._tbl.xml, f_tbl._tbl.xml
    n_t_img, n_f_img = _drawing_count(t_xml), _drawing_count(f_xml)
    rep.add("CF-02 图片数量一致", n_t_img == n_f_img and n_t_img >= 1,
            f"模板封面图={n_t_img} 成品封面图={n_f_img}")
    # CF-03/04：校徽与书法字样 = 封面 inline 图（≥2 张视为校徽+书法字样）
    rep.add("CF-03 圆形校徽存在", n_t_img >= 1 and n_f_img >= 1,
            f"封面图≥1（模板 {n_t_img}/成品 {n_f_img}）")
    rep.add("CF-04 校名字样存在", n_t_img >= 2 and n_f_img >= 2,
            f"封面图≥2 判定校徽+书法字样齐全（模板 {n_t_img}/成品 {n_f_img}）")
    tc, fc = _cell_text(t_tbl), _cell_text(f_tbl)
    def norm(s):
        return s.replace(" ", "").replace("\u3000", "")
    def has_date(t):
        return ("年" in t) and ("月" in t) and ("日" in t)
    for code, key in [("CF-05", "本科生毕业论文（设计）"),
                      ("CF-06", "题    目"), ("CF-07", "姓    名"), ("CF-08", "学    号"),
                      ("CF-09", "学    院"), ("CF-10", "专    业"),
                      ("CF-11", "指导教师"), ("CF-12", "职称")]:
        ok = norm(key) in norm(tc) and norm(key) in norm(fc)
        rep.add(f"{code} {key.replace(chr(32), '')}字段存在", ok,
                f"模板={'有' if norm(key) in norm(tc) else '无'} 成品={'有' if norm(key) in norm(fc) else '无'}")
    rep.add("CF-13 日期字段存在", has_date(tc) and has_date(fc),
            f"模板={'有' if has_date(tc) else '无'} 成品={'有' if has_date(fc) else '无'}（年/月/日）")
    # CF-14 表格结构
    def tbl_struct(tbl):
        tblPr = tbl._tbl.find(qn("w:tblPr"))
        attrs = {}
        if tblPr is not None:
            for tag, attr in (("w:tblW", "w:w"), ("w:tblLayout", "w:type"), ("w:tblInd", "w:w")):
                el = tblPr.find(qn(tag))
                if el is not None:
                    attrs[tag] = el.get(qn(attr)) if attr else None
            attrs["tblStyle"] = tblPr.find(qn("w:tblStyle")) is not None
            attrs["cellMar"] = tblPr.find(qn("w:tblCellMar")) is not None
        return len(tbl.rows), len(tbl.columns), attrs
    tr, tcol, ta = tbl_struct(t_tbl)
    fr, fcol, fa = tbl_struct(f_tbl)
    ok14 = (tr, tcol) == (fr, fcol) and ta.get("w:tblW") == fa.get("w:tblW") and ta.get("w:tblLayout") == fa.get("w:tblLayout")
    warn = []
    if ta.get("tblStyle") and not fa.get("tblStyle"):
        warn.append("tblStyle 缺失（须先运行 --restore 注入）")
        ok14 = False
    if ta.get("cellMar") and not fa.get("cellMar"):
        warn.append("tblCellMar 缺失（须先运行 --restore 注入）")
        ok14 = False
    rep.add("CF-14 表格结构一致", ok14,
            f"行列={fr}x{fcol} tblW/布局一致；" + ("；".join(warn) if warn else "tblStyle/cellMar 齐备"))
    rep.add("CF-15 文本框结构一致",
            _has_textbox(t_xml) == _has_textbox(f_xml),
            f"模板封面文本框={'有' if _has_textbox(t_xml) else '无'} 成品={'有' if _has_textbox(f_xml) else '无'}")
    # ---------- PDF 证据 ----------
    tp, fp = fitz.open(tpl_pdf), fitz.open(fin_pdf)
    tp1, fp1 = tp[0], fp[0]
    t_imgs, f_imgs = _pdf_page_images(tp1), _pdf_page_images(fp1)
    h = tp1.rect.height
    ok16, ok17 = True, True
    detail16 = []
    if len(t_imgs) != len(f_imgs):
        ok16 = False
        detail16.append(f"图数 {len(t_imgs)} vs {len(f_imgs)}")
    for i, (ti, fi) in enumerate(zip(t_imgs, f_imgs)):
        dx = abs(ti[1][0] - fi[1][0]); dy = abs(ti[1][1] - fi[1][1])
        dw = abs((ti[1][2] - ti[1][0]) - (fi[1][2] - fi[1][0]))
        dh = abs((ti[1][3] - ti[1][1]) - (fi[1][3] - fi[1][1]))
        if dy > 2 or dx > 2:
            ok16 = False
        if dw > 1 or dh > 1:
            ok17 = False
        detail16.append(f"图{i+1}: 偏移Δ=({dx:.1f},{dy:.1f})pt")
        if fi[1][1] < 0 or fi[1][3] > h + 1:
            ok16 = False
            detail16.append("顶部/底部越界裁切")
    rep.add("CF-16 图片位置一致", ok16, "；".join(detail16) or "无图")
    rep.add("CF-17 图片尺寸一致", ok17, "逐图宽高差<1pt" if ok17 else "存在尺寸偏差")
    # CF-18 关键文本行位置
    key_lines = [("本科生毕业论文（设计）", "主标题行"),
                 ("20", "日期行"), ("指导教师", "指导教师行")]
    deltas = []
    for needle, label in key_lines:
        ty = _line_y(tp1, needle)
        fy = _line_y(fp1, needle)
        if ty is not None and fy is not None:
            deltas.append(abs(ty - fy))
    ok18 = bool(deltas) and max(deltas) < 6
    rep.add("CF-18 封面视觉布局一致", ok18,
            f"关键行偏移 Δmax={max(deltas):.1f}pt（<6pt）" if deltas else "关键行未定位")
    # CF-19 像素覆盖率：固定区（页面上部 45%：校徽/书法字样/主标题/题目标签）
    # 可变字段填写带（占位下划线被字段值替换属预期行为，不计入缺失判据）
    t_mask, f_mask = _page_fg_mask(tp1), _page_fg_mask(fp1)
    import numpy as np
    mh = min(t_mask.shape[0], f_mask.shape[0])
    mw = min(t_mask.shape[1], f_mask.shape[1])
    t_mask, f_mask = t_mask[:mh, :mw], f_mask[:mh, :mw]
    cut = int(mh * 0.45)
    t_fix, f_fix = t_mask[:cut], f_mask[:cut]
    t_total = int(t_fix.sum())
    covered = int((t_fix & f_fix).sum())
    ratio = (covered / t_total) if t_total else 1.0
    ok19 = ratio >= 0.98
    rep.add("CF-19 封面第一页无内容缺失", ok19,
            f"固定区（上部 45%）前景覆盖 {ratio*100:.1f}%（≥98%，可变字段带排除）")
    # CF-20 视觉对照 PNG + 汇总
    pair = os.path.join(out_dir, "pair_cover.png")
    try:
        from PIL import Image
        t_pix = tp1.get_pixmap(dpi=110)
        f_pix = fp1.get_pixmap(dpi=110)
        im1 = Image.frombytes("RGB", (t_pix.width, t_pix.height), t_pix.samples).convert("RGB")
        im2 = Image.frombytes("RGB", (f_pix.width, f_pix.height), f_pix.samples).convert("RGB")
        hh = max(im1.height, im2.height)
        canvas = Image.new("RGB", (im1.width + im2.width + 20, hh), "white")
        canvas.paste(im1, (0, 0)); canvas.paste(im2, (im1.width + 20, 0))
        os.makedirs(out_dir, exist_ok=True)
        canvas.save(pair)
    except Exception:
        pair = "(PNG 生成失败)"
    ok20 = ok16 and ok17 and ok18 and ok19
    rep.add("CF-20 封面视觉回归", ok20,
            f"CF-16~19 汇总；对照图 {os.path.basename(pair)}（人工复核）")
    # ---------- v1.3.0 新增：CF-21~25（OBS-008） ----------
    # CF-21 对象树一致：封面区 body 元素序列 + cell 段落签名（绘图/横线/标签）
    def cover_region(d):
        els = []
        for el in d.element.body.iterchildren():
            els.append(el)
            if el.tag == qn("w:p"):
                pPr = el.find(qn("w:pPr"))
                if pPr is not None and pPr.find(qn("w:sectPr")) is not None:
                    break
        return els

    def para_sig(p_el):
        xml = p_el.xml
        has_draw = ("w:drawing" in xml) or ("w:pict" in xml)
        has_rule = False
        text = "".join(t.text or "" for t in p_el.iter(qn("w:t"))).strip()
        for r in p_el.iter(qn("w:r")):
            rPr = r.find(qn("w:rPr"))
            if rPr is not None and rPr.find(qn("w:u")) is not None:
                rtext = "".join(t.text or "" for t in r.iter(qn("w:t")))
                if not rtext.strip():
                    has_rule = True
        return has_draw, has_rule, text

    t_region, f_region = cover_region(td), cover_region(fd)
    issues21 = []
    if [el.tag for el in t_region] != [el.tag for el in f_region]:
        issues21.append("封面区元素序列不一致")
    t_ps = [para_sig(p._p) for p in t_tbl.cell(0, 0).paragraphs]
    f_ps = [para_sig(p._p) for p in f_tbl.cell(0, 0).paragraphs]
    if len(t_ps) != len(f_ps):
        issues21.append(f"段落数 {len(t_ps)}/{len(f_ps)}")
    for i, (ta, fb) in enumerate(zip(t_ps, f_ps)):
        if ta[0] and not fb[0]:
            issues21.append(f"P{i} 绘图对象丢失")
        if ta[1] and not fb[1]:
            issues21.append(f"P{i} 横线（u=single）丢失")
        if ta[2] and norm(ta[2]) not in norm(fb[2]):
            issues21.append(f"P{i} 标签文本缺失")
    rep.add("CF-21 对象树一致（封面区）", not issues21,
            "；".join(issues21) if issues21 else f"元素序列/{len(f_ps)} 段/绘图/横线/标签 全部一致")
    # CF-22 首表图片数量（独立编号，同源证据）
    rep.add("CF-22 首表图片数量一致", n_t_img == n_f_img,
            f"模板封面图={n_t_img} 成品封面图={n_f_img}")
    # CF-23 固定图片位置/尺寸（复用 CF-16/17 的 PDF 证据，含越界裁切检测）
    rep.add("CF-23 固定图片位置/尺寸一致", ok16 and ok17,
            "复用 CF-16/17：逐图 rect 偏移/尺寸比对")
    # CF-24 文本框数量一致
    def txbx_count(x):
        return x.count("v:textbox") + x.count("w:txbxContent")
    rep.add("CF-24 封面文本框数量一致", txbx_count(t_xml) == txbx_count(f_xml),
            f"模板={txbx_count(t_xml)} 成品={txbx_count(f_xml)}")
    # CF-25 首屏全页视觉回归：全页覆盖 + 固定区 + 图像区域（校徽/书法缺失直接 FAIL）
    import numpy as _np
    full_ratio = (t_mask & f_mask).sum() / t_mask.sum() if t_mask.sum() else 1.0
    img_ok = len(t_imgs) == len(f_imgs)
    img_detail = []
    for k, (ti, fi) in enumerate(zip(t_imgs, f_imgs)):
        x0, y0, x1, y1 = [int(round(v * 100 / 72)) for v in ti[1]]
        x0 = max(0, x0 - 2); y0 = max(0, y0 - 2)
        x1 = min(t_mask.shape[1], x1 + 2); y1 = min(t_mask.shape[0], y1 + 2)
        reg_t = t_mask[y0:y1, x0:x1]
        reg_f = f_mask[y0:y1, x0:x1]
        r = (reg_t & reg_f).sum() / reg_t.sum() if reg_t.sum() else 0.0
        if r < 0.98:
            img_ok = False
        img_detail.append(f"图{k+1} {r*100:.1f}%")
    ok25 = (full_ratio >= 0.95) and (ratio >= 0.98) and img_ok
    rep.add("CF-25 首屏全页视觉回归", ok25,
            f"全页 {full_ratio*100:.1f}%（>=95%）| 固定区 {ratio*100:.1f}% | " + " ".join(img_detail))

    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--template-pdf", default=None)
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--out", default=".")
    ap.add_argument("--restore", action="store_true",
                    help="仅执行封面表格 tblPr 恢复（Word COM 规范化防护），不跑 QA")
    args = ap.parse_args()
    if args.restore:
        injected = restore_cover_tblpr(args.template, args.docx)
        print("tblPr 注入:", injected if injected else "（无需注入或模板无样式）")
        return 0
    if not args.template_pdf or not args.pdf:
        print("错误: 需要 --template-pdf 与 --pdf（先导出模板与成品的 PDF）")
        return 2
    return run(args.template, args.template_pdf, args.docx, args.pdf, args.out)


if __name__ == "__main__":
    sys.exit(main())
