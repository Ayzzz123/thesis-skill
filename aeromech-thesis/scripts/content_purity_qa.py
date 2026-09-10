# -*- coding: utf-8 -*-
"""content_purity_qa.py — 内容净化与附录分页 QA（MD/INT/PRM/APX/TABCAP），thesis-test-4.0 交付验证用。
MD-01 无 Markdown 残留；INT-01 无内部路径泄漏；PRM-01 无提示语/角色词泄漏；
APX-01 附录标题独立起页；APX-02 附录表不跨页断裂；
TABCAP-01~08 表启动块（TABLE_START_BLOCK）：中英题同页/英题与表头同页/表头与首行同页/
表题不单独留上一页/启动页无大片空白/长表跨页重复表头/图表题注顺序正确/图3-1后无长重复说明。
用法: python content_purity_qa.py --docx <final.docx> --pdf <final.pdf> --out <dir>
"""
import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self, title="Content Purity / Appendix Flow QA"):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "content-purity-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = [f"# {title}", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines.append("")
        lines.append(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rep = Report(args.out)
    import pymupdf as fitz
    doc = fitz.open(args.pdf)
    pages = [doc[i].get_text() for i in range(len(doc))]
    full = "\n".join(pages)
    d = docx.Document(args.docx)

    # MD-01 Markdown 残留（PDF 文本层）
    bad_md = []
    for i, t in enumerate(pages):
        if "**" in t:
            bad_md.append((i + 1, "**"))
        if "|" in t:
            bad_md.append((i + 1, "|"))
        if re.search(r"^\s*#{1,3}\s", t, re.M):
            bad_md.append((i + 1, "##"))
        if re.search(r"^\s*-{3,}\s*$", t, re.M):
            bad_md.append((i + 1, "---"))
    rep.add("MD-01 无 Markdown 残留", not bad_md,
            "无 ** / | / ## / --- 残留" if not bad_md else f"残留: {bad_md}")

    # INT-01 内部路径/工程词泄漏
    leaks = []
    for kw in ["artifacts/", ".aeromech", "transcripts/", "state.yaml", "materials.yaml",
               "qa-report", "build_docx", "basis-notes", "fmea-table.md", "literature.md",
               "thesis-test", "Desktop\\", "C:\\Users"]:
        if kw in full:
            idx = full.find(kw)
            leaks.append((kw, full[max(0, idx - 20):idx + 25].replace("\n", " ")))
    docx_text = []
    for p in d.paragraphs:
        docx_text.append(p.text)
    dtext = "\n".join(docx_text)
    for kw in ["artifacts/", ".aeromech", "build_docx", "thesis-test"]:
        if kw in dtext:
            leaks.append((kw, "docx段落"))
    rep.add("INT-01 无内部路径泄漏", not leaks, "无内部路径/工程词" if not leaks else f"{leaks[:4]}")

    # PRM-01 提示语/角色词泄漏（合法标签除外）
    forbidden = ["Agent", "Skill", "请自行补充", "测试项目", "AI 生成", "语言模型", "ChatGPT", "Claude"]
    hits = []
    for kw in forbidden:
        if kw in full:
            idx = full.find(kw)
            hits.append((kw, full[max(0, idx - 20):idx + 25].replace("\n", " ")))
    if "用户" in full:
        idx = full.find("用户")
        hits.append(("用户", full[max(0, idx - 20):idx + 25].replace("\n", " ")))
    rep.add("PRM-01 无提示语泄漏", not hits,
            "无 Agent/Skill/用户/请自行补充/测试项目" if not hits else f"{hits[:4]}")

    # APX-01 附录标题独立起页（附录A 标题位于页面首行附近）
    apx1_ok, apx_detail = True, []
    for marker in ["附录A", "附录B"]:
        found = False
        for i, t in enumerate(pages):
            lines = [l for l in t.split("\n") if l.strip()]
            if not lines:
                continue
            for k, l in enumerate(lines[:5]):
                if l.strip().startswith(marker):
                    found = True
                    apx_detail.append(f"{marker}=p{i+1}第{k+1}行")
                    break
            if found:
                break
        if not found:
            apx1_ok = False
            apx_detail.append(f"{marker}未在页首定位")
    rep.add("APX-01 附录标题独立起页", apx1_ok, "；".join(apx_detail))

    # APX-02 附录表不跨页（附录区各表三线在单页）
    body = d.element.body
    els = list(body.iterchildren())
    app_el = None
    for p in d.paragraphs:
        if p.style.name == "Heading 1" and p.text.strip().startswith("附录A"):
            app_el = p._p
            break
    seen = False
    app_tbls = []
    for el in els:
        if el is app_el:
            seen = True
            continue
        if seen and el.tag == qn("w:tbl"):
            app_tbls.append(el)
    apx2_ok, d2 = True, []
    for tel in app_tbls:
        rows = tel.findall(qn("w:tr"))
        first = "".join(x.text or "" for x in rows[0].iter(qn("w:t")))[:12] if rows else "?"
        last_row_txt = "".join(x.text or "" for x in rows[-1].iter(qn("w:t")))[:10] if rows else ""
        def nx(x):
            return x.replace(" ", "").replace("\u3000", "").replace("\n", "")
        pg_first = pg_last = None
        for i, t in enumerate(pages):
            nt = nx(t)
            if rows and first and nx(first)[:6] and nx(first)[:6] in nt and pg_first is None:
                pg_first = i
            if last_row_txt and nx(last_row_txt)[:6] in nt:
                pg_last = i
        if pg_first is None or pg_last is None:
            apx2_ok = False
            d2.append(f"{first[:8]} 未定位")
            continue
        if pg_first != pg_last:
            header_ok = False
            for q in range(pg_first + 1, pg_last + 1):
                nt = nx(pages[q])
                if "分值" in nt and "判据描述" in nt:
                    header_ok = True
            if not header_ok:
                apx2_ok = False
            d2.append(f"{first[:8]} p{pg_first+1}~{pg_last+1}（跨页，表头重复={'是' if header_ok else '否'}）")
        else:
            d2.append(f"{first[:8]} p{pg_first+1}（单页）")
    rep.add("APX-02 附录表不跨页断裂", apx2_ok and len(app_tbls) == 3,
            "；".join(d2) if d2 else "未定位附录表")

    # ---------- TABCAP-01~08：表启动块（TABLE_START_BLOCK）+ 图注净化 ----------
    def nz(x):
        return (x or "").replace(" ", "").replace("\u3000", "").replace("\n", "")

    # 收集：数据表（题注/表头/首末行）与图题（wrapper 表内），docx 元素顺序
    tbls = []
    fig_cap_pos = []  # (cap_text, cap_after_drawing)
    for i, el in enumerate(els):
        if el.tag != qn("w:tbl"):
            continue
        if "w:drawing" in el.xml:
            ps = list(el.iter(qn("w:p")))
            draw_idx = cap_idx = None
            cap_txt = None
            for pi, p_el in enumerate(ps):
                if "w:drawing" in p_el.xml and draw_idx is None:
                    draw_idx = pi
                t = "".join(x.text or "" for x in p_el.iter(qn("w:t"))).strip()
                if t and re.match(r"^图\d+-\d+", t) and cap_idx is None:
                    cap_idx = pi
                    cap_txt = t
            if cap_txt:
                fig_cap_pos.append((cap_txt, draw_idx is not None and cap_idx is not None and cap_idx > draw_idx))
            continue
        rows = el.findall(qn("w:tr"))
        if len(rows) < 2 or len(rows[0].findall(qn("w:tc"))) < 2:
            continue
        cap_cn = cap_en = ""
        j = i - 1
        steps = 0
        while j >= 0 and steps < 4:
            if els[j].tag == qn("w:p"):
                t = "".join(x.text or "" for x in els[j].iter(qn("w:t"))).strip()
                if t.startswith("Tab.") and not cap_en:
                    cap_en = t
                elif re.match(r"^表[0-9AB]-\d+", t) and not cap_cn:
                    cap_cn = t
                    break
                elif t and not cap_cn:
                    break
            j -= 1
            steps += 1
        if not cap_cn:
            continue
        hdr_cells = ["".join(x.text or "" for x in tc.iter(qn("w:t"))) for tc in rows[0].findall(qn("w:tc"))]
        sig = nz(hdr_cells[0]) + (nz(hdr_cells[1]) if len(hdr_cells) > 1 else "")
        first_row = "".join(x.text or "" for x in rows[1].iter(qn("w:t")))
        last_row = "".join(x.text or "" for x in rows[-1].iter(qn("w:t")))
        tbls.append({"cap_cn": cap_cn, "cap_en": cap_en, "sig": sig[:10],
                     "cap_sig": nz(cap_cn)[:14],
                     "first": nz(first_row)[:14], "last": nz(last_row)[:14]})

    # TABCAP-07 图表题注顺序正确：表题在表上方 + 图题在图下方 + 编号单调递增
    order_ok, order_d = True, []
    for i, el in enumerate(els):
        if el.tag != qn("w:tbl") or "w:drawing" in el.xml:
            continue
        rows = el.findall(qn("w:tr"))
        if len(rows) < 2 or len(rows[0].findall(qn("w:tc"))) < 2:
            continue
        prev_texts = []
        j = i - 1
        while j >= 0 and len(prev_texts) < 2:
            if els[j].tag == qn("w:p"):
                t = "".join(x.text or "" for x in els[j].iter(qn("w:t"))).strip()
                if t:
                    prev_texts.append(t)
            j -= 1
        joined = "|".join(prev_texts[:2])
        if not (re.search(r"表[0-9AB]-\d+", joined) or "Tab." in joined):
            order_ok = False
            order_d.append("表题顺序异常")
    for cap_txt, after in fig_cap_pos:
        if not after:
            order_ok = False
            order_d.append(f"{cap_txt[:10]}图题未在图下")

    def cap_key(s):
        m = re.match(r"^([表图])\s*(\d+|[AB])\s*-\s*(\d+)", s)
        if not m:
            return None
        ch = m.group(2)
        major = (0, int(ch)) if ch.isdigit() else (1, ord(ch))
        return (m.group(1),) + major + (int(m.group(3)),)

    for kind, seq_caps in (("表", [t["cap_cn"] for t in tbls]), ("图", [c for c, _ in fig_cap_pos])):
        keys = [cap_key(s) for s in seq_caps]
        keys = [k for k in keys if k and k[0] == kind]
        if any(keys[k] >= keys[k + 1] for k in range(len(keys) - 1)):
            order_ok = False
            order_d.append(f"{kind}题编号顺序异常")

    pages_nz = [nz(p) for p in pages]
    seq = 0
    t1_bad, t2_bad, t3_bad, t4_bad, t5_bad, t6_bad = [], [], [], [], [], []
    detail = []
    geo = []
    for t in tbls:
        m = re.match(r"^表([0-9AB]-\d+)", t["cap_cn"])
        key = "表" + m.group(1) if m else t["cap_cn"][:4]
        en_key = "Tab." + m.group(1) if m else ""
        p_cap = None
        for q in range(seq, len(pages_nz)):
            if t["cap_sig"] in pages_nz[q] and "......" not in pages[q]:
                p_cap = q
                break
        if p_cap is None:
            for q in range(seq, len(pages_nz)):
                if nz(key) in pages_nz[q] and "......" not in pages[q]:
                    p_cap = q
                    break
        if p_cap is None:
            t1_bad.append((key, "未定位题注"))
            continue
        p_en = None
        for q in range(max(0, p_cap - 1), len(pages_nz)):
            if nz(en_key) in pages_nz[q]:
                p_en = q
                break
        p_hdr = None
        for q in range(p_cap, len(pages_nz)):
            if t["sig"] and t["sig"] in pages_nz[q]:
                p_hdr = q
                break
        p_first = p_last = None
        for q in range(p_cap, len(pages_nz)):
            if t["first"] and t["first"] in pages_nz[q] and p_first is None:
                p_first = q
            if t["last"] and t["last"] in pages_nz[q]:
                p_last = q
        if p_en is None or p_en != p_cap:
            t1_bad.append((key, f"中题p{p_cap+1}/英题p{(p_en or 0)+1}"))
        if p_hdr is None or p_en is None or p_hdr != p_en:
            t2_bad.append((key, f"英题p{(p_en or 0)+1}/表头p{(p_hdr or 0)+1}"))
        if p_hdr is None or p_first is None or p_hdr != p_first:
            t3_bad.append((key, f"表头p{(p_hdr or 0)+1}/首行p{(p_first or 0)+1}"))
        if p_hdr is None or p_hdr != p_cap:
            t4_bad.append((key, f"题注p{p_cap+1}/表头p{(p_hdr or 0)+1}"))
        if p_first is not None and p_last is not None and p_first != p_last:
            ok_hdr = all(t["sig"] in pages_nz[q] for q in range(p_first + 1, p_last + 1)) if t["sig"] else False
            if not ok_hdr:
                t6_bad.append((key, f"跨页p{p_first+1}~p{p_last+1}表头未重复"))
        rd = f"{key}:题p{p_cap+1}/英p{(p_en or 0)+1}/头p{(p_hdr or 0)+1}/首行p{(p_first or 0)+1}"
        if p_first is not None and p_last is not None and p_first != p_last:
            rd += f"/尾行p{p_last+1}"
        seq = p_cap
        detail.append(rd)
        # TABCAP-05 启动页（题注页）在题注与表头之间无大片空白
        if p_hdr == p_cap and p_en == p_cap:
            pg = doc[p_cap]
            H = pg.rect.height
            try:
                blks = [b for b in pg.get_text("blocks") if b[4].strip()]
            except Exception:
                blks = []
            en_tok = nz(en_key)
            en_blk = None
            for b in blks:
                if en_tok and en_tok in nz(b[4]):
                    en_blk = b
                    break
            nb = None
            if en_blk is not None:
                below = sorted([b for b in blks if b[1] >= en_blk[3] - 2 and b is not en_blk],
                               key=lambda b: b[1])
                below = [b for b in below if b[3] < H - 60]
                if below:
                    nb = below[0]
            if en_blk is not None and nb is not None:
                gap_cm = (nb[1] - en_blk[3]) / 28.35
                geo.append((key, gap_cm))
                if gap_cm > 2.0:
                    t5_bad.append((key, f"题注-表头空白 {gap_cm:.2f}cm"))
            else:
                geo.append((key, None))

    rep.add("TABCAP-01 表题中文与英文同页", not t1_bad,
            "；".join(detail) if not t1_bad else f"异常: {t1_bad[:6]}")
    rep.add("TABCAP-02 表题英文与表头同页", not t2_bad, "全部同页" if not t2_bad else f"{t2_bad[:6]}")
    rep.add("TABCAP-03 表头与表格首行同页", not t3_bad, "全部同页" if not t3_bad else f"{t3_bad[:6]}")
    rep.add("TABCAP-04 表题不单独留在上一页", not t4_bad, "无题注-表格跨页" if not t4_bad else f"{t4_bad[:6]}")
    gskip = [k for k, v in geo if v is None]
    gmax = max((v for _, v in geo if v is not None), default=0.0)
    rep.add("TABCAP-05 启动页无大片空白", not t5_bad,
            (f"题注-表头最大空白 {gmax:.2f}cm（阈值2.0cm）" + (f"；未测: {gskip}" if gskip else ""))
            if not t5_bad else f"{t5_bad[:6]}")
    rep.add("TABCAP-06 长表跨页必须重复表头", not t6_bad, "全部合规" if not t6_bad else f"{t6_bad[:6]}")

    rep.add("TABCAP-07 图表题注顺序正确", order_ok,
            "表题在表上方、图题在图下方、编号单调递增" if order_ok else "；".join(order_d[:4]))

    # TABCAP-08 图3-1后不再出现长重复说明（全局残留 + 图页净化）
    t8_bad = []
    for pat, tag in [(r"主轮刹车系统\s*→", "长清单残留"), (r"（图\d+-\d+[^）]{60,}", "长图注行残留")]:
        mm = re.search(pat, full)
        if mm:
            idx = full.find(mm.group(0))
            t8_bad.append((tag, full[max(0, idx - 20):idx + 40].replace("\n", " ")))
    fig31_page = None
    for q, t in enumerate(pages_nz):
        if nz("图3-1　主轮刹车系统结构分解与功能层次图")[:16] in t and "Fig.3-1" in t:
            fig31_page = q
            break
    if fig31_page is not None:
        pg = doc[fig31_page]
        H = pg.rect.height
        others = []
        for b in pg.get_text("blocks"):
            txt = b[4].strip()
            if not txt or b[1] < 65 or b[3] > H - 60:
                continue
            nt = nz(txt)
            if "图3-1" in nt and "主轮刹车系统结构分解" in nt:
                continue
            if nt.startswith("Fig.3-1"):
                continue
            others.append(nt)
        if [o for o in others if len(o) > 40] or len(others) > 2:
            t8_bad.append(("图3-1页存在多余文本", str((fig31_page + 1, others[:3]))))
    rep.add("TABCAP-08 图3-1后无长重复说明", not t8_bad,
            f"图注净化（图3-1 页 p{fig31_page + 1 if fig31_page is not None else '?'}：仅图+中英题注）"
            if not t8_bad else f"{t8_bad[:4]}")

    path = rep.save()
    print("report:", path)
    return 0 if all(ok for _, ok, _ in rep.items) else 1


if __name__ == "__main__":
    sys.exit(main())
