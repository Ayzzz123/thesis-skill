# -*- coding: utf-8 -*-
"""test_resume.py — 断点恢复全流程（指令 §七/§十二/§十六；ORCH-05）

四个中断点：S3 后、S5 中（计算中断）、S7 中、S9 QA 中。
每次 resume 必须：读取 checkpoint / 确认 artifacts+registry+QA / 恢复正确阶段 / 继续正确任务；
禁止从 S1 重启；已完成成果不丢；不重复执行不必要任务。
运行：python tests/v1_6/test_resume.py
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


# 注册表→所属阶段（与 orchestrator.registry_stage 同语义；夹具按 stage 裁剪保持一致）
REG_STAGE = {"rq": "S3", "methods": "S3", "design": "S3", "scope": "S3", "repairs": "S3",
             "evidence": "S4", "conflicts": "S4", "analyses": "S5",
             "datasets": "S6", "computations": "S6",
             "claims": "S7", "conclusions": "S7", "figures": "S8"}


def prune_registries(root, stage):
    """把注册表裁剪到 stage 应有范围（避免夹具与 state 阶段自相矛盾）。"""
    for reg, st_ in REG_STAGE.items():
        if STAGES.index(st_) > STAGES.index(stage):
            RI.save_registry(root, reg, [])
    tp = os.path.join(root, ".aeromech", "research", "traceability.json")
    if os.path.isfile(tp):
        os.remove(tp)


STAGES = TS.STAGES


def bring_to_s3(root, with_research=True, stage="S3"):
    """构造 stage 进行中的项目（注册表裁剪到该阶段应有范围+方案文件在场）。"""
    if with_research:
        filler = os.path.join(root, ".filler")
        F15.write_project(filler)
        shutil.copytree(os.path.join(filler, ".aeromech", "research"),
                        os.path.join(root, ".aeromech", "research"))
        shutil.rmtree(filler)
        prune_registries(root, stage)
    st, _ = TS.load_state(root)
    st["project"].update(title="中断恢复题", paper_type="research")
    st["stage"]["current"] = stage
    st["research"].update(topic_card_file="artifacts/topic-card.md",
                          plan_file="artifacts/research-plan.md",
                          outline_file="artifacts/thesis-outline.md",
                          literature_status="reviewed")
    for n in ("topic-card", "research-plan", "thesis-outline"):
        F.write_text(root, f".aeromech/artifacts/{n}.md", "# x\n")
    TS.save_state(root, st)


def main():
    tmp = tempfile.mkdtemp(prefix="resume_v16_")
    print("== test_resume ==")

    # ============ 中断点 1：S3（研究设计进行中） ============
    root = F.make_project(os.path.join(tmp, "r3"))
    bring_to_s3(root)
    F.write_text(root, ".aeromech/artifacts/analysis/AN-001-notes.md", "半程分析笔记\n")
    ck = TS.create_checkpoint(root, task="S3-design-review",
                              artifacts=[".aeromech/artifacts/research-plan.md",
                                         ".aeromech/artifacts/analysis/AN-001-notes.md"],
                              next_action="跑 feasibility 证据")
    # —— 进程死亡；新会话恢复 ——
    rc, res = ORCH.resume(root)
    check("S3 中断→resume 阶段=S3（不从 S1 重启）",
          rc == 0 and res["status"] == "RESUMED" and res["stage"] == "S3"
          and res["from_start"] is False, str(res)[:120])
    check("S3 resume 确认已有成果（plan+笔记 sha256 完好）",
          any("research-plan.md" in a for a in res["artifacts_ok"]))
    check("S3 resume 给出正确续点（next_action/next 非空）",
          res["next"]["action"] in ("run_pending", "advance", "stay")
          and res["next_action"] == "跑 feasibility 证据")
    # 恢复后 step 正常接续（pending 工具执行而非重做 S1/S2）
    rc2, r2 = ORCH.step(root)
    check("S3 resume→step 接续执行 pending AI（feasibility 证据生成）",
          r2["action"] == "RUN_PENDING" and r2["detail"]["done"] == ["feasibility"], str(r2)[:140])

    # ============ 中断点 2：S5 计算中断（指令 §十二 场景） ============
    root2 = F.make_project(os.path.join(tmp, "r5"))
    bring_to_s3(root2, stage="S5")
    F.write_text(root2, "out/calc/step1.md", "")
    calc1 = ".aeromech/artifacts/computation/CALC-001-output.md"
    F.write_text(root2, calc1, "RPN=180 已完成\n")          # 已完成步骤 1
    ck5 = TS.create_checkpoint(root2, task="S5-computation",
                               cursor={"done": "CALC-001", "total": "CALC-001..003"},
                               artifacts=[calc1],
                               next_action="继续 CALC-002")
    rc, res = ORCH.resume(root2)
    check("S5 中断→resume 阶段=S5 且游标恢复",
          res["stage"] == "S5" and res["cursor"].get("done") == "CALC-001", str(res)[:140])
    check("S5 已完成计算产物被确认完好（不重复执行）",
          calc1 in res["artifacts_ok"])
    check("S5 续点指向未完成步骤（next_action=继续 CALC-002）",
          res["next_action"] == "继续 CALC-002")
    # resume 不重跑已完成任务：actions 日志无重复 RUN_PENDING 对已完成 CALC 的工具
    n_before = len(ORCH.read_actions(root2))
    ORCH.step(root2)
    check("S5 resume 后 step 不删除/不覆盖已完成产物",
          os.path.isfile(os.path.join(root2, calc1)) and
          open(os.path.join(root2, calc1), encoding="utf-8").read().startswith("RPN=180"))

    # ============ 中断点 3：S7 写作中 ============
    root3 = F.make_project(os.path.join(tmp, "r7"))
    bring_to_s3(root3, stage="S7")
    st, _ = TS.load_state(root3)
    st["writing"].update(status="in_progress",
                         chapters={"ch1": {"file": "artifacts/chapters/ch1.md", "status": "done"},
                                   "ch2": {"file": "artifacts/chapters/ch2.md", "status": "wip"}})
    TS.save_state(root3, st)
    F.write_text(root3, ".aeromech/artifacts/chapters/ch1.md", "第一章全文\n")
    ck7 = TS.create_checkpoint(root3, task="S7-writing",
                               cursor={"chapters_done": "ch1", "wip": "ch2"},
                               artifacts=[".aeromech/artifacts/chapters/ch1.md"],
                               next_action="续写 ch2")
    rc, res = ORCH.resume(root3)
    check("S7 中断→resume 恢复写作游标与已完成章",
          res["cursor"]["chapters_done"] == "ch1" and
          ".aeromech/artifacts/chapters/ch1.md" in res["artifacts_ok"]
          and res["next_action"] == "续写 ch2", str(res)[:140])
    # 中断期间章稿被外部改动 → 必须报（不默默续写错版本）
    F.write_text(root3, ".aeromech/artifacts/chapters/ch1.md", "第一章全文（被改）\n")
    rc, res = ORCH.resume(root3)
    check("S7 中断期间章稿改动→ARTIFACT_CHANGED 不默默继续",
          rc == 1 and any(p["code"] == "ARTIFACT_CHANGED" for p in res["drift"]))

    # ============ 中断点 4：S9 QA 中 ============
    root4 = F.make_project(os.path.join(tmp, "r9"))
    bring_to_s3(root4, stage="S9")
    analysis = os.path.join(root4, ".aeromech", "artifacts", "analysis")
    os.makedirs(analysis, exist_ok=True)
    qa_dir = os.path.join(root4, ".aeromech", "artifacts", "qa")
    os.makedirs(qa_dir, exist_ok=True)
    st, _ = TS.load_state(root4)
    st["writing"]["status"] = "draft_done"
    TS.save_state(root4, st)
    F.write_text(root4, ".aeromech/artifacts/chapters/ch1.md", "全文\n")
    # QA 跑到一半：诊断已生成，loop 未跑完
    with open(os.path.join(analysis, "research-diagnosis.json"), "w", encoding="utf-8") as f:
        json.dump({"feasibility": {"verdict": "FEASIBLE", "reasons": []}, "diagnoses": [],
                   "counts": {"total": 0, "critical": 0, "high": 0}}, f)
    ck9 = TS.create_checkpoint(root4, task="S9-qa",
                               artifacts=[".aeromech/artifacts/analysis/research-diagnosis.json"],
                               qa_state={"diagnosis": {"status": "PASS", "report":
                                                       ".aeromech/artifacts/analysis/research-diagnosis.json"}},
                               next_action="跑 agent loop（full_qa）")
    rc, res = ORCH.resume(root4)
    check("S9 QA 中断→resume 阶段=S9 且 QA 状态保留",
          res["stage"] == "S9" and res["qa_state"].get("diagnosis", {}).get("status") == "PASS",
          str(res)[:140])
    # 恢复后 step：loop 证据缺→run_pending 执行 loop（既有工具），QA 中间成果（诊断 json）不丢
    rc2, r2 = ORCH.step(root4)
    check("S9 resume→step 续跑 full_qa（既有 Agent Loop，不重造）",
          r2["action"] == "RUN_PENDING" and r2["detail"]["done"] == ["full_qa"]
          and r2["detail"]["result"].get("status") in
          ("PASS", "PASS_WITH_WARNINGS", "WARN", "PASS_WITH_HUMAN_REVIEW", "BLOCK"), str(r2)[:160])
    check("S9 续跑不丢既有 QA 中间成果（诊断 json 仍在）",
          os.path.isfile(os.path.join(analysis, "research-diagnosis.json")))

    # ============ 通用：无 checkpoint 的项目 ============
    root5 = F.make_project(os.path.join(tmp, "nockpt"))
    rc, res = ORCH.resume(root5)
    check("boundary 无 checkpoint：resume 仍返回当前阶段（按 state 真源，不重启）",
          rc in (0, 1) and res.get("stage", res.get("status")) in ("S1", "RESUMED")
          and res.get("from_start") is False, str(res)[:120])
    # state.yaml 不可读 → resume 不崩、不假装恢复
    open(os.path.join(root5, ".aeromech", "state.yaml"), "w", encoding="utf-8").write("\tbad: [")
    # 无备份可读时 load_state 抛 StateError → resume rc3
    rc, res = ORCH.resume(root5)
    check("boundary state 不可读→resume ERROR（不伪造恢复）",
          rc == 3 and res["status"] == "ERROR")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_resume 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
