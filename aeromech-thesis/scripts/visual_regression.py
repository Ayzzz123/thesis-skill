# -*- coding: utf-8 -*-
"""
visual_regression.py — PDF 视觉回归（aeromech-thesis v1.0.0）
用法: python visual_regression.py <project_root> [--render-dir tmp]
对每页计算内容占用率（排除页脚），标注 <40% 低占用并分类原因。
退出码: 0=无异常或仅有 B 类内容型低占用, 1=发现 A 类布局异常
"""
import os
import sys

EXEMPT = {0, 3}  # 封面(1)、目录(4) 等特殊页索引，可扩展


def main():
    if len(sys.argv) < 2:
        print("用法: python visual_regression.py <project_root>")
        return 1
    root = sys.argv[1]
    pdf = os.path.join(root, "毕业论文.pdf")
    if not os.path.exists(pdf):
        print(f"错误: 找不到 {pdf}")
        return 1
    try:
        import pymupdf as fitz
    except ImportError:
        print("错误: 需要 pymupdf")
        return 1

    doc = fitz.open(pdf)
    N = doc.page_count

    def is_chapter_start_pg(pg):
        """下一页(索引 pg)是否以 H1 类标题起始（去空格匹配，兼容 阿拉伯/中文 章号与隔空标题）。"""
        if pg >= N:
            return False
        t = doc[pg].get_text().replace(" ", "").replace("\u3000", "")
        heads = ["第1章", "第2章", "第3章", "第4章", "第5章", "第6章",
                 "第一章", "第二章", "第三章", "第四章", "第五章", "第六章",
                 "参考文献", "致谢", "附录A", "附录B", "目录", "摘要", "Abstract",
                 "ABSTRACT"]
        return any(h.replace(" ", "") in t[:200] for h in heads)

    issues = []       # A 类候选（布局异常，需修复/人工复核）
    b_type = []       # B 类豁免（章节自然结束等）
    print(f"=== 视觉回归: {N} 页 ===")
    for pg in range(N):
        page = doc[pg]
        H = page.rect.height
        body_bottom = H - 50
        ymin, ymax = H, 0
        d = page.get_text("dict")
        for bl in d["blocks"]:
            if "lines" in bl:
                for ln in bl["lines"]:
                    y0 = ln["bbox"][1]
                    if y0 < body_bottom:
                        ymin = min(ymin, y0)
                        ymax = max(ymax, min(ln["bbox"][3], body_bottom))
        for img in page.get_image_info():
            b = img["bbox"]
            if b[1] < body_bottom:
                ymin = min(ymin, b[1])
                ymax = max(ymax, min(b[3], body_bottom))
        usable = body_bottom - 55
        ratio = (ymax - ymin) / usable * 100 if ymax > ymin else 0
        tag = ""
        if ratio < 40:
            tag = "LOW"
        elif ratio > 90:
            tag = "HIGH"
        if pg in EXEMPT and tag:
            tag += " (exempt)"
        # B 类判定：低占用页 → 若下一/后页为章节起始，判章节自然结束
        if tag.startswith("LOW") and pg not in EXEMPT:
            if is_chapter_start_pg(pg + 1) or is_chapter_start_pg(pg):
                b_type.append((pg + 1, ratio))
                tag += " [B类:章节自然结束]"
            else:
                issues.append((pg + 1, ratio, "A类候选: 低占用且后页非章节起始，需人工复核"))
                tag += " [A类候选]"
        print(f"  P{pg+1}: {ratio:.0f}% {tag}")
    doc.close()
    print("\n=== 结果 ===")
    print(f"B 类豁免页: {[p for p, _ in b_type]}")
    if issues:
        for p, r, why in issues:
            print(f"  P{p}: {r:.0f}% -> {why}")
        print("结论: 存在 A 类候选低占用页")
        return 1
    print("结论: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
