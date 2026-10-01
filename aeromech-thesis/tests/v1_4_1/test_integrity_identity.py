# -*- coding: utf-8 -*-
"""test_integrity_identity.py — 第二轮修复回归锁（A4a / A4b / A4c）

背景（全面审查 2026-10-01 发现的三条研究诚信绕过通道）：

  A4a  自动修复只改**注册表副本**、不改论文正文，却标 `verified`；复检也读注册表
       → 正文里的"实测/证明/显著"原样保留，门禁却转 PASS（"看起来修好、实际没修"）。
  A4b  `human-review-queue.yaml` 的 approve/modify 可**任意覆写注册表字段**
       （含 datasets.type / evidence.source_type / verification_status）→ 人工复核
       成为"把模拟洗成实测"的通道。
  A4c  `simulated_only = all(数据集均为模拟)` 是全篇模拟身份检测的**唯一总开关**——
       加一个无关的 type=public 数据集即整体关闭 RQG-09b/RQG-10 的 Critical 检查；
       且 `coverage()` 把非 simulated 数据集一律记为 verified。

本测试锁定"修好之后不得退化"，全部走真实函数调用（不 mock 业务逻辑）。
运行：python tests/v1_4_1/test_integrity_identity.py
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "v1_4"))
import research_integrity as RI
import research_quality_qa as RQ
import research_repair as RP
import yaml

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def _root(tmp, name):
    r = os.path.join(tmp, name)
    os.makedirs(os.path.join(r, ".aeromech", "research"), exist_ok=True)
    os.makedirs(os.path.join(r, ".aeromech", "artifacts", "chapters"), exist_ok=True)
    RI.init_registries(r) if hasattr(RI, "init_registries") else None
    return r


def _chapter(root, name, text):
    p = os.path.join(root, ".aeromech", "artifacts", "chapters", name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.relpath(p, root).replace("\\", "/")


def _front(root, text):
    p = os.path.join(root, ".aeromech", "artifacts", "front.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.relpath(p, root).replace("\\", "/")


def main():
    tmp = tempfile.mkdtemp(prefix="a4_")
    print("== test_integrity_identity ==")

    # ================= A4a：仅改注册表不得 verified =================
    r1 = _root(tmp, "a4a")
    strong = "本文通过试验表明该部件寿命显著提升，证明了维修策略有效。"
    _chapter(r1, "ch3.md", strong)
    RI.save_registry(r1, "claims", [{"id": "CL-001", "claim": strong,
                                     "claim_type": "fact", "evidence_ids": ["E-001"]}])
    RI.save_registry(r1, "evidence", [{"id": "E-001", "source_type": "simulation",
                                       "verification_status": "simulated"}])
    # 正文与注册表**不一致**：注册表条目被改成正文里不存在的文本 → 替换必然 miss
    rep_only_reg = {
        "diagnosis_id": "D-TEST-1", "operation": "downgrade_wording",
        "target_nodes": ["CL-001"],
        "payload": {"claim_id": "CL-001"},
        "before": {"text": "注册表里的另一段文本（正文中不存在）"},
        "after": None, "auto": True, "status": "proposed",
    }
    RI.add_entry(r1, "repairs", rep_only_reg)
    RI.save_registry(r1, "claims", [{"id": "CL-001",
                                     "claim": "注册表里的另一段文本（正文中不存在）",
                                     "claim_type": "fact"}])
    done, failed = RP.execute(r1)
    reps = RI.load_registry(r1, "repairs") or []
    rep1 = next((x for x in reps if x.get("diagnosis_id") == "D-TEST-1"), None)
    check("A4a-01 正文未发生替换时 REP 不得为 verified",
          rep1 and rep1.get("status") != "verified",
          str(rep1 and rep1.get("status")))
    check("A4a-02 复检消息点名 text_changes 为空（可诊断）",
          rep1 and "正文未发生" in str(rep1.get("verification", "")),
          str(rep1 and rep1.get("verification", ""))[:70])
    body1 = open(os.path.join(r1, ".aeromech", "artifacts", "chapters", "ch3.md"),
                 encoding="utf-8").read()
    check("A4a-03 正文原样保留（没有任何静默改写）", body1 == strong, body1[:40])

    # 正文**确实**被改到时，允许进入 verified
    # 用 DOWNGRADE_MAP 可完整覆盖的表述（"试验结果表明" → "模拟结果显示"），
    # 使降级后正文不再命中任何强断言词，复检得以通过。
    r2 = _root(tmp, "a4a-ok")
    strong2 = "本文通过试验结果表明该部件寿命提升。"
    RI.save_registry(r2, "claims", [{"id": "CL-001", "claim": strong2,
                                     "claim_type": "fact"}])
    _chapter(r2, "ch3.md", strong2)
    RI.add_entry(r2, "repairs", {
        "diagnosis_id": "D-TEST-2", "operation": "downgrade_wording",
        "target_nodes": ["CL-001"], "payload": {"claim_id": "CL-001"},
        "before": {"text": strong2}, "after": None, "auto": True, "status": "proposed"})
    RP.execute(r2)
    rep2 = next((x for x in (RI.load_registry(r2, "repairs") or [])
                 if x.get("diagnosis_id") == "D-TEST-2"), None)
    body2 = open(os.path.join(r2, ".aeromech", "artifacts", "chapters", "ch3.md"),
                 encoding="utf-8").read()
    check("A4a-04 正文真被替换 → REP 可为 verified",
          rep2 and rep2.get("status") == "verified",
          f"{rep2 and rep2.get('status')} / {rep2 and rep2.get('verification', '')[:60]}")
    check("A4a-05 正文内容确实已降级（不再是原句）", body2 != strong2, body2[:60])

    # ================= A4b：身份字段禁经人工裁决改写 =================
    r3 = _root(tmp, "a4b")
    RI.save_registry(r3, "datasets", [{"id": "DS-001", "type": "simulated",
                                       "label": RI.SYNTH_LABEL,
                                       "reason": "演示构造", "source": "construct"}])
    qp = os.path.join(r3, ".aeromech", "research", "human-review-queue.yaml")
    with open(qp, "w", encoding="utf-8") as f:
        yaml.safe_dump({"queue": [{
            "diagnosis_id": "D-IDENT-1", "issue_type": "EVIDENCE_GAP",
            "decision": "approve", "reviewer": "someone", "date": "2026-10-01",
            "payload": {"registry": "datasets", "id": "DS-001",
                        "values": {"type": "real", "label": ""}},
        }]}, f, allow_unicode=True)
    res3 = RP.apply_human(r3)
    ds3 = (RI.load_registry(r3, "datasets") or [{}])[0]
    check("A4b-01 身份字段 type 未被改写（仍为 simulated）",
          str(ds3.get("type")) == "simulated", str(ds3.get("type")))
    check("A4b-02 身份字段 label 未被清空",
          RI.SYNTH_LABEL in str(ds3.get("label", "")), str(ds3.get("label"))[:30])
    check("A4b-03 该条进入 needs_input（交人工走正规路径，不静默）",
          any("D-IDENT-1" in x for x in res3.get("needs_input", [])),
          str(res3.get("needs_input"))[:80])
    check("A4b-04 记入 blocked_identity 审计字段",
          any("D-IDENT-1" in x for x in res3.get("blocked_identity", [])),
          str(res3.get("blocked_identity"))[:80])

    # evidence 的身份字段同样受保护
    r4 = _root(tmp, "a4b-ev")
    RI.save_registry(r4, "evidence", [{"id": "E-001", "source_type": "simulation",
                                       "verification_status": "simulated"}])
    with open(os.path.join(r4, ".aeromech", "research", "human-review-queue.yaml"),
              "w", encoding="utf-8") as f:
        yaml.safe_dump({"queue": [{
            "diagnosis_id": "D-IDENT-2", "decision": "modify",
            "payload": {"registry": "evidence", "id": "E-001",
                        "values": {"source_type": "experiment",
                                   "verification_status": "verified"}},
        }]}, f, allow_unicode=True)
    RP.apply_human(r4)
    ev4 = (RI.load_registry(r4, "evidence") or [{}])[0]
    check("A4b-05 evidence.source_type 未被改写",
          str(ev4.get("source_type")) == "simulation", str(ev4.get("source_type")))
    check("A4b-06 evidence.verification_status 未被改写",
          str(ev4.get("verification_status")) == "simulated",
          str(ev4.get("verification_status")))

    # 非身份字段仍可正常人工修改（不得把整个通道堵死）
    r5 = _root(tmp, "a4b-ok")
    RI.save_registry(r5, "conflicts", [{"id": "CONFLICT-001", "conflict": "x",
                                        "status": "pending", "note": ""}])
    with open(os.path.join(r5, ".aeromech", "research", "human-review-queue.yaml"),
              "w", encoding="utf-8") as f:
        yaml.safe_dump({"queue": [{
            "diagnosis_id": "D-OK-1", "decision": "approve",
            "payload": {"registry": "conflicts", "id": "CONFLICT-001",
                        "values": {"note": "已与导师确认"}},
        }]}, f, allow_unicode=True)
    RP.apply_human(r5)
    cf5 = (RI.load_registry(r5, "conflicts") or [{}])[0]
    check("A4b-07 非身份字段仍允许人工修改（通道未被整体封死）",
          str(cf5.get("note")) == "已与导师确认", str(cf5.get("note")))

    # ================= A4c：混合数据不得关闭 simulated 检测 =================
    r6 = _root(tmp, "a4c")
    RI.save_registry(r6, "datasets", [
        {"id": "DS-001", "type": "simulated", "label": RI.SYNTH_LABEL,
         "reason": "构造", "source": "construct"},
        {"id": "DS-002", "type": "public", "source": "公开数据集"},
    ])
    RI.save_registry(r6, "claims", [{"id": "CL-001", "claim": "x",
                                     "claim_type": "fact", "evidence_ids": ["DS-001"]}])
    _front(r6, "本数据集来源于机队实测，试验表明寿命提升 30%。")
    _chapter(r6, "ch1.md", "本文通过试验表明该部件寿命显著提升，证明了策略有效。")
    RI.save_registry(r6, "conclusions", [{"id": "CON-001", "conclusion": "策略有效"}])
    sum6, rep6 = RQ.run(r6)
    st6 = {d["code"]: d["status"] for d in rep6.items}
    # 不变式：不得 PASS（FAIL 或 NEEDS_HUMAN_REVIEW 都是"未放行"，均可接受）。
    # 旧实现会因 public 数据集把 simulated_only 关掉 → 这两项直接 PASS。
    check("A4c-01 混合数据（simulated+public）时 RQG-09 不得 PASS",
          st6.get("RQG-09") in ("FAIL", "NEEDS_HUMAN_REVIEW"), str(st6.get("RQG-09")))
    check("A4c-02 RQG-10 同样不得因存在 public 而 PASS",
          st6.get("RQG-10") in ("FAIL", "NEEDS_HUMAN_REVIEW"), str(st6.get("RQG-10")))

    # 纯真实数据（无任何模拟/未定）时不得误报
    r7 = _root(tmp, "a4c-real")
    RI.save_registry(r7, "datasets", [
        {"id": "DS-001", "type": "real", "verification_status": "verified",
         "source": "实测台账"},
    ])
    RI.save_registry(r7, "claims", [{"id": "CL-001", "claim": "x",
                                     "claim_type": "fact", "evidence_ids": ["DS-001"]}])
    _front(r7, "本文基于实测数据开展分析，寿命提升 30%。")
    _chapter(r7, "ch1.md", "实测数据表明该部件寿命提升。")
    sum7, rep7 = RQ.run(r7)
    st7 = {d["code"]: d["status"] for d in rep7.items}
    check("A4c-03 纯真实数据不触发模拟身份 Critical（无误报）",
          st7.get("RQG-09") != "FAIL", str(st7.get("RQG-09")))

    # 身份未登记（缺 type）→ 按 unknown 处理，不得被当作真实而放行
    r8 = _root(tmp, "a4c-unknown")
    RI.save_registry(r8, "datasets", [{"id": "DS-001", "source": "?"}])
    RI.save_registry(r8, "claims", [{"id": "CL-001", "claim": "x",
                                     "claim_type": "fact", "evidence_ids": ["DS-001"]}])
    _front(r8, "本数据集来源于机队实测。")
    _chapter(r8, "ch1.md", "文本。")
    sum8, rep8 = RQ.run(r8)
    st8 = {d["code"]: d["status"] for d in rep8.items}
    check("A4c-04 身份未登记 + 实测措辞 → 不得 PASS",
          st8.get("RQG-09") in ("FAIL", "NEEDS_HUMAN_REVIEW"), str(st8.get("RQG-09")))

    # ================= A4c：coverage() 不得自动升级 =================
    r9 = _root(tmp, "a4c-cov")
    RI.save_registry(r9, "datasets", [
        {"id": "DS-001", "type": "public", "source": "公开"},
        {"id": "DS-002", "type": "real", "source": "台账"},
        {"id": "DS-003", "type": "simulated", "label": RI.SYNTH_LABEL,
         "reason": "构造", "source": "c"},
    ])
    RI.save_registry(r9, "claims", [
        {"id": "CL-001", "claim": "a", "claim_type": "fact", "evidence_ids": ["DS-001"]},
        {"id": "CL-002", "claim": "b", "claim_type": "fact", "evidence_ids": ["DS-002"]},
        {"id": "CL-003", "claim": "c", "claim_type": "fact", "evidence_ids": ["DS-003"]},
    ])
    cov9 = RI.coverage(r9)
    det9 = {d["claim"]: d["statuses"] for d in cov9.get("details", [])}
    # public 无核验状态 → pending：不得计入 covered（不得被当成 verified 证据）
    check("A4c-05 无 verification_status 的 public 数据集不得记为 verified",
          "CL-001" not in det9 and "CL-001" in cov9.get("uncovered", []),
          f"details={det9.get('CL-001')} uncovered={cov9.get('uncovered')}")
    check("A4c-06 real 数据集有来源时可记 verified（不误伤合法路径）",
          det9.get("CL-002") == ["verified"], str(det9.get("CL-002")))
    check("A4c-07 simulated 数据集仍记为 simulated（身份不被抹掉）",
          det9.get("CL-003") == ["simulated"], str(det9.get("CL-003")))

    # 未知身份（缺 type）→ pending，绝不自动 verified
    r9b = _root(tmp, "a4c-cov2")
    RI.save_registry(r9b, "datasets", [{"id": "DS-001", "source": "?"}])
    RI.save_registry(r9b, "claims", [{"id": "CL-001", "claim": "a",
                                      "claim_type": "fact", "evidence_ids": ["DS-001"]}])
    cov9b = RI.coverage(r9b)
    det9b = {d["claim"]: d["statuses"] for d in cov9b.get("details", [])}
    check("A4c-07b 身份未知的数据集不得自动 verified",
          "CL-001" not in det9b
          and "CL-001" in cov9b.get("uncovered", [])
          and cov9b.get("evidence_by_status", {}).get("verified", 0) == 0,
          f"uncovered={cov9b.get('uncovered')} by={cov9b.get('evidence_by_status')}")

    # ================= 缺失注册表不得降低要求 =================
    r10 = os.path.join(tmp, "a4-noreg")
    os.makedirs(os.path.join(r10, ".aeromech", "artifacts", "chapters"), exist_ok=True)
    _front(r10, "本文基于机队实测数据。")
    _chapter(r10, "ch1.md", "内容。")
    sum10, rep10 = RQ.run(r10)
    check("A4c-08 注册表缺失 → gate=not_initialized（不得记为 PASS）",
          sum10.get("gate") == "not_initialized", str(sum10.get("gate")))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_integrity_identity 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
