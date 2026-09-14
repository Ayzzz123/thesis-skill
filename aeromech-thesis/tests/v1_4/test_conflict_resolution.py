# -*- coding: utf-8 -*-
"""test_conflict_resolution.py — Conflict Resolution 注册与"不得静默选择"

运行：python tests/v1_4/test_conflict_resolution.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_integrity as RI

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def mutate(root, reg, fn):
    items = RI.load_registry(root, reg)
    fn(items)
    RI.save_registry(root, reg, items)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_cf_")
    print("== test_conflict_resolution ==")

    # ---- 正例：冲突登记齐备 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    cf = RI.load_registry(root, "conflicts")[0]
    for f in ("source_a", "source_b", "conflict", "resolution", "reason", "status"):
        check(f"冲突字段 {f} 存在", bool(cf.get(f)))
    val = RI.validate(root)
    check("正例 validate ok（冲突合法）", val["ok"], str(val["problems"][:2]))

    # ---- FAIL：resolution/reason 缺失（视为静默选择风险）----
    root2 = F.write_project(os.path.join(tmp, "noreason"), variant="conflict_missing_reason")
    val2 = RI.validate(root2)
    check("缺 reason 报 RI-CF-FIELD",
          any(p["code"] == "RI-CF-FIELD" for p in val2["problems"]), str(val2["problems"][:2]))
    check("缺 reason validate not ok", not val2["ok"])

    # ---- boundary：status=pending（待核实）合法，不阻塞为 Critical/High ----
    root3 = F.write_project(os.path.join(tmp, "pending"), variant="conflict_pending")
    val3 = RI.validate(root3)
    check("pending 合法", val3["ok"], str(val3["problems"][:2]))

    # ---- boundary：非法 status → medium（不阻塞但登记）----
    root4 = F.write_project(os.path.join(tmp, "badstatus"), variant="conflict_bad_status")
    val4 = RI.validate(root4)
    check("非法 status 报 RI-CF-STATUS(medium)",
          any(p["code"] == "RI-CF-STATUS" and p["severity"] == "medium" for p in val4["problems"]),
          str(val4["problems"][:2]))
    check("非法 status 不阻塞（ok 仍 True）", val4["ok"])

    # ---- boundary：无 conflicts 注册表文件 → validate 不受影响 ----
    root5 = F.write_project(os.path.join(tmp, "nofile"))
    os.remove(os.path.join(root5, ".aeromech", "research", "conflicts.yaml"))
    val5 = RI.validate(root5)
    check("无 conflicts.yaml 时 validate ok", val5["ok"], str(val5["problems"][:2]))

    print(f"test_conflict_resolution 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
