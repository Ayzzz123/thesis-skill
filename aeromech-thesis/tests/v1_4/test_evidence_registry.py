# -*- coding: utf-8 -*-
"""test_evidence_registry.py — Evidence Registry 结构/伪装检测（PASS/FAIL/boundary）

运行：python tests/v1_4/test_evidence_registry.py
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
    tmp = tempfile.mkdtemp(prefix="ri_v14_ev_")
    print("== test_evidence_registry ==")

    # ---- 正例 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    val = RI.validate(root)
    check("正例 validate ok", val["ok"], str(val["problems"][:2]))
    check("证据记录数=3", val["stats"]["evidence"] == 3)
    s, rep = run_rq(root)
    check("正例 gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))

    # ---- FAIL/Critical：simulation 伪装成 verified ----
    root2 = F.write_project(os.path.join(tmp, "disguise"), variant="disguised_evidence")
    val2 = RI.validate(root2)
    check("伪装 validate critical",
          val2["has_critical"] and any(p["code"] == "RI-E-DISGUISE" for p in val2["problems"]),
          str([p for p in val2["problems"] if p["code"] == "RI-E-DISGUISE"]))
    s2, rep2 = run_rq(root2)
    check("伪装 RQG-00 FAIL(Critical)", item(rep2, "RQG-00")["status"] == "FAIL"
          and item(rep2, "RQG-00")["severity"] == "Critical")
    check("伪装 gate=FAIL", s2["gate"] == "FAIL")

    # ---- FAIL：source_type 非法 ----
    root3 = F.write_project(os.path.join(tmp, "badtype"))
    probe(root3, "evidence", "E-001", source_type="forum")
    val3 = RI.validate(root3)
    check("非法 source_type 报 RI-E-TYPE",
          any(p["code"] == "RI-E-TYPE" for p in val3["problems"]), str(val3["problems"][:2]))

    # ---- FAIL：缺 source ----
    root4 = F.write_project(os.path.join(tmp, "nosource"))
    probe(root4, "evidence", "E-001", source="")
    val4 = RI.validate(root4)
    check("缺 source 报 RI-E-FIELD",
          any(p["code"] == "RI-E-FIELD" for p in val4["problems"]), str(val4["problems"][:2]))

    # ---- FAIL：claim_supported 悬空 ----
    root5 = F.write_project(os.path.join(tmp, "dangling"))
    probe(root5, "evidence", "E-001", claim_supported=["CL-999"])
    val5 = RI.validate(root5)
    check("claim_supported 悬空报 RI-DANGLING",
          any(p["code"] == "RI-DANGLING" for p in val5["problems"]), str(val5["problems"][:2]))

    # ---- boundary：assumption / simulated / partial / pending 合法且不升级身份 ----
    root6 = F.write_project(os.path.join(tmp, "boundary"))
    ev4 = {"id": "E-004", "source_type": "assumption", "source": "参数假定（来源不可得）",
           "source_location": "本文第4章", "claim_supported": [], "reliability": "low",
           "verification_status": "simulated", "used_in": [], "notes": "仅演示方法"}
    RI.add_entry(root6, "evidence", ev4)
    ev5 = {"id": "E-005", "source_type": "standard", "source": "相关标准条目 [9]",
           "source_location": "标准条款【待核实】", "claim_supported": [], "reliability": "medium",
           "verification_status": "pending", "used_in": [], "notes": "待核实"}
    RI.add_entry(root6, "evidence", ev5)
    val6 = RI.validate(root6)
    check("boundary assumption+simulated 合法", val6["ok"], str(val6["problems"][:2]))
    check("boundary pending 合法（不视为 verified）",
          not any(p["code"] == "RI-E-STATUS" for p in val6["problems"]))
    # 身份保持：assumption 不得标 verified
    probe(root6, "evidence", "E-004", verification_status="verified")
    val6b = RI.validate(root6)
    check("assumption 标 verified 被拦截",
          any(p["code"] == "RI-E-DISGUISE" for p in val6b["problems"]), str(val6b["problems"][:2]))

    print(f"test_evidence_registry 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
