# -*- coding: utf-8 -*-
"""tests/v1_4/_fixtures.py — v1.4 Research Integrity 测试夹具

构建链路完整的项目夹具（.aeromech/research/ 注册表 + 章节文本 + 研究方案），
供 tests/v1_4/test_*.py 复用；通过 variant 注入变异以构造 FAIL / boundary 用例。
"""
import os

import yaml

import research_integrity as RI

TOP_KEYS = {reg: spec[1] for reg, spec in RI.REGISTRY_SPECS.items()}


# ---------------- 默认（正例）注册表 ----------------
def default_registries():
    return {
        "rq": [
            {"id": "RQ-01",
             "question": "民用飞机刹车系统的主要故障模式及其影响是什么？",
             "objective": "识别主要故障模式并评估其影响",
             "related_methods": ["M-001", "M-002"],
             "related_chapters": [3, 4],
             "related_analyses": ["AN-001"],
             "related_conclusions": ["CON-001"]},
            {"id": "RQ-02",
             "question": "面向主要故障模式应采用什么维修策略？",
             "objective": "确定面向主要故障模式的维修策略",
             "related_methods": ["M-001"],
             "related_chapters": [5],
             "related_analyses": ["AN-002"],
             "related_conclusions": ["CON-002"]},
        ],
        "methods": [
            {"id": "M-001", "name": "FMEA",
             "basis": "FMEA 能够系统识别故障模式及其影响，适配本文自下而上的故障识别目标；与 FTA 相比更适合构建完整故障清单",
             "used_in": [3, 4]},
            {"id": "M-002", "name": "Weibull分布拟合",
             "basis": "两参数 Weibull 分布能够刻画磨损类故障的累积失效规律，适用于维修间隔特征分析",
             "used_in": [4]},
        ],
        "evidence": [
            {"id": "E-001", "source_type": "literature",
             "source": "教材《民用飞机液压与刹车系统》 [1]",
             "source_location": "第3章 液压刹车系统组成",
             "claim_supported": ["CL-001"], "reliability": "medium",
             "verification_status": "verified", "used_in": ["ch3", "ch4"],
             "notes": "馆藏可查"},
            {"id": "E-002", "source_type": "manual",
             "source": "某型飞机维修手册相关章节 [2]",
             "source_location": "刹车系统故障隔离章节",
             "claim_supported": ["CL-001"], "reliability": "medium",
             "verification_status": "partial", "used_in": ["ch3"],
             "notes": "手册具体编号【待核实】"},
            {"id": "E-003", "source_type": "simulation",
             "source": "模拟故障数据集 DS-001 的统计摘要",
             "source_location": "本文第4章", "claim_supported": ["CL-002"],
             "reliability": "low", "verification_status": "simulated",
             "used_in": ["ch4"], "notes": "仅演示方法"},
        ],
        "datasets": [
            {"id": "DS-001", "type": "simulated",
             "source": "基于公开故障率参数假定构造",
             "source_location": "本文第4章数据说明", "n": 50,
             "reason": "真实维修数据库不可用",
             "assumptions": ["故障间隔时间服从两参数 Weibull 分布",
                             "各故障模式发生率参数参照文献经验值假定"],
             "generation_method": "以假定参数生成 50 条故障间隔样本，用于演示 RPN 与分布拟合流程",
             "parameters": {"beta": 1.8, "eta": 320},
             "limitations": "不能代表真实机队的统计特征，仅用于方法演示",
             "label": RI.SYNTH_LABEL,
             "used_in": ["ch4", "TABLE-001"]},
        ],
        "analyses": [
            {"id": "AN-001", "name": "刹车系统 FMEA 分析", "method": "FMEA",
             "inputs": [{"kind": "dataset", "ref": "DS-001"},
                        {"kind": "evidence", "ref": "E-001"}],
             "outputs": ["TABLE-001"], "summary": "识别 8 类故障模式并排序 RPN"},
            {"id": "AN-002", "name": "维修策略设计", "method": "工程判断",
             "inputs": [{"kind": "calculation", "ref": "CALC-001"}],
             "outputs": ["FIG-001"], "summary": "基于 RPN 结果提出视情维修为主策略"},
        ],
        "computations": [
            {"id": "CALC-001",
             "inputs": [{"kind": "dataset", "ref": "DS-001"}],
             "formula": "RPN = S × O × D",
             "operation": "对 8 类故障模式逐项评定 S/O/D 并相乘排序",
             "output": "RPN 最大值为 180（刹车片过度磨损）",
             "verification": "Python 脚本复核通过（numpy 乘积与排序一致）",
             "verified": True, "used_in": ["TABLE-001", "CL-002"],
             "timestamp": "2026-09-12T10:00:00+08:00"},
        ],
        "claims": [
            {"id": "CL-001",
             "claim": "刹车系统存在刹车片磨损、液压内漏、作动筒卡滞等典型故障模式",
             "claim_type": "fact", "evidence_ids": ["E-001", "E-002"],
             "analysis_ids": ["AN-001"], "chapter": 3, "confidence": "medium",
             "status": "registered"},
            {"id": "CL-002",
             "claim": "模拟数据下刹车片过度磨损模式的 RPN 最大值为 180",
             "claim_type": "calculation_result", "evidence_ids": ["E-003"],
             "analysis_ids": ["AN-001"], "chapter": 4, "confidence": "medium",
             "status": "registered"},
        ],
        "conclusions": [
            {"id": "CON-001",
             "conclusion": "刹车片磨损类故障的 RPN 最高，应作为重点维修对象",
             "claims": ["CL-001", "CL-002"], "analyses": ["AN-001"],
             "evidence": ["E-001"]},
            {"id": "CON-002",
             "conclusion": "提出以视情维修为主、定时维修为辅的维修策略框架",
             "claims": ["CL-001"], "analyses": ["AN-002"],
             "evidence": ["E-001"]},
        ],
        "figures": [
            {"id": "FIG-001", "title": "维修策略框架图",
             "related_rqs": ["RQ-02"], "related_analyses": ["AN-002"],
             "related_claims": []},
            {"id": "TABLE-001", "title": "故障模式 RPN 排序表",
             "related_rqs": ["RQ-01"], "related_analyses": ["AN-001"],
             "related_claims": ["CL-002"]},
        ],
        "conflicts": [
            {"id": "CONFLICT-001",
             "source_a": "E-002 手册章节", "source_b": "E-001 教材",
             "conflict": "两来源对液压内漏的常见诱因描述不一致",
             "resolution": "正文按教材表述并标注手册差异",
             "reason": "教材为公开出版物，手册编号待核实",
             "status": "resolved"},
        ],
    }


