# -*- coding: utf-8 -*-
"""test_quality_score.py — Research Quality Score（v1.5 §14）

八维 0~100 + Overall；综合分不得掩盖 Critical/High 完整性问题（blocked 时不具交付权威性）。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_quality_score.py
"""
import os
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
import research_quality_score as QS

PASS, FAIL = 0, 0
SCRIPTS = os.path.join(SKILL, "scripts")
DIMS = ["Research Design", "Evidence", "Data", "Analysis", "Argumentation",
        "Conclusion", "Citation", "Coherence"]


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def open_findings(root):
    return [d for d in DIA.diagnose(root)["diagnoses"] if d["status"] == "open"]


def score_of(root):
    return QS.compute(root, findings=open_findings(root))


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_score_")
    print("== test_quality_score ==")

    # ---------- positive：八维齐备、满分基线、overall 为均值 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    s = score_of(root)
    check("positive 八维全部存在", all(d in s["dimensions"] for d in DIMS),
          str(sorted(s["dimensions"]))[:200])
    check("positive 分值 0~100", all(0 <= v["score"] <= 100 for v in s["dimensions"].values()))
    check("positive overall = 维度均值",
          abs(s["overall"] - round(sum(v["score"] for v in s["dimensions"].values()) / len(DIMS))) <= 1,
          str(s["overall"]))
    check("positive 干净项目高分", s["overall"] >= 90, str(s["overall"]))
    check("positive 未阻断时 authoritative=True", s["blocked"] is False and s["authoritative"] is True)
    check("positive 每维记录扣分依据",
          all("deductions" in v for v in s["dimensions"].values()))

    # ---------- negative：Critical 存在时 blocked，总分不作放行依据 ----------
    r2 = F.write_project(os.path.join(tmp, "crit"), variant="claim_overstrength")
    s2 = score_of(r2)
    crit = [d for d in open_findings(r2) if d["severity"] == "critical"]
    check("negative 存在 Critical 未解决项", bool(crit))
    check("negative Critical → blocked", s2["blocked"] is True)
    check("negative blocked 时不具权威性", s2["authoritative"] is False)
    check("negative 扣分不掩盖 Critical（即使 overall 仍高）",
          s2["block_reasons"] and crit, str(s2["block_reasons"])[:120])
    check("negative 相关维度被扣分",
          any(v["score"] < 100 for v in s2["dimensions"].values()),
          str({k: v["score"] for k, v in s2["dimensions"].items() if v["score"] < 100})[:120])

    # ---------- negative：严重度越高扣分越重（单调性） ----------
    pts = QS.SEVERITY_POINTS
    check("negative 扣分随严重度单调递增",
          pts["critical"] > pts["high"] > pts["medium"] > pts["low"], str(pts))
    r3 = F.write_project(os.path.join(tmp, "sev"))
    base = QS.compute(r3, findings=[])["overall"]
    one_med = QS.compute(r3, findings=[{"issue_type": "ORPHAN_FIGURE", "severity": "medium",
                                        "affected_nodes": ["FIG-001"], "detail": "x",
                                        "disposition": "queue", "status": "open"}])
    one_crit = QS.compute(r3, findings=[{"issue_type": "ORPHAN_FIGURE", "severity": "critical",
                                         "affected_nodes": ["FIG-001"], "detail": "x",
                                         "disposition": "block", "status": "open"}])
    check("negative medium 扣分低于 critical",
          base > one_med["overall"] > one_crit["overall"],
          f"{base} > {one_med['overall']} > {one_crit['overall']}")
    check("negative critical(block) 才置 blocked",
          one_crit["blocked"] is True and one_med["blocked"] is False)

    # ---------- boundary：人工判定类未裁决不判 blocked（按 §26 记 PASS_WITH_HUMAN_REVIEW） ----------
    r4 = F.write_project(os.path.join(tmp, "queue"), variant="conflict_pending")
    s4 = score_of(r4)
    highs = [d for d in open_findings(r4) if d["severity"] == "high"]
    check("boundary 高危人工项存在但不判 blocked",
          bool(highs) and s4["blocked"] is False, str([(d["issue_type"], d["disposition"]) for d in highs]))
    check("boundary 仍按扣分降低分值", s4["overall"] < 100, str(s4["overall"]))

    # ---------- boundary：Evidence 维度反映覆盖率 ----------
    r5 = F.write_project(os.path.join(tmp, "cov"))
    s5 = QS.compute(r5, findings=[], coverage={"evidence_coverage_ratio": 0.5, "uncovered": ["CL-003"]})
    s6 = QS.compute(r5, findings=[], coverage={"evidence_coverage_ratio": 1.0, "uncovered": []})
    check("boundary Evidence 分随覆盖率下降",
          s5["dimensions"]["Evidence"]["score"] < s6["dimensions"]["Evidence"]["score"],
          f"{s5['dimensions']['Evidence']['score']} vs {s6['dimensions']['Evidence']['score']}")
    check("boundary 覆盖率信息写入扣分依据",
          any("Coverage" in x for x in s5["dimensions"]["Evidence"]["deductions"]),
          str(s5["dimensions"]["Evidence"]["deductions"])[:120])

    # ---------- boundary：分值下限 0（大量问题不会为负） ----------
    many = [{"issue_type": "CLAIM_OVERSTRENGTH", "severity": "critical", "affected_nodes": [f"CL-00{i}"],
             "detail": "x", "disposition": "block", "status": "open"} for i in range(1, 10)]
    s7 = QS.compute(r5, findings=many)
    check("boundary 维度分不低于 0",
          all(v["score"] >= 0 for v in s7["dimensions"].values()),
          str({k: v["score"] for k, v in s7["dimensions"].items()})[:160])

    # ---------- repair：问题消除后分数回升且不再 blocked ----------
    r8 = F.write_project(os.path.join(tmp, "rep"), variant="claim_overstrength")
    before = score_of(r8)
    ids = __import__("research_repair").plan(r8, DIA.diagnose(r8)["diagnoses"])
    __import__("research_repair").execute(r8, ids=ids)
    after = score_of(r8)
    check("repair 修复前 blocked", before["blocked"] is True)
    check("repair 修复后分数回升", after["overall"] > before["overall"],
          f"{before['overall']} → {after['overall']}")
    check("repair 修复后恢复权威可读", after["blocked"] is False and after["authoritative"] is True)

    # ---------- boundary：CLI 产出评分报告 ----------
    out = os.path.join(tmp, "out")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "research_quality_score.py"), r5,
                        "--out", out], capture_output=True, text=True, encoding="utf-8", errors="replace")
    sp = os.path.join(out, "research-quality-score.md")
    txt = open(sp, encoding="utf-8").read() if os.path.isfile(sp) else (p.stdout or "")
    check("boundary CLI 报告含八维", all(d in txt for d in DIMS), txt[:120])
    check("boundary CLI rc=0（无阻断）", p.returncode == 0, f"rc={p.returncode}")
    import json as _json
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "research_diagnosis.py"), r2],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    pj = subprocess.run([sys.executable, os.path.join(SCRIPTS, "research_quality_score.py"), r2,
                         "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        js = _json.loads(pj.stdout)
    except Exception:
        js = {}
    check("boundary 评分 CLI 从诊断产物读到阻断", js.get("blocked") is True,
          str({"blocked": js.get("blocked"), "overall": js.get("overall")}) or (pj.stderr or "")[:100])

    print(f"test_quality_score 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
