# -*- coding: utf-8 -*-
"""research_integrity.py — Research Integrity 注册表引擎（aeromech-thesis v1.5.0）

存储：<project_root>/.aeromech/research/*.yaml（13 个注册表 + 生成的 traceability.json）
能力：读写 / 结构校验 / 追踪图构建与完整性校验 / Evidence Coverage 计算 / ID 分配
用法：
  python research_integrity.py <project_root> init
  python research_integrity.py <project_root> validate   [--json]
  python research_integrity.py <project_root> trace      [--out <dir>]
  python research_integrity.py <project_root> coverage   [--json]
退出码：0=成功/校验通过；1=校验发现问题；2=环境/注册表不存在；3=注册表损坏（ERROR）
"""
import argparse
import datetime
import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

# ---------------- 注册表定义 ----------------
REGISTRY_SPECS = {
    # name: (file, top_key, id_prefix, id_digits)
    "rq":          ("rq.yaml", "RQs", "RQ", 2),
    "methods":     ("methods.yaml", "methods", "M", 3),
    "evidence":    ("evidence.yaml", "evidence", "E", 3),
    "datasets":    ("datasets.yaml", "datasets", "DS", 3),
    "analyses":    ("analyses.yaml", "analyses", "AN", 3),
    "computations": ("computations.yaml", "computations", "CALC", 3),
    "claims":      ("claims.yaml", "claims", "CL", 3),
    "conclusions": ("conclusions.yaml", "conclusions", "CON", 3),
    "figures":     ("figures.yaml", "figures", "FIG", 3),   # 含 TABLE-XXX 前缀条目
    "conflicts":   ("conflicts.yaml", "conflicts", "CONFLICT", 3),
    # v1.5 Research Intelligence 注册表（缺省即 N/A，旧项目兼容）
    "design":      ("design.yaml", "designs", "DESIGN", 3),
    "scope":       ("scope.yaml", "scopes", "SCOPE", 3),
    "repairs":     ("repairs.yaml", "repairs", "REP", 3),
}

EVIDENCE_TYPES = ["literature", "standard", "manual", "official_document",
                  "project_material", "experiment", "calculation", "simulation", "assumption"]
VERIFICATION_STATUS = ["verified", "partial", "pending", "simulated"]
CLAIM_TYPES = ["fact", "interpretation", "calculation_result",
               "engineering_judgement", "assumption", "simulation_result"]
DATASET_TYPES = ["real", "public", "user_provided", "literature", "simulated", "assumption"]
SYNTH_LABEL = "【假设/模拟·仅演示方法】"

# v1.5：RQ 声明的证据要求（设计级能力边界）与修复类型
EVIDENCE_REQUIREMENTS = ["real_world_data", "verified_evidence", "simulated_ok", "literature_only"]
REPAIR_TYPES = ["REFRAME_RQ", "CHANGE_METHOD", "LIMIT_SCOPE", "ADD_EVIDENCE", "REVISE_CLAIM",
                "REVISE_CONCLUSION", "REVISE_ABSTRACT", "RECALCULATE", "REBUILD_FIGURE",
                "REBUILD_TABLE", "REWRITE_SECTION", "REQUEST_HUMAN_REVIEW"]
REPAIR_STATUS = ["proposed", "applied", "verified", "rejected"]

ID_RE = re.compile(r"^(RQ|M|E|DS|AN|CALC|CL|CON|FIG|TABLE|CONFLICT|DESIGN|SCOPE|REP)-\d{2,3}$")


class RegistryError(Exception):
    """注册表文件损坏/不可解析（v1.4.1：稳定错误模型，绝不静默当空表）。"""

    def __init__(self, path, detail):
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


