# -*- coding: utf-8 -*-
"""
update_toc.py — 更新 DOCX 原生 TOC 域（aeromech-thesis v1.0.0）
用法: python update_toc.py <project_root>
流程: 打开 DOCX → 两轮 TablesOfContents.Update + Repaginate → 保存
退出码: 0=成功, 1=无 TOC 域或失败
"""
import os
import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python update_toc.py <project_root>")
        return 1
    root = sys.argv[1]
    docx_path = os.path.join(root, "毕业论文.docx")
    if not os.path.exists(docx_path):
        print(f"错误: 找不到 {docx_path}")
        return 1

    try:
        import win32com.client
    except ImportError:
        print("错误: 需要 pywin32 (pip install pywin32)")
        return 1

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = word.Documents.Open(os.path.abspath(docx_path))
    try:
        if doc.TablesOfContents.Count == 0:
            print("警告: 文档中没有 TOC 域，跳过更新")
            doc.Close(False)
            return 1
        # 两轮更新：第一轮建目录，第二轮按新页码重算
        for i in range(2):
            doc.Repaginate()
            doc.TablesOfContents(1).Update()
            try:
                doc.Fields.Update()
            except Exception:
                pass
            doc.Repaginate()
            print(f"第 {i+1} 轮 TOC 更新完成")
        doc.Save()
        print("DOCX 已保存:", docx_path)
        return 0
    finally:
        doc.Close(False)
        word.Quit()


if __name__ == "__main__":
    sys.exit(main())
