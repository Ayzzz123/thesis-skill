# -*- coding: utf-8 -*-
"""research_diagnosis.py — Research Diagnosis Engine（aeromech-thesis v1.5.0）

对研究现状做统一诊断：设计一致性 / 可行性 / 范围控制 / 一致性链 / 数字一致性 /
冲突 / RQG 结果 → DIAG-XXX 条目（issue_type / severity / 受影响节点 / 根因 /
证据 / 建议修复 / 置信度 / 自动可修 / 需人工）。

用法：
  python research_diagnosis.py <project_root> [--out <dir>] [--json] [--no-rqg]
退出码：0=无 critical/high；1=存在 critical/high；2=注册表未初始化；3=ERROR
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_integrity as RI
import research_quality_qa as RQ
import research_design as RD

# §13 Repair Priority：类别优先级（值越小越优先）
PRIORITY_CLASS = {
    "RQ_METHOD_MISMATCH": 0, "DESIGN_EVIDENCE_MISMATCH": 0, "METHOD_SELECTION_WEAK": 0,
    "SCOPE_OVERFLOW": 0, "SCOPE_UNDERFLOW": 0, "FEASIBILITY_BLOCK": 0,
    "EVIDENCE_GAP": 1, "DATA_GAP": 1, "UNRESOLVED_CONFLICT": 1, "CITATION_GAP": 1,
    "CLAIM_OVERSTRENGTH": 2, "CONCLUSION_OVERREACH": 2, "ABSTRACT_MISMATCH": 2,
    "CALCULATION_GAP": 3, "QUANTITATIVE_INCONSISTENCY": 3,
    "TRACEABILITY_GAP": 4, "DUPLICATE_ANALYSIS": 4, "REDUNDANT_CONTENT": 4,
    "ORPHAN_FIGURE": 5, "ORPHAN_TABLE": 5,
}
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# 各 issue_type 的建议修复选项（R-00x）——供人工队列与报告展示
REPAIR_OPTIONS = {
    "RQ_METHOD_MISMATCH": [
        {"id": "R-001", "repair_type": "REFRAME_RQ", "action": "收缩/重述研究问题，使其与所选方法能力一致"},
        {"id": "R-002", "repair_type": "CHANGE_METHOD", "action": "更换/增设能够满足该需求的方法（需重新论证选择依据）"},
        {"id": "R-003", "repair_type": "ADD_EVIDENCE", "action": "补充能够覆盖该需求的证据/数据（不得捏造）"},
    ],
    "DESIGN_EVIDENCE_MISMATCH": [
        {"id": "R-001", "repair_type": "REFRAME_RQ", "action": "把 RQ 收缩为模拟数据可回答的形式并显式限定"},
        {"id": "R-002", "repair_type": "ADD_EVIDENCE", "action": "获取真实世界数据/已核实证据后再回答该 RQ"},
        {"id": "R-003", "repair_type": "LIMIT_SCOPE", "action": "把该 RQ 移出范围并在 scope.excluded 登记"},
    ],
    "METHOD_SELECTION_WEAK": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "补齐候选方法对比与选择/拒绝理由（方法选择论证）"},
    ],
    "SCOPE_OVERFLOW": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "修改越界段落，回归注册范围"},
        {"id": "R-002", "repair_type": "REFRAME_RQ", "action": "更新 Research Design / Scope 并说明扩展理由（设计更新后方可保留）"},
    ],
    "SCOPE_UNDERFLOW": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "补充 in-scope 但未覆盖的设定内容，或收敛 scope"},
    ],
    "EVIDENCE_GAP": [
        {"id": "R-001", "repair_type": "ADD_EVIDENCE", "action": "补充可核实证据（用户提供/检索核验；不得捏造）"},
        {"id": "R-002", "repair_type": "REVISE_CONCLUSION", "action": "收敛依赖该证据的结论强度并标注【待核实】"},
    ],
    "DATA_GAP": [
        {"id": "R-001", "repair_type": "ADD_EVIDENCE", "action": "补充数据来源/出处，或登记为模拟并保持 label"},
        {"id": "R-002", "repair_type": "REVISE_CLAIM", "action": "收敛依赖该数据的论断"},
    ],
    "UNRESOLVED_CONFLICT": [
        {"id": "R-001", "repair_type": "REQUEST_HUMAN_REVIEW", "action": "人工裁定来源取舍并填写 resolution/reason"},
    ],
    "CITATION_GAP": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "在正文相应论断处补引用编号（不得凭空造来源）"},
        {"id": "R-002", "repair_type": "ADD_EVIDENCE", "action": "确系未使用的注册文献退回未注册状态（清理登记表）"},
    ],
    "CLAIM_OVERSTRENGTH": [
        {"id": "R-001", "repair_type": "REVISE_CLAIM", "action": "论断强度降级（C4→C2/C1），保持技术事实不变"},
        {"id": "R-002", "repair_type": "ADD_EVIDENCE", "action": "补充与论断强度匹配的证据"},
    ],
    "CONCLUSION_OVERREACH": [
        {"id": "R-001", "repair_type": "REVISE_CONCLUSION", "action": "结论降级并加模拟条件限定"},
        {"id": "R-002", "repair_type": "ADD_EVIDENCE", "action": "补充支撑该结论强度的证据"},
        {"id": "R-003", "repair_type": "REVISE_CONCLUSION", "action": "删除超出证据能力的结论"},
    ],
    "ABSTRACT_MISMATCH": [
        {"id": "R-001", "repair_type": "REVISE_ABSTRACT", "action": "按正文/结论同步修正摘要（数值与措辞）"},
    ],
    "CALCULATION_GAP": [
        {"id": "R-001", "repair_type": "RECALCULATE", "action": "按注册的 recompute 命令重新执行计算并登记验证"},
        {"id": "R-002", "repair_type": "REQUEST_HUMAN_REVIEW", "action": "人工复核计算输入与公式"},
    ],
    "QUANTITATIVE_INCONSISTENCY": [
        {"id": "R-001", "repair_type": "REVISE_ABSTRACT", "action": "把摘要数字同步为正文/计算的基准值"},
        {"id": "R-002", "repair_type": "REQUEST_HUMAN_REVIEW", "action": "人工确认哪一处为准（可能正文有误）"},
    ],
    "TRACEABILITY_GAP": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "补齐链路上的注册条目（claims/analyses/evidence）"},
    ],
    "ORPHAN_FIGURE": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "为图表建立论证链接并补正文引用"},
    ],
    "ORPHAN_TABLE": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "为表格建立论证链接并补正文引用"},
    ],
    "DUPLICATE_ANALYSIS": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION",
         "action": "合并重复分析或改写其一使其产生新增论证（不得自动删除注册条目）"},
    ],
    "REDUNDANT_CONTENT": [
        {"id": "R-001", "repair_type": "REWRITE_SECTION", "action": "删并重复段落或改写为递进表述（保留技术内容）"},
    ],
    "FEASIBILITY_BLOCK": [
        {"id": "R-001", "repair_type": "REQUEST_HUMAN_REVIEW", "action": "人工复核研究设计（INFEASIBLE：需重构设计后方可继续）"},
    ],
}

# §9 根因分析：问题对研究有效性的影响（Impact）
IMPACT_BY_TYPE = {
    "RQ_METHOD_MISMATCH": "研究问题无法由所选方法回答，结论将缺乏方法学支撑",
    "DESIGN_EVIDENCE_MISMATCH": "设计承诺与可得证据不匹配，研究声称超出可实现范围",
    "METHOD_SELECTION_WEAK": "方法选择缺少论证，无法证明研究路径的合理性",
    "EVIDENCE_GAP": "关键论断缺少可核实证据，论证链在此处断裂",
    "CITATION_GAP": "注册文献证据未被正文使用，引用完整性与来源-论断对应关系受损",
    "DATA_GAP": "分析输入不完整或来源不可追，结果可复现性受损",
    "CLAIM_OVERSTRENGTH": "论断强度超过证据能力，读者会高估结论可靠性",
    "CONCLUSION_OVERREACH": "结论超出证据支持范围，可能构成研究性失实",
    "ABSTRACT_MISMATCH": "摘要与正文口径不一致，摘要向读者传递了未成立的信息",
    "QUANTITATIVE_INCONSISTENCY": "同一结果在不同位置数值不同，研究结论的数据一致性受损",
    "CALCULATION_GAP": "计算未复核或不可重算，下游表格/论断的数值缺少依据",
    "TRACEABILITY_GAP": "追踪链断裂，无法从结论回溯到证据与分析",
    "SCOPE_OVERFLOW": "研究范围被擅自扩大，结论适用范围与注册设计不一致",
    "SCOPE_UNDERFLOW": "注册范围内的问题未被回答，研究完整性不足",
    "DUPLICATE_ANALYSIS": "分析重复但无新增论证，研究工作量与结论支撑被高估",
    "REDUNDANT_CONTENT": "内容重复导致论证密度下降，易被误读为独立证据",
    "ORPHAN_FIGURE": "图未参与论证（装饰性），其结论支撑作用不成立",
    "ORPHAN_TABLE": "表未参与论证（装饰性），其结论支撑作用不成立",
    "UNRESOLVED_CONFLICT": "来源冲突未裁定，相关结论存在二义性",
    "FEASIBILITY_BLOCK": "研究设计层面不可行，按当前设计无法产生可交付结论",
}
DEFAULT_IMPACT = "该问题削弱研究结论的可信度与可追溯性"

# 自动修复资格：仅白名单类型 + 上下文条件（在 _classify 内细化）
AUTO_ELIGIBLE = {"CLAIM_OVERSTRENGTH", "CONCLUSION_OVERREACH", "ABSTRACT_MISMATCH",
                 "QUANTITATIVE_INCONSISTENCY", "CALCULATION_GAP"}

# 人工判定类（disposition=queue）：待人类裁决期间记 NEEDS_HUMAN_REVIEW（不按 High 直接 BLOCK）
# 其余 critical/high 未解决项按 Integrity Failure 处理 → BLOCK
JUDGMENT_TYPES = {"RQ_METHOD_MISMATCH", "DESIGN_EVIDENCE_MISMATCH", "METHOD_SELECTION_WEAK",
                  "SCOPE_OVERFLOW", "SCOPE_UNDERFLOW", "UNRESOLVED_CONFLICT"}

# ---------------- Claim Strength Model（§7：Claim Strength ≤ Evidence Strength）----------------
# 论断强度（由高到低匹配；C4 为最强断言）
CLAIM_LEVELS = [
    ("C4", ["必然", "确定", "一定是", "显著导致"]),
    ("C3", ["支持", "证明", "证实"]),
    ("C2", ["表明", "提示", "说明", "显示"]),
    ("C1", ["可能", "可以", "或许", "推测"]),
]
CLAIM_RANK = {"C1": 1, "C2": 2, "C3": 3, "C4": 4}
ES_RANK = {"ES1": 1, "ES2": 2, "ES3": 3, "ES4": 4}
# 各证据强度允许的最高论断强度（弱证据只允许弱断言）
MAX_CLAIM_BY_ES = {"ES1": "C2", "ES2": "C3", "ES3": "C4", "ES4": "C4"}
# 一手产出型证据（实验/计算/仿真本身）→ ES4
DIRECT_EVIDENCE_TYPES = {"experiment", "calculation", "simulation"}


def claim_strength(text):
    """返回文本的论断强度等级 C1~C4（无断言词返回 None）。"""
    t = str(text or "")
    for level, pats in CLAIM_LEVELS:
        if any(p in t for p in pats):
            return level
    return None


def evidence_strength(statuses, types=()):
    """证据强度 ES1~ES4：statuses 为 verification_status 集合，types 为证据/数据集类型集合。"""
    statuses = [str(s) for s in (statuses or [])]
    types = {str(t) for t in (types or ())}
    if not statuses:
        return None
    if any(s == "verified" for s in statuses):
        return "ES4" if types & DIRECT_EVIDENCE_TYPES else "ES3"
    if any(s == "partial" for s in statuses):
        return "ES2"
    return "ES1"


NEGATION_RE = re.compile(
    r"(?:不|非|未|无法|难以|不足以|尚)(?:能|会|应|足以|曾|直接|尚)?\s*"
    r"(?:必然|确定|一定|显著|证明|证实|表明|说明|支持)")


def is_negated(text):
    """否定/免责式表述（"不能证明""尚未证实"）不构成强断言。"""
    return bool(NEGATION_RE.search(str(text or "")))


def strength_violation(c_level, es_level):
    """返回 (是否越界, 允许上限)。"""
    if not c_level or not es_level:
        return False, None
    cap = MAX_CLAIM_BY_ES.get(es_level)
    return CLAIM_RANK[c_level] > CLAIM_RANK[cap], cap


def _disposition(issue_type, auto):
    if auto and issue_type in AUTO_ELIGIBLE:
        return "auto"
    if issue_type in JUDGMENT_TYPES:
        return "queue"
    return "block"


class _DiagBuilder:
    def __init__(self):
        self.items = []
        self.n = 0
        self._seen = set()

    def add(self, issue_type, severity, detail, nodes, root_cause, evidence,
            repair_type, operation, payload, confidence, auto, rule, target=None):
        # severity 归一到统一小写词表（RQG 派生项携带 "Critical/High/…" 首字母大写形态；
        #不归一则 SEV_ORDER/counts/SEV_HARD 的 lowercase 比较会漏计——B 类伴生缺陷修复）
        severity = str(severity or "medium").lower()
        try:
            pkey = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, default=str)
        except Exception:
            pkey = str(payload)
        key = (issue_type, ",".join(str(x) for x in (nodes or [])), rule, pkey)
        if key in self._seen:
            return
        self._seen.add(key)
        self.n += 1
        auto_ok = bool(auto) and issue_type in AUTO_ELIGIBLE
        # 稳定 ID 键含 severity：同一（type,nodes,rule）不同严重度的条目必须可分别裁决
        # （B9：human-review-queue 以 diagnosis_id 为键，ID 碰撞会使一条决定误关多条诊断）
        nkey = f"{issue_type}|{','.join(str(x) for x in nodes)}|{rule}|{severity}"
        stable = hashlib.md5(nkey.encode("utf-8")).hexdigest()[:6].upper()
        self.items.append({
            "diagnosis_id": f"DIAG-{stable}",
            "issue_type": issue_type,
            "severity": severity,
            "priority_class": PRIORITY_CLASS.get(issue_type, 4),
            "disposition": _disposition(issue_type, auto_ok),
            "affected_nodes": [str(x) for x in nodes],
            "detail": detail,
            "root_cause": root_cause,
            "impact": IMPACT_BY_TYPE.get(issue_type, DEFAULT_IMPACT),
            "evidence": [str(x) for x in evidence],
            "recommended_repair": {"repair_type": repair_type, "operation": operation,
                                   "target": target or (nodes[0] if nodes else None),
                                   "payload": payload or {}},
            "repair_options": REPAIR_OPTIONS.get(issue_type, []),
            "confidence": confidence,
            "auto_repairable": auto_ok,
            "human_review_required": not auto_ok,
            "rule": rule,
            "status": "open",
        })


def _num(s):
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(s))
    return float(m.group(1)) if m else None


def _num_close(a, b, lo=0.005, hi=0.10):
    """返回 'eq'（≤0.5%，视为同一结果）/ 'near'（0.5%~10%，疑似不一致）/ None。"""
    fa, fb = _num(a), _num(b)
    if fa is None or fb is None:
        return None
    if fa == fb:
        return "eq"
    base = max(abs(fa), abs(fb), 1e-9)
    d = abs(fa - fb) / base
    if d <= lo:
        return "eq"
    if d <= hi:
        return "near"
    return None


def _near_score(cand, fnum, calc_nums):
    """near 候选的排序键（越小越优）：先算出处的值，其次与摘要值的相对差。"""
    bnum = cand[0]
    try:
        d = abs(float(_num(bnum)) - float(_num(fnum))) / max(abs(float(_num(bnum))), abs(float(_num(fnum))), 1e-9)
    except (TypeError, ValueError):
        d = 1.0
    return (0 if bnum in calc_nums else 1, d)


def _sentence_with(text, term):
    """返回首个包含 term 的句子（用于给人工修复提供待替换原文）。"""
    for sent in re.split(r"[。；！？!?;\n]", text or ""):
        if term in sent:
            return sent.strip()
    return ""


def _texts(root):
    with contextlib.redirect_stdout(io.StringIO()):
        return RQ.load_texts(root)


def diagnose(root, pdf=None, use_rqg=True):
    errors = []
    data = RI.load_all(root, collect_errors=errors)
    if not RI.initialized(root):
        return {"status": "not_initialized", "diagnoses": [],
                "reason": "Research Integrity 注册表未初始化"}
    b = _DiagBuilder()
    texts = _texts(root)
    chapters = texts.get("chapters", "")
    front = texts.get("front", "")

    # ---------- A. 设计一致性 / 方法选择 ----------
    da = RD.analyze(root, data=data)
    for f in da.get("findings", []):
        it = {"RQ_METHOD_MISMATCH": "RQ_METHOD_MISMATCH",
              "DESIGN_EVIDENCE_MISMATCH": "DESIGN_EVIDENCE_MISMATCH",
              "EVIDENCE_GAP": "EVIDENCE_GAP", "DATA_GAP": "DATA_GAP",
              "TRACEABILITY_GAP": "TRACEABILITY_GAP",
              "METHOD_SELECTION_WEAK": "METHOD_SELECTION_WEAK"}.get(f["code"], f["code"])
        opts = REPAIR_OPTIONS.get(it, [])
        rec = opts[0] if opts else {"repair_type": "REQUEST_HUMAN_REVIEW", "action": "人工复核"}
        b.add(it, f["severity"], f["detail"], f.get("nodes") or [], 
              root_cause=f.get("detail"), evidence=[f.get("rule", "")],
              repair_type=rec["repair_type"], operation=None, payload={"option": rec["id"]},
              confidence="high" if f["severity"] in ("critical", "high") else "medium",
              auto=False, rule=f.get("rule", ""))

    # ---------- B. 可行性 ----------
    feas = RD.feasibility(root, data=data)
    if feas["verdict"] == "INFEASIBLE":
        fails = [c for c in feas["checks"] if c["status"] == "FAIL"]
        b.add("FEASIBILITY_BLOCK", "critical",
              "研究可行性门禁 INFEASIBLE：" + "；".join(f"{c['rule']} {c['detail']}" for c in fails),
              ["DESIGN"], root_cause="研究设计层面存在不可行项（RF FAIL）：" + ", ".join(c["rule"] for c in fails),
              evidence=[c["rule"] for c in fails], repair_type="REQUEST_HUMAN_REVIEW",
              operation=None, payload={}, confidence="high", auto=False, rule="RF-GATE")

    # ---------- C. 范围控制（scope creep）----------
    scope = da.get("scope") or {}
    if scope:
        for lay_term in scope.get("included") or []:
            term = str(lay_term).strip()
            if term and term not in chapters and len(term) >= 3:
                b.add("SCOPE_UNDERFLOW", "medium",
                      f"scope.included 项「{term}」未在正文出现（研究设定未覆盖）", ["SCOPE"],
                      root_cause="正文未覆盖注册在范围内的问题域", evidence=["scope.yaml"],
                      repair_type="REWRITE_SECTION", operation=None, payload={"term": term},
                      confidence="medium", auto=False, rule="SC-02/included-coverage")
        for ex_term in scope.get("excluded") or []:
            term = str(ex_term).strip()
            if not term or len(term) < 3:
                continue
            cnt = chapters.count(term)
            if cnt >= 2:
                b.add("SCOPE_OVERFLOW", "high",
                      f"正文出现 scope.excluded 项「{term}」×{cnt}（疑似范围蔓延 scope creep）", ["SCOPE"],
                      root_cause=f"写作阶段引入范围外主题「{term}」，与注册 Scope Boundary 不一致",
                      evidence=["scope.yaml", f"章节文本命中 {cnt} 次"],
                      repair_type="REWRITE_SECTION", operation=None,
                      payload={"term": term, "old": _sentence_with(chapters, term)},
                      confidence="medium", auto=False, rule="SC-01/excluded-hit")
            elif cnt == 1:
                b.add("SCOPE_OVERFLOW", "medium",
                      f"正文提及 scope.excluded 项「{term}」×1（需确认是背景性提及还是范围外延）", ["SCOPE"],
                      root_cause=f"范围外主题「{term}」在正文出现一次", evidence=["scope.yaml"],
                      repair_type="REWRITE_SECTION", operation=None,
                      payload={"term": term, "old": _sentence_with(chapters, term)},
                      confidence="low", auto=False, rule="SC-01/excluded-hit")

    # ---------- D. RQG 结果消费 ----------
    rqg_summary = None
    if use_rqg:
        with contextlib.redirect_stdout(io.StringIO()):
            rqg_summary, rqg_rep = RQ.run(root)
        ev_by_id = {str(e.get("id")): e for e in (data.get("evidence") or [])}
        ds_by_id = {str(d.get("id")): d for d in (data.get("datasets") or [])}

        def _ev_refs(claim):
            """返回 (verification_status 列表, 证据/数据集类型列表)。"""
            sts, types = [], []
            for r in claim.get("evidence_ids") or []:
                if str(r) in ev_by_id:
                    sts.append(str(ev_by_id[str(r)].get("verification_status")))
                    types.append(str(ev_by_id[str(r)].get("type")))
                elif str(r) in ds_by_id:
                    dt = str(ds_by_id[str(r)].get("type"))
                    types.append(dt)
                    sts.append("simulated" if dt in ("simulated", "assumption") else "verified")
            for a in claim.get("analysis_ids") or []:
                an = next((x for x in (data.get("analyses") or []) if str(x.get("id")) == str(a)), None)
                for inp in (an or {}).get("inputs") or []:
                    ref = str(inp.get("ref", ""))
                    if ref in ds_by_id:
                        dt = str(ds_by_id[ref].get("type"))
                        types.append(dt)
                        sts.append("simulated" if dt in ("simulated", "assumption") else "verified")
                    elif ref in ev_by_id:
                        sts.append(str(ev_by_id[ref].get("verification_status")))
                        types.append(str(ev_by_id[ref].get("type")))
            return sts, types

        # ---- D0. Claim Strength × Evidence Strength（§7：C1~C4 × ES1~ES4；技术事实不变）----
        for c in data.get("claims") or []:
            st = claim_strength(c.get("claim", ""))
            es_sts, es_types = _ev_refs(c)
            es = evidence_strength(es_sts, es_types)
            bad, cap = strength_violation(st, es)
            if bad and not is_negated(c.get("claim", "")):
                b.add("CLAIM_OVERSTRENGTH", "critical" if (st == "C4" and es == "ES1") else "high",
                      f"{c.get('id')} 表述强度 {st} 超过证据强度 {es} 允许上限 {cap}"
                      f"（证据为 simulated/pending 口径）",
                      [str(c.get("id"))],
                      root_cause=f"弱证据（{es}）支撑 {st} 表述；按 §7 降级强度且不改技术事实",
                      evidence=[str(c.get("claim", ""))[:60]],
                      repair_type="REVISE_CLAIM", operation="downgrade_wording",
                      payload={"claim_id": str(c.get("id"))}, confidence="high", auto=True,
                      rule="§7/claim-strength")
        for c in data.get("conclusions") or []:
            st = claim_strength(c.get("conclusion", ""))
            con_refs = {"evidence_ids": c.get("evidence") or [], "analysis_ids": c.get("analyses") or []}
            es_sts, es_types = _ev_refs(con_refs)
            es = evidence_strength(es_sts, es_types)
            bad, cap = strength_violation(st, es)
            if bad and not is_negated(c.get("conclusion", "")):
                b.add("CONCLUSION_OVERREACH", "critical" if (st == "C4" and es == "ES1") else "high",
                      f"{c.get('id')} 结论强度 {st} 超过证据强度 {es} 允许上限 {cap}"
                      f"（证据为 simulated/pending 口径）",
                      [str(c.get("id"))],
                      root_cause=f"弱证据（{es}）支撑 {st} 结论；需降级并加模拟条件限定",
                      evidence=[str(c.get("conclusion", ""))[:60]],
                      repair_type="REVISE_CONCLUSION", operation="downgrade_wording",
                      payload={"claim_id": str(c.get("id"))}, confidence="high", auto=True,
                      rule="§7/claim-strength")

        for item in rqg_rep.fails:
            code, sev, detail = item["code"], item["severity"], item["detail"]
            ids = re.findall(r"(CL-\d{2,3}|CON-\d{2,3}|E-\d{2,3}|DS-\d{2,3}|CALC-\d{2,3}|FIG-\d{2,3}|TABLE-\d{2,3})", detail)
            if code == "RQG-10":
                for nid in [i for i in ids if i.startswith(("CL-", "CON-"))]:
                    is_con = nid.startswith("CON-")
                    rec = REPAIR_OPTIONS["CONCLUSION_OVERREACH" if is_con else "CLAIM_OVERSTRENGTH"][0]
                    b.add("CONCLUSION_OVERREACH" if is_con else "CLAIM_OVERSTRENGTH",
                          "critical" if sev == "Critical" else "high",
                          f"{nid} 存在强断言×弱证据（RQG-10）：{detail}",
                          [nid],
                          root_cause=f"{nid} 的证据全为 simulated/pending，表述强度超过证据能力",
                          evidence=[detail], repair_type=rec["repair_type"],
                          operation="downgrade_wording" if rec["repair_type"] in
                          ("REVISE_CLAIM", "REVISE_CONCLUSION") else None,
                          payload={"claim_id": nid}, confidence="high", auto=True, rule="RQG-10")
            elif code == "RQG-09":
                # 数字/身份措辞不一致 → 交给 E/F 检测器细化为 QUANTITATIVE/ABSTRACT；此处记录身份类
                if "实测" in detail or "试验" in detail:
                    b.add("ABSTRACT_MISMATCH", "critical" if sev == "Critical" else "high",
                          f"摘要身份措辞越界（RQG-09）：{detail}", ["ABSTRACT"],
                          root_cause="摘要把模拟数据表述为真实口径",
                          evidence=[detail], repair_type="REVISE_ABSTRACT",
                          operation="downgrade_wording", payload={},
                          confidence="high", auto=True, rule="RQG-09/b")
            elif code == "RQG-06":
                dsids = [i for i in ids if i.startswith("DS-")]
                b.add("DATA_GAP", sev, f"模拟数据标记缺失（RQG-06）：{detail}", dsids,
                      root_cause="模拟数据集缺少 label 或 label 未进入文档",
                      evidence=[detail], repair_type="REVISE_CLAIM", operation="fix_synth_label",
                      payload={"datasets": dsids}, confidence="high", auto=False, rule="RQG-06")
            elif code == "RQG-08":
                b.add("TRACEABILITY_GAP", sev, f"结论断链（RQG-08）：{detail}",
                      [i for i in ids if i.startswith("CON-")],
                      root_cause="结论缺少 claims/analyses 回溯链", evidence=[detail],
                      repair_type="REWRITE_SECTION", operation=None, payload={},
                      confidence="high", auto=False, rule="RQG-08")
            elif code == "RQG-11":
                for nid in ids:
                    if nid.startswith("FIG-") or nid.startswith("TABLE-"):
                        b.add("ORPHAN_FIGURE" if nid.startswith("FIG-") else "ORPHAN_TABLE",
                              "medium", f"图表无论证链接（RQG-11）：{nid}", [nid],
                              root_cause="图表未关联 RQ/分析/论断，属装饰性图表",
                              evidence=[detail], repair_type="REWRITE_SECTION", operation=None,
                              payload={}, confidence="medium", auto=False, rule="RQG-11")
            elif code == "RQG-12":
                b.add("CITATION_GAP", sev, f"注册文献证据未被正文使用（RQG-12）：{detail}",
                      ids, root_cause="文献登记与正文引用不同步（引用完整性受损）", evidence=[detail],
                      repair_type="ADD_EVIDENCE", operation=None, payload={},
                      confidence="medium", auto=False, rule="RQG-12")
            elif code == "RQG-13":
                b.add("TRACEABILITY_GAP", "medium", f"正文数字可追溯率不足（RQG-13）：{detail}",
                      [], root_cause="含数字句缺少引用/计算标注", evidence=[detail],
                      repair_type="REWRITE_SECTION", operation=None, payload={},
                      confidence="medium", auto=False, rule="RQG-13")
            elif code == "RQG-14":
                calcs = [i for i in ids if i.startswith("CALC-")]
                for cid in calcs or [None]:
                    calc = next((c for c in (data.get("computations") or []) if str(c.get("id")) == cid), {}) if cid else {}
                    has_re = bool(str(calc.get("recompute", "")).strip())
                    rec = REPAIR_OPTIONS["CALCULATION_GAP"][0 if has_re else 1]
                    b.add("CALCULATION_GAP", sev, f"计算溯源/验证不足（RQG-14）：{detail}",
                          [cid] if cid else [],
                          root_cause="计算缺少 inputs/formula/verification" + ("；可执行 recompute" if has_re else "；未注册 recompute"),
                          evidence=[detail], repair_type=rec["repair_type"],
                          operation="recompute" if has_re else None,
                          payload={"calc_id": cid, "recompute": calc.get("recompute")},
                          confidence="high", auto=has_re, rule="RQG-14")
            elif code.startswith("RQG-0") and sev in ("Critical", "High"):
                b.add({"RQG-00": "TRACEABILITY_GAP"}.get(code, "TRACEABILITY_GAP"), sev,
                      f"{code}：{detail}", ids, root_cause="研究完整性注册表问题（见 RQG 报告）",
                      evidence=[detail], repair_type="REQUEST_HUMAN_REVIEW", operation=None,
                      payload={}, confidence="high", auto=False, rule=code)

        # 未解决冲突（不静默选择）
        for c in data.get("conflicts") or []:
            if str(c.get("status")) == "pending":
                b.add("UNRESOLVED_CONFLICT", "high",
                      f"未解决来源冲突（禁止静默选择）：{c.get('conflict')}", [str(c.get("id"))],
                      root_cause=f"{c.get('source_a')} 与 {c.get('source_b')} 冲突，尚待人工裁定",
                      evidence=[str(c.get("conflict")), "resolution=" + str(c.get("resolution"))],
                      repair_type="REQUEST_HUMAN_REVIEW", operation=None, payload={},
                      confidence="high", auto=False, rule="CONFLICT/pending")

    # ---------- E. Coherence（结论→摘要覆盖）----------
    cons = data.get("conclusions") or []
    if cons and front.strip():
        covers = 0
        for c in cons:
            kw = RQ.keywords_of(c.get("conclusion"))
            if kw and len(kw & RQ.keywords_of(front)) / len(kw) >= 0.4:
                covers += 1
        if covers < len(cons):
            miss = [str(c.get("id")) for c in cons
                    if not (RQ.keywords_of(c.get("conclusion")) &
                            RQ.keywords_of(front)) or
                    len(RQ.keywords_of(c.get("conclusion")) & RQ.keywords_of(front)) /
                    max(len(RQ.keywords_of(c.get("conclusion")) or {1}), 1) < 0.4]
            b.add("ABSTRACT_MISMATCH", "medium",
                  f"摘要对结论的覆盖不足（{covers}/{len(cons)}）", miss,
                  root_cause="部分核心结论未在摘要中体现（Coherence: Conclusion→Abstract）",
                  evidence=["keyword coverage < 0.4"], repair_type="REVISE_ABSTRACT",
                  operation=None, payload={}, confidence="medium", auto=False, rule="COH-08")

    # ---------- E2. 孤立图表（registry 级，独立于 RQG 状态）----------
    for f in data.get("figures") or []:
        links = ((f.get("related_rqs") or []) + (f.get("related_analyses") or [])
                 + (f.get("related_claims") or []))
        if not links:
            fid = str(f.get("id"))
            b.add("ORPHAN_FIGURE" if fid.startswith("FIG-") else "ORPHAN_TABLE", "medium",
                  f"{fid} 无论证链接（孤立图表，未参与论证）", [fid],
                  root_cause="图表未关联任何 RQ/分析/论断（装饰性图表）",
                  evidence=["figures.yaml"], repair_type="REWRITE_SECTION", operation=None,
                  payload={}, confidence="high", auto=False, rule="FIG-ORPHAN")

    # ---------- E3. 重复分析 / 内容冗余（§8 DUPLICATE_ANALYSIS / REDUNDANT_CONTENT）----------
    seen_sig = {}
    for a in data.get("analyses") or []:
        method = str(a.get("method", "")).strip().lower()
        refs = tuple(sorted(str(i.get("ref")) for i in (a.get("inputs") or [])))
        outs = tuple(sorted(str(o) for o in (a.get("outputs") or [])))
        if not method or not refs:
            continue  # 登记不完整时不判重（避免把缺字段误判为重复分析）
        sig = (method, refs, outs)
        aid = str(a.get("id"))
        if sig in seen_sig:
            prev = seen_sig[sig]
            b.add("DUPLICATE_ANALYSIS", "medium",
                  f"{prev} 与 {aid} 的方法/输入/输出完全相同（重复分析，未产生新增论证）",
                  [prev, aid],
                  root_cause=f"同一分析被登记两次（method={a.get('method')}, inputs={list(refs)}）",
                  evidence=[f"outputs={list(outs)}", "analyses.yaml"],
                  repair_type="REWRITE_SECTION", operation=None,
                  payload={"ids": [prev, aid]}, confidence="high", auto=False,
                  rule="DUP-01/analysis-signature")
        else:
            seen_sig[sig] = aid

    para_counts = {}
    for para in re.split(r"\n\s*\n", chapters or ""):
        key = RQ.nz(para)
        if len(key) >= 40:
            para_counts[key] = para_counts.get(key, 0) + 1
    for key in sorted(k for k, v in para_counts.items() if v >= 2):
        b.add("REDUNDANT_CONTENT", "medium",
              f"段落原样重复出现 {para_counts[key]} 次（内容冗余）：{key[:40]}…", ["CHAPTERS"],
              root_cause="写作阶段复制粘贴，同一表述在多处重复",
              evidence=[key[:120]], repair_type="REWRITE_SECTION", operation=None,
              payload={"fragment": key[:80]}, confidence="high", auto=False,
              rule="RED-01/paragraph-dup")

    # ---------- F. 数字一致性（§16）----------
    body_text = texts.get("chapters", "") + "\n" + texts.get("conclusion", "")
    body_nums = RQ.numbers_of(body_text)
    front_nums = RQ.numbers_of(front)
    calc_nums = set()
    for c in data.get("computations") or []:
        calc_nums |= RQ.numbers_of(str(c.get("output", "")))
    for fnum in sorted(front_nums):
        if fnum in body_nums:
            continue
        best = None
        for bnum in body_nums:
            rel = _num_close(fnum, bnum)
            if rel == "eq":
                best = (bnum, "eq")
                break
            if rel == "near":
                # 基准选择：优先带计算出处的候选，其次相对差最小者——
                # 不得取"先遇到"的近似值（多个近邻数值并存时会把摘要同步到错误基准）
                cand = (bnum, "near")
                if best is None or _near_score(cand, fnum, calc_nums) < _near_score(best, fnum, calc_nums):
                    best = cand
        if best and best[1] == "near":
            canonical = best[0]
            prov = canonical in calc_nums
            b.add("QUANTITATIVE_INCONSISTENCY", "high",
                  f"摘要数值 {fnum} 与正文 {canonical} 疑似同一结果但不一致", ["ABSTRACT"],
                  root_cause=f"摘要数字与正文/计算基准不一致（正文 {canonical}"
                             + ("，来自计算输出" if prov else "") + "）",
                  evidence=[f"abstract={fnum}", f"body={canonical}"],
                  repair_type="REVISE_ABSTRACT", operation="number_sync",
                  payload={"old": fnum, "new": canonical, "canonical_in_calc": prov},
                  confidence="high" if prov else "medium", auto=True, rule="QC-01/number-sync")
        elif best is None:
            # 摘要独立数值且与正文无任何近似匹配：无法自动判定基准 → 人工核对
            b.add("ABSTRACT_MISMATCH", "high",
                  f"摘要数值 {fnum} 在正文中找不到对应（无法确认是否同一结果）", ["ABSTRACT"],
                  root_cause="摘要与正文的数字口径不一致或正文缺失该结果",
                  evidence=[f"abstract={fnum}"], repair_type="REVISE_ABSTRACT",
                  operation=None, payload={"number": fnum, "old": fnum}, confidence="medium",
                  auto=False, rule="QC-02/no-counterpart")

    # ---------- G. TRACEABILITY（设计覆盖 RQ）----------
    if da.get("status") == "ok" and da.get("design"):
        d_rqs = set(str(x) for x in (da["design"].get("research_questions") or []))
        for r in data.get("rq") or []:
            if str(r.get("id")) not in d_rqs:
                b.add("TRACEABILITY_GAP", "high",
                      f"{r.get('id')} 未登记进 Research Design（设计→RQ 链缺口）", [str(r.get("id"))],
                      root_cause="RQ 建立后未回填 design.research_questions",
                      evidence=["design.yaml"], repair_type="REWRITE_SECTION", operation=None,
                      payload={}, confidence="high", auto=False, rule="DSG-01/rq-coverage")

    # 消费 human-review-queue 裁决（reject=关闭；deferred=人工承诺后续处理 → 视为待复核类）
    try:
        qp = os.path.join(root, ".aeromech", "research", "human-review-queue.yaml")
        if os.path.isfile(qp):
            import yaml as _yaml
            qd = _yaml.safe_load(open(qp, encoding="utf-8")) or {}
            st_map = {str(e.get("diagnosis_id")): str(e.get("applied_status") or "")
                      for e in (qd.get("queue") or [])}
            for it in b.items:
                st = st_map.get(it["diagnosis_id"], "")
                if st == "rejected_by_human":
                    it["status"] = "rejected_by_human"
                elif st == "deferred":
                    it["status"] = "deferred_by_human"
    except Exception:
        pass

    # 排序：§13 优先级（类别 → 严重度）
    items = sorted(b.items, key=lambda x: (x["priority_class"], SEV_ORDER.get(x["severity"], 9),
                                           x["diagnosis_id"]))
    open_items = [x for x in items if x["status"] == "open"]
    deferred = [x for x in items if x["status"] == "deferred_by_human"]
    return {"status": "ok", "diagnoses": items,
            "feasibility": feas, "rqg_gate": (rqg_summary or {}).get("gate"),
            "rqg_needs_human_review": (rqg_summary or {}).get("needs_human_review") or [],
            "counts": {"total": len(open_items),
                       "critical": sum(1 for x in open_items if x["severity"] == "critical"),
                       "high": sum(1 for x in open_items if x["severity"] == "high"),
                       "auto": sum(1 for x in open_items if x["auto_repairable"]),
                       "human": sum(1 for x in open_items if x["human_review_required"]),
                       "deferred": len(deferred),
                       "rejected": sum(1 for x in items if x["status"] == "rejected_by_human")}}


def save(root, res, out_dir=None):
    out_dir = out_dir or os.path.join(root, ".aeromech", "artifacts", "analysis")
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, "research-diagnosis.json")
    json.dump(res, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    mp = os.path.join(out_dir, "research-diagnosis.md")
    lines = ["# Research Diagnosis（v1.5）", "",
             f"- 诊断条目: {res['counts']['total']}（Critical {res['counts']['critical']} / "
             f"High {res['counts']['high']} / 可自动修复 {res['counts']['auto']} / 需人工 {res['counts']['human']}）",
             f"- 可行性: {res.get('feasibility', {}).get('verdict', '-')}",
             f"- RQG Gate: {res.get('rqg_gate', '-')}", ""]
    for d in res["diagnoses"]:
        lines.append(f"## {d['diagnosis_id']} [{d['severity']}] {d['issue_type']}")
        lines.append(f"- 问题: {d['detail']}")
        lines.append(f"- 受影响节点: {', '.join(d['affected_nodes']) or '—'}")
        lines.append(f"- 根因: {d['root_cause']}")
        lines.append(f"- 影响: {d.get('impact', DEFAULT_IMPACT)}")
        lines.append(f"- 证据: {'; '.join(d['evidence'])}")
        opts = "；".join(f"{o['id']} {o['repair_type']}：{o['action']}" for o in d["repair_options"])
        lines.append(f"- 修复选项: {opts or '（无）'}")
        lines.append(f"- 自动可修: {d['auto_repairable']}；需人工: {d['human_review_required']}；"
                     f"置信度: {d['confidence']}；规则: {d['rule']}")
        lines.append("")
    open(mp, "w", encoding="utf-8").write("\n".join(lines))
    return jp, mp


def main():
    ap = argparse.ArgumentParser(description="Research Diagnosis Engine（v1.5）")
    ap.add_argument("project_root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-rqg", action="store_true")
    args = ap.parse_args()
    root = args.project_root
    if not RI.initialized(root):
        print("注册表未初始化：.aeromech/research/ 不存在")
        return 2
    try:
        res = diagnose(root, use_rqg=not args.no_rqg)
        jp, mp = save(root, res, args.out)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"诊断: {res['counts']}；可行性 {res.get('feasibility', {}).get('verdict')}；"
                  f"RQG {res.get('rqg_gate')}")
            for d in res["diagnoses"]:
                print(f"  [{d['severity']}] {d['diagnosis_id']} {d['issue_type']} | {d['detail'][:70]}")
            print("report:", mp)
        return 1 if (res["counts"]["critical"] or res["counts"]["high"]) else 0
    except RI.RegistryError as e:
        print(f"ERROR: 注册表损坏 {e.path}: {e.detail}")
        return 3
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DIAGNOSIS ERROR: {type(e).__name__}: {e}（未产生 PASS 结论）")
        return 3


if __name__ == "__main__":
    sys.exit(main())
