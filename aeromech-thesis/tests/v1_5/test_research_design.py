# -*- coding: utf-8 -*-
"""test_research_design.py — Research Design Registry 与结构/一致性校验（v1.5 §4）

覆盖：positive（完整设计可解析）/ negative（缺字段、悬空引用、RQ 覆盖不足）/
boundary（无 design.yaml 的旧项目、多设计条目）/ repair（补齐后 finding 消失）。

运行：python tests/v1_5/test_research_design.py
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


def codes(res):
    return [f["code"] for f in res.get("findings", [])]


def problem_codes(root):
    return [p["code"] for p in RI.validate(root)["problems"]]


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_design_")
    print("== test_research_design ==")

    # ---------- positive：完整设计可解析且无设计缺陷 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    da = RD.analyze(root)
    check("positive status=ok", da["status"] == "ok", da.get("reason", ""))
    check("positive 读到设计条目", bool(da.get("design")) and da["design"]["id"] == "DESIGN-001")
    check("positive 读到 scope 边界", bool(da.get("scope")))
    check("positive 无 RQ_METHOD_MISMATCH", "RQ_METHOD_MISMATCH" not in codes(da))
    check("positive 注册表校验无 design 相关缺陷",
          not [c for c in problem_codes(root) if c.startswith("RI-DESIGN")],
          str(problem_codes(root))[:160])

    # ---------- negative：缺必填字段 → RI-DESIGN-FIELD ----------
    d = copy.deepcopy(F.default_design())
    del d["limitations"]
    root2 = F.write_project(os.path.join(tmp, "neg1"), design=d)
    probs = RI.validate(root2)["problems"]
    hit = [p for p in probs if p["code"] == "RI-DESIGN-FIELD" and "limitations" in p["detail"]]
    check("negative 缺 limitations 被注册表拒绝", bool(hit), str(hit)[:120])
    check("negative 缺字段条目仍可读回（不静默丢弃）",
          len(RI.load_registry(root2, "design")) == 1)

    # ---------- negative：evidence_requirement 非法枚举 ----------
    d = copy.deepcopy(F.default_design())
    d["rq_requirements"][0]["evidence_requirement"] = "whatever"
    root3 = F.write_project(os.path.join(tmp, "neg2"), design=d)
    check("negative 非法 evidence_requirement → RI-DESIGN-REQ",
          "RI-DESIGN-REQ" in problem_codes(root3))

    # ---------- negative：data_plan / analysis_plan 悬空引用 ----------
    d = copy.deepcopy(F.default_design())
    d["data_plan"] = ["DS-999"]
    d["analysis_plan"] = ["AN-777"]
    root4 = F.write_project(os.path.join(tmp, "neg3"), design=d)
    da4 = RD.analyze(root4)
    det = " | ".join(f["detail"] for f in da4["findings"])
    check("negative data_plan 悬空被识别", "DS-999" in det, det[:120])
    check("negative analysis_plan 悬空被识别", "AN-777" in det)

    # ---------- negative：design.research_questions 少列一个 RQ ----------
    d = copy.deepcopy(F.default_design())
    d["research_questions"] = ["RQ-01"]
    root5 = F.write_project(os.path.join(tmp, "neg4"), design=d)
    dg = DIA.diagnose(root5)
    check("negative 设计未覆盖全部 RQ → TRACEABILITY_GAP",
          any(x["issue_type"] == "TRACEABILITY_GAP" for x in dg["diagnoses"]),
          str([x["issue_type"] for x in dg["diagnoses"]])[:160])

    # ---------- boundary：无 design.yaml（旧项目）→ not_initialized，不报错 ----------
    root6 = F.write_project(os.path.join(tmp, "bnd1"), with_design=False)
    da6 = RD.analyze(root6)
    check("boundary 无设计时 status=not_initialized", da6["status"] == "not_initialized")
    check("boundary 无设计时不产生伪造结论", da6["findings"] == [] and da6.get("design") is None)
    feas6 = RD.feasibility(root6)
    check("boundary 无设计时可行性不判 FEASIBLE",
          feas6["verdict"] in ("NOT_APPLICABLE", "INFEASIBLE", "CONDITIONALLY_FEASIBLE"),
          feas6["verdict"])

    # ---------- boundary：多条 design 条目 → 取首条且可分析 ----------
    root7 = F.write_project(os.path.join(tmp, "bnd2"))
    two = [copy.deepcopy(F.default_design())]
    two.append(copy.deepcopy(F.default_design()))
    two[1]["id"] = "DESIGN-002"
    RI.save_registry(root7, "design", two)
    da7 = RD.analyze(root7)
    check("boundary 多设计条目仍取首条分析",
          da7["status"] == "ok" and da7["design"]["id"] == "DESIGN-001")

    # ---------- repair：补齐悬空引用后 finding 消失 ----------
    before = "DS-999" in " ".join(f["detail"] for f in RD.analyze(root4)["findings"])
    reg = RI.load_registry(root4, "design")
    reg[0]["data_plan"] = ["DS-001"]
    reg[0]["analysis_plan"] = ["AN-001"]
    RI.save_registry(root4, "design", reg)
    after = "DS-999" in " ".join(f["detail"] for f in RD.analyze(root4)["findings"])
    check("repair 悬空引用修复后 finding 消失", before and not after, f"before={before} after={after}")

    print(f"test_research_design 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
