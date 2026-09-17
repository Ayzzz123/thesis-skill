# -*- coding: utf-8 -*-
"""test_material_ingestion.py — 统一材料进入流程（v1.6 §八）

覆盖：positive（扫描/注册/去重不重复读取）/ negative（篡改=changed、重复内容拒注、未知类型/等级）/
boundary（school 目录内类型细分、旧结构兼容、缺失登记）/ check 门禁语义。
运行：python tests/v1_6/test_material_ingestion.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import material_ingestion as MI

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
    tmp = tempfile.mkdtemp(prefix="mi_v16_")
    print("== test_material_ingestion ==")

    # ---------- positive ----------
    root = F.make_project(os.path.join(tmp, "pos"), with_template=True,
                          with_pdf_spec=True)
    F.write_text(root, "materials/project_data/faults.csv", "a,b\n1,2\n")
    un, new, ch, miss, legacy = MI.classify(root)
    check("positive 三类目录各 1+ 未登记", len(new) >= 3, str([d["rel"] for d in new]))
    types = {d["rel"].split("/")[1]: d["inferred_type"] for d in new}
    check("positive 目录→类型推断", types.get("project_data") == "project_data"
          and types.get("school") in ("school_template", "school_notice", "task_book"))
    added, warn, *_ = MI.register(root, all_new=True, notes="冷启动注册")
    check("positive --all 全注册且带 sha256", len(added) == len(new)
          and all(str(e["hash_or_identifier"]).startswith("sha256:") for e in added))
    reg = MI.load_materials(root)
    check("positive 登记 schema 字段（state.md §16.1）",
          all({"material_id", "filename", "availability", "type", "authority",
               "hash_or_identifier", "verification_status"} <= set(e) for e in reg))
    check("positive 注册后 verification=pending（诚实待确认）",
          all(e["verification_status"] == "pending" for e in reg))
    # 去重：已登记且未变更 → 不再列 new（不得重复读取）
    _, new2, *_ = MI.classify(root)
    check("positive 重复扫描 0 新增（不重复读取）", new2 == [])
    lines, consistent = MI.report(root)
    check("positive check 一致→True", consistent)
    # 同内容新文件 → 哈希去重：classify 归入 unchanged（不重复登记、不重复读取）；
    # 显式 --add 同哈希文件 → 警告不注册
    dup = os.path.join(root, "materials", "literature")
    os.makedirs(dup, exist_ok=True)
    src = os.path.join(root, "materials", "project_data", "faults.csv")
    shutil.copy(src, os.path.join(dup, "faults_copy.csv"))
    un2, new2b, *_ = MI.classify(root)
    check("boundary 同哈希内容不列 new（去重）",
          not any("faults_copy" in d["rel"] for d in new2b)
          and any("faults_copy" in d["rel"] and d.get("material_id") for d in un2))
    a_dup, w_dup, *_ = MI.register(root, add=["materials/literature/faults_copy.csv:literature_pdf:user_provided"])
    check("boundary 显式 --add 同哈希→警告不注册", a_dup == [] and any("重复" in w for w in w_dup))
    os.remove(os.path.join(dup, "faults_copy.csv"))

    # ---------- negative ----------
    F.write_text(root, "materials/school/本科毕业论文模板.docx", "TAMPERED")
    _, _, ch3, _, _ = MI.classify(root)
    check("negative 篡改→changed 且指向原 MAT",
          any("模板" in d["rel"] and d.get("material_id") for d in ch3), str(ch3))
    lines, consistent = MI.report(root)
    check("negative changed → check 不一致", not consistent)
    # 登记条目指向不存在文件 → missing
    e = MI.load_materials(root)[0]
    reg2 = MI.load_materials(root)
    reg2[0] = dict(e, filename="materials/does_not_exist.pdf",
                   hash_or_identifier="sha256:" + "0" * 64)
    MI.save_materials(root, reg2)
    _, _, _, miss2, _ = MI.classify(root)
    check("negative 登记文件缺失→missing 报告", len(miss2) == 1)
    # 未知类型/等级：--add 显式指定 → 警告不落盘
    F.write_text(root, "materials/standard/GB_T_xxx.txt", "std\n")
    a3, w3, *_ = MI.register(root, add=["materials/standard/GB_T_xxx.txt:fake_type:school"])
    check("negative 未知类型拒绝注册", a3 == [] and any("未知类型" in w for w in w3))
    a4, w4, *_ = MI.register(root, add=["materials/standard/GB_T_xxx.txt:standard_doc:alien"])
    check("negative 未知来源等级拒绝注册", a4 == [] and any("来源等级" in w for w in w4))
    a5, w5, *_ = MI.register(root, add=["materials/standard/nope.pdf:standard_doc:school"])
    check("negative 磁盘无此文件→警告", a5 == [] and any("磁盘无" in w for w in w5))
    # 显式 --add 正常路径
    a6, *_ = MI.register(root, add=["materials/standard/GB_T_xxx.txt:standard_doc:public_verified"])
    check("positive 显式 --add 注册成功（类型/等级指定）",
          len(a6) == 1 and a6[0]["type"] == "standard_doc" and a6[0]["authority"] == "public_verified")
    # 损坏 materials.yaml → ERROR 不静默
    open(os.path.join(root, ".aeromech", "materials.yaml"), "w", encoding="utf-8").write("materials: [broken\n")
    try:
        MI.classify(root)
        check("negative materials.yaml 损坏→RuntimeError（不静默当空表）", False)
    except RuntimeError:
        check("negative materials.yaml 损坏→RuntimeError（不静默当空表）", True)

    # ---------- boundary：类型细分 + 旧结构 ----------
    root4 = F.make_project(os.path.join(tmp, "names"))
    for fn, want in (("本科毕业论文模板（自然科学）.docx", "school_template"),
                     ("毕业设计任务书.pdf", "task_book"),
                     ("开题报告要求.docx", "proposal"),
                     ("关于规范论文格式的通知.pdf", "school_notice")):
        F.write_text(root4, "materials/school/" + fn, "x\n")
        got = [d["inferred_type"] for d in MI.scan_disk(root4) if d["filename"] == fn]
        check(f"boundary school 文件名细分 {fn[:12]}…", got == [want], str(got))
    root5 = F.make_project(os.path.join(tmp, "legacy"), with_template=False)
    F.write_text(root5, ".aeromech/materials/school/旧模板.docx", "x\n")
    _, new5, _, _, legacy5 = MI.classify(root5)
    check("boundary 旧结构 .aeromech/materials/ 兼容扫描",
          len(new5) == 1 and new5[0]["rel"].startswith(".aeromech/materials/")
          and new5[0]["inferred_type"] == "school_template")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_material_ingestion 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