# ---------------- 默认（正例）文本 ----------------
def default_texts():
    return {
        "front-abstract.md": """# 摘 要

本文以民用飞机液压刹车系统为研究对象，围绕故障诊断与维修策略开展研究。采用 FMEA 方法识别刹车系统的典型故障模式，并结合 Weibull分布拟合方法分析维修间隔特征。分析结果显示，共识别出 8 类典型故障模式，其中刹车片磨损类故障的风险优先数最高，RPN 最大值为 180。针对上述结果，本文提出了以视情维修为主、定时维修为辅的维修策略。需要说明的是，本文故障数据为模拟数据，仅用于演示方法流程，不代表真实机队的统计特征。

关键词：刹车系统；故障诊断；FMEA；维修策略
""",
        "ch3-fault-modes.md": """# 第3章 刹车系统故障模式分析

## 系统组成与工作原理

本文研究对象为某型民用飞机液压刹车系统，由刹车控制单元、液压管路、刹车作动筒、刹车盘及防滞控制装置组成 [1]。系统通过液压压力驱动刹车作动筒，实现机轮制动与防滞保护功能 [1]。

## 分析与诊断方法选择

方法选择说明：本文采用 FMEA 识别故障模式，原因是 FMEA 能够系统地覆盖各子系统的潜在失效，与 FTA 相比更适合自下而上的故障识别目标；维修间隔特征分析采用 Weibull分布拟合，方法选择依据是两参数 Weibull 分布能够刻画磨损类故障的累积失效规律。

## 故障模式识别结果

依据 FMEA 分析流程，从功能、故障模式、故障原因、局部影响与最终影响五个维度开展识别，共得到 8 类典型故障模式 [1]。其中刹车片过度磨损、液压内漏、作动筒卡滞三类模式的危害度较高 [2]。
""",
        "ch4-risk-analysis.md": """# 第4章 风险优先数分析

## 模拟数据集说明

由于真实维修数据库不可用，本文构造模拟故障数据集 DS-001 用于演示分析流程，该数据集标记为【假设/模拟·仅演示方法】，其生成方法与参数假定见数据说明部分 [1]。

## RPN 计算与排序

对识别出的 8 类故障模式逐项评定严重度 S、发生度 O 与探测度 D，并按 RPN = S × O × D 计算风险优先数。计算结果显示，刹车片过度磨损模式的 RPN 最大值为 180，液压内漏模式次之。

## 结果分析

分析表明，磨损类与密封失效类故障模式的综合风险最高，应作为维修策略设计的重点对象。
""",
        "ch5-strategy.md": """# 第5章 维修策略设计

## 策略总体思路

基于第4章的风险分析结果，本文提出以视情维修为主、定时维修为辅的维修策略框架。对高风险模式采用状态监控与定期检测相结合的方式，对低风险模式保留定时维修间隔。
""",
        "conclusion.md": """# 结论

本文围绕民用飞机刹车系统的故障诊断与维修策略开展研究，采用 FMEA 方法识别出 8 类典型故障模式 [1]，并通过模拟数据完成了 RPN 计算。研究表明，刹车片过度磨损与液压内漏是风险最高的两类故障模式，应重点监控；在此基础上提出的视情维修为主、定时维修为辅的策略框架对同类机型具有一定的参考价值。

本文的研究局限如下：所采用的故障数据为模拟数据，仅用于演示方法流程，不代表真实机队的统计特征；研究结论未经过实际运行条件下的验证。
""",
        "research-plan.md": """# 研究方案

## 研究问题
- RQ-01：民用飞机刹车系统的主要故障模式及其影响是什么？
- RQ-02：面向主要故障模式应采用什么维修策略？

## 方法与依据
采用 FMEA 与 Weibull分布拟合方法，方法选择依据见第3章。

## 数据说明
DS-001 为模拟数据集，仅用于演示方法流程。
""",
    }


