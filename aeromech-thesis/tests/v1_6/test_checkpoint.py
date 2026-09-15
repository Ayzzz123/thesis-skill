# -*- coding: utf-8 -*-
"""test_checkpoint.py — Checkpoint 模型与 Resume 视图（v1.6 §六）

覆盖：positive（写/读/字段齐备/注册表快照）/ negative（产物丢失/变化检测）/
boundary（ID 唯一、损坏 checkpoint 不拖垮 resume、无 checkpoint 的旧项目）/
resume（S5 中断→恢复：阶段/游标/需重跑判定，不从 S1 重启）。
运行：python tests/v1_6/test_checkpoint.py
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


def main():
    tmp = tempfile.mkdtemp(prefix="ck_v16_")
    print("== test_checkpoint ==")

    # ---------- positive ----------
    root = F.make_project(os.path.join(tmp, "pos"))
    F.write_text(root, ".aeromech/artifacts/analysis/fmea.md", "# fmea\n")
    ck = TS.create_checkpoint(root, task="S5-analysis", cursor={"iter": "2", "chapter": "ch4"},
                              artifacts=[".aeromech/artifacts/analysis/fmea.md"],
                              qa_state={"tf_qa": {"status": "PASS", "report": "out/tf.md"}},
                              next_action="补齐 AN-002")
    need = {"checkpoint_id", "stage", "task", "ts", "cursor", "artifacts",
            "registries", "qa_state", "next_action"}
    check("positive 字段齐备（指令 §六 最小集）", need <= set(ck), str(need - set(ck)))
    check("positive ID 格式 CK-XXX", ck["checkpoint_id"] == "CK-001")
    check("positive artifact 记录 exists+sha256",
          ck["artifacts"][".aeromech/artifacts/analysis/fmea.md"]["exists"] is True
          and len(ck["artifacts"][".aeromech/artifacts/analysis/fmea.md"]["sha256"]) == 64)
    check("positive registries 快照含 13 注册表", len(ck["registries"]) >= 14)
    st, _ = TS.load_state(root)
    check("positive state.checkpoint 记录 last_id",
          st.get("checkpoint", {}).get("last_id") == "CK-001")
    ck2 = TS.create_checkpoint(root, task="x")
    check("boundary 多 checkpoint ID 唯一递增", ck2["checkpoint_id"] == "CK-002")

    # 注册表快照真实计数（复用引擎，不另造）
    import research_integrity as RI
    RI.init_registries(root)
    ck3 = TS.create_checkpoint(root, task="with-registries")
    check("positive 注册表 present/count 反映真实状态",
          ck3["registries"]["rq"]["present"] is True, str(ck3["registries"]["rq"]))

    # ---------- negative：产物丢失/变化 ----------
    os.remove(os.path.join(root, ".aeromech", "artifacts", "analysis", "fmea.md"))
    F.write_text(root, ".aeromech/artifacts/analysis/fmea.md", "# rewritten\n")
    v = TS.resume_view(root)  # 对比的是 CK-003（无该 artifact）→ 用 CK-001 手工比对
    cps = TS.load_checkpoints(root)
    ok, missing, changed = TS._compare_checkpoint(root, cps[0])   # CK-001
    check("negative 内容变化被检测", ".aeromech/artifacts/analysis/fmea.md" in changed)
    F.write_text(root, ".aeromech/artifacts/analysis/other.md", "z\n")
    ckx = TS.create_checkpoint(root, artifacts=[".aeromech/artifacts/analysis/other.md"])
    os.remove(os.path.join(root, ".aeromech", "artifacts", "analysis", "other.md"))
    ok, missing, changed = TS._compare_checkpoint(root, ckx)
    check("negative 产物丢失被检测", ".aeromech/artifacts/analysis/other.md" in missing)

    # ---------- boundary：损坏 checkpoint 不拖垮 resume ----------
    badp = os.path.join(TS.checkpoint_dir(root), "CK-999.yaml")
    with open(badp, "w", encoding="utf-8") as f:
        f.write("checkpoints: [broken\n  indent")
    cps = TS.load_checkpoints(root)
    check("boundary 损坏 checkpoint 被跳过，其余仍可用",
          all(c.get("checkpoint_id") != "CK-999" for c in cps) and len(cps) >= 1)
    os.remove(badp)

    # ---------- resume：S5 中断场景（指令 §六核心） ----------
    root2 = F.make_project(os.path.join(tmp, "resume"))
    st, _ = TS.load_state(root2)
    st["project"].update(title="中断题", paper_type="research")
    st["research"].update(topic_card_file="artifacts/topic-card.md",
                          plan_file="artifacts/research-plan.md")
    TS.save_state(root2, st)
    for f_ in ("topic-card", "research-plan"):
        F.write_text(root2, f".aeromech/artifacts/{f_}.md", "# x\n")
    TS.transition(root2, "S3", "forward", "ok")
    TS.transition(root2, "S4", "forward", "ok")
    TS.transition(root2, "S5", "forward", "ok")
    F.write_text(root2, ".aeromech/artifacts/analysis/fmea.md", "成果1\n")
    TS.create_checkpoint(root2, task="S5-fmea", cursor={"stage": "S5", "done": "fmea"},
                         artifacts=[".aeromech/artifacts/analysis/fmea.md"],
                         next_action="完成 AN-001")
    # —— Agent 中断，进程销毁；新会话仅凭项目目录恢复 ——
    v = TS.resume_view(root2)
    check("resume 阶段=S5（不从 S1 重启）", v["stage"] == "S5", str(v["stage"]))
    check("resume 游标恢复", v["cursor"].get("done") == "fmea")
    check("resume 已有成果完好", ".aeromech/artifacts/analysis/fmea.md" in v["artifacts_ok"])
    check("resume 给出下一步", v["next_action"] == "完成 AN-001")
    check("resume 不丢未关闭问题视图", isinstance(v["open_issues"], list))
    # checkpoint 落后于 state（旧记录）→ 标记供上层判断
    st2, _ = TS.load_state(root2)
    st2["stage"]["current"] = "S6"
    TS.save_state(root2, st2)
    v2 = TS.resume_view(root2)
    check("boundary checkpoint 落后 state 被标记", v2["checkpoint_behind"] is True)
    # 无 checkpoint 的旧项目：仍可给出 stage 视图（不崩溃）
    root3 = F.make_project(os.path.join(tmp, "legacy"))
    v3 = TS.resume_view(root3)
    check("boundary 无 checkpoint 旧项目 resume 可用",
          v3["checkpoint"] is None and v3["stage"] == "S1")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_checkpoint 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
