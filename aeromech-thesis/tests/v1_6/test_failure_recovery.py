# -*- coding: utf-8 -*-
"""test_failure_recovery.py — Failure Recovery 五策略（指令 §七~九；ORCH-09~13）

恢复决策必须由 issue_type + severity + routing（阶段映射）+ state 共同决定。
场景使用 v1.5 真实缺陷夹具（非硬编 findings）：
  retry=RETRY / 计算·写作类=REPAIR（白名单）/ 证据冲突=HUMAN_REVIEW（复用 v1.4.1 队列）/
  设计不可行=ROLLBACK / Critical 完整性=BLOCK。
运行：python tests/v1_6/test_failure_recovery.py
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
import stage_routing as SR
import research_integrity as RI
import research_diagnosis as RDIA
import research_agent_loop as AL
import research_repair as RRP
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("f15", os.path.join(HERE, "..", "v1_5", "_fixtures.py"))
F15 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(F15)

PASS, FAIL = 0, 0
STAGES = TS.STAGES

REG_STAGE = {"rq": "S3", "methods": "S3", "design": "S3", "scope": "S3", "repairs": "S3",
             "evidence": "S4", "conflicts": "S4", "analyses": "S5",
             "datasets": "S6", "computations": "S6",
             "claims": "S7", "conclusions": "S7", "figures": "S8"}


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def prune_registries(root, stage):
    for reg, st_ in REG_STAGE.items():
        if STAGES.index(st_) > STAGES.index(stage):
            RI.save_registry(root, reg, [])
    tp = os.path.join(root, ".aeromech", "research", "traceability.json")
    if os.path.isfile(tp):
        os.remove(tp)


def bring(root, stage, variant=None):
    F.make_project(root)
    filler = os.path.join(root, ".filler")
    F15.write_project(filler, variant=variant)
    shutil.copytree(os.path.join(filler, ".aeromech", "research"),
                    os.path.join(root, ".aeromech", "research"))
    shutil.copytree(os.path.join(filler, ".aeromech", "artifacts", "chapters"),
                    os.path.join(root, ".aeromech", "artifacts", "chapters"), dirs_exist_ok=True)
    shutil.rmtree(filler)
    prune_registries(root, stage)
    st, _ = TS.load_state(root)
    st["project"].update(title="恢复测试题", paper_type="research")
    st["stage"]["current"] = stage
    st["writing"]["status"] = "draft_done" if STAGES.index(stage) >= STAGES.index("S7") else "not_started"
    st["research"].update(topic_card_file="artifacts/topic-card.md",
                          plan_file="artifacts/research-plan.md",
                          outline_file="artifacts/thesis-outline.md",
                          literature_status="reviewed")
    for n in ("topic-card", "research-plan", "thesis-outline"):
        F.write_text(root, f".aeromech/artifacts/{n}.md", "# x\n")
    TS.save_state(root, st)
    return root


def main():
    tmp = tempfile.mkdtemp(prefix="rec_v16_")
    print("== test_failure_recovery ==")

    # ---------- 决策矩阵单元：issue_type+severity+routing+state 共同决定 ----------
    state = {"stage": {"current": "S7"}}
    cases = [
        ({"issue_type": "FEASIBILITY_BLOCK", "severity": "critical", "human": True}, "rollback"),
        ({"issue_type": "RQ_METHOD_MISMATCH", "severity": "high", "human": True}, "rollback"),
        ({"issue_type": "UNRESOLVED_CONFLICT", "severity": "high", "human": True}, "human_review"),
        ({"issue_type": "CLAIM_OVERSTRENGTH", "severity": "high", "auto_repairable": True}, "repair"),
        ({"issue_type": "CONCLUSION_OVERREACH", "severity": "critical"}, "block"),
        ({"issue_type": "SCOPE_OVERFLOW", "severity": "high", "human": True}, "rollback"),
    ]
    for f, want in cases:
        got = ORCH.classify_recovery(None, [f], state)[0][0]
        check(f"策略判定 {f['issue_type']}→{want}", got == want, got)
    # 优先级：block > rollback > human_review > repair（混合时取最重）
    mixed = [{"issue_type": "CLAIM_OVERSTRENGTH", "severity": "high", "auto_repairable": True},
             {"issue_type": "UNRESOLVED_CONFLICT", "severity": "high", "human": True},
             {"issue_type": "RQ_METHOD_MISMATCH", "severity": "high"},
             {"issue_type": "CONCLUSION_OVERREACH", "severity": "critical"}]
    check("混合 findings 按严重度排序（block 优先）",
          ORCH.classify_recovery(None, mixed, state)[0][0] == "block")
    # retry 不掩盖 critical（指令 §24）：critical 不映射 retry
    crit_retry = ORCH.classify_recovery(None, [{"issue_type": "CONCLUSION_OVERREACH",
                                                "severity": "critical"}], state)
    check("critical 绝不判 retry", crit_retry[0][0] != "retry")
    # S1 时的设计类 → 目标 S3（前进非回退，由 transition 层把关合法性）
    droot = F.make_project(os.path.join(tmp, "dummy"))
    st1 = {"stage": {"current": "S1"}}
    rc, rep = ORCH.recovery(droot, [("rollback", {"issue_type": "RQ_METHOD_MISMATCH",
                                                  "severity": "high"},
                                     {"to": "S3"})], st1)
    check("边界：cur=S1 rollback 迁移被 StateIO 拒绝（S1→S3 非回退边）",
          rep["action"] == "ROLLBACK" and rep.get("ok") is False and rc == 1, str(rep)[:120])

    # ---------- ORCH-13 Critical BLOCK（真实 loop：证据伪装 critical，RI-E-DISGUISE） ----------
    root = bring(os.path.join(tmp, "crit"), "S9")
    ev = RI.load_registry(root, "evidence")
    ev[0]["source_type"] = "simulation"
    ev[0]["verification_status"] = "verified"        # 伪装：critical（v1.4 不静默）
    RI.save_registry(root, "evidence", ev)
    res = AL.run_loop(root)   # 真实诊断链
    check("真实 v1.5 loop 对 Critical 完整性缺陷给出 BLOCK",
          res["status"] == "BLOCK", str(res.get("status")))
    rc, r = ORCH.step(root)
    check("ORCH-13 blocked→BLOCK（Critical 完整性不得 retry 掩盖）",
          rc == 1 and r["action"] == "BLOCK", str(r)[:160])
    stx, _ = TS.load_state(root)
    check("ORCH-13 BLOCK 不改阶段不伪造修复", stx["stage"]["current"] == "S9")
    check("ORCH-13 BLOCK 记录进 Action 日志",
          any(x["status"] == "BLOCK" for x in ORCH.read_actions(root)))

    # ---------- ORCH-11 ROLLBACK（真实 infeasible → 设计类回退 S3） ----------
    root2 = bring(os.path.join(tmp, "roll"), "S7", variant="infeasible")
    AL.run_loop(root2)
    rc, r = ORCH.step(root2)
    st2, _ = TS.load_state(root2)
    check("ORCH-11 设计不可行→ROLLBACK（stays/route 到 S3；不得硬写论文）",
          r["action"] == "ROLLBACK" and st2["stage"]["current"] == "S3",
          str(r)[:140])
    h2 = st2["stage"]["history"][-1]
    check("ORCH-11 回退经 thesis_state（type=revert+触发 issue_id+reason）",
          h2["type"] == "revert" and h2["issue_id"] and "recovery" in h2["reason"], str(h2)[:120])
    check("ORCH-11 回退前建 checkpoint（失败恢复之前，指令 §六）",
          any("recovery-before" in (c.get("task") or "") for c in TS.load_checkpoints(root2)))
    check("ORCH-11 自动挂 open_issue（category 映射 structure）",
          any(i["category"] == "structure" for i in st2["stage"]["open_issues"]))

    # ---------- ORCH-10 REPAIR（真实白名单：claim 降级） ----------
    root3 = bring(os.path.join(tmp, "fix"), "S7", variant="claim_overstrength")
    diag = RDIA.diagnose(root3)
    RDIA.save(root3, diag)
    auto = [d for d in diag["diagnoses"] if d["status"] == "open" and d.get("auto_repairable")]
    check("真实诊断产生 auto_repairable 项", len(auto) >= 1)
    rc, rep = ORCH.recovery(root3, ORCH.classify_recovery(root3, auto, {"stage": {"current": "S7"}}),
                            TS.load_state(root3)[0])
    check("ORCH-10 普通输出错误→REPAIR（白名单执行，不越权）",
          rc == 0 and rep["action"] == "REPAIR", str(rep)[:140])
    reps = RI.load_registry(root3, "repairs") or []
    check("REPAIR 全留痕（REP 条目 status/applied/verified）",
          reps and all(r_.get("status") in ("applied", "verified", "rejected") for r_ in reps)
          and any(r_.get("operation") in ("downgrade_wording", "number_sync") for r_ in reps),
          str([r_.get("status") for r_ in reps]))
    check("REPAIR 后重新诊断证据在位",
          os.path.isfile(os.path.join(root3, ".aeromech", "artifacts", "analysis",
                                      "research-diagnosis.json")))

    # ---------- ORCH-12 HUMAN_REVIEW（真实冲突 → 队列，不代签） ----------
    root4 = bring(os.path.join(tmp, "hum"), "S7", variant="conflict_pending")
    res = AL.run_loop(root4)
    qp = os.path.join(root4, ".aeromech", "research", "human-review-queue.yaml")
    check("人工队列由 v1.5 loop 生成（复用机制，不新建）", os.path.isfile(qp))
    import yaml
    q = yaml.safe_load(open(qp, encoding="utf-8")) or {}
    pend = [x for x in q.get("queue") or [] if not x.get("decision")]
    check("冲突类保持未裁决（禁止静默解决）", len(pend) >= 1, str([x["issue_type"] for x in pend]))
    decisions = ORCH.classify_recovery(root4, [{"issue_type": "UNRESOLVED_CONFLICT",
                                                "severity": "high", "human": True,
                                                "id": pend[0]["diagnosis_id"]}],
                                       {"stage": {"current": "S7"}})
    rc, rep = ORCH.recovery(root4, decisions, TS.load_state(root4)[0])
    check("ORCH-12 证据冲突→HUMAN_REVIEW（rc1 挂起，编排不代判）",
          rc == 1 and rep["action"] == "HUMAN_REVIEW", str(rep)[:140])
    q2 = yaml.safe_load(open(qp, encoding="utf-8")) or {}
    check("HUMAN_REVIEW 不消费/不改队列",
          q2.get("queue") == q.get("queue"))
    # "人类"回填裁决后（approve/reject），apply-human 复用 v1.5 执行
    for item in q2.get("queue") or []:
        if item.get("decision") in (None, ""):
            item["decision"] = "reject"
            item["reviewer"] = "外部复核者-测试"
            item["note"] = "reject（测试模拟人类裁决）"
    yaml.safe_dump({"queue": q2["queue"]}, open(qp, "w", encoding="utf-8"), allow_unicode=True)
    rc, rep = ORCH.apply_human(root4)
    check("ORCH-12 apply-human 委托 research_repair（不重造）",
          rc == 0 and rep["status"] == "APPLIED", str(rep)[:140])
    q3 = yaml.safe_load(open(qp, encoding="utf-8")) or {}
    check("裁决被消费（applied_status 写回，不静默丢弃）",
          all(str(x.get("applied_status") or x.get("decision")) not in ("", "None")
              for x in q3.get("queue") or []))

    # ---------- ORCH-09 RETRY（工具瞬时失败；上限 1 次） ----------
    root5 = bring(os.path.join(tmp, "retry"), "S3")
    calls = {"n": 0}
    orig = ORCH.execute_ai

    def flaky(root, ai_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "tool": "flaky", "detail": "瞬时故障（模拟环境抖动）"}
        return orig(root, ai_id)
    ORCH.execute_ai = flaky
    try:
        rc, r = ORCH.step(root5)     # 首次失败→retry→二次成功
    finally:
        ORCH.execute_ai = orig
    check("ORCH-09 pending 工具瞬时失败→RETRY 一次后成功",
          r["action"] == "RUN_PENDING" and calls["n"] == 2, str(r)[:120])
    check("ORCH-09 RETRY 有 Action 记录",
          any(x["status"] == "RETRY" for x in ORCH.read_actions(root5)))
    # 持续失败 → 重试上限后停（RETRY_EXHAUSTED），不无限循环（全新项目：pending 未被消费）
    root6 = bring(os.path.join(tmp, "retry2"), "S3")
    ORCH.execute_ai = lambda root, ai_id: {"ok": False, "tool": "broken", "detail": "永久故障"}
    try:
        rc2, r2 = ORCH.step(root6)
    finally:
        ORCH.execute_ai = orig
    check("ORCH-09 重试上限=1：二次仍失败→RETRY_EXHAUSTED 停止（不无限 retry）",
          r2["action"] == "RETRY_EXHAUSTED" and rc2 == 1, str(r2)[:120])
    # 证据已生成（retry 成功那次的项目），step 不再 run_pending

    # ---------- 指令 §二十四：Overall Score 不掩盖 BLOCK ----------
    # （评分仅展示：blocked 时 gate 仍 BLOCK——由 routing 五态保证，此处断言编排层不读总分放行）
    dg = SR.delivery_gate_status(root)   # crit 项目：loop BLOCK 证据在位
    check("BLOCK 项目 gate 不产 PASS（评分不参与放行判定）",
          dg["status"] in ("BLOCK", "ERROR"), str(dg)[:120])

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_failure_recovery 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
