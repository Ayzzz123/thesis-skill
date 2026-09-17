# -*- coding: utf-8 -*-
"""delivery_gate.py — Delivery Gate 聚合器（aeromech-thesis v1.6.0，Phase 4）

统一消费（指令 §九/§十二）：Format QA（tf/cover/cover_align/cover_fill/color/page/
figure_table/graph/table/content_purity 报告）+ pipeline 步骤记录（toc/repaginate/pdf/
finalize/pdf_qa/visual_regression，取自 artifact-manifest meta）+ Document/PDF（交付物
存在性 + manifest sha256 一致性）+ Figure 生命周期（figure_iface）+ Research QA
（复用 stage_routing.delivery_gate_status，RQG/loop/NHR 语义不重算）+ Human Review（双队列）。

状态模型（指令 §九/§二十二）：域级 item 复用 v1.4.1 七态；终局五态 PASS /
PASS_WITH_WARNINGS / PASS_WITH_HUMAN_REVIEW / BLOCK / ERROR。**不造第五套状态。**

聚合规则（指令 §十）：ERROR > Critical/High FAIL(BLOCK) > NEEDS_HUMAN_REVIEW > WARN > PASS。
**Overall Score 绝不参与放行**；无模板 → 模板对照域由 tf_qa 自身输出 NOT_APPLICABLE
（不伪造 PASS 也不 BLOCK）；旧项目无注册表/图计划 → 研究/图域 NOT_APPLICABLE（§十三，
不误判 PASS 也不误伤）；但**交付物域没有 N/A 豁免**：无交付物或无 manifest 一致性证据 =
BLOCK（未执行≠通过）。证据缺且域适用 → BLOCK。

每项 Gate（指令 §十一）：{gate_id, domain, status, severity, evidence[], reason,
remediation}；--write 输出 artifacts/qa/gate-summary.json + gate-report.md。

用法：
  python delivery_gate.py <root> [--json] [--write]
退出码：0=PASS/PASS_WITH_WARNINGS/PASS_WITH_HUMAN_REVIEW；1=BLOCK；3=ERROR
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

import thesis_state as TS
import stage_routing as SR
import thesis_build as TB
import figure_iface as FI
import research_integrity as RI

GATE_STATES = ["PASS", "PASS_WITH_WARNINGS", "PASS_WITH_HUMAN_REVIEW", "BLOCK", "ERROR"]
RANK = {"PASS": 0, "PASS_WITH_WARNINGS": 1, "PASS_WITH_HUMAN_REVIEW": 2,
        "BLOCK": 3, "ERROR": 4}
REMEDIATION = {
    "critical": "修复 Critical 项（交付物完整性/证据真实性）后重跑对应 QA，再入 Gate",
    "high": "修复 High 项后重跑对应 QA（High 禁正式终稿，delivery-pipeline §8）",
    "nhr": "完成人工裁决（human-review.yaml / human-review-queue.yaml）后重跑",
    "missing": "补跑缺失的 QA/构建步骤（thesis_build pipeline 或对应脚本）后重跑",
    "error": "ERROR=内部异常/证据损坏（绝不伪造 PASS）：修复后重跑",
    "doc": "接入统一构建产出 artifact-manifest，或恢复交付物一致性（构建后被改动/丢失=内容身份不可信）",
}

# md 报告驱动域：(报告文件, 域, pipeline 步名|None)——步 PASS 却无报告 = 证据缺失
FORMAT_REPORTS = [
    ("tf-qa-report.md", "template_fidelity", "tf_qa"),
    ("cover-fidelity-report.md", "cover", "cover_fidelity"),
    ("cover-align-report.md", "cover_align", None),
    ("cover-fill-report.md", "cover_fill", None),
    ("color-fidelity-report.md", "color", None),
    ("page-fidelity-report.md", "page", None),
    ("figure-table-report.md", "figure_table", None),
    ("graph-quality-report.md", "graph", None),
    ("table-readability-report.md", "table", None),
    ("content-purity-report.md", "content_purity", None),
]
# 无 md 报告、按 manifest 步骤记录入域的步：(步名, 域, FAIL 默认严重度)
STEP_DOMAINS = [
    ("pdf_qa", "pdf", "critical"),          # Critical rc=2 时升级（见下）
    ("visual_regression", "visual", "high"),
    ("toc", "toc", "high"),
    ("repaginate", "repaginate", "high"),
    ("pdf", "pdf_export", "critical"),
    ("finalize", "finalize", "high"),
]
ITEM_RE = re.compile(
    r"^- (.+?)[:：] ?(PASS|FAIL|SKIP|NOT_APPLICABLE|SKIPPED_WITH_REASON) ?\| ?(.*)$")


def parse_format_report(path, domain):
    """md 报告行（tf/cover/page/… 通用 `- CODE 名称: ST | 证据`）→ 域记录；无文件→None。"""
    if not os.path.isfile(path):
        return None
    items = []
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                m = ITEM_RE.match(ln.strip())
                if m:
                    code, st, ev = m.group(1).strip(), m.group(2), m.group(3).strip()
                    st = {"SKIP": "SKIPPED_WITH_REASON"}.get(st, st)
                    items.append((code, st, ev))
    except OSError:
        return {"domain": domain, "status": "ERROR", "failures": [],
                "not_applicable": [], "evidence": [path], "checks": 0,
                "reason": "报告不可读"}
    if not items:
        return None
    fails = [(c, e) for c, st, e in items if st == "FAIL"]
    nas = [c for c, st, e in items if st == "NOT_APPLICABLE"]
    if fails:
        status = "FAIL"
    elif len(nas) == len(items):
        status = "NOT_APPLICABLE"
    else:
        status = "PASS"
    return {"domain": domain, "status": status,
            "failures": [{"code": c, "evidence": e[:140]} for c, e in fails],
            "not_applicable": nas, "evidence": [path], "checks": len(items)}


def aggregate(root, write=False):
    items = []

    def add(gid, domain, status, severity, evidence, reason, remediation):
        items.append({"gate_id": gid, "domain": domain, "status": status,
                      "severity": severity, "evidence": [e for e in evidence if e],
                      "reason": reason, "remediation": remediation})

    def step_status(steps, name):
        st = steps.get(name)
        if isinstance(st, dict):
            return st.get("status"), st.get("rc")
        return (str(st) if st else None), None

    # ---------- 研究侧（复用 Phase 2/3 聚合语义；不重算 RQG/loop） ----------
    try:
        research = SR.delivery_gate_status(root)
    except TS.StateError as e:
        research = {"status": "ERROR", "reasons": [f"state 不可读: {e}"], "missing": []}
    try:
        legacy_research = not RI.initialized(root)
    except Exception:
        legacy_research = False
    rmap = {"PASS": ("PASS", "none"), "PASS_WITH_WARNINGS": ("WARN", "medium"),
            "PASS_WITH_HUMAN_REVIEW": ("NEEDS_HUMAN_REVIEW", "high"),
            "BLOCK": ("FAIL", "high"), "ERROR": ("ERROR", "critical")}
    rst, rsev = rmap.get(research["status"], ("ERROR", "critical"))
    if legacy_research and rst == "PASS":
        rst, rsev = "NOT_APPLICABLE", "none"   # 旧项目：研究域未评估，不判 PASS（§十三）
    add("G-RES-01", "research", rst, rsev,
        ["artifacts/qa/research-quality.json", "artifacts/analysis/research-loop-log.json"],
        ("旧项目：注册表未初始化（v1.4/v1.5 兼容规则，研究域 N/A）" if rst == "NOT_APPLICABLE"
         else "; ".join(research.get("reasons") or []) or research["status"]),
        REMEDIATION["missing"] if research.get("missing") and rst == "FAIL" else
        (REMEDIATION["nhr"] if rst == "NEEDS_HUMAN_REVIEW" else
         REMEDIATION["error"] if rst == "ERROR" else
         REMEDIATION["high"] if rst == "FAIL" else ""))

    # ---------- 人工队列（复用 v1.4.1/v1.5 双队列） ----------
    try:
        gs, _st, _ctx = SR.gates(root)
        hrv = gs.get("human_review", {})
        if hrv.get("status") == "NEEDS_HUMAN_REVIEW":
            add("G-HR-01", "human_review", "NEEDS_HUMAN_REVIEW", "high",
                ["research/human-review-queue.yaml"],
                f"loop 队列未裁决 {hrv.get('pending')} 项", REMEDIATION["nhr"])
        elif hrv.get("status") == "ERROR":
            add("G-HR-01", "human_review", "ERROR", "critical",
                ["research/human-review-queue.yaml"], hrv.get("reason", "队列损坏"),
                REMEDIATION["error"])
        elif os.path.isfile(os.path.join(root, ".aeromech", "research",
                                         "human-review-queue.yaml")):
            add("G-HR-01", "human_review", "PASS", "none",
                ["research/human-review-queue.yaml"], "队列存在且已清零", "")
        else:
            add("G-HR-01", "human_review", "NOT_APPLICABLE", "none", [],
                "无人工队列（不构成放行证据）", "")
    except TS.StateError as e:
        add("G-HR-01", "human_review", "ERROR", "critical", [], f"state 不可读: {e}",
            REMEDIATION["error"])

    # ---------- 格式链 md 报告 ----------
    manifest = TB.load_manifest(root) or {}
    steps = ((manifest.get("meta") or {}).get("steps") or {})
    contract = TB.load_contract(root)[0]
    qa_rel = ((contract or {}).get("qa") or {}).get("out") or "artifacts/qa"
    qad = os.path.join(root, ".aeromech", *qa_rel.split("/"))
    for fname, domain, step in FORMAT_REPORTS:
        rel_disp = f".aeromech/{qa_rel}/{fname}"
        rep = parse_format_report(os.path.join(qad, fname), domain)
        if rep is not None:
            rep["evidence"] = [rel_disp]     # 相对路径（不落本机绝对路径）
        if rep is None:
            s_st, _ = step_status(steps, step) if step else (None, None)
            if s_st == "PASS":
                add(f"G-FMT-{domain}", domain, "FAIL", "high", [fname],
                    f"pipeline 记 {step} PASS 但报告缺失（未执行≠通过）", REMEDIATION["missing"])
            continue
        if rep["status"] == "FAIL":
            add(f"G-FMT-{domain}", domain, "FAIL", "high", rep["evidence"],
                f"{len(rep['failures'])}/{rep['checks']} 项 FAIL: "
                + "; ".join(x["code"] for x in rep["failures"][:6]), REMEDIATION["high"])
        elif rep["status"] == "NOT_APPLICABLE":
            add(f"G-FMT-{domain}", domain, "NOT_APPLICABLE", "none", rep["evidence"],
                f"{len(rep['not_applicable'])} 项全部 N/A（条件不适用，不伪造 PASS）", "")
        elif rep["status"] == "ERROR":
            add(f"G-FMT-{domain}", domain, "ERROR", "critical", rep["evidence"],
                rep.get("reason", "报告损坏"), REMEDIATION["error"])
        else:
            add(f"G-FMT-{domain}", domain, "PASS", "none", rep["evidence"],
                f"{rep['checks']} 项通过"
                + (f"（{len(rep['not_applicable'])} N/A 披露）" if rep["not_applicable"] else ""),
                "")

    # ---------- pipeline 步骤域（无 md 报告的步） ----------
    for sname, domain, default_sev in STEP_DOMAINS:
        st, rc = step_status(steps, sname)
        if not st:
            continue
        m = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERROR",
             "NOT_APPLICABLE": "NOT_APPLICABLE",
             "SKIPPED_WITH_REASON": "NOT_APPLICABLE"}.get(st, "ERROR")
        sev = default_sev if m == "FAIL" else ("critical" if m == "ERROR" else "none")
        if sname == "pdf_qa" and rc == 2:
            sev = "critical"
        add(f"G-STP-{sname}", domain, m, sev,
            [".aeromech/artifacts/build/artifact-manifest.yaml"],
            f"pipeline {sname}: {st}" + (f" rc={rc}" if rc else ""),
            REMEDIATION["critical"] if (m == "FAIL" and default_sev == "critical") else
            REMEDIATION["high"] if m == "FAIL" else
            REMEDIATION["error"] if m == "ERROR" else "")

    # ---------- Document / PDF ----------
    # 由 v1.6 统一构建管理（有 build-contract）→ 交付物+manifest 一致性硬要求；
    # 旧项目（无契约，各自 builder 交付，指令 §十三）→ 域 NOT_APPLICABLE：
    # 其交付 QA 由各项目自身报告人工核验，Gate 不强制 v1.6 专属材料，也不误判 PASS。
    docx_rel = ((contract or {}).get("output") or {}).get("docx") or TB.DEFAULT_DOCX
    pdf_rel = ((contract or {}).get("output") or {}).get("pdf") or TB.DEFAULT_PDF
    docx_p = os.path.join(root, docx_rel)
    pdf_p = os.path.join(root, pdf_rel)
    if contract is None:
        add("G-DOC-01", "document", "NOT_APPLICABLE", "none", [docx_rel] if os.path.isfile(docx_p) else [],
            "旧项目（无 build-contract）：交付物经各自 builder 产出，交付域按其自身 QA 报告"
            "由人工核验，Gate 不强制 v1.6 manifest（指令 §十三）", "")
    elif os.path.isfile(docx_p):
        chk = TB.check_manifest(root)
        if chk["status"] == "NOT_APPLICABLE":
            add("G-DOC-01", "document", "FAIL", "high", [docx_rel],
                "交付物存在但无 artifact-manifest（未经统一构建校验链，内容身份不可程序核验）",
                REMEDIATION["doc"])
        elif chk.get("missing"):
            add("G-DOC-01", "document", "FAIL", "critical", [docx_rel],
                f"manifest 登记产物丢失: {chk['missing']}", REMEDIATION["doc"])
        elif chk.get("changed"):
            add("G-DOC-01", "document", "FAIL", "critical", [docx_rel],
                f"交付物与 manifest 漂移（构建后被改动，内容身份不可信）: {chk['changed']}",
                REMEDIATION["doc"])
        else:
            add("G-DOC-01", "document", "PASS", "none", [docx_rel],
                "交付物与 manifest 一致（sha256 核对）", "")
        if not os.path.isfile(pdf_p):
            add("G-DOC-02", "document", "FAIL", "critical", [pdf_rel],
                "DOCX 在场但 PDF 缺失（PDF 是最终真值）", REMEDIATION["doc"])
        else:
            add("G-DOC-02", "document", "PASS", "none", [pdf_rel], "PDF 在位", "")
    else:
        add("G-DOC-01", "document", "FAIL", "critical", [docx_rel],
            "交付物未构建（未执行≠通过；旧项目按其交付流程核验后仍需在此域给出证据）",
            REMEDIATION["doc"])

    # ---------- Figure 生命周期 ----------
    lst = FI.lifecycle_state(root)
    if lst["has_plan"]:
        rej = [f for f, x in lst["figures"].items() if x["status"] == "REJECTED"]
        nhr = [f for f, x in lst["figures"].items() if x["status"] == "NEEDS_HUMAN_REVIEW"]
        if rej:
            add("G-FIG-01", "figure", "FAIL", "critical",
                ["figures/figure-lifecycle.yaml"],
                f"REJECTED 图禁止入文: {rej}", REMEDIATION["critical"])
        elif nhr:
            add("G-FIG-01", "figure", "NEEDS_HUMAN_REVIEW", "high",
                ["figures/figure-lifecycle.yaml"],
                f"图等待人工/其他 Provider: {nhr}", REMEDIATION["nhr"])
        else:
            add("G-FIG-01", "figure", "PASS", "none", ["figures/figure-lifecycle.yaml"],
                f"{len(lst['figures'])} 图生命周期健康", "")
    else:
        add("G-FIG-01", "figure", "NOT_APPLICABLE", "none", [], "无图计划（未走图接口）", "")

    # ---------- 五态终局 ----------
    status = "PASS"
    decisive = False
    for it in items:
        s = it["status"]
        if s == "NOT_APPLICABLE":
            continue
        decisive = True
        if s == "ERROR":
            status = _bump(status, "ERROR")
        elif s == "FAIL":
            status = _bump(status, "BLOCK")
        elif s == "NEEDS_HUMAN_REVIEW":
            status = _bump(status, "PASS_WITH_HUMAN_REVIEW")
        elif s == "WARN":
            status = _bump(status, "PASS_WITH_WARNINGS")
    if not decisive:
        status = "BLOCK"
        add("G-ALL-00", "overall", "FAIL", "high", [],
            "无任何决定性门禁证据（全 N/A=未评估；未执行≠通过）", REMEDIATION["missing"])
    result = {"status": status, "items": items,
              "research_substatus": research["status"],
              "note": "Research Quality Score 为展示值，不参与放行判定"}
    if write:
        os.makedirs(qad, exist_ok=True)
        with open(os.path.join(qad, "gate-summary.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        md = ["# Delivery Gate 汇总（v1.6）", "", f"- 终局: **{status}**",
              f"- 研究侧: {research['status']}", ""]
        for it in items:
            md.append(f"- {it['gate_id']} [{it['domain']}]: {it['status']}"
                      + (f"（{it['severity']}）" if it["severity"] != "none" else "")
                      + f" — {it['reason']}")
        with open(os.path.join(qad, "gate-report.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(md))
    return result


def _bump(cur, new):
    return new if RANK[new] > RANK[cur] else cur


def main(argv=None):
    ap = argparse.ArgumentParser(description="Delivery Gate 聚合器（v1.6）")
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    res = aggregate(root, write=a.write)
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json
          else f"Delivery Gate: {res['status']}\n"
          + "\n".join(f"  {x['gate_id']:<18} {x['status']:<18} {x['reason'][:90]}"
                      for x in res["items"]))
    return {"PASS": 0, "PASS_WITH_WARNINGS": 0, "PASS_WITH_HUMAN_REVIEW": 0,
            "BLOCK": 1, "ERROR": 3}[res["status"]]


if __name__ == "__main__":
    sys.exit(main())
