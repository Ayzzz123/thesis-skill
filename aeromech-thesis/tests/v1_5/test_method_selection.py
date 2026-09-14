# -*- coding: utf-8 -*-
"""test_method_selection.py — Method Selection Intelligence（v1.5 §5）

要求方法选择必须给出候选、被选方法、选择理由与被拒理由；不得按题目关键词机械选定。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_method_selection.py
"""
import copy
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_design as RD
import research_diagnosis as DIA
import research_integrity as RI

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def audit_of(root, mid):
    return next((a for a in RD.analyze(root)["methods_audit"] if a["id"] == mid), None)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_msel_")
    print("== test_method_selection ==")

    # ---------- positive：每个方法都有候选 + 被选 + 理由，无弱化 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    audit = RD.analyze(root)["methods_audit"]
    check("positive 审计覆盖全部方法", len(audit) == len(RI.load_registry(root, "methods")))
    check("positive 无 METHOD_SELECTION_WEAK",
          all(not a["weak"] for a in audit), str([a["weak"] for a in audit])[:160])
    m1 = audit_of(root, "M-001")
    check("positive candidate_methods ≥2", len(m1["candidates"]) >= 2, str(m1["candidates"]))
    check("positive selected_method 在候选内", m1["selected"] in m1["candidates"])
    m1r = next(x for x in RI.load_registry(root, "methods") if x["id"] == "M-001")
    check("positive selection_reason 非空", bool(str(m1r["selection"].get("selection_reason", "")).strip()))
    check("positive 每个候选都给出取舍理由",
          all(str(c.get("reason", "")).strip() for c in m1r["selection"]["candidates"]))
    check("positive 被拒候选也说明了原因（reason 覆盖非选中项）",
          all(str(c.get("reason", "")).strip() for c in m1r["selection"]["candidates"]
              if c.get("name") != m1r["selection"].get("selected")))

    # ---------- negative：只有 1 个候选 + 无理由（题目关键词式选择） ----------
    root2 = F.write_project(os.path.join(tmp, "neg1"), variant="method_weak")
    a2 = audit_of(root2, "M-001")
    check("negative 候选不足被标记", any("候选" in w for w in a2["weak"]), str(a2["weak"]))
    check("negative 缺选择理由被标记", any("selection_reason" in w for w in a2["weak"]))
    dg = DIA.diagnose(root2)
    check("negative 产生 METHOD_SELECTION_WEAK 诊断",
          any(x["issue_type"] == "METHOD_SELECTION_WEAK" for x in dg["diagnoses"]),
          str([x["issue_type"] for x in dg["diagnoses"]])[:160])
    item = next(x for x in dg["diagnoses"] if x["issue_type"] == "METHOD_SELECTION_WEAK")
    check("negative 非自动可修（须人工补论证）",
          item["auto_repairable"] is False and item["human_review_required"] is True)

    # ---------- negative：selected 不在候选列表中 ----------
    regs = RI.load_registry(root, "methods")
    m = next(x for x in regs if x["id"] == "M-002")
    m["selection"]["selected"] = "蒙特卡洛模拟"
    root3 = F.write_project(os.path.join(tmp, "neg2"))
    RI.save_registry(root3, "methods", copy.deepcopy(regs))
    a3 = audit_of(root3, "M-002")
    check("negative 被选方法不在候选内被标记",
          any("候选" in w or "selected" in w for w in a3["weak"]), str(a3["weak"]))

    # ---------- boundary：方法完全没有 selection 块 ----------
    regs = RI.load_registry(root, "methods")
    for x in regs:
        x.pop("selection", None)
    root4 = F.write_project(os.path.join(tmp, "bnd1"))
    RI.save_registry(root4, "methods", regs)
    audit4 = RD.analyze(root4)["methods_audit"]
    check("boundary 无 selection 不崩溃且全部标记弱化",
          len(audit4) == 3 and all(a["weak"] for a in audit4), str(audit4)[:160])

    # ---------- boundary：无 design.yaml 时返回结构完整（不做方法审计，不抛 KeyError） ----------
    root5 = F.write_project(os.path.join(tmp, "bnd2"), with_design=False)
    da5 = RD.analyze(root5)
    check("boundary 无设计时结构完整且 methods_audit 为空",
          da5["status"] == "not_initialized" and da5["methods_audit"] == [])

    # ---------- repair：补齐候选与理由后弱化消失 ----------
    check("repair 前 M-001 有弱化", bool(audit_of(root2, "M-001")["weak"]))
    regs = RI.load_registry(root2, "methods")
    m = next(x for x in regs if x["id"] == "M-001")
    m["selection"] = {
        "candidates": [
            {"name": "FMEA", "reason": "自下而上识别故障模式并给出风险排序，匹配现有证据能力"},
            {"name": "FTA", "reason": "需要顶事件概率与底事件失效率数据，本研究无真实数据支撑"},
        ],
        "selected": "FMEA",
        "selection_reason": "研究目标为模式识别与优先级排序，概率推断所需的可靠失效率数据不可得",
    }
    RI.save_registry(root2, "methods", regs)
    a_after = audit_of(root2, "M-001")
    check("repair 补齐后 M-001 弱化消失", a_after["weak"] == [], str(a_after["weak"]))
    dg2 = DIA.diagnose(root2)
    check("repair 后不再报 METHOD_SELECTION_WEAK",
          not any(x["issue_type"] == "METHOD_SELECTION_WEAK" for x in dg2["diagnoses"]))

    print(f"test_method_selection 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
