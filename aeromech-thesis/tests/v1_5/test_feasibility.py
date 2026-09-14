# -*- coding: utf-8 -*-
"""test_feasibility.py — Research Feasibility Gate RF-01~RF-10（v1.5 §6）

输出三态 FEASIBLE / CONDITIONALLY_FEASIBLE / INFEASIBLE；INFEASIBLE 必须阻断正常生成并进入修复环。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_feasibility.py
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
RF_ALL = [f"RF-{i:02d}" for i in range(1, 11)]


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def by_rule(res):
    return {c["rule"]: c for c in res["checks"]}


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_feas_")
    print("== test_feasibility ==")

    # ---------- positive：十项齐备且全通过 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    f = RD.feasibility(root)
    got = sorted({c["rule"] for c in f["checks"]})
    check("positive RF-01~RF-10 全覆盖", got == RF_ALL, str(got))
    check("positive verdict=FEASIBLE", f["verdict"] == "FEASIBLE", f["verdict"])
    check("positive 每项都有 status 与 detail",
          all(c.get("status") and "detail" in c for c in f["checks"]))
    check("positive reasons 为空", not f["reasons"])

    # ---------- negative：真实数据需求 vs 仅模拟数据 → RF-03 FAIL + INFEASIBLE ----------
    root2 = F.write_project(os.path.join(tmp, "neg1"), variant="evidence_mismatch")
    f2 = RD.feasibility(root2)
    check("negative DESIGN-EVIDENCE MISMATCH → RF-03 FAIL",
          by_rule(f2)["RF-03"]["status"] == "FAIL", by_rule(f2)["RF-03"]["detail"][:80])
    check("negative verdict=INFEASIBLE", f2["verdict"] == "INFEASIBLE", f2["verdict"])
    check("negative INFEASIBLE 给出阻塞理由", bool(f2["reasons"]))
    dg = DIA.diagnose(root2)
    check("negative INFEASIBLE 生成 FEASIBILITY_BLOCK（critical）",
          any(x["issue_type"] == "FEASIBILITY_BLOCK" and x["severity"] == "critical"
              for x in dg["diagnoses"]), str([x["issue_type"] for x in dg["diagnoses"]])[:160])
    block = next(x for x in dg["diagnoses"] if x["issue_type"] == "FEASIBILITY_BLOCK")
    check("negative FEASIBILITY_BLOCK 不得自动修复",
          block["auto_repairable"] is False and block["disposition"] == "block")
    check("negative 同时给出设计层根因（DESIGN_EVIDENCE_MISMATCH）",
          any(x["issue_type"] == "DESIGN_EVIDENCE_MISMATCH" for x in dg["diagnoses"]))

    # ---------- negative：方法能力不覆盖 RQ 需求 → RF-05 FAIL ----------
    root3 = F.write_project(os.path.join(tmp, "neg2"), variant="rq_mismatch")
    f3 = RD.feasibility(root3)
    check("negative RQ 需求未被方法覆盖 → RF-05 FAIL",
          by_rule(f3)["RF-05"]["status"] == "FAIL", by_rule(f3)["RF-05"]["detail"][:80])
    check("negative RF-05 FAIL 使 verdict 非 FEASIBLE", f3["verdict"] != "FEASIBLE", f3["verdict"])

    # ---------- negative：研究范围过大 RF-08 / 过小 RF-09 ----------
    big = copy.deepcopy(F.default_design())
    big["rq_requirements"] = big["rq_requirements"] + [
        {"id": f"RQ-0{i}", "needs": ["fault_modes"], "evidence_requirement": "simulated_ok"}
        for i in range(3, 9)]
    root4 = F.write_project(os.path.join(tmp, "neg3"))
    RI.save_registry(root4, "rq", RI.load_registry(root4, "rq") + [
        {"id": f"RQ-0{i}", "question": f"扩展研究问题{i}", "type": "engineering",
         "status": "active", "related_methods": ["M-001"], "related_analyses": ["AN-001"],
         "related_conclusions": ["CON-001"]} for i in range(3, 9)])
    RI.save_registry(root4, "design", [big])
    f4 = RD.feasibility(root4)
    check("negative 范围过大 → RF-08 非 PASS",
          by_rule(f4)["RF-08"]["status"] != "PASS", by_rule(f4)["RF-08"]["detail"][:90])

    small = copy.deepcopy(F.default_design())
    small["expected_outputs"] = []
    small["analysis_plan"] = []
    root5 = F.write_project(os.path.join(tmp, "neg4"), design=small)
    f5 = RD.feasibility(root5)
    check("negative 范围过小 → RF-09 非 PASS",
          by_rule(f5)["RF-09"]["status"] != "PASS", by_rule(f5)["RF-09"]["detail"][:90])

    # ---------- negative：假设不合理 RF-10（模拟数据但声明无局限） ----------
    nofail = copy.deepcopy(F.default_design())
    nofail["limitations"] = []
    root6 = F.write_project(os.path.join(tmp, "neg5"), design=nofail)
    f6 = RD.feasibility(root6)
    check("negative 模拟数据未登记局限 → RF-10 非 PASS",
          by_rule(f6)["RF-10"]["status"] != "PASS", by_rule(f6)["RF-10"]["detail"][:90])

    # ---------- boundary：无 design.yaml → NOT_APPLICABLE（旧项目不误判不可行） ----------
    root7 = F.write_project(os.path.join(tmp, "bnd1"), with_design=False)
    f7 = RD.feasibility(root7)
    check("boundary 无设计时 NOT_APPLICABLE", f7["verdict"] == "NOT_APPLICABLE", f7["verdict"])
    check("boundary NOT_APPLICABLE 不产出检查项伪证", isinstance(f7["checks"], list))

    # ---------- boundary：计算不可执行 RF-06 ----------
    cal = copy.deepcopy(F.default_design())
    root8 = F.write_project(os.path.join(tmp, "bnd2"), design=cal)
    comps = RI.load_registry(root8, "computations")
    comps[0]["verified"] = False
    comps[0]["verification"] = ""
    comps[0]["recompute"] = {"cmd": "python not_exists_script_xyz.py"}
    RI.save_registry(root8, "computations", comps)
    f8 = RD.feasibility(root8)
    check("boundary 计算未复核且重算不可执行 → RF-06 非 PASS",
          by_rule(f8)["RF-06"]["status"] != "PASS", by_rule(f8)["RF-06"]["detail"][:90])

    # ---------- repair：把 RQ 的证据需求改回模拟可答 → 重新可行 ----------
    reg = RI.load_registry(root2, "design")
    check("repair 前 INFEASIBLE", RD.feasibility(root2)["verdict"] == "INFEASIBLE")
    reg[0]["rq_requirements"][0]["evidence_requirement"] = "simulated_ok"
    RI.save_registry(root2, "design", reg)
    after = RD.feasibility(root2)
    check("repair 后不再 INFEASIBLE", after["verdict"] != "INFEASIBLE", after["verdict"])
    check("repair 后 RF-03 转 PASS", by_rule(after)["RF-03"]["status"] == "PASS")
    check("repair 后 FEASIBILITY_BLOCK 消失",
          not any(x["issue_type"] == "FEASIBILITY_BLOCK" for x in DIA.diagnose(root2)["diagnoses"]))

    print(f"test_feasibility 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
