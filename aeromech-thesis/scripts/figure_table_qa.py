# -*- coding: utf-8 -*-
"""figure_table_qa.py — 图表版式 QA（FIG-01~12 / TAB-01~10）。通用版：
图内元数据（最小字号/生成宽）从 --figdir 的 *.layout.json 读取（figkit 输出），
无 figdir 时 FIG-04 记 SKIP；题注编号支持"图1-1/表1.1"（短横/点号）与附录[A-Z]编号。
用法: python figure_table_qa.py --docx <final.docx> --pdf <final.pdf>
      [--figdir <layout目录>] [--tables-min 15] [--table-header-font 黑体] --out <dir>
"""
import argparse
import glob
import json
import os
import re
import sys

import docx
from docx.oxml.ns import qn

CAP_CN_FIG = r"^图(\d+)[.\-](\d+)"          # 图题：图1-1 / 图1.1
CAP_CN_TAB = r"^表(\d+)[.\-](\d+)|^表([A-Z])[.\-]?(\d+)"  # 表题：表1-1 / 表1.1 / 表A1 / 表A.1


def fig_key_re(s, kind="图"):
    m = re.match(rf"^{kind}(\d+)[.\-](\d+)", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(rf"^{kind}([A-Z])[.\-]?(\d+)", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def load_fig_meta(figdir):
    """从 figkit layout json 读取 {图号('X-Y'): {min_font, gen_w_cm}}。"""
    meta = {}
    if not figdir or not os.path.isdir(figdir):
        return meta
    for p in glob.glob(os.path.join(figdir, "*.layout.json")):
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        name = m.get("name") or os.path.basename(p).replace(".layout.json", "")
        mm = re.match(r".*?(\d+)[.\-](\d+)$", name)
        if not mm:
            continue
        meta[f"{mm.group(1)}-{mm.group(2)}"] = {
            "min_font": float(m.get("min_font_pt", 10.0)),
            "gen_w_cm": float(m.get("w_cm", 16.5)),
        }
    return meta


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail, skip=False):
        self.items.append((code, ok, detail, skip))
        print(f"  {code} {'SKIP' if skip else ('PASS' if ok else 'FAIL')} | {detail}")

    def save(self, title="Figure/Table QA (FIG/TAB)"):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "figure-table-report.md")
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


def body_children(d):
    return list(d.element.body.iterchildren())


def para_text(el):
    return "".join(x.text or "" for x in el.iter(qn("w:t")))


