# -*- coding: utf-8 -*-
"""finalize_metadata.py — 交付前元数据中性化（aeromech-thesis 通用工具）
清除 DOCX/PDF 文档属性中的工具痕迹（python-docx 等）与系统用户名（隐私/污染）。
用法: python finalize_metadata.py <project_root>
执行顺序：必须在 export_pdf 之后（Word 保存会重写 lastModifiedBy）。
退出码: 0=成功
"""
import os
import re
import shutil
import sys
import zipfile


def clean_docx(path):
    tmp = path + ".tmp"
    zin = zipfile.ZipFile(path, "r")
    zout = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "docProps/core.xml":
            t = data.decode("utf-8")
            t = re.sub(r"<dc:creator>.*?</dc:creator>", "<dc:creator></dc:creator>", t, flags=re.S)
            t = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", t, flags=re.S)
            t = re.sub(r"<dc:description>.*?</dc:description>", "<dc:description></dc:description>", t, flags=re.S)
            data = t.encode("utf-8")
        elif item.filename == "docProps/app.xml":
            t = data.decode("utf-8")
            t = re.sub(r"<Company>.*?</Company>", "<Company></Company>", t, flags=re.S)
            data = t.encode("utf-8")
        zout.writestr(item, data)
    zin.close()
    zout.close()
    shutil.move(tmp, path)


def clean_pdf(path):
    import pymupdf
    doc = pymupdf.open(path)
    doc.set_metadata({
        "title": "", "author": "", "subject": "", "keywords": "",
        "creator": "", "producer": "", "creationDate": "", "modDate": "",
    })
    tmp = path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    shutil.move(tmp, path)


def main():
    if len(sys.argv) < 2:
        print("用法: python finalize_metadata.py <project_root>")
        return 2
    root = sys.argv[1]
    docx = os.path.join(root, "毕业论文.docx")
    pdf = os.path.join(root, "毕业论文.pdf")
    if os.path.exists(docx):
        clean_docx(docx)
        print("DOCX metadata cleaned:", docx)
    if os.path.exists(pdf):
        clean_pdf(pdf)
        print("PDF metadata cleaned:", pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
