# -*- coding: utf-8 -*-
"""test_auto_repair.py — Auto Repair Policy 与执行（v1.5 §11）

白名单动作可自动执行并复检；白名单之外一律人工（禁止捏造数据/文献、改核心方法、把模拟改真实）。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_auto_repair.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
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


def read(root, name):
    return open(os.path.join(root, ".aeromech", "artifacts", "chapters", name), encoding="utf-8").read()


def plan_and_exec(root):
    ids = RP.plan(root, DIA.diagnose(root)["diagnoses"])
    return ids, RP.execute(root, ids=ids)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_auto_")
    print("== test_auto_repair ==")

    # ---------- positive：论断降级（白名单第 1 项） ----------
    root = F.write_project(os.path.join(tmp, "claim"), variant="claim_overstrength")
    ids, (done, failed) = plan_and_exec(root)
    check("positive claim 降级执行成功", bool(done) and not failed, str(done)[:120])
    cl = next(x for x in RI.load_registry(root, "claims") if x["id"] == "CL-002")
    check("positive 注册表强断言已消除", "必然" not in cl["claim"], cl["claim"])
    check("positive 正文同步更新", "必然导致制动失效" not in read(root, "ch3-fault-modes.md"))
    check("positive 复检通过", next(x for x in RI.load_registry(root, "repairs")
                                  if x["id"] == ids[0])["status"] == "verified")

    # ---------- positive：摘要数字同步（白名单第 2 项） ----------
    root2 = F.write_project(os.path.join(tmp, "num"), variant="number_mismatch")
    front_before = read(root2, "front-abstract.md")
    ids2, (done2, _) = plan_and_exec(root2)
    front_after = read(root2, "front-abstract.md")
    check("positive 摘要数字同步执行", bool(done2), str(done2)[:120])
    check("positive 摘要 176→180", "176" not in front_after and "180" in front_after)
    check("positive 仅改动数值所在文件",
          front_after != front_before and "8 类" in front_after, "其余内容保持")
    check("positive 复检后 QUANTITATIVE_INCONSISTENCY 消失",
          "QUANTITATIVE_INCONSISTENCY" not in [d["issue_type"] for d in DIA.diagnose(root2)["diagnoses"]])

    # ---------- positive：计算重执行（白名单第 3 项） ----------
    root3 = F.write_project(os.path.join(tmp, "calc"), variant="calc_gap_recompute")
    ids3, (done3, _) = plan_and_exec(root3)
    calc = next(x for x in RI.load_registry(root3, "computations") if x["id"] == "CALC-001")
    check("positive recompute 执行", bool(done3), str(done3)[:120])
    check("positive 计算标记 verified", calc.get("verified") is True)
    check("positive 重算输出回填", "180" in str(calc.get("output", "")), str(calc.get("output"))[:60])
    check("positive verification 记录命令依据", "recompute" in str(calc.get("verification", "")))

    # ---------- positive：模拟标签回填（白名单第 4 项） ----------
    root4 = F.write_project(os.path.join(tmp, "label"))
    ds = RI.load_registry(root4, "datasets")
    ds[0]["label"] = ""
    RI.save_registry(root4, "datasets", ds)
    diag_lab = [{"diagnosis_id": "DIAG-LAB01", "issue_type": "DATA_GAP", "severity": "medium",
                 "affected_nodes": ["DS-001"], "detail": "模拟数据集缺少标识", "auto_repairable": True,
                 "recommended_repair": {"repair_type": "REVISE_CLAIM", "operation": "fix_synth_label",
                                        "payload": {"datasets": ["DS-001"]}}}]
    ids4 = RP.plan(root4, diag_lab)
    done4, failed4 = RP.execute(root4, ids=ids4)
    ds_after = next(x for x in RI.load_registry(root4, "datasets") if x["id"] == "DS-001")
    check("positive fix_synth_label 回填规定标签",
          ds_after.get("label") == RI.SYNTH_LABEL, str(ds_after.get("label"))[:60])
    check("positive 回填不改变数据类型（仍为 simulated）",
          str(ds_after.get("type")) in ("simulated", "assumption", "public", "user_provided"),
          str(ds_after.get("type")))

    # ---------- negative：禁止把模拟数据改成真实数据 ----------
    before_type = str(next(x for x in RI.load_registry(root4, "datasets")
                           if x["id"] == "DS-001").get("type"))
    ids_x = RP.plan(root4, [{"diagnosis_id": "DIAG-X1", "issue_type": "DATA_GAP", "severity": "high",
                             "affected_nodes": ["DS-001"], "detail": "希望改为真实数据",
                             "auto_repairable": True,
                             "recommended_repair": {"repair_type": "ADD_EVIDENCE",
                                                    "operation": "promote_to_real",
                                                    "payload": {"datasets": ["DS-001"]}}}])
    check("negative 升级模拟为真实不被建单", ids_x == [], str(ids_x))
    after_type = str(next(x for x in RI.load_registry(root4, "datasets")
                          if x["id"] == "DS-001").get("type"))
    check("negative 数据类型未被改动", before_type == after_type, f"{before_type} → {after_type}")

    # ---------- negative（B7 回归）：recompute 受控执行模型 —— 白名单外的命令形态一律拒执 ----------
    root9 = F.write_project(os.path.join(tmp, "recomp_ctl"), variant="calc_gap_recompute")
    evil_cmds = [
        ("任意代码入口", "python -c print(1)"),
        ("非 python 解释器", "calc.exe"),
        ("越界相对路径", "python ../outside.py"),
        ("绝对路径", "python C:/Windows/System32/calc.py"),
        ("shell 元字符注入", "python a.py && del b.py"),
        ("项目内不存在的脚本", "python no_such_script.py"),
    ]
    for i, (name, cmd) in enumerate(evil_cmds):
        ids_e = RP.plan(root9, [{"diagnosis_id": f"DIAG-EV{i}", "issue_type": "CALCULATION_GAP",
                                 "severity": "high", "affected_nodes": ["CALC-001"],
                                 "detail": "重算", "auto_repairable": True,
                                 "recommended_repair": {"repair_type": "RECALCULATE",
                                                        "operation": "recompute",
                                                        "payload": {"calc_id": "CALC-001",
                                                                    "recompute": {"cmd": cmd}}}}])
        done_e, failed_e = RP.execute(root9, ids=ids_e)
        check(f"negative recompute 拒绝「{name}」", not done_e and bool(failed_e),
              cmd[:26])
    check("negative 危险命令全部未把计算伪标 verified",
          next(x for x in RI.load_registry(root9, "computations")
               if x["id"] == "CALC-001").get("verified") is not True)
    ids_ok = RP.plan(root9, [{"diagnosis_id": "DIAG-EVOK", "issue_type": "CALCULATION_GAP",
                              "severity": "high", "affected_nodes": ["CALC-001"],
                              "detail": "重算", "auto_repairable": True,
                              "recommended_repair": {"repair_type": "RECALCULATE",
                                                     "operation": "recompute",
                                                     "payload": {"calc_id": "CALC-001", "recompute": {
                                                         "cmd": "python .aeromech/transcripts/recompute_calc001.py"}}}}])
    done_ok, failed_ok = RP.execute(root9, ids=ids_ok)
    calc_ok = next(x for x in RI.load_registry(root9, "computations") if x["id"] == "CALC-001")
    check("negative 对照组：受控命令（项目内 .py）仍可执行并通过复检",
          bool(done_ok) and not failed_ok and calc_ok.get("verified") is True,
          str(done_ok)[:100])

    # ---------- negative：非白名单 operation 即使被标 auto 也不执行 ----------
    root5 = F.write_project(os.path.join(tmp, "forbid"))
    RI.add_entry(root5, "repairs", {
        "diagnosis_id": "DIAG-FB1", "target_nodes": ["E-999"], "repair_type": "ADD_EVIDENCE",
        "operation": "fabricate_evidence", "before": {"text": ""}, "after": None, "payload": {},
        "rationale": "越权尝试", "expected_effect": "-", "risk": "-", "auto": True,
        "status": "proposed", "timestamp": "2026-09-12T00:00:00"})
    n_ev = len(RI.load_registry(root5, "evidence") or [])
    done5, failed5 = RP.execute(root5)
    check("negative 越权 operation 不执行", done5 == [] and failed5 == [], f"{done5} {failed5}")
    check("negative 未新增任何证据条目", len(RI.load_registry(root5, "evidence") or []) == n_ev)
    check("negative 越权条目保持 proposed（不伪报已修）",
          next(x for x in RI.load_registry(root5, "repairs")
               if x["operation"] == "fabricate_evidence")["status"] == "proposed")

    # ---------- boundary：dry-run 不改动任何文件 ----------
    root6 = F.write_project(os.path.join(tmp, "dry"), variant="claim_overstrength")
    snap = {f: read(root6, f) for f in os.listdir(os.path.join(root6, ".aeromech", "artifacts", "chapters"))}
    ids6 = RP.plan(root6, DIA.diagnose(root6)["diagnoses"])
    done6, _ = RP.execute(root6, ids=ids6, dry_run=True)
    check("boundary dry-run 报告将执行", bool(done6))
    check("boundary dry-run 未改动章节",
          all(read(root6, f) == t for f, t in snap.items()))
    check("boundary dry-run 条目仍为 proposed",
          all(x["status"] == "proposed" for x in RI.load_registry(root6, "repairs")))

    # ---------- boundary：数字替换不得误伤相邻数值 ----------
    root7 = F.write_project(os.path.join(tmp, "edge"))
    ab = os.path.join(root7, ".aeromech", "artifacts", "chapters", "front-abstract.md")
    s = read(root7, "front-abstract.md")
    open(ab, "w", encoding="utf-8").write(s + "\n对照值 1176 与 176.5 保持不变，目标 176。\n")
    rid = RI.add_entry(root7, "repairs", {
        "diagnosis_id": "DIAG-ED01", "target_nodes": ["ABSTRACT"], "repair_type": "REVISE_ABSTRACT",
        "operation": "number_sync", "before": {"text": "176"}, "after": None,
        "payload": {"old": "176", "new": "180"}, "rationale": "边界", "expected_effect": "-",
        "risk": "-", "auto": True, "status": "proposed", "timestamp": "2026-09-12T00:00:00"})
    done7, failed7 = RP.execute(root7, ids=[rid])
    txt = read(root7, "front-abstract.md")
    check("boundary 独立数值被同步", "目标 180" in txt, str(done7 + failed7)[:120])
    check("boundary 相邻数值 1176 / 176.5 未被误改", "1176" in txt and "176.5" in txt)

    # ---------- repair：复检不通过时不得记为 verified ----------
    root8 = F.write_project(os.path.join(tmp, "verify"))
    rid8 = RI.add_entry(root8, "repairs", {
        "diagnosis_id": "DIAG-VP01", "target_nodes": ["CL-002"], "repair_type": "REVISE_CLAIM",
        "operation": "downgrade_wording", "before": {"text": "…"}, "after": None,
        "payload": {"claim_id": "CL-009"}, "rationale": "目标不存在", "expected_effect": "-",
        "risk": "-", "auto": True, "status": "proposed", "timestamp": "2026-09-12T00:00:00"})
    done8, failed8 = RP.execute(root8, ids=[rid8])
    rep8 = next(x for x in RI.load_registry(root8, "repairs") if x["id"] == rid8)
    check("repair 目标缺失时执行判失败", done8 == [] and bool(failed8), str(failed8)[:120])
    check("repair 失败条目状态为 rejected（不伪报 verified）",
          rep8["status"] == "rejected", rep8["status"])

    print(f"test_auto_repair 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
