# -*- coding: utf-8 -*-
"""tests/run_all.py — aeromech-thesis 顶层统一测试入口（v1.6.5）

一次执行全部套件并给出统一汇总：

    v1_4 · v1_4_1 · v1_5 · v1_6 · v1_6_5 · Test A · Test B

判定规则（fail-closed，与各套件内部语义一致）：
  1. 任一套件存在真实 FAIL → 总体 FAIL（退出码 1）；
  2. 任一套件只有 SKIP、没有任何 PASS → 总体 FAIL（未验证 ≠ 通过）；
  3. SKIP **永不计入 PASS**；
  4. 套件崩溃（非 0 退出码）→ 记为 FAIL 并回显尾部日志。

各套件自身的退出码与断言语义保持不变——本入口只做编排与汇总。
环境不可用导致的 SKIP 会如实单列，但不会让总体"因跳过而通过"。

用法：
    python tests/run_all.py               # 跑全部
    python tests/run_all.py --only v1_6   # 只跑指定套件（逗号分隔）
    python tests/run_all.py --list        # 列出套件
退出码：0=全部通过；1=存在 FAIL 或"全 SKIP"套件
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (显示名, 相对 tests/ 的路径, 是否为目录型套件)
SUITES = [
    ("v1_4", os.path.join("v1_4", "run_all.py"), True),
    ("v1_4_1", os.path.join("v1_4_1", "run_all.py"), True),
    ("v1_5", os.path.join("v1_5", "run_all.py"), True),
    ("v1_6", os.path.join("v1_6", "run_all.py"), True),
    ("v1_6_5", os.path.join("v1_6_5", "run_all.py"), True),
    ("TestA", "test_a_template_fidelity.py", False),
    ("TestB", "test_b_format_reconstruction.py", False),
]

# 各套件汇总行的 PASS/FAIL/SKIP 计数形态不一，逐个模式尝试解析
_NUM_PATTERNS = [
    re.compile(r"(PASS|FAIL|SKIP)\s*[=:]\s*(\d+)"),
    re.compile(r"结果:\s*PASS=(\d+)\s+FAIL=(\d+)(?:\s+SKIP=(\d+))?"),
    re.compile(r"(\d+)/(\d+)\s*(?:文件)?通过"),
]


def _tally(text):
    """从套件输出中解析 PASS/FAIL/SKIP 计数（取最后一次出现）。"""
    out = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for key, val in _NUM_PATTERNS[0].findall(text or ""):
        out[key] = int(val)
    return out


def _ok_ratio(text):
    """'n/m 通过' 形态（v1_4 / v1_4_1 等）：返回 (n, m) 或 None。"""
    m = None
    for mm in _NUM_PATTERNS[2].finditer(text or ""):
        m = mm
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def run_suite(name, rel, is_dir, env):
    path = os.path.join(HERE, rel)
    if not os.path.isfile(path):
        return {"name": name, "rc": 127, "status": "FAIL",
                "reason": f"套件入口不存在: {rel}", "tail": "",
                "counts": {"PASS": 0, "FAIL": 0, "SKIP": 0}}
    p = subprocess.run([sys.executable, path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    counts = _tally(out)
    tail = ""
    for ln in reversed((p.stdout or "").strip().splitlines()):
        if ln.strip():
            tail = ln.strip()
            break
    # 套件只报 "n/m 通过" 而无显式计数时，用比例补齐 PASS/FAIL 口径
    if counts["PASS"] == 0 and counts["FAIL"] == 0:
        ratio = _ok_ratio(out)
        if ratio:
            counts["PASS"], counts["FAIL"] = ratio[0], ratio[1] - ratio[0]
    if p.returncode != 0:
        status = "FAIL"
        reason = f"套件退出码 {p.returncode}"
    elif counts["PASS"] == 0 and counts["SKIP"] > 0:
        status = "SKIP"
        reason = "全部跳过，无有效断言（未验证 ≠ 通过）"
    elif counts["PASS"] == 0 and counts["FAIL"] == 0:
        status = "FAIL"
        reason = "无任何断言产出（疑似空跑），不得视为通过"
    else:
        status = "PASS"
        reason = ""
    return {"name": name, "rc": p.returncode, "status": status, "reason": reason,
            "tail": tail, "counts": counts, "output": out}


def main():
    ap = argparse.ArgumentParser(description="aeromech-thesis 顶层测试入口")
    ap.add_argument("--only", default=None, help="只跑指定套件（逗号分隔）")
    ap.add_argument("--list", action="store_true", help="列出套件后退出")
    a = ap.parse_args()

    if a.list:
        for n, rel, _d in SUITES:
            print(f"{n:<10} {rel}")
        return 0

    picked = SUITES
    if a.only:
        want = {s.strip().lower() for s in a.only.split(",") if s.strip()}
        picked = [s for s in SUITES if s[0].lower() in want]
        if not picked:
            print(f"[ERROR] --only 未匹配任何套件；可用：{', '.join(s[0] for s in SUITES)}")
            return 1

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    print("=" * 72)
    print("aeromech-thesis 全量测试")
    print("=" * 72)

    results, total = [], {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for name, rel, is_dir in picked:
        r = run_suite(name, rel, is_dir, env)
        results.append(r)
        for k in total:
            total[k] += r["counts"].get(k, 0)
        mark = {"PASS": "OK  ", "FAIL": "FAIL", "SKIP": "SKIP"}[r["status"]]
        line = f"[{mark}] {name:<8} rc={r['rc']:<3} PASS={r['counts']['PASS']:<4} " \
               f"FAIL={r['counts']['FAIL']:<3} SKIP={r['counts']['SKIP']:<3} {r['tail'][:60]}"
        print(line)
        if r["status"] != "PASS":
            print(f"         └─ {r['reason']}")

    failed = [r["name"] for r in results if r["status"] == "FAIL"]
    skipped = [r["name"] for r in results if r["status"] == "SKIP"]

    print("-" * 72)
    print(f"套件: {len(results) - len(failed) - len(skipped)}/{len(results)} 通过"
          f"（PASS={total['PASS']} FAIL={total['FAIL']} SKIP={total['SKIP']}）")
    if failed:
        print(f"失败套件: {', '.join(failed)}")
    if skipped:
        print(f"未验证套件（全 SKIP，不计为通过）: {', '.join(skipped)}")
    ok = not failed and not skipped
    print(f"总体结果: {'PASS' if ok else 'FAIL'}")

    # 失败时回显尾部日志（便于定位，不打印全部）
    for r in results:
        if r["status"] == "FAIL":
            print(f"\n---- {r['name']} 尾部输出 ----")
            print(r["output"][-1500:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
