# -*- coding: utf-8 -*-
"""research_agent_loop.py — Research Agent Loop（aeromech-thesis v1.5.0）

PLAN → ANALYZE → DETECT → DIAGNOSE → REPAIR → RE-ANALYZE → VALIDATE → ACCEPT
（≤ MAX_ITERATIONS=5；无改善即停；白名单自动修复；其余进人工队列；Critical/High 未解决 → BLOCK）

用法：
  python research_agent_loop.py <project_root> [--max-iterations 5] [--no-auto-repair]
                                [--out <dir>] [--json]
退出码：0=ACCEPTED（PASS / PASS_WITH_WARNINGS / WARN / PASS_WITH_HUMAN_REVIEW）；1=BLOCK；2=未初始化；3=ERROR
"""
import argparse
import contextlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_integrity as RI
import research_diagnosis as DIA
import research_repair as REP
import research_quality_score as QS
import yaml

MAX_ITERATIONS = 5
AUTO_OPS = set(REP.AUTO_OPERATIONS)
SEV_HARD = ("critical", "high")


def _queue_path(root):
    return os.path.join(root, ".aeromech", "research", "human-review-queue.yaml")


def _load_old_queue(root):
    p = _queue_path(root)
    if not os.path.isfile(p):
        return {}
    try:
        q = yaml.safe_load(open(p, encoding="utf-8")) or {}
        return {str(e.get("diagnosis_id")): e for e in (q.get("queue") or [])}
    except Exception:
        return {}


