# -*- coding: utf-8 -*-
"""test_orchestrator.py — Orchestrator 主循环 / Action 模型 / 迁移纪律（v1.6 §一~六、ORCH-01~04/06~08）

覆盖：正常前进、非法前进（委托 StateIO 拒绝）、run_pending（SKIPPED_WITH_REASON 必须执行）、
checkpoint（字段+sha256）、Action 记录（禁止静默）、artifact/registry/state drift。
运行：python tests/v1_6/test_orchestrator.py
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

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def fill_s1(root):
    st, _ = TS.load_state(root)
    st["project"].update(title="题目X", paper_type="research")
    st["research"]["topic_card_file"] = "artifacts/topic-card.md"
    F.write_text(root, ".aeromech/artifacts/topic-card.md", "# card\n")
    TS.save_state(root, st)


def s3_ready(root):
    F.write_text(root, ".aeromech/artifacts/research-plan.md", "# p\n")
    F.write_text(root, ".aeromech/artifacts/thesis-outline.md", "# o\n")
    st, _ = TS.load_state(root)
    st["research"].update(plan_file="artifacts/research-plan.md",
                          outline_file="artifacts/thesis-outline.md")
    TS.save_state(root, st)


def main():
    tmp = tempfile.mkdtemp(prefix="orch_v16_")
    print("== test_orchestrator ==")

    # ---------- ORCH-01 正常前进 ----------
    root = F.make_project(os.path.join(tmp, "adv"))
    fill_s1(root)
    rc, res = ORCH.step(root)
    check("ORCH-01 S1 出口齐→前进（经 StateIO 合法边）",
          rc == 0 and res["action"] == "ADVANCE" and res["to"] == "S2", str(res))
    rc2, res2 = ORCH.step(root)
    check("ORCH-01 S2→S3 前进", rc2 == 0 and res2["action"] == "ADVANCE"
          and res2["to"] == "S3", str(res2))
    st, _ = TS.load_state(root)
    check("ORCH-01 history 记 forward 且迁移由 thesis_state 完成",
          st["stage"]["history"][-1]["type"] == "forward"
          and len(st["stage"]["history"]) == 3)

    # ---------- ORCH-02 非法前进：拒绝且不落盘 ----------
    root2 = F.make_project(os.path.join(tmp, "illegal"))
    rc, res = ORCH.step(root2)   # S1 空项目：出口产物缺
    check("ORCH-02 出口未齐→NEEDS_UPSTREAM_WORK（编排不代做研究/不硬推进）",
          res["action"] == "NEEDS_UPSTREAM_WORK" and rc == 1, str(res))
    st2, _ = TS.load_state(root2)
    check("ORCH-02 state 未被改写", st2["stage"]["current"] == "S1"
          and len(st2["stage"]["history"]) == 1)
    # 伪造 route 返回非法 advance → transition 拒绝，不落盘
    orig_route = SR.route
    SR.route = lambda r: {"status": "OK", "current": "S1", "blocked": False, "block_reason": "",
                          "stages_completed": [], "stage_complete": True,
                          "gates": SR.gates(r)[0], "next": {"action": "advance", "to": "S7", "reason": "x"},
                          "ai_mounts": [], "research_context_status": "NOT_APPLICABLE"}
    try:
        rc, res = ORCH.step(root2)
    finally:
        SR.route = orig_route
    st2b, _ = TS.load_state(root2)
    check("ORCH-02 非法迁移经 StateIO 拒绝（ADVANCE_REJECTED，history 不变）",
          res["action"] == "ADVANCE_REJECTED" and rc == 1
          and st2b["stage"]["current"] == "S1" and len(st2b["stage"]["history"]) == 1)

    # ---------- ORCH-03 RUN_PENDING：SKIPPED_WITH_REASON 必须执行 pending 工具 ----------
    root3 = F.make_project(os.path.join(tmp, "pending"))
    # 造 design.yaml（S3 级）→ feasibility 门禁 SKIPPED_WITH_REASON
    os.makedirs(os.path.join(root3, ".aeromech", "research"), exist_ok=True)
    RI.init_registries(root3)
    st3, _ = TS.load_state(root3)
    st3["stage"]["current"] = "S3"
    st3["project"].update(title="T", paper_type="research")
    st3["research"].update(topic_card_file="artifacts/topic-card.md",
                           plan_file="artifacts/research-plan.md",
                           outline_file="artifacts/thesis-outline.md")
    TS.save_state(root3, st3)
    for n in ("topic-card", "research-plan", "thesis-outline"):
        F.write_text(root3, f".aeromech/artifacts/{n}.md", "# x\n")
    RI.save_registry(root3, "rq", [{"id": "RQ-01", "question": "q", "objective": "o",
                                    "related_methods": ["M-001"], "related_chapters": [3],
                                    "related_analyses": ["AN-001"], "related_conclusions": ["CON-001"]}])
    RI.save_registry(root3, "design", [{"id": "DESIGN-001", "research_questions": ["RQ-01"],
                                        "objectives": ["o"], "methods": ["M-001"],
                                        "rq_requirements": [{"id": "RQ-01", "needs": ["n1"],
                                                             "evidence_requirement": "simulated_ok"}],
                                        "analysis_plan": ["AN-001"], "expected_outputs": ["FIG-001"],
                                        "constraints": [], "assumptions": ["a"], "limitations": ["l"]}])
    rc, res = ORCH.step(root3)
    check("ORCH-03 feasibility 证据缺→RUN_PENDING 执行既有诊断工具",
          res["action"] == "RUN_PENDING" and res["detail"]["done"] == ["feasibility"]
          and res["detail"]["result"]["ok"], str(res)[:160])
    check("ORCH-03 pending 工具产出真实证据文件",
          os.path.isfile(os.path.join(root3, ".aeromech", "artifacts", "analysis",
                                      "research-diagnosis.json")))
    check("ORCH-03 RUN_PENDING 后 checkpoint 已建（task=ai:）",
          "ai:feasibility" in str(TS.load_checkpoints(root3)))
    # 证据在位后，S3 前进判定恢复（design 无 AN 条目 → INFEASIBLE 分支属 recovery 测试）

    # ---------- ORCH-04 checkpoint 完整性（指令 §六） ----------
    cps = TS.load_checkpoints(root3)
    cp = [c for c in cps if c["task"] == "ai:feasibility"][0]
    need = {"checkpoint_id", "stage", "task", "ts", "cursor", "artifacts",
            "registries", "qa_state", "next_action"}
    check("ORCH-04 checkpoint 字段齐备", need <= set(cp))
    check("ORCH-04 artifact 带 sha256",
          all((v.get("sha256") is None or len(v["sha256"]) == 64)
              for v in cp["artifacts"].values()))
    check("ORCH-04 registry snapshot 含 design 计数",
          cp["registries"]["design"]["present"] and cp["registries"]["design"]["count"] == 1)

    # ---------- ORCH-06 artifact integrity（指令 §十三） ----------
    root6 = F.make_project(os.path.join(tmp, "artint"))
    F.write_text(root6, ".aeromech/artifacts/chapters/ch3.md", "定稿内容\n")
    TS.create_checkpoint(root6, artifacts=[".aeromech/artifacts/chapters/ch3.md"],
                         next_action="写 ch4")
    F.write_text(root6, ".aeromech/artifacts/chapters/ch3.md", "被偷偷改了\n")
    rc, res = ORCH.resume(root6)
    check("ORCH-06 artifact 变化→resume 拒绝默默继续（NEEDS_HUMAN_REVIEW）",
          rc == 1 and res["status"] == "NEEDS_HUMAN_REVIEW"
          and any(p["code"] == "ARTIFACT_CHANGED" for p in res["drift"]), str(res)[:140])
    F.write_text(root6, ".aeromech/artifacts/chapters/ch3.md", "定稿内容\n")  # 还原
    rc, res = ORCH.resume(root6)
    check("ORCH-06 还原后 resume 正常", rc == 0 and res["status"] == "RESUMED")
    os.remove(os.path.join(root6, ".aeromech", "artifacts", "chapters", "ch3.md"))
    rc, res = ORCH.resume(root6)
    check("ORCH-06 artifact 丢失→resume ERROR", rc == 3 and any(
        p["code"] == "ARTIFACT_MISSING" for p in res["drift"]))

    # ---------- ORCH-07 registry drift（指令 §十四） ----------
    root7 = F.make_project(os.path.join(tmp, "regdrift"))
    os.makedirs(os.path.join(root7, ".aeromech", "research"), exist_ok=True)
    RI.save_registry(root7, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(root7, "claims", [{"id": "CL-001", "claim": "c", "claim_type": "fact"}])
    RI.save_registry(root7, "conclusions", [{"id": "CON-001", "conclusion": "x",
                                             "claims": ["CL-001"], "analyses": ["AN-001"]}])
    # state 仍在 S5，注册表却已有 S7 级内容
    st7, _ = TS.load_state(root7)
    st7["stage"]["current"] = "S5"
    TS.save_state(root7, st7)
    probs, _v = ORCH.drift_checks(root7)
    codes = [p["code"] for p in probs]
    check("ORCH-07 state=S5 而 registry=S7 → REGISTRY_DRIFT 检出（不静默覆盖）",
          "REGISTRY_DRIFT" in codes, str(codes))
    rc, res = ORCH.resume(root7)
    check("ORCH-07 drift→resume 转人工（NEEDS_HUMAN_REVIEW，state 不改写）",
          rc == 1 and res["status"] == "NEEDS_HUMAN_REVIEW"
          and TS.load_state(root7)[0]["stage"]["current"] == "S5")

    # ---------- ORCH-08 state drift（指令 §十五） ----------
    root8 = F.make_project(os.path.join(tmp, "statedrift"))
    TS.create_checkpoint(root8, task="在 S4 工作")
    st8, _ = TS.load_state(root8)
    st8["stage"]["current"] = "S5"          # 外部直改 state（模拟中断时未记录迁移）
    TS.save_state(root8, st8)
    rc, res = ORCH.resume(root8)
    check("ORCH-08 checkpoint=S4 而 state=S5 → STATE_DRIFT 需人工",
          rc == 1 and any(p["code"] == "STATE_DRIFT" for p in res["drift"]), str(res)[:140])

    # ---------- Action 记录（指令 §三：禁止静默执行） ----------
    acts = ORCH.read_actions(root3)
    check("Action 记录含七字段（action_id/stage/reason/input/output/status/timestamp）",
          acts and all({"action_id", "stage", "reason", "input", "output",
                        "status", "timestamp"} <= set(x) for x in acts))
    check("Action id 稳定递增",
          [x["action_id"] for x in acts] == sorted(x["action_id"] for x in acts))
    ids = {x["action_id"] for x in ORCH.read_actions(root)}
    check("跨项目 action id 独立计数", ids and all(i.startswith("ACT-") for i in ids))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_orchestrator 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
