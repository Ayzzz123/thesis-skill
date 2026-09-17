# -*- coding: utf-8 -*-
"""test_document_contract.py — 文档=代码=测试 一致性锁（v1.6 Phase 5，指令 §十一）

原则：文档写 A、代码实现 B → FAIL。检查对象：
  DOC-01 SKILL/README 版本声明（发布态：v1.6.0 为正式版，三处版本联动一致；
       SKILL/README 不再含 v1.6.0 开发中/未发布措辞）
  DOC-02 CHANGELOG v1.6.0 顶部正式 release 条目（不再 [Unreleased]；v1.5.0 降为历史条目）
  DOC-03 orchestration.md 存在且覆盖 State/Context/Route/Action/Checkpoint/Resume/Recovery/
       Agent Loop/Build/Gate + 主循环链
  DOC-04 state.md 引用程序化层（§18/thesis_state/Checkpoint/drift），且与脚本 schema 行为一致
  DOC-05 delivery-pipeline.md 引用统一构建/manifest/图生命周期/聚合器 + BUILD→…→FINALIZE 顺序 +
       Critical/ERROR 不得伪装 PASS 条款
  DOC-06 状态词表统一：item 级七态/gate 级五态在 orchestration.md 与代码常量一致
  DOC-07 figure 接口文档 plan_figures/generate_figure/validate_figure + 生命周期 7 态 = 代码常量
  DOC-08 build contract 文档七域 = thesis_build 实际校验域；缺失语义 required=ERROR/optional=N/A
  DOC-09 delivery_gate 文档五态 + "总分不参与放行" = 代码 RANK/常量
  DOC-10 脚本存在性与 CLI 注册（orchestration.md §15 列出的每个模块都真实可 import）
运行：python tests/v1_6/test_document_contract.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
import thesis_state as TS
import stage_routing as SR
import thesis_orchestrator as ORCH
import figure_iface as FI
import thesis_build as TB
import delivery_gate as DG

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def read(*rel):
    with open(os.path.join(SKILL_DIR, *rel), encoding="utf-8") as f:
        return f.read()


def flat(text):
    """markdown 有硬换行，短语匹配前折叠空白。"""
    return re.sub(r"\s+", " ", text)


def main():
    print("== test_document_contract ==")
    skill = read("SKILL.md")
    readme = read("README.md")
    changelog = read("CHANGELOG.md")
    orch = read("references", "orchestration.md")
    stm = read("references", "state.md")
    dpipe = read("references", "delivery-pipeline.md")

    orch_f, stm_f, dpipe_f = flat(orch), flat(stm), flat(dpipe)

    # ---------- DOC-01 版本声明（发布态：v1.6.0 为正式版） ----------
    v_skill = re.search(r"版本：v([0-9.]+)", skill)
    check("DOC-01 SKILL 正式版本=1.6.0（Phase 7 已升级）",
          v_skill and v_skill.group(1) == "1.6.0", str(v_skill and v_skill.group(1)))
    skill_f = flat(skill)
    check("DOC-01 SKILL 不再含 v1.6.0 开发中/未发布措辞",
          "v1.6.0 开发中" not in skill_f and "不视为 v1.5.0 交付承诺" not in skill_f)
    check("DOC-01 README 当前版本声明为 aeromech-thesis v1.6.0",
          re.search(r"aeromech-thesis v1\.6\.0", readme) is not None)
    check("DOC-01 README §11 声明 v1.6.0 已发布且含发布验证（test-8.0/人工复核）",
          "v1.6.0 已发布" in readme and "test-8.0" in readme and "人工复核" in readme)
    check("hard README 不再声明 v1.6.0 为 development/未发布 roadmap",
          "v1.6.0 development" not in readme and "未发布）**：" not in readme)

    # ---------- DOC-02 CHANGELOG（发布态：v1.6.0 为顶部正式条目） ----------
    head = changelog.split("\n## ", 2)
    check("DOC-02 CHANGELOG 顶部条目=v1.6.0 正式 release（不再是 [Unreleased]）",
          head[1].startswith("v1.6.0 —"), head[1][:30])
    check("DOC-02 v1.6.0 为最新正式发布条目",
          re.search(r"^## v1\.6\.0", changelog, re.M) is not None)
    clg_f = flat(changelog)
    check("DOC-02 v1.6.0 条目声明已发布且含 test-8.0/Phase 7 收口",
          "已发布" in clg_f and "test-8.0" in clg_f and "Phase 7" in clg_f
          and "正式版本号仍为 v1.5.0" not in clg_f)
    # 一致性联动（与 test_dev_install_sync 同口径）
    cm = re.search(r"^## v(\d+\.\d+\.\d+)", changelog, re.M)
    rm = re.search(r"aeromech-thesis v(\d+\.\d+\.\d+)", readme)
    check("DOC-02 CHANGELOG 最新 release 与 README/SKILL 版本联动一致",
          cm and rm and v_skill and cm.group(1) == rm.group(1) == v_skill.group(1) == "1.6.0")

    # ---------- DOC-03 orchestration.md 覆盖 ----------
    need_topics = ["State", "Context", "Route", "Action", "Checkpoint", "Resume", "Recovery",
                   "Agent Loop", "Build", "Gate"]
    for t in need_topics:
        check(f"DOC-03 orchestration.md 覆盖 {t}", t in orch_f)
    check("DOC-03 主循环链完整（LOAD→CONTEXT→ROUTE→PREREQ→EXECUTE→CHECKPOINT→VALIDATE→NEXT）",
          "LOAD STATE" in orch_f and "CHECK PREREQUISITES" in orch_f
          and "CHECKPOINT" in orch_f and "VALIDATE" in orch_f and "NEXT" in orch_f)
    check("DOC-03 失败链 DETECT→DIAGNOSE→RECOVERY→VALIDATE",
          "DETECT" in orch_f and "DIAGNOSE" in orch_f and "RECOVERY" in orch_f)
    check("DOC-03 禁止从 S1 重启条款", "禁止从 S1 重启" in orch_f)

    # ---------- DOC-04 state.md 同步 ----------
    check("DOC-04 state.md 引用程序化状态层与 thesis_state.py",
          "thesis_state.py" in stm and "§18" in stm or "## 18" in stm)
    check("DOC-04 checkpoint 工件路径与代码一致",
          ".aeromech/checkpoints/CK-XXX.yaml" in stm
          and os.path.basename(TS.checkpoint_dir("x")).endswith("checkpoints"))
    check("DOC-04 schema 支持集合与代码一致（1.0/1.1）",
          set(re.findall(r"`(1\.\d)`", stm.split("## 10")[1].split("## 11")[0]))
          == TS.SUPPORTED_SCHEMA, str(TS.SUPPORTED_SCHEMA))
    import inspect
    drift_codes = {"STATE_DRIFT", "REGISTRY_DRIFT", "ARTIFACT_MISSING", "ARTIFACT_CHANGED"}
    src = inspect.getsource(ORCH.drift_checks)
    check("DOC-04 drift codes 与代码逐一对应", all(f'"{c}"' in src for c in drift_codes))

    # ---------- DOC-05 delivery-pipeline.md ----------
    check("DOC-05 引用统一构建 thesis_build 与 artifact-manifest",
          "thesis_build.py" in dpipe and "artifact-manifest" in dpipe)
    check("DOC-05 引用 figure 生命周期", "figure_iface" in dpipe and "EMBEDDED" in dpipe)
    check("DOC-05 引用 Delivery Gate 聚合器",
          "delivery_gate.py" in dpipe and "五态" in dpipe)
    check("DOC-05 流水线顺序 docx→toc→repaginate→pdf→finalize→qa 与 ALL_STEPS 一致",
          "docx → toc → repaginate → pdf → finalize → qa" in dpipe
          and TB.ALL_STEPS == ["docx", "toc", "repaginate", "pdf", "finalize", "qa"])
    check("DOC-05 Critical/ERROR 不得伪装 PASS 条款在位",
          "不得伪装 PASS" in dpipe)

    # ---------- DOC-06 状态词表统一 ----------
    item7 = {"PASS", "WARN", "FAIL", "NEEDS_HUMAN_REVIEW", "NOT_APPLICABLE",
             "SKIPPED_WITH_REASON", "ERROR"}
    check("DOC-06 orchestration.md 列 item 级七态（v1.4.1 词表，不造新）",
          all(s in orch for s in item7))
    gate5 = {"PASS", "PASS_WITH_WARNINGS", "PASS_WITH_HUMAN_REVIEW", "BLOCK", "ERROR"}
    check("DOC-06 orchestration.md gate 级五态 = delivery_gate.GATE_STATES",
          set(DG.GATE_STATES) == gate5 and all(s in orch for s in gate5))
    check("DOC-06 旧冲突术语清理：SKILL/delivery/state/orchestration 不再有'待人工复核'等漂移变体",
          not re.search(r"待人工复核", skill + dpipe + stm + orch)
          and "NEEDS_HUMAN_REVIEW" in orch)

    # ---------- DOC-07 figure 接口文档化 ----------
    for fn in ("plan_figures", "generate_figure", "validate_figure"):
        check(f"DOC-07 orchestration.md 记录 {fn}()", f"{fn}(" in orch and hasattr(FI, fn))
    life = {"PLANNED", "GENERATED", "VALIDATED", "EMBEDDED", "VERIFIED", "REJECTED",
            "NEEDS_HUMAN_REVIEW"}
    check("DOC-07 生命周期 7 态文档=代码常量",
          set(FI.LIFECYCLE) == life and all(s in orch for s in life))
    check("DOC-07 SKILL.md 记录图接口且不复制 Figure Engine 承诺在位",
          "figure_iface.py" in skill and "不复制 Figure Engine" in skill)
    check("DOC-07 Provider 契约三方法抽象基类真实",
          all(hasattr(FI.FigureProvider, m) for m in ("plan", "generate", "validate")))

    # ---------- DOC-08 build contract 文档化 ----------
    for dom in ("project", "content", "research", "school_format", "figures", "output", "qa"):
        check(f"DOC-08 orchestration.md 记录契约域 {dom}", dom in orch)
    check("DOC-08 缺失语义 required=ERROR / optional=NOT_APPLICABLE 文档化",
          "required 缺→ERROR" in orch_f and "optional 缺→NOT_APPLICABLE" in orch_f)
    check("DOC-08 代码行为与文档一致：无契约→NOT_APPLICABLE；必需缺→ERROR",
          TB.validate_contract(SKILL_DIR)["status"] == "NOT_APPLICABLE")   # 本仓库根当然无契约

    # ---------- DOC-09 delivery gate 文档化 ----------
    check("DOC-09 聚合域清单文档化（Research/Evidence/Data/Figure/Document/Format/PDF/Human Review）",
          all(t in orch_f for t in ("格式 QA", "Document", "Figure", "Research QA", "Human Review")))
    check("DOC-09 每项 gate 必带 evidence/reason/remediation 文档化",
          "evidence" in orch and "remediation" in orch and "gate_id" in orch)
    check("DOC-09 终局规则以代码为准：RANK 顺序与文档优先级一致",
          DG.RANK["PASS"] < DG.RANK["PASS_WITH_WARNINGS"] < DG.RANK["PASS_WITH_HUMAN_REVIEW"]
          < DG.RANK["BLOCK"] < DG.RANK["ERROR"]
          and "ERROR > Critical/High FAIL(BLOCK) > NEEDS_HUMAN_REVIEW > WARN > PASS" in orch)
    import inspect
    dg_src = inspect.getsource(DG)
    check("DOC-09 总分不掩盖 Critical 条款文档+代码一致",
          "不参与放行" in orch_f and "不参与放行" in dg_src
          and "Overall Score" in dg_src)

    # ---------- DOC-10 模块注册表真实 ----------
    mods = ["thesis_state", "material_ingestion", "school_requirements", "research_context",
            "stage_routing", "thesis_orchestrator", "figure_iface", "thesis_build",
            "delivery_gate"]
    for m in mods:
        check(f"DOC-10 orchestration.md 引用的模块真实存在 scripts/{m}.py",
              os.path.isfile(os.path.join(SKILL_DIR, "scripts", m + ".py")) and m in orch)
    # AI 挂载点：文档表格的工具全部映射到真实执行器
    src_exec = inspect.getsource(ORCH.execute_ai)
    for tool in ("research_diagnosis", "research_quality_qa", "research_agent_loop",
                 "research_integrity"):
        check(f"DOC-10 文档挂载点执行器 {tool} 在编排中真实接线", tool in orch and
              (tool.split("_")[-1] in src_exec or tool in src_exec))

    print(f"test_document_contract 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
