# -*- coding: utf-8 -*-
"""repaginate_tables.py — TABLE_START_BLOCK 硬校验与强制分页（aeromech-thesis v1.3.5）

用途：在 update_toc 之后、export_pdf 之前运行。用 Word COM 实测每张数据表的
  题注页 / 表头页 / 首行页；若"中文题+英文题+表头+首行"未同页（Word keep 链失效），
  在题注前插入硬分页并重新分页至收敛（≤3 轮）。长表跨页表头重复（Rows(1).HeadingFormat）
  一并校验与修复。

用法: python repaginate_tables.py <project_root>
退出码: 0=全部绑定, 1=仍有未绑定表, 2=环境错误
"""
import os
import re
import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python repaginate_tables.py <project_root>")
        return 2
    root = os.path.abspath(sys.argv[1])
    docx_path = os.path.join(root, "毕业论文.docx")
    if not os.path.exists(docx_path):
        print(f"错误: 找不到 {docx_path}")
        return 2
    try:
        import win32com.client as win32
        import pythoncom
    except ImportError:
        print("错误: 需要 pywin32")
        return 2

    WD_PAGE = 3        # wdActiveEndPageNumber
    WD_BREAK_PAGE = 7  # wdPageBreak
    CAP = re.compile(r"^表((?:\d+|[AB])-\d+)")

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(docx_path, ReadOnly=False)

        modified = False
        final_rows = []
        for rnd in range(3):
            doc.Repaginate()
            caps = []
            for p in doc.Paragraphs:
                t = p.Range.Text.strip()
                m = CAP.match(t)
                if m:
                    caps.append({"key": "表" + m.group(1), "start": p.Range.Start,
                                 "page": p.Range.Information(WD_PAGE), "para": p})
            issues = []
            final_rows = []
            for tb in doc.Tables:
                if tb.Rows.Count < 2:
                    continue
                start = tb.Range.Start
                cap = None
                for c in caps:
                    if c["start"] < start:
                        cap = c
                    else:
                        break
                if cap is None:
                    continue
                hdr_page = tb.Rows(1).Range.Information(WD_PAGE)
                first_page = tb.Rows(2).Range.Information(WD_PAGE)
                last_page = tb.Rows(tb.Rows.Count).Range.Information(WD_PAGE)
                if not tb.Rows(1).HeadingFormat:
                    tb.Rows(1).HeadingFormat = True
                    modified = True
                final_rows.append((cap["key"], cap["page"], hdr_page, first_page, last_page))
                if cap["page"] != hdr_page or hdr_page != first_page:
                    issues.append(cap)
            if not issues:
                print(f"[repaginate] 第{rnd + 1}轮: 全部表 题注=表头=首行 同页")
                break
            print(f"[repaginate] 第{rnd + 1}轮: {len(issues)} 张表未绑定，插入硬分页: "
                  + ", ".join(c['key'] for c in issues))
            for c in issues:
                rng = c["para"].Range
                rng.Collapse(1)
                rng.InsertBreak(WD_BREAK_PAGE)
            modified = True

        remaining = [r for r in final_rows if not (r[1] == r[2] == r[3])]
        if modified:
            doc.Save()
        doc.Close(0)

        out_dir = os.path.join(root, ".aeromech", "artifacts", "qa", "repaginate")
        os.makedirs(out_dir, exist_ok=True)
        rep = os.path.join(out_dir, "repaginate-report.md")
        with open(rep, "w", encoding="utf-8") as f:
            f.write("# TABLE_START_BLOCK 硬校验（Word COM 实测）\n\n")
            for key, cp, hp, fp, lp in final_rows:
                span = f"{fp}~{lp}" if fp != lp else f"{fp}"
                f.write(f"- {key}: 题注p{cp} / 表头p{hp} / 首行p{fp}（表体 {span}）\n")
            f.write("\n结果: " + ("ALL PASS" if not remaining
                                  else "FAIL: " + ", ".join(r[0] for r in remaining)) + "\n")
        print("report:", rep)
        print("结果:", "PASS" if not remaining else f"FAIL {len(remaining)}")
        return 0 if not remaining else 1
    finally:
        try:
            if word is not None:
                word.Quit(0)
        except Exception:
            pass
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