# ---------------- 变异 ----------------
def _find(items, iid):
    return next(x for x in items if x["id"] == iid)


def apply_variant(regs, texts, variant):
    """就地注入变异；未知 variant 抛 KeyError（防止测试静默失效）。"""
    if variant is None:
        return
    if variant == "overreach_claim":
        # 模拟数据证据 → 强断言"机队/发生率为"（应 RQG-10 Critical）
        c = _find(regs["claims"], "CL-002")
        c["claim"] = "该故障在航空公司机队中的发生率为 6.7%"
        c["analysis_ids"] = []
    elif variant == "disguised_evidence":
        # simulation 证据伪装为 verified（应 RI-E-DISGUISE Critical）
        _find(regs["evidence"], "E-003")["verification_status"] = "verified"
    elif variant == "unlabeled_synthetic":
        _find(regs["datasets"], "DS-001")["label"] = ""
    elif variant == "synthetic_label_not_in_text":
        for k in list(texts):
            texts[k] = texts[k].replace(RI.SYNTH_LABEL, "（模拟）")
    elif variant == "no_limitation_text":
        texts["conclusion.md"] = texts["conclusion.md"].replace(
            "本文的研究局限如下：所采用的故障数据为模拟数据，仅用于演示方法流程，不代表真实机队的统计特征；研究结论未经过实际运行条件下的验证。",
            "本研究工作仍将继续深入。")
    elif variant == "abstract_real_claim":
        texts["front-abstract.md"] = texts["front-abstract.md"].replace(
            "分析结果显示，", "实测结果证明，")
    elif variant == "abstract_extra_number":
        texts["front-abstract.md"] = texts["front-abstract.md"].replace(
            "RPN 最大值为 180", "RPN 最大值为 245")
    elif variant == "dangling_ref":
        _find(regs["claims"], "CL-001")["evidence_ids"] = ["E-999"]
    elif variant == "conclusion_no_trace":
        c = _find(regs["conclusions"], "CON-002")
        c["claims"], c["analyses"], c["evidence"] = [], [], []
    elif variant == "calc_no_verification":
        _find(regs["computations"], "CALC-001")["verification"] = ""
    elif variant == "orphan_figures":
        for f in regs["figures"]:
            f["related_rqs"], f["related_analyses"], f["related_claims"] = [], [], []
    elif variant == "unused_literature":
        _find(regs["evidence"], "E-001")["source"] = "教材《民用飞机液压与刹车系统》 [7]"
    elif variant == "empty_rq":
        regs["rq"] = []
    elif variant == "orphan_claim":
        regs["claims"].append({"id": "CL-003", "claim": "未被证据支持的附加论断",
                               "claim_type": "fact", "evidence_ids": [], "analysis_ids": [],
                               "chapter": 4, "confidence": "low", "status": "registered"})
    elif variant == "assumption_dataset":
        _find(regs["datasets"], "DS-001")["type"] = "assumption"
    elif variant == "calc_dangling_usedin":
        _find(regs["computations"], "CALC-001")["used_in"] = ["TABLE-999"]
    elif variant == "calc_with_constant_input":
        regs["computations"].append({
            "id": "CALC-002",
            "inputs": [{"kind": "dataset", "ref": "DS-001"},
                       {"kind": "constant", "name": "beta", "value": 1.8}],
            "formula": "beta_hat = 斜率估计",
            "output": "beta 估计值 1.8",
            "verification": "Python 复核通过", "verified": True, "used_in": []})
    elif variant == "claim_no_evidence":
        c = _find(regs["claims"], "CL-001")
        c["evidence_ids"], c["analysis_ids"] = [], []
    elif variant == "interpretation_claim":
        _find(regs["claims"], "CL-001")["claim_type"] = "interpretation"
    elif variant == "conflict_missing_reason":
        _find(regs["conflicts"], "CONFLICT-001")["reason"] = ""
    elif variant == "conflict_bad_status":
        _find(regs["conflicts"], "CONFLICT-001")["status"] = "open"
    elif variant == "conflict_pending":
        _find(regs["conflicts"], "CONFLICT-001")["status"] = "pending"
    elif variant == "short_rq":
        _find(regs["rq"], "RQ-01")["question"] = "故障有哪些"
    elif variant == "rq_no_method":
        _find(regs["rq"], "RQ-01")["related_methods"] = []
    elif variant == "rq_mismatched_objective":
        _find(regs["rq"], "RQ-01")["objective"] = "探讨维护成本构成比例"
    elif variant == "abstract_negated_real_claim":
        texts["front-abstract.md"] = texts["front-abstract.md"].replace(
            "需要说明的是，本文故障数据为模拟数据，仅用于演示方法流程，不代表真实机队的统计特征。",
            "需要说明的是，本文数据并非实测数据，仅用于演示方法流程。")
    elif variant == "nhr_weak":
        # v1.4.1：弱证据（全 simulated）且无强断言模式 → RQG-10 应转 NEEDS_HUMAN_REVIEW（非 PASS/FAIL）
        cl2 = _find(regs["claims"], "CL-002")
        cl2["evidence_ids"], cl2["analysis_ids"] = ["E-003"], []
        con2 = _find(regs["conclusions"], "CON-002")
        con2["evidence"], con2["analyses"] = ["E-003"], []
    else:
        raise KeyError(f"unknown variant: {variant}")


