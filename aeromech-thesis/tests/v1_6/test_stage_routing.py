# -*- coding: utf-8 -*-
"""test_stage_routing.py — 阶段调度矩阵数据化 + 路由判定（v1.6 §十一/§十三/§二十一）

纪律：本层只判定不执行（不调脚本、不改状态）；门禁证据来自既有产物文件（不重新发明状态词表：
item 级用 v1.4.1 七态，gate 级用交付五态）；证据缺失 → SKIPPED_WITH_REASON（Orchestrator 先运行），
INFEASIBLE/BLOCK 证据 → 停留/回退建议。
运行：python tests/v1_6/test_stage_routing.py
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import stage_routing as SR
import thesis_state as TS
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("f15", os.path.join(HERE, "..", "v1_5", "_fixtures.py"))
F15 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(F15)

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def advance_to_s3(root, with_research=True):
    if with_research:
        filler = os.path.join(root, ".filler")
        F15.write_project(filler)
        shutil.copytree(os.path.join(filler, ".aeromech", "research"),
                        os.path.join(root, ".aeromech", "research"))
        shutil.rmtree(filler)
    st, _ = TS.load_state(root)
    st["project"].update(title="题目X", paper_type="research")
    st["stage"]["current"] = "S3"
    st["research"].update(topic_card_file="artifacts/topic-card.md",
                          plan_file="artifacts/research-plan.md",
                          outline_file="artifacts/thesis-outline.md")
    for name in ("topic-card", "research-plan", "thesis-outline"):
        F.write_text(root, f".aeromech/artifacts/{name}.md", "# x\n")
    TS.save_state(root, st)
    return root


def main():
    tmp = tempfile.mkdtemp(prefix="srouting_v16_")
    print("== test_stage_routing ==")

    # ---------- matrix 数据完整性 ----------
    M = SR.matrix()
    check("positive 矩阵覆盖 S1~S10", set(M.keys()) == {f"S{i}" for i in range(1, 11)}, str(sorted(M)))
    need_ai = {"S1": "feasibility", "S3": "feasibility", "S4": "coverage", "S5": "diagnosis",
               "S6": "data_integrity", "S7": "agent_loop", "S8": "figure_traceability",
               "S9": "full_qa"}
    for st, key in need_ai.items():
        ai = [x["id"] for x in M[st]["ai"]]
        check(f"positive 指令§十一挂载点 {st}⊃{key}", key in ai, str(ai))
    check("positive 迁移边+前置为数据（可枚举）",
          all("to" in t and "prereq" in t for s in M.values() for t in s["forward"]))
    check("positive 矩阵只读且稳定（两次返回相等）", SR.matrix() == SR.matrix())
    check("positive S2 不进 AI 挂载（指令表无 S2 行）", M["S2"]["ai"] == [])

    # ---------- 阶段完成判定 ----------
    root = advance_to_s3(F.make_project(os.path.join(tmp, "p1")))
    r0 = SR.route(F.make_project(os.path.join(tmp, "fresh")))
    check("positive 空项目→current=S1 且无完成阶段（不从零误判也不误启）",
          r0["current"] == "S1" and r0["stages_completed"] == [], str(r0["stages_completed"]))
    r1 = SR.route(root)
    check("positive S1~S3 完成被识别（证据齐）",
          {"S1", "S2", "S3"} <= set(r1["stages_completed"]), str(r1["stages_completed"]))
    check("positive 未执行证据=SKIPPED_WITH_REASON（非伪造/非猜测）",
          r1["gates"]["feasibility"]["status"] == "SKIPPED_WITH_REASON"
          and r1["gates"]["feasibility"]["reason"], str(r1["gates"]["feasibility"]))
    check("hard 出口产物齐但 AI 门禁证据未生成→run_pending（先运行再前进，不猜测）",
          r1["blocked"] is False and r1["next"]["action"] == "run_pending"
          and any("feasibility" in x for x in r1["next"]["run"]), str(r1["next"]))

    # ---------- §十三 Feasibility Gate：INFEASIBLE 必须停留 ----------
    analysis = os.path.join(root, ".aeromech", "artifacts", "analysis")
    write_json(os.path.join(analysis, "research-diagnosis.json"),
               {"feasibility": {"verdict": "INFEASIBLE", "reasons": ["RF-03"]},
                "diagnoses": []})
    r2 = SR.route(root)
    check("hard design 在场且 INFEASIBLE→blocked 停留（禁止进写作）",
          r2["blocked"] is True and r2["next"]["action"] == "stay", str(r2["next"]))
    check("positive 门禁状态映射 FEASIBLE×3态→PASS/WARN/FAIL（v1.4.1 词表）",
          r2["gates"]["feasibility"]["status"] == "FAIL")
    check("positive gate 证据可溯源（写明来源文件）",
          "research-diagnosis.json" in r2["gates"]["feasibility"].get("evidence", ""))
    write_json(os.path.join(analysis, "research-diagnosis.json"),
               {"feasibility": {"verdict": "CONDITIONALLY_FEASIBLE", "reasons": ["RF-04"]},
                "diagnoses": []})
    r3 = SR.route(root)
    check("boundary CONDITIONALLY_FEASIBLE→WARN 可前进（Orchestrator 负责挂 issue）",
          not r3["blocked"] and r3["gates"]["feasibility"]["status"] == "WARN")
    check("positive 证据齐后 S3→S4 advance",
          r3["next"]["action"] == "advance" and r3["next"]["to"] == "S4", str(r3["next"]))
    os.remove(os.path.join(analysis, "research-diagnosis.json"))

    # ---------- 旧项目无 design → NOT_APPLICABLE ----------
    legacy = F.make_project(os.path.join(tmp, "legacy"))
    rl = SR.route(legacy)
    check("positive 无 design 注册表→feasibility NOT_APPLICABLE（兼容）",
          rl["gates"]["feasibility"]["status"] == "NOT_APPLICABLE")

    # ---------- S7 门禁复用 Phase1 StateIO（不另造校验） ----------
    r6 = SR.route(root)
    check("positive s7 门禁用 state.md 三态词表",
          r6["gates"]["s7_evidence"]["status"] in ("passed", "conditional", "failed"),
          str(r6["gates"]["s7_evidence"]))
    check("positive 无 gate_evidence→failed（拒写，不猜测）",
          r6["gates"]["s7_evidence"]["status"] == "failed")
    TS.add_issue(root, severity="高", category="data", target_stage="S5", desc="缺实测数据")
    F.write_text(root, ".aeromech/artifacts/analysis/fmea-table.md", "# 表头骨架\n")
    st, _ = TS.load_state(root)
    open_ids = [i["id"] for i in st["stage"]["open_issues"] if i["status"] == "open"]
    st["writing"]["gate_evidence"] = {
        "plan_file": "artifacts/research-plan.md",
        "evidence_type": "data_or_analysis",
        "evidence_files": ["artifacts/analysis/fmea-table.md"],
        "gate_passed": "conditional", "open_issues": open_ids}
    TS.save_state(root, st)
    r7 = SR.route(root)
    check("boundary conditional（降级+open_issue）=合法 CONDITIONAL 态",
          r7["gates"]["s7_evidence"]["status"] == "conditional")

    # ---------- S9 loop BLOCK → 回退建议 ----------
    write_json(os.path.join(analysis, "research-diagnosis.json"),
               {"feasibility": {"verdict": "FEASIBLE", "reasons": []}, "diagnoses": []})
    st, _ = TS.load_state(root)
    st["stage"]["current"] = "S9"
    st["writing"]["status"] = "draft_done"
    TS.save_state(root, st)
    write_json(os.path.join(analysis, "research-loop-log.json"),
               {"status": "BLOCK", "iterations": [], "open_findings": [
                   {"id": "DIAG-1", "issue_type": "CONCLUSION_OVERREACH",
                    "severity": "critical", "human": False, "detail": "…"}]})
    write_json(os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality.json"),
               {"gate": "FAIL"})
    r8 = SR.route(root)
    check("hard loop BLOCK→S9 阻塞 + revert 建议（issue→目标阶段映射）",
          r8["blocked"] and r8["next"]["action"] == "revert" and r8["next"]["to"] == "S7",
          str(r8["next"]))
    check("positive BLOCK 原因引用 loop 终态", "BLOCK" in str(r8["block_reason"]))
    write_json(os.path.join(analysis, "research-loop-log.json"),
               {"status": "PASS_WITH_HUMAN_REVIEW", "iterations": [], "open_findings": [
                   {"id": "DIAG-2", "issue_type": "UNRESOLVED_CONFLICT",
                    "severity": "high", "human": True, "detail": "…"}]})
    write_json(os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality.json"),
               {"gate": "PASS"})
    r9 = SR.route(root)
    check("positive loop PHR→门禁 NEEDS_HUMAN_REVIEW（流程可续，交付前须裁决）",
          r9["gates"]["agent_loop"]["status"] == "NEEDS_HUMAN_REVIEW")
    # 高严重 open issue（conditional 遗留）未关 → 交付级仍 BLOCK（High 禁正式终稿）
    dg_phr0 = SR.delivery_gate_status(root)
    check("hard conditional 的高严重 open_issue 未关→gate BLOCK",
          dg_phr0["status"] == "BLOCK" and any("open_issue" in x for x in dg_phr0["reasons"]),
          str(dg_phr0)[:160])
    st, _ = TS.load_state(root)
    for i in st["stage"]["open_issues"]:
        i["status"] = "closed"
    TS.save_state(root, st)
    check("positive 交付门禁五态：PHR→PASS_WITH_HUMAN_REVIEW",
          SR.delivery_gate_status(root)["status"] == "PASS_WITH_HUMAN_REVIEW",
          str(SR.delivery_gate_status(root)))

    # ---------- 交付门禁聚合（五态，gate 级） ----------
    os.remove(os.path.join(analysis, "research-loop-log.json"))
    dg0 = SR.delivery_gate_status(root)
    check("hard QA 证据缺失→BLOCK（缺项=不得交付，非通过）",
          dg0["status"] == "BLOCK" and dg0["missing"], str(dg0)[:150])
    write_json(os.path.join(analysis, "research-loop-log.json"),
               {"status": "PASS", "iterations": [], "open_findings": []})
    TS.add_issue(root, severity="高", category="data", target_stage="S6", desc="新缺口")
    dg1 = SR.delivery_gate_status(root)
    check("positive RQG PASS+loop PASS 但 open issue 高未关→BLOCK（引用 open_issue）",
          dg1["status"] == "BLOCK" and any("open_issue" in r for r in dg1["reasons"]), str(dg1))
    st, _ = TS.load_state(root)
    for i in st["stage"]["open_issues"]:
        i["status"] = "closed"
    TS.save_state(root, st)
    dg2 = SR.delivery_gate_status(root)
    check("positive 证据齐且 PASS 且无未关问题→PASS",
          dg2["status"] == "PASS", str(dg2))
    write_json(os.path.join(analysis, "research-loop-log.json"),
               {"status": "PASS_WITH_WARNINGS", "iterations": [], "open_findings": []})
    check("boundary loop PASS_WITH_WARNINGS→PASS_WITH_WARNINGS（披露放行）",
          SR.delivery_gate_status(root)["status"] == "PASS_WITH_WARNINGS")
    write_json(os.path.join(analysis, "research-loop-log.json"),
               {"status": "ERROR", "iterations": [], "open_findings": []})
    check("negative loop ERROR→gate ERROR（绝不 PASS）",
          SR.delivery_gate_status(root)["status"] == "ERROR")
    write_json(os.path.join(analysis, "research-loop-log.json"),
               {"status": "WARN", "iterations": [], "open_findings": []})
    check("boundary loop WARN（medium 未解决）→PASS_WITH_WARNINGS",
          SR.delivery_gate_status(root)["status"] == "PASS_WITH_WARNINGS")

    # ---------- 回退目标映射（state.md §8 + v1.5 issue_type） ----------
    for cat, tgt in (("citation", "S4"), ("engineering", "S5"), ("data", "S6"),
                     ("structure", "S3"), ("writing", "S7"), ("figure", "S7")):
        check(f"positive 类别映射 {cat}→{tgt}", SR.CATEGORY_TARGET[cat] == tgt)
    for it, tgt in (("FEASIBILITY_BLOCK", "S3"), ("RQ_METHOD_MISMATCH", "S3"),
                    ("UNRESOLVED_CONFLICT", "S4"), ("DATA_GAP", "S6"),
                    ("CONCLUSION_OVERREACH", "S7"), ("CLAIM_OVERSTRENGTH", "S7"),
                    ("ORPHAN_FIGURE", "S8"), ("QUANTITATIVE_INCONSISTENCY", "S7")):
        check(f"positive issue_type 映射 {it}→{tgt}", SR.ISSUE_TYPE_TARGET[it] == tgt)
    check("positive 未知 issue_type 回落类别映射不崩溃",
          SR.issue_target("SOMETHING_NEW") in SR.STAGES or SR.issue_target("SOMETHING_NEW") is None)

    # ---------- route 不执行不改状态（只判定纪律） ----------
    before = json.dumps(TS.load_state(root)[0], ensure_ascii=False, sort_keys=True, default=str)
    SR.route(root)
    SR.delivery_gate_status(root)
    after = json.dumps(TS.load_state(root)[0], ensure_ascii=False, sort_keys=True, default=str)
    check("hard 路由层只判定：state 未被改写、不写 checkpoint", before == after)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_stage_routing 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
