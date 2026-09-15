# -*- coding: utf-8 -*-
"""test_research_context.py — Research Context 只读聚合视图（v1.6 §十）

纪律：Orchestrator/上层不得重新定义 RQ/Objectives/…——一律来自本视图；
本视图必须复用 v1.4/v1.5 注册表引擎（research_integrity），数值与引擎直接调用一致。
运行：python tests/v1_6/test_research_context.py
"""
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F  # v1_6 fixtures
import research_context as RC
import research_integrity as RI
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("f15", os.path.join(HERE, "..", "v1_5", "_fixtures.py"))
F15 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(F15)

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def _tree_hash(root):
    """整个 .aeromech 树的内容指纹（只读性验证用）。"""
    h = hashlib.sha256()
    for dirpath, _d, files in os.walk(os.path.join(root, ".aeromech")):
        for fn in sorted(files):
            p = os.path.join(dirpath, fn)
            h.update(fn.encode())
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


SECTIONS = ["research_questions", "objectives", "methods", "evidence", "data",
            "analysis", "claims", "conclusions", "scope", "assumptions", "limitations"]


def main():
    tmp = tempfile.mkdtemp(prefix="rc_v16_")
    print("== test_research_context ==")

    # ---------- positive：v1.5 全注册表项目 ----------
    root = F15.write_project(os.path.join(tmp, "full"))
    ctx = RC.context(root)
    check("positive status=OK", ctx["status"] == "OK", ctx.get("status"))
    check("positive 指令 §十 全部段存在", all(k in ctx for k in SECTIONS),
          str([k for k in SECTIONS if k not in ctx]))
    check("positive RQ 来自注册表（非重定义）",
          [r["id"] for r in ctx["research_questions"]] == [x["id"] for x in RI.load_registry(root, "rq")])
    check("positive objectives 聚合自 RQ", ctx["objectives"] and
          all(o for o in ctx["objectives"]))
    for sec, reg in (("methods", "methods"), ("evidence", "evidence"), ("data", "datasets"),
                     ("analysis", "analyses"), ("claims", "claims"),
                     ("conclusions", "conclusions")):
        check(f"positive {sec} 条目=引擎条目",
              len(ctx[sec]) == len(RI.load_registry(root, reg) or []))
    check("positive scope 来自 scope.yaml", ctx["scope"]["included"]
          == (RI.load_registry(root, "scope") or [{}])[0]["included"])
    cov = RI.coverage(root)
    check("positive coverage 与引擎一致（不另算）",
          ctx["summary"]["evidence_coverage_ratio"] == cov["evidence_coverage_ratio"],
          f'{ctx["summary"]["evidence_coverage_ratio"]}')
    val = RI.validate(root)
    check("positive validate 计数与引擎一致",
          len(ctx["summary"]["validation_problems"]) == len(val["problems"]))
    orph = RI.build_traceability(root)["orphans"]
    check("positive traceability orphans 与引擎一致", ctx["summary"]["traceability"]["orphans"] == orph)
    check("positive assumptions/limitations 汇聚 design+scope",
          isinstance(ctx["assumptions"], list) and len(ctx["assumptions"]) >= 1
          and isinstance(ctx["limitations"], list))
    check("positive 未初始化标记正确", ctx["summary"]["initialized"] is True)

    # ---------- 只读性 ----------
    before = _tree_hash(root)
    RC.context(root)          # 再取一次
    RC.main([root, "--json"])  # 走 CLI（默认不 --refresh-trace）
    check("hard 聚合完全只读（.aeromech 树指纹不变）", _tree_hash(root) == before)

    # ---------- legacy：无 research/ → NOT_APPLICABLE 不报错 ----------
    root2 = F.make_project(os.path.join(tmp, "legacy"))
    ctx2 = RC.context(root2)
    check("positive 旧项目 NOT_APPLICABLE（不伪造数据）",
          ctx2["status"] == "NOT_APPLICABLE" and not ctx2["research_questions"])
    rc2 = RC.main([root2, "--json"])
    check("positive 旧项目 CLI rc=0（不阻塞）", rc2 == 0, f"rc={rc2}")

    # ---------- negative：损坏注册表 → ERROR，不静默当空 ----------
    badp = os.path.join(root2, ".aeromech", "research")
    os.makedirs(badp, exist_ok=True)
    with open(os.path.join(badp, "rq.yaml"), "w", encoding="utf-8") as f:
        f.write("RQs: [broken\n  indent")
    ctx3 = RC.context(root2)
    check("negative 损坏注册表→status=ERROR（rc 3 路径）",
          ctx3["status"] == "ERROR" and ctx3.get("detail"), str(ctx3)[:120])
    rc3 = RC.main([root2, "--json"])
    check("negative CLI 损坏 rc=3", rc3 == 3, f"rc={rc3}")

    # ---------- boundary：部分初始化（仅 rq 存在=已初始化） ----------
    root4 = F.make_project(os.path.join(tmp, "partial"))
    os.makedirs(os.path.join(root4, ".aeromech", "research"), exist_ok=True)
    RI.save_registry(root4, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    ctx4 = RC.context(root4)
    check("boundary 部分注册表→OK，缺的段为空列表不崩溃",
          ctx4["status"] == "OK" and len(ctx4["research_questions"]) == 1
          and ctx4["claims"] == [])
    check("boundary conflicts_open 只计 pending", ctx4["summary"]["conflicts_open"] == [])

    # ---------- CLI 文本模式冒烟 ----------
    rct = RC.main([root])
    check("positive CLI 默认文本模式 rc=0", rct == 0)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_research_context 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
