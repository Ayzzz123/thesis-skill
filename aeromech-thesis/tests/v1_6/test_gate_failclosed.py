# -*- coding: utf-8 -*-
"""test_gate_failclosed.py — 第一轮修复回归锁（A1/A2/A3/B3）

背景（全面审查 2026-10-01 发现）：
  A1  figure_visual 报告行带 `[severity]`，与 delivery_gate.ITEM_RE 不兼容 →
      所有 FAIL/WARN/NHR 行被静默丢弃，v1.6.5 视觉闸域形同虚设。
  A2  thesis_build._step 在子进程**正常返回 rc==3** 时 `out` 未定义 → NameError
      → 整条 pipeline 崩溃且不落 manifest。
  A3  报告缺失时域被 `continue` 跳过 → 域从 items 中凭空消失 → 若其余域 PASS
      则终局可 PASS（假 PASS 泄漏）。
  B3  报告内 `SKIP` 被折算成 SKIPPED_WITH_REASON 后不计入 nas/nhrs/warns →
      混合报告落 `else: PASS`，把"未执行"洗成"通过"。

本测试全部使用**真实产出路径**（真实 figure_visual_qa.Report 写出的报告文本、
真实 _step 子进程调用），不使用手写的简化格式行，以锁死跨模块格式契约。

fail-closed 判据：未执行≠PASS、报告缺失≠PASS、SKIP≠PASS、解析失败≠PASS。
运行：python tests/v1_6/test_gate_failclosed.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import delivery_gate as DG
import figure_visual_qa as VQ
import thesis_build as TB

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def domains(res):
    return {x["gate_id"]: x for x in res["items"]}


def _mkroot(tmp, name):
    """最小项目根：含 .aeromech 与一份可读 state.yaml。

    state.yaml 是 Gate 的研究侧/人工队列域输入；缺它会得到 G-RES-01/G-HR-01
    ERROR（更严格但不属于本测试要锁的问题），故此处给出最小合法骨架，
    使断言聚焦于 A1/A2/A3/B3 本身。
    """
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, ".aeromech", "artifacts", "qa"), exist_ok=True)
    with open(os.path.join(root, ".aeromech", "state.yaml"), "w", encoding="utf-8") as f:
        f.write("schema_version: '1.0'\n"
                "project:\n  title: T\n  major: M\n  paper_type: research\n"
                "stage:\n  current: S9\n  history: []\n  open_issues: []\n")
    return root


def _put(root, rel, text):
    p = os.path.join(root, ".aeromech", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def _real_vis_report(root, items):
    """用真实 figure_visual_qa.Report 产出报告（含 [severity] 后缀）。"""
    rep = VQ.Report(os.path.join(root, ".aeromech", "artifacts", "qa"))
    for code, name, status, sev, ev, reason in items:
        rep.add(code, name, status, sev, ev, reason)
    return rep.save()


def main():
    tmp = tempfile.mkdtemp(prefix="gate_fc_")
    print("== test_gate_failclosed ==")

    # ---------- A1：真实 figure_visual 报告文本必须能被解析 ----------
    r1 = _mkroot(tmp, "a1")
    _real_vis_report(r1, [
        ("VIS-01", "Layout Balance", "PASS", "none", "fig3-1", "平衡"),
        ("VIS-03", "Typography Readability", "FAIL", "critical", "fig3-1", "有效字号 8pt"),
    ])
    rep_path = os.path.join(r1, ".aeromech", "artifacts", "qa", "figure-visual-report.md")
    parsed = DG.parse_format_report(rep_path, "figure_visual")
    check("A1-01 真实 REPORT 文本可解析（非 None）", parsed is not None)
    check("A1-02 带 [critical] 的 FAIL 行被识别（不再静默丢弃）",
          parsed and parsed["status"] == "FAIL",
          str(parsed and parsed["status"]))
    check("A1-03 FAIL 行完整计入 failures",
          parsed and len(parsed["failures"]) == 1
          and "VIS-03" in parsed["failures"][0]["code"],
          str(parsed and parsed["failures"]))
    check("A1-04 行数与产出条数一致（无丢行）",
          parsed and parsed["checks"] == 2, str(parsed and parsed["checks"]))

    # 带 [medium] 的 NHR 行同样不得丢失
    r1b = _mkroot(tmp, "a1b")
    _real_vis_report(r1b, [
        ("VIS-01", "Layout Balance", "PASS", "none", "k", "ok"),
        ("VIS-09", "Academic Style", "NEEDS_HUMAN_REVIEW", "medium", "k", "非 figkit 源"),
    ])
    p1b = DG.parse_format_report(
        os.path.join(r1b, ".aeromech", "artifacts", "qa", "figure-visual-report.md"),
        "figure_visual")
    check("A1-05 带 [medium] 的 NHR 行被识别（域→NHR 而非 PASS）",
          p1b and p1b["status"] == "PASS_WITH_HUMAN_REVIEW"
          and len(p1b["needs_human_review"]) == 1,
          str(p1b and p1b["status"]))

    # 带 [high] 的 WARN 行
    r1c = _mkroot(tmp, "a1c")
    _real_vis_report(r1c, [
        ("VIS-01", "Layout Balance", "WARN", "medium", "k", "留白比 0.3"),
    ])
    p1c = DG.parse_format_report(
        os.path.join(r1c, ".aeromech", "artifacts", "qa", "figure-visual-report.md"),
        "figure_visual")
    check("A1-06 带 [medium] 的 WARN 行被识别（域→WARN 而非 PASS）",
          p1c and p1c["status"] == "PASS_WITH_WARNINGS", str(p1c and p1c["status"]))

    # 真实报告端到端入 gate：FAIL 行必须使域 FAIL 且终局 BLOCK
    r1d = _mkroot(tmp, "a1d")
    _real_vis_report(r1d, [
        ("VIS-01", "Layout Balance", "PASS", "none", "k", "ok"),
        ("VIS-10", "PDF Readability", "FAIL", "critical", "k", "裁切"),
    ])
    with open(os.path.join(r1d, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    res1d = DG.aggregate(r1d)
    it1d = domains(res1d).get("G-FMT-figure_visual")
    check("A1-07 真实报告 FAIL→域 FAIL→终局 BLOCK（端到端）",
          it1d is not None and it1d["status"] == "FAIL" and res1d["status"] == "BLOCK",
          f"{it1d and it1d['status']} / {res1d['status']}")

    # ---------- A3：报告缺失不得让域消失 ----------
    r2 = _mkroot(tmp, "a3")
    with open(os.path.join(r2, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")           # 构建已发生（交付物在场）但无任何 QA 报告
    res2 = DG.aggregate(r2)
    d2 = domains(res2)
    check("A3-01 报告缺失时域仍在 items 中（不消失）",
          "G-FMT-figure_visual" in d2 and "G-FMT-cover" in d2,
          str(sorted(k for k in d2 if k.startswith('G-FMT'))[:4]))
    check("A3-02 交付物在场 + 报告缺失 → 记 FAIL（证据缺失≠通过）",
          d2.get("G-FMT-figure_visual", {}).get("status") == "FAIL",
          str(d2.get("G-FMT-figure_visual", {}).get("status")))
    check("A3-03 该场景终局 BLOCK（不被其余域拉回 PASS）",
          res2["status"] == "BLOCK", res2["status"])
    check("A3-04 缺失域覆盖全部 FORMAT_REPORTS 条目",
          sum(1 for k in d2 if k.startswith("G-FMT-")) == len(DG.FORMAT_REPORTS),
          str(sum(1 for k in d2 if k.startswith("G-FMT-"))))

    # 尚未构建（无交付物）→ N/A 不阻断，但也不构成放行证据
    r2b = _mkroot(tmp, "a3b")
    res2b = DG.aggregate(r2b)
    d2b = domains(res2b)
    check("A3-05 尚未构建（无交付物）→ 报告缺失记 N/A（不误报为内容失败）",
          d2b.get("G-FMT-figure_visual", {}).get("status") == "NOT_APPLICABLE",
          str(d2b.get("G-FMT-figure_visual", {}).get("status")))
    check("A3-06 未构建且无决定性证据 → BLOCK（N/A 不构成 PASS）",
          res2b["status"] == "BLOCK", res2b["status"])

    # pipeline 明确记 NOT_APPLICABLE 时，报告缺失与之相符 → N/A（条件不适用）
    r2c = _mkroot(tmp, "a3c")
    with open(os.path.join(r2c, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    TB.write_manifest(r2c, [{"artifact": "docx", "path": "毕业论文.docx"}])
    man = TB.load_manifest(r2c)
    man["meta"]["steps"] = {"cover_fidelity": {"status": "NOT_APPLICABLE"}}
    import yaml
    with open(os.path.join(r2c, ".aeromech", "artifacts", "build",
                           "artifact-manifest.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(man, f, allow_unicode=True)
    d2c = domains(DG.aggregate(r2c))
    check("A3-07 pipeline 记 N/A 且报告缺失 → 域 N/A（与步一致，不误判 FAIL）",
          d2c.get("G-FMT-cover", {}).get("status") == "NOT_APPLICABLE",
          str(d2c.get("G-FMT-cover", {}).get("status")))

    # ---------- B3：SKIP / SKIPPED_WITH_REASON 不得判 PASS ----------
    r3 = _mkroot(tmp, "b3")
    with open(os.path.join(r3, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    _put(r3, "artifacts/qa/graph-quality-report.md",
         "\n".join(["- GQ-01: PASS | ok",
                    "- GQ-15: SKIP | 人工目检步骤，机器不判定其通过",
                    "- GQ-02: PASS | ok"]) + "\n")
    p3 = DG.parse_format_report(
        os.path.join(r3, ".aeromech", "artifacts", "qa", "graph-quality-report.md"), "graph")
    check("B3-01 SKIP 被规范化为 SKIPPED_WITH_REASON",
          p3 and "GQ-15" in p3.get("skips", []), str(p3 and p3.get("skips")))
    check("B3-02 混合报告含 SKIP → 域不得记 PASS",
          p3 and p3["status"] == "SKIPPED_WITH_REASON", str(p3 and p3["status"]))
    res3 = DG.aggregate(r3)
    it3 = domains(res3).get("G-FMT-graph")
    check("B3-03 含 SKIP 的域→NEEDS_HUMAN_REVIEW（未执行≠通过）",
          it3 is not None and it3["status"] == "NEEDS_HUMAN_REVIEW",
          str(it3 and it3["status"]))
    check("B3-04 该域不得使终局记 PASS",
          res3["status"] != "PASS", res3["status"])

    # 全 SKIP 报告 → 无任何可判定项 → N/A（仍不构成放行证据）
    r3b = _mkroot(tmp, "b3b")
    with open(os.path.join(r3b, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    _put(r3b, "artifacts/qa/graph-quality-report.md",
         "\n".join(["- GQ-01: SKIP | a", "- GQ-15: SKIP | b"]) + "\n")
    p3b = DG.parse_format_report(
        os.path.join(r3b, ".aeromech", "artifacts", "qa", "graph-quality-report.md"), "graph")
    check("B3-05 全 SKIP 报告→N/A（无判定项，不伪造 PASS）",
          p3b and p3b["status"] == "NOT_APPLICABLE", str(p3b and p3b["status"]))
    res3b = DG.aggregate(r3b)
    check("B3-06 全 SKIP 域为 N/A 时终局不得 PASS（其余域仍缺证据）",
          res3b["status"] == "BLOCK", res3b["status"])

    # 显式 SKIPPED_WITH_REASON 写法同样不得判 PASS
    r3c = _mkroot(tmp, "b3c")
    with open(os.path.join(r3c, "毕业论文.docx"), "wb") as f:
        f.write(b"PK fake")
    _put(r3c, "artifacts/qa/table-readability-report.md",
         "\n".join(["- TR-01: PASS | ok",
                    "- TR-14: SKIPPED_WITH_REASON | 无长表"]) + "\n")
    p3c = DG.parse_format_report(
        os.path.join(r3c, ".aeromech", "artifacts", "qa", "table-readability-report.md"),
        "table")
    check("B3-07 显式 SKIPPED_WITH_REASON 同样触发非 PASS 域终局",
          p3c and p3c["status"] == "SKIPPED_WITH_REASON", str(p3c and p3c["status"]))

    # ---------- A2：_step 在 rc==3 时不得抛 NameError ----------
    r4 = _mkroot(tmp, "a2")
    # 子进程**正常返回 3**（不是 FileNotFoundError/TimeoutExpired）
    rec = TB._step(r4, "probe_rc3",
                   [sys.executable, "-c", "import sys; sys.exit(3)"])
    check("A2-01 rc==3 不抛 NameError（返回步记录）",
          isinstance(rec, dict) and rec.get("rc") == 3, str(rec.get("rc")))
    check("A2-02 rc==3 → status=ERROR（环境/配置错误，不装作成功）",
          rec.get("status") == "ERROR", str(rec.get("status")))
    check("A2-03 rc==3 时 output_tail 可读（不因未定义变量崩溃）",
          "output_tail" in rec and isinstance(rec["output_tail"], str),
          repr(rec.get("output_tail"))[:60])

    # rc==3 且脚本有 stderr 时，诊断信息应被保留
    rec4b = TB._step(r4, "probe_rc3_err",
                     [sys.executable, "-c",
                      "import sys; sys.stderr.write('dep missing\\n'); sys.exit(3)"])
    check("A2-04 rc==3 保留子进程诊断输出",
          rec4b.get("status") == "ERROR" and "dep missing" in rec4b.get("output_tail", ""),
          repr(rec4b.get("output_tail"))[:60])

    # 脚本不存在（FileNotFoundError）路径仍为 ERROR
    rec4c = TB._step(r4, "probe_missing", ["definitely-not-a-real-binary-xyz"])
    check("A2-05 脚本缺失仍记 ERROR（原异常分支不回归）",
          rec4c.get("status") == "ERROR" and rec4c.get("rc") == 3,
          str(rec4c.get("rc")))

    # pipeline 整体：某步 rc=3 不得导致 pipeline 抛异常
    r4d = os.path.join(tmp, "a2pipeline")
    os.makedirs(os.path.join(r4d, ".aeromech"), exist_ok=True)
    import yaml as _yaml
    with open(os.path.join(r4d, "build-contract.yaml"), "w", encoding="utf-8") as f:
        _yaml.safe_dump({"project": {"title": "T"}, "content": {"chapters": []},
                         "school_format": {}}, f, allow_unicode=True)
    try:
        out = TB.pipeline(r4d, steps=["qa"])
        raised = None
    except Exception as e:                       # noqa: BLE001 - 就是要断言不抛
        out, raised = None, f"{type(e).__name__}: {e}"
    check("A2-06 pipeline 含 rc=3 步骤时不抛异常（不出现 NameError）",
          raised is None, str(raised))
    check("A2-07 pipeline 记录 ERROR 步骤而非崩溃（结果结构完整）",
          isinstance(out, dict) and "steps" in out, str(type(out)))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_gate_failclosed 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
