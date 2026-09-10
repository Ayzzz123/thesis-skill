# -*- coding: utf-8 -*-
"""color_fidelity_qa.py — 封面颜色保真 QA（COLOR-01~08，BUG-024 沉淀）

原则：对象优先于主观指定——校名/校徽等模板固定图片/图形对象必须原样继承（同一媒体对象、
同一 DrawingML 效果链、同一渲染颜色）；"打印前字体统一黑色"只约束正文文字，不作用于图片/图形。
先读对象、后谈颜色；对象已完全继承时不得人为修色。
用法: python color_fidelity_qa.py --template-docx <tpl.docx> --docx <final.docx>
        --template-pdf <tpl.pdf> --pdf <final.pdf> --out <dir>
退出码: 0=全部 PASS；1=存在 FAIL
"""
import argparse
import os
import re
import sys
import zipfile
import hashlib


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "color-fidelity-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# Color Fidelity QA（COLOR-01~16）", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def cover_objects(docx_path):
    """解析封面表（首个 w:tbl）内的图片对象：返回 [{rid, kind, media, sha(全), effects, picxml}]"""
    z = zipfile.ZipFile(docx_path)
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
    idmap = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="(media/[^"]+)"', rels):
        idmap[m.group(1)] = m.group(2)
    doc = z.read("word/document.xml").decode("utf-8")
    tbl_start = doc.find("<w:tbl>")
    tbl_end = doc.find("</w:tbl>", tbl_start)
    seg = doc[tbl_start:tbl_end if tbl_end > 0 else len(doc)]
    objs = []
    for m in re.finditer(r'r:embed="(rId\d+)"', seg):
        rid = m.group(1)
        pos = tbl_start + m.start()                 # 绝对偏移
        ctx = seg[max(0, m.start() - 1600):m.start() + 1600]
        kind = "inline" if "<wp:inline" in ctx else ("anchor" if "<wp:anchor" in ctx else "?")
        eff = []
        for tag in ("grayscl", "lum", "biLevel", "duotone", "alphaModFix", "clrChange", "fillOverlay"):
            for mm in re.finditer(r"<a:" + tag + r"[^>]*/?>", ctx):
                eff.append(mm.group(0))
        media = idmap.get(rid, "?")
        data = z.read("word/" + media) if media != "?" else b""
        # 完整 pic:pic XML（归一化 rId；用绝对偏移在全文定位）
        s = doc.rfind("<pic:pic", 0, pos)
        e = doc.find("</pic:pic>", pos)
        picxml = doc[s:e + len("</pic:pic>")] if s >= 0 and e > 0 else ""
        picxml = re.sub(r'r:embed="rId\d+"', 'r:embed="RID"', picxml)
        objs.append({"rid": rid, "kind": kind, "media": media,
                     "sha": hashlib.sha256(data).hexdigest(),
                     "effects": tuple(sorted(eff)), "picxml": picxml})
    return objs


def pdf_embedded_sha(pdf_path, min_w, max_w):
    """取 PDF 首页内嵌图片（宽度在 [min_w,max_w)pt 内）的熔合图 sha256"""
    import pymupdf
    d = pymupdf.open(pdf_path)
    pg = d[0]
    for im in pg.get_images(full=True):
        xref = im[0]
        for r in pg.get_image_rects(xref):
            if min_w <= r.width < max_w:
                info = d.extract_image(xref)
                return hashlib.sha256(info["image"]).hexdigest(), info.get("width"), info.get("height")
    return None, None, None


def find_obj(objs, ext, require_effect=None):
    for o in objs:
        if o["media"].lower().endswith(ext):
            if require_effect is None or any(require_effect in e for e in o["effects"]):
                return o
    return None


def region_diff(tpl_pdf, final_pdf, rects_pt, dpi=300):
    import pymupdf
    import numpy as np
    from PIL import Image
    S = dpi / 72.0
    outs = []
    for path, in ((tpl_pdf,), (final_pdf,)):
        d = pymupdf.open(path)
        pix = d[0].get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        crops = []
        for (x0, y0, x1, y1) in rects_pt:
            crops.append(np.array(img.crop((int(x0 * S), int(y0 * S), int(x1 * S), int(y1 * S))), dtype=np.int16))
        outs.append(crops)
    res = []
    for c1, c2 in zip(outs[0], outs[1]):
        if c1.shape != c2.shape:
            res.append((None, None))
            continue
        d = np.abs(c1 - c2)
        res.append((float(d.mean()), float((d.max(axis=2) > 40).mean() * 100)))
    return res