REMEDIATION = {
    "RI-000": "按 references/research-integrity.md 建立 .aeromech/research/ 注册表后重跑",
    "RI-CORRUPT": "修复该 YAML 语法/结构（或从备份恢复）后重跑 validate",
    "RI-ID-FORMAT": "按 ID 规则修正（RQ-XX / M-XXX / E-XXX / CALC-XXX / CONFLICT-XXX 等）",
    "RI-ID-DUP": "为重复条目分配新 ID 并更新所有引用",
    "RI-RQ-FIELD": "补齐 RQ 的 question/objective 字段",
    "RI-RQ-LINK": "补齐 RQ 链路字段（related_methods/chapters/analyses）",
    "RI-DANGLING": "修复悬空引用：创建被引用条目或改指有效 ID",
    "RI-M-FIELD": "补齐方法 name 字段",
    "RI-M-BASIS": "补齐方法选择依据 basis（说明为什么选该方法）",
    "RI-E-TYPE": "source_type 使用许可枚举（literature/standard/manual/official_document/project_material/experiment/calculation/simulation/assumption）",
    "RI-E-STATUS": "verification_status 使用许可枚举（verified/partial/pending/simulated）",
    "RI-E-DISGUISE": "禁止伪装：simulation/assumption 证据必须记 simulated；如确为实测请更正 source_type",
    "RI-E-FIELD": "补齐证据 source 字段",
    "RI-DS-TYPE": "type 使用许可枚举（real/public/user_provided/literature/simulated/assumption）",
    "RI-DS-SOURCE": "补齐数据集 source 字段",
    "RI-DS-SYNTH": "模拟/假定数据集必须补齐 reason/assumptions/generation_method/limitations/label",
    "RI-DS-LABEL": f"label 必须含「{SYNTH_LABEL}」标记（身份保持）",
    "RI-AN-INPUT": "为核心分析补齐 inputs（数据/证据/计算引用）",
    "RI-CALC-ID": "计算 ID 须为 CALC-XXX",
    "RI-CALC-FIELD": "补齐计算 inputs/formula/verification 三件套",
    "RI-CALC-VERIFY": "补充验证状态（verified:true 或 verification 注明复核通过）",
    "RI-CL-FIELD": "补齐 claim 文本字段",
    "RI-CL-TYPE": "claim_type 使用许可枚举（fact/interpretation/calculation_result/engineering_judgement/assumption/simulation_result）",
    "RI-CL-NOEVID": "为需证据的核心论断补齐证据/分析链接，或显式声明 evidence_required:false 并说明理由",
    "RI-CON-FIELD": "补齐 conclusion 文本字段",
    "RI-CON-TRACE": "为结论补齐 claims/analyses 回溯链（无分析支撑的结论需降级或补证据）",
    "RI-FIG-ORPHAN": "为图表建立 related_rqs/analyses/claims 论证链接（避免装饰性图表）",
    "RI-CF-FIELD": "补齐冲突记录字段（source_a/source_b/conflict/resolution/reason/status）",
    "RI-CF-STATUS": "status 仅允许 resolved/pending（无法判断时用 pending + 【待核实】）",
    "RI-DESIGN-FIELD": "补齐研究设计字段（RQ/目标/方法/证据计划/数据计划/分析计划/预期产出/约束/假设/局限），"
                       "并按 references/research-intelligence.md §2 维护",
    "RI-DESIGN-REQ": "rq_requirements[].evidence_requirement 使用许可枚举"
                     "（real_world_data/verified_evidence/simulated_ok/literature_only）",
    "RI-SCOPE-FIELD": "补齐 Scope Boundary 的 included/excluded/assumptions（可用于 scope creep 检测）",
    "RI-REP-FIELD": "补齐修复计划字段（diagnosis_id/target_nodes/repair_type/rationale/expected_effect/risk/status）",
    "RI-REP-TYPE": f"repair_type 使用许可枚举：{REPAIR_TYPES}",
    "RI-REP-STATUS": f"status 仅允许 {REPAIR_STATUS}",
}


def _with_meta(problems):
    """v1.4.1：为每个问题补齐 reason/remediation（稳定错误模型）。"""
    for p in problems or []:
        p.setdefault("reason", p.get("detail", ""))
        p.setdefault("remediation", REMEDIATION.get(p.get("code"), "按 references/research-integrity.md 修复后重跑"))
    return problems


def research_dir(root):
    return os.path.join(root, ".aeromech", "research")


def _path(root, reg):
    return os.path.join(research_dir(root), REGISTRY_SPECS[reg][0])


def load_registry(root, reg):
    p = _path(root, reg)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise RegistryError(p, f"YAML 解析失败: {e}") from e
    except OSError as e:
        raise RegistryError(p, f"读取失败: {e}") from e
    if not isinstance(data, dict):
        raise RegistryError(p, f"顶层结构应为映射（含 {REGISTRY_SPECS[reg][1]} 键）")
    key = REGISTRY_SPECS[reg][1]
    items = data.get(key) or []
    if not isinstance(items, list):
        raise RegistryError(p, f"{key} 应为列表")
    return items


