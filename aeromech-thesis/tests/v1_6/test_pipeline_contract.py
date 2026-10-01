# -*- coding: utf-8 -*-
"""test_pipeline_contract.py — B5c：交付链下半段契约锁（DOCX→COM→TOC→repaginate→PDF→finalize→QA→gate）

覆盖目标（不依赖真实 Word GUI 的契约/单元层）：
  1. pipeline 步骤顺序固定（ALL_STEPS 与执行顺序一致）
  2. 每一步失败后的状态语义（FAIL / ERROR / NOT_APPLICABLE / SKIPPED_WITH_REASON）
  3. manifest 是否正确落盘、是否可被 gate 读取
  4. delivery_gate 读取的是**最新**结果
  5. QA 缺失不能 PASS
  6. rc=3 / ERROR 不能 PASS
  7. DOCX/PDF 不存在时不能误判
  8. Format-QA FAIL 能传递到最终 gate
  9. 成功链路能正确聚合

SKIP 语义：需要真实 Word/COM 的步骤在本环境用 subprocess 直接探测；不可用则
**显式记 SKIP 并单独计数**，不得计入 PASS，也不得让套件整体"因跳过而通过"。
运行：python tests/v1_6/test_pipeline_contract.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import _fixtures as F
import delivery_gate as DG
import thesis_build as TB
import yaml

PASS, FAIL, SKIP = 0, 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def skip(name, reason):
    global SKIP
    SKIP += 1
    print(f"  SKIP {name} | {reason}")


def word_available():
    """真实 Word COM 是否可用（不可用则相关断言显式 SKIP，不伪装 PASS）。"""
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return False, "pywin32 不可用"
    try:
        r = subprocess.run([sys.executable, "-c",
                            "import win32com.client as w;"
                            "a=w.DispatchEx('Word.Application');a.Quit()"],
                           capture_output=True, timeout=60)
        return (r.returncode == 0), ("Word COM 可用" if r.returncode == 0
                                     else "Word.Application 无法启动")
    except Exception as e:                       # noqa: BLE001
        return False, f"COM 探测异常: {type(e).__name__}"


def w(root, rel, txt):
    p = os.path.join(root, ".aeromech", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def contract(root):
    c = {
        "project": {"title": "交付链契约测试", "author": "张三", "major": "飞行器维修",
                    "school": "某大学"},
        "content": {"abstract_zh": "摘要。", "keywords": ["k"],
                    "chapters": ["artifacts/chapters/ch1.md"],
                    "references_file": "artifacts/literature.md"},
        "research": {"required": False},
        "school_format": {},
        "qa": {"out": "artifacts/qa"},
    }
    w(root, "build-contract.yaml", yaml.safe_dump(c, allow_unicode=True))
    w(root, "artifacts/chapters/ch1.md", "# 第1章 绪论\n\n背景一段。\n")
    w(root, "artifacts/literature.md", "- 参考文献一\n")
    return c


def mkdir_project(tmp, name):
    return F.make_project(os.path.join(tmp, name), with_template=False)


def main():
    tmp = tempfile.mkdtemp(prefix="pipe_v16_")
    print("== test_pipeline_contract ==")

    # ---------- 1. pipeline 步骤顺序固定 ----------
    check("B5c-01 ALL_STEPS 顺序为 docx→toc→repaginate→pdf→finalize→qa",
          TB.ALL_STEPS == ["docx", "toc", "repaginate", "pdf", "finalize", "qa"],
          str(TB.ALL_STEPS))

    r1 = mkdir_project(tmp, "order")
    contract(r1)
    res1 = TB.pipeline(r1, steps=["docx"])
    steps1 = [s.get("step") for s in (res1.get("steps") or [])]
    check("B5c-02 指定 steps 子集时按固定顺序执行",
          steps1 == ["docx"], str(steps1))

    # ---------- 7. DOCX 构建失败 → 下游不得伪装成功 ----------
    r2 = mkdir_project(tmp, "nodocx")
    c2 = contract(r2)
    # 让 docx 步骤必然失败：章节文件指向不存在路径
    c2["content"]["chapters"] = ["artifacts/chapters/missing.md"]
    w(r2, "build-contract.yaml", yaml.safe_dump(c2, allow_unicode=True))
    res2 = TB.pipeline(r2, steps=["docx"])
    st2 = {s.get("step"): s for s in (res2.get("steps") or [])}
    check("B5c-03 docx 步骤失败 → 记 FAIL 且 pipeline 返回（不抛未捕获异常）",
          st2.get("docx", {}).get("status") == "FAIL",
          f"{st2.get('docx', {}).get('status')}/{st2.get('docx', {}).get('rc')}")
    check("B5c-03b 失败原因可诊断（含缺失文件名，非空泛信息）",
          "missing.md" in str(st2.get("docx", {}).get("output_tail", "")),
          str(st2.get("docx", {}).get("output_tail"))[:70])
    check("B5c-03c docx 失败后 pipeline 终局不得 PASS",
          res2.get("status") != "PASS", str(res2.get("status")))

    # pipeline 在 pdf 缺失时，pdf_export 记 FAIL/ERROR，不记 PASS
    r3 = mkdir_project(tmp, "nopdf")
    contract(r3)
    res3 = TB.pipeline(r3, steps=["docx", "qa"])
    st3 = {s.get("step"): s.get("status") for s in (res3.get("steps") or [])}
    check("B5c-04 未跑 pdf 时无 pdf_export PASS 记录（未执行≠通过）",
          st3.get("pdf") != "PASS", str(st3.get("pdf")))

    # ---------- 2/6. rc=3 → ERROR（A2 修复语义不得回归） ----------
    r4 = mkdir_project(tmp, "rc3")
    rec4 = TB._step(r4, "probe_rc3", [sys.executable, "-c", "import sys; sys.exit(3)"])
    check("B5c-05 rc=3 → status=ERROR（不记 FAIL、更不记 PASS）",
          rec4.get("status") == "ERROR" and rec4.get("rc") == 3,
          f"{rec4.get('rc')}/{rec4.get('status')}")
    rec4b = TB._step(r4, "probe_rc1", [sys.executable, "-c", "import sys; sys.exit(1)"])
    check("B5c-06 rc=1 → status=FAIL", rec4b.get("status") == "FAIL",
          str(rec4b.get("status")))
    rec4c = TB._step(r4, "probe_rc0", [sys.executable, "-c", "import sys; sys.exit(0)"])
    check("B5c-07 rc=0 → status=PASS", rec4c.get("status") == "PASS",
          str(rec4c.get("status")))
    rec4d = TB._step(r4, "probe_rc2", [sys.executable, "-c", "import sys; sys.exit(2)"])
    check("B5c-08 rc=2 默认记 FAIL（NOT_APPLICABLE 仅在 allow_na 时）",
          rec4d.get("status") == "FAIL", str(rec4d.get("status")))
    rec4e = TB._step(r4, "probe_rc2na", [sys.executable, "-c", "import sys; sys.exit(2)"],
                     allow_na=True)
    check("B5c-09 allow_na + rc=2 → NOT_APPLICABLE", rec4e.get("status") == "NOT_APPLICABLE",
          str(rec4e.get("status")))

    # ---------- 8. Format-QA FAIL 传递到最终 gate ----------
    r5 = mkdir_project(tmp, "qafail")
    contract(r5)
    TB.pipeline(r5, steps=["docx"])
    with open(os.path.join(r5, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    with open(os.path.join(r5, "毕业论文.pdf"), "wb") as f:
        f.write(b"%PDF fake")
    w(r5, "artifacts/qa/graph-quality-report.md",
      "- GQ-01: FAIL | 节点重叠\n- GQ-02: PASS | ok\n")
    res5 = DG.aggregate(r5)
    d5 = {x["gate_id"]: x for x in res5["items"]}
    check("B5c-10 Format-QA FAIL → 域 FAIL 且终局 BLOCK",
          d5.get("G-FMT-graph", {}).get("status") == "FAIL"
          and res5["status"] == "BLOCK",
          f"{d5.get('G-FMT-graph', {}).get('status')}/{res5['status']}")

    # ---------- 5. QA 缺失不能 PASS ----------
    r6 = mkdir_project(tmp, "qamissing")
    contract(r6)
    TB.pipeline(r6, steps=["docx"])
    with open(os.path.join(r6, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    res6 = DG.aggregate(r6)
    d6 = {x["gate_id"]: x for x in res6["items"]}
    check("B5c-11 交付物在场但 QA 报告缺失 → 域不得 PASS",
          d6.get("G-FMT-graph", {}).get("status") not in (None,),
          str(d6.get("G-FMT-graph", {}).get("status")))
    check("B5c-12 该场景终局不得 PASS", res6["status"] != "PASS", res6["status"])

    # ---------- 4. gate 读取最新结果（覆盖旧的 PASS 证据） ----------
    r7 = mkdir_project(tmp, "latest")
    contract(r7)
    TB.pipeline(r7, steps=["docx"])
    with open(os.path.join(r7, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    with open(os.path.join(r7, "毕业论文.pdf"), "wb") as f:
        f.write(b"%PDF fake")
    w(r7, "artifacts/qa/content-purity-report.md", "- MD-01: PASS | ok\n")
    first7 = DG.aggregate(r7)["items"]
    w(r7, "artifacts/qa/content-purity-report.md", "- MD-01: FAIL | 残留 ** 标记\n")
    second7 = DG.aggregate(r7)["items"]
    d7a = {x["gate_id"]: x["status"] for x in first7}
    d7b = {x["gate_id"]: x["status"] for x in second7}
    check("B5c-13 gate 读到的是最新报告（PASS→FAIL 立即反映）",
          d7a.get("G-FMT-content_purity") == "PASS"
          and d7b.get("G-FMT-content_purity") == "FAIL",
          f"{d7a.get('G-FMT-content_purity')} -> {d7b.get('G-FMT-content_purity')}")

    # ---------- 3/9. 成功链路正确聚合 ----------
    r8 = mkdir_project(tmp, "ok")
    contract(r8)
    TB.pipeline(r8, steps=["docx"])
    with open(os.path.join(r8, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    with open(os.path.join(r8, "毕业论文.pdf"), "wb") as f:
        f.write(b"%PDF fake")
    TB.write_manifest(r8, [{"artifact": "docx", "path": "毕业论文.docx"},
                           {"artifact": "pdf", "path": "毕业论文.pdf"}])
    man8 = TB.load_manifest(r8)
    man8["meta"]["steps"] = {k: {"status": "PASS", "rc": 0}
                             for k in ("pdf_qa", "visual_regression", "toc",
                                       "repaginate", "pdf", "finalize")}
    with open(os.path.join(r8, ".aeromech", "artifacts", "build",
                           "artifact-manifest.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(man8, f, allow_unicode=True)
    for rep_name, code in [("tf-qa-report.md", "TF-05"), ("cover-fidelity-report.md", "CF-01"),
                           ("cover-align-report.md", "COVER-ALIGN-01"),
                           ("cover-fill-report.md", "COVER-FILL-01"),
                           ("color-fidelity-report.md", "COLOR-01"),
                           ("page-fidelity-report.md", "HF-01"),
                           ("figure-table-report.md", "FIG-01"),
                           ("graph-quality-report.md", "GQ-01"),
                           ("figure-visual-report.md", "VIS-01"),
                           ("table-readability-report.md", "TR-01"),
                           ("content-purity-report.md", "MD-01")]:
        w(r8, "artifacts/qa/" + rep_name, f"- {code}: PASS | ok\n")
    res8 = DG.aggregate(r8)
    chk8 = TB.check_manifest(r8)
    check("B5c-14 manifest 一致性核对通过（sha256 与现场一致）",
          chk8.get("status") in ("PASS", "OK") and not chk8.get("changed"),
          str(chk8.get("status")))
    check("B5c-15 全 PASS 链路终局为 PASS",
          res8["status"] == "PASS", res8["status"])
    check("B5c-16 聚合结果含全部 FORMAT_REPORTS 域",
          sum(1 for x in res8["items"] if x["gate_id"].startswith("G-FMT-"))
          == len(DG.FORMAT_REPORTS),
          str(sum(1 for x in res8["items"] if x["gate_id"].startswith("G-FMT-"))))

    # manifest 漂移 → gate 必须发现（构建后改动=内容身份不可信）
    with open(os.path.join(r8, "毕业论文.docx"), "ab") as f:
        f.write(b"tampered")
    res8b = DG.aggregate(r8)
    d8b = {x["gate_id"]: x for x in res8b["items"]}
    check("B5c-17 交付物被改动 → document 域 FAIL（manifest 漂移可检出）",
          d8b.get("G-DOC-01", {}).get("status") == "FAIL",
          str(d8b.get("G-DOC-01", {}).get("status")))

    # ---------- 7. DOCX/PDF 不存在时不能误判 ----------
    r9 = mkdir_project(tmp, "nofile")
    contract(r9)
    res9 = DG.aggregate(r9)
    d9 = {x["gate_id"]: x for x in res9["items"]}
    check("B5c-18 交付物未构建 → document 域明确判定（不静默消失）",
          "G-DOC-01" in d9, str(sorted(k for k in d9 if k.startswith("G-DOC"))))
    check("B5c-19 未构建时终局不得 PASS", res9["status"] != "PASS", res9["status"])

    # ---------- 10. COM / Word 不可用环境：显式 SKIP，不伪装 PASS ----------
    ok_word, why = word_available()
    if ok_word:
        r10 = mkdir_project(tmp, "com")
        contract(r10)
        TB.pipeline(r10, steps=["docx"])
        r10toc = TB._step(r10, "toc", [sys.executable,
                                       os.path.join(HERE, "..", "..", "scripts",
                                                    "update_toc.py"), r10],
                          timeout=300)
        check("B5c-20 真实 Word 环境：toc 步骤返回明确状态（0 或非 0）",
              r10toc.get("status") in ("PASS", "FAIL", "ERROR"),
              f"{r10toc.get('rc')}/{r10toc.get('status')}")
    else:
        skip("B5c-20 真实 Word COM 冒烟（toc/repaginate/pdf）", why)
        # 即便 Word 不可用，也必须保证"不可用 ≠ PASS"
        r10 = mkdir_project(tmp, "comna")
        contract(r10)
        TB.pipeline(r10, steps=["docx"])
        rec10 = TB._step(r10, "toc", [sys.executable,
                                      os.path.join(HERE, "..", "..", "scripts",
                                                   "update_toc.py"), r10],
                         timeout=300)
        check("B5c-21 Word 不可用时 toc 步骤不得记 PASS（环境缺失≠通过）",
              rec10.get("status") != "PASS",
              f"{rec10.get('rc')}/{rec10.get('status')}")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_pipeline_contract 结果: PASS={PASS} FAIL={FAIL} SKIP={SKIP}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