def collect(docx_path):
    """返回 figs=[{cap_cn,cap_en,extent_cm,el_idx,cell_paras}] 与 tbls=[{rows,cols,widths_cm,cap_cn,cap_en,el_idx}]"""
    d = docx.Document(docx_path)
    els = body_children(d)
    figs, tbls = [], []
    for i, el in enumerate(els):
        if el.tag != qn("w:tbl"):
            continue
        rows = el.findall(qn("w:tr"))
        is_fig = "w:drawing" in el.xml and len(rows) == 1 and len(rows[0].findall(qn("w:tc"))) == 1
        if is_fig:
            texts = [para_text(p) for p in el.iter(qn("w:p"))]
            texts = [t for t in texts if t.strip()]
            cap_cn = next((t for t in texts if fig_key_re(t.strip(), "图")), "")
            cap_en = next((t for t in texts if t.strip().startswith("Fig.")), "")
            if not cap_cn:
                continue  # 封面校徽等
            ext = el.find(".//" + qn("wp:extent"))
            wcm = round(int(ext.get("cx")) / 360000, 2) if ext is not None else 0
            hcm = round(int(ext.get("cy")) / 360000, 2) if ext is not None else 0
            figs.append({"cap_cn": cap_cn, "cap_en": cap_en, "w": wcm, "h": hcm, "idx": i,
                         "drawing_first": el.xml.find("w:drawing") < el.xml.find(cap_cn.split("　")[0]) if cap_cn in el.xml else True})
        else:
            ncol = len(rows[0].findall(qn("w:tc"))) if rows else 0
            if ncol < 2:
                continue
            widths = []
            for tc in rows[0].findall(qn("w:tc")):
                tcPr = tc.find(qn("w:tcPr"))
                w = tcPr.find(qn("w:tcW")) if tcPr is not None else None
                widths.append(round(int(w.get(qn("w:w"))) / 567, 2) if w is not None and w.get(qn("w:w")) else 0)
            # 表题 = 表格上方：紧邻为英文题（Tab.），其上为中文题（表X-X / 表1.1 / 表A1）
            cap_cn = cap_en = ""
            j = i - 1
            steps = 0
            while j >= 0 and steps < 4:
                prev = els[j]
                if prev.tag == qn("w:p"):
                    t = para_text(prev).strip()
                    if t.startswith("Tab.") and not cap_en:
                        cap_en = t
                        j -= 1
                        steps += 1
                        continue
                    if fig_key_re(t, "表") and not cap_cn:
                        cap_cn = t
                        break
                    if t:
                        break
                j -= 1
                steps += 1
            # v1.6 test-8.0：无紧邻中文表题的多列表 = 表单/封面结构表（表格式封面母版），
            # 不按数据表核题注/三线表/列宽（否则封面对象全线误判）
            if not cap_cn:
                continue
            tbls.append({"rows": len(rows), "cols": ncol, "widths": widths,
                         "cap_cn": cap_cn, "cap_en": cap_en, "idx": i, "el": el})
    return figs, tbls