# ---------------- 落盘 ----------------
def write_project(root, regs=None, texts=None, variant=None):
    """将注册表与文本写入 root/.aeromech/ 结构。返回 root。"""
    regs = regs if regs is not None else default_registries()
    texts = texts if texts is not None else default_texts()
    apply_variant(regs, texts, variant)
    rdir = os.path.join(root, ".aeromech", "research")
    os.makedirs(rdir, exist_ok=True)
    for reg, items in regs.items():
        with open(os.path.join(rdir, RI.REGISTRY_SPECS[reg][0]), "w", encoding="utf-8") as f:
            yaml.safe_dump({TOP_KEYS[reg]: items}, f, allow_unicode=True, sort_keys=False)
    cdir = os.path.join(root, ".aeromech", "artifacts", "chapters")
    os.makedirs(cdir, exist_ok=True)
    for name, body in texts.items():
        if name == "research-plan.md":
            p = os.path.join(root, ".aeromech", "artifacts", name)
        else:
            p = os.path.join(cdir, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
    return root


def make_tmp_project(tmp_base, name="ri_fixture", variant=None, **kw):
    import tempfile
    root = os.path.join(tmp_base, name)
    os.makedirs(root, exist_ok=True)
    return write_project(root, variant=variant, **kw)


def make_empty_project(tmp_base, name="ri_uninit"):
    root = os.path.join(tmp_base, name)
    os.makedirs(root, exist_ok=True)
    return root
