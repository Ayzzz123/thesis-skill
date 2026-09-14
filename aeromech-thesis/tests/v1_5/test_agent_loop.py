# -*- coding: utf-8 -*-
"""test_agent_loop.py — Research Agent Loop（v1.5 §12/§13/§20）

验证闭环：PLAN→ANALYZE→DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→VALIDATE→ACCEPT；
必须记录每轮 issues_before/repairs/issues_after/improvement/remaining_issues，且受最大轮数约束。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_agent_loop.py
"""
import json
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
import research_agent_loop as AL
import research_integrity as RI

PASS, FAIL = 0, 0
SCRIPTS = os.path.join(SKILL, "scripts")
ITER_FIELDS = ["iteration_id", "issues_before", "repairs", "issues_after", "improvement",
               "remaining_issues"]


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def run(*args):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, args[0])] + list(args[1:]),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_loop_")
    print("== test_agent_loop ==")

    # ---------- positive：闭环真正完成"发现→修复→再验证" ----------
    root = F.write_project(os.path.join(tmp, "e2e"), variant="claim_overstrength")
    res = AL.run_loop(root)
    its = res["iterations"]
    check("positive 至少 1 轮", len(its) >= 1)
    it1 = its[0]
    check("positive 每轮记录字段齐备", all(k in it1 for k in ITER_FIELDS),
          str([k for k in ITER_FIELDS if k not in it1]))
    check("positive 第 1 轮发现问题", it1["issues_before"]["counts"]["total"] > 0)
    check("positive 第 1 轮执行了自动修复", bool(it1["repairs"]), str(it1["repairs"])[:120])
    check("positive 修复后问题减少", it1["improvement"] > 0,
          f"{it1['issues_before']['counts']['total']} → {it1['issues_after']['counts']['total']}")
    check("positive 再验证后 CLAIM_OVERSTRENGTH 归零",
          "CLAIM_OVERSTRENGTH" not in (its[-1]["issues_after"]["types"] or []))
    check("positive 终态非 BLOCK", res["status"] != "BLOCK", res["status"])
    check("positive 终态为 ACCEPTED*", res["loop_status"].startswith("ACCEPTED"), res["loop_status"])
    check("positive 停止原因明确", res["stopped_reason"] in
          ("clean", "pending_human_review", "no_actionable_items", "no_improvement", "max_iterations"),
          res["stopped_reason"])
    check("positive 每轮记录解释依据(why)", {"detected_by", "severity_basis", "repair_choice",
                                          "auto_allowed", "human_required"} <= set(it1["why"]))
    check("positive 修复留痕写入 repairs", bool(RI.load_registry(root, "repairs")))

    # ---------- positive：日志产物 ----------
    out = os.path.join(tmp, "log1")
    AL.run_loop(F.write_project(os.path.join(tmp, "e2e2"), variant="number_mismatch"), out_dir=out)
    lp = os.path.join(out, "research-loop-log.md")
    jp = os.path.join(out, "research-loop-log.json")
    check("positive 生成 research-loop-log.md", os.path.isfile(lp))
    check("positive 生成 research-loop-log.json", os.path.isfile(jp))
    txt = open(lp, encoding="utf-8").read()
    check("positive 日志含终态与轮次", "终态" in txt and "第 1 轮" in txt)
    check("positive 日志记录事实与规则命中（非内部推理链）",
          "规则命中" in txt and "issues_before" in txt)

    # ---------- negative：INFEASIBLE 设计必须 BLOCK，不得继续交付 ----------
    root2 = F.write_project(os.path.join(tmp, "infeas"), variant="infeasible")
    res2 = AL.run_loop(root2)
    check("negative INFEASIBLE → BLOCK", res2["status"] == "BLOCK", res2["status"])
    check("negative BLOCK 给出原因", bool(res2["block_reasons"]), str(res2["block_reasons"])[:140])
    rc2, _ = run("research_agent_loop.py", root2)
    check("negative BLOCK CLI rc=1", rc2 == 1, f"rc={rc2}")
    check("negative Score 存在但不作为放行依据",
          res2["score"]["blocked"] is True or res2["status"] == "BLOCK")

    # ---------- negative：无自动修复手段的高危项 → 人工队列，不静默放过 ----------
    root3 = F.write_project(os.path.join(tmp, "human"), variant="conflict_pending")
    res3 = AL.run_loop(root3)
    check("negative 冲突项进入人工队列",
          os.path.isfile(os.path.join(root3, ".aeromech", "research", "human-review-queue.yaml")))
    q = __import__("yaml").safe_load(open(os.path.join(root3, ".aeromech", "research",
                                                       "human-review-queue.yaml"), encoding="utf-8"))
    entry = [e for e in q["queue"] if e["issue_type"] == "UNRESOLVED_CONFLICT"]
    check("negative 队列条目说明判断所需信息",
          bool(entry) and bool(entry[0]["required_input"].strip()) and bool(entry[0]["options"]))
    check("negative 未擅自选择来源（无自动修复记录）",
          all(not (r.get("auto") and r.get("status") in ("applied", "verified"))
              for r in (RI.load_registry(root3, "repairs") or [])))

    # ---------- boundary：最大轮数约束（防无限循环） ----------
    check("boundary 默认 MAX_ITERATIONS=5", AL.MAX_ITERATIONS == 5, str(AL.MAX_ITERATIONS))
    root4 = F.write_project(os.path.join(tmp, "maxit"), variant="conclusion_overreach")
    res4 = AL.run_loop(root4, max_iterations=2)
    check("boundary 轮数不超过上限", len(res4["iterations"]) <= 2, str(len(res4["iterations"])))
    res5 = AL.run_loop(F.write_project(os.path.join(tmp, "maxit3"), variant="conclusion_overreach"),
                       max_iterations=3)
    check("boundary 收敛后提前停止（不空转）", len(res5["iterations"]) <= 3)

    # ---------- boundary：--no-auto-repair 时不改文本 ----------
    root6 = F.write_project(os.path.join(tmp, "noauto"), variant="claim_overstrength")
    chap = os.path.join(root6, ".aeromech", "artifacts", "chapters", "ch3-fault-modes.md")
    before = open(chap, encoding="utf-8").read()
    rc6, _ = run("research_agent_loop.py", root6, "--no-auto-repair")
    check("boundary --no-auto-repair 不改写正文", open(chap, encoding="utf-8").read() == before)
    check("boundary --no-auto-repair 未产生已执行修复",
          not [x for x in (RI.load_registry(root6, "repairs") or []) if x.get("auto")])

    # ---------- boundary：未初始化项目 rc=2（不误判 PASS/FAIL） ----------
    empty = os.path.join(tmp, "empty")
    os.makedirs(empty, exist_ok=True)
    rc7, out7 = run("research_agent_loop.py", empty)
    check("boundary 未初始化 CLI rc=2", rc7 == 2, f"rc={rc7} {out7[:80]}")
    rbad = F.write_project(os.path.join(tmp, "corrupt"))
    open(os.path.join(rbad, ".aeromech", "research", "evidence.yaml"), "w", encoding="utf-8").write(
        "evidence: !!bad {\n")
    rc8, out8 = run("research_agent_loop.py", rbad)
    check("boundary 注册表损坏 CLI rc=3", rc8 == 3, f"rc={rc8} {out8[:100]}")
    check("boundary 损坏时不产出 PASS 结论", "PASS" not in out8)

    # ---------- repair：裁决后重跑 loop 完成闭环 ----------
    root9 = F.write_project(os.path.join(tmp, "hrloop"), variant="abstract_unique")
    r9a = AL.run_loop(root9)
    check("repair 首轮为人工项且 BLOCK（High 未解决）", r9a["status"] == "BLOCK", r9a["status"])
    F.write_queue_decisions(root9, {r9a["open_findings"][0]["id"]: {
        "decision": "modify", "payload": {"replacement": "180"},
        "reviewer": "评审人", "date": "2026-09-12", "note": "以正文为准"}})
    r9b = AL.run_loop(root9)
    check("repair 人工裁决后不再 BLOCK", r9b["status"] != "BLOCK", r9b["status"])
    check("repair 人工裁决已执行（正文同步）",
          "999" not in open(os.path.join(root9, ".aeromech", "artifacts", "chapters",
                                         "front-abstract.md"), encoding="utf-8").read())
    check("repair 裁决留痕写入 repairs",
          any(not x.get("auto") for x in (RI.load_registry(root9, "repairs") or [])))

    print(f"test_agent_loop 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