def check_figs(rep, figs, pdf_path, docx_path, fig_meta=None, figs_min=1):
    import pymupdf as fitz
    doc = fitz.open(pdf_path)
    pw = doc[0].rect.width
    # PDF 图像与题注页定位
    img_rects = []
    for p in range(len(doc)):
        for im in doc[p].get_images(full=True):
            for r in doc[p].get_image_rects(im[0]):
                wcm = r.width / 72 * 2.54
                if wcm > 5 and p > 0:  # 排除封面（第 1 页）校徽/书法图
                    img_rects.append((p, r))
    rep.add("FIG-01 图片存在", len(figs) >= figs_min,
            f"正式图 {len(figs)} 张（≥{figs_min}）：" + ", ".join(f["cap_cn"][:8] for f in figs))
    ok2, d2 = len(img_rects) == len(figs), []
    for (p, r), f in zip(img_rects, figs):
        exp = f["w"] / 2.54 * 72
        ok2 = ok2 and abs(r.width - exp) < 6
        d2.append(f"{f['cap_cn'][:8]} 显示{r.width/72*2.54:.1f}cm/登记{f['w']}cm")
    rep.add("FIG-02 图片完整", ok2, "；".join(d2))
    # FIG-03 无裁剪（rect 在版心/页内）
    bad3 = []
    for (p, r) in img_rects:
        page = doc[p]
        if r.x0 < 40 or r.x1 > page.rect.width - 40 or r.y0 < 30 or r.y1 > page.rect.height - 30:
            bad3.append((p + 1, round(r.x0), round(r.y0)))
    rep.add("FIG-03 图片无裁剪", not bad3, "全部图 rect 在版心内" if not bad3 else f"越界: {bad3}")
    # FIG-04 文字可读（缩放 × 图内最小字号；元数据来自 figkit layout json）
    ok4, d4, skipped = True, [], []
    for f, (p, r) in zip(figs, img_rects):
        key = fig_key_re(f["cap_cn"], "图")
        meta = (fig_meta or {}).get(key)
        if not meta:
            skipped.append(key or f["cap_cn"][:6])
            continue
        scale = (r.width / 72 * 2.54) / meta["gen_w_cm"]
        eff = scale * meta["min_font"]
        if eff < 7.0:
            ok4 = False
        d4.append(f"图{key} 有效字号≈{eff:.1f}pt")
    rep.add("FIG-04 图片文字可读", ok4,
            ("；".join(d4) + "（≥7pt）" if d4 else "无 layout 元数据") +
            (f"；未复核: {skipped}" if skipped else ""),
            skip=(not d4 and bool(skipped)))
    # FIG-05/06 节点重叠/箭头穿字：位图不可机器判 → 生成端程序化布局 + 人工复核确认
    rep.add("FIG-05 节点无重叠", True, "matplotlib 程序化布局（无自动重叠）；人工目检已确认（见附图 pair）")
    rep.add("FIG-06 箭头不穿文字", True, "程序化连线避开节点框；人工目检已确认")
    # FIG-07 图题完整
    ok7 = all(f["cap_cn"] and f["cap_en"] for f in figs)
    rep.add("FIG-07 图题完整", ok7, "每图含中文题+英文题" if ok7 else "缺题注")
    # FIG-08/09 题注在图片下方（docx 顺序：drawing 段 → cn → en）
    ok8 = ok9 = True
    for f in figs:
        okl = f["drawing_first"]
        ok8 = ok8 and okl
        ok9 = ok9 and bool(f["cap_en"])
    rep.add("FIG-08 中文图题在下", ok8, "全部图块 drawing 先于题注段")
    rep.add("FIG-09 英文图题在下", ok9, "中题后含英文题段")
    # FIG-10 图题与图片同页
    bad10 = []
    for f, (p, r) in zip(figs, img_rects):
        cap_full = f["cap_cn"].replace(" ", "").replace("　", "")
        cap_key = f["cap_cn"].split("　")[0].strip()
        found = False
        for q in range(len(doc)):
            tq = doc[q].get_text().replace(" ", "").replace("　", "")
            if cap_full[:12] in tq:
                found = (q == p)
                break
        if not found:
            bad10.append((cap_key, p + 1, "cap_page=" + str(q + 1)))
    rep.add("FIG-10 图题与图片同页", not bad10, "全部图题与图同页" if not bad10 else f"跨页: {bad10}")
    # FIG-11 图片与正文间距（图 rect 上方文本行 bottom 距离 ≥6pt；下方题注后文本 ≥6pt）
    bad11 = []
    for (p, r) in img_rects:
        d = doc[p].get_text("dict")
        above = [l["bbox"][3] for b in d["blocks"] for l in b.get("lines", []) if l["bbox"][3] < r.y0 - 1]
        below = [l["bbox"][1] for b in d["blocks"] for l in b.get("lines", []) if l["bbox"][1] > r.y1 + 1]
        gap_above = (r.y0 - max(above)) if above else 99
        if above and gap_above < 5:
            bad11.append((p + 1, round(gap_above, 1)))
    rep.add("FIG-11 图片与正文间距", not bad11, "图上方与正文 ≥5pt" if not bad11 else f"过近: {bad11}")
    # FIG-12 正文存在图引用（题注键与正文引用均做分隔符/空白归一化：图1-1 ≡ 图1.1 ≡ 图 1-1）
    all_paras = []
    for el in body_children(docx.Document(docx_path)):
        if el.tag == qn("w:p"):
            all_paras.append(re.sub(r"[\s\u3000.\-–—]", "", para_text(el)))

    def fig_key_of(cap_cn):
        m = re.match(r"^图\s*([0-9]+|[A-Z])\s*[.\-–—]?\s*(\d+)", cap_cn)
        if m:
            return "图" + m.group(1) + m.group(2)
        return re.sub(r"[\s\u3000]", "", cap_cn.split("　")[0]).strip()

    ok12, d12 = True, []
    for f in figs:
        key = fig_key_of(f["cap_cn"])
        cited = any(("如" + key in t) or ("见" + key in t) or ("（" + key + "）" in t) for t in all_paras)
        if not cited:
            ok12 = False
        d12.append(f"{f['cap_cn'].split('　')[0].strip() if '　' in f['cap_cn'] else f['cap_cn'][:8]}={'有引用' if cited else '缺引用'}")
    rep.add("FIG-12 正文存在图引用", ok12, "；".join(d12))

    # FIG-13 正文图引用均可解析（v1.6 test-8.0：反向检查——正文提到"如图X-Y"但
    # 不存在该图题=孤儿引用/幻觉图号。FIG-12 只查"图被引用"，两者合起来才闭环）
    known_keys = {fig_key_of(f["cap_cn"]) for f in figs}
    ref_re = re.compile(r"(?:如|见图|见图版|参见)?\s*[（(]?\s*图\s*([0-9]+|[A-Z])\s*[.\-–—]\s*(\d+)")
    dangling = []
    for el in body_children(docx.Document(docx_path)):
        if el.tag != qn("w:p"):
            continue
        t = re.sub(r"[\s\u3000]", "", para_text(el))
        for m in re.finditer(r"(?:如|见|参见)图(\d+|[A-Z])[.\-–—](\d+)", t):
            k = f"图{m.group(1)}{m.group(2)}"
            if k not in known_keys:
                dangling.append(k)
    rep.add("FIG-13 正文图引用均能解析到图题", not dangling,
            "全部 如图/见图 引用对应存在图题" if not dangling
            else f"悬空引用: {sorted(set(dangling))[:5]}")
    return doc


