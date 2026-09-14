# -*- coding: utf-8 -*-
"""research_design.py — Research Design & Feasibility 引擎（aeromech-thesis v1.5.0）

职责（Research Intelligence Layer）：
  1) 设计一致性审计（design.yaml × rq/methods/evidence/datasets/analyses/figures）：
     - RQ×方法能力矩阵（needs ⊆ provides）→ RQ_METHOD_MISMATCH
     - RQ 声明证据要求 × 实际数据/证据类型 → DESIGN_EVIDENCE_MISMATCH
     - 方法选择审计（候选 ≥2、选择理由、拒绝理由）→ METHOD_SELECTION_WEAK
  2) Research Feasibility Gate（RF-01~10）→ FEASIBLE / CONDITIONALLY_FEASIBLE / INFEASIBLE

用法：
  python research_design.py <project_root> audit [--json]
  python research_design.py <project_root> feasibility [--json]
  python research_design.py <project_root> all [--json] [--out <dir>]
退出码：0=无 high/critical 发现；1=存在 high/critical；2=设计注册表未建立（旧项目兼容，不阻塞）；3=ERROR
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_integrity as RI

SCOPE_MAX_INCLUDED = 6      # RF-08：声明式范围上限（超过 → 范围过大告警）
RQ_MAX = 5                  # RF-08：研究问题数量上限
SIM_TYPES = ("simulated", "assumption")
REAL_TYPES = ("real", "public", "user_provided", "literature")


def _finding(code, severity, detail, nodes=None, rule=None, auto=False):
    return {"code": code, "severity": severity, "detail": detail,
            "nodes": nodes or [], "rule": rule or code, "auto_repairable": auto}


def _by_id(items):
    return {str(x.get("id")): x for x in (items or [])}


def analyze(root, data=None, errors=None):
    """设计一致性 + 方法选择审计。返回 {status, findings[], design, methods_audit}。"""
    errors = [] if errors is None else errors
    if data is None:
        data = RI.load_all(root, collect_errors=errors)
    findings = []
    designs = data.get("design") or []
    scopes = data.get("scope") or []
    if not designs:
        return {"status": "not_initialized", "findings": findings,
                "design": None, "scope": scopes[0] if scopes else None,
                "methods_audit": [],
                "reason": "design.yaml 未建立（旧项目或未到 S3）：Research Design Registry 缺失"}

    design = designs[0]
    rq_by_id = _by_id(data.get("rq"))
    m_by_id = _by_id(data.get("methods"))
    ev = data.get("evidence") or []
    ds = data.get("datasets") or []
    an = data.get("analyses") or []

    # ---- 1) RQ×方法能力矩阵：needs ⊆ provides ----
    provides = set()
    for mref in design.get("methods") or []:
        m = m_by_id.get(str(mref)) or {}
        for p in m.get("provides") or []:
            provides.add(str(p))
    for req in design.get("rq_requirements") or []:
        rid = str(req.get("id", ""))
        needs = [str(x) for x in (req.get("needs") or [])]
        unmet = [n for n in needs if n not in provides]
        if unmet:
            findings.append(_finding(
                "RQ_METHOD_MISMATCH", "high",
                f"{rid} 需求 {unmet} 未被所选方法能力覆盖（方法 provides={sorted(provides) or '未声明'}）",
                nodes=[rid], rule="DSG-03/needs⊆provides"))

    # ---- 2) RQ 证据要求 × 实际数据/证据能力 ----
    for req in design.get("rq_requirements") or []:
        rid = str(req.get("id", ""))
        need = str(req.get("evidence_requirement", ""))
        if need == "real_world_data":
            has_real = any(str(d.get("type")) in REAL_TYPES for d in ds)
            if not has_real:
                types = sorted({str(d.get("type")) for d in ds}) or ["（无数据集）"]
                findings.append(_finding(
                    "DESIGN_EVIDENCE_MISMATCH", "high",
                    f"{rid} 声明需要真实世界数据（real_world_data），但 datasets 仅含 {types}",
                    nodes=[rid], rule="DSG-04/evidence_requirement"))
        elif need == "verified_evidence":
            has_v = any(str(e.get("verification_status")) == "verified" for e in ev)
            if not has_v:
                sts = sorted({str(e.get("verification_status")) for e in ev}) or ["（无证据）"]
                findings.append(_finding(
                    "DESIGN_EVIDENCE_MISMATCH", "high",
                    f"{rid} 声明需要已核实证据（verified_evidence），但 evidence 最高状态为 {sts}",
                    nodes=[rid], rule="DSG-04/evidence_requirement"))
        elif need == "literature_only":
            has_lit = any(str(e.get("source_type")) == "literature"
                          and str(e.get("verification_status")) in ("verified", "partial") for e in ev)
            if not has_lit:
                findings.append(_finding(
                    "EVIDENCE_GAP", "medium",
                    f"{rid} 声明需要文献级证据（literature_only），但缺少 verified/partial 的 literature 证据",
                    nodes=[rid], rule="DSG-04/evidence_requirement"))

    # ---- 3) 数据/分析计划 × 注册表存在性 ----
    for ref in design.get("data_plan") or []:
        if str(ref).startswith("DS-") and str(ref) not in _by_id(ds):
            findings.append(_finding("DATA_GAP", "high",
                                     f"data_plan 引用 {ref} 不存在于 datasets", nodes=[str(ref)],
                                     rule="DSG-05/data_plan"))
    for ref in design.get("analysis_plan") or []:
        if str(ref).startswith("AN-") and str(ref) not in _by_id(an):
            findings.append(_finding("TRACEABILITY_GAP", "high",
                                     f"analysis_plan 引用 {ref} 不存在于 analyses", nodes=[str(ref)],
                                     rule="DSG-06/analysis_plan"))

    # ---- 4) 方法选择审计（§5 Method Selection Intelligence）----
    audit = []
    for m in data.get("methods") or []:
        mid = str(m.get("id"))
        sel = m.get("selection") or {}
        cands = sel.get("candidates") or []
        reasons_missing = [str(c.get("name", "?")) for c in cands
                           if not str(c.get("reason", "")).strip()]
        weak = []
        if len(cands) < 2:
            weak.append(f"候选方法不足 2 个（{len(cands)}）")
        if not str(sel.get("selection_reason", "")).strip():
            weak.append("缺少选择理由 selection_reason")
        if reasons_missing:
            weak.append(f"候选缺少取舍理由：{reasons_missing}")
        sel_name = str(sel.get("selected", ""))
        if sel_name and cands and sel_name not in [str(c.get("name")) for c in cands]:
            weak.append("selected 不在候选列表中")
        audit.append({"id": mid, "weak": weak, "candidates": [str(c.get("name")) for c in cands],
                      "selected": sel_name})
        if weak:
            sev = "high" if any("selection_reason" in w or "selected 不在" in w for w in weak) else "medium"
            findings.append(_finding(
                "METHOD_SELECTION_WEAK", sev,
                f"{mid} 方法选择论证不足：{'；'.join(weak)}", nodes=[mid],
                rule="DSG-07/method_selection"))

    return {"status": "ok", "findings": findings, "design": design,
            "scope": scopes[0] if scopes else None, "methods_audit": audit}


def feasibility(root, data=None, errors=None):
    """Research Feasibility Gate（RF-01~10）。返回 {verdict, checks[], reasons[]}。"""
    errors = [] if errors is None else errors
    if data is None:
        data = RI.load_all(root, collect_errors=errors)
    designs = data.get("design") or []
    scopes = data.get("scope") or []
    if not designs:
        return {"verdict": "NOT_APPLICABLE", "checks": [],
                "reason": "design.yaml 未建立（旧项目兼容：可行性门禁不适用，不阻塞）"}
    design = designs[0]
    scope = scopes[0] if scopes else {}
    rq = data.get("rq") or []
    ev = data.get("evidence") or []
    ds = data.get("datasets") or []
    an = data.get("analyses") or []
    calcs = data.get("computations") or []
    cons = data.get("conclusions") or []
    figs = data.get("figures") or []
    an_by_id = _by_id(an)
    cov = RI.coverage(root) if RI.initialized(root) else {"evidence_coverage_ratio": 1.0,
                                                          "uncovered": []}

    checks = []

    def add(rf, ok, severity_if_fail, detail):
        checks.append({"rule": rf, "ok": bool(ok),
                       "status": "PASS" if ok else severity_if_fail, "detail": detail})

    # RF-01 研究问题可回答：每个 RQ 至少一条分析链接
    bad01 = [str(r.get("id")) for r in rq if not (r.get("related_analyses") or [])]
    add("RF-01", not bad01, "FAIL", f"RQ 无分析链接: {bad01 or '无'}")
    # RF-02 目标可实现：expected_outputs 均能在 analyses outputs / figures 中找到落点
    outs = set()
    for a in an:
        for o in a.get("outputs") or []:
            outs.add(str(o))
    for f in figs:
        outs.add(str(f.get("id")))
    need_out = [str(x) for x in design.get("expected_outputs") or []]
    missing_out = [x for x in need_out if x not in outs and not x.startswith("章节")]
    add("RF-02", not missing_out, "WARN", f"预期产出未落到分析/图表: {missing_out or '无'}")
    # RF-03 数据足够：至少 1 数据集；且各 RQ 的 real_world_data 要求被满足（结构性）
    need_real = [str(r.get("id")) for r in (design.get("rq_requirements") or [])
                 if str(r.get("evidence_requirement")) == "real_world_data"]
    has_real = any(str(d.get("type")) in REAL_TYPES for d in ds)
    ok03 = bool(ds) and (not need_real or has_real)
    add("RF-03", ok03, "FAIL",
        f"数据集 {len(ds)} 个；真实数据需求 {need_real or '无'}；真实数据可得={has_real}")
    # RF-04 证据足够：coverage ≥ 0.8 且无 uncovered
    cov_ok = cov.get("evidence_coverage_ratio", 1.0) >= 0.8 and not cov.get("uncovered")
    add("RF-04", cov_ok, "WARN",
        f"Evidence Coverage={cov.get('evidence_coverage_ratio')} uncovered={cov.get('uncovered') or '无'}")
    # RF-05 方法匹配：无 RQ_METHOD_MISMATCH
    a = analyze(root, data=data)
    mis = [f for f in a["findings"] if f["code"] == "RQ_METHOD_MISMATCH"]
    add("RF-05", not mis, "FAIL", f"方法能力不匹配: {[f['nodes'] for f in mis] or '无'}")
    # RF-06 计算可执行：CALC 字段齐备（validate 已约束）+ recompute 存在性或已复核
    bad06 = [str(c.get("id")) for c in calcs
             if not (str(c.get("formula", "")).strip() and str(c.get("verification", "")).strip())]
    add("RF-06", not bad06, "WARN", f"计算不可执行/未复核: {bad06 or '无'}")
    # RF-07 结论可被支持：全部结论有 claims/analyses 链且无仅模拟证据的强断言意图
    bad07 = [str(c.get("id")) for c in cons if not (c.get("claims") or c.get("analyses"))]
    add("RF-07", not bad07, "FAIL", f"结论缺乏回溯链: {bad07 or '无'}")
    # RF-08 范围过大：included 项与 RQ 数量上限（声明阈值）
    inc = scope.get("included") or []
    ok08 = len(inc) <= SCOPE_MAX_INCLUDED and len(rq) <= RQ_MAX
    add("RF-08", ok08, "WARN",
        f"scope.included={len(inc)}（上限 {SCOPE_MAX_INCLUDED}），RQ={len(rq)}（上限 {RQ_MAX}）")
    # RF-09 范围过小：至少 1 分析、1 预期产出、1 included
    ok09 = bool(inc) and bool(an) and bool(need_out)
    add("RF-09", ok09, "WARN",
        f"included={len(inc)} analyses={len(an)} expected_outputs={len(need_out)}")
    # RF-10 假设合理：design.assumptions 非空；含模拟数据时必须声明局限
    sim_used = any(str(d.get("type")) in SIM_TYPES for d in ds)
    ok10 = bool(design.get("assumptions")) and (not sim_used or bool(design.get("limitations")))
    add("RF-10", ok10, "FAIL",
        f"assumptions={len(design.get('assumptions') or [])} 模拟数据={sim_used} limitations={'有' if design.get('limitations') else '无'}")

    fails = [c for c in checks if c["status"] == "FAIL"]
    warns = [c for c in checks if c["status"] == "WARN"]
    verdict = "INFEASIBLE" if fails else ("CONDITIONALLY_FEASIBLE" if warns else "FEASIBLE")
    return {"verdict": verdict, "checks": checks,
            "reasons": [f"{c['rule']}: {c['detail']}" for c in fails + warns]}


def run_all(root, out_dir=None):
    data = RI.load_all(root, collect_errors=[])
    res = analyze(root, data=data)
    res["feasibility"] = feasibility(root, data=data)
    if res.get("status") == "ok":
        highs = [f for f in res["findings"] if f["severity"] in ("critical", "high")]
    else:
        highs = []
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, "research-design-report.md")
        lines = ["# Research Design & Feasibility 报告（v1.5）", ""]
        lines.append(f"- 设计注册表: {res.get('status')}")
        if res.get("design"):
            lines.append(f"- design_id: {res['design'].get('id')}")
        lines.append(f"- 可行性: {res['feasibility']['verdict']}")
        lines.append("")
        lines.append("## 设计一致性发现")
        for f in res["findings"] or [{"code": "（无）", "severity": "-", "detail": "无发现"}]:
            lines.append(f"- {f['code']} [{f['severity']}] {f['detail']}")
        lines.append("")
        lines.append("## RF-01~10")
        for c in res["feasibility"]["checks"]:
            lines.append(f"- {c['rule']}: {c['status']} | {c['detail']}")
        open(p, "w", encoding="utf-8").write("\n".join(lines))
        print("report:", p)
    return res, (1 if highs else 0)


def main():
    ap = argparse.ArgumentParser(description="Research Design & Feasibility（v1.5）")
    ap.add_argument("project_root")
    ap.add_argument("action", choices=["audit", "feasibility", "all"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = args.project_root
    if not RI.initialized(root):
        print("注册表未初始化：.aeromech/research/ 不存在")
        return 2
    try:
        if args.action == "audit":
            res = analyze(root)
            rc = 1 if any(f["severity"] in ("critical", "high") for f in res["findings"]) else 0
        elif args.action == "feasibility":
            res = feasibility(root)
            rc = 1 if res["verdict"] == "INFEASIBLE" else 0
        else:
            res, rc = run_all(root, out_dir=args.out)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            if res.get("status") == "not_initialized":
                print("NOT_APPLICABLE: design.yaml 未建立（旧项目兼容，不阻塞）")
            else:
                for f in res.get("findings", []):
                    print(f"  [{f['severity']}] {f['code']} | {f['detail']}")
                if "feasibility" in res:
                    print("verdict:", res["feasibility"]["verdict"])
                elif args.action == "feasibility":
                    print("verdict:", res["verdict"])
                    for c in res["checks"]:
                        print(f"  {c['rule']}: {c['status']} | {c['detail']}")
        return rc
    except RI.RegistryError as e:
        print(f"ERROR: 注册表损坏 {e.path}: {e.detail}")
        return 3
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DESIGN ENGINE ERROR: {type(e).__name__}: {e}（未产生 PASS 结论）")
        return 3


if __name__ == "__main__":
    sys.exit(main())
