# -*- coding: utf-8 -*-
"""test_computation_provenance.py — Computation Registry（CALC inputs/formula/verification/used_in）

运行：python tests/v1_4/test_computation_provenance.py
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


def probe(root, reg, iid, **kw):
    def fn(items):
        it = next(x for x in items if x["id"] == iid)
        it.update(kw)
    mutate(root, reg, fn)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_calc_")
    print("== test_computation_provenance ==")

    # ---- 正例 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    calc = RI.load_registry(root, "computations")[0]
    check("CALC-001 输入指向 DS-001", calc["inputs"][0]["ref"] == "DS-001")
    check("CALC-001 含公式", bool(calc["formula"]))
    check("CALC-001 含验证", bool(calc["verification"]))
    check("CALC-001 used_in 含 TABLE-001/CL-002",
          "TABLE-001" in calc["used_in"] and "CL-002" in calc["used_in"])
    val = RI.validate(root)
    check("正例 validate ok", val["ok"], str(val["problems"][:2]))
    s, rep = run_rq(root)
    check("RQG-14 PASS", item(rep, "RQG-14")["status"] == "PASS")
    check("正例 gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))

    # ---- FAIL：缺验证方式 ----
    root2 = F.write_project(os.path.join(tmp, "noverify"), variant="calc_no_verification")
    val2 = RI.validate(root2)
    check("缺验证报 RI-CALC-FIELD",
          any(p["code"] == "RI-CALC-FIELD" for p in val2["problems"]), str(val2["problems"][:2]))
    s2, rep2 = run_rq(root2)
    check("缺验证 RQG-14 FAIL(High)", item(rep2, "RQG-14")["status"] == "FAIL"
          and item(rep2, "RQG-14")["severity"] == "High")
    check("缺验证 gate=FAIL", s2["gate"] == "FAIL")

    # ---- FAIL：used_in 悬空 ----
    root3 = F.write_project(os.path.join(tmp, "dangling"), variant="calc_dangling_usedin")
    val3 = RI.validate(root3)
    check("used_in 悬空报 RI-DANGLING",
          any(p["code"] == "RI-DANGLING" for p in val3["problems"]), str(val3["problems"][:2]))

    # ---- FAIL：无输入 ----
    root4 = F.write_project(os.path.join(tmp, "noinput"))
    probe(root4, "computations", "CALC-001", inputs=[])
    val4 = RI.validate(root4)
    check("无输入报 RI-CALC-FIELD",
          any(p["code"] == "RI-CALC-FIELD" for p in val4["problems"]), str(val4["problems"][:2]))
    s4, rep4 = run_rq(root4)
    check("无输入 RQG-14 FAIL", item(rep4, "RQG-14")["status"] == "FAIL")

    # ---- boundary：数据集输入 + 常量参数混合合法 ----
    root5 = F.write_project(os.path.join(tmp, "const"), variant="calc_with_constant_input")
    val5 = RI.validate(root5)
    check("常量+数据集输入 validate ok", val5["ok"], str(val5["problems"][:2]))
    s5, rep5 = run_rq(root5)
    check("常量+数据集输入 RQG-14 PASS", item(rep5, "RQG-14")["status"] == "PASS")

    # ---- boundary：CALC ID 前缀必须为 CALC-XXX ----
    root6 = F.write_project(os.path.join(tmp, "badid"))
    probe(root6, "computations", "CALC-001", id="C-001")
    val6 = RI.validate(root6)
    check("非法 CALC ID 报 RI-ID-FORMAT/RI-CALC-ID",
          any(p["code"] in ("RI-ID-FORMAT", "RI-CALC-ID") for p in val6["problems"]),
          str(val6["problems"][:2]))

    print(f"test_computation_provenance 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
