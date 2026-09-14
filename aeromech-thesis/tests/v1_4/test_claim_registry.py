# -*- coding: utf-8 -*-
"""test_claim_registry.py — Claim Registry 类型/证据需求规则（PASS/FAIL/boundary）

运行：python tests/v1_4/test_claim_registry.py
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
    tmp = tempfile.mkdtemp(prefix="ri_v14_cl_")
    print("== test_claim_registry ==")

    # ---- 正例：一 Claim 多 Evidence；一 Evidence 支持多 Claim ----
    root = F.write_project(os.path.join(tmp, "pos"))
    val = RI.validate(root)
    check("正例 validate ok", val["ok"], str(val["problems"][:2]))
    claims = RI.load_registry(root, "claims")
    cl1 = next(x for x in claims if x["id"] == "CL-001")
    check("CL-001 链到 2 条证据", len(cl1["evidence_ids"]) == 2)
    s, rep = run_rq(root)
    check("正例 gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))

    # ---- FAIL：fact 类论断无证据 ----
    root2 = F.write_project(os.path.join(tmp, "noev"), variant="claim_no_evidence")
    val2 = RI.validate(root2)
    check("无证据 fact 报 RI-CL-NOEVID",
          any(p["code"] == "RI-CL-NOEVID" for p in val2["problems"]), str(val2["problems"][:2]))
    s2, rep2 = run_rq(root2)
    check("无证据 RQG-00 FAIL(High)", item(rep2, "RQG-00")["status"] == "FAIL"
          and item(rep2, "RQG-00")["severity"] == "High")
    check("无证据 gate=FAIL", s2["gate"] == "FAIL")

    # ---- FAIL：claim_type 非法 ----
    root3 = F.write_project(os.path.join(tmp, "badtype"))
    probe(root3, "claims", "CL-001", claim_type="opinion")
    val3 = RI.validate(root3)
    check("非法 claim_type 报 RI-CL-TYPE",
          any(p["code"] == "RI-CL-TYPE" for p in val3["problems"]), str(val3["problems"][:2]))

    # ---- FAIL：evidence_ids 悬空 ----
    root4 = F.write_project(os.path.join(tmp, "dangling"), variant="dangling_ref")
    val4 = RI.validate(root4)
    check("evidence_ids 悬空报 RI-DANGLING",
          any(p["code"] == "RI-DANGLING" for p in val4["problems"]), str(val4["problems"][:2]))

    # ---- boundary：interpretation 类默认不需证据 ----
    root5 = F.write_project(os.path.join(tmp, "interp"), variant="interpretation_claim")
    val5 = RI.validate(root5)
    check("interpretation 无证据合法", val5["ok"], str(val5["problems"][:2]))

    # ---- boundary：显式 evidence_required=false 的 fact 不再强制 ----
    root6 = F.write_project(os.path.join(tmp, "explicit"))
    probe(root6, "claims", "CL-001", evidence_ids=[], analysis_ids=[], evidence_required=False)
    val6 = RI.validate(root6)
    check("显式 evidence_required=false 合法",
          not any(p["code"] == "RI-CL-NOEVID" for p in val6["problems"]), str(val6["problems"][:2]))

    # ---- boundary：六种 claim_type 全部合法 ----
    root7 = F.write_project(os.path.join(tmp, "types"))
    for i, t in enumerate(RI.CLAIM_TYPES, start=10):
        RI.add_entry(root7, "claims", {
            "id": f"CL-{i:03d}", "claim": f"类型测试论断 {t}", "claim_type": t,
            "evidence_ids": ["E-001"], "analysis_ids": [], "chapter": 4,
            "confidence": "low", "status": "registered"})
    val7 = RI.validate(root7)
    check("六种 claim_type 全部合法",
          not any(p["code"] == "RI-CL-TYPE" for p in val7["problems"]), str(val7["problems"][:2]))

    print(f"test_claim_registry 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