def save_registry(root, reg, items):
    os.makedirs(research_dir(root), exist_ok=True)
    p = _path(root, reg)
    key = REGISTRY_SPECS[reg][1]
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump({key: items}, f, allow_unicode=True, sort_keys=False)


def load_all(root, collect_errors=None):
    """返回 {reg: items|None}；None 表示该注册表文件不存在（未初始化）。
    collect_errors 非 None 时：损坏的注册表记入该列表并将值置 None（供 validate/QA 走 ERROR/Critical 路径）；
    否则遇到损坏直接抛 RegistryError（调用方应捕获并给稳定错误码）。"""
    out = {}
    for reg in REGISTRY_SPECS:
        try:
            out[reg] = load_registry(root, reg)
        except RegistryError as e:
            out[reg] = None
            if collect_errors is not None:
                collect_errors.append(e)
            else:
                raise
    return out


def initialized(root):
    return os.path.isdir(research_dir(root)) and any(
        os.path.isfile(_path(root, r)) for r in REGISTRY_SPECS)


def next_id(root, reg):
    items = load_registry(root, reg) or []
    _, _, prefix, digits = REGISTRY_SPECS[reg]
    mx = 0
    for it in items:
        m = re.match(rf"^{prefix}-(\d+)$", str(it.get("id", "")))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{prefix}-{mx + 1:0{digits}d}"


def add_entry(root, reg, data):
    items = load_registry(root, reg) or []
    if not data.get("id"):
        data["id"] = next_id(root, reg)
    items.append(data)
    save_registry(root, reg, items)
    return data["id"]


def init_registries(root):
    os.makedirs(research_dir(root), exist_ok=True)
    created = []
    for reg in REGISTRY_SPECS:
        p = _path(root, reg)
        if not os.path.isfile(p):
            save_registry(root, reg, [])
            created.append(REGISTRY_SPECS[reg][0])
    return created


# ---------------- 结构校验 ----------------
def _require(item, field, code, where, problems, severity="high"):
    v = item.get(field)
    missing = (v is None
               or (isinstance(v, str) and not v.strip())
               or (isinstance(v, (list, dict)) and not v))
    if missing:
        problems.append({"code": code, "severity": severity, "where": where,
                         "detail": f"缺少必填字段 {field}"})
        return False
    return True


def _ref_exists(reg_data, ref):
    """ref 形如 'E-001'；在全部注册表中查找（含 FIG/TABLE）。"""
    if not ref or not isinstance(ref, str):
        return False
    for items in reg_data.values():
        if not items:
            continue
        for it in items:
            if str(it.get("id", "")) == ref:
                return True
    return False


