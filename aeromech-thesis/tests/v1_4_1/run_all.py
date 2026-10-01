# -*- coding: utf-8 -*-
"""run_all.py — 运行 tests/v1_4_1 全部测试并汇总

运行：python tests/v1_4_1/run_all.py

SKIP 语义（2026-10-01）：解析各文件自报的 PASS/FAIL/SKIP 计数。只报 SKIP 而无
任何 PASS 的文件（如路径不存在的环境依赖测试）视为**未验证**，在汇总中单列并
计入退出码 1 —— 不得让"全部跳过"被当成通过。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    "test_not_applicable_qa.py",
    "test_human_review.py",
    "test_gate_state.py",
    "test_dev_install_sync.py",
    "test_false_pass_prevention.py",
    "test_integrity_identity.py",
]

_NUM = re.compile(r"(PASS|FAIL|SKIP)\s*[=:]\s*(\d+)")


def _tally(text):
    """从输出尾部解析 PASS/FAIL/SKIP 计数（取最后一次出现）。"""
    out = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for key, val in _NUM.findall(text or ""):
        out[key] = int(val)
    return out


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    failed, unverified = [], []
    totals = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for t in TESTS:
        p = subprocess.run([sys.executable, os.path.join(HERE, t)],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        out = p.stdout or ""
        tail = "\n".join(out.strip().splitlines()[-1:])
        n = _tally(tail) or _tally(out)
        for k in totals:
            totals[k] += n.get(k, 0)
        # 无任何 PASS 且无 FAIL（即全程 SKIP）→ 未验证，不算通过
        if p.returncode == 0 and n.get("PASS", 0) == 0 and n.get("SKIP", 0) > 0:
            status = "SKIP"
            unverified.append(t)
        else:
            status = "OK " if p.returncode == 0 else "FAIL"
        print(f"[{status}] {t}  rc={p.returncode}  {tail}")
        if p.returncode != 0:
            failed.append(t)
            print(out[-2000:])
            print((p.stderr or "")[-1000:])
    ok = [t for t in TESTS if t not in failed and t not in unverified]
    print(f"\nv1_4_1 测试汇总: {len(ok)}/{len(TESTS)} 通过"
          f"（PASS={totals['PASS']} FAIL={totals['FAIL']} SKIP={totals['SKIP']}）"
          + (f"；未验证（全 SKIP）: {unverified}" if unverified else "")
          + (f"；失败: {failed}" if failed else ""))
    return 0 if (not failed and not unverified) else 1


if __name__ == "__main__":
    sys.exit(main())
