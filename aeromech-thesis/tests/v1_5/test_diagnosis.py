# -*- coding: utf-8 -*-
"""test_diagnosis.py — Research Diagnosis Engine（v1.5 §8）

校验诊断条目字段齐备、issue_type 覆盖 §8 列表、严重度/处置分类、稳定 ID 与退出码。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_diagnosis.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_diagnosis as DIA

PASS, FAIL = 0, 0
SCRIPTS = os.path.join(SKILL, "scripts")

REQUIRED_FIELDS = ["diagnosis_id", "severity", "issue_type", "affected_nodes", "root_cause",
                   "evidence", "recommended_repair", "confidence", "auto_repairable",
                   "human_review_required"]
SPEC_TYPES = ["RQ_METHOD_MISMATCH", "EVIDENCE_GAP", "DATA_GAP", "CLAIM_OVERSTRENGTH",
              "CONCLUSION_OVERREACH", "ABSTRACT_MISMATCH", "CALCULATION_GAP", "TRACEABILITY_GAP",
              "SCOPE_OVERFLOW", "SCOPE_UNDERFLOW", "METHOD_SELECTION_WEAK", "DUPLICATE_ANALYSIS",
              "REDUNDANT_CONTENT", "ORPHAN_FIGURE", "ORPHAN_TABLE"]


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def run(script, *args):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def emitted_types():
    """静态收集诊断引擎可产出的 issue_type（含设计层与 RQG 派生）。"""
    out = set()
    for fname in ("research_diagnosis.py", "research_design.py"):
        s = open(os.path.join(SCRIPTS, fname), encoding="utf-8").read()
        out |= set(re.findall(r'b\.add\("([A-Z_0-9]+)"', s))
        out |= set(re.findall(r'_finding\("([A-Z_0-9]+)"', s))
        out |= set(re.findall(r'^\s+"([A-Z_0-9]{4,})":', s, re.M))
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_diag_")
    print("== test_diagnosis ==")

    # ---------- positive：干净项目 0 诊断，字段与产物齐备 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    res = DIA.diagnose(root)
    check("positive status=ok", res["status"] == "ok")
    check("positive 干净项目无 open 诊断", res["counts"]["total"] == 0,
          str([d["issue_type"] for d in res["diagnoses"]])[:160])
    rc, out = run("research_diagnosis.py", root, "--out", os.path.join(tmp, "out_pos"))
    check("positive CLI rc=0（无问题）", rc == 0, out[:160])
    jp = os.path.join(tmp, "out_pos", "research-diagnosis.json")
    mp = os.path.join(tmp, "out_pos", "research-diagnosis.md")
    check("positive 生成 JSON 产物", os.path.isfile(jp))
    check("positive 生成 Markdown 产物", os.path.isfile(mp))
    check("positive JSON 可解析", isinstance(json.load(open(jp, encoding="utf-8")), dict))

    # ---------- negative：缺陷矩阵 → 期望 issue_type ----------
    matrix = {
        "rq_mismatch": "RQ_METHOD_MISMATCH",
        "evidence_mismatch": "DESIGN_EVIDENCE_MISMATCH",
        "method_weak": "METHOD_SELECTION_WEAK",
        "claim_overstrength": "CLAIM_OVERSTRENGTH",
        "conclusion_overreach": "CONCLUSION_OVERREACH",
        "number_mismatch": "QUANTITATIVE_INCONSISTENCY",
        "abstract_unique": "ABSTRACT_MISMATCH",
        "scope_creep": "SCOPE_OVERFLOW",
        "scope_under": "SCOPE_UNDERFLOW",
        "orphan_fig": "ORPHAN_FIGURE",
        "conflict_pending": "UNRESOLVED_CONFLICT",
        "duplicate_analysis": "DUPLICATE_ANALYSIS",
        "redundant_content": "REDUNDANT_CONTENT",
    }
    for variant, want in matrix.items():
        r = F.write_project(os.path.join(tmp, "n_" + variant), variant=variant)
        ds = DIA.diagnose(r)["diagnoses"]
        types = [d["issue_type"] for d in ds]
        check(f"negative {variant} → {want}", want in types, str(types)[:140])
        hit = [d for d in ds if d["issue_type"] == want]
        if hit:
            check(f"negative {variant} 字段齐备",
                  all(k in hit[0] for k in REQUIRED_FIELDS))
            check(f"negative {variant} 给出受影响节点", bool(hit[0]["affected_nodes"]))
            check(f"negative {variant} 严重度合法",
                  hit[0]["severity"] in ("critical", "high", "medium", "low"))
            check(f"negative {variant} 处置合法",
                  hit[0]["disposition"] in ("auto", "queue", "block"))

    # ---------- negative：CALCULATION_GAP / DATA_GAP / EVIDENCE_GAP / TRACEABILITY_GAP 可达 ----------
    r = F.write_project(os.path.join(tmp, "n_calc"), variant="calc_gap_recompute")
    ds = [d["issue_type"] for d in DIA.diagnose(r)["diagnoses"]]
    check("negative calc_gap 变体报 CALCULATION_GAP", "CALCULATION_GAP" in ds, str(ds)[:140])
    check("negative 未复核计算允许自动重算",
          any(d["issue_type"] == "CALCULATION_GAP" and d["auto_repairable"]
              for d in DIA.diagnose(r)["diagnoses"]))

    # ---------- boundary：§8 要求的 15 类 issue_type 均可产出 ----------
    have = emitted_types()
    missing = [t for t in SPEC_TYPES if t not in have]
    check("boundary §8 十五类 issue_type 全部受支持", not missing, f"缺失={missing}")

    # ---------- boundary：未初始化项目 → not_initialized，不产出诊断 ----------
    empty = os.path.join(tmp, "empty")
    os.makedirs(empty, exist_ok=True)
    res2 = DIA.diagnose(empty)
    check("boundary 未初始化 status=not_initialized", res2["status"] == "not_initialized")
    check("boundary 未初始化 diagnoses 为空", res2["diagnoses"] == [])
    rc2, out2 = run("research_diagnosis.py", empty)
    check("boundary 未初始化 CLI rc=2", rc2 == 2, f"rc={rc2} {out2[:80]}")

    # ---------- boundary：注册表损坏 → ERROR rc=3，不得伪报无问题 ----------
    bad = F.write_project(os.path.join(tmp, "corrupt"))
    open(os.path.join(bad, ".aeromech", "research", "claims.yaml"), "w", encoding="utf-8").write(
        "claims: [ {id: CL-001,, broken\n")
    rc3, out3 = run("research_diagnosis.py", bad)
    check("boundary 损坏注册表 CLI rc=3", rc3 == 3, f"rc={rc3} {out3[:120]}")
    check("boundary 损坏注册表不输出 PASS 结论", "无问题" not in out3 and "PASS" not in out3)

    # ---------- boundary：稳定 ID（同项目两次运行一致）与排序 ----------
    r = F.write_project(os.path.join(tmp, "stable"), variant="claim_overstrength")
    ids1 = [d["diagnosis_id"] for d in DIA.diagnose(r)["diagnoses"]]
    ids2 = [d["diagnosis_id"] for d in DIA.diagnose(r)["diagnoses"]]
    check("boundary diagnosis_id 跨运行稳定", ids1 == ids2 and ids1)
    r2 = F.write_project(os.path.join(tmp, "mix"), variant="infeasible")
    ds = DIA.diagnose(r2)["diagnoses"]
    order = [d["priority_class"] for d in ds]
    check("boundary 诊断按 §13 优先级排序", order == sorted(order), str(order))
    check("boundary Critical 排在 High 之前",
          not ds or (ds[0]["severity"] == "critical" and ds[0]["issue_type"] == "FEASIBILITY_BLOCK"),
          str([(d["severity"], d["issue_type"]) for d in ds])[:140])

    # ---------- repair：消除根因后诊断条目归零 ----------
    r3 = F.write_project(os.path.join(tmp, "rep"), variant="orphan_fig")
    before = [d["issue_type"] for d in DIA.diagnose(r3)["diagnoses"]]
    check("repair 前存在 ORPHAN_FIGURE", "ORPHAN_FIGURE" in before)
    figs = __import__("research_integrity").load_registry(r3, "figures")
    next(x for x in figs if x["id"] == "FIG-001")["related_analyses"] = ["AN-002"]
    __import__("research_integrity").save_registry(r3, "figures", figs)
    after = [d["issue_type"] for d in DIA.diagnose(r3)["diagnoses"]]
    check("repair 后 ORPHAN_FIGURE 消失", "ORPHAN_FIGURE" not in after, str(after)[:140])

    print(f"test_diagnosis 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
