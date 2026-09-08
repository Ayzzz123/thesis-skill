# -*- coding: utf-8 -*-
"""
export_pdf.py — DOCX → PDF 导出（aeromech-thesis v1.0.0）
用法: python export_pdf.py <project_root>
实现: docx2pdf（Microsoft Word COM），输出 <project_root>/毕业论文.pdf
退出码: 0=成功, 1=失败
"""
import os
import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python export_pdf.py <project_root>")
        return 1
    root = sys.argv[1]
    docx_path = os.path.join(root, "毕业论文.docx")
    pdf_path = os.path.join(root, "毕业论文.pdf")
    if not os.path.exists(docx_path):
        print(f"错误: 找不到 {docx_path}")
        return 1
    try:
        from docx2pdf import convert
    except ImportError:
        print("错误: 需要 docx2pdf (pip install docx2pdf)")
        return 1
    try:
        convert(docx_path, pdf_path)
    except Exception as e:
        print(f"PDF 导出失败: {e}")
        return 1
    if os.path.exists(pdf_path):
        print("PDF 已生成:", pdf_path)
        return 0
    print("错误: PDF 未生成")
    return 1


if __name__ == "__main__":
    sys.exit(main())