def validate(root):
    """结构校验。返回 {ok, problems[], stats}。problems[].severity ∈ critical/high/medium/low
    v1.4.1：每个问题含 reason/remediation；注册表损坏记 RI-CORRUPT（critical）而非静默当空表。"""
    errors = []
    data = load_all(root, collect_errors=errors)
    problems = []
    stats = {reg: len(items or []) for reg, items in data.items()}

    if not initialized(root):
        return {"ok": False, "initialized": False, "problems": _with_meta([
            {"code": "RI-000", "severity": "medium", "where": "research/",
             "detail": "注册表未初始化（旧项目兼容：RQG 记 not_initialized，不阻塞）"}]),
            "stats": stats}

    for e in errors:
        problems.append({"code": "RI-CORRUPT", "severity": "critical",
                         "where": os.path.basename(e.path),
                         "detail": f"注册表损坏：{e.detail}（不得视为空表；修复后重跑）"})

    # ID 唯一性与格式
    seen_ids = {}
    for reg, items in data.items():
        for it in items or []:
            iid = str(it.get("id", ""))
            if not ID_RE.match(iid):
                problems.append({"code": "RI-ID-FORMAT", "severity": "high",
                                 "where": f"{reg}:{iid}", "detail": "ID 缺失或格式非法"})
            if iid in seen_ids:
                problems.append({"code": "RI-ID-DUP", "severity": "high",
                                 "where": iid, "detail": f"ID 重复（{seen_ids[iid]} 与 {reg}）"})
            seen_ids[iid] = reg

    def reg_items(reg):
        return data.get(reg) or []

    # RQ 必填与链接
    for it in reg_items("rq"):
        w = f"rq:{it.get('id')}"
        _require(it, "question", "RI-RQ-FIELD", w, problems)
        _require(it, "objective", "RI-RQ-FIELD", w, problems)
        for k in ("related_methods", "related_chapters", "related_analyses"):
            v = it.get(k)
            if not v:
                problems.append({"code": "RI-RQ-LINK", "severity": "high", "where": w,
                                 "detail": f"RQ 缺少链路字段 {k}"})
        for ref in it.get("related_methods") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"related_methods 悬空引用 {ref}"})
        for ref in it.get("related_analyses") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"related_analyses 悬空引用 {ref}"})

    # Method
    for it in reg_items("methods"):
        w = f"methods:{it.get('id')}"
        _require(it, "name", "RI-M-FIELD", w, problems)
        _require(it, "basis", "RI-M-BASIS", w, problems)

    # Evidence
    for it in reg_items("evidence"):
        w = f"evidence:{it.get('id')}"
        st = it.get("source_type")
        vs = it.get("verification_status")
        if st not in EVIDENCE_TYPES:
            problems.append({"code": "RI-E-TYPE", "severity": "high", "where": w,
                             "detail": f"source_type 非法: {st}"})
        if vs not in VERIFICATION_STATUS:
            problems.append({"code": "RI-E-STATUS", "severity": "high", "where": w,
                             "detail": f"verification_status 非法: {vs}"})
        if st in ("simulation", "assumption") and vs != "simulated":
            problems.append({"code": "RI-E-DISGUISE", "severity": "critical", "where": w,
                             "detail": f"{st} 证据不得标记为 {vs}（禁止伪装）"})
        _require(it, "source", "RI-E-FIELD", w, problems)
        for ref in it.get("claim_supported") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"claim_supported 悬空引用 {ref}"})

    # Datasets（Synthetic Data Ledger）
    for it in reg_items("datasets"):
        w = f"datasets:{it.get('id')}"
        typ = it.get("type")
        if typ not in DATASET_TYPES:
            problems.append({"code": "RI-DS-TYPE", "severity": "high", "where": w,
                             "detail": f"type 非法: {typ}"})
        _require(it, "source", "RI-DS-SOURCE", w, problems)
        if typ in ("simulated", "assumption"):
            for f in ("reason", "assumptions", "generation_method", "limitations", "label"):
                _require(it, f, "RI-DS-SYNTH", w, problems)
            if SYNTH_LABEL not in str(it.get("label", "")):
                problems.append({"code": "RI-DS-LABEL", "severity": "critical", "where": w,
                                 "detail": f"模拟数据 label 必须含 {SYNTH_LABEL}"})

    # Analyses
    for it in reg_items("analyses"):
        w = f"analyses:{it.get('id')}"
        inputs = it.get("inputs") or []
        if not inputs:
            problems.append({"code": "RI-AN-INPUT", "severity": "high", "where": w,
                             "detail": "分析缺少 inputs（核心分析必须有数据/证据支撑）"})
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("kind") != "reasoning":
                if inp.get("ref") and not _ref_exists(data, str(inp.get("ref"))):
                    problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                     "detail": f"inputs 悬空引用 {inp.get('ref')}"})

    # Computations
    for it in reg_items("computations"):
        w = f"computations:{it.get('id')}"
        cid = str(it.get("id", ""))
        if not re.match(r"^CALC-\d{2,3}$", cid):
            problems.append({"code": "RI-CALC-ID", "severity": "high", "where": w,
                             "detail": "计算 ID 须为 CALC-XXX"})
        for f in ("inputs", "formula", "verification"):
            _require(it, f, "RI-CALC-FIELD", w, problems)
        if not it.get("verified", False) and it.get("verification_result") != "passed":
            vres = str(it.get("verification", ""))
            if "通过" not in vres and "passed" not in vres and "verified" not in vres.lower():
                problems.append({"code": "RI-CALC-VERIFY", "severity": "medium", "where": w,
                                 "detail": "计算未标注验证通过状态"})
        for inp in it.get("inputs") or []:
            if isinstance(inp, dict) and inp.get("ref") and not _ref_exists(data, str(inp["ref"])):
                # 允许形如 DS-001/输入列表内联（非注册实体）时降级
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"inputs 悬空引用 {inp.get('ref')}"})
        for ref in it.get("used_in") or []:
            r = str(ref)
            if ID_RE.match(r) and not _ref_exists(data, r):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"used_in 悬空引用 {r}"})

    # Claims
    for it in reg_items("claims"):
        w = f"claims:{it.get('id')}"
        _require(it, "claim", "RI-CL-FIELD", w, problems)
        if it.get("claim_type") not in CLAIM_TYPES:
            problems.append({"code": "RI-CL-TYPE", "severity": "high", "where": w,
                             "detail": f"claim_type 非法: {it.get('claim_type')}"})
        for ref in it.get("evidence_ids") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"evidence_ids 悬空引用 {ref}"})
        for ref in it.get("analysis_ids") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"analysis_ids 悬空引用 {ref}"})
        need = it.get("evidence_required")
        if need is None:
            need = it.get("claim_type") in ("fact", "calculation_result", "assumption", "simulation_result")
        if need and not (it.get("evidence_ids") or it.get("analysis_ids")):
            problems.append({"code": "RI-CL-NOEVID", "severity": "high", "where": w,
                             "detail": "需证据的核心论断没有任何证据/分析链接"})

    # Conclusions（结论可追溯）
    for it in reg_items("conclusions"):
        w = f"conclusions:{it.get('id')}"
        _require(it, "conclusion", "RI-CON-FIELD", w, problems)
        if not it.get("claims") and not it.get("analyses"):
            problems.append({"code": "RI-CON-TRACE", "severity": "high", "where": w,
                             "detail": "结论无可追溯链（claims/analyses 均缺）"})
        for ref in (it.get("claims") or []) + (it.get("analyses") or []) + (it.get("evidence") or []):
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"结论引用悬空 {ref}"})

    # Figures/Tables links
    for it in reg_items("figures"):
        w = f"figures:{it.get('id')}"
        links = (it.get("related_rqs") or []) + (it.get("related_analyses") or []) + (it.get("related_claims") or [])
        if not links:
            problems.append({"code": "RI-FIG-ORPHAN", "severity": "medium", "where": w,
                             "detail": "图表无论证链接（related_rqs/analyses/claims 全空）"})
        for ref in links:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"图表链接悬空 {ref}"})

    # Conflicts
    for it in reg_items("conflicts"):
        w = f"conflicts:{it.get('id')}"
        for f in ("source_a", "source_b", "conflict", "resolution", "reason", "status"):
            _require(it, f, "RI-CF-FIELD", w, problems)
        if it.get("status") not in ("resolved", "pending"):
            problems.append({"code": "RI-CF-STATUS", "severity": "medium", "where": w,
                             "detail": f"status 非法: {it.get('status')}"})

    # Design（v1.5 Research Design Registry）
    for it in reg_items("design"):
        w = f"design:{it.get('id')}"
        for f in ("research_questions", "objectives", "methods", "evidence_plan", "data_plan",
                  "analysis_plan", "expected_outputs", "constraints", "assumptions", "limitations"):
            _require(it, f, "RI-DESIGN-FIELD", w, problems)
        for ref in it.get("research_questions") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"research_questions 悬空引用 {ref}"})
        for ref in it.get("methods") or []:
            if not _ref_exists(data, ref):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"methods 悬空引用 {ref}"})
        for rq in it.get("rq_requirements") or []:
            if isinstance(rq, dict):
                if str(rq.get("id", "")) and not _ref_exists(data, str(rq.get("id"))):
                    problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                     "detail": f"rq_requirements 悬空引用 {rq.get('id')}"})
                if rq.get("evidence_requirement") not in EVIDENCE_REQUIREMENTS:
                    problems.append({"code": "RI-DESIGN-REQ", "severity": "high", "where": w,
                                     "detail": f"evidence_requirement 非法: {rq.get('evidence_requirement')}"
                                               f"（允许: {EVIDENCE_REQUIREMENTS}）"})

    # Scope（v1.5 Scope Boundary）
    for it in reg_items("scope"):
        w = f"scope:{it.get('id')}"
        _require(it, "included", "RI-SCOPE-FIELD", w, problems)
        _require(it, "excluded", "RI-SCOPE-FIELD", w, problems)
        _require(it, "assumptions", "RI-SCOPE-FIELD", w, problems)

    # Repairs（v1.5 Repair Plan Registry）
    for it in reg_items("repairs"):
        w = f"repairs:{it.get('id')}"
        for f in ("diagnosis_id", "target_nodes", "repair_type", "rationale",
                  "expected_effect", "risk", "status"):
            _require(it, f, "RI-REP-FIELD", w, problems)
        if it.get("repair_type") not in REPAIR_TYPES:
            problems.append({"code": "RI-REP-TYPE", "severity": "high", "where": w,
                             "detail": f"repair_type 非法: {it.get('repair_type')}"})
        if it.get("status") not in REPAIR_STATUS:
            problems.append({"code": "RI-REP-STATUS", "severity": "medium", "where": w,
                             "detail": f"status 非法: {it.get('status')}"})
        for ref in it.get("target_nodes") or []:
            if str(ref).startswith(("CL-", "CON-", "E-", "DS-", "AN-", "CALC-", "M-", "RQ-")) \
                    and not _ref_exists(data, str(ref)):
                problems.append({"code": "RI-DANGLING", "severity": "high", "where": w,
                                 "detail": f"target_nodes 悬空引用 {ref}"})

    has_critical = any(p["severity"] == "critical" for p in problems)
    has_high = any(p["severity"] == "high" for p in problems)
    return {"ok": not (has_critical or has_high), "initialized": True,
            "problems": _with_meta(problems), "stats": stats,
            "has_critical": has_critical, "has_high": has_high}


