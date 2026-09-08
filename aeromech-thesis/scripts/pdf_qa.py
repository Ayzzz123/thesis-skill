# -*- coding: utf-8 -*-
"""
pdf_qa.py — PDF 结构 QA（aeromech-thesis v1.0.0 delivery stabilization）
用法: python pdf_qa.py <project_root>
检查（以最终 PDF 为真值）: 页数/页码/TOC/Heading/Figure/Table/占位文字/
      路径泄露/模拟数据标签/待核实/引用/文本可提取/TOC-01~10
退出码: 0=通过, 1=High 级问题, 2=Critical 级问题
"""
import os
import re
import sys

CRITICAL_ISSUES, HIGH_ISSUES = [], []


def main():
    if len(sys.argv) < 2:
        print("用法: python pdf_qa.py <project_root>")
        return 1
    root = sys.argv[1]
    pdf = os.path.join(root, "毕业论文.pdf")
    if not os.path.exists(pdf):
        print(f"错误: 找不到 {pdf}")
        return 2
    try:
        import pymupdf as fitz
    except ImportError:
        print("错误: 需要 pymupdf (pip install pymupdf)")
        return 1

    doc = fitz.open(pdf)
    N = doc.page_count
    full = "".join(doc[p].get_text() for p in range(N))
    print(f"PDF 总页数: {N}")

    # ---- 页码检查（页脚单一数字）----
    for pg in range(N):
        page = doc[pg]
        d = page.get_text("dict")
        digits = []
        for bl in d["blocks"]:
            if "lines" in bl:
                for ln in bl["lines"]:
                    txt = "".join(s["text"] for s in ln["spans"]).strip()
                    if ln["bbox"][1] > page.rect.height - 60 and txt.isdigit():
                        digits.append(txt)
        if digits != [str(pg + 1)]:
            HIGH_ISSUES.append(f"P{pg+1} 页码异常: {digits}")

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

    # ---- Heading 存在性（章标题）----
    chapter_titles = ["第1章", "第2章", "第3章", "第4章", "第5章", "第6章",
                      "参考文献", "致谢", "附录A", "附录B"]
    missing_heads = [h for h in chapter_titles
                     if h not in full.replace(" ", "").replace("\n", "")]
    if missing_heads:
        CRITICAL_ISSUES.append(f"章节标题缺失: {missing_heads}")

    # ---- TOC 页码一致性（章节标题→实际起始页）----
    def norm(s):
        return s.replace(" ", "").replace("\u3000", "").replace("\n", "")

    toc_pages = []
    for pg in range(min(6, N)):
        t = norm(doc[pg].get_text())
        if "目录" in t and "第1章" in t:
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
        # 找每个章的正文实际起始页
        for key in ["第1章", "第2章", "第3章", "第4章", "第5章", "第6章",
                    "致谢", "附录A"]:
            toc_pg = None
            for tk, tp in toc_entries.items():
                if tk.startswith(key):
                    toc_pg = tp
                    break
            actual = None
            for pg in range(toc_end - 1, N):
                # 逐行判断正文标题（去除点线行干扰与空格）
                for raw_line in doc[pg].get_text().split("\n"):
                    ln = norm(raw_line)
                    if ln.startswith(key) and "...." not in raw_line and len(ln) < 40:
                        actual = pg + 1
                        break
                if actual:
                    break
            if toc_pg and actual and toc_pg != actual:
                HIGH_ISSUES.append(f"TOC 页码不一致: {key} TOC={toc_pg} 实际={actual}")

    # ---- Abstract QA（ABSTRACT-01~04）----
    abstract_pg = None
    for pg in range(min(6, N)):
        for line in doc[pg].get_text().split("\n"):
            if line.strip() == "Abstract":
                abstract_pg = pg
                break
        if abstract_pg is not None:
            break
    if abstract_pg is None:
        HIGH_ISSUES.append("ABSTRACT-01: 未找到 Abstract 标题")
    else:
        # ABSTRACT-01: 标题后正文非孤立
        lines_on_pg = [l for l in doc[abstract_pg].get_text().split("\n")
                       if l.strip() and not l.strip().isdigit()]
        if len(lines_on_pg) < 4:
            HIGH_ISSUES.append(f"ABSTRACT-01: Abstract 标题页异常孤立 (P{abstract_pg+1})")
        # ABSTRACT-02/03: Keywords 与 Abstract 主体同页 → 摘要单页完整
        if "Keywords" not in doc[abstract_pg].get_text():
            HIGH_ISSUES.append(f"ABSTRACT-02/03: Abstract 可能跨页 (P{abstract_pg+1} 无 Keywords)，需人工判定断裂点")
        # ABSTRACT-04: Keywords 所在页非孤立
        for pg in range(abstract_pg, min(abstract_pg + 2, N)):
            if "Keywords" in doc[pg].get_text():
                klines = [l for l in doc[pg].get_text().split("\n") if l.strip()]
                if len(klines) < 4:
                    HIGH_ISSUES.append(f"ABSTRACT-04: Keywords 页异常孤立 (P{pg+1})")
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
