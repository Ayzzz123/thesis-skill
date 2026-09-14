# -*- coding: utf-8 -*-
"""tests/v1_5/_fixtures.py — v1.5 Research Intelligence 测试夹具

在 tests/v1_4/_fixtures.py 的项目夹具之上：
- 为 methods 增补 provides / selection（方法选择论证）；
- 追加 design.yaml / scope.yaml / repairs.yaml（默认正例）；
- 提供研究缺陷变体（variant）用于诊断/修复/循环测试。
"""
import copy
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts"))

# 显式按文件路径加载 v1_4 夹具，避免与包内同名 _fixtures 冲突
_spec = importlib.util.spec_from_file_location(
    "f14_fixtures", os.path.join(SKILL, "tests", "v1_4", "_fixtures.py"))
F14 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F14)
import research_integrity as RI  # noqa: E402


def default_design():
    return {
        "id": "DESIGN-001",
        "research_questions": ["RQ-01", "RQ-02"],
        "objectives": ["识别主要故障模式并评估其影响", "确定面向主要故障模式的维修策略"],
        "methods": ["M-001", "M-002", "M-003"],
        "rq_requirements": [
            {"id": "RQ-01", "needs": ["fault_modes", "fault_effects", "risk_ranking"],
             "evidence_requirement": "simulated_ok"},
            {"id": "RQ-02", "needs": ["repair_priority", "strategy_mapping"],
             "evidence_requirement": "simulated_ok"},
        ],
        "evidence_plan": ["E-001", "E-002", "E-003"],
        "data_plan": ["DS-001"],
        "analysis_plan": ["AN-001", "AN-002"],
        "expected_outputs": ["TABLE-001", "FIG-001"],
        "constraints": ["无真实机队数据；不获取新手册"],
        "assumptions": ["模拟参数为工程假定，仅用于方法演示"],
        "limitations": ["模拟数据不代表真实机队统计特征"],
    }


def default_scope():
    return {
        "id": "SCOPE-001",
        "included": ["刹车系统", "故障模式", "维修策略"],
        "excluded": ["飞控系统", "发动机系统", "起落架收放机构"],
        "assumptions": ["分析限于液压刹车系统的机电子系统"],
    }


def _augment_methods(regs):
    if not any(m["id"] == "M-003" for m in regs["methods"]):
        regs["methods"].append({
            "id": "M-003", "name": "维修策略决策矩阵",
            "basis": "将风险等级与可探测性结构化映射为维修方式，形成可复核的维修策略论证",
            "used_in": [5]})
    for m in regs["methods"]:
        if m["id"] == "M-001":
            m["provides"] = ["fault_modes", "fault_effects", "risk_ranking", "repair_priority"]
            m["selection"] = {
                "candidates": [
                    {"name": "FMEA", "reason": "能自下而上系统识别故障模式并给出风险排序"},
                    {"name": "FTA", "reason": "面向顶事件概率推断，缺少概率数据时不适用"},
                ],
                "selected": "FMEA",
                "selection_reason": "研究目标是识别与排序而非概率推断，与可用数据及证据能力匹配",
            }
        elif m["id"] == "M-002":
            m["provides"] = ["reliability_metrics"]
            m["selection"] = {
                "candidates": [
                    {"name": "Weibull分布分析", "reason": "适用于磨损类故障的间隔数据拟合"},
                    {"name": "指数分布假设", "reason": "恒定失效率假设不适用于磨损型故障"},
                ],
                "selected": "Weibull分布分析",
                "selection_reason": "磨损类故障符合 Weibull 累积失效规律",
            }
        elif m["id"] == "M-003":
            m["provides"] = ["repair_priority", "strategy_mapping"]
            m["selection"] = {
                "candidates": [
                    {"name": "维修策略决策矩阵", "reason": "可把风险与可探测性结构化映射为维修方式"},
                    {"name": "纯经验排序", "reason": "缺乏结构化依据，不适合作本科研究论证"},
                ],
                "selected": "维修策略决策矩阵",
                "selection_reason": "需要结构化映射并留下可复核的判定依据",
            }
    return regs


