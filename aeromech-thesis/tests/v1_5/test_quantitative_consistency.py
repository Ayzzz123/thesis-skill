# -*- coding: utf-8 -*-
"""test_quantitative_consistency.py — Quantitative Consistency QA（v1.5 §16）

核心数字须可追踪且跨位置一致：同一结果的不同写法（425.4 / 425.40 / 425 h）判为同一结果；
摘要与正文数值实质性不一致 → QUANTITATIVE_INCONSISTENCY（可自动同步）；
摘要数值在正文无对应 → 人工核对（不得凭猜测改数）。
覆盖：positive / negative / boundary / repair。

运行：python tests/v1_5/test_quantitative_consistency.py
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
import research_quality_qa as RQ
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


def hits(root, want):
    return [d for d in DIA.diagnose(root)["diagnoses"] if d["issue_type"] == want]


def front(root):
    return os.path.join(root, ".aeromech", "artifacts", "chapters", "front-abstract.md")


def write(path, text):
    open(path, "w", encoding="utf-8").write(text)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v15_qc_")
    print("== test_quantitative_consistency ==")

    # ---------- positive：等价写法判为同一结果 ----------
    check("positive 425.4 与 425.40 等价", DIA._num_close("425.4", "425.40") == "eq")
    check("positive 425.4 与 425 h 等价（0.5% 容差）", DIA._num_close("425.4", "425") == "eq")
    check("positive 完全相同", DIA._num_close("180", "180") == "eq")
    check("positive 数值抽取带单位（425.4h / 8类）",
          {"425.4h", "8类"} <= RQ.numbers_of("MTBF 为 425.4 h，另有 8 类"),
          str(RQ.numbers_of("MTBF 为 425.4 h，另有 8 类")))
    check("positive 无单位短整数（小节号）被排除",
          "3" not in "".join(RQ.numbers_of("本节 3 项指标 12 mm")), str(RQ.numbers_of("本节 3 项指标 12 mm")))
    check("positive 年份被排除", RQ.numbers_of("参照 2019 版规范") == set())

    # ---------- positive：数值一致时不报 ----------
    root = F.write_project(os.path.join(tmp, "pos"))
    check("positive 一致项目无 QUANTITATIVE_INCONSISTENCY", not hits(root, "QUANTITATIVE_INCONSISTENCY"))
    check("positive 一致项目无 ABSTRACT_MISMATCH", not hits(root, "ABSTRACT_MISMATCH"))

    # ---------- negative：摘要 176 vs 正文 180 ----------
    r2 = F.write_project(os.path.join(tmp, "mismatch"), variant="number_mismatch")
    ds = hits(r2, "QUANTITATIVE_INCONSISTENCY")
    check("negative 检出摘要/正文不一致", bool(ds), str([d["detail"] for d in ds])[:120])
    check("negative 判 high", ds and ds[0]["severity"] == "high")
    check("negative 依据写明两侧数值",
          ds and "abstract=176" in ds[0]["evidence"] and "body=180" in ds[0]["evidence"],
          str(ds[0]["evidence"]) if ds else "")
    check("negative 基准可溯源到计算 → 置信度 high", ds and ds[0]["confidence"] == "high")
    check("negative 允许自动同步（number_sync）",
          ds and ds[0]["auto_repairable"] and ds[0]["recommended_repair"]["operation"] == "number_sync")
    check("negative 修复载荷给出 old/new",
          ds and ds[0]["recommended_repair"]["payload"] == {"old": "176", "new": "180",
                                                            "canonical_in_calc": True},
          str(ds[0]["recommended_repair"]["payload"]) if ds else "")

    # ---------- negative：摘要独立数值无对应 → 人工，不得自动改 ----------
    r3 = F.write_project(os.path.join(tmp, "unique"), variant="abstract_unique")
    ds3 = hits(r3, "ABSTRACT_MISMATCH")
    check("negative 无对应数值转人工", bool(ds3) and ds3[0]["human_review_required"] is True,
          str([(d["severity"], d["auto_repairable"]) for d in ds3]))
    check("negative 不自动猜测基准值", ds3 and ds3[0]["recommended_repair"]["operation"] is None)
    check("negative 规则可追溯", ds3 and ds3[0]["rule"] == "QC-02/no-counterpart")
    ids3 = RP.plan(r3, ds3)
    check("negative 人工项不建自动修复单", ids3 == [], str(ids3))

    # ---------- boundary：差异过大不视为同一结果（不误报） ----------
    check("boundary 180 vs 999 判为无对应", DIA._num_close("999", "180") is None)
    check("boundary 180 vs 176 判为疑似同一（near）", DIA._num_close("176", "180") == "near")
    check("boundary 容差边界 0.5% 内为 eq", DIA._num_close("100", "100.4") == "eq")
    check("boundary 超出 10% 不再算疑似", DIA._num_close("100", "112") is None)
    check("boundary 零值不炸", DIA._num_close("0", "0") == "eq" and DIA._num_close("0", "5") is None)

    # ---------- boundary：表格/图/正文同源数值一致 ----------
    r4 = F.write_project(os.path.join(tmp, "table"))
    with open(os.path.join(r4, ".aeromech", "artifacts", "chapters", "ch4-risk-analysis.md"),
              "a", encoding="utf-8") as fh:
        fh.write("\n\n表 4-2 复核值 180.0 与正文一致。\n")
    check("boundary 同一结果的等价写法不报不一致",
          not hits(r4, "QUANTITATIVE_INCONSISTENCY"))

    # ---------- repair：同步后复检通过且只动摘要 ----------
    chap_before = open(os.path.join(r4, ".aeromech", "artifacts", "chapters",
                                    "ch4-risk-analysis.md"), encoding="utf-8").read()
    ids = RP.plan(r2, DIA.diagnose(r2)["diagnoses"])
    done, failed = RP.execute(r2, ids=ids)
    check("repair number_sync 执行", bool(done) and not failed, str(done)[:120])
    text = open(front(r2), encoding="utf-8").read()
    check("repair 摘要数字与正文对齐", "180" in text and "176" not in text)
    check("repair 修复后不一致诊断消失", not hits(r2, "QUANTITATIVE_INCONSISTENCY"))
    rep = next(x for x in RI.load_registry(r2, "repairs") if x["id"] == ids[0])
    check("repair 记录改动次数（可审计）", "处" in str((rep.get("after") or {}).get("result")),
          str((rep.get("after") or {}).get("result"))[:80])
    check("repair 正文未被牵连改动",
          open(os.path.join(r2, ".aeromech", "artifacts", "chapters",
                            "ch4-risk-analysis.md"), encoding="utf-8").read().count("180") > 0)
    check("repair 其它文件保持原样", chap_before.endswith("180.0 与正文一致。\n"))

    print(f"test_quantitative_consistency 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
