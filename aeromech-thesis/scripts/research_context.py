# -*- coding: utf-8 -*-
"""research_context.py — Research Context 只读聚合视图（aeromech-thesis v1.6.0）

定位（指令 §十）：给 Orchestrator 提供统一的"研究上下文"读取入口——
Research Questions / Objectives / Methods / Evidence / Data / Analysis / Claims /
Conclusions / Scope / Assumptions / Limitations。
**本层不新造定义、不写注册表**：全部字段直接来自 v1.4/v1.5 注册表引擎
（research_integrity.load_registry / validate / coverage / build_traceability，只读复用）；
写入仍归 research_integrity.py 与各阶段工具。

状态模型（复用 v1.4.1 词表，不发明新状态）：
  OK（聚合成功）/ NOT_APPLICABLE（注册表未初始化=旧项目，各段为空）/ ERROR（注册表损坏，不静默当空）。

用法：
  python research_context.py <project_root> [--json] [--refresh-trace]
退出码：0=OK/NOT_APPLICABLE；3=ERROR（损坏/内部异常）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import yaml  # noqa: F401  （引擎依赖，保持导入一致性）
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

import research_integrity as RI

SECTIONS = ["research_questions", "objectives", "methods", "evidence", "data",
            "analysis", "claims", "conclusions", "scope", "assumptions", "limitations"]


def _items(root, reg):
    """单注册表读取：文件不存在→[]（不崩溃，缺段如实为空）。"""
    try:
        return RI.load_registry(root, reg) or []
    except RI.RegistryError:
        raise


def context(root):
    """返回聚合视图 dict（纯只读；不写任何文件）。"""
    try:
        initialized = RI.initialized(root)
        if not initialized:
            v = {"status": "NOT_APPLICABLE",
                 "reason": "Research Integrity 注册表未初始化（旧项目/新项目未建：各段为空，"
                           "由调度层决定在 S3 init，不伪造内容）",
                 "root": os.path.abspath(root)}
            for s in SECTIONS:
                v[s] = [] if s != "scope" else {}
            v["summary"] = {"initialized": False, "counts": {},
                            "evidence_coverage_ratio": None,
                            "validation_problems": [], "traceability": None,
                            "conflicts_open": [], "simulated_datasets": 0}
            return v
        data_all = {}
        for reg in RI.REGISTRY_SPECS:
            data_all[reg] = RI.load_registry(root, reg)   # 损坏→RegistryError→ERROR
        rqs = data_all.get("rq") or []
        scope_items = data_all.get("scope") or []
        design_items = data_all.get("design") or []
        datasets = data_all.get("datasets") or []
        conflicts = data_all.get("conflicts") or []
        cov = RI.coverage(root)
        val = RI.validate(root)
        trace = RI.build_traceability(root)
        limitations, assumptions = [], []
        for d in design_items:
            for x in d.get("limitations") or []:
                limitations.append({"source": d.get("id"), "text": x})
            for x in d.get("assumptions") or []:
                assumptions.append({"source": d.get("id"), "text": x})
        for sc in scope_items:
            for x in sc.get("assumptions") or []:
                assumptions.append({"source": sc.get("id"), "text": x})
        # 模拟数据局限也计入（identity 保持：limitations 字段非空才算披露）
        synth_lim = [{"source": ds.get("id"), "text": ds.get("limitations", "")}
                     for ds in datasets
                     if str(ds.get("type")) in ("simulated", "assumption") and ds.get("limitations")]
        limitations += [x for x in synth_lim if x not in limitations]
        return {
            "status": "OK",
            "root": os.path.abspath(root),
            "research_questions": [
                {"id": r.get("id"), "question": r.get("question"),
                 "objective": r.get("objective"),
                 "related_methods": r.get("related_methods") or [],
                 "related_chapters": r.get("related_chapters") or []} for r in rqs],
            "objectives": [r.get("objective") for r in rqs if r.get("objective")],
            "methods": [
                {"id": m.get("id"), "name": m.get("name"), "basis": m.get("basis"),
                 "provides": (m.get("capability") or m.get("provides") or []),
                 "related_rqs": m.get("related_rqs") or []}
                for m in (data_all.get("methods") or [])],
            "evidence": [
                {"id": e.get("id"), "source_type": e.get("source_type"),
                 "source": e.get("source"), "verification_status": e.get("verification_status"),
                 "claim_supported": e.get("claim_supported") or []}
                for e in (data_all.get("evidence") or [])],
            "data": [
                {"id": d.get("id"), "name": d.get("name"), "type": d.get("type"),
                 "label": d.get("label", ""), "source": d.get("source"),
                 "verification_status": d.get("verification_status")}
                for d in datasets],
            "analysis": [
                {"id": a.get("id"), "name": a.get("name"), "method": a.get("method"),
                 "inputs": a.get("inputs") or [], "outputs": a.get("outputs") or [],
                 "artifact": a.get("artifact", "")}
                for a in (data_all.get("analyses") or [])],
            "computations": [
                {"id": c.get("id"), "description": c.get("description"),
                 "output": c.get("output"), "verified": bool(c.get("verified"))}
                for c in (data_all.get("computations") or [])],
            "claims": [
                {"id": c.get("id"), "claim": c.get("claim"), "claim_type": c.get("claim_type"),
                 "evidence_ids": c.get("evidence_ids") or [],
                 "analysis_ids": c.get("analysis_ids") or [],
                 "status": c.get("status")}
                for c in (data_all.get("claims") or [])],
            "conclusions": [
                {"id": c.get("id"), "conclusion": c.get("conclusion"),
                 "claims": c.get("claims") or [], "analyses": c.get("analyses") or [],
                 "evidence": c.get("evidence") or []}
                for c in (data_all.get("conclusions") or [])],
            "scope": {
                "included": (scope_items[0].get("included") if scope_items else []),
                "excluded": (scope_items[0].get("excluded") if scope_items else []),
                "sources": [s.get("id") for s in scope_items]} if scope_items else {
                "included": [], "excluded": [], "sources": []},
            "design": [{"id": d.get("id"), "objectives": d.get("objectives") or [],
                        "constraints": d.get("constraints") or []} for d in design_items],
            "assumptions": assumptions,
            "limitations": limitations,
            "summary": {
                "initialized": True,
                "counts": {reg: len(items or []) for reg, items in data_all.items()},
                "evidence_coverage_ratio": cov["evidence_coverage_ratio"],
                "coverage": cov,
                "validation_problems": val["problems"],
                "traceability": {"nodes": len(trace["nodes"]), "edges": len(trace["edges"]),
                                 "orphans": trace["orphans"]},
                "conflicts_open": sorted(c.get("id") for c in conflicts
                                         if str(c.get("status")) == "pending"),
                "simulated_datasets": sorted(str(d.get("id")) for d in datasets
                                             if str(d.get("type")) in ("simulated", "assumption")),
            },
        }
    except RI.RegistryError as e:
        return {"status": "ERROR", "detail": str(e),
                "reason": "注册表损坏：不静默当空表（v1.4.1 错误模型）"}
    except Exception as e:  # 内部异常路径绝不产生 OK（delivery 同款纪律）
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}


def save_snapshot(root, out_path=None):
    """可选：把视图落盘为快照（artifacts/research-context.json），供跨会话对齐。
    注意这是"视图的缓存"，不是注册表的替代真源。"""
    ctx = context(root)
    out = out_path or os.path.join(root, ".aeromech", "artifacts", "research-context.json")
    if ctx["status"] == "ERROR":
        return ctx
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=1)
    ctx["_snapshot"] = out
    return ctx


def main(argv=None):
    ap = argparse.ArgumentParser(description="Research Context 聚合视图（v1.6，只读）")
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh-trace", action="store_true",
                    help="额外把 traceability.json 重生成到 research/（唯一允许写盘的动作，显式请求才做）")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    ctx = context(root)
    if ctx["status"] == "ERROR":
        print(json.dumps(ctx, ensure_ascii=False) if a.json else f"ERROR: {ctx['detail']}")
        return 3
    if a.refresh_trace:
        RI.save_traceability(root)
    if a.json:
        print(json.dumps(ctx, ensure_ascii=False, indent=1))
        return 0
    s = ctx["summary"]
    print(f"status={ctx['status']} initialized={s['initialized']} "
          f"coverage={s['evidence_coverage_ratio']} orphans={len(s['traceability']['orphans']) if s['traceability'] else '-'} "
          f"conflicts_open={s['conflicts_open']} simulated={s['simulated_datasets']}")
    print(f"RQ={len(ctx['research_questions'])} methods={len(ctx['methods'])} "
          f"evidence={len(ctx['evidence'])} data={len(ctx['data'])} claims={len(ctx['claims'])} "
          f"conclusions={len(ctx['conclusions'])} design={len(ctx.get('design', []))}")
    for r in ctx["research_questions"]:
        print(f"  {r['id']}: {r['question'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
