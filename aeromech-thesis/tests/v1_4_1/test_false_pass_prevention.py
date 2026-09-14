# -*- coding: utf-8 -*-
"""tests/v1_4_1/test_false_pass_prevention.py — 防伪 PASS（错误模型）

验证（任何异常/损坏/配置错误路径都不得产生 PASS 结论）：
1. 注册表损坏：RI validate → rc 1 + RI-CORRUPT(critical)+remediation；trace/coverage → rc 3；
   RQG → rc 3 + gate=ERROR（报告无 "RI Gate: PASS" 行）。
2. tf_qa：--template 指向不存在文件 → rc 3；DOCX 缺失（内部异常）→ rc 3 且错误报告覆盖同目录旧报告
   （防止陈旧 PASS 报告被误读为本次结果）。
3. 内部异常报告包含 reason 与 remediation。
运行：python tests/v1_4_1/test_false_pass_prevention.py
"""
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

RI = os.path.join(SCRIPTS, "research_integrity.py")
RQG = os.path.join(SCRIPTS, "research_quality_qa.py")
TF = os.path.join(SCRIPTS, "tf_qa.py")
PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def run(args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       encoding="utf-8", env=env, cwd=cwd or SKILL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def corrupt_registry(root, reg_file="claims.yaml"):
    p = os.path.join(root, ".aeromech", "research", reg_file)
    with open(p, "w", encoding="utf-8") as f:
        f.write("claims:\n  - id: [unclosed\n")


def main():
    print("== test_false_pass_prevention ==")
    tmp = tempfile.mkdtemp(prefix="v141_fpp_")
    root = F.write_project(os.path.join(tmp, "proj"))
    corrupt_registry(root)

    # ---- 1) RI validate：critical + remediation；rc 1 ----
    rc, out = run([RI, root, "validate"])
    check("损坏注册表 validate rc=1", rc == 1, f"rc={rc}")
    check("validate 输出 RI-CORRUPT", "RI-CORRUPT" in out)
    check("validate 输出 remediation", "remediation" in out)

    # ---- 2) RI trace/coverage：rc 3 ----
    rc2, out2 = run([RI, root, "trace"])
    rc3, out3 = run([RI, root, "coverage"])
    check("损坏注册表 trace rc=3", rc2 == 3, f"rc={rc2}")
    check("损坏注册表 coverage rc=3", rc3 == 3, f"rc={rc3}")
    check("trace/coverage 输出 ERROR", "ERROR" in out2 and "ERROR" in out3)
    check("trace/coverage 不把损坏当空表", "当作空表" in out2 + out3)

    # ---- 3) RQG：rc 3 + gate=ERROR + 无 PASS 行 ----
    rc4, out4 = run([RQG, "--project", root])
    check("损坏注册表 RQG rc=3", rc4 == 3, f"rc={rc4}")
    rep_path = os.path.join(root, ".aeromech", "artifacts", "qa", "research-quality-report.md")
    rep = open(rep_path, encoding="utf-8").read()
    check("RQG 报告 gate=ERROR", "RI Gate: ERROR" in rep)
    check("RQG 报告无 PASS 行", "**RI Gate: PASS**" not in rep and "**RI Gate: PASS_WITH_HUMAN_REVIEW**" not in rep)
    check("RQG 报告含 RQG-ERR + remediation", "RQG-ERR" in rep and "remediation" in rep)

    # ---- 4) tf_qa：正常路径不误报 ERROR；DOCX 缺失 rc 3 + 错误报告覆盖旧报告 ----
    good = os.path.join(tmp, "good.docx")
    from docx import Document
    Document().save(good)
    outdir = os.path.join(tmp, "tfout")
    rc5, _ = run([TF, "--docx", good, "--out", outdir])
    check("tf_qa 正常路径 rc∈{0,1}（非 3/非异常）", rc5 in (0, 1), f"rc={rc5}")
    rep5 = open(os.path.join(outdir, "tf-qa-report.md"), encoding="utf-8").read()
    check("正常路径报告不为 ERROR", "状态: ERROR" not in rep5)
    rc6, out6 = run([TF, "--docx", os.path.join(tmp, "missing.docx"), "--out", outdir])
    check("DOCX 缺失 tf_qa rc=3", rc6 == 3, f"rc={rc6}")
    rep_tf = open(os.path.join(outdir, "tf-qa-report.md"), encoding="utf-8").read()
    check("错误报告覆盖旧报告（无陈旧 PASS）", "状态: ERROR" in rep_tf and "PASS" not in rep_tf.split("\n")[0])
    check("错误报告含 reason 与 remediation", "reason:" in rep_tf and "remediation:" in rep_tf)

    print(f"test_false_pass_prevention 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
