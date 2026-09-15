# -*- coding: utf-8 -*-
"""test_school_context.py — School Requirement Context 解析器（v1.6 §九）

核心纪律：字段级 provenance ∈ official/sample/default/unknown；
样文不得冒充正式要求；PDF/扫描件不猜测（保持 unknown）；合并写入不破坏 §16.2 既有键。
运行：python tests/v1_6/test_school_context.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import school_requirements as SR

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def main():
    tmp = tempfile.mkdtemp(prefix="sr_v16_")
    print("== test_school_context ==")

    # ---------- positive：模板在场 ----------
    root = F.make_project(os.path.join(tmp, "pos"), with_template=True)
    fields, meta, conflicts = SR.parse(root)
    check("positive 模板边距 official", fields["margins"]["provenance"] == "official"
          and fields["margins"]["value"]["left_cm"] == 3.0)
    check("positive page_size 提取", fields["page_size"]["value"]["width_cm"] == 21.0)
    check("positive 正文字号 official（12pt）", fields["font_size_body"]["value"] == 12.0)
    check("positive 标题层级提取", fields["heading_format"]["value"]["level1"]["size_pt"] == 16.0)
    check("positive 模板在场→format_source=school_template", meta["format_source"] == "school_template")
    check("positive docx_mode=template_fidelity", meta["docx_mode"] == "template_fidelity")
    check("positive 未提取字段保持 unknown（不乱填）",
          fields["abstract"]["provenance"] == "unknown" and fields["abstract"]["value"] is None
          and fields["reference"]["provenance"] == "unknown")
    p = SR.write_school_format(root, fields, meta, conflicts)
    import yaml
    data = yaml.safe_load(open(p, encoding="utf-8"))
    check("positive 写入 school_requirement（additive 字段）",
          "school_requirement" in data and "general_principles" in data)
    check("positive format_source/format_status 更新",
          data["format_source"] == "school_template" and data["format_status"] in ("partial", "complete"))
    check("positive 逐字段 source_material 溯源",
          data["school_requirement"]["fields"]["margins"]["source_material"].endswith("模板.docx"))

    # ---------- 既有键合并保留 ----------
    data["general_defaults"] = {"font_body": "宋体"}     # 模拟旧文件既有键
    data["custom_section"] = {"x": 1}
    yaml.safe_dump(data, open(p, "w", encoding="utf-8"), allow_unicode=True)
    SR.write_school_format(root, fields, meta, conflicts)
    d2 = yaml.safe_load(open(p, encoding="utf-8"))
    check("boundary 合并不破坏既有键（§16.2 兼容）",
          d2.get("general_defaults", {}).get("font_body") == "宋体" and d2.get("custom_section") == {"x": 1})

    # ---------- 样文不得冒充 official ----------
    root2 = F.make_project(os.path.join(tmp, "sample"), with_template=False, with_samples=True)
    f2, m2, c2 = SR.parse(root2)
    check("硬规则 无模板仅有样文→字段全部 sample（不冒充 official）",
          f2["margins"]["provenance"] == "sample" and m2["format_source"] == "sample_thesis")
    # 模板+样文：样文不覆盖模板字段（同级/高级冲突记录）
    root3 = F.make_project(os.path.join(tmp, "both"), with_template=True, with_samples=True)
    f3, m3, c3 = SR.parse(root3)
    check("硬规则 样文不覆盖 official 值", f3["margins"]["value"]["left_cm"] == 3.0
          and f3["margins"]["provenance"] == "official")

    # ---------- PDF 规范：不猜测 ----------
    root4 = F.make_project(os.path.join(tmp, "pdf"), with_template=False, with_pdf_spec=True)
    f4, m4, c4 = SR.parse(root4)
    unknown_cnt = sum(1 for k in SR.FIELD_KEYS if f4[k]["provenance"] == "unknown")
    check("硬规则 PDF 规范不猜字段（全 unknown）", unknown_cnt == len(SR.FIELD_KEYS))
    check("positive PDF 规范登记为来源+备注", "格式要求.pdf" in str(f4.get("_notes"))
          or "格式要求.pdf" in str(f4.get("_official_spec_documents")))

    # ---------- 空项目：general_default/missing ----------
    root5 = F.make_project(os.path.join(tmp, "empty"), with_template=False)
    f5, m5, _ = SR.parse(root5)
    check("boundary 无学校材料→general_default + missing（不阻塞）",
          m5["format_source"] == "general_default" and m5["format_status"] == "missing"
          and m5["docx_mode"] == "format_reconstruction")
    # 全部字段可提取性 = 指令字段清单覆盖（提取不到的以 unknown 显式存在）
    check("positive 覆盖指令 §九 字段清单", set(SR.FIELD_KEYS) >= {
        "page_size", "margins", "font_body", "font_size_body", "heading_format",
        "abstract", "reference", "figure", "table", "page_number", "sections", "special"},
        str(SR.FIELD_KEYS))

    # ---------- CLI 冒烟 ----------
    rc = SR.main([root, "parse", "--json"])
    check("positive CLI parse rc∈{0,1}（无冲突=0）", rc == 0, f"rc={rc}")
    rc2 = SR.main([root5, "parse", "--json"])
    check("positive CLI 空项目也成功（全 unknown 合法）", rc2 == 0)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_school_context 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