# ---------------- 追踪图 ----------------
def build_traceability(root):
    """由注册表构建追踪图：nodes[{id,type,in_chain}] + edges[[from,to]] + orphans[]。"""
    data = load_all(root)
    nodes = {}
    edges = []

    def add_node(iid, typ, extra=None):
        nodes[iid] = {"id": iid, "type": typ, "in_chain": False}
        if extra:
            nodes[iid].update(extra)

    def add_edge(a, b):
        if a and b:
            edges.append([a, b])

    for it in data.get("rq") or []:
        iid = str(it.get("id"))
        add_node(iid, "RQ")
        for m in it.get("related_methods") or []:
            add_edge(iid, m)
        for a in it.get("related_analyses") or []:
            add_edge(iid, a)
        for con in it.get("related_conclusions") or []:
            add_edge(iid, con)
    for reg, typ in (("methods", "M"), ("evidence", "E"), ("datasets", "DS"),
                     ("analyses", "AN"), ("computations", "CALC"), ("claims", "CL"),
                     ("conclusions", "CON"), ("figures", "FIG"), ("conflicts", "CF")):
        for it in data.get(reg) or []:
            iid = str(it.get("id"))
            add_node(iid, "TABLE" if iid.startswith("TABLE-") else typ)
    for it in data.get("evidence") or []:
        iid = str(it.get("id"))
        for c in it.get("claim_supported") or []:
            add_edge(iid, c)
    for it in data.get("analyses") or []:
        iid = str(it.get("id"))
        for inp in it.get("inputs") or []:
            if isinstance(inp, dict) and inp.get("ref"):
                add_edge(str(inp["ref"]), iid)
        for o in it.get("outputs") or []:
            if ID_RE.match(str(o)):
                add_edge(iid, str(o))
    for it in data.get("computations") or []:
        iid = str(it.get("id"))
        for inp in it.get("inputs") or []:
            if isinstance(inp, dict) and inp.get("ref"):
                add_edge(str(inp["ref"]), iid)
        for o in it.get("used_in") or []:
            if ID_RE.match(str(o)):
                add_edge(iid, str(o))
    for it in data.get("claims") or []:
        iid = str(it.get("id"))
        for r in (it.get("evidence_ids") or []) + (it.get("analysis_ids") or []):
            add_edge(str(r), iid)
    for it in data.get("conclusions") or []:
        iid = str(it.get("id"))
        for r in (it.get("claims") or []) + (it.get("analyses") or []):
            add_edge(str(r), iid)
    for it in data.get("figures") or []:
        iid = str(it.get("id"))
        for r in (it.get("related_rqs") or []) + (it.get("related_analyses") or []) + (it.get("related_claims") or []):
            add_edge(str(r), iid)

    # 可达性：从任意上游 E/DS/CALC/M 出发的节点标记 in_chain
    fwd = {}
    for a, b in edges:
        fwd.setdefault(a, []).append(b)
    seeds = [n for n in nodes if nodes[n]["type"] in ("E", "DS", "CALC", "M")]
    visited = set(seeds)
    stack = list(seeds)
    while stack:
        cur = stack.pop()
        for nxt in fwd.get(cur, []):
            if nxt not in visited:
                visited.add(nxt)
                stack.append(nxt)
    for n in visited:
        if n in nodes:
            nodes[n]["in_chain"] = True
    core_types = ("CL", "CON")
    orphans = sorted(n for n, v in nodes.items()
                     if v["type"] in core_types and not v["in_chain"])
    return {"nodes": sorted(nodes.values(), key=lambda x: x["id"]),
            "edges": sorted(edges), "orphans": orphans}


