# -*- coding: utf-8 -*-
"""test_research_questions.py — Research Question Registry 与 RQG-01/02/03（PASS/FAIL/boundary）

运行：python tests/v1_4/test_research_questions.py
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
import research_integrity as RI
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


def mutate(root, reg, fn):
    items = RI.load_registry(root, reg)
    fn(items)
    RI.save_registry(root, reg, items)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_rq_")
    print("== test_research_questions ==")

    # ---- 正例 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    val = RI.validate(root)
    check("正例 validate ok", val["ok"], str(val["problems"][:2]))
    check("RQ 记录数=2", val["stats"]["rq"] == 2)
    s, rep = run_rq(root)
    check("RQG-01 PASS", item(rep, "RQG-01")["status"] == "PASS")
    check("RQG-02 PASS", item(rep, "RQG-02")["status"] == "PASS")
    check("RQG-03 PASS", item(rep, "RQG-03")["status"] == "PASS")
    check("gate=PASS_WITH_HUMAN_REVIEW（v1.4.1：全模拟数据→NHR 队列）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))

    # ---- FAIL：问题过短 ----
    root2 = F.write_project(os.path.join(tmp, "short"), variant="short_rq")
    s2, rep2 = run_rq(root2)
    check("短问题 RQG-01 FAIL", item(rep2, "RQG-01")["status"] == "FAIL")
    check("短问题 gate=FAIL", s2["gate"] == "FAIL")
    check("短问题 severity=High", item(rep2, "RQG-01")["severity"] == "High")

    # ---- FAIL：目标与问题无关 ----
    root3 = F.write_project(os.path.join(tmp, "mismatch"), variant="rq_mismatched_objective")
    s3, rep3 = run_rq(root3)
    check("目标无关 RQG-02 FAIL", item(rep3, "RQG-02")["status"] == "FAIL")
    check("目标无关 gate=FAIL", s3["gate"] == "FAIL")

    # ---- FAIL：RQ 缺方法链接 ----
    root4 = F.write_project(os.path.join(tmp, "nomethod"), variant="rq_no_method")
    val4 = RI.validate(root4)
    check("缺方法 validate 报 RI-RQ-LINK",
          any(p["code"] == "RI-RQ-LINK" for p in val4["problems"]), str(val4["problems"][:2]))
    s4, rep4 = run_rq(root4)
    check("缺方法 RQG-03 FAIL", item(rep4, "RQG-03")["status"] == "FAIL")
    check("缺方法 RQG-00 FAIL(High)", item(rep4, "RQG-00")["status"] == "FAIL"
          and item(rep4, "RQG-00")["severity"] == "High")

    # ---- FAIL：方法引用悬空 ----
    root5 = F.write_project(os.path.join(tmp, "danglingM"))

    def _set_dangling(items):
        items[0]["related_methods"] = ["M-999"]
    mutate(root5, "rq", _set_dangling)
    val5 = RI.validate(root5)
    check("悬空方法引用报 RI-DANGLING",
          any(p["code"] == "RI-DANGLING" for p in val5["problems"]), str(val5["problems"][:2]))
    check("悬空方法 validate not ok", not val5["ok"])

    # ---- boundary：question 恰 8 字 / objective 恰 4 字 允许通过 ----
    root6 = F.write_project(os.path.join(tmp, "boundary"))

    def _add_boundary(items):
        items.append({"id": "RQ-03", "question": "一二三四五六七八", "objective": "一二三四",
                      "related_methods": ["M-001"], "related_chapters": [6],
                      "related_analyses": ["AN-001"], "related_conclusions": []})
    mutate(root6, "rq", _add_boundary)
    val6 = RI.validate(root6)
    check("boundary validate ok", val6["ok"], str(val6["problems"][:2]))
    s6, rep6 = run_rq(root6)
    check("boundary RQG-01 PASS（8字/4字临界）", item(rep6, "RQG-01")["status"] == "PASS")
    check("boundary RQG-02 PASS（n-gram 关联）", item(rep6, "RQG-02")["status"] == "PASS")

    print(f"test_research_questions 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
