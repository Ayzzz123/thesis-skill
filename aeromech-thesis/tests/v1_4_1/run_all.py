# -*- coding: utf-8 -*-
"""run_all.py — 运行 tests/v1_4_1 全部测试并汇总

运行：python tests/v1_4_1/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    "test_not_applicable_qa.py",
    "test_human_review.py",
    "test_gate_state.py",
    "test_dev_install_sync.py",
    "test_false_pass_prevention.py",
]


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    failed = []
    for t in TESTS:
        p = subprocess.run([sys.executable, os.path.join(HERE, t)],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        tail = "\n".join((p.stdout or "").strip().splitlines()[-1:])
        status = "OK " if p.returncode == 0 else "FAIL"
        print(f"[{status}] {t}  rc={p.returncode}  {tail}")
        if p.returncode != 0:
            failed.append(t)
            print((p.stdout or "")[-2000:])
            print((p.stderr or "")[-1000:])
    print(f"\nv1_4_1 测试汇总: {len(TESTS) - len(failed)}/{len(TESTS)} 通过"
          + (f"；失败: {failed}" if failed else ""))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
