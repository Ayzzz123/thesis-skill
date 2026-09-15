# -*- coding: utf-8 -*-
"""run_all.py — 运行 tests/v1_6 全部专项测试并汇总（v1.6 Full-Stack Orchestration）

运行：python tests/v1_6/run_all.py
Phase 1 模块：test_state_transition / test_checkpoint / test_material_ingestion /
test_school_context。Phase 2 模块：test_research_context / test_stage_routing。
后续 Phase 的测试文件加入 TESTS 即可。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    "test_state_transition.py",
    "test_checkpoint.py",
    "test_material_ingestion.py",
    "test_school_context.py",
    "test_research_context.py",
    "test_stage_routing.py",
    "test_orchestrator.py",
    "test_resume.py",
    "test_failure_recovery.py",
    "test_agent_loop_integration.py",
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
    print(f"\nv1_6 测试汇总: {len(TESTS) - len(failed)}/{len(TESTS)} 文件通过；"
          f"检查项合计 PASS={total_checks}")
    if failed:
        print("失败：", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
