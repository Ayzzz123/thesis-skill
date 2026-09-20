# -*- coding: utf-8 -*-
"""run_all.py — 运行 tests/v1_6_5 全部专项测试并汇总（v1.6.5 Academic Visual System）

Phase 1 模块：test_visual_system（style/颜色/字体/VIS 负例/fallback-critical/集成）、
test_golden_samples（golden 基线：自验/家族一致/幂等）。
运行：python tests/v1_6_5/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    "test_visual_system.py",
    "test_golden_samples.py",
    # v1.6.5 Phase 2A：Image Provider（可选增强 + 兼容回落 + 凭据安全）
    "test_image_config.py",
    "test_image_resolution.py",
    "test_image_fallback.py",
    "test_image_security.py",
    "test_image_external.py",
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
            print((p.stderr or "")[-1500:])
        for tok in tail.replace("=", " ").split():
            if tok.isdigit():
                total_checks += int(tok)
    print(f"\nv1_6_5 测试汇总: {len(TESTS) - len(failed)}/{len(TESTS)} 文件通过；"
          f"检查项合计 PASS={total_checks}")
    if failed:
        print("失败：", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