def save_traceability(root, out_dir=None):
    t = build_traceability(root)
    out_dir = out_dir or research_dir(root)
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "traceability.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=1)
    return p, t


# ---------------- Evidence Coverage ----------------
def coverage(root):
    """Evidence Coverage Ratio：核心 Claim 覆盖 + 证据状态四分类（不升级模拟身份）。"""
    data = load_all(root)
    claims = data.get("claims") or []
    ev_by_id = {str(e.get("id")): e for e in (data.get("evidence") or [])}
    ds_by_id = {str(e.get("id")): e for e in (data.get("datasets") or [])}

    need, covered, uncovered = [], [], []
    coverage_details = []
    for c in claims:
        cid = str(c.get("id"))
        need_ev = c.get("evidence_required")
        if need_ev is None:
            need_ev = c.get("claim_type") in ("fact", "calculation_result",
                                              "assumption", "simulation_result")
        if not need_ev:
            continue
        need.append(cid)
        refs = list(c.get("evidence_ids") or []) + list(c.get("analysis_ids") or [])
        statuses = []
        for r in refs:
            e = ev_by_id.get(str(r))
            if e:
                statuses.append(str(e.get("verification_status")))
            elif str(r) in ds_by_id:
                dt = str(ds_by_id[str(r)].get("type"))
                statuses.append("simulated" if dt in ("simulated", "assumption") else "verified")
        has_partial = "partial" in statuses
        has_sim = "simulated" in statuses
        has_ok = any(s in ("verified", "partial", "simulated") for s in statuses)
        if refs and has_ok:
            covered.append(cid)
            coverage_details.append({"claim": cid, "statuses": statuses or ["pending"],
                                     "partial": has_partial, "simulated": has_sim})
        else:
            uncovered.append(cid)
    n_need, n_cov = len(need), len(covered)
    ratio = (n_cov / n_need) if n_need else 1.0
    by_status = {"verified": 0, "partial": 0, "pending": 0, "simulated": 0}
    for e in ev_by_id.values():
        s = str(e.get("verification_status"))
        if s in by_status:
            by_status[s] += 1
    return {"evidence_coverage_ratio": round(ratio, 4),
            "claims_need_evidence": n_need, "claims_covered": n_cov,
            "uncovered": sorted(uncovered),
            "evidence_by_status": by_status,
            "details": coverage_details}


# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser(description="Research Integrity 注册表引擎")
    ap.add_argument("project_root")
    ap.add_argument("action", choices=["init", "validate", "trace", "coverage"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = args.project_root

    if args.action == "init":
        created = init_registries(root)
        print("created:", created or "(已存在，无新增)")
        return 0
    if not initialized(root):
        print("注册表未初始化：.aeromech/research/ 不存在")
        return 2
    if args.action == "validate":
        r = validate(root)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            print(f"ok={r['ok']} problems={len(r['problems'])} stats={r['stats']}")
            for p in r["problems"][:20]:
                print(f"  [{p['severity']}] {p['code']} @ {p['where']}: {p['detail']}")
                if p.get("remediation"):
                    print(f"      remediation: {p['remediation']}")
        return 0 if r["ok"] else 1
    try:
        if args.action == "trace":
            p, t = save_traceability(root, args.out)
            print(f"traceability saved: {p} nodes={len(t['nodes'])} edges={len(t['edges'])} orphans={t['orphans']}")
            return 0
        if args.action == "coverage":
            c = coverage(root)
            if args.json:
                print(json.dumps(c, ensure_ascii=False, indent=1))
            else:
                print(f"coverage={c['evidence_coverage_ratio']} "
                      f"({c['claims_covered']}/{c['claims_need_evidence']}) "
                      f"by_status={c['evidence_by_status']}")
            return 0
    except RegistryError as e:
        print(f"ERROR: 注册表损坏 {e.path}: {e.detail}")
        print(f"       remediation: {REMEDIATION['RI-CORRUPT']}（本工具不会把损坏注册表当作空表继续）")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
