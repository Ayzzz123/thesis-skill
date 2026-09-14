# -*- coding: utf-8 -*-
"""test_claim_strength.py — Claim Strength Model C1~C4 × ES1~ES4（v1.5 §7）

规则：Claim Strength ≤ Evidence Strength；弱证据 + 强断言 → CLAIM-OVERSTRENGTH 并建议降级；
禁止未经依据改变技术事实（降级只改措辞强度/口径，数值与术语保持）。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_claim_strength.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_design  # noqa: F401  （确保 scripts 路径优先生效）
import research_diagnosis as DIA
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


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_strength_")
    print("== test_claim_strength ==")

    # ---------- positive：强度分级本身 ----------
    check("positive C4 分级", DIA.claim_strength("该故障必然导致制动失效") == "C4")
    check("positive C3 分级（证明）", DIA.claim_strength("试验证明该规律成立") == "C3")
    check("positive C2 分级（表明）", DIA.claim_strength("结果表明风险最高") == "C2")
    check("positive C1 分级（可能）", DIA.claim_strength("该故障可能导致性能下降") == "C1")
    check("positive 无断言词返回 None", DIA.claim_strength("本节给出系统组成") is None)

    # ---------- positive：证据强度分级 ----------
    check("positive ES1（simulated）", DIA.evidence_strength(["simulated"]) == "ES1")
    check("positive ES1（pending）", DIA.evidence_strength(["pending", "simulated"]) == "ES1")
    check("positive ES2（partial）", DIA.evidence_strength(["partial"]) == "ES2")
    check("positive ES3（verified 文献类）",
          DIA.evidence_strength(["verified"], ["literature"]) == "ES3")
    check("positive ES4（verified 一手实验/计算）",
          DIA.evidence_strength(["verified"], ["experiment"]) == "ES4")
    check("positive 无证据返回 None", DIA.evidence_strength([]) is None)

    # ---------- positive：允许组合不判越界 ----------
    check("positive ES1 + C2 不越界", DIA.strength_violation("C2", "ES1")[0] is False)
    check("positive ES3 + C4 不越界", DIA.strength_violation("C4", "ES3")[0] is False)
    check("positive ES4 + C4 不越界", DIA.strength_violation("C4", "ES4")[0] is False)

    # ---------- negative：弱证据 + 强断言 → 越界 ----------
    bad, cap = DIA.strength_violation("C4", "ES1")
    check("negative ES1 + C4 越界且上限为 C2", bad is True and cap == "C2", f"{bad} {cap}")
    bad3, _ = DIA.strength_violation("C3", "ES1")
    check("negative ES1 + C3 越界", bad3 is True)
    bad2, _ = DIA.strength_violation("C4", "ES2")
    check("negative ES2 + C4 越界", bad2 is True)

    # ---------- negative：整项目集成（模拟证据 + 必然导致） ----------
    root = F.write_project(os.path.join(tmp, "neg-int"), variant="claim_overstrength")
    dg = DIA.diagnose(root)
    hits = [x for x in dg["diagnoses"] if x["issue_type"] == "CLAIM_OVERSTRENGTH"]
    check("negative 检测到 CLAIM_OVERSTRENGTH", bool(hits), str([x["issue_type"] for x in dg["diagnoses"]]))
    check("negative 目标定位到 CL-002", hits and hits[0]["affected_nodes"] == ["CL-002"])
    check("negative C4+ES1 判为 critical", hits and hits[0]["severity"] == "critical")
    check("negative 允许自动降级", hits and hits[0]["auto_repairable"] is True)
    check("negative 推荐动作为 downgrade_wording",
          hits and hits[0]["recommended_repair"]["operation"] == "downgrade_wording")

    # ---------- boundary：否定/免责式表述不算强断言 ----------
    check("boundary 否定式识别（不会必然导致）",
          DIA.is_negated("该故障不会必然导致制动失效") is True)
    check("boundary 否定式识别（不能证明）", DIA.is_negated("本研究不能证明该规律普适") is True)
    check("boundary 否定式识别（尚未证实）", DIA.is_negated("该机理尚未证实") is True)
    check("boundary 否定式识别（不足以说明）", DIA.is_negated("样本量不足以说明趋势") is True)
    check("boundary 肯定式不判否定（必然导致）", DIA.is_negated("该故障必然导致失效") is False)
    check("boundary 肯定式不判否定（证明）", DIA.is_negated("试验证明该规律成立") is False)
    check("boundary 无断言词句子 strength=None",
          DIA.claim_strength("该故障不会导致制动失效") is None)
    root_n = F.write_project(os.path.join(tmp, "bnd-neg"))
    cl = RI.load_registry(root_n, "claims")
    tgt = next(x for x in cl if x["id"] == "CL-002")
    tgt["claim"] = "刹车片过度磨损不会必然导致制动失效"
    tgt["evidence_ids"] = ["E-003"]
    RI.save_registry(root_n, "claims", cl)
    dg_n = DIA.diagnose(root_n)
    check("boundary 否定式不判越界",
          not any(x["issue_type"] == "CLAIM_OVERSTRENGTH" and x["affected_nodes"] == ["CL-002"]
                  for x in dg_n["diagnoses"]),
          str([x["issue_type"] for x in dg_n["diagnoses"]])[:140])

    # ---------- boundary：无证据引用时不凭空判级 ----------
    root_e = F.write_project(os.path.join(tmp, "bnd-noev"))
    cl = RI.load_registry(root_e, "claims")
    tgt = next(x for x in cl if x["id"] == "CL-002")
    tgt["claim"] = "该故障必然导致制动失效"
    tgt["evidence_ids"], tgt["analysis_ids"] = [], []
    RI.save_registry(root_e, "claims", cl)
    es_none = DIA.evidence_strength([])
    check("boundary 无证据时 ES=None（不臆断证据强度）", es_none is None)
    check("boundary ES=None 时不判越界（转由 RQG 缺证据规则处理）",
          DIA.strength_violation("C4", es_none)[0] is False)
    dg_e = DIA.diagnose(root_e)
    check("boundary 无证据的强断言仍被其它规则捕获",
          any(x["issue_type"] in ("CLAIM_OVERSTRENGTH", "CONCLUSION_OVERREACH", "TRACEABILITY_GAP",
                                  "EVIDENCE_GAP", "DATA_GAP") for x in dg_e["diagnoses"]),
          str([x["issue_type"] for x in dg_e["diagnoses"]])[:160])

    # ---------- repair：降级只改强度/口径，不改技术事实 ----------
    original = "刹车片过度磨损必然导致制动失效，该故障在机队中的发生率为 12%"
    downgraded = RP.downgrade_text(original)
    check("repair 强断言被降级", "必然" not in downgraded and "可能" in downgraded, downgraded)
    check("repair 技术事实保留（术语与数值不变）",
          "刹车片过度磨损" in downgraded and "制动失效" in downgraded and "12" in downgraded)
    check("repair 口径纠正（机队→模拟样本）", "机队" not in downgraded and "模拟样本" in downgraded)
    check("repair 降级后强度等级下降",
          DIA.CLAIM_RANK[DIA.claim_strength(downgraded)] < DIA.CLAIM_RANK["C4"],
          DIA.claim_strength(downgraded) or "-")

    # ---------- repair：执行后诊断消失且留下 verified 记录 ----------
    rc, done, failed = 0, [], []
    diags = DIA.diagnose(root)["diagnoses"]
    ids = RP.plan(root, diags)
    done, failed = RP.execute(root, ids=ids)
    check("repair 自动修复成功执行", bool(done) and not failed, str(done) + str(failed)[:160])
    rep = next(x for x in RI.load_registry(root, "repairs") if x["id"] == ids[0])
    check("repair REP 记录 status=verified", rep["status"] == "verified", rep.get("verification", ""))
    check("repair REP 保留 before/after 留痕",
          bool((rep.get("before") or {}).get("text")) and bool(rep.get("after")))
    after_types = [x["issue_type"] for x in DIA.diagnose(root)["diagnoses"]]
    check("repair 后 CLAIM_OVERSTRENGTH 消失", "CLAIM_OVERSTRENGTH" not in after_types, str(after_types)[:160])
    # 注册表与正文都要真正被改（不是只写日志）
    cl_after = next(x for x in RI.load_registry(root, "claims") if x["id"] == "CL-002")
    chap = open(os.path.join(root, ".aeromech", "artifacts", "chapters", "ch3-fault-modes.md"),
                encoding="utf-8").read()
    check("repair 注册表文本已更新", "必然" not in cl_after["claim"], cl_after["claim"])
    check("repair 正文章节文本已同步更新", "必然导致制动失效" not in chap)

    print(f"test_claim_strength 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
