# -*- coding: utf-8 -*-
"""test_abstract_consistency.py — 摘要↔正文一致性（RQG-09）与数值工具函数

运行：python tests/v1_4/test_abstract_consistency.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_quality_qa as RQ

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def run_rq(root):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        s, rep = RQ.run(root)
    return s, rep


def item(rep, code):
    return next((i for i in rep.items if i["code"] == code), None)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_abs_")
    print("== test_abstract_consistency ==")

    # ---- 正例 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    s, rep = run_rq(root)
    r9 = item(rep, "RQG-09")
    check("正例 RQG-09 NEEDS_HUMAN_REVIEW（v1.4.1：模拟身份语义须人工复核，不得自动 PASS）",
          r9["status"] == "NEEDS_HUMAN_REVIEW", r9["detail"])
    check("正例 gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))
    # 正例摘要含免责句"不代表真实机队的统计特征"→ 不得误报
    front = open(os.path.join(root, ".aeromech", "artifacts", "chapters",
                              "front-abstract.md"), encoding="utf-8").read()
    check("免责句含'机队'但不触发越界 FAIL（NHR 为待复核，非 FAIL）",
          "机队" in front and r9["status"] != "FAIL", r9["status"])

    # ---- FAIL/Critical：模拟数据摘要写成"实测" ----
    root2 = F.write_project(os.path.join(tmp, "real"), variant="abstract_real_claim")
    s2, rep2 = run_rq(root2)
    r9b = item(rep2, "RQG-09")
    check("摘要实测声明 RQG-09 FAIL(Critical)", r9b["status"] == "FAIL" and r9b["severity"] == "Critical")
    check("摘要实测声明 gate=FAIL", s2["gate"] == "FAIL")

    # ---- FAIL：摘要数值正文未出现 ----
    root3 = F.write_project(os.path.join(tmp, "extra"), variant="abstract_extra_number")
    s3, rep3 = run_rq(root3)
    r9c = item(rep3, "RQG-09")
    check("摘要独立数值 RQG-09 FAIL", r9c["status"] == "FAIL")
    check("摘要独立数值详情含 245", "245" in r9c["detail"], r9c["detail"][:80])

    # ---- boundary：否定语境中的"实测"免责句不触发 ----
    root4 = F.write_project(os.path.join(tmp, "negated"), variant="abstract_negated_real_claim")
    s4, rep4 = run_rq(root4)
    check("否定语境'并非实测'不触发 RQG-09 FAIL",
          item(rep4, "RQG-09")["status"] in ("PASS", "NEEDS_HUMAN_REVIEW"), item(rep4, "RQG-09")["detail"][:80])

    # ---- boundary：numbers_of 工具函数 ----
    check("numbers_of 保留带单位小数字", "8类" in RQ.numbers_of("共得到 8 类故障模式"))
    check("numbers_of 保留百分比", "95%" in RQ.numbers_of("置信度为 95%"))
    check("numbers_of 保留小数", "6.7%" in RQ.numbers_of("发生率为 6.7%"))
    check("numbers_of 排除年份", RQ.numbers_of("自 2020 年以来") == set())
    check("numbers_of 排除无单位 1-2 位整数", RQ.numbers_of("第 4 章") == set())
    check("numbers_of 保留三位数", "180" in RQ.numbers_of("RPN 最大值为 180"))

    print(f"test_abstract_consistency 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
