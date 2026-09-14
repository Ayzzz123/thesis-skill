# -*- coding: utf-8 -*-
"""research_quality_score.py — Research Quality Score（aeromech-thesis v1.5.0）

8 维评分（各 0–100）+ Overall；**总分不得覆盖 Critical/High 未解决问题**（blocked=True 时总分仅为展示值）。
维度：Research Design / Evidence / Data / Analysis / Argumentation / Conclusion / Citation / Coherence

用法：
  python research_quality_score.py <project_root> [--findings-json <path>] [--json] [--out <dir>]
退出码：0=无阻断；1=存在未解决 Critical/High（BLOCK）；2=注册表未初始化；3=ERROR
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_integrity as RI

SEVERITY_POINTS = {"critical": 60, "high": 30, "medium": 10, "low": 3}

DIMENSIONS = ["Research Design", "Evidence", "Data", "Analysis",
              "Argumentation", "Conclusion", "Citation", "Coherence"]

# issue_type → 归属维度（v1.5 §8 全部类型；新增类型必须同步登记，未知类型走兜底不静默丢弃）
ISSUE_DIMENSION = {
    "RQ_METHOD_MISMATCH": "Research Design",
    "DESIGN_EVIDENCE_MISMATCH": "Research Design",
    "METHOD_SELECTION_WEAK": "Research Design",
    "SCOPE_OVERFLOW": "Research Design",
    "SCOPE_UNDERFLOW": "Research Design",
    "FEASIBILITY_BLOCK": "Research Design",
    "EVIDENCE_GAP": "Evidence",
    "UNRESOLVED_CONFLICT": "Evidence",
    "DATA_GAP": "Data",
    "CALCULATION_GAP": "Analysis",
    "DUPLICATE_ANALYSIS": "Analysis",
    "CLAIM_OVERSTRENGTH": "Argumentation",
    "TRACEABILITY_GAP": "Argumentation",
    "CITATION_GAP": "Citation",
    "CONCLUSION_OVERREACH": "Conclusion",
    "ABSTRACT_MISMATCH": "Conclusion",
    "QUANTITATIVE_INCONSISTENCY": "Conclusion",
    "REDUNDANT_CONTENT": "Coherence",
    "ORPHAN_FIGURE": "Coherence",
    "ORPHAN_TABLE": "Coherence",
}


def compute(root, findings=None, coverage=None):
    """findings = 未解决的诊断条目（含 severity/issue_type）。返回评分结构。"""
    if findings is None:
        findings = _load_findings(root)
    dims = {d: {"score": 100, "deductions": []} for d in DIMENSIONS}
    blocks = []
    for f in findings:
        it = str(f.get("issue_type", ""))
        dim = ISSUE_DIMENSION.get(it)
        if not dim:
            # 兜底（B2 机制修复）：未映射类型不得静默丢失——计入 Coherence 并标注 UNMAPPED，
            # 使"诊断发现问题但评分不认识"在结构上不可能发生；同时暴露给映射表维护者。
            dim = "Coherence"
        sev = str(f.get("severity", "medium")).lower()
        pts = SEVERITY_POINTS.get(sev, 5)
        dims[dim]["score"] = max(0, dims[dim]["score"] - pts)
        tag = it if it in ISSUE_DIMENSION else f"{it}(UNMAPPED)"
        dims[dim]["deductions"].append(f"{tag}({sev}): {str(f.get('detail', ''))[:48]} (−{pts})")
        if sev in ("critical", "high") and str(f.get("disposition", "block")) != "queue":
            blocks.append(f"{it}[{sev}] {str(f.get('detail', ''))[:60]}")

    # Evidence 维度附加按覆盖率折算（无 finding 也可能低覆盖）
    if coverage is None:
        try:
            coverage = RI.coverage(root)
        except Exception:
            coverage = None
    if coverage:
        cov = float(coverage.get("evidence_coverage_ratio", 1.0))
        if cov < 1.0:
            pts = int(round((1.0 - cov) * 40))
            dims["Evidence"]["score"] = max(0, dims["Evidence"]["score"] - pts)
            dims["Evidence"]["deductions"].append(
                f"Evidence Coverage={cov}（未覆盖 {coverage.get('uncovered')}） (−{pts})")

    overall = round(sum(d["score"] for d in dims.values()) / len(DIMENSIONS))
    return {"dimensions": dims, "overall": overall,
            "blocked": bool(blocks), "block_reasons": blocks,
            "authoritative": not blocks}


def _load_findings(root):
    """读取最近一次诊断 JSON（未解决项）；缺失则返回空（评分基于现状）。"""
    p = os.path.join(root, ".aeromech", "artifacts", "analysis", "research-diagnosis.json")
    if not os.path.isfile(p):
        return []
    try:
        j = json.load(open(p, encoding="utf-8"))
    except Exception:
        return []
    return [d for d in (j.get("diagnoses") or []) if d.get("status", "open") == "open"]


def render(score):
    lines = ["# Research Quality Score（v1.5）", ""]
    for d in DIMENSIONS:
        lines.append(f"- {d}: {score['dimensions'][d]['score']}")
        for x in score["dimensions"][d]["deductions"]:
            lines.append(f"    - {x}")
    lines.append("")
    lines.append(f"**Overall Research Quality Score: {score['overall']}**"
                 + ("（存在未解决 Critical/High：总分不构成交付依据）" if score["blocked"] else ""))
    for r in score["block_reasons"]:
        lines.append(f"- BLOCK: {r}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Research Quality Score（v1.5）")
    ap.add_argument("project_root")
    ap.add_argument("--findings-json", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = args.project_root
    if not RI.initialized(root):
        print("注册表未初始化：.aeromech/research/ 不存在")
        return 2
    try:
        findings = None
        if args.findings_json:
            j = json.load(open(args.findings_json, encoding="utf-8"))
            findings = [d for d in (j.get("diagnoses") or []) if d.get("status", "open") == "open"]
        score = compute(root, findings=findings)
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            open(os.path.join(args.out, "research-quality-score.md"), "w", encoding="utf-8") \
                .write(render(score))
            json.dump(score, open(os.path.join(args.out, "research-quality-score.json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=1)
        if args.json:
            print(json.dumps(score, ensure_ascii=False, indent=1))
        else:
            print(render(score))
        return 1 if score["blocked"] else 0
    except RI.RegistryError as e:
        print(f"ERROR: 注册表损坏 {e.path}: {e.detail}")
        return 3
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"QUALITY SCORE ERROR: {type(e).__name__}: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
