# -*- coding: utf-8 -*-
"""test_scope_control.py — Research Scope Control（v1.5 §17）

注册 Scope Boundary（included/excluded/assumptions），检测写作阶段的 scope creep；
范围外主题命中 ≥2 次判 high、1 次判 medium（需人工确认是否背景性提及）。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_scope_control.py
"""
import copy
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_design as RD
import research_diagnosis as DIA
import research_integrity as RI

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def hits(root, want):
    return [d for d in DIA.diagnose(root)["diagnoses"] if d["issue_type"] == want]


def chap(root, name):
    return os.path.join(root, ".aeromech", "artifacts", "chapters", name)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_scope_")
    print("== test_scope_control ==")

    # ---------- positive：注册边界存在且正文不越界 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    da = RD.analyze(root)
    check("positive scope 已注册", bool(da.get("scope")) and da["scope"]["included"],
          str(da.get("scope", {}).get("included")))
    check("positive excluded 非空", bool(da["scope"].get("excluded")))
    check("positive 无 SCOPE_OVERFLOW", not hits(root, "SCOPE_OVERFLOW"))
    check("positive 无 SCOPE_UNDERFLOW", not hits(root, "SCOPE_UNDERFLOW"))
    check("positive 范围检查不产出人工队列项",
          not [d for d in DIA.diagnose(root)["diagnoses"]
               if d["issue_type"].startswith("SCOPE_") and d["human_review_required"]])

    # ---------- negative：正文擅自扩展到 excluded 主题（scope creep） ----------
    r2 = F.write_project(os.path.join(tmp, "creep"), variant="scope_creep")
    ds = hits(r2, "SCOPE_OVERFLOW")
    check("negative 检测到 scope creep", bool(ds), str([x["detail"] for x in ds])[:120])
    check("negative 命中 2 次判 high", ds and ds[0]["severity"] == "high",
          str(ds[0]["severity"]) if ds else "")
    check("negative 根因指向注册边界不一致",
          ds and "Scope Boundary" in ds[0]["root_cause"], ds[0]["root_cause"] if ds else "")
    check("negative 不得自动扩范围（转人工）",
          ds and ds[0]["auto_repairable"] is False and ds[0]["human_review_required"] is True)
    check("negative 处置为 queue（人工判定类）", ds and ds[0]["disposition"] == "queue")
    check("negative 受影响节点定位 SCOPE", ds and ds[0]["affected_nodes"] == ["SCOPE"])
    check("negative 修复选项含设计更新路径",
          ds and any(o["repair_type"] in ("REFRAME_RQ", "REWRITE_SECTION") for o in ds[0]["repair_options"]))

    # ---------- negative：仅一次背景性提及 → medium（不打成 high） ----------
    r3 = F.write_project(os.path.join(tmp, "once"))
    with open(chap(r3, "ch3-fault-modes.md"), "a", encoding="utf-8") as fh:
        fh.write("\n\n飞控系统的分析流程与本研究无直接关联，仅举一例说明方法通用性。\n")
    ds3 = hits(r3, "SCOPE_OVERFLOW")
    check("negative 单次提及判 medium", bool(ds3) and ds3[0]["severity"] == "medium",
          str([(d["severity"], d["detail"]) for d in ds3])[:120])

    # ---------- negative：included 项未被覆盖 → SCOPE_UNDERFLOW ----------
    r4 = F.write_project(os.path.join(tmp, "under"), variant="scope_under")
    ds4 = hits(r4, "SCOPE_UNDERFLOW")
    check("negative 范围内未覆盖被识别", bool(ds4), str([d["detail"] for d in ds4])[:120])
    check("negative 指向缺失项名称", ds4 and "起落架收放机构" in ds4[0]["detail"])

    # ---------- boundary：无 scope 注册表 → 不做范围判定（不臆断） ----------
    r5 = F.write_project(os.path.join(tmp, "noscope"), with_design=False)
    dg5 = DIA.diagnose(r5)
    check("boundary 无范围注册时不产生范围类诊断",
          not [d for d in dg5["diagnoses"] if d["issue_type"].startswith("SCOPE_")],
          str([d["issue_type"] for d in dg5["diagnoses"]])[:120])

    # ---------- boundary：同一 excluded 词多次命中只出一条（按词聚合） ----------
    r6 = F.write_project(os.path.join(tmp, "multi"))
    with open(chap(r6, "ch3-fault-modes.md"), "a", encoding="utf-8") as fh:
        fh.write("\n\n发动机系统的传热分析亦可用同一流程。发动机系统的件号管理另成体系。\n")
    ds6 = [d for d in DIA.diagnose(r6)["diagnoses"]
           if d["issue_type"] == "SCOPE_OVERFLOW" and "发动机系统" in d["detail"]]
    check("boundary 同一越界主题聚合为一条", len(ds6) == 1, str(len(ds6)))
    check("boundary 计数写入描述（×2）", ds6 and "×2" in ds6[0]["detail"],
          ds6[0]["detail"] if ds6 else "")

    # ---------- boundary：多个不同主题各自成案（不被折叠） ----------
    r7 = F.write_project(os.path.join(tmp, "multi2"))
    with open(chap(r7, "ch3-fault-modes.md"), "a", encoding="utf-8") as fh:
        fh.write("\n\n飞控系统的分析可比照进行。飞控系统的余度设计也需评估。\n"
                 "发动机系统的滑耗分析同样适用。发动机系统的孔探检查亦需安排。\n")
    types = [d["detail"] for d in DIA.diagnose(r7)["diagnoses"] if d["issue_type"] == "SCOPE_OVERFLOW"]
    check("boundary 不同越界主题分别报告",
          any("飞控" in t for t in types) and any("发动机" in t for t in types), str(types)[:160])

    # ---------- repair：更新 Research Design/Scope 后越界可被接受 ----------
    check("repair 前 high 越界存在", bool(hits(r2, "SCOPE_OVERFLOW")))
    sc = RI.load_registry(r2, "scope")
    sc[0]["excluded"] = [x for x in sc[0]["excluded"] if "飞控" not in str(x)]
    sc[0]["included"] = sc[0]["included"] + ["飞控系统对比分析"]
    RI.save_registry(r2, "scope", sc)
    after = hits(r2, "SCOPE_OVERFLOW")
    check("repair 设计更新后 scope creep 解除", not after, str([d["detail"] for d in after])[:120])

    # ---------- repair：改写越界段落后严重度下降 ----------
    r8 = F.write_project(os.path.join(tmp, "rewrite"), variant="scope_creep")
    text = open(chap(r8, "ch3-fault-modes.md"), encoding="utf-8").read()
    open(chap(r8, "ch3-fault-modes.md"), "w", encoding="utf-8").write(
        text.replace("飞控系统的作动器故障也应按相同流程分析", "本方法的流程可推广至其它机电子系统"))
    sev = [d["severity"] for d in hits(r8, "SCOPE_OVERFLOW")]
    check("repair 改写后不再有 high 越界", "high" not in sev, str(sev))

    print(f"test_scope_control 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
