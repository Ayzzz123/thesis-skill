# -*- coding: utf-8 -*-
"""test_state_transition.py — StateIO 迁移校验（v1.6 Phase 1）

规则真源：references/state.md §3/§4/§5/§7/§9/§11。
覆盖：positive（合法前进/回退/返程）/ negative（非法边、缺前置、无触发源回退）/
boundary（milestone、override、schema 只读）/ recovery（损坏→备份→恢复）。
运行：python tests/v1_6/test_state_transition.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import thesis_state as TS

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def prep_for_s3(root):
    st, _ = TS.load_state(root)
    st["project"]["title"] = "题目X"
    st["research"]["topic_card_file"] = "artifacts/topic-card.md"
    TS.save_state(root, st)
    F.write_text(root, ".aeromech/artifacts/topic-card.md", "# card\n")


def main():
    tmp = tempfile.mkdtemp(prefix="ts_v16_")
    print("== test_state_transition ==")

    # ---------- positive ----------
    root = F.make_project(os.path.join(tmp, "pos"))
    prep_for_s3(root)
    ok, r = TS.transition(root, "S3", "forward", "题目已确定")
    check("positive S1→S3 前进", ok, str(r.get("reason", "")))
    st, _ = TS.load_state(root)
    check("positive current=S3", st["stage"]["current"] == "S3")
    check("positive history 追加 forward",
          st["stage"]["history"][-1]["type"] == "forward" and st["stage"]["history"][-1]["to"] == "S3")
    ok, _ = TS.transition(root, "S5", "forward", "方案齐备")
    check("positive S3→S5", ok)
    iss = TS.add_issue(root, severity="高", category="citation", target_stage="S4",
                       desc="文献缺口")
    check("positive issue id 自增", iss["id"] == "ISS-001" and iss["status"] == "open")
    ok, _ = TS.transition(root, "S4", "revert", "补文献", issue_id="ISS-001")
    check("positive S5→S4 回退（触发源齐备）", ok)
    TS.close_issue(root, "ISS-001")
    ok, _ = TS.transition(root, "S5", "forward", "文献补齐返程")
    check("positive 返程回原阶段", ok)
    st, _ = TS.load_state(root)
    check("positive 回退留 bak-revert 备份",
          any(".bak-revert-" in x for x in os.listdir(os.path.join(root, ".aeromech"))))

    # ---------- negative ----------
    root2 = F.make_project(os.path.join(tmp, "neg"))
    ok, r = TS.transition(root2, "S5", "forward", "跳步")
    check("negative S1→S5 非法边拒绝", not ok and "不在允许边" in r.get("reason", ""))
    st2, _ = TS.load_state(root2)
    check("negative 拒绝不落盘（current 不变）", st2["stage"]["current"] == "S1")
    check("negative 非法迁移不写 history",
          len(st2["stage"]["history"]) == 1)
    ok, r = TS.transition(root2, "S3", "forward", "缺题目")
    check("negative 边合法但前置缺失→拒绝并列出缺项",
          not ok and any("title" in m for m in r.get("missing", [])), str(r.get("missing")))
    prep_for_s3(root2)
    F.write_text(root2, ".aeromech/artifacts/research-plan.md", "# plan\n")
    st2, _ = TS.load_state(root2)
    st2["research"]["plan_file"] = "artifacts/research-plan.md"
    TS.save_state(root2, st2)
    TS.transition(root2, "S3", "forward", "ok")
    TS.transition(root2, "S5", "forward", "ok")
    ok, r = TS.transition(root2, "S3", "revert", "")
    check("negative 回退无触发源→拒绝", not ok and "触发源" in r.get("reason", ""))
    ok, r = TS.transition(root2, "S7", "override", "用户强推")
    check("negative override 无确认记录→拒绝", not ok and "override-note" in r.get("reason", ""))

    # ---------- boundary ----------
    ok, r = TS.transition(root2, "S7", "override", "用户一次要求方案+正文",
                          override_note="用户明确要求跨阶段推进")
    check("boundary override 带确认→放行且挂 open_issue", ok)
    stb, _ = TS.load_state(root2)
    ov = [i for i in stb["stage"]["open_issues"] if "强行推进" in i["desc"]]
    check("boundary override 自动挂问题（severity=高）", len(ov) == 1 and ov[0]["severity"] == "高")
    ok, r = TS.transition(root2, "S7", "milestone", "第3章完成")
    check("boundary milestone 不改 current", ok and r["type"] == "milestone"
          and TS.load_state(root2)[0]["stage"]["current"] == "S7")
    # 门禁证据：无 gate_evidence → S7 拒绝；有齐备证据 → 通过
    root3 = F.make_project(os.path.join(tmp, "gate"))
    prep_for_s3(root3)
    TS.transition(root3, "S3", "forward", "ok")
    TS.transition(root3, "S5", "forward", "ok")
    ok, r = TS.transition(root3, "S7", "forward", "开始写作")
    check("boundary S7 无门禁证据→拒绝", not ok)
    F.write_text(root3, ".aeromech/artifacts/analysis/fmea-table.md", "# 分析表\n")
    stg, _ = TS.load_state(root3)
    stg["writing"]["gate_evidence"] = {
        "plan_file": "artifacts/research-plan.md",
        "evidence_type": "data_or_analysis",
        "evidence_files": ["artifacts/analysis/fmea-table.md"],
        "gate_passed": "passed"}
    F.write_text(root3, ".aeromech/artifacts/research-plan.md", "# plan\n")
    TS.save_state(root3, stg)
    ok, r = TS.transition(root3, "S7", "forward", "证据齐备")
    check("boundary S7 门禁证据齐备→放行", ok, str(r.get("missing", "")))
    # conditional 但无 open_issues → failed
    stg2, _ = TS.load_state(root3)
    stg2["writing"]["gate_evidence"]["gate_passed"] = "conditional"
    stg2["stage"]["current"] = "S5"
    TS.save_state(root3, stg2)
    status, probs = TS.check_gate_evidence(stg2, root3)
    check("boundary conditional 缺 open_issues→不通过", status != "conditional" or probs)

    # ---------- recovery ----------
    root4 = F.make_project(os.path.join(tmp, "rec"))
    prep_for_s3(root4)
    TS.transition(root4, "S3", "forward", "ok")
    TS._backup(root4, "revert")
    open(os.path.join(root4, ".aeromech", "state.yaml"), "w", encoding="utf-8").write(
        "stage: {current: [broken\n  bad indent")
    st4, repaired = TS.load_state(root4)
    check("recovery 损坏→从最近备份恢复", st4["stage"]["current"] == "S3"
          and any("restored-from" in x for x in repaired), str(repaired))
    open(os.path.join(root4, ".aeromech", "state.yaml"), "w", encoding="utf-8").write(
        "stage: {current: [broken\n  bad indent")
    for bak in __import__("glob").glob(os.path.join(root4, ".aeromech", "state.yaml.bak-*")):
        os.remove(bak)
    try:
        TS.load_state(root4)
        check("recovery 损坏且无备份→StateError（不静默）", False)
    except TS.StateError:
        check("recovery 损坏且无备份→StateError（不静默）", True)
    # 高 schema 只读
    root5 = F.make_project(os.path.join(tmp, "hi"))
    sth, _ = TS.load_state(root5)
    sth["schema_version"] = "9.9"
    import yaml
    with open(os.path.join(root5, ".aeromech", "state.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(sth, f, allow_unicode=True)
    try:
        TS.load_state(root5)
        check("boundary schema 高版本→拒绝（只读保护）", False)
    except TS.StateError:
        check("boundary schema 高版本→拒绝（只读保护）", True)
    # 未知字段保留
    root6 = F.make_project(os.path.join(tmp, "unk"))
    with open(os.path.join(root6, ".aeromech", "state.yaml"), encoding="utf-8") as f:
        d = yaml.safe_load(f)
    d["my_future_field"] = {"keep": 1}
    with open(os.path.join(root6, ".aeromech", "state.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(d, f, allow_unicode=True)
    st6, _ = TS.load_state(root6)
    check("boundary 未识别字段原样保留（向前兼容）", st6.get("my_future_field") == {"keep": 1})
    # validate 词表
    bad = TS.validate_state({"schema_version": "1.0",
                             "stage": {"current": "S11", "history": [
                                 {"from": "S1", "to": "S2", "type": "teleport"}],
                                 "open_issues": [{"id": "ISS-001", "severity": "极高",
                                                  "category": "vibes", "status": "done"}]},
                             "project": {"paper_type": "essay"}})
    codes = {p["code"] for p in bad}
    check("boundary validate 捕获非法枚举",
          codes == {"ST-ENUM"} and len(bad) >= 6, f"{len(bad)} 项")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_state_transition 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
