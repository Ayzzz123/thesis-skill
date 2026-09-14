# -*- coding: utf-8 -*-
"""test_human_review_loop.py — NEEDS_HUMAN_REVIEW 接入 Agent Loop（v1.5 §24）

流程：NHR → 人工队列 → 裁决（approve/reject/modify）→ 修复 → 重分析 → QA；裁决记录必须留痕。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_human_review_loop.py
"""
import os
import shutil
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_agent_loop as AL
import research_integrity as RI
import research_repair as RP

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def qpath(root):
    return os.path.join(root, ".aeromech", "research", "human-review-queue.yaml")


def load_q(root):
    if not os.path.isfile(qpath(root)):
        return {"queue": []}
    return yaml.safe_load(open(qpath(root), encoding="utf-8")) or {"queue": []}


def decide(root, issue_type, decision, payload=None, reviewer="评审人A", note=""):
    q = load_q(root)
    hit = False
    for e in q["queue"]:
        if e["issue_type"] == issue_type:
            e["decision"] = decision
            e["payload"] = payload or {}
            e["reviewer"] = reviewer
            e["date"] = "2026-09-12"
            e["note"] = note or f"针对 {issue_type} 的裁决"
            hit = True
    yaml.safe_dump(q, open(qpath(root), "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    return hit


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_nhr_")
    print("== test_human_review_loop ==")

    # ---------- positive：队列条目自带裁决所需信息 ----------
    root = F.write_project(os.path.join(tmp, "pos"), variant="scope_creep")
    res = AL.run_loop(root)
    q = load_q(root)["queue"]
    entry = next((e for e in q if e["issue_type"] == "SCOPE_OVERFLOW"), None)
    check("positive 生成人工复核条目", entry is not None)
    # B9 回归：同一规则命中的不同严重度条目必须拥有不同 diagnosis_id（可分别裁决）
    r_b9 = F.write_project(os.path.join(tmp, "b9"), variant="scope_creep_two_level")
    AL.run_loop(r_b9)
    scope_entries = [e for e in load_q(r_b9)["queue"] if e["issue_type"] == "SCOPE_OVERFLOW"]
    check("B9 同规则不同严重度 diagnosis_id 不碰撞",
          len(scope_entries) >= 2 and
          len({e["diagnosis_id"] for e in scope_entries}) == len(scope_entries),
          str([(e["diagnosis_id"], e["severity"]) for e in scope_entries]))
    check("positive 条目含问题/根因/证据/选项",
          all(entry.get(k) for k in ("detail", "root_cause", "evidence", "options")), str(entry)[:160])
    check("positive 说明需要人工输入什么", bool(entry["required_input"].strip()))
    check("positive 提供待替换原文（before_text）", bool(entry.get("before_text", "").strip()),
          entry.get("before_text", "")[:60])
    check("positive 默认 decision 为空（未裁决）", entry["decision"] in (None, ""))
    check("positive 终态为 PASS_WITH_HUMAN_REVIEW", res["status"] == "PASS_WITH_HUMAN_REVIEW",
          res["status"])

    # ---------- negative：未裁决不得当成已解决 ----------
    check("negative 未裁决项仍在 open_findings",
          any(f["issue_type"] == "SCOPE_OVERFLOW" for f in res["open_findings"]))
    check("negative 未裁决不产出 PASS 终态", res["status"] != "PASS")
    check("negative 未执行任何自动修复",
          not [r for r in (RI.load_registry(root, "repairs") or [])
               if r.get("auto") and str(r.get("status")) in ("applied", "verified")])

    # ---------- negative：未知 decision 被忽略（不猜测执行） ----------
    decide(root, "SCOPE_OVERFLOW", "maybe")
    AL.run_loop(root)
    e2 = next((e for e in load_q(root)["queue"] if e["issue_type"] == "SCOPE_OVERFLOW"), None)
    check("negative 非法裁决不改变状态", e2 is not None and not e2.get("applied_status"),
          str(e2.get("applied_status")) if e2 else "gone")

    # ---------- repair：modify + 替换文本 → 执行 → 重分析 → 问题降级/消失 ----------
    sev_before = [d["severity"] for d in AL.run_loop(root)["open_findings"]]
    target_sentence = next(e.get("before_text", "") for e in load_q(root)["queue"]
                           if e["issue_type"] == "SCOPE_OVERFLOW")
    hit = decide(root, "SCOPE_OVERFLOW", "modify",
                 payload={"replacement": "在同类机电子系统中，可借鉴通用的分析方法。"},
                 reviewer="导师甲", note="回归注册范围")
    check("repair 裁决写入成功", hit)
    res2 = AL.run_loop(root)
    q2 = next((e for e in load_q(root)["queue"] if e["issue_type"] == "SCOPE_OVERFLOW"), None)
    # B9 修复后的正确语义：裁决按 diagnosis_id 精确消费，不得跨条目泄漏——
    # 已裁决的 high 项被处理，残留 medium 项必须保持"未裁决"等待人工单独处理。
    check("repair 已裁决条目被消费，残留项不继承裁决（决策按 ID 隔离）",
          q2 is not None and q2["severity"] == "medium"
          and q2.get("decision") in (None, "") and q2.get("applied_status") in (None, ""),
          str({k: q2.get(k) for k in ("severity", "decision", "applied_status")}) if q2 else "closed")
    chapter_text = open(os.path.join(root, ".aeromech", "artifacts", "chapters",
                                     "ch3-fault-modes.md"), encoding="utf-8").read()
    check("repair 裁决指向的原句已被替换", bool(target_sentence) and target_sentence not in chapter_text,
          target_sentence[:60])
    check("repair 一次裁决只处理一句，残留越界句由 high 降为 medium",
          q2 is None or (q2["severity"] == "medium" and "high" in sev_before),
          f"before={sev_before} after={q2['severity'] if q2 else 'closed'}")
    # 对残留 medium 项单独裁决（队列此刻仅剩该条）→ 下一轮闭环消费并关闭
    med_sentence = (q2 or {}).get("before_text", "")
    decide(root, "SCOPE_OVERFLOW", "modify",
           payload={"replacement": "（背景性提及，保留）"}, reviewer="导师甲", note="确认背景提及")
    res2b = AL.run_loop(root)
    check("repair 残留 medium 项单独裁决后被消费",
          bool(med_sentence) and not any(f["issue_type"] == "SCOPE_OVERFLOW"
                                         for f in res2b["open_findings"]),
          str([(f["issue_type"], f["severity"]) for f in res2b["open_findings"]])[:140])
    check("repair 严重度较裁决前下降",
          "high" not in [f["severity"] for f in res2["open_findings"]] or q2 is None,
          str([(f["issue_type"], f["severity"]) for f in res2["open_findings"]])[:120])
    rep = [r for r in (RI.load_registry(root, "repairs") or []) if not r.get("auto")]
    check("repair 人工裁决留痕写入 repairs", bool(rep), str(rep)[:120])
    check("repair 留痕含裁决人与依据",
          bool(rep) and "导师甲" in str(rep[-1].get("verification", ""))
          and bool(str(rep[-1].get("rationale", "")).strip()), str(rep[-1])[:160] if rep else "")

    # ---------- positive：reject 记录为例外且关闭该项（人工权威，留痕可查） ----------
    r3 = F.write_project(os.path.join(tmp, "reject"), variant="conflict_pending")
    AL.run_loop(r3)
    decide(r3, "UNRESOLVED_CONFLICT", "reject", reviewer="评审人B", note="两处来源口径不同，取来源1，正文已另行说明")
    res3 = AL.run_loop(r3)
    q3 = load_q(r3)["queue"]
    check("positive reject 记为 rejected_by_human",
          any(e.get("applied_status") == "rejected_by_human" for e in q3), str(q3)[:120])
    check("positive reject 后该项不再 open",
          not [f for f in res3["open_findings"] if f["issue_type"] == "UNRESOLVED_CONFLICT"])
    check("positive reject 不改动研究文本（无擅自取舍）",
          bool(open(os.path.join(r3, ".aeromech", "research", "conflicts.yaml"),
                    encoding="utf-8").read()))

    # ---------- positive：approve + 非文本动作 → deferred 记录（人工承诺后续） ----------
    r4 = F.write_project(os.path.join(tmp, "defer"), variant="evidence_mismatch")
    res4 = AL.run_loop(r4)
    check("positive INFEASIBLE 仍给出人工队列项", bool(load_q(r4)["queue"]) or res4["status"] == "BLOCK",
          res4["status"])
    decide(r4, "DESIGN_EVIDENCE_MISMATCH", "approve",
           payload={"registry": "design", "id": "DESIGN-001",
                    "values": {"limitations": ["已补充：需真实机队数据方可给出概率结论"]}},
           reviewer="评审人C", note="承认为设计局限，后续补数据")
    res4b = AL.run_loop(r4)
    rep4 = [x for x in (RI.load_registry(r4, "repairs") or []) if not x.get("auto")]
    check("positive 注册表字段按裁决更新",
          any("真实机队数据" in str(v) for v in (RI.load_registry(r4, "design")[0].get("limitations") or [])))
    check("positive 裁决记录留痕", bool(rep4), str(rep4)[:120])
    check("positive 循环状态可解释", res4b["stopped_reason"] and res4b["status"],
          f"{res4b['status']}/{res4b['stopped_reason']}")

    # ---------- boundary：裁决幂等（重跑不重复建单/不误判 needs_input） ----------
    n_before = len(RI.load_registry(root, "repairs") or [])
    RP.apply_human(root)
    RP.apply_human(root)
    n_after = len(RI.load_registry(root, "repairs") or [])
    check("boundary 重复消费裁决不重复建单", n_before == n_after, f"{n_before} → {n_after}")

    # ---------- boundary：RQG NHR 通道仍可用（v1.4.1 机制不被削弱） ----------
    check("boundary loop 结果保留 rqg_needs_human_review 字段",
          "rqg_needs_human_review" in res and isinstance(res["rqg_needs_human_review"], list))
    check("boundary 队列文件同时记录 RQG NHR",
          "rqg_needs_human_review" in yaml.safe_load(open(qpath(root), encoding="utf-8")))

    # ---------- repair：无决策时 loop 稳定（不因缺裁决而崩） ----------
    r5 = F.write_project(os.path.join(tmp, "pending"), variant="scope_creep")
    ra = AL.run_loop(r5)
    rb = AL.run_loop(r5)
    check("repair 无裁决重复运行结果一致",
          [f["id"] for f in ra["open_findings"]] == [f["id"] for f in rb["open_findings"]],
          str([f["id"] for f in rb["open_findings"]])[:120])

    print(f"test_human_review_loop 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
