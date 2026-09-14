# -*- coding: utf-8 -*-
"""test_repair_plan.py — Repair Plan Registry REP-001…（v1.5 §10/§11）

校验修复计划条目字段、repair_type 枚举、去重策略与"白名单之外不建单"。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_repair_plan.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_diagnosis as DIA
import research_integrity as RI
import research_repair as RP

PASS, FAIL = 0, 0
REQUIRED_REP_FIELDS = ["diagnosis_id", "target_nodes", "repair_type", "before", "after",
                       "rationale", "expected_effect", "risk", "status"]


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def reps(root):
    return RI.load_registry(root, "repairs") or []


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_plan_")
    print("== test_repair_plan ==")

    # ---------- positive：自动项建单且字段齐备 ----------
    root = F.write_project(os.path.join(tmp, "pos"), variant="claim_overstrength")
    diags = DIA.diagnose(root)["diagnoses"]
    ids = RP.plan(root, diags)
    check("positive 生成修复单", bool(ids), str(ids))
    check("positive ID 采用 REP-00x", all(str(i).startswith("REP-") for i in ids), str(ids))
    r = reps(root)[0]
    check("positive §10 字段齐备", all(k in r for k in REQUIRED_REP_FIELDS),
          str([k for k in REQUIRED_REP_FIELDS if k not in r]))
    check("positive repair_type 属 §10 枚举", r["repair_type"] in RI.REPAIR_TYPES, r["repair_type"])
    check("positive status 初始为 proposed", r["status"] == "proposed")
    check("positive target_nodes 指回受影响节点", r["target_nodes"] == ["CL-002"], str(r["target_nodes"]))
    check("positive diagnosis_id 可回溯",
          r["diagnosis_id"] in [d["diagnosis_id"] for d in diags])
    check("positive rationale/expected_effect/risk 均非空",
          all(str(r.get(k, "")).strip() for k in ("rationale", "expected_effect", "risk")))
    check("positive 标记 auto", r["auto"] is True)

    # ---------- negative：人工判定类不得建自动单 ----------
    root2 = F.write_project(os.path.join(tmp, "neg1"), variant="scope_creep")
    ids2 = RP.plan(root2, DIA.diagnose(root2)["diagnoses"])
    check("negative SCOPE_OVERFLOW 不建自动修复单", ids2 == [], str(ids2))
    check("negative 未越权修改注册表", not reps(root2))
    root3 = F.write_project(os.path.join(tmp, "neg2"), variant="conflict_pending")
    check("negative 冲突不建单（不得静默选择来源）",
          RP.plan(root3, DIA.diagnose(root3)["diagnoses"]) == [])

    # ---------- negative：白名单之外的 operation 一律不建单 ----------
    fake = [{"diagnosis_id": "DIAG-FAKE1", "issue_type": "EVIDENCE_GAP", "severity": "high",
             "affected_nodes": ["CL-001"], "detail": "缺证据", "auto_repairable": True,
             "recommended_repair": {"repair_type": "ADD_EVIDENCE", "operation": "fabricate_evidence",
                                    "payload": {}}}]
    root4 = F.write_project(os.path.join(tmp, "neg3"))
    n0 = len(reps(root4))
    check("negative 非白名单 operation 被拒绝", RP.plan(root4, fake) == [])
    check("negative 白名单集合恰为四项",
          RP.AUTO_OPERATIONS == {"downgrade_wording", "number_sync", "recompute", "fix_synth_label"},
          str(sorted(RP.AUTO_OPERATIONS)))
    check("negative 未产生任何条目", len(reps(root4)) == n0)

    # ---------- boundary：无诊断文件 → 友好提示且不建单 ----------
    root5 = F.write_project(os.path.join(tmp, "bnd1"))
    missing = os.path.join(root5, ".aeromech", "artifacts", "analysis", "research-diagnosis.json")
    if os.path.isfile(missing):
        os.remove(missing)
    check("boundary 缺诊断 JSON 时返回空列表", RP.plan(root5) == [])
    check("boundary 空诊断列表可安全调用", RP.plan(root5, []) == [])

    # ---------- boundary：同一诊断重复 plan 不重复建单 ----------
    n_before = len(reps(root))
    RP.plan(root, diags)
    check("boundary 重复 plan 不产生重复条目", len(reps(root)) == n_before, str(len(reps(root))))

    # ---------- boundary：同一问题被两条规则命中只建一单 ----------
    dup = [dict(diags[0], diagnosis_id="DIAG-AAA111"), dict(diags[0], diagnosis_id="DIAG-BBB222")]
    n_before = len(reps(root))
    RP.plan(root, dup)
    check("boundary 多规则命中同一动作只建一单", len(reps(root)) == n_before)

    # ---------- boundary：同一目标上的不同修复各自建单 ----------
    two = [
        {"diagnosis_id": "DIAG-C1", "issue_type": "CLAIM_OVERSTRENGTH", "severity": "critical",
         "affected_nodes": ["CL-001"], "detail": "强断言", "auto_repairable": True,
         "recommended_repair": {"repair_type": "REVISE_CLAIM", "operation": "downgrade_wording",
                                "payload": {"claim_id": "CL-001"}}},
        {"diagnosis_id": "DIAG-C2", "issue_type": "QUANTITATIVE_INCONSISTENCY", "severity": "high",
         "affected_nodes": ["ABSTRACT"], "detail": "数字不一致", "auto_repairable": True,
         "recommended_repair": {"repair_type": "REVISE_ABSTRACT", "operation": "number_sync",
                                "payload": {"old": "9", "new": "8"}}},
    ]
    n_before = len(reps(root))
    made = RP.plan(root, two)
    check("boundary 不同目标/不同动作各自建单", len(made) == 2 and len(reps(root)) == n_before + 2,
          str(made))

    # ---------- repair：执行后状态推进且注册表校验通过 ----------
    done, failed = RP.execute(root, ids=ids)
    check("repair 执行成功", bool(done) and not failed, str(done)[:120])
    r_after = next(x for x in reps(root) if x["id"] == ids[0])
    check("repair 状态推进为 verified", r_after["status"] == "verified", r_after.get("verification", ""))
    check("repair after 记录实际改动", bool((r_after.get("after") or {}).get("result")))
    probs = [p for p in RI.validate(root)["problems"] if "repairs" in str(p.get("where", ""))]
    check("repair 后 repairs 注册表校验无缺陷", not probs, str(probs)[:160])
    st = RP.status(root)
    check("repair status 汇总可读", isinstance(st, dict) and st, str(st)[:120])

    print(f"test_repair_plan 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
