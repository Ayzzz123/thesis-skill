# -*- coding: utf-8 -*-
"""thesis_orchestrator.py — Full-Stack Thesis Orchestrator（aeromech-thesis v1.6.0）

职责边界（指令 §一）：routing / state / coordination / checkpoint / recovery——
**不含具体业务逻辑**：研究判断全部复用 research_integrity / research_quality_qa /
research_diagnosis / research_repair / research_agent_loop（v1.4/v1.5 原样调用），
阶段判定复用 stage_routing.route()（指令 §四：不自己重新判断 S1-S10），
状态迁移只经 thesis_state（指令 §五：非法边拒绝不落盘，override 需确认记录，回退需触发源），
检查点只经 thesis_state checkpoint（指令 §六），人工复核复用 v1.4.1/§六双队列机制（指令 §十六）。

主循环（指令 §二）：LOAD STATE → LOAD CONTEXT → ROUTE → CHECK PREREQUISITES →
EXECUTE → SAVE ARTIFACT → CHECKPOINT → VALIDATE → NEXT；FAIL → DIAGNOSE → RECOVERY；
NEEDS_HUMAN_REVIEW → 队列；CRITICAL → BLOCK。

Action 模型（指令 §三）：每个动作一条记录 {action_id, stage, reason, input, output,
status, timestamp}，追加写 artifacts/analysis/orchestrator-actions.jsonl——禁止静默执行。

用法：
  python thesis_orchestrator.py <root> status [--json]
  python thesis_orchestrator.py <root> step          # 执行一步（一个 Action）
  python thesis_orchestrator.py <root> drive [--until S9] [--max-steps 25]
  python thesis_orchestrator.py <root> resume        # 中断恢复（drift + artifact 完整性 + 续点）
  python thesis_orchestrator.py <root> run-loop [--max-iterations 5]
  python thesis_orchestrator.py <root> apply-human   # 消费人工裁决（复用 research_repair）
  python thesis_orchestrator.py <root> gate [--json]
  python thesis_orchestrator.py <root> actions [--last N]
退出码：0=动作成功；1=BLOCK/迁移拒绝/恢复要求人工（判定本身成功但流程受阻）；
       2=环境（无 .aeromech）；3=ERROR（state/注册表不可读、drift）
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

import thesis_state as TS
import research_context as RC
import stage_routing as SR
import research_integrity as RI
import research_diagnosis as RDIA
import research_repair as RRP
import research_agent_loop as AL
import research_quality_qa as RQA
import delivery_gate as DG

STAGE_ORDER = SR.STAGES
DRIVE_DEFAULT_MAX = 25          # 总步数保护（防驱动层无限循环；阶段内轮次保护由 v1.5 loop 负责）
RETRY_MAX = 1                   # 同一 pending 工具失败重试上限（超过→升级人工/停）
LOOP_MAX_ITER = AL.MAX_ITERATIONS   # 5（指令 §十一：复用 v1.5 loop 的轮次与日志机制，不重造）

# issue_type → 恢复策略（指令 §八/§九：由 issue_type + severity + routing + state 共同决定；表为数据）
DESIGN_ROLLBACK = {"FEASIBILITY_BLOCK", "RQ_METHOD_MISMATCH", "DESIGN_EVIDENCE_MISMATCH",
                   "METHOD_SELECTION_WEAK", "SCOPE_OVERFLOW", "SCOPE_UNDERFLOW"}
HUMAN_TYPES = {"UNRESOLVED_CONFLICT"}
BLOCK_TYPES = set()             # v1.5 disposition=block 的 critical 默认即 BLOCK，无需名单
# AI 挂载点 → 执行器（只调既有工具，不新造逻辑）
AI_EXECUTOR = {
    "feasibility": "diagnose", "diagnosis": "diagnose", "data_integrity": "diagnose",
    "coverage": "rqg", "figure_traceability": "trace+diagnose",
    "agent_loop": "loop", "full_qa": "loop",
}


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def actions_path(root):
    return os.path.join(root, ".aeromech", "artifacts", "analysis", "orchestrator-actions.jsonl")


_counter = {"n": None}


def log_action(root, stage, reason, input_, output, status):
    """Action 记录（指令 §三）。n 以文件行数续计（跨进程稳定）。"""
    p = actions_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if _counter["n"] is None:
        try:
            with open(p, encoding="utf-8") as f:
                _counter["n"] = sum(1 for _ in f)
        except OSError:
            _counter["n"] = 0
    _counter["n"] += 1
    rec = {"action_id": f"ACT-{_counter['n']:04d}", "stage": stage, "reason": reason,
           "input": input_, "output": output, "status": status, "timestamp": _now()}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_actions(root, last=None):
    p = actions_path(root)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f if l.strip()]
    return recs[-last:] if last else recs


# ---------------- 状态/上下文/路由装载 ----------------

def load_all(root):
    state, repaired = TS.load_state(root)
    ctx = RC.context(root)
    r = SR.route(root)
    return state, ctx, r


def registry_stage(ctx):
    """从注册表推断已达阶段（drift 检测用；数据表，非业务逻辑）。"""
    if ctx.get("status") != "OK":
        return None
    counts = ctx["summary"]["counts"]
    infer = "S3" if (counts.get("rq") or counts.get("design")) else None
    if counts.get("evidence"):
        infer = "S4"
    if counts.get("analyses"):
        infer = "S5"
    if counts.get("datasets") or counts.get("computations"):
        infer = "S6"
    if counts.get("claims") or counts.get("conclusions"):
        infer = "S7"
    if counts.get("figures"):
        infer = "S8"
    return infer


def drift_checks(root, state=None, ctx=None):
    """STATE_DRIFT / REGISTRY_DRIFT / ARTIFACT 完整性（指令 §十三/§十四/§十五）。
    返回 (drift_problems, resume_view)。发现 drift 绝不静默覆盖。"""
    state = state or TS.load_state(root)[0]
    ctx = ctx or RC.context(root)
    v = TS.resume_view(root)
    problems = []
    st_stage = (state.get("stage") or {}).get("current")
    if v["checkpoint"] and v["checkpoint_stage"] != st_stage:
        problems.append({"code": "STATE_DRIFT",
                         "detail": f"state={st_stage} 但 checkpoint {v['checkpoint']} 记 {v['checkpoint_stage']}",
                         "disposition": "NEEDS_HUMAN_REVIEW"})
    reg_stage = registry_stage(ctx)
    if reg_stage and st_stage and STAGE_ORDER.index(reg_stage) > STAGE_ORDER.index(st_stage):
        problems.append({"code": "REGISTRY_DRIFT",
                         "detail": f"state={st_stage}，但注册表已含 {reg_stage} 级内容（不得静默覆盖：人工确认或补 state 迁移记录）",
                         "disposition": "NEEDS_HUMAN_REVIEW"})
    if v["artifacts_missing"]:
        problems.append({"code": "ARTIFACT_MISSING",
                         "detail": f"checkpoint 登记的产物丢失：{v['artifacts_missing']}",
                         "disposition": "ERROR"})
    if v["artifacts_changed"]:
        problems.append({"code": "ARTIFACT_CHANGED",
                         "detail": f"checkpoint 登记的产物在 checkpoint 之后被改动（非经 Orchestrator）："
                                   f"{v['artifacts_changed']}；sha256 不一致，不得默默继续",
                         "disposition": "NEEDS_HUMAN_REVIEW"})
    for pr in v["state_problems"]:
        problems.append({"code": "STATE_INVALID", "detail": f"{pr['field']}: {pr['reason']}",
                         "disposition": "ERROR"})
    return problems, v


# ---------------- pending 工具执行（只调既有模块函数） ----------------

def execute_ai(root, ai_id):
    """执行 AI 挂载点对应的既有工具（无 subprocess shell，进程内直调；指令 §四：SKIPPED_WITH_REASON
    必须执行 pending tool，不能放行）。返回 {tool, rc-like, detail}。"""
    kind = AI_EXECUTOR.get(ai_id)
    if kind is None:
        return {"ok": False, "detail": f"未知挂载点 {ai_id}"}
    try:
        if kind == "diagnose":
            res = RDIA.diagnose(root)
            RDIA.save(root, res)
            return {"ok": True, "tool": "research_diagnosis.diagnose+save",
                    "detail": f"counts={res['counts']} feasibility={(res.get('feasibility') or {}).get('verdict')}"}
        if kind == "rqg":
            summary, _rep = RQA.run(root, verbose=False)
            return {"ok": True, "tool": "research_quality_qa.run", "gate": summary.get("gate"),
                    "detail": f"gate={summary.get('gate')}"}
        if kind == "trace+diagnose":
            RI.save_traceability(root)
            res = RDIA.diagnose(root)
            RDIA.save(root, res)
            return {"ok": True, "tool": "research_integrity.save_traceability + diagnosis",
                    "detail": f"counts={res['counts']}"}
        if kind == "loop":
            rqa, _ = RQA.run(root, verbose=False)          # full_qa 含 RQG 报告落盘
            res = AL.run_loop(root, max_iterations=LOOP_MAX_ITER)
            return {"ok": True, "tool": "research_agent_loop.run_loop",
                    "status": res["status"], "rqg": rqa.get("gate"),
                    "detail": json.dumps({"status": res["status"], "stopped_reason": res.get("stopped_reason"),
                                          "block_reasons": res.get("block_reasons"),
                                          "open_findings": res.get("open_findings")}, ensure_ascii=False)}
    except Exception as e:
        return {"ok": False, "tool": str(kind), "detail": f"{type(e).__name__}: {e}"}
    return {"ok": False, "detail": f"无执行器 {kind}"}


def pending_ai_ids(root, stage):
    """该阶段 gate 证据未生成的挂载点 id 列表（结构化，不解析字符串）。"""
    gs, _state, ctx = SR.gates(root)
    out = []
    for ai in SR.matrix().get(stage, {}).get("ai", []):
        gk = SR._gate_key_for(ai["id"])
        if gs.get(gk, {}).get("status") == "SKIPPED_WITH_REASON":
            out.append(ai["id"])
    return out


# ---------------- Failure Recovery（指令 §七/§八/§九） ----------------

def classify_recovery(root, findings, state):
    """五策略判定（issue_type + severity + disposition + routing 阶段映射 共同决定）。
    disposition 是 v1.5 诊断引擎按优先级链判定的权威通道（block=完整性失败/queue=人工判定/
    auto=白名单可修），编排层消费它，不自行重新发明；缺字段条目（合成测试）按 issue_type/severity 回退。
    设计类优先 ROLLBACK（指令 §九：研究设计不可行→rollback/redesign）；rollback 落点=
    routing 的 issue→阶段映射；Critical/High integrity→BLOCK（retry 不得掩盖，指令 §24）。"""
    cur = (state.get("stage") or {}).get("current")
    decisions = []
    for f in findings or []:
        it = f.get("issue_type")
        sev = str(f.get("severity", "")).lower()
        disp = f.get("disposition")
        if it in DESIGN_ROLLBACK:
            tgt = SR.issue_target(it) or "S3"
            decisions.append(("rollback", f, {"to": tgt}))
        elif disp == "auto" or f.get("auto_repairable") or f.get("auto"):
            decisions.append(("repair", f, {}))
        elif (disp == "block" and sev in ("critical", "high")) or sev == "critical":
            decisions.append(("block", f, {}))
        elif disp == "queue" or f.get("human") or it in HUMAN_TYPES:
            decisions.append(("human_review", f, {}))
        else:
            decisions.append(("repair", f, {}))
    order = {"block": 0, "rollback": 1, "human_review": 2, "repair": 3, "retry": 4}
    decisions.sort(key=lambda x: order[x[0]])
    return decisions


def recovery(root, decisions, state):
    """执行恢复动作。返回 (rc, report)。rollback 前必做 checkpoint（失败恢复之前，指令 §六）。"""
    if not decisions:
        return 0, {"action": "none"}
    strategy, f, extra = decisions[0]
    cur = (state.get("stage") or {}).get("current")
    if strategy == "retry":
        # 瞬时执行失败：重跑该 pending（调用方计数上限 RETRY_MAX，超限升级）
        return 0, {"action": "retry", "issue": f.get("issue_type")}
    if strategy == "repair":
        TS.create_checkpoint(root, task=f"recovery-before-repair:{f.get('id')}",
                             next_action="whitelist repair then re-diagnose")
        plan = RRP.plan(root)
        exe = RRP.execute(root)
        RDIA.save(root, RDIA.diagnose(root))
        return 0, {"action": "REPAIR", "plan": len(plan or []), "exec": exe if not isinstance(exe, dict) else exe}
    if strategy == "rollback":
        to = extra["to"]
        if cur == to:
            # 已在目标阶段（典型：S3 设计不可行）→ 设计修复仅限人工决策（v1.5 §3），不得自动放行
            return 1, {"action": "HUMAN_REVIEW",
                       "queue": ".aeromech/research/human-review-queue.yaml",
                       "note": f"设计类问题 {f.get('issue_type')} 已在 {cur}：修复途径仅限人工决策（REFRAME/LIMIT/ADD）"}
        TS.create_checkpoint(root, task=f"recovery-before-rollback:{f.get('issue_type')}",
                             next_action=f"rollback→{to}")
        iss = TS.add_issue(root, severity="严重" if f.get("severity") == "critical" else "高",
                           category=_issue_category(f.get("issue_type")),
                           target_stage=to,
                           desc=f"orchestrator rollback: {f.get('issue_type')} {str(f.get('detail',''))[:60]}")
        ok, res = TS.transition(root, to, "revert", reason=f"failure recovery：{f.get('issue_type')}",
                                issue_id=iss["id"])
        return (0 if ok else 1), {"action": "ROLLBACK", "ok": ok, "to": to, "issue": iss["id"],
                                  "transition": res}
    if strategy == "human_review":
        return 1, {"action": "HUMAN_REVIEW",
                   "queue": ".aeromech/research/human-review-queue.yaml",
                   "note": "裁决由人类完成（approve/modify/reject），再 thesis_orchestrator apply-human；Agent 不代签"}
    # block
    return 1, {"action": "BLOCK", "reason": f"Critical 完整性问题：{f.get('issue_type')}",
               "detail": str(f.get("detail", ""))[:120]}


def _issue_category(issue_type):
    if issue_type in ("DATA_GAP", "CALCULATION_GAP", "QUANTITATIVE_INCONSISTENCY"):
        return "data"
    if issue_type in ("CONCLUSION_OVERREACH", "CLAIM_OVERSTRENGTH", "EVIDENCE_GAP", "CITATION_GAP"):
        return "citation" if issue_type in ("EVIDENCE_GAP", "CITATION_GAP") else "integrity"
    if issue_type in ("ORPHAN_FIGURE", "ORPHAN_TABLE"):
        return "figure"
    if issue_type in DESIGN_ROLLBACK:
        return "structure"
    return "structure"


# ---------------- 主循环 ----------------

def step(root):
    """执行一个 Action。返回 (rc, {action, detail, state_after})。"""
    try:
        problems, _v = drift_checks(root)
    except TS.StateError as e:
        return 3, {"action": "ERROR", "detail": f"state 不可读: {e}"}
    hard = [p for p in problems if p["disposition"] == "ERROR"]
    soft = [p for p in problems if p["disposition"] == "NEEDS_HUMAN_REVIEW"]
    if hard:
        log_action(root, (TS.load_state(root)[0].get("stage") or {}).get("current"),
                   "drift 硬错误", "drift_checks", {"problems": hard}, "BLOCK")
        return 3, {"action": "STATE_DRIFT", "detail": hard}
    r = SR.route(root)
    if r.get("status") == "ERROR":
        return 3, {"action": "ERROR", "detail": r.get("detail")}
    cur = r["current"]
    nx = r["next"]

    if r["blocked"]:
        # 完整诊断条目（含 disposition/auto 字段）是真源：loop open_findings 缺这些字段
        full = {x.get("diagnosis_id"): x for x in _read_diagnosis_findings(root)}
        loop_findings = (r["gates"].get("agent_loop") or {}).get("open_findings") or []
        findings = []
        for lf in loop_findings:
            fid = lf.get("id")
            findings.append({**lf, **(full.get(fid) or {})})
        if not findings:
            findings = [x for x in full.values()
                        if x.get("severity", "").lower() in ("critical", "high")
                        or x.get("disposition") == "block"] or list(full.values())
        state = TS.load_state(root)[0]
        decisions = classify_recovery(root, findings, state)
        rc, rep = recovery(root, decisions, state)
        log_action(root, cur, r["block_reason"], {"findings": len(findings)},
                   rep, {"ROLLBACK": "ROLLBACK", "REPAIR": "REPAIR", "HUMAN_REVIEW": "NEEDS_HUMAN_REVIEW",
                         "BLOCK": "BLOCK", "retry": "RETRY", "none": "BLOCK"}.get(rep["action"], rep["action"]))
        return rc, {"action": rep["action"], "detail": rep, "recovery": decisions[:1]}

    if nx["action"] == "run_pending":
        ids = pending_ai_ids(root, cur)
        done = []
        if not ids and nx.get("run"):        # run_pending 但 gate 键不在映射（防御：兜底解析）
            ids = [x.split(":")[0] for x in nx["run"]]
        if ids:
            for aid in ids[:1]:              # 每步执行一个 pending，保持 Action 粒度
                res = execute_ai(root, aid)
                log_action(root, cur, f"run_pending:{aid}", {"ai": aid}, res,
                           "PASS" if res["ok"] else "ERROR")
                if not res["ok"]:
                    rc, rep = recovery(root, [("retry", {"issue_type": "TOOL_ERROR",
                                                         "detail": res["detail"]}, {})], TS.load_state(root)[0])
                    log_action(root, cur, "pending 工具失败→RETRY 上限1", {"ai": aid}, rep, "RETRY" if rep["action"] == "retry" else "BLOCK")
                    if rep["action"] == "retry":
                        res2 = execute_ai(root, aid)
                        log_action(root, cur, f"retry:{aid}", {"ai": aid}, res2, "PASS" if res2["ok"] else "ERROR")
                        if res2["ok"]:
                            TS.create_checkpoint(root, task=f"ai:{aid}", next_action="re-route")
                            return 0, {"action": "RUN_PENDING", "detail": {"done": [aid], "result": res2}}
                        return 1, {"action": "RETRY_EXHAUSTED", "detail": res2}
                    return 1, {"action": "RETRY_EXHAUSTED", "detail": res}
                done.append(aid)
            if done:
                TS.create_checkpoint(root, task=f"ai:{done[0]}",
                                     next_action="re-route")
                return 0, {"action": "RUN_PENDING", "detail": {"done": done, "result": res}}
        # 出口产物缺失（missing 非 run）：补齐属 Agent 职责（写作/登记），编排层不代做研究
        return 1, {"action": "NEEDS_UPSTREAM_WORK", "stage": cur, "detail": nx.get("missing") or nx.get("reason")}

    if nx["action"] == "advance":
        to = nx["to"]
        ok, res = TS.transition(root, to, "forward", reason=nx["reason"],
                                evidence=_stage_exit_evidence(root, cur))
        log_action(root, cur, f"advance→{to}", {"from": cur, "to": to}, res,
                   "PASS" if ok else "FAIL")
        if not ok:
            return 1, {"action": "ADVANCE_REJECTED", "detail": res}
        TS.create_checkpoint(root, task=f"stage:{cur}→{to}",
                             next_action=f"进入 {to}")
        return 0, {"action": "ADVANCE", "to": to}

    if nx["action"] == "revert":
        to = nx["to"]
        iss = TS.add_issue(root, severity="高", category="structure",
                           target_stage=to, desc=f"orchestrator：交付阻塞回退（{r['block_reason'][:80]}）")
        ok, res = TS.transition(root, to, "revert", reason=r["block_reason"], issue_id=iss["id"])
        TS.create_checkpoint(root, task=f"revert:{to}", next_action="修复后按返程规则前进")
        log_action(root, cur, "ROLLBACK(route)", {"to": to}, res, "ROLLBACK" if ok else "FAIL")
        return (0 if ok else 1), {"action": "ROLLBACK", "ok": ok, "to": to}

    # stay（末阶段或人工复核挂起）
    if soft:
        log_action(root, cur, "drift 软提示", None, {"problems": soft}, "NEEDS_HUMAN_REVIEW")
    gate = DG.aggregate(root)
    log_action(root, cur, "stay", {"gate": gate["status"]}, gate,
               gate["status"])
    return (0 if gate["status"] in ("PASS", "PASS_WITH_WARNINGS", "PASS_WITH_HUMAN_REVIEW") else 1), \
        {"action": "FINALIZE" if gate["status"] not in ("BLOCK", "ERROR") else "BLOCK",
         "gate": {"status": gate["status"],
                  "blocking": [x["gate_id"] for x in gate["items"]
                               if x["status"] in ("FAIL", "ERROR", "NEEDS_HUMAN_REVIEW")]},
         "soft_drift": soft}


def _stage_exit_evidence(root, stage):
    """出口产物路径记入 history evidence（相对 .aeromech 的产物清单，存在者）。"""
    out = []
    st = TS.load_state(root)[0]
    for e in SR.matrix().get(stage, {}).get("exit", []):
        pr = e["probe"]
        if pr.startswith("any_file:") or pr.startswith("any_artifact:"):
            rel = pr.split(":", 1)[1]
            out.append(f".aeromech/{rel}")
        elif "." in pr:
            base, _, _rest = pr.partition("==")
            val = SR._get_path(st, base) if base.split(".")[0] in ("research", "project", "writing") else None
            if val:
                out.append(str(val))
    return [x for x in out if x]


def _read_diagnosis_findings(root):
    p = os.path.join(root, ".aeromech", "artifacts", "analysis", "research-diagnosis.json")
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return [x for x in d.get("diagnoses", []) if x.get("status") == "open"]
    except (json.JSONDecodeError, OSError):
        return []


def drive(root, until=None, max_steps=DRIVE_DEFAULT_MAX):
    """多步驱动（有步数上限，防编排层无限循环；指令 §十一）。"""
    actions = []
    for i in range(max_steps):
        rc, res = step(root)
        actions.append(res)
        cur = TS.load_state(root)[0]["stage"].get("current")
        if res["action"] in ("BLOCK", "RETRY_EXHAUSTED", "STATE_DRIFT", "ADVANCE_REJECTED",
                             "HUMAN_REVIEW", "NEEDS_HUMAN_REVIEW"):
            return rc, actions, cur
        if until and cur == until and res["action"] in ("FINALIZE", "BLOCK"):
            return rc, actions, cur
        if res["action"] == "NEEDS_UPSTREAM_WORK":
            return 1, actions, cur
        if until and cur == until and res["action"] == "ADVANCE":
            return 0, actions, cur
        if res["action"] == "FINALIZE":
            return rc, actions, cur
    log_action(root, cur, "drive 步数上限", {"max_steps": max_steps},
               {"actions": len(actions)}, "NEEDS_HUMAN_REVIEW")
    return 1, actions + [{"action": "MAX_STEPS_EXCEEDED"}], cur


# ---------------- resume（指令 §六/§七/§十二/§十五） ----------------

def resume(root):
    state, ctx, r = None, None, None
    try:
        problems, v = drift_checks(root)
    except TS.StateError as e:
        log_action(root, None, "resume", None, {"error": str(e)}, "ERROR")
        return 3, {"status": "ERROR", "detail": f"state 不可读: {e}", "from_start": False}
    hard = [p for p in problems if p["disposition"] == "ERROR"]
    soft = [p for p in problems if p["disposition"] == "NEEDS_HUMAN_REVIEW"]
    if hard:
        log_action(root, v["stage"], "resume：硬 drift", None, {"problems": hard}, "ERROR")
        return 3, {"status": "ERROR", "drift": hard, "from_start": False}
    if soft:
        log_action(root, v["stage"], "resume：drift 需人工", None, {"problems": soft}, "NEEDS_HUMAN_REVIEW")
        return 1, {"status": "NEEDS_HUMAN_REVIEW", "drift": soft, "stage": v["stage"],
                   "note": "绝不静默继续：请人工确认差异后恢复"}
    r = SR.route(root)
    log_action(root, v["stage"], "resume：续点确认", {"checkpoint": v["checkpoint"]},
               {"next": r["next"], "artifacts_ok": len(v["artifacts_ok"])}, "PASS")
    return 0, {"status": "RESUMED", "stage": v["stage"], "checkpoint": v["checkpoint"],
               "next": r["next"], "artifacts_ok": v["artifacts_ok"],
               "qa_state": v.get("qa_state") or {},
               "cursor": v["cursor"], "next_action": v["next_action"], "from_start": False}


def apply_human(root):
    """人工裁决消费：复用 research_repair.apply_human（不新建第二套队列，指令 §十六）。"""
    if not RI.initialized(root):
        return 1, {"status": "NOT_APPLICABLE", "reason": "注册表未初始化"}
    res = RRP.apply_human(root)
    # 裁决后复跑诊断与环，恢复流程由后续 step/route 接管
    RDIA.save(root, RDIA.diagnose(root))
    return 0, {"status": "APPLIED", "result": res}


# ---------------- CLI ----------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Thesis Orchestrator（v1.6）")
    ap.add_argument("root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status"); st.add_argument("--json", action="store_true")
    sub.add_parser("step")
    d = sub.add_parser("drive"); d.add_argument("--until", default=None); d.add_argument("--max-steps", type=int, default=DRIVE_DEFAULT_MAX)
    sub.add_parser("resume")
    rl = sub.add_parser("run-loop"); rl.add_argument("--max-iterations", type=int, default=LOOP_MAX_ITER)
    sub.add_parser("apply-human")
    g = sub.add_parser("gate"); g.add_argument("--json", action="store_true")
    ac = sub.add_parser("actions"); ac.add_argument("--last", type=int, default=None)
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    if not os.path.isdir(os.path.join(root, ".aeromech")):
        print("未找到 .aeromech/（先 thesis_state.py init）")
        return 2
    if a.cmd == "status":
        try:
            state, ctx, r = load_all(root)
        except TS.StateError as e:
            print(f"ERROR: {e}"); return 3
        v = {"stage": (state.get("stage") or {}).get("current"),
             "route": r, "research_context": ctx["status"],
             "gate": DG.aggregate(root),
             "drift": [p["code"] for p in drift_checks(root)[0]]}
        if a.json:
            print(json.dumps(v, ensure_ascii=False, indent=1))
        else:
            print(f"阶段 {v['stage']} · route.next={r['next']['action']}→{r['next'].get('to') or '-'} · "
                  f"blocked={r['blocked']} · gate={v['gate']['status']} · drift={v['drift'] or '无'}")
        return 0
    if a.cmd == "step":
        rc, res = step(root)
        print(json.dumps(res, ensure_ascii=False, default=str))
        return rc
    if a.cmd == "drive":
        rc, acts, cur = drive(root, a.until, a.max_steps)
        print(f"drive 完成于 {cur}：{len(acts)} 步 · 终步={acts[-1]['action'] if acts else '-'}")
        return rc
    if a.cmd == "resume":
        rc, res = resume(root)
        print(json.dumps(res, ensure_ascii=False, default=str))
        return rc
    if a.cmd == "run-loop":
        res = AL.run_loop(root, max_iterations=max(1, min(a.max_iterations, 20)))
        status = res["status"]
        findings = res.get("open_findings") or []
        state = TS.load_state(root)[0]
        decisions = classify_recovery(root, findings, state)
        rc, rep = (recovery(root, decisions, state) if status == "BLOCK" else (0, {"action": "NONE"}))
        log_action(root, (state.get("stage") or {}).get("current"), "run-loop",
                   {"max_iterations": a.max_iterations},
                   {"loop_status": status, "recovery": rep},
                   {"PASS": "PASS", "PASS_WITH_WARNINGS": "PASS_WITH_WARNINGS",
                    "PASS_WITH_HUMAN_REVIEW": "NEEDS_HUMAN_REVIEW", "BLOCK": "BLOCK",
                    "WARN": "WARN", "not_initialized": "NOT_APPLICABLE"}.get(status, status))
        if status != "BLOCK":
            TS.create_checkpoint(root, task="agent-loop",
                                 cursor={"loop_status": status, "iterations": len(res.get("iterations", []))},
                                 next_action="交付门禁" if status.startswith("PASS") else "复核队列")
        print(json.dumps({"loop": {"status": status, "stopped_reason": res.get("stopped_reason"),
                                   "iterations": len(res.get("iterations", []))},
                          "recovery": rep}, ensure_ascii=False, default=str))
        return rc
    if a.cmd == "apply-human":
        rc, res = apply_human(root)
        print(json.dumps(res, ensure_ascii=False, default=str))
        return rc
    if a.cmd == "gate":
        d = DG.aggregate(root, write=True)
        print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else f"Delivery Gate: {d['status']}")
        return 0 if d["status"] in ("PASS", "PASS_WITH_WARNINGS", "PASS_WITH_HUMAN_REVIEW") else 1
    if a.cmd == "actions":
        for rec in read_actions(root, a.last):
            print(json.dumps(rec, ensure_ascii=False))
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main())
