# -*- coding: utf-8 -*-
"""test_delivery_gate.py — Delivery Gate 聚合器（指令 §九~十三；GATE-01~10）

域覆盖：研究侧（复用 routing）+ 格式链（tf/cover/…/content_purity 报告）+ pipeline 步骤
（pdf_qa/visual/toc/repaginate/pdf/finalize）+ Document/PDF + Figure 生命周期 + Human Review。
五态终局、N/A 语义（无模板≠FAIL、旧项目≠PASS）、Critical 不被总分掩盖、证据缺位=BLOCK、
每项 gate 带 evidence/reason/remediation、聚合确定性（同输入两次一致）。
运行：python tests/v1_6/test_delivery_gate.py
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import delivery_gate as DG
import thesis_build as TB
import thesis_state as TS
import figure_iface as FI
import yaml

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def w(root, rel, txt):
    p = os.path.join(root, ".aeromech", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def qa_file(root, name, lines):
    w(root, "artifacts/qa/" + name, "\n".join(lines) + "\n")


def base_report(items):
    """items: [(code, ST, evidence)]"""
    return [f"- {c}: {s} | {e}" for c, s, e in items]


def full_pass_env(root):
    """构造决定性证据全 PASS 的环境（研究侧+格式链+步骤+交付物+图）。"""
    # 研究侧：design 不在场且注册表未初始化 → legacy N/A；给 routing 决定性 PASS 需注册表，
    # 简化：造 research-quality PASS + 无 design（agent_loop N/A）+ 无 loop BLOCK
    os.makedirs(os.path.join(root, ".aeromech", "research"), exist_ok=True)
    # routing: rqg 读 research-quality.json
    w(root, "artifacts/qa/research-quality.json",
      json.dumps({"gate": "PASS"}))
    # 格式链报告（tf 含 N/A 行示例：无模板对照项）
    qa_file(root, "tf-qa-report.md",
            base_report([("TF-01 封面结构", "NOT_APPLICABLE", "无模板"),
                         ("TF-05 摘要结构", "PASS", "ok"),
                         ("TF-08 正文字体", "PASS", "ok")]))
    qa_file(root, "content-purity-report.md", base_report([("MD-01 残留", "PASS", "0 命中")]))
    # pipeline 步骤（manifest meta.steps）
    w(root, "build-contract.yaml", yaml.safe_dump({
        "project": {"title": "T"}, "content": {"chapters": []},
        "school_format": {}}, allow_unicode=True))
    TB.write_manifest(root, [{"artifact": "docx", "path": "毕业论文.docx"}])
    # 步骤记录：改 manifest 以含 steps meta
    man = TB.load_manifest(root)
    man["meta"]["steps"] = {"pdf_qa": {"status": "PASS", "rc": 0},
                            "visual_regression": {"status": "PASS", "rc": 0},
                            "toc": {"status": "PASS", "rc": 0},
                            "repaginate": {"status": "PASS", "rc": 0},
                            "pdf": {"status": "PASS", "rc": 0},
                            "finalize": {"status": "PASS", "rc": 0}}
    with open(os.path.join(root, ".aeromech", "artifacts", "build",
                           "artifact-manifest.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(man, f, allow_unicode=True)
    # 交付物 + manifest 一致
    docx = os.path.join(root, "毕业论文.docx")
    with open(docx, "wb") as f:
        f.write(b"PK fake docx")
    pdf = os.path.join(root, "毕业论文.pdf")
    with open(pdf, "wb") as f:
        f.write(b"%PDF fake")
    # 重新写 manifest 让 sha256 匹配现场
    TB.write_manifest(root, [{"artifact": "docx", "path": "毕业论文.docx"},
                             {"artifact": "pdf", "path": "毕业论文.pdf"}],
                      build_id=man.get("build_id"))
    # 步骤 meta 又被重置，再注入一次
    man2 = TB.load_manifest(root)
    man2["meta"]["steps"] = {"pdf_qa": {"status": "PASS", "rc": 0},
                             "visual_regression": {"status": "PASS", "rc": 0},
                             "toc": {"status": "PASS", "rc": 0},
                             "repaginate": {"status": "PASS", "rc": 0},
                             "pdf": {"status": "PASS", "rc": 0},
                             "finalize": {"status": "PASS", "rc": 0}}
    with open(os.path.join(root, ".aeromech", "artifacts", "build",
                           "artifact-manifest.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(man2, f, allow_unicode=True)
    return root


def with_design(root):
    """design.yaml 在场（agent_loop 域适用性开关；routing v1.5 兼容规则）。"""
    import research_integrity as RI
    RI.save_registry(root, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(root, "design", [{"id": "DESIGN-001", "research_questions": ["RQ-01"],
                                       "objectives": ["o"], "methods": ["M-001"],
                                       "rq_requirements": [{"id": "RQ-01", "needs": ["n"],
                                                            "evidence_requirement": "simulated_ok"}],
                                       "analysis_plan": [], "expected_outputs": [],
                                       "constraints": [], "assumptions": ["a"],
                                       "limitations": ["l"]}])
    return root


def domains(res):
    return {x["gate_id"]: x for x in res["items"]}


def main():
    tmp = tempfile.mkdtemp(prefix="gate_v16_")
    print("== test_delivery_gate ==")

    # ---------- GATE-01 PASS：决定性证据全过 → PASS ----------
    root = F.make_project(os.path.join(tmp, "pass"), with_template=False)
    full_pass_env(root)
    res = DG.aggregate(root)
    check("GATE-01 全证据 PASS→终局 PASS", res["status"] == "PASS",
          str({k: v["status"] for k, v in domains(res).items() if v["status"] != "PASS"}))
    check("GATE-01 每项含 gate_id/status/severity/evidence/reason/remediation",
          all({"gate_id", "domain", "status", "severity", "evidence", "reason",
               "remediation"} <= set(x) for x in res["items"]))

    # ---------- GATE-06/08 N/A 语义 ----------
    check("GATE-08 无模板：tf 域 N/A（不伪造 PASS、不 BLOCK）",
          domains(res)["G-FMT-template_fidelity"]["status"] == "PASS"
          and any("NOT_APPLICABLE" in str(x["evidence"]) or x["status"] == "NOT_APPLICABLE"
                  for x in res["items"] if x["domain"] == "template_fidelity")
          or "N/A" in domains(res)["G-FMT-template_fidelity"]["reason"],
          domains(res)["G-FMT-template_fidelity"]["reason"])
    check("GATE-08 图无计划→figure N/A；但研究/文档域决定性 → 仍 PASS",
          domains(res)["G-FIG-01"]["status"] == "NOT_APPLICABLE")
    # 全部 N/A → 不得 PASS（未评估≠通过）
    root_aliens = F.make_project(os.path.join(tmp, "emptygate"), with_template=False)
    res_e = DG.aggregate(root_aliens)
    check("GATE-06 空证据环境→BLOCK（全 N/A 不构成 PASS）",
          res_e["status"] == "BLOCK" and any(x["gate_id"] == "G-ALL-00" for x in res_e["items"]),
          str(res_e["status"]))

    # ---------- GATE-04 BLOCK（格式 FAIL + 交付漂移） ----------
    r2 = full_pass_env(F.make_project(os.path.join(tmp, "b1"), with_template=False))
    qa_file(r2, "content-purity-report.md",
            base_report([("MD-01 Markdown残留", "FAIL", "发现 ** 12 处"),
                         ("PRM-01 内部路径", "PASS", "0")]))
    res2 = DG.aggregate(r2)
    check("GATE-04 格式链 FAIL→BLOCK", res2["status"] == "BLOCK"
          and domains(res2)["G-FMT-content_purity"]["status"] == "FAIL")
    check("GATE-04 BLOCK 项带 severity 与 remediation",
          domains(res2)["G-FMT-content_purity"]["severity"] == "high"
          and domains(res2)["G-FMT-content_purity"]["remediation"])
    # 交付物漂移（构建后被改）→ critical FAIL
    with open(os.path.join(r2, "毕业论文.docx"), "ab") as f:
        f.write(b"tamper")
    res3 = DG.aggregate(r2)
    check("GATE-04 交付物与 manifest 漂移→document critical→仍 BLOCK",
          res3["status"] == "BLOCK"
          and domains(res3)["G-DOC-01"]["severity"] == "critical")

    # ---------- GATE-02 WARN ----------
    r4 = full_pass_env(F.make_project(os.path.join(tmp, "warn"), with_template=False))
    qa_file(r4, "page-fidelity-report.md", base_report([("HF-01 页眉", "PASS", "ok")]))
    # 研究侧 WARN：rqg PASS 但 loop WARN → routing PASS_WITH_WARNINGS → research WARN
    w(r4, "artifacts/analysis/research-diagnosis.json",
      json.dumps({"feasibility": {"verdict": "FEASIBLE", "reasons": []}, "diagnoses": []}))
    w(r4, "artifacts/analysis/research-loop-log.json",
      json.dumps({"status": "WARN", "iterations": [], "open_findings": [
          {"id": "D1", "issue_type": "SCOPE_UNDERFLOW", "severity": "medium",
           "human": False, "detail": "m"}]}))
    import research_integrity as RI
    RI.save_registry(r4, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(r4, "design", [{"id": "DESIGN-001", "research_questions": ["RQ-01"],
                                     "objectives": ["o"], "methods": ["M-001"],
                                     "rq_requirements": [{"id": "RQ-01", "needs": ["n"],
                                                          "evidence_requirement": "simulated_ok"}],
                                     "analysis_plan": [], "expected_outputs": [],
                                     "constraints": [], "assumptions": ["a"],
                                     "limitations": ["l"]}])
    res4 = DG.aggregate(r4)
    check("GATE-02 loop WARN→终局 PASS_WITH_WARNINGS（披露放行）",
          res4["status"] == "PASS_WITH_WARNINGS",
          domains(res4)["G-RES-01"]["status"] + " " + res4["status"])

    # ---------- GATE-03 NHR ----------
    r5 = full_pass_env(F.make_project(os.path.join(tmp, "nhr"), with_template=False))
    RI.save_registry(r5, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(r5, "design", [{"id": "DESIGN-001", "research_questions": ["RQ-01"],
                                     "objectives": ["o"], "methods": ["M-001"],
                                     "rq_requirements": [{"id": "RQ-01", "needs": ["n"],
                                                          "evidence_requirement": "simulated_ok"}],
                                     "analysis_plan": [], "expected_outputs": [],
                                     "constraints": [], "assumptions": ["a"],
                                     "limitations": ["l"]}])
    w(r5, "artifacts/analysis/research-diagnosis.json",
      json.dumps({"feasibility": {"verdict": "FEASIBLE", "reasons": []}, "diagnoses": []}))
    w(r5, "artifacts/analysis/research-loop-log.json",
      json.dumps({"status": "PASS_WITH_HUMAN_REVIEW", "iterations": [], "open_findings": [
          {"id": "D2", "issue_type": "UNRESOLVED_CONFLICT", "severity": "high",
           "human": True, "detail": "c"}]}))
    w(r5, "research/human-review-queue.yaml", yaml.safe_dump({"queue": [
        {"diagnosis_id": "D2", "issue_type": "UNRESOLVED_CONFLICT", "decision": None}]},
        allow_unicode=True))
    res5 = DG.aggregate(r5)
    check("GATE-03 未裁决队列→NEEDS_HUMAN_REVIEW 域+终局 PASS_WITH_HUMAN_REVIEW",
          res5["status"] == "PASS_WITH_HUMAN_REVIEW"
          and domains(res5)["G-HR-01"]["status"] == "NEEDS_HUMAN_REVIEW", str(res5["status"]))
    # 裁决清零后回到 PASS
    w(r5, "research/human-review-queue.yaml", yaml.safe_dump({"queue": [
        {"diagnosis_id": "D2", "decision": "reject", "applied_status": "rejected_by_human"}]},
        allow_unicode=True))
    w(r5, "artifacts/analysis/research-loop-log.json",
      json.dumps({"status": "PASS", "iterations": [], "open_findings": []}))
    check("GATE-03 裁决后终局回 PASS", DG.aggregate(r5)["status"] == "PASS")

    # ---------- GATE-05/07 Critical 不可掩盖 + ERROR 不透 PASS ----------
    r6 = full_pass_env(F.make_project(os.path.join(tmp, "crit"), with_template=False))
    w(r6, "artifacts/analysis/research-loop-log.json",
      json.dumps({"status": "BLOCK", "iterations": [], "open_findings": [
          {"id": "D9", "issue_type": "CONCLUSION_OVERREACH", "severity": "critical",
           "human": False, "detail": "越界"}]}))
    import research_integrity as RI2
    RI2.save_registry(r6, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI2.save_registry(r6, "design", [{"id": "DESIGN-001", "research_questions": ["RQ-01"],
                                      "objectives": ["o"], "methods": [],
                                      "rq_requirements": [], "analysis_plan": [],
                                      "expected_outputs": [], "constraints": [],
                                      "assumptions": ["a"], "limitations": ["l"]}])
    w(r6, "artifacts/qa/research-quality.json",
      json.dumps({"gate": "FAIL"}))
    # 格式链全 PASS 也不能掩盖研究侧 Critical（总分不掩盖 Critical 的聚合版）
    res6 = DG.aggregate(r6)
    check("GATE-07 格式链全 PASS+研究 Critical 未解→BLOCK（任何分/格式不得掩盖）",
          res6["status"] == "BLOCK")
    # loop ERROR → 域 ERROR → 终局 ERROR（design 在场证据域才适用）
    r7 = full_pass_env(F.make_project(os.path.join(tmp, "err"), with_template=False))
    with_design(r7)
    w(r7, "artifacts/analysis/research-loop-log.json", "{broken json")
    res7 = DG.aggregate(r7)
    check("GATE-05 证据损坏→域 ERROR 终局 ERROR（绝不 PASS）",
          res7["status"] == "ERROR", str(res7["status"]))

    # ---------- GATE-09 evidence 指向真实产物 ----------
    r8 = full_pass_env(F.make_project(os.path.join(tmp, "ev"), with_template=False))
    res8 = DG.aggregate(r8, write=True)
    tf_item = domains(res8)["G-FMT-template_fidelity"]
    evp = os.path.join(r8, tf_item["evidence"][0])   # evidence 为项目根相对路径
    check("GATE-09 evidence 项目根相对路径真实可定位（不落绝对路径）",
          os.path.isfile(evp) and not os.path.isabs(tf_item["evidence"][0]),
          tf_item["evidence"])
    check("GATE-09 gate-summary.json+report.md 落盘",
          os.path.isfile(os.path.join(r8, ".aeromech", "artifacts", "qa", "gate-summary.json"))
          and os.path.isfile(os.path.join(r8, ".aeromech", "artifacts", "qa", "gate-report.md")))

    # ---------- GATE-10 确定性 ----------
    a = DG.aggregate(r8)
    b = DG.aggregate(r8)
    check("GATE-10 同输入两次聚合逐字节一致（确定性）",
          json.dumps(a, sort_keys=True, ensure_ascii=False, default=str)
          == json.dumps(b, sort_keys=True, ensure_ascii=False, default=str))

    # ---------- 状态词表纪律（指令 §二十二）：终局五态、域 item ⊆ v1.4.1 七态 ----------
    ITEM_STATES = {"PASS", "WARN", "FAIL", "NEEDS_HUMAN_REVIEW", "NOT_APPLICABLE",
                   "SKIPPED_WITH_REASON", "ERROR"}
    check("hard 终局词表=五态、域词表 ⊆ v1.4.1 七态（不造第五套状态）",
          all(x["status"] in ITEM_STATES for x in res8["items"])
          and res8["status"] in DG.GATE_STATES
          and set(DG.GATE_STATES) == {"PASS", "PASS_WITH_WARNINGS", "PASS_WITH_HUMAN_REVIEW",
                                      "BLOCK", "ERROR"})

    # ---------- Figure 域（GATE-04 变体：REJECTED 图= critical） ----------
    r9 = full_pass_env(F.make_project(os.path.join(tmp, "fig"), with_template=False))
    FI.plan_figures(r9, provider="local",
                    specs=[{"figure_id": "FIG-001", "name": "n", "kind": "mermaid",
                            "source": None, "out": ".aeromech/artifacts/figures/final/a.png",
                            "related_rqs": ["RQ-01"], "related_analyses": [], "related_claims": []}])
    FI.record(r9, "FIG-001", "REJECTED", reason="FIGURE_ERROR")
    res9 = DG.aggregate(r9)
    check("GATE-04/FIGIF REJECTED 图→figure critical→BLOCK",
          res9["status"] == "BLOCK" and domains(res9)["G-FIG-01"]["severity"] == "critical")
    FI.record(r9, "FIG-001", "VALIDATED", reason="修复后复检通过")
    check("图修复后 figure 域回 PASS", DG.aggregate(r9)["status"] == "PASS")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_delivery_gate 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
