# -*- coding: utf-8 -*-
"""tests/v1_4_1/test_human_review.py — NEEDS_HUMAN_REVIEW 人工复核回路

验证：
1. 弱证据（全 simulated/pending）语境下，RQG-09/RQG-10 未命中强断言模式时输出 NEEDS_HUMAN_REVIEW
   （不得自动 PASS），队列项含 claim / evidence / reason / uncertainty；生成 human-review-checklist.md；
   Gate = PASS_WITH_HUMAN_REVIEW（退出码 0）。
2. 强断言模式命中仍必须 FAIL Critical（启发式证伪能力未削弱）。
3. 回填 human-review.yaml：全部 ok → Gate PASS；任一 violation → Gate FAIL（退出码 1）。
4. 未知 decision / 未匹配键 → WARN（不阻断）。
运行：python tests/v1_4_1/test_human_review.py
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(SKILL, "tests", "v1_4"))
import _fixtures as F  # noqa: E402
import research_quality_qa as RQ  # noqa: E402

RQG = os.path.join(SCRIPTS, "research_quality_qa.py")
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


def run_cli(root):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, RQG, "--project", root],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=SKILL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load_json(root):
    p = os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality.json")
    return json.load(open(p, encoding="utf-8"))


def write_reviews(root, entries):
    import yaml
    p = os.path.join(root, ".aeromech", "research", "human-review.yaml")
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump({"reviews": entries}, f, allow_unicode=True, sort_keys=False)


def main():
    print("== test_human_review ==")
    tmp = tempfile.mkdtemp(prefix="v141_hr_")

    # ---- 1) 弱证据 → NHR 队列 + checklist ----
    root = F.write_project(os.path.join(tmp, "nhr"), variant="nhr_weak")
    s, rep = run_rq(root)
    r9, r10 = item(rep, "RQG-09"), item(rep, "RQG-10")
    check("RQG-09 NEEDS_HUMAN_REVIEW", r9["status"] == "NEEDS_HUMAN_REVIEW", r9["detail"][:60])
    check("RQG-10 NEEDS_HUMAN_REVIEW", r10["status"] == "NEEDS_HUMAN_REVIEW", r10["detail"][:60])
    check("RQG-09/10 不得为 PASS", r9["status"] != "PASS" and r10["status"] != "PASS")
    check("gate=PASS_WITH_HUMAN_REVIEW", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))
    nhr = s["needs_human_review"]
    check("队列含 RQG-09:ABSTRACT 与 RQG-10 项", any("RQG-09" in k for k in nhr) and
          any("RQG-10" in k for k in nhr), str(nhr))
    cl = s["human_review_checklist"]
    check("生成 human-review-checklist.md", cl and os.path.isfile(cl))
    body = open(cl, encoding="utf-8").read()
    for field in ("claim", "evidence", "reason", "uncertainty"):
        check(f"清单含 {field} 维度", field in body)
    check("清单含 7 维复核要点", "核心结论是否真的被证据支持" in body and "文献是否真正支持对应论断" in body)
    rc, _ = run_cli(root)
    check("NHR 状态退出码=0（可继续但须复核）", rc == 0, f"rc={rc}")

    # ---- 2) 强断言命中仍 FAIL Critical ----
    root_ov = F.write_project(os.path.join(tmp, "overreach"), variant="overreach_claim")
    s_ov, rep_ov = run_rq(root_ov)
    r10o = item(rep_ov, "RQG-10")
    check("强断言命中 RQG-10 FAIL(Critical)", r10o["status"] == "FAIL" and r10o["severity"] == "Critical")

    # ---- 3) 回填裁决：全部 ok → PASS ----
    write_reviews(root, [{"item": k, "decision": "ok", "reviewer": "Tester",
                          "date": "2026-09-12", "note": "逐条核对通过"} for k in nhr])
    s2, rep2 = run_rq(root)
    check("全部 ok 后 gate=PASS", s2["gate"] == "PASS", str(s2["gate"]))
    check("队列已裁决（resolved 记录）", len(s2.get("review_resolved", [])) == len(nhr),
          str(s2.get("review_resolved")))
    hr2 = item(rep2, "RQG-HR")
    check("RQG-HR 记录为 PASS", hr2 and hr2["status"] == "PASS", hr2["detail"][:50] if hr2 else "")
    rc2, _ = run_cli(root)
    check("已裁决退出码=0", rc2 == 0, f"rc={rc2}")

    # ---- 4) violation → FAIL（退出码 1）----
    write_reviews(root, [{"item": k, "decision": ("violation" if i == 0 else "ok"),
                          "reviewer": "Tester", "date": "2026-09-12", "note": "越界确认"}
                         for i, k in enumerate(nhr)])
    s3, rep3 = run_rq(root)
    check("violation 后 gate=FAIL", s3["gate"] == "FAIL", str(s3["gate"]))
    hr3 = [i for i in rep3.items if i["code"] == "RQG-HR" and i["status"] == "FAIL"]
    check("violation 记 RQG-HR FAIL(Critical)", bool(hr3) and hr3[0]["severity"] == "Critical")
    rc3, _ = run_cli(root)
    check("violation 退出码=1", rc3 == 1, f"rc={rc3}")

    # ---- 5) 未知 decision / 未匹配键 → WARN，不阻断 ----
    write_reviews(root, [{"item": nhr[0], "decision": "banana"},
                         {"item": "RQG-10:NOT-EXIST", "decision": "ok"}])
    s4, rep4 = run_rq(root)
    warns = [i for i in rep4.items if i["code"] == "RQG-HR-WARN"]
    check("未知 decision/未匹配键记 WARN", len(warns) >= 2, str([w["detail"][:30] for w in warns]))
    check("WARN 不改变 NHR 状态", s4["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s4["gate"]))

    print(f"test_human_review 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
