# -*- coding: utf-8 -*-
"""test_agent_loop_integration.py — Orchestrator × 现有 Agent Loop 集成（指令 §十/§十一；ORCH-12/14/15）

验证三个完整场景（调用既有 research_agent_loop，不重写 loop）：
  1 Auto Repair：DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→PASS
  2 Human Review：DETECT→NHR→人工裁决→RE-ANALYZE→PASS_WITH_HUMAN_REVIEW→apply-human→继续
  3 Critical：DETECT→BLOCK（编排层不掩盖）
外加：轮次上限保护、loop 日志逐轮字段、BLOCK→回退→重入→通过 的恢复闭环。
运行：python tests/v1_6/test_agent_loop_integration.py
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
import thesis_state as TS
import thesis_orchestrator as ORCH
import research_integrity as RI
import research_agent_loop as AL
import research_repair as RRP
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


def bring(root, stage="S7", variant=None):
    """完整自洽的 v1.5 夹具项目（不裁剪注册表：裁剪会制造悬空引用→RQG BLOCK，属夹具失真）。"""
    F.make_project(root)
    filler = os.path.join(root, ".filler")
    F15.write_project(filler, variant=variant)
    shutil.copytree(os.path.join(filler, ".aeromech", "research"),
                    os.path.join(root, ".aeromech", "research"))
    shutil.copytree(os.path.join(filler, ".aeromech", "artifacts", "chapters"),
                    os.path.join(root, ".aeromech", "artifacts", "chapters"), dirs_exist_ok=True)
    shutil.rmtree(filler)
    st, _ = TS.load_state(root)
    st["project"].update(title="loop集成题", paper_type="research")
    st["stage"]["current"] = stage
    st["writing"]["status"] = "draft_done"
    st["research"].update(topic_card_file="artifacts/topic-card.md",
                          plan_file="artifacts/research-plan.md",
                          outline_file="artifacts/thesis-outline.md",
                          literature_status="reviewed")
    for n in ("topic-card", "research-plan", "thesis-outline"):
        F.write_text(root, f".aeromech/artifacts/{n}.md", "# x\n")
    TS.save_state(root, st)
    return root


def main():
    tmp = tempfile.mkdtemp(prefix="loopint_v16_")
    print("== test_agent_loop_integration ==")

    # ---------- 场景 1：Auto Repair → PASS（DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→PASS） ----------
    root = bring(os.path.join(tmp, "auto"), "S7", variant="claim_overstrength")
    ch3 = os.path.join(root, ".aeromech", "artifacts", "chapters", "ch3-fault-modes.md")
    before = open(ch3, encoding="utf-8").read()
    rc, res = ORCH.step(root)              # S7 证据缺 → run_pending 触发 loop
    check("ORCH-15 S7 自动修复场景→step 执行 agent_loop",
          rc == 0 and res["action"] == "RUN_PENDING"
          and res["detail"]["done"] == ["agent_loop"], str(res)[:150])
    check("ORCH-15 loop 完成（既有工具返回终态）",
          res["detail"]["result"].get("status") in
          ("PASS", "PASS_WITH_WARNINGS", "WARN", "PASS_WITH_HUMAN_REVIEW"),
          str(res["detail"]["result"].get("status")))
    after = open(ch3, encoding="utf-8").read()
    check("Auto Repair 真实改文（白名单降级，非模拟）", after != before)
    reps = RI.load_registry(root, "repairs") or []
    check("修复全留痕（REP verified + before/after）",
          any(x.get("status") == "verified" and "before" in x and "after" in x for x in reps),
          str([x.get("status") for x in reps]))
    lp = os.path.join(root, ".aeromech", "artifacts", "analysis", "research-loop-log.json")
    lg = json.load(open(lp, encoding="utf-8"))
    check("loop 逐轮记录齐备（issues_before/repairs/issues_after/improvement）",
          lg["iterations"] and all({"issues_before", "repairs", "issues_after",
                                    "improvement"} <= set(it) for it in lg["iterations"]))
    check("RUN_PENDING 后 checkpoint 建立（task=ai）",
          any("ai:agent_loop" in (c.get("task") or "") for c in TS.load_checkpoints(root)))
    # 恢复流程：loop PASS 后 route 不再 blocked
    r2 = AL.run_loop(root)
    check("复检：已修复项目 loop 终态非 BLOCK", r2["status"] != "BLOCK", r2["status"])

    # ---------- 场景 2：Human Review → 队列 → 裁决 → 继续 ----------
    root2 = bring(os.path.join(tmp, "human"), "S7", variant="conflict_pending")
    rc2, res2 = ORCH.step(root2)
    loop_status = res2["detail"]["result"].get("status")
    check("NHR 场景 loop 终态为 PASS_WITH_HUMAN_REVIEW/WARN",
          loop_status in ("PASS_WITH_HUMAN_REVIEW", "WARN"), str(loop_status))
    qp = os.path.join(root2, ".aeromech", "research", "human-review-queue.yaml")
    check("复用 v1.4.1/v1.5 队列机制（loop 生成，非新建第二套）", os.path.isfile(qp))
    import yaml
    q = yaml.safe_load(open(qp, encoding="utf-8")) or {}
    pend = [x for x in q.get("queue") or [] if not x.get("decision")]
    check("未裁决项存在时编排不代签", len(pend) >= 1)
    # 人类裁决（测试模拟外部复核者写入）→ apply-human 消费 → 复检
    for item in q.get("queue") or []:
        if not item.get("decision"):
            item["decision"] = "reject"
            item["reviewer"] = "外部复核者"
            item["note"] = "reject（人工判定非缺陷）"
    yaml.safe_dump({"queue": q["queue"]}, open(qp, "w", encoding="utf-8"), allow_unicode=True)
    rc3, res3 = ORCH.apply_human(root2)
    check("apply-human 复用 research_repair（rc0/APPLIED）",
          rc3 == 0 and res3["status"] == "APPLIED", str(res3)[:120])
    r4 = AL.run_loop(root2)
    q4 = yaml.safe_load(open(qp, encoding="utf-8")) or {}
    conflict = [x for x in q4.get("queue") or [] if x.get("issue_type") == "UNRESOLVED_CONFLICT"]
    check("裁决被消费：冲突条目 applied_status 写回（rejected_by_human，不静默丢弃）",
          conflict and all(x.get("applied_status") for x in conflict), str(conflict)[:120])
    check("裁决后复跑：loop 不再 BLOCK（流程可续；RQG 语义 NHR 属另一合法队列）",
          r4["status"] != "BLOCK", r4["status"])
    check("裁决持久保留（rejected 条目复活=违规）",
          all(not (x.get("applied_status") == "rejected_by_human" and x.get("decision") is None)
              for x in ((yaml.safe_load(open(qp, encoding="utf-8")) or {}).get("queue") or [])))

    # ---------- 场景 3：Critical → BLOCK（编排不掩盖） ----------
    root3 = bring(os.path.join(tmp, "crit"), "S7")
    ev = RI.load_registry(root3, "evidence")
    ev[0]["source_type"] = "simulation"
    ev[0]["verification_status"] = "verified"
    RI.save_registry(root3, "evidence", ev)
    rc4, res4 = ORCH.step(root3)           # loop→BLOCK
    check("Critical 场景 step 后 route 不 blocked（loop 证据未先行为 BLOCK 证据）",
          res4["action"] in ("RUN_PENDING", "BLOCK", "RETRY_EXHAUSTED"), str(res4)[:140])
    rc5, res5 = ORCH.step(root3)           # 第二次 step：route blocked → recovery
    st3, _ = TS.load_state(root3)
    gate = AL.run_loop(root3)["status"]
    check("loop 终态 BLOCK 的 Critical 项目：gate 不产 PASS",
          gate == "BLOCK" and ORCH.SR.delivery_gate_status(root3)["status"] in ("BLOCK", "ERROR"),
          str(gate))
    check("BLOCK 项目 step 给出恢复动作（block/rollback，不静默）",
          res5["action"] in ("BLOCK", "ROLLBACK", "HUMAN_REVIEW"), str(res5)[:140])

    # ---------- ORCH-14：轮数上限 + drive 步数上限 ----------
    root4 = bring(os.path.join(tmp, "maxit"), "S9", variant="conclusion_overreach")
    lr = AL.run_loop(root4, max_iterations=2)
    check("ORCH-14 loop 轮数不超上限（<=2）", len(lr["iterations"]) <= 2, str(len(lr["iterations"])))
    check("ORCH-14 默认上限沿用 v1.5（5，不重造旋钮）", ORCH.LOOP_MAX_ITER == 5)
    # run-loop CLI 超限路径：编排层把超限转人工（不无限循环）
    res6 = AL.run_loop(F15.write_project(os.path.join(tmp, "exh")) and os.path.join(tmp, "exh"),
                       max_iterations=1, auto_repair=False)
    check("boundary 无改善即停（stopped_reason 存在）",
          "stopped_reason" in res6, str(res6.get("stopped_reason")))
    # drive 级保护
    rc7, acts, cur = ORCH.drive(root4, max_steps=3)
    check("ORCH-14 drive 步数上限生效（绝不无限循环）", len(acts) <= 3, str(len(acts)))

    # ---------- BLOCK→回退→重入→通过 闭环（指令 §二 recovery 分支） ----------
    root5 = bring(os.path.join(tmp, "cycle"), "S9", variant="infeasible")
    AL.run_loop(root5)                      # 生成 loop BLOCK 证据
    rc8, r8 = ORCH.step(root5)
    check("S9 INFEASIBLE→ROLLBACK 到 S3（recovery 链）",
          r8["action"] == "ROLLBACK" and TS.load_state(root5)[0]["stage"]["current"] == "S3",
          str(r8)[:120])
    st5, _ = TS.load_state(root5)
    open_iss = [i for i in st5["stage"]["open_issues"] if i["status"] == "open"]
    check("回退挂 design 类 open_issue（structure）", open_iss and open_iss[0]["category"] == "structure")
    # 人工修复设计（模拟：收敛 RQ needs 使其匹配方法）→ 重跑诊断 → 清问题 → 返程
    dg = RI.load_registry(root5, "design")[0]
    for rq in dg.get("rq_requirements") or []:
        rq["needs"] = ["fault_modes", "fault_effects", "risk_ranking",
                       "repair_priority", "strategy_mapping"]
        rq["evidence_requirement"] = "simulated_ok"
    RI.save_registry(root5, "design", [dg])
    ORCH.step(root5)                        # S3 出口齐（诊断证据旧→需重跑）
    ORCH.step(root5)                        # 重跑 feasibility 证据（FEASIBLE）
    for i in open_iss:
        TS.close_issue(root5, i["id"])
    st5, _ = TS.load_state(root5)
    st5["stage"]["current"] = "S3"
    TS.save_state(root5, st5)
    r_back = AL.run_loop(root5)
    check("设计修复后 loop 不再 BLOCK（重入合法）",
          r_back["status"] != "BLOCK", r_back["status"])

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_agent_loop_integration 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