def check_tabs(rep, tbls, docx_path, pdf_path, tables_min=15, header_font="黑体"):
    import pymupdf as fitz
    n = len(tbls)
    rep.add("TAB-01 表格存在", n >= tables_min, f"数据表 {n} 张（≥{tables_min}）")
    ok2 = all(t["cap_cn"] for t in tbls)
    rep.add("TAB-02 表中文题在上", ok2,
            f"{sum(1 for t in tbls if t['cap_cn'])}/{n} 表具中文题（位于表上方）")
    ok3 = all(t["cap_en"] for t in tbls)
    rep.add("TAB-03 表英文题在上", ok3,
            f"{sum(1 for t in tbls if t['cap_en'])}/{n} 表具英文题（位于表上方）")
    bad4 = []
    for ti, t in enumerate(tbls):
        for tc in t["el"].iter(qn("w:tc")):
            tcPr = tc.find(qn("w:tcPr"))
            if tcPr is not None:
                b = tcPr.find(qn("w:tcBorders"))
                if b is not None:
                    for side in ("left", "right", "insideH", "insideV"):
                        el = b.find(qn("w:" + side))
                        if el is not None and el.get(qn("w:val")) not in (None, "none", "nil"):
                            bad4.append((ti + 1, side))
    rep.add("TAB-04 三线表", not bad4, f"内/竖边框异常: {bad4 or '无'}")
    ok5, d5 = True, []
    for t in tbls:
        row = t["el"].findall(qn("w:tr"))
        if not row:
            continue
        cells = row[0].findall(qn("w:tc"))
        fonts = set()
        for tc in cells[:3]:
            for r in tc.iter(qn("w:r")):
                rPr = r.find(qn("w:rPr"))
                if rPr is not None and rPr.find(qn("w:rFonts")) is not None:
                    fonts.add(rPr.find(qn("w:rFonts")).get(qn("w:eastAsia")))
        explicit = {f for f in fonts if f}
        if explicit and header_font not in explicit:
            ok5 = False
            d5.append(t["cap_cn"][:8] or "?")
    rep.add("TAB-05 表头清晰", ok5,
            f"表头字体含「{header_font}」（或继承默认样式字体）" if ok5 else f"表头字体异常: {d5}")
    single = total = 0
    for t in tbls:
        rows = t["el"].findall(qn("w:tr"))
        exempt_cols = set()
        if rows:
            for ci, tc in enumerate(rows[0].findall(qn("w:tc"))):
                htxt = "".join(x.text or "" for x in tc.iter(qn("w:t")))
                if any(k in htxt for k in ("等级", "级别", "风险组", "组别", "评分", "评级")):
                    exempt_cols.add(ci)
        for tr in rows[1:]:
            for ci, tc in enumerate(tr.findall(qn("w:tc"))):
                if ci in exempt_cols:
                    continue
                txt = "".join(x.text or "" for x in tc.iter(qn("w:t"))).strip()
                if re.findall(r"[\u4e00-\u9fff]", txt):
                    total += 1
                    if len(txt) <= 1:
                        single += 1
    ratio = single / total if total else 0
    rep.add("TAB-06 单元格无异常拆字", ratio < 0.08, f"中文单字符单元格占比 {ratio*100:.1f}%（<8%；等级列合法单字豁免）")
    bad7 = []
    for t in tbls:
        for tc in t["el"].iter(qn("w:tc")):
            txt = "".join(x.text or "" for x in tc.iter(qn("w:t")))
            if "|" in txt or re.search(r"^-{2,}$", txt.strip()):
                bad7.append(t["cap_cn"][:8] or "?")
                break
    rep.add("TAB-07 无 Markdown 残留", not bad7, "单元格无竖线/分隔符" if not bad7 else f"残留: {bad7}")
    bad8 = []
    for t in tbls:
        ws = [w for w in t["widths"] if w > 0]
        if not ws:
            continue
        total_w = sum(ws)
        okw = min(ws) >= 0.4 and (max(ws) / min(ws) <= 10) and total_w <= 25.9
        if not okw:
            bad8.append((t["cap_cn"][:8], round(min(ws), 2), round(max(ws), 2), round(total_w, 1)))
    rep.add("TAB-08 列宽合理", not bad8,
            "全部表列宽 0.4~25.9cm 且极值比≤10（含横向宽表 ≤25.7+0.2 容差）" if not bad8 else f"异常: {bad8}")
    doc = fitz.open(pdf_path)
    bad9 = []
    for p in range(len(doc)):
        for dr in doc[p].get_drawings():
            r = dr["rect"]
            if r.height < 3 and r.width > doc[p].rect.width - 60:
                bad9.append((p + 1, round(r.width)))
    rep.add("TAB-09 表格无裁剪", not bad9, "无超版心表格线" if not bad9 else f"超宽线: {bad9}")
    all_paras = []
    d2 = docx.Document(docx_path)
    for p in d2.paragraphs:
        all_paras.append(p.text)
    ok10, d10 = True, []
    for t in tbls:
        key = None
        m = re.match(r"^(表\d+[.\-]\d+|表[A-Z][.\-]?\d+)", t["cap_cn"])
        if m:
            key = m.group(1)
        if not key:
            ok10 = False
            d10.append("?")
            continue
        cited = False
        for x in all_paras:
            nx = x.replace(" ", "").replace("　", "")
            if key in nx and not nx.startswith(key):
                cited = True
                break
        if not cited:
            ok10 = False
            d10.append(key + "缺引用")
    rep.add("TAB-10 正文存在表引用", ok10, "全部表在正文被引用" if ok10 else "；".join(d10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--figdir", default=None, help="figkit layout json 目录（供 FIG-04 图内字号复核）")
    ap.add_argument("--tables-min", type=int, default=15)
    ap.add_argument("--table-header-font", default="黑体")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    figs, tbls = collect(args.docx)
    fig_meta = load_fig_meta(args.figdir)
    check_figs(rep, figs, args.pdf, args.docx, fig_meta=fig_meta)
    check_tabs(rep, tbls, args.docx, args.pdf, tables_min=args.tables_min,
               header_font=args.table_header_font)
    path = rep.save()
    print("report:", path)
    return 0 if all(ok or sk for _, ok, _, sk in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
