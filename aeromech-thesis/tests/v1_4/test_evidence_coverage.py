# -*- coding: utf-8 -*-
"""test_evidence_coverage.py — Evidence Coverage Ratio 与状态四分类

运行：python tests/v1_4/test_evidence_coverage.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
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


def mutate(root, reg, fn):
    items = RI.load_registry(root, reg)
    fn(items)
    RI.save_registry(root, reg, items)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_cov_")
    print("== test_evidence_coverage ==")

    # ---- 正例：2/2 = 1.0，状态四分类 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    cov = RI.coverage(root)
    check("coverage=1.0", cov["evidence_coverage_ratio"] == 1.0, str(cov))
    check("需要证据的 core claim=2", cov["claims_need_evidence"] == 2)
    check("被覆盖=2", cov["claims_covered"] == 2)
    check("uncovered=[]", cov["uncovered"] == [])
    check("状态分布 verified=1/partial=1/simulated=1",
          cov["evidence_by_status"] == {"verified": 1, "partial": 1, "pending": 0, "simulated": 1},
          str(cov["evidence_by_status"]))

    # ---- 身份保持：simulated 证据不得计入 verified ----
    cl2 = next(d for d in cov["details"] if d["claim"] == "CL-002")
    check("CL-002 标记 simulated=True", cl2["simulated"] is True)
    check("CL-002 未混入 verified 桶", "verified" not in cl2["statuses"])

    # ---- FAIL：核心论断无证据 → 覆盖率下降 ----
    root2 = F.write_project(os.path.join(tmp, "noev"), variant="claim_no_evidence")
    cov2 = RI.coverage(root2)
    check("无证据 claim 后 ratio=0.5", cov2["evidence_coverage_ratio"] == 0.5, str(cov2))
    check("uncovered 含 CL-001", "CL-001" in cov2["uncovered"])

    # ---- boundary：interpretation 类不计入分母 ----
    root3 = F.write_project(os.path.join(tmp, "interp"), variant="interpretation_claim")
    cov3 = RI.coverage(root3)
    check("interpretation 不计入分母", cov3["claims_need_evidence"] == 1, str(cov3))
    check("boundary ratio=1.0", cov3["evidence_coverage_ratio"] == 1.0)

    # ---- boundary：无 claims 时 ratio 缺省=1.0 ----
    root4 = F.write_project(os.path.join(tmp, "noclaims"))

    def _clear(items):
        items.clear()
    mutate(root4, "claims", _clear)
    cov4 = RI.coverage(root4)
    check("无 claims ratio=1.0 且 need=0",
          cov4["evidence_coverage_ratio"] == 1.0 and cov4["claims_need_evidence"] == 0, str(cov4))

    # ---- boundary：partial 证据计入覆盖但保留 partial 标记 ----
    root5 = F.write_project(os.path.join(tmp, "partial"))

    def _partial(items):
        items[0]["evidence_ids"] = ["E-002"]  # partial
        items[0]["analysis_ids"] = []
    mutate(root5, "claims", _partial)
    cov5 = RI.coverage(root5)
    c = next(d for d in cov5["details"] if d["claim"] == "CL-001")
    check("partial 计入覆盖", "CL-001" not in cov5["uncovered"])
    check("partial 保留标记", c["partial"] is True)

    print(f"test_evidence_coverage 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
