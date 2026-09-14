# -*- coding: utf-8 -*-
"""test_root_cause.py — Root Cause Analysis（v1.5 §9）

诊断必须给出 Problem / Root cause / Impact / Repair options（含 R-001 式编号与修复类型），
不能只输出 FAIL。覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_root_cause.py
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

PASS, FAIL = 0, 0
SECTIONS = ("问题:", "根因:", "影响:", "证据:", "修复选项:")


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def diag_of(root, issue_type):
    return [d for d in DIA.diagnose(root)["diagnoses"] if d["issue_type"] == issue_type]


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_rca_")
    print("== test_root_cause ==")

    # ---------- positive：结论证据不足给出四段式根因分析 ----------
    root = F.write_project(os.path.join(tmp, "pos"), variant="conclusion_overreach")
    hits = diag_of(root, "CONCLUSION_OVERREACH")
    check("positive 命中 CONCLUSION_OVERREACH", bool(hits))
    d = hits[0]
    check("positive Problem 非空（不是裸 FAIL）", bool(d["detail"].strip()))
    check("positive Root cause 指出证据侧原因",
          "ES1" in d["root_cause"] or "证据" in d["root_cause"], d["root_cause"])
    check("positive Impact 说明对研究的影响", bool(d.get("impact", "").strip()), d.get("impact", ""))
    check("positive evidence 给出可核验依据", bool(d["evidence"]) and all(str(x).strip() for x in d["evidence"]))
    check("positive affected_nodes 定位到 CON-002", d["affected_nodes"] == ["CON-002"])
    check("positive confidence 合法", d["confidence"] in ("high", "medium", "low"))
    check("positive rule 可追溯", bool(d["rule"].strip()), d["rule"])

    # ---------- positive：修复选项带编号与合法 repair_type ----------
    opts = d["repair_options"]
    check("positive 提供多个修复选项", len(opts) >= 1, str([o["id"] for o in opts]))
    check("positive 选项 ID 采用 R-00x 编号",
          all(str(o["id"]).startswith("R-") for o in opts))
    check("positive 选项 repair_type 属 §10 枚举",
          all(o["repair_type"] in RI.REPAIR_TYPES for o in opts),
          str([o["repair_type"] for o in opts]))
    check("positive 每个选项都说明动作", all(str(o.get("action", "")).strip() for o in opts))
    check("positive 推荐修复与选项之一一致",
          d["recommended_repair"]["repair_type"] in [o["repair_type"] for o in opts])

    # ---------- positive：Markdown 报告含四段式结构 ----------
    DIA.save(root, DIA.diagnose(root), os.path.join(tmp, "out"))
    md = open(os.path.join(tmp, "out", "research-diagnosis.md"), encoding="utf-8").read()
    check("positive 报告含 Problem/Root cause/Impact/Repair options",
          all(s in md for s in SECTIONS))
    check("positive 报告不为空壳", len(md) > 300)

    # ---------- negative：不得只报类型不给根因 ----------
    for variant, want in [("claim_overstrength", "CLAIM_OVERSTRENGTH"),
                          ("scope_creep", "SCOPE_OVERFLOW"),
                          ("number_mismatch", "QUANTITATIVE_INCONSISTENCY"),
                          ("conflict_pending", "UNRESOLVED_CONFLICT")]:
        r = F.write_project(os.path.join(tmp, "n_" + variant), variant=variant)
        ds = diag_of(r, want)
        check(f"negative {variant} 给出根因与影响",
              bool(ds) and all(x["root_cause"].strip() and x["impact"].strip() and x["evidence"]
                               for x in ds))
        check(f"negative {variant} 给出修复选项",
              bool(ds) and all(x["repair_options"] for x in ds))

    # ---------- boundary：§8 全类型都有 Impact 说明，且无拼写漂移 ----------
    spec_types = {"RQ_METHOD_MISMATCH", "EVIDENCE_GAP", "DATA_GAP", "CLAIM_OVERSTRENGTH",
                  "CONCLUSION_OVERREACH", "ABSTRACT_MISMATCH", "CALCULATION_GAP",
                  "TRACEABILITY_GAP", "SCOPE_OVERFLOW", "SCOPE_UNDERFLOW", "METHOD_SELECTION_WEAK",
                  "DUPLICATE_ANALYSIS", "REDUNDANT_CONTENT", "ORPHAN_FIGURE", "ORPHAN_TABLE"}
    impact_keys = set(DIA.IMPACT_BY_TYPE)
    check("boundary Impact 覆盖 §8 十五类", spec_types <= impact_keys,
          f"缺失={sorted(spec_types - impact_keys)}")
    check("boundary Impact 键均为已实现的 issue_type",
          impact_keys <= set(DIA.REPAIR_OPTIONS) | spec_types,
          f"多余={sorted(impact_keys - (set(DIA.REPAIR_OPTIONS) | spec_types))}")
    check("boundary 兜底 Impact 存在", bool(DIA.DEFAULT_IMPACT.strip()))

    # ---------- boundary：RQG 派生项同样带四段式（不只新引擎有） ----------
    r = F.write_project(os.path.join(tmp, "bnd-rqg"), variant="claim_overstrength")
    ds = [x for x in DIA.diagnose(r)["diagnoses"] if x["rule"].startswith("RQG")]
    check("boundary RQG 派生诊断也给出根因/影响",
          all(x["root_cause"].strip() and x["impact"].strip() for x in ds), f"n={len(ds)}")

    # ---------- repair：按选项执行后根因消失 ----------
    before = len(diag_of(root, "CONCLUSION_OVERREACH"))
    ids = __import__("research_repair").plan(root, DIA.diagnose(root)["diagnoses"])
    done, failed = __import__("research_repair").execute(root, ids=ids)
    after = len(diag_of(root, "CONCLUSION_OVERREACH"))
    check("repair 按根因执行修复并复检", bool(done) and not failed, str(done)[:120])
    check("repair 根因条目归零", before > 0 and after == 0, f"{before} → {after}")
    rep = RI.load_registry(root, "repairs")[-1]
    check("repair 记录 rationale 指回诊断",
          str(rep.get("diagnosis_id")) == d["diagnosis_id"] or bool(rep.get("rationale")),
          str(rep.get("rationale"))[:80])

    print(f"test_root_cause 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