def _build_queue(root, diag, rqg_nhr):
    """生成/更新人工复核队列（保留既有决策字段）。"""
    old = _load_old_queue(root)
    queue = []
    for d in diag["diagnoses"]:
        if d["status"] != "open":
            # B10：已裁决关闭的条目（rejected/deferred/closed）必须保留在队列中——
            # diagnose 依据队列里的 applied_status 维持关闭状态；重建时丢弃会使裁决
            # 记录消失，被驳回/延期的诊断在下一轮复活（决策必须持久）。
            prev_closed = old.get(d["diagnosis_id"])
            if d["status"] in ("rejected_by_human", "deferred_by_human") and prev_closed:
                queue.append(dict(prev_closed))
            continue
        if not d["human_review_required"]:
            continue
        opts = d.get("repair_options") or []
        first = opts[0] if opts else {"id": "", "repair_type": "REQUEST_HUMAN_REVIEW", "action": ""}
        prev = old.get(d["diagnosis_id"], {})
        rpayload = (d.get("recommended_repair") or {}).get("payload") or {}
        queue.append({
            "diagnosis_id": d["diagnosis_id"],
            "issue_type": d["issue_type"],
            "severity": d["severity"],
            "detail": d["detail"],
            "target_nodes": d["affected_nodes"],
            "root_cause": d["root_cause"],
            "evidence": d["evidence"],
            "options": opts,
            "option": prev.get("option", first.get("id", "")),
            "repair_type": prev.get("repair_type", first.get("repair_type", "")),
            "action": prev.get("action", first.get("action", "")),
            "before_text": rpayload.get("old") or rpayload.get("old_text") or prev.get("before_text", ""),
            "repair_payload": rpayload,
            "required_input": prev.get("required_input",
                                       "decision(approve|reject|modify) + payload.replacement（如需改文）"),
            "decision": prev.get("decision"),
            "payload": prev.get("payload") or {},
            "reviewer": prev.get("reviewer", ""),
            "date": prev.get("date", ""),
            "note": prev.get("note", ""),
            "applied_status": prev.get("applied_status"),
        })
    data = {"queue": queue,
            "rqg_needs_human_review": rqg_nhr,
            "note": "NHR/人工项必须由人类复核者填写 decision 后重跑 loop；rqg_needs_human_review 项通过 "
                    "research/human-review.yaml 裁决（v1.4.1 机制）。"}
    with open(_queue_path(root), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return data


def _sig(diag):
    return tuple(sorted((d["issue_type"], ",".join(d["affected_nodes"]), d["severity"])
                        for d in diag["diagnoses"] if d["status"] == "open"))


def _iter_snapshot(diag):
    open_items = [d for d in diag["diagnoses"] if d["status"] == "open"]
    return {
        "counts": {"total": len(open_items),
                   "critical": sum(1 for d in open_items if d["severity"] == "critical"),
                   "high": sum(1 for d in open_items if d["severity"] == "high"),
                   "medium": sum(1 for d in open_items if d["severity"] == "medium"),
                   "low": sum(1 for d in open_items if d["severity"] == "low"),
                   "auto": sum(1 for d in open_items if d["auto_repairable"]),
                   "human": sum(1 for d in open_items if d["human_review_required"])},
        "ids": [d["diagnosis_id"] for d in open_items],
        "types": [d["issue_type"] for d in open_items],
    }


def run_loop(root, max_iterations=MAX_ITERATIONS, auto_repair=True, out_dir=None):
    if not RI.initialized(root):
        return {"status": "not_initialized", "reason": "Research Integrity 注册表未初始化（旧项目兼容，不阻塞）",
                "iterations": []}
    out_dir = out_dir or os.path.join(root, ".aeromech", "artifacts", "analysis")
    iterations = []
    prev_sig = None
    stopped_reason = "max_iterations"
    for i in range(1, max_iterations + 1):
        diag = DIA.diagnose(root)
        before = _iter_snapshot(diag)
        # PLAN：为可自动修复项建立 REP
        created, done, failed = [], [], []
        auto_open = [d for d in diag["diagnoses"]
                     if d["status"] == "open" and d["auto_repairable"]
                     and str((d.get("recommended_repair") or {}).get("operation")) in AUTO_OPS]
        if auto_repair and auto_open:
            created = REP.plan(root, diag["diagnoses"])
            if created:
                done, failed = REP.execute(root, ids=created)
        # 人工队列（含既有裁决的执行）
        qdata = _build_queue(root, diag, diag.get("rqg_needs_human_review") or [])
        human_res = REP.apply_human(root) if any(e.get("decision") for e in qdata["queue"]) else \
            {"applied": [], "rejected": [], "deferred": [], "needs_input": []}
        # RE-ANALYZE
        diag_after = DIA.diagnose(root) if (done or failed or human_res["applied"]) else diag
        after = _iter_snapshot(diag_after)
        it = {
            "iteration_id": i,
            "issues_before": before,
            "repairs": [{"id": rid, "result": msg} for rid, msg in done] +
                       [{"id": rid, "result": "FAILED: " + msg} for rid, msg in failed] +
                       [{"human": x} for x in human_res["applied"]] +
                       [{"human_reject": x} for x in human_res["rejected"]] +
                       [{"human_defer": x} for x in human_res["deferred"]],
            "issues_after": after,
            "improvement": before["counts"]["total"] - after["counts"]["total"],
            "remaining_issues": after["ids"],
            "why": {
                "detected_by": sorted(set(before["types"])),
                "severity_basis": "按 references/research-intelligence.md §6（issue_type→severity→priority_class）",
                "repair_choice": "白名单自动修复（降级/数字同步/重算/标签）+ 人工队列（设计/证据/范围/冲突类）",
                "auto_allowed": f"仅 AUTO_OPERATIONS={sorted(AUTO_OPS)} 且类型在自动白名单内",
                "human_required": [d["diagnosis_id"] + ":" + d["issue_type"]
                                   for d in diag["diagnoses"] if d["human_review_required"]
                                   and d["status"] == "open"],
            },
        }
        iterations.append(it)
        sig = _sig(diag_after)
        if sig == prev_sig:
            open_after = [d for d in diag_after["diagnoses"] if d["status"] == "open"]
            if not open_after:
                stopped_reason = "clean"
            elif all(d["human_review_required"] for d in open_after):
                stopped_reason = "pending_human_review"
            else:
                stopped_reason = "no_improvement"
            break
        prev_sig = sig
        if not auto_open and not human_res["applied"]:
            stopped_reason = "no_actionable_items"
            break

    # ---- VALIDATE / ACCEPT ----
    final_diag = DIA.diagnose(root)
    open_items = [d for d in final_diag["diagnoses"] if d["status"] == "open"]
    deferred = [d for d in final_diag["diagnoses"] if d["status"] == "deferred_by_human"]
    # BLOCK：disposition=block 的 critical/high 未解决项（Integrity Failure；自动修复失败也归此类）
    hard = [d for d in open_items
            if d["severity"] in SEV_HARD and d.get("disposition") != "queue"]
    # NHR：judgment 类未裁决项 + 人工承诺后续处理项
    nhr_open = [d for d in open_items if d.get("disposition") == "queue"] + deferred
    medium = [d for d in open_items if d["severity"] == "medium" and d not in hard]
    low = [d for d in open_items if d["severity"] == "low" and d not in hard]
    rqg_gate = final_diag.get("rqg_gate")
    rqg_nhr = final_diag.get("rqg_needs_human_review") or []
    if hard:
        status = "BLOCK"
    elif nhr_open or rqg_nhr:
        status = "PASS_WITH_HUMAN_REVIEW"
    elif medium:
        status = "WARN"
    elif low:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    score = QS.compute(root, findings=open_items)
    result = {
        "status": status,
        "loop_status": {"PASS": "ACCEPTED", "PASS_WITH_WARNINGS": "ACCEPTED",
                        "WARN": "ACCEPTED_WITH_WARNINGS",
                        "PASS_WITH_HUMAN_REVIEW": "ACCEPTED_PENDING_HUMAN_REVIEW",
                        "BLOCK": "BLOCKED"}[status],
        "stopped_reason": stopped_reason,
        "iterations": iterations,
        "open_findings": [{"id": d["diagnosis_id"], "issue_type": d["issue_type"],
                           "severity": d["severity"], "human": d["human_review_required"],
                           "detail": d["detail"][:80]} for d in open_items],
        "rqg_gate": rqg_gate,
        "rqg_needs_human_review": rqg_nhr,
        "score": score,
        "block_reasons": [f"{d['diagnosis_id']} {d['issue_type']}: {d['detail'][:80]}" for d in hard],
    }
    _write_log(root, out_dir, result)
    return result


def _write_log(root, out_dir, result):
    os.makedirs(out_dir, exist_ok=True)
    lines = ["# Research Agent Loop 日志（v1.5）", "",
             f"- 终态: **{result['status']}**（{result['loop_status']}）；停止原因: {result['stopped_reason']}",
             f"- RQG Gate: {result.get('rqg_gate')}；Overall Score: {result['score']['overall']}"
             + ("（存在未解决 Critical/High：总分不构成交付依据）" if result["score"]["blocked"] else ""),
             f"- 待人工复核（RQG NHR）: {result.get('rqg_needs_human_review') or '无'}", ""]
    lines.append("> 本日志仅记录：事实依据 / 规则命中 / 诊断结果 / 修复动作 / 验证结果（不含内部推理链）。")
    lines.append("")
    for it in result["iterations"]:
        lines.append(f"## 第 {it['iteration_id']} 轮")
        lines.append(f"- issues_before: {it['issues_before']['counts']} ids={it['issues_before']['ids']}")
        lines.append(f"- 规则命中（issue_type）: {it['why']['detected_by']}")
        lines.append(f"- 严重度依据: {it['why']['severity_basis']}")
        lines.append(f"- 修复动作: {it['repairs'] or '无'}")
        lines.append(f"- 自动修复依据: {it['why']['auto_allowed']}")
        lines.append(f"- 需人工项: {it['why']['human_required'] or '无'}")
        lines.append(f"- issues_after: {it['issues_after']['counts']} improvement={it['improvement']}")
        lines.append(f"- remaining_issues: {it['remaining_issues']}")
        lines.append("")
    lines.append("## 最终状态")
    for f in result["open_findings"]:
        lines.append(f"- [open] {f['id']} {f['issue_type']} [{f['severity']}] {'人工' if f['human'] else '自动'} | {f['detail']}")
    for r in result["block_reasons"]:
        lines.append(f"- BLOCK: {r}")
    if result["status"] == "PASS_WITH_HUMAN_REVIEW":
        lines.append("- 交付前必须完成人工复核（human-review-queue.yaml / human-review.yaml）并重跑 loop。")
    open(os.path.join(out_dir, "research-loop-log.md"), "w", encoding="utf-8").write("\n".join(lines))
    json.dump(result, open(os.path.join(out_dir, "research-loop-log.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description="Research Agent Loop（v1.5）")
    ap.add_argument("project_root")
    ap.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    ap.add_argument("--no-auto-repair", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = args.project_root
    try:
        res = run_loop(root, max_iterations=max(1, min(args.max_iterations, 20)),
                       auto_repair=not args.no_auto_repair, out_dir=args.out)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"loop 终态: {res['status']}（{res.get('loop_status')}）停止原因: {res.get('stopped_reason')}")
            for it in res.get("iterations", []):
                print(f"  轮{it['iteration_id']}: before={it['issues_before']['counts']['total']} "
                      f"repairs={len(it['repairs'])} after={it['issues_after']['counts']['total']}")
            for f in res.get("open_findings", []):
                print(f"  [open] {f['id']} {f['issue_type']} [{f['severity']}] {'人工' if f['human'] else '自动'}")
            print(f"score: {res.get('score', {}).get('overall')}（blocked={res.get('score', {}).get('blocked')}）")
        if res["status"] == "not_initialized":
            return 2
        return 1 if res["status"] == "BLOCK" else 0
    except RI.RegistryError as e:
        print(f"ERROR: 注册表损坏 {e.path}: {e.detail}")
        return 3
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"AGENT LOOP ERROR: {type(e).__name__}: {e}（未产生 PASS 结论）")
        return 3


if __name__ == "__main__":
    sys.exit(main())