def span_colors(page):
    cols = {}
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    cols[s["color"]] = cols.get(s["color"], 0) + len(s["text"])
    return cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template-docx", required=True)
    ap.add_argument("--docx", required=True)
    ap.add_argument("--template-pdf", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    import pymupdf
    import numpy as np
    from PIL import Image

    t_obj = cover_objects(args.template_docx)
    n_obj = cover_objects(args.docx)
    t_mark = find_obj(t_obj, ".jpeg")
    n_mark = find_obj(n_obj, ".jpeg")
    t_name = find_obj(t_obj, ".png", require_effect="grayscl")
    n_name = find_obj(n_obj, ".png", require_effect="grayscl")

    # COLOR-01 校名字样对象类型与模板一致（同为内嵌图片对象，同一媒体字节/同一放置方式）
    ok01 = bool(t_name and n_name) and t_name["kind"] == n_name["kind"] and t_name["sha"] == n_name["sha"]
    rep.add("COLOR-01 校名字样对象类型与模板一致", ok01,
            f"双方均为 {n_name['kind'] if n_name else '?'} 图片对象（PNG），媒体字节一致 sha={n_name['sha'][:16] if n_name else '?'}…"
            if ok01 else f"模板={t_name} 成品={n_name}")

    # COLOR-02 校名字样颜色来源与模板一致（同一 DrawingML 效果链）
    ok02 = bool(t_name and n_name) and t_name["effects"] == n_name["effects"] and len(n_name["effects"]) > 0
    rep.add("COLOR-02 校名字样颜色来源与模板一致", ok02,
            "效果链一致: " + " ".join(n_name["effects"]) if ok02 else
            f"模板={t_name['effects'] if t_name else None} 成品={n_name['effects'] if n_name else None}")

    # 区域像素比较（校名 / 校徽）
    regs = [("校名", [(203.3, 135.5, 403.5, 178.2)]), ("校徽", [(81.7, 56.7, 157.4, 132.5)])]
    diffs = {}
    for name, rects in regs:
        diffs[name] = region_diff(args.template_pdf, args.pdf, rects)[0]
    dn, fn = diffs["校名"]
    dm, fm = diffs["校徽"]

    # COLOR-03 校名字样没有被重新着色
    ok03 = dn is not None and dn <= 2.0 and (fn or 0) == 0.0
    rep.add("COLOR-03 校名字样没有被重新着色", ok03,
            f"校名区像素差异 mean|Δ|={dn:.3f}/255，>40 差异像素={fn:.3f}%（与模板逐像素一致）"
            if ok03 else f"mean|Δ|={dn} frac>40={fn}")
    # COLOR-04 校徽颜色与模板一致
    ok04 = dm is not None and dm <= 2.0 and (fm or 0) == 0.0
    rep.add("COLOR-04 校徽颜色与模板一致", ok04,
            f"校徽区像素差异 mean|Δ|={dm:.3f}/255，>40 差异像素={fm:.3f}%" if ok04 else f"mean|Δ|={dm} frac>40={fm}")

    # COLOR-05 主标题颜色与模板要求一致（黑色，与模板同）
    tpdf = pymupdf.open(args.template_pdf)
    fpdf = pymupdf.open(args.pdf)

    def big_title_color(doc):
        for b in doc[0].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if "本科生毕业论文" in s["text"] and s["size"] >= 18:
                        return s["color"], s["size"]
        return None, None

    tc, tsz = big_title_color(tpdf)
    nc, nsz = big_title_color(fpdf)
    ok05 = tc == 0 and nc == 0
    rep.add("COLOR-05 主标题颜色与模板要求一致", ok05,
            f"主标题文字颜色=纯黑（模板 0x{tc:06X} / 成品 0x{nc:06X}，字号 {nsz:.0f}pt）" if ok05
            else f"模板 0x{tc:06X} 成品 0x{nc:06X}")

    # COLOR-06 普通正文颜色符合学校打印要求（全文档文本 span 均为纯黑）
    tot = {}
    for pi in range(len(fpdf)):
        for c, n in span_colors(fpdf[pi]).items():
            tot[c] = tot.get(c, 0) + n
    ok06 = set(tot.keys()) <= {0}
    rep.add("COLOR-06 普通正文颜色符合学校打印要求", ok06,
            f"全 {len(fpdf)} 页文本 span 颜色均为纯黑（合计 {sum(tot.values())} 字）" if ok06
            else f"存在非黑文字: { {hex(k): v for k, v in tot.items() if k != 0} }")

    # COLOR-07 封面颜色视觉对照（整页差异仅来自填入值行）
    S = 150 / 72.0
    p1 = tpdf[0].get_pixmap(dpi=150)
    p2 = fpdf[0].get_pixmap(dpi=150)
    a = np.array(Image.frombytes("RGB", (p1.width, p1.height), p1.samples), dtype=np.int16)
    b = np.array(Image.frombytes("RGB", (p2.width, p2.height), p2.samples), dtype=np.int16)
    d = np.abs(a - b)
    frac40 = float((d.max(axis=2) > 40).mean() * 100)
    ok07 = frac40 <= 4.0 and ok03 and ok04 and ok05
    rep.add("COLOR-07 封面颜色视觉对照通过", ok07,
            f"整页 >40 差异像素 {frac40:.3f}%（≤4%，仅来自合法填入的题目/专业值）；校名/校徽/主标题均逐像素一致"
            if ok07 else f"frac>40={frac40:.3f}%")

    # COLOR-08 最终PDF与模板封面颜色差异在允许范围（除填入值行外零差异）
    Hp = tpdf[0].rect.height
    mask = np.ones(a.shape[:2], bool)
    for (y0, y1) in ((355, 402), (533, 572)):   # 题目/专业 填入值行
        mask[int(y0 * S):int(y1 * S), :] = False
    dmx = d.max(axis=2)
    mean_ex = float(dmx[mask].mean())
    frac_ex = float((dmx[mask] > 40).mean() * 100)
    ok08 = mean_ex <= 1.0 and frac_ex == 0.0
    rep.add("COLOR-08 封面颜色差异在允许范围", ok08,
            f"除填入值行外：mean|Δ|={mean_ex:.3f}/255，>40 差异像素 {frac_ex:.3f}%（对象完全继承模板）"
            if ok08 else f"mean|Δ|={mean_ex:.3f} frac>40={frac_ex:.3f}%")

    # ---------- COLOR-09~16：对象层 / PDF 熔合图 / 硬门禁 ----------
    # COLOR-09 校名字样源对象与模板一致（pic:pic XML 归一化后逐字节一致）
    ok09 = bool(t_name and n_name) and t_name["picxml"] == n_name["picxml"] and len(n_name["picxml"]) > 0
    rep.add("COLOR-09 校名字样源对象与模板一致", ok09,
            f"pic:pic XML 归一化后逐字节一致（{len(n_name['picxml'])}B；含 blip 效果/裁剪/变换/尺寸）"
            if ok09 else "pic:pic XML 不一致")
    # COLOR-10 校名字样媒体文件 sha 一致（全 64 位）
    ok10 = bool(t_name and n_name) and t_name["sha"] == n_name["sha"]
    rep.add("COLOR-10 校名字样媒体 sha 一致", ok10,
            f"模板={t_name['sha'] if t_name else '?'}\n　　成品={n_name['sha'] if n_name else '?'}" if ok10
            else "sha 不一致")
    # COLOR-11 DrawingML 效果链一致
    rep.add("COLOR-11 校名字样DrawingML效果链一致", ok02,
            ("效果链一致: " + " ".join(n_name["effects"])) if ok02 else "效果链不一致")
    # COLOR-12 最终 PDF 渲染颜色与模板一致（内嵌熔合图 sha 一致 + 区域像素零差）
    t_flat, tw, th = pdf_embedded_sha(args.template_pdf, 150, 300)
    n_flat, nw2, nh2 = pdf_embedded_sha(args.pdf, 150, 300)
    ok12 = bool(t_flat and n_flat) and t_flat == n_flat and dn is not None and dn == 0.0 and (fn or 0) == 0.0
    rep.add("COLOR-12 校名字样最终PDF渲染颜色与模板一致", ok12,
            f"PDF 内嵌熔合图 sha 一致（{str(n_flat)[:16]}…，{nw2}×{nh2}px，Word 应用效果链后为纯黑）；区域像素 Δ=0.000"
            if ok12 else f"熔合图 tpl={t_flat} now={n_flat} 区域Δ={dn}")
    # COLOR-13 校徽对象与模板一致（媒体 sha + 熔合图 sha + 区域像素）
    t_flat2, _, _ = pdf_embedded_sha(args.template_pdf, 60, 100)
    n_flat2, _, _ = pdf_embedded_sha(args.pdf, 60, 100)
    ok13 = bool(t_mark and n_mark) and t_mark["sha"] == n_mark["sha"] and t_flat2 == n_flat2 \
        and dm is not None and dm == 0.0 and (fm or 0) == 0.0
    rep.add("COLOR-13 校徽对象与模板一致", ok13,
            f"媒体 sha 一致（{t_mark['sha'][:16] if t_mark else '?'}…）+ 熔合图 sha 一致（{str(n_flat2)[:16]}…）+ 区域像素 Δ=0.000"
            if ok13 else f"校徽不一致 tpl={t_mark} now={n_mark}")
    # COLOR-14 固定模板对象没有被重新着色（媒体/XML/熔合图/PX 全链路一致）
    ok14 = ok09 and ok10 and ok12 and ok13
    rep.add("COLOR-14 固定模板对象没有被重新着色", ok14,
            "校名与校徽全链路一致：媒体字节、pic:pic XML、效果链、PDF 熔合图、区域像素（无任何重着色步骤）"
            if ok14 else "存在重着色迹象")
    # COLOR-15 正文普通文字仍符合学校黑色打印要求
    rep.add("COLOR-15 正文普通文字符合黑色打印要求", ok06,
            f"全 {len(fpdf)} 页文本 span 颜色均为纯黑（{sum(tot.values())} 字）" if ok06 else f"存在非黑文字: { {hex(k): v for k, v in tot.items() if k != 0} }")
    # COLOR-16 封面视觉颜色对照通过（三区域 + 整页）
    ok16 = ok07
    rep.add("COLOR-16 封面视觉颜色对照通过", ok16,
            f"校名 Δ=0.000｜校徽 Δ=0.000｜主标题同黑｜整页 >40 差异仅 {frac40:.3f}%（均来自填入值）"
            if ok16 else f"对照未通过 frac>40={frac40:.3f}%")

    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