def apply_variant(regs, texts, design, scope, variant):
    if variant is None:
        return
    if variant == "rq_mismatch":
        # RQ 需要 real_world_prediction，而方法能力未覆盖 → RQ_METHOD_MISMATCH
        design["rq_requirements"][0]["needs"] = ["fault_modes", "real_world_prediction"]
    elif variant == "evidence_mismatch":
        # RQ 声明需要真实世界数据，但数据集全为模拟 → DESIGN_EVIDENCE_MISMATCH
        design["rq_requirements"][0]["evidence_requirement"] = "real_world_data"
    elif variant == "method_weak":
        m = next(x for x in regs["methods"] if x["id"] == "M-001")
        m["selection"] = {"candidates": [{"name": "FMEA", "reason": "常用方法"}],
                          "selected": "FMEA", "selection_reason": ""}
    elif variant == "infeasible":
        design["rq_requirements"][0]["needs"] = ["fault_modes", "real_world_prediction"]
        design["rq_requirements"][0]["evidence_requirement"] = "real_world_data"
    elif variant == "scope_creep":
        texts["ch3-fault-modes.md"] += "\n\n与飞控系统相比，刹车系统的故障模式具有相似的分析方法。飞控系统的作动器故障也应按相同流程分析。\n"
    elif variant == "scope_creep_two_level":
        # 同一规则 SC-01 命中两个 excluded 词且严重度不同（×3=high / ×1=medium）→ B9 场景
        texts["ch3-fault-modes.md"] += "\n\n飞控系统的分析对象包括飞控计算机、作动器与数据总线。飞控系统的安全评估另有标准。飞控系统的维护按专册执行。\n\n发动机系统的孔探检查也采用类似的组织方式。\n"
    elif variant == "scope_under":
        scope["included"] = scope["included"] + ["起落架收放机构"]
    elif variant == "claim_overstrength":
        c = next(x for x in regs["claims"] if x["id"] == "CL-002")
        c["claim"] = "刹车片过度磨损必然导致制动失效，该故障在机队中的发生率为 12%"
        c["evidence_ids"], c["analysis_ids"] = ["E-003"], []
        texts["ch3-fault-modes.md"] += "\n\n刹车片过度磨损必然导致制动失效，该故障在机队中的发生率为 12%。\n"
    elif variant == "conclusion_overreach":
        c = next(x for x in regs["conclusions"] if x["id"] == "CON-002")
        c["conclusion"] = "液压内漏必然导致刹车失效"
        c["evidence"], c["analyses"] = ["E-003"], []
        texts["ch5-strategy.md"] += "\n\n经分析，液压内漏必然导致刹车失效。\n"
    elif variant == "number_mismatch":
        texts["front-abstract.md"] = texts["front-abstract.md"].replace(
            "RPN 最大值为 180", "RPN 最大值为 176")
    elif variant == "abstract_unique":
        texts["front-abstract.md"] = texts["front-abstract.md"].replace(
            "RPN 最大值为 180", "RPN 最大值为 999")
    elif variant == "calc_gap_recompute":
        c = next(x for x in regs["computations"] if x["id"] == "CALC-001")
        c["verification"] = ""
        c["verified"] = False
        c["recompute"] = {"cmd": "python .aeromech/transcripts/recompute_calc001.py"}
    elif variant == "duplicate_analysis":
        a1 = next(x for x in regs["analyses"] if x["id"] == "AN-001")
        dup = copy.deepcopy(a1)
        dup["id"], dup["name"] = "AN-003", "刹车系统 FMEA 分析（重复登记）"
        regs["analyses"].append(dup)
    elif variant == "redundant_content":
        para = ("为统一分析口径，本节按故障模式、故障原因、故障影响与补偿措施四个维度组织维修策略，"
                "并给出实施顺序与验证方式")
        texts["ch3-fault-modes.md"] += "\n\n" + para + "。\n"
        texts["ch5-strategy.md"] += "\n\n" + para + "。\n"
    elif variant == "orphan_fig":
        f = next(x for x in regs["figures"] if x["id"] == "FIG-001")
        f["related_rqs"], f["related_analyses"], f["related_claims"] = [], [], []
    elif variant == "conflict_pending":
        c = next(x for x in regs["conflicts"] if x["id"] == "CONFLICT-001")
        c["status"] = "pending"
    elif variant == "unused_literature":
        # 注册文献编号全部不在正文出现 → RQG-12 FAIL(High) → 诊断 CITATION_GAP（B1 可达性）
        for name in list(texts):
            if name.startswith("ch"):
                texts[name] = (texts[name].replace(" [1]", "").replace(" [2]", "")
                               .replace("[1]", "").replace("[2]", ""))
    else:
        raise KeyError(f"unknown v1_5 variant: {variant}")


def write_project(root, variant=None, design=None, scope=None, with_design=True):
    """建 v1.4 项目夹具 + v1.5 注册表。返回 root。"""
    regs = F14.default_registries()
    texts = F14.default_texts()
    _augment_methods(regs)
    d = copy.deepcopy(design if design is not None else default_design())
    s = copy.deepcopy(scope if scope is not None else default_scope())
    apply_variant(regs, texts, d, s, variant)
    F14.write_project(root, regs=regs, texts=texts)
    if with_design:
        RI.save_registry(root, "design", [d])
        RI.save_registry(root, "scope", [s])
        RI.save_registry(root, "repairs", [])
    if variant == "calc_gap_recompute":
        tdir = os.path.join(root, ".aeromech", "transcripts")
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, "recompute_calc001.py"), "w", encoding="utf-8") as f:
            f.write("# -*- coding: utf-8 -*-\n"
                    "print('OUTPUT=RPN 最大值为 180（刹车片过度磨损）')\n")
    return root


def write_queue_decisions(root, decisions):
    """写 human-review-queue.yaml：decisions = {diagnosis_id: dict}。"""
    import yaml
    qp = os.path.join(root, ".aeromech", "research", "human-review-queue.yaml")
    q = yaml.safe_load(open(qp, encoding="utf-8")) if os.path.isfile(qp) else {"queue": []}
    for e in q.get("queue") or []:
        d = decisions.get(str(e.get("diagnosis_id")))
        if d:
            e.update(d)
    with open(qp, "w", encoding="utf-8") as f:
        yaml.safe_dump(q, f, allow_unicode=True, sort_keys=False)
