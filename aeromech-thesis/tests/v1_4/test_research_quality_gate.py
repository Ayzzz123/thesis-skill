# -*- coding: utf-8 -*-
"""test_research_quality_gate.py — RQG 门禁 CLI/退出码/报告文件（端到端）

运行：python tests/v1_4/test_research_quality_gate.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F

SCRIPT = os.path.join(SKILL, "scripts", "research_quality_qa.py")
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
    p = subprocess.run([sys.executable, SCRIPT, "--project", root],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=SKILL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load_json(root):
    p = os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality.json")
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_gate_")
    print("== test_research_quality_gate ==")

    # ---- 正例：exit 0，报告/JSON 落盘 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    rc, out = run_cli(root)
    check("正例 exit=0", rc == 0, out[-160:])
    md = os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality-report.md")
    check("报告文件存在", os.path.isfile(md))
    body = open(md, encoding="utf-8").read()
    check("报告含 RI Gate: PASS", "RI Gate: PASS" in body)
    check("报告含 RQG-01~15 全部检查项",
          all(f"RQG-{i:02d}" in body for i in range(1, 16)))
    j = load_json(root)
    check("JSON gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", j and j["gate"] == "PASS_WITH_HUMAN_REVIEW", str(j and j["gate"]))
    check("JSON 含 coverage", j and j["coverage"]["evidence_coverage_ratio"] == 1.0)

    # ---- FAIL/Critical：exit 1 且原因可读 ----
    root2 = F.write_project(os.path.join(tmp, "overreach"), variant="overreach_claim")
    rc2, out2 = run_cli(root2)
    check("越界 exit=1", rc2 == 1)
    j2 = load_json(root2)
    check("越界 gate=FAIL", j2["gate"] == "FAIL")
    check("越界 fails 含 RQG-10/Critical",
          any(c == "RQG-10" and s == "Critical" for c, s, _ in j2["fails"]), str(j2["fails"]))

    # ---- 未初始化（旧项目兼容）：exit 2 且有 WARN 记录，不视为 Critical/High ----
    root3 = F.make_empty_project(tmp, "uninit")
    rc3, out3 = run_cli(root3)
    check("未初始化 exit=2", rc3 == 2, out3[-160:])
    j3 = load_json(root3)
    check("未初始化 gate=not_initialized", j3 and j3["gate"] == "not_initialized")
    md3 = os.path.join(root3, ".aeromech", "artifacts", "qa", "research-quality-report.md")
    check("未初始化仍写报告（旧项目可解释）", os.path.isfile(md3)
          and "未初始化" in open(md3, encoding="utf-8").read())

    # ---- boundary：不存在的项目目录 → exit 2 ----
    rc4, _ = run_cli(os.path.join(tmp, "does_not_exist"))
    check("不存在目录 exit=2", rc4 == 2)

    # ---- boundary：多个 Critical 同时存在时全部进入 fails ----
    root5 = F.write_project(os.path.join(tmp, "multi"), variant="overreach_claim")
    # 再叠加一个模拟数据无标记
    items = None
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    import research_integrity as RI
    items = RI.load_registry(root5, "datasets")
    items[0]["label"] = ""
    RI.save_registry(root5, "datasets", items)
    rc5, _ = run_cli(root5)
    j5 = load_json(root5)
    codes = {c for c, s, _ in j5["fails"]}
    check("多 Critical 并存（RQG-10+RQG-06/RQG-00）",
          rc5 == 1 and "RQG-10" in codes and ({"RQG-06", "RQG-00"} & codes), str(codes))

    print(f"test_research_quality_gate 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
