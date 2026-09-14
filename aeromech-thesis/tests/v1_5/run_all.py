# -*- coding: utf-8 -*-
"""run_all.py — 运行 tests/v1_5 全部专项测试并汇总（v1.5 Research Intelligence & Agent Loop）

运行：python tests/v1_5/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    "test_research_design.py",
    "test_method_selection.py",
    "test_feasibility.py",
    "test_claim_strength.py",
    "test_diagnosis.py",
    "test_root_cause.py",
    "test_repair_plan.py",
    "test_auto_repair.py",
    "test_agent_loop.py",
    "test_quality_score.py",
    "test_scope_control.py",
    "test_quantitative_consistency.py",
    "test_human_review_loop.py",
]


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    failed, total_checks = [], 0
    for t in TESTS:
        p = subprocess.run([sys.executable, os.path.join(HERE, t)],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        tail = (p.stdout or "").strip().splitlines()[-1] if (p.stdout or "").strip() else ""
        status = "OK  " if p.returncode == 0 else "FAIL"
        print(f"[{status}] {t}  rc={p.returncode}  {tail}")
        if p.returncode != 0:
            failed.append(t)
            print((p.stdout or "")[-2500:])
            print((p.stderr or "")[-1000:])
        else:
            try:
                total_checks += int(tail.split("PASS=")[1].split()[0])
            except Exception:
                pass
    print(f"\nv1_5 测试汇总: {len(TESTS) - len(failed)}/{len(TESTS)} 文件通过"
          f"；检查项合计 PASS={total_checks}"
          + (f"；失败: {failed}" if failed else ""))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
