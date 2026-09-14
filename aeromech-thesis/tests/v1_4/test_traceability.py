# -*- coding: utf-8 -*-
"""test_traceability.py — Research Traceability Graph（RQ→M→E/DS→AN→CALC→CL→CON→FIG/TABLE）

运行：python tests/v1_4/test_traceability.py
"""
import json
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


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_trace_")
    print("== test_traceability ==")

    root = F.write_project(os.path.join(tmp, "pos"))
    t = RI.build_traceability(root)
    nodes = {n["id"]: n for n in t["nodes"]}
    edges = {tuple(e) for e in t["edges"]}

    # 链条关键边存在
    chains = [
        ("RQ-01", "M-001"), ("RQ-01", "AN-001"), ("RQ-01", "CON-001"),
        ("RQ-02", "M-001"), ("RQ-02", "AN-002"),
        ("DS-001", "AN-001"), ("E-001", "AN-001"),
        ("AN-001", "TABLE-001"), ("AN-002", "FIG-001"),
        ("DS-001", "CALC-001"), ("CALC-001", "CL-002"), ("CALC-001", "TABLE-001"),
        ("E-001", "CL-001"), ("E-002", "CL-001"), ("E-003", "CL-002"),
        ("AN-001", "CL-001"), ("CL-001", "CON-001"), ("CL-002", "CON-001"),
        ("CL-001", "CON-002"), ("RQ-01", "TABLE-001"), ("RQ-02", "FIG-001"),
    ]
    missing = [c for c in chains if c not in edges]
    check("关键链路边完整", not missing, str(missing))

    # 节点类型
    check("DS-001 节点类型=DS", nodes["DS-001"]["type"] == "DS")
    check("CALC-001 节点类型=CALC", nodes["CALC-001"]["type"] == "CALC")
    check("TABLE-001 节点类型=TABLE", nodes["TABLE-001"]["type"] == "TABLE")
    check("FIG-001 节点类型=FIG", nodes["FIG-001"]["type"] == "FIG")

    # 可达性：核心结论/论断 in_chain
    core = ["CL-001", "CL-002", "CON-001", "CON-002"]
    check("核心 CL/CON 全部 in_chain", all(nodes[c]["in_chain"] for c in core),
          str({c: nodes[c]["in_chain"] for c in core}))
    check("正例 orphans=[]", t["orphans"] == [], str(t["orphans"]))

    # 落盘 JSON
    p, t2 = RI.save_traceability(root)
    check("traceability.json 生成", os.path.isfile(p))
    loaded = json.load(open(p, encoding="utf-8"))
    check("JSON 可回读且边一致", {tuple(e) for e in loaded["edges"]} == edges)

    # FAIL：孤立 claim（无论证链）
    root2 = F.write_project(os.path.join(tmp, "orphan"), variant="orphan_claim")
    t3 = RI.build_traceability(root2)
    check("孤立 CL-003 被标记 orphan", "CL-003" in t3["orphans"], str(t3["orphans"]))
    n3 = {n["id"]: n for n in t3["nodes"]}
    check("CL-003 in_chain=False", n3["CL-003"]["in_chain"] is False)

    # boundary：RQ 无 related_conclusions 时图仍可构建（不报错、不产生悬空节点）
    root3 = F.write_project(os.path.join(tmp, "nocon"))
    items = RI.load_registry(root3, "rq")
    items[0]["related_conclusions"] = []
    RI.save_registry(root3, "rq", items)
    t4 = RI.build_traceability(root3)
    check("boundary 无 related_conclusions 可构建", len(t4["nodes"]) > 0 and t4["orphans"] == [])

    print(f"test_traceability 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
