# -*- coding: utf-8 -*-
"""tests/v1_4_1/test_gate_state.py — Gate 状态机（PASS / PASS_WITH_HUMAN_REVIEW / FAIL / ERROR / not_initialized）

验证各状态与退出码一一对应，且状态可由 JSON 稳定读取。
运行：python tests/v1_4_1/test_gate_state.py
"""
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


def run_cli(root):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, RQG, "--project", root],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=SKILL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def gate_json(root):
    p = os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality.json")
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}


def main():
    print("== test_gate_state ==")
    tmp = tempfile.mkdtemp(prefix="v141_gate_")

    # ---- not_initialized（旧项目兼容，不阻塞）----
    root_un = F.make_empty_project(tmp, "uninit")
    rc, _ = run_cli(root_un)
    j = gate_json(root_un)
    check("no-registry rc=2", rc == 2, f"rc={rc}")
    check("no-registry gate=not_initialized", j.get("gate") == "not_initialized", str(j.get("gate")))

    # ---- PASS_WITH_HUMAN_REVIEW（NHR 队列）----
    root_nhr = F.write_project(os.path.join(tmp, "nhr"), variant="nhr_weak")
    rc, _ = run_cli(root_nhr)
    j = gate_json(root_nhr)
    check("NHR rc=0", rc == 0, f"rc={rc}")
    check("NHR gate=PASS_WITH_HUMAN_REVIEW", j.get("gate") == "PASS_WITH_HUMAN_REVIEW", str(j.get("gate")))
    check("NHR 队列非空", bool(j.get("needs_human_review")), str(j.get("needs_human_review")))

    # ---- FAIL（强断言越界，Critical 阻断）----
    root_ov = F.write_project(os.path.join(tmp, "ov"), variant="overreach_claim")
    rc, _ = run_cli(root_ov)
    j = gate_json(root_ov)
    check("越界 rc=1", rc == 1, f"rc={rc}")
    check("越界 gate=FAIL", j.get("gate") == "FAIL", str(j.get("gate")))
    check("越界 fails 含 RQG-10/Critical",
          any(c == "RQG-10" and s == "Critical" for c, s, _ in j.get("fails", [])))

    # ---- ERROR（注册表损坏，绝不 PASS）----
    root_cor = F.write_project(os.path.join(tmp, "corrupt"))
    with open(os.path.join(root_cor, ".aeromech", "research", "claims.yaml"), "w",
              encoding="utf-8") as f:
        f.write("claims:\n  - id: [unclosed\n")
    rc, out = run_cli(root_cor)
    j = gate_json(root_cor)
    check("损坏注册表 rc=3", rc == 3, f"rc={rc}")
    check("损坏注册表 gate=ERROR", j.get("gate") == "ERROR", str(j.get("gate")))
    rep = open(os.path.join(root_cor, ".aeromech", "artifacts", "qa",
                            "research-quality-report.md"), encoding="utf-8").read()
    check("ERROR 报告不含 RI Gate: PASS 行", "**RI Gate: PASS**" not in rep)
    check("ERROR 项含 remediation", "remediation" in rep)

    # ---- 状态稳定性：同状态多跑一次结果一致 ----
    rc_again, _ = run_cli(root_nhr)
    j2 = gate_json(root_nhr)
    check("状态可重入（重复运行一致）",
          rc_again == 0 and j2.get("gate") == "PASS_WITH_HUMAN_REVIEW")

    print(f"test_gate_state 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
