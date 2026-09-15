# -*- coding: utf-8 -*-
"""stage_routing.py — 阶段调度矩阵数据化 + 路由判定（aeromech-thesis v1.6.0）

定位（指令 §十一/§十三，Phase 2 范围）：**提供调度数据与判定，不执行任何脚本、不改任何状态**——
执行/写入属于 Phase 3 Orchestrator。判定输入：state.yaml（Phase 1 StateIO）、
Research Context（v1.4/v1.5 注册表，只读复用 research_context）、既有产物文件证据
（loop-log / diagnosis / RQG 报告 json；缺失=SKIPPED_WITH_REASON，不猜测、不代替运行）。

状态词表：item 级门禁复用 v1.4.1 七态（PASS/WARN/FAIL/NEEDS_HUMAN_REVIEW/NOT_APPLICABLE/
SKIPPED_WITH_REASON/ERROR）；交付门禁复用指令 §二十一 五态（PASS/PASS_WITH_WARNINGS/
PASS_WITH_HUMAN_REVIEW/BLOCK/ERROR）。s7 门禁沿用 state.md §5 三态（passed/conditional/failed）。

用法：
  python stage_routing.py <project_root> route [--json]
  python stage_routing.py <project_root> matrix
  python stage_routing.py <project_root> gate [--json]
退出码：0=判定成功（含 BLOCK 判定本身是成功的判定）；3=ERROR（state 不可读等）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

import thesis_state as TS
import research_context as RC
import research_integrity as RI

STAGES = TS.STAGES

# ---------------- 回退目标映射（state.md §8 + v1.5 issue_type 细化，数据非逻辑） ----------------
CATEGORY_TARGET = {"structure": "S3", "academic": "S3", "citation": "S4", "engineering": "S5",
                   "data": "S6", "figure": "S7", "writing": "S7", "integrity": "S4"}
ISSUE_TYPE_TARGET = {   # research-intelligence.md §5 issue_type → 阶段（loop BLOCK 回退建议用）
    "RQ_METHOD_MISMATCH": "S3", "DESIGN_EVIDENCE_MISMATCH": "S3", "METHOD_SELECTION_WEAK": "S3",
    "SCOPE_OVERFLOW": "S3", "SCOPE_UNDERFLOW": "S3", "FEASIBILITY_BLOCK": "S3",
    "EVIDENCE_GAP": "S4", "CITATION_GAP": "S4", "UNRESOLVED_CONFLICT": "S4", "TRACEABILITY_GAP": "S4",
    "DATA_GAP": "S6", "CALCULATION_GAP": "S6",
    "CLAIM_OVERSTRENGTH": "S7", "CONCLUSION_OVERREACH": "S7", "ABSTRACT_MISMATCH": "S7",
    "QUANTITATIVE_INCONSISTENCY": "S7",
    "DUPLICATE_ANALYSIS": "S7", "REDUNDANT_CONTENT": "S7", "ORPHAN_FIGURE": "S8", "ORPHAN_TABLE": "S8",
}


def issue_target(issue_type, category=None):
    t = ISSUE_TYPE_TARGET.get(issue_type)
    if t:
        return t
    return CATEGORY_TARGET.get(category)


# ---------------- 调度矩阵（指令 §十一：阶段×产物×门禁×AI 挂载点） ----------------
# pr: state.md §3 允许边前置（数据化；执行仍由 thesis_state.transition 校验，这里是"该阶段完成判据"）
# ai: Research Intelligence 挂载点（id × evidence × action=Orchestrator 应调用的既有工具）
MATRIX = {
    "S1": {"name": "题目分析", "exit": [{"id": "topic_card", "desc": "题目卡片",
                                        "probe": "research.topic_card_file"}],
           "ai": [{"id": "feasibility", "desc": "Research Feasibility（题目级初判）",
                   "tool": "research_design.py feasibility", "requires": "design.yaml",
                   "gate": "feasibility",
                   "evidence": ["artifacts/analysis/research-diagnosis.json"]}],
           "forward": [{"to": "S2", "prereq": []}, {"to": "S3",
                                                    "prereq": ["topic_card"]}]},
    "S2": {"name": "智能选题", "exit": [{"id": "topic_card", "desc": "候选题目确定",
                                        "probe": "research.topic_card_file"}],
           "ai": [],
           "forward": [{"to": "S3", "prereq": ["topic_card", "title_nonempty"]}]},
    "S3": {"name": "研究方案", "exit": [{"id": "plan", "desc": "研究方案", "probe": "research.plan_file"},
                                        {"id": "outline", "desc": "论文目录", "probe": "research.outline_file"},
                                        {"id": "rq_registry", "desc": "RQ/方法注册表",
                                         "probe": "registry:rq"},
                                        {"id": "design_registry", "desc": "研究设计注册表",
                                         "probe": "registry:design"},
                                        {"id": "paper_type", "desc": "论文类型确认",
                                         "probe": "project.paper_type"}],
           "ai": [{"id": "feasibility", "desc": "Research Design / Method Selection",
                   "tool": "research_design.py audit+feasibility", "requires": "design.yaml",
                   "gate": "feasibility",
                   "evidence": ["artifacts/analysis/research-diagnosis.json"]}],
           "forward": [{"to": "S4", "prereq": ["plan"]}, {"to": "S5", "prereq": ["plan", "rq_registry"]},
                       {"to": "S7", "prereq": ["plan", "rq_registry", "s7_evidence", "feasibility_passed"],
                        "types": ["review"]}]},
    "S4": {"name": "文献研究", "exit": [{"id": "evidence_registry", "desc": "证据登记",
                                        "probe": "registry:evidence"},
                                       {"id": "literature_reviewed", "desc": "文献 reviewed",
                                        "probe": "research.literature_status==reviewed"}],
           "ai": [{"id": "coverage", "desc": "Evidence Coverage",
                   "tool": "research_integrity.py coverage", "requires": "research/",
                   "gate": "rqg",
                   "evidence": ["research/traceability.json", "artifacts/qa/research-quality.json"]}],
           "forward": [{"to": "S5", "prereq": ["evidence_registry"]},
                       {"to": "S3", "prereq": [], "revert": True},
                       {"to": "S7", "prereq": ["literature_reviewed", "s7_evidence"],
                        "types": ["review"]}]},
    "S5": {"name": "工程分析", "exit": [{"id": "analysis_registry", "desc": "分析注册",
                                        "probe": "registry:analyses"},
                                       {"id": "analysis_artifacts", "desc": "分析产物",
                                        "probe": "any_artifact:artifacts/analysis"}],
           "ai": [{"id": "diagnosis", "desc": "Research Diagnosis（首轮）",
                   "tool": "research_diagnosis.py", "requires": "research/",
                   "gate": "diagnosis",
                   "evidence": ["artifacts/analysis/research-diagnosis.json"]}],
           "forward": [{"to": "S6", "prereq": ["analysis_registry"]},
                       {"to": "S7", "prereq": ["analysis_registry", "s7_evidence"]}]},
    "S6": {"name": "数据分析", "exit": [{"id": "data_registry", "desc": "数据集注册",
                                        "probe": "registry:datasets"},
                                       {"id": "computation_registry", "desc": "计算注册",
                                        "probe": "registry:computations"}],
           "ai": [{"id": "data_integrity", "desc": "Data Integrity / Computation",
                   "tool": "research_integrity.py validate + research_diagnosis.py",
                   "requires": "research/", "gate": "diagnosis",
                   "evidence": ["artifacts/analysis/research-diagnosis.json"]}],
           "forward": [{"to": "S5", "prereq": [], "revert": True},
                       {"to": "S7", "prereq": ["data_registry", "s7_evidence"]}]},
    "S7": {"name": "章节写作", "exit": [{"id": "draft_done", "desc": "全稿完成",
                                        "probe": "writing.status==draft_done"},
                                       {"id": "claims_registry", "desc": "论断注册",
                                        "probe": "registry:claims"},
                                       {"id": "conclusions_registry", "desc": "结论注册",
                                        "probe": "registry:conclusions"}],
           "ai": [{"id": "agent_loop", "desc": "Claim/Conclusion/Abstract 一致性闭环",
                   "tool": "research_agent_loop.py", "requires": "design.yaml",
                   "gate": "agent_loop",
                   "evidence": ["artifacts/analysis/research-loop-log.json"]}],
           "forward": [{"to": "S8", "prereq": ["draft_done", "claims_registry"]}]},
    "S8": {"name": "图表规整", "exit": [{"id": "figures_registry", "desc": "图表论证链接注册",
                                        "probe": "registry:figures"},
                                       {"id": "figure_plan", "desc": "图表点位表/计划",
                                        "probe": "any_file:artifacts/figures"}],
           "ai": [{"id": "figure_traceability", "desc": "Figure 研究可追溯（无孤儿图表）",
                   "tool": "research_integrity.py trace + figure QA", "requires": "research/",
                   "gate": "traceability",
                   "evidence": ["research/traceability.json"]}],
           "forward": [{"to": "S9", "prereq": ["figures_registry"]},
                       {"to": "S7", "prereq": [], "revert": True}]},
    "S9": {"name": "全文QA", "exit": [{"id": "qa_reports", "desc": "QA 报告集",
                                      "probe": "any_file:artifacts/qa"}],
           "ai": [{"id": "full_qa", "desc": "Full QA（RQG+Loop 终态+格式链）",
                   "tool": "research_quality_qa.py + research_agent_loop.py + 格式 QA 链",
                   "requires": "research/", "gate": "agent_loop",
                   "evidence": ["artifacts/qa/research-quality.json",
                                "artifacts/analysis/research-loop-log.json"]}],
           "forward": [{"to": "S10", "prereq": ["full_qa_closed"]}],
           "gate_before_exit": ["feasibility", "s7_evidence", "rqg", "agent_loop", "human_review"]},
    "S10": {"name": "答辩", "exit": [{"id": "defense", "desc": "答辩材料",
                                     "probe": "any_file:artifacts/defense"}],
            "ai": [], "forward": []},
}

VERDICT_MAP = {"FEASIBLE": "PASS", "CONDITIONALLY_FEASIBLE": "WARN", "INFEASIBLE": "FAIL"}


# ---------------- 探针：从 state/注册表/文件读事实（只读） ----------------

def _get_path(state, dotted):
    """按 research./project./writing. 前缀取 state 路径值（支持 ==value 比较）。"""
    base_key, _, rest = dotted.partition(".")
    val = state.get(base_key) if base_key in ("research", "project", "writing", "stage", "data", "qa") else None
    for k in rest.split("."):
        val = (val or {}).get(k)
    return val


def _probe(root, state, pr, ctx):
    if pr == "title_nonempty":
        return bool((state.get("project") or {}).get("title"))
    if pr == "s7_evidence":
        return check_s7_gate(state, root)[0] in ("passed", "conditional")
    if pr == "full_qa_closed":
        return delivery_gate_status(root)["status"] in (
            "PASS", "PASS_WITH_WARNINGS", "PASS_WITH_HUMAN_REVIEW")
    if pr.startswith("registry:"):
        return bool(ctx.get("status") == "OK" and
                    (ctx["summary"]["counts"].get(pr.split(":", 1)[1]) or 0) > 0)
    if pr.startswith("any_file:"):
        base = _ap(root, pr.split(":", 1)[1])
        return os.path.isdir(base) and any(
            fn for _d, _s, fs in os.walk(base) for fn in fs)
    if pr.startswith("any_artifact:"):
        base = _ap(root, pr.split(":", 1)[1])
        return os.path.isdir(base) and any(
            fn for _d, _s, fs in os.walk(base) for fn in fs)
    if "==" in pr:
        base, want = pr.split("==", 1)
        return str(_get_path(state, base)) == want
    if "." in pr:
        return bool(_get_path(state, pr))
    return False


def _ap(root, rel):
    return os.path.join(root, ".aeromech", rel) if not os.path.isabs(rel) and not rel.startswith("materials") else os.path.join(root, rel)


def check_s7_gate(state, root):
    """复用 Phase 1 StateIO 门禁校验（不另造）。"""
    return TS.check_gate_evidence(state, root)


def _read_json(root, rel):
    p = os.path.join(root, ".aeromech", rel)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"_corrupt": p}


# ---------------- 门禁判定（item 级 v1.4.1 词表） ----------------

def gates(root, ctx=None):
    state, _ = TS.load_state(root)
    ctx = ctx or RC.context(root)
    design_exists = ctx.get("status") == "OK" and bool((ctx.get("summary", {}).get("counts") or {}).get("design"))
    research_exists = ctx["status"] in ("OK",) or RI.initialized(root)
    out = {}

    # ① Feasibility（§十三：design 在场即为硬门禁；INFEASIBLE 绝不放行进入写作）
    diag = _read_json(root, "artifacts/analysis/research-diagnosis.json")
    if not design_exists:
        out["feasibility"] = {"status": "NOT_APPLICABLE" if ctx["status"] == "NOT_APPLICABLE"
                              else "SKIPPED_WITH_REASON",
                              "evidence": None,
                              "reason": "design.yaml 未建立（旧项目兼容或 S3 未产出设计）"}
    elif diag is None:
        out["feasibility"] = {"status": "SKIPPED_WITH_REASON", "evidence": None,
                              "reason": "有 design 但 research-diagnosis.json 不存在：由调度层先运行诊断"}
    elif diag.get("_corrupt"):
        out["feasibility"] = {"status": "ERROR", "evidence": diag["_corrupt"],
                              "reason": "诊断证据文件损坏"}
    else:
        v = (diag.get("feasibility") or {}).get("verdict")
        if not v:
            out["feasibility"] = {"status": "SKIPPED_WITH_REASON", "evidence": None,
                                  "reason": "诊断证据文件不含 feasibility 记录：运行 research_design.py feasibility"}
        else:
            out["feasibility"] = {"status": VERDICT_MAP.get(v, "ERROR"),
                                  "verdict": v,
                                  "reasons": (diag.get("feasibility") or {}).get("reasons") or [],
                                  "evidence": "artifacts/analysis/research-diagnosis.json"}

    # ② S7 写作门禁（state.md §5 三态，复用 StateIO）
    status, probs = check_s7_gate(state, root)
    out["s7_evidence"] = {"status": status, "problems": probs}

    # ③ RQG（注册表在场时）
    rqg = _read_json(root, "artifacts/qa/research-quality.json")
    if not research_exists:
        out["rqg"] = {"status": "NOT_APPLICABLE", "reason": "注册表未初始化（旧项目兼容）"}
    elif rqg is None:
        out["rqg"] = {"status": "SKIPPED_WITH_REASON",
                      "reason": "research-quality.json 不存在：由调度层先运行 RQG"}
    elif rqg.get("_corrupt"):
        out["rqg"] = {"status": "ERROR", "evidence": rqg["_corrupt"]}
    else:
        g = rqg.get("gate")
        m = {"PASS": "PASS", "PASS_WITH_HUMAN_REVIEW": "NEEDS_HUMAN_REVIEW",
             "FAIL": "FAIL", "not_initialized": "NOT_APPLICABLE", "ERROR": "ERROR"}
        out["rqg"] = {"status": m.get(g, "ERROR"), "gate": g,
                      "evidence": "artifacts/qa/research-quality.json"}

    # ④ Agent Loop 终态（design 在场时硬门禁）
    loop = _read_json(root, "artifacts/analysis/research-loop-log.json")
    if not design_exists:
        out["agent_loop"] = {"status": "NOT_APPLICABLE" if not research_exists
                             else "SKIPPED_WITH_REASON",
                             "reason": "无 design 注册表（旧项目/未运行）"}
    elif loop is None:
        out["agent_loop"] = {"status": "SKIPPED_WITH_REASON",
                             "reason": "research-loop-log.json 不存在：由调度层先运行 agent loop"}
    elif loop.get("_corrupt"):
        out["agent_loop"] = {"status": "ERROR", "evidence": loop["_corrupt"]}
    else:
        stt = loop.get("status")
        m = {"PASS": "PASS", "PASS_WITH_WARNINGS": "WARN", "WARN": "WARN",
             "PASS_WITH_HUMAN_REVIEW": "NEEDS_HUMAN_REVIEW", "BLOCK": "FAIL",
             "not_initialized": "NOT_APPLICABLE"}
        out["agent_loop"] = {"status": m.get(stt, "ERROR"), "loop_status": stt,
                             "open_findings": loop.get("open_findings") or [],
                             "evidence": "artifacts/analysis/research-loop-log.json"}

    # ⑤ 人工裁决队列（loop 队列：approve/reject/modify/deferred 之外的都算未裁决）
    pend = 0
    qp = os.path.join(root, ".aeromech", "research", "human-review-queue.yaml")
    if os.path.isfile(qp):
        try:
            import yaml as _y
            with open(qp, encoding="utf-8") as f:
                qd = _y.safe_load(f) or {}
            for it in qd.get("queue") or []:
                if not str(it.get("applied_status") or "").lower() in (
                        "approved", "rejected", "modified", "deferred",
                        "applied", "verified", "rejected_by_human",
                        "deferred_by_human"):
                    dec = it.get("decision")
                    if dec in (None, "", "needs_input"):
                        pend += 1
        except Exception:
            out["human_review"] = {"status": "ERROR", "reason": "human-review-queue.yaml 损坏"}
            return out, state, ctx
    out["human_review"] = {"status": "NEEDS_HUMAN_REVIEW" if pend else "PASS",
                           "pending": pend}
    return out, state, ctx


def delivery_gate_status(root):
    """交付门禁五态聚合（Phase 2 = 研究侧证据；格式链 QA 接入见 Phase 4 thesis_build）。
    规则（SKILL §16 / delivery-pipeline §8.3）：
      ERROR 证据缺失必 BLOCK（缺项=不得交付）；Critical/High open issues 未关 → BLOCK；
      loop BLOCK / RQG FAIL → BLOCK；loop PHR / RQG NHR / 队列未裁决 → PASS_WITH_HUMAN_REVIEW；
      WARN → PASS_WITH_WARNINGS；全 PASS → PASS。"""
    try:
        gs, state, ctx = gates(root)
    except TS.StateError as e:
        return {"status": "ERROR", "reasons": [f"state 不可读: {e}"], "missing": []}
    missing = sorted(k for k, g in gs.items() if g["status"] == "SKIPPED_WITH_REASON")
    hard_open = [i for i in TS._open_issues(state) if i.get("severity") in ("严重", "高")]
    reasons = []
    worst = "PASS"
    rank = {"PASS": 0, "PASS_WITH_WARNINGS": 1, "PASS_WITH_HUMAN_REVIEW": 2,
            "BLOCK": 3, "ERROR": 4}

    def bump(s, why):
        nonlocal worst
        if rank[s] > rank[worst]:
            worst = s
        reasons.append(why)

    if any(g["status"] == "ERROR" for g in gs.values()):
        bump("ERROR", "存在 ERROR 证据（注册表/报告损坏），不伪造结论")
    for k in ("feasibility", "rqg", "agent_loop"):
        st = gs[k]["status"]
        if st == "FAIL":
            bump("BLOCK", f"{k}=FAIL（{gs[k].get('verdict') or gs[k].get('gate') or gs[k].get('loop_status') or ''}）")
        elif st == "WARN":
            bump("PASS_WITH_WARNINGS", f"{k}=WARN 披露放行")
        elif st == "NEEDS_HUMAN_REVIEW":
            bump("PASS_WITH_HUMAN_REVIEW", f"{k} 待人工裁决")
    if gs["human_review"]["status"] == "NEEDS_HUMAN_REVIEW":
        bump("PASS_WITH_HUMAN_REVIEW", "human-review-queue 存在未裁决项")
    if missing:
        bump("BLOCK", f"QA 证据缺失（未执行≠通过）: {missing}")
    if hard_open:
        bump("BLOCK", "open_issue 严重/高 未关闭: " + ",".join(i["id"] for i in hard_open))
    return {"status": worst, "reasons": reasons, "missing": missing,
            "gates": {k: g["status"] for k, g in gs.items()}}


# ---------------- 路由主判定（只判定不执行） ----------------

def route(root):
    try:
        gs, state, ctx = gates(root)
    except TS.StateError as e:
        return {"status": "ERROR", "detail": str(e)}
    cur = (state.get("stage") or {}).get("current")
    if not cur:
        return {"status": "ERROR", "detail": "stage.current 为空（未初始化）"}
    stage_def = MATRIX[cur]

    def stage_complete(s):
        return all(_probe(root, state, e["probe"], ctx) for e in MATRIX[s]["exit"]) and bool(MATRIX[s]["exit"])

    completed = [s for s in STAGES if STAGES.index(s) < STAGES.index(cur) and stage_complete(s)]
    # 当前阶段出口产物齐备也算"已完成"（下一步=前进/交付，Orchestrator 据此不重做已完成任务）
    cur_complete = stage_complete(cur)
    if cur_complete:
        completed.append(cur)

    blocked, block_reason = False, ""
    # 研究完整性/闭环门禁在 S7+ 才作为 blocked 依据（S1-S6 阶段 RQG/loop 属"提前评估"，
    # 其 FAIL 不作为阶段推进的阻塞——设计类 INFEASIBLE 由 feasibility gate 独立把关，不受此限）
    quality_stage = STAGES.index(cur) >= STAGES.index("S7")
    # 硬门禁（§十三 + loop BLOCK + RQG FAIL + 证据 ERROR）：停留并给建议
    if gs["feasibility"]["status"] == "FAIL":
        blocked, block_reason = True, "feasibility INFEASIBLE：研究设计不可行，禁止进入写作/交付（停留本阶段或回退 S3）"
    if (gs["agent_loop"]["status"] == "FAIL" or gs["rqg"]["status"] == "FAIL") and quality_stage:
        blocked = True
        block_reason = block_reason or (
            f"RQG={gs['rqg'].get('gate')} / Agent Loop 终态 "
            f"{gs['agent_loop'].get('loop_status')}：按 issue→阶段映射回退")
    if any(g["status"] == "ERROR" for g in gs.values()):
        blocked, block_reason = True, "存在 ERROR 证据（损坏），修复前不得推进"

    # 前进建议
    pt = (state.get("project") or {}).get("paper_type")
    forward = stage_def["forward"]
    # forward 边的 prereq 引用出口产物 id → 映射为 probe 字符串
    exit_probe = {e["id"]: e["probe"] for e in stage_def["exit"]}
    cands = [e for e in forward
             if (not e.get("types") or pt in e["types"]) and not e.get("revert")]
    next_act = {"action": "stay", "to": None, "reason": ""}
    if blocked:
        # 回退建议：loop BLOCK 的 open_findings → 目标阶段（state.md §8 映射）
        tgt = None
        if gs["agent_loop"]["status"] == "FAIL":
            for f in gs["agent_loop"].get("open_findings", []):
                t = issue_target(f.get("issue_type"))
                if t and STAGES.index(t) <= STAGES.index(cur):
                    tgt = t
                    break
        if tgt:
            next_act = {"action": "revert", "to": tgt, "reason": block_reason}
        else:
            next_act = {"action": "stay", "to": None, "reason": block_reason}
    elif cur_complete:
        # 阶段内 AI 挂载点证据未生成（SKIPPED_WITH_REASON）→ 先运行，不猜测、不放行
        pending_ai = [f"{ai['id']}: {ai['tool']}" for ai in stage_def["ai"]
                      if gs.get(_gate_key_for(ai["id"]), {}).get("status") == "SKIPPED_WITH_REASON"]
        if pending_ai:
            next_act = {"action": "run_pending", "to": cur,
                        "reason": "出口产物齐但 AI 门禁证据未生成：先运行调度动作再前进",
                        "run": pending_ai}
        else:
            def _prereq_ok(p):
                if p in exit_probe:
                    return _probe(root, state, exit_probe[p], ctx)
                if p in GATE_PREREQ:
                    return gs[GATE_PREREQ[p]]["status"] in GATE_PASS_SET
                return _probe(root, state, p, ctx)
            for e in cands:
                if e["to"] in STAGES and STAGES.index(e["to"]) > STAGES.index(cur) and \
                        all(_prereq_ok(p) for p in e["prereq"]):
                    next_act = {"action": "advance", "to": e["to"],
                                "reason": "当前阶段出口产物齐备、AI 证据在位且无阻塞门禁"}
                    break
            else:
                missing = [e["desc"] for e in stage_def["exit"]
                           if not _probe(root, state, e["probe"], ctx)]
                missing += [p for p in (cands[0]["prereq"] if cands else [])
                            if not _prereq_ok(p)]
                next_act = {"action": "run_pending", "to": cur,
                            "reason": "前进前置（出口产物/门禁）未齐备", "missing": missing}
    else:
        missing = [e["desc"] for e in stage_def["exit"]
                   if not _probe(root, state, e["probe"], ctx)]
        next_act = {"action": "run_pending", "to": cur,
                    "reason": "当前阶段出口未齐备", "missing": missing}
    return {"status": "OK", "current": cur,
            "stages_completed": completed,
            "stage_complete": cur_complete,
            "blocked": blocked, "block_reason": block_reason,
            "gates": gs, "next": next_act,
            "ai_mounts": [ai["id"] for ai in stage_def["ai"]],
            "research_context_status": ctx["status"]}


def _gate_key_for(ai_id):
    """AI 挂载点 → 证据门禁 key（diagnosis 与 feasibility 共用 research-diagnosis.json 证据）。"""
    return {"feasibility": "feasibility", "diagnosis": "feasibility", "coverage": "rqg",
            "data_integrity": "rqg", "figure_traceability": "rqg",
            "agent_loop": "agent_loop", "full_qa": "agent_loop"}.get(ai_id, "rqg")


# forward prereq 中引用门禁态的符号（非 exit 产物 id）
GATE_PREREQ = {"feasibility_passed": "feasibility"}
GATE_PASS_SET = ("PASS", "WARN", "NOT_APPLICABLE")


def matrix():
    return json.loads(json.dumps(MATRIX, ensure_ascii=False))   # 深拷贝防外部篡改


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage Routing（v1.6，只判定不执行）")
    ap.add_argument("root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route")
    r.add_argument("--json", action="store_true")
    sub.add_parser("matrix")
    g = sub.add_parser("gate")
    g.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    if not os.path.isdir(os.path.join(root, ".aeromech")):
        print("未找到 .aeromech/（请先 thesis_state.py init）")
        return 2
    try:
        if a.cmd == "route":
            v = route(root)
            if a.json:
                print(json.dumps(v, ensure_ascii=False, indent=1))
            else:
                print(f"当前 {v['current']} · 阻塞={'是' if v['blocked'] else '否'}"
                      + (f"（{v['block_reason']}）" if v["blocked"] else ""))
                print(f"建议下一步：{v['next']}")
                for k, g2 in v["gates"].items():
                    print(f"  gate {k:<14} {g2['status']}")
            return 0 if v.get("status") != "ERROR" else 3
        if a.cmd == "matrix":
            print(json.dumps(matrix(), ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "gate":
            d = delivery_gate_status(root)
            print(json.dumps(d, ensure_ascii=False, indent=1) if a.json
                  else f"Delivery Gate: {d['status']}"
                  + "".join(f"\n  - {r_}" for r_ in d["reasons"]))
            return 0
    except TS.StateError as e:
        print(f"ERROR: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
