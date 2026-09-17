# -*- coding: utf-8 -*-
"""
pdf_qa.py — PDF 结构 QA（aeromech-thesis v1.0.0 delivery stabilization）
用法: python pdf_qa.py <project_root>
检查（以最终 PDF 为真值）: 页数/页码/TOC/Heading/Figure/Table/占位文字/
      路径泄露/模拟数据标签/待核实/引用/文本可提取/TOC-01~10
退出码: 0=通过, 1=High 级问题(FAIL), 2=Critical 级问题(FAIL), 3=环境/配置错误(非内容结论)
      （v1.5 B6 收口：找不到 PDF/缺依赖/参数错误属 ERROR，不占用内容失败码；
        交付链其余旧脚本沿用 0/1/2(severity) 语义，统一状态词表见 delivery-pipeline.md §8.1）
"""
import os
import re
import sys

CRITICAL_ISSUES, HIGH_ISSUES = [], []


def main():
    if len(sys.argv) < 2:
        print("用法: python pdf_qa.py <project_root>")
        return 3
    root = sys.argv[1]
    pdf = os.path.join(root, "毕业论文.pdf")
    if not os.path.exists(pdf):
        print(f"错误: 找不到 {pdf}")
        return 3
    try:
        import pymupdf as fitz
    except ImportError:
        print("错误: 需要 pymupdf (pip install pymupdf)")
        return 3

    doc = fitz.open(pdf)
    N = doc.page_count
    full = "".join(doc[p].get_text() for p in range(N))
    print(f"PDF 总页数: {N}")

    # ---- 页码检查（页脚单一数字；支持 前置罗马码/正文阿拉伯码 分节与封面声明无码）----
    def norm(s):
        return s.replace(" ", "").replace("\u3000", "").replace("\n", "")

    CN = {"1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六"}
    body_start = None
    # v1.6 test-8.0：正文起点=存在"行首即第X章"的页（逐行判定）。旧实现按"任意页文本
    # 含第N章"判定，会把提到"见第5章"的摘要页误判为正文起点（页码序列整体错位）。
    for pg in range(N):
        t = doc[pg].get_text()
        if "...." in t:
            continue  # 跳过目录页（含点线引导符）
        if any(re.match(r"^第[0-9一二三四五六七八九十]{1,3}章", norm(l))
               for l in t.split("\n")):
            body_start = pg
            break
    arabic_pg = 1
    for pg in range(N):
        if body_start is not None and pg < body_start:
            continue  # 前置部分（封面/声明/摘要/目录）：罗马码或无码，由结构 QA 人工复核
        page = doc[pg]
        W, H = page.rect.width, page.rect.height
        d = page.get_text("dict")
        cands = []
        for bl in d["blocks"]:
            if "lines" not in bl:
                continue
            for ln in bl["lines"]:
                y0 = ln["bbox"][1]
                if not (H - 74 < y0 < H - 56):
                    continue
                xc = (ln["bbox"][0] + ln["bbox"][2]) / 2
                if abs(xc - W / 2) > 9:
                    continue  # 页脚页码严格居中；排除表格列数字
                txt = "".join(sp["text"] for sp in ln["spans"]).strip()
                if txt.isdigit():
                    cands.append(txt)
        # PAGE 域被渲染为两层（完整行+逐字行），取最长文本为准
        digits = max(cands, key=len) if cands else ""
        if digits != str(arabic_pg):
            HIGH_ISSUES.append(f"P{pg+1} 页码异常: {digits!r} (期望 {arabic_pg})")
        arabic_pg += 1

    # ---- TOC 占位文字 ----
    if "将在 Word 中更新域后生成" in full:
        CRITICAL_ISSUES.append("目录占位文字残留")

    # ---- 路径泄露 ----
    leaks = re.findall(r"[A-Za-z]:\\Users\\(\w+)", full)
    if leaks:
        CRITICAL_ISSUES.append(f"路径泄露: {set(leaks)}")

    # ---- 模拟数据/待核实标签存在性 ----
    for tag in ["【假设/模拟·仅演示方法】", "【待核实】"]:
        if tag not in full:
            HIGH_ISSUES.append(f"缺少标签: {tag}")

    # ---- Figure+Caption 同页检查（按已知图题关键词）----
    cap_keys = ["技术路线图", "系统组成", "功能分解图", "帕累托", "风险矩阵",
                "故障树", "分布图", "敏感性分析"]
    fig_found = 0
    for pg in range(N):
        t = doc[pg].get_text()
        imgs = doc[pg].get_image_info()
        for ck in cap_keys:
            if ck in t and imgs:
                fig_found += 1
    print(f"检测到 图+题注 同页 的图块数: {fig_found}")

    # ---- Heading 存在性（章标题；兼容 阿拉伯/中文数字 两种章编号体系）----
    # v1.6 test-8.0 通用化：不假定论文章数/附录数——发现编号体系后要求从第1章起
    # 连续覆盖（≥2 章）；参考文献/致谢必备；附录按字母连续（有B必有A）。
    import re as _re
    CN_DIG = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
              "七": 7, "八": 8, "九": 9, "十": 10}
    full_norm = full.replace(" ", "").replace("\u3000", "").replace("\n", "")
    missing_heads = []

    def chapter_nums(arabic):
        nums = set()
        if arabic:
            for m in _re.finditer(r"第(\d{1,2})章", full_norm):
                nums.add(int(m.group(1)))
        else:
            for ch, n in CN_DIG.items():
                if f"第{ch}章" in full_norm:
                    nums.add(n)
        return nums

    ar, cn = chapter_nums(True), chapter_nums(False)
    if not ar and not cn:
        missing_heads.append("未检测到任何章编号（第1章/第一章）")
    else:
        best = ar if len(ar) >= len(cn) else cn
        mx = max(best)
        if mx < 2:
            missing_heads.append("章数异常（仅检出 1 章）")
        gaps = [k for k in range(1, mx + 1) if k not in best]
        if gaps:
            missing_heads.append("章编号不连续: 缺 " +
                                 ",".join(f"第{k}章" for k in gaps))
    for h in ["参考文献", "致谢"]:
        if h not in full_norm:
            missing_heads.append(h)
    for letter in "ABCDEFGH":
        cur, nxt = f"附录{letter}", f"附录{chr(ord(letter) + 1)}"
        if nxt in full_norm and cur not in full_norm:
            missing_heads.append(f"附录字母不连续：缺{cur}")
            break
    if missing_heads:
        CRITICAL_ISSUES.append(f"章节标题缺失: {missing_heads}")

    # ---- TOC 页码一致性（章节标题→实际起始页）----
    def norm(s):
        return s.replace(" ", "").replace("\u3000", "").replace("\n", "")

    toc_pages = []
    # v1.6 test-8.0：目录页扫描范围=正文起点之前的全部页（旧窗口 min(8,N) 在前置
    # 内容较多时漏检目录，"未定位目录页"误报 High）
    toc_limit = body_start if body_start is not None else N
    for pg in range(toc_limit):
        t = norm(doc[pg].get_text())
        if "目录" in t and ("第1章" in t or "第一章" in t):
            toc_pages.append(pg)
    if not toc_pages:
        HIGH_ISSUES.append("未定位目录页")
    else:
        toc_end = max(toc_pages) + 1  # 目录结束页后为正文
        # 解析目录条目页码
        toc_entries = {}
        for pg in toc_pages:
            for line in doc[pg].get_text().split("\n"):
                m = re.search(r"\.{2,}\s*(\d+)\s*$", line.strip())
                if m:
                    title = norm(line[: m.start()])
                    title = title.replace(".", "").strip()
                    if title:
                        toc_entries[title] = int(m.group(1))
        # 找每个章的正文实际起始页（兼容 阿拉伯/中文 章号）
        CN = {"1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六"}
        for k in CN:
            cands = [f"第{k}章", f"第{CN[k]}章"]
            toc_pg = None
            for tk, tp in toc_entries.items():
                if any(tk.startswith(c) for c in cands):
                    toc_pg = tp
                    break
            actual = None
            for pg in range(toc_end, N):
                for raw_line in doc[pg].get_text().split("\n"):
                    ln = norm(raw_line)
                    ok = False
                    for c in cands:
                        c0 = norm(c)
                        if ln.startswith(c0) and len(ln) < 40 and "...." not in raw_line:
                            # heading 行 = 章号后接空白再接标题；正文折行“第五章的…”无空白
                            sp = chr(32) + c + chr(32)
                            if raw_line.startswith(c + " ") or raw_line.startswith(c + chr(0x3000)) or ln == c0:
                                ok = True
                                break
                    if ok:
                        actual = pg + 1
                        break
                if actual:
                    break
            if toc_pg and actual and body_start is not None:
                actual_num = actual - body_start  # 正文页码 = 物理页 - 正文起始页(0基)
                if toc_pg != actual_num:
                    HIGH_ISSUES.append(f"TOC 页码不一致: 第{k}章 TOC={toc_pg} 实际={actual_num}")
            elif toc_pg and actual and toc_pg != actual:
                HIGH_ISSUES.append(f"TOC 页码不一致: 第{k}章 TOC={toc_pg} 实际={actual}")
        for key in ["致谢", "附录A"]:
            toc_pg = None
            for tk, tp in toc_entries.items():
                if tk.startswith(key):
                    toc_pg = tp
                    break
            actual = None
            for pg in range(toc_end, N):
                for raw_line in doc[pg].get_text().split("\n"):
                    ln = norm(raw_line)
                    if ln.startswith(key) and "...." not in raw_line and len(ln) < 40:
                        actual = pg + 1
                        break
                if actual:
                    break
            if toc_pg and actual and body_start is not None:
                actual_num = actual - body_start
                if toc_pg != actual_num:
                    HIGH_ISSUES.append(f"TOC 页码不一致: {key} TOC={toc_pg} 实际={actual_num}")
            elif toc_pg and actual and toc_pg != actual:
                HIGH_ISSUES.append(f"TOC 页码不一致: {key} TOC={toc_pg} 实际={actual}")

    # ---- Abstract QA（ABSTRACT-01~04；兼容 ABSTRACT/Abstract 大小写与 KEY WORDS/Keywords）----
    abstract_pg = None
    for pg in range(min(8, N)):
        t = doc[pg].get_text()
        if re.search(r"^\s*(ABSTRACT|Abstract)\s*$", t, re.M):
            abstract_pg = pg
            break
    if abstract_pg is None:
        HIGH_ISSUES.append("ABSTRACT-01: 未找到 ABSTRACT 标题")
    else:
        lines_on_pg = [l for l in doc[abstract_pg].get_text().split("\n")
                       if l.strip() and not l.strip().isdigit()]
        if len(lines_on_pg) < 4:
            HIGH_ISSUES.append(f"ABSTRACT-01: ABSTRACT 标题页异常孤立 (P{abstract_pg+1})")
        kw = re.search(r"KEY\s*WORDS|Keywords", doc[abstract_pg].get_text())
        if not kw:
            HIGH_ISSUES.append(f"ABSTRACT-02/03: ABSTRACT 可能跨页 (P{abstract_pg+1} 无 KEY WORDS)，需人工判定断裂点")
        else:
            for pg in range(abstract_pg, min(abstract_pg + 3, N)):
                if re.search(r"KEY\s*WORDS|Keywords", doc[pg].get_text()):
                    klines = [l for l in doc[pg].get_text().split("\n") if l.strip()]
                    if len(klines) < 4:
                        HIGH_ISSUES.append(f"ABSTRACT-04: KEY WORDS 所在页异常孤立 (P{pg+1})")
                    break

    doc.close()

    # ---- 报告 ----
    print("\n=== PDF QA 结果 ===")
    print(f"Critical: {len(CRITICAL_ISSUES)} | High: {len(HIGH_ISSUES)}")
    for i in CRITICAL_ISSUES:
        print("  [Critical]", i)
    for i in HIGH_ISSUES:
        print("  [High]", i)
    if CRITICAL_ISSUES:
        print("结论: FAIL (Critical)")
        return 2
    if HIGH_ISSUES:
        print("结论: FAIL (High)")
        return 1
    print("结论: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
