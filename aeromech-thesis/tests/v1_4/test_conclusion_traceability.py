# -*- coding: utf-8 -*-
"""test_conclusion_traceability.py — 结论可追溯与证据越界（RQG-08/RQG-10）

运行：python tests/v1_4/test_conclusion_traceability.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_integrity as RI
import research_quality_qa as RQ

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def run_rq(root):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        s, rep = RQ.run(root)
    return s, rep


def item(rep, code):
    return next((i for i in rep.items if i["code"] == code), None)


def mutate(root, reg, fn):
    items = RI.load_registry(root, reg)
    fn(items)
    RI.save_registry(root, reg, items)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_con_")
    print("== test_conclusion_traceability ==")

    # ---- 正例 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    val = RI.validate(root)
    check("正例 validate ok", val["ok"], str(val["problems"][:2]))
    s, rep = run_rq(root)
    check("RQG-08 PASS", item(rep, "RQG-08")["status"] == "PASS")
    check("RQG-10 PASS", item(rep, "RQG-10")["status"] == "PASS")
    check("正例 gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))

    # ---- FAIL：结论无分析链 ----
    root2 = F.write_project(os.path.join(tmp, "notrace"), variant="conclusion_no_trace")
    val2 = RI.validate(root2)
    check("断链结论报 RI-CON-TRACE",
          any(p["code"] == "RI-CON-TRACE" for p in val2["problems"]), str(val2["problems"][:2]))
    s2, rep2 = run_rq(root2)
    check("断链结论 RQG-08 FAIL(High)", item(rep2, "RQG-08")["status"] == "FAIL"
          and item(rep2, "RQG-08")["severity"] == "High")
    check("断链结论 gate=FAIL", s2["gate"] == "FAIL")

    # ---- FAIL/Critical：证据越界（模拟数据 → "机队发生率为…"）----
    root3 = F.write_project(os.path.join(tmp, "overreach"), variant="overreach_claim")
    s3, rep3 = run_rq(root3)
    r10 = item(rep3, "RQG-10")
    check("越界 RQG-10 FAIL(Critical)", r10["status"] == "FAIL" and r10["severity"] == "Critical")
    check("越界详情含 CL-002", "CL-002" in r10["detail"], r10["detail"][:60])
    check("越界 gate=FAIL", s3["gate"] == "FAIL")
    check("越界 report 写入 FAIL",
          "RI Gate: FAIL" in open(os.path.join(root3, ".aeromech", "artifacts", "qa",
                                               "research-quality-report.md"), encoding="utf-8").read())

    # ---- boundary：结论仅链接分析（无 claims）仍可追溯 ----
    root4 = F.write_project(os.path.join(tmp, "anonly"))
    items = RI.load_registry(root4, "conclusions")
    items[1]["claims"] = []
    RI.save_registry(root4, "conclusions", items)
    val4 = RI.validate(root4)
    check("仅分析链结论 validate ok", val4["ok"], str(val4["problems"][:2]))
    s4, rep4 = run_rq(root4)
    check("仅分析链结论 RQG-08 PASS", item(rep4, "RQG-08")["status"] == "PASS")

    # ---- boundary：结论链接 pending/partial 证据不判越界 ----
    root5 = F.write_project(os.path.join(tmp, "pending"))
    items = RI.load_registry(root5, "conclusions")
    items[0]["claims"], items[0]["analyses"] = [], []
    items[0]["evidence"] = ["E-002"]  # partial
    RI.save_registry(root5, "conclusions", items)
    s5, rep5 = run_rq(root5)
    check("partial 证据结论 RQG-10 PASS", item(rep5, "RQG-10")["status"] == "PASS")

    print(f"test_conclusion_traceability 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
