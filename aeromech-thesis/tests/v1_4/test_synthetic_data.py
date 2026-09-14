# -*- coding: utf-8 -*-
"""test_synthetic_data.py — Synthetic Data Ledger 与身份保持（PASS/FAIL/boundary）

运行：python tests/v1_4/test_synthetic_data.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import research_integrity as RI
import research_quality_qa as RQ

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def run_rq(root):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        s, rep = RQ.run(root)
    return s, rep


def item(rep, code):
    return next((i for i in rep.items if i["code"] == code), None)


def mutate(root, reg, fn):
    items = RI.load_registry(root, reg)
    fn(items)
    RI.save_registry(root, reg, items)


def probe(root, reg, iid, **kw):
    def fn(items):
        it = next(x for x in items if x["id"] == iid)
        it.update(kw)
    mutate(root, reg, fn)


def main():
    tmp = tempfile.mkdtemp(prefix="ri_v14_ds_")
    print("== test_synthetic_data ==")

    # ---- 正例 ----
    root = F.write_project(os.path.join(tmp, "pos"))
    ds = RI.load_registry(root, "datasets")[0]
    check("DS-001 type=simulated", ds["type"] == "simulated")
    check("label 含模拟标记", RI.SYNTH_LABEL in ds["label"])
    for f in ("reason", "assumptions", "generation_method", "limitations"):
        check(f"模拟数据集必备字段 {f}", bool(ds.get(f)))
    val = RI.validate(root)
    check("正例 validate ok", val["ok"], str(val["problems"][:2]))
    s, rep = run_rq(root)
    check("RQG-06 PASS", item(rep, "RQG-06")["status"] == "PASS")
    check("RQG-05 PASS", item(rep, "RQG-05")["status"] == "PASS")
    check("正例 gate=PASS_WITH_HUMAN_REVIEW（v1.4.1）", s["gate"] == "PASS_WITH_HUMAN_REVIEW", str(s["gate"]))

    # ---- FAIL/Critical：模拟数据无标记 ----
    root2 = F.write_project(os.path.join(tmp, "nolabel"), variant="unlabeled_synthetic")
    val2 = RI.validate(root2)
    check("缺 label 报 RI-DS-LABEL critical",
          any(p["code"] == "RI-DS-LABEL" for p in val2["problems"]), str(val2["problems"][:2]))
    s2, rep2 = run_rq(root2)
    check("缺 label RQG-06 FAIL(Critical)", item(rep2, "RQG-06")["status"] == "FAIL"
          and item(rep2, "RQG-06")["severity"] == "Critical")
    check("缺 label gate=FAIL", s2["gate"] == "FAIL")

    # ---- FAIL：标记未出现在文档文本 ----
    root3 = F.write_project(os.path.join(tmp, "notext"), variant="synthetic_label_not_in_text")
    s3, rep3 = run_rq(root3)
    check("标记未入文 RQG-06 FAIL(High)", item(rep3, "RQG-06")["status"] == "FAIL"
          and item(rep3, "RQG-06")["severity"] == "High")

    # ---- FAIL：缺 generation_method ----
    root4 = F.write_project(os.path.join(tmp, "nogen"))
    probe(root4, "datasets", "DS-001", generation_method="")
    val4 = RI.validate(root4)
    check("缺生成方法报 RI-DS-SYNTH",
          any(p["code"] == "RI-DS-SYNTH" for p in val4["problems"]), str(val4["problems"][:2]))

    # ---- boundary：type=assumption 同样要求 label/字段（身份不升级）----
    root5 = F.write_project(os.path.join(tmp, "assume"), variant="assumption_dataset")
    val5 = RI.validate(root5)
    check("assumption 数据集合法（字段齐备）", val5["ok"], str(val5["problems"][:2]))
    s5, rep5 = run_rq(root5)
    check("assumption RQG-06 PASS", item(rep5, "RQG-06")["status"] == "PASS")

    # ---- boundary：真实数据（type=real）必须有 source_location ----
    root6 = F.write_project(os.path.join(tmp, "real"))

    def _to_real(items):
        items[0].update({"type": "real", "source_location": ""})
    mutate(root6, "datasets", _to_real)
    s6, rep6 = run_rq(root6)
    check("真实数据缺出处 RQG-05 FAIL", item(rep6, "RQG-05")["status"] == "FAIL")
    # 补上出处后通过
    probe(root6, "datasets", "DS-001", source_location="某航司维修记录（用户提供）")
    val6b = RI.validate(root6)
    s6b, rep6b = run_rq(root6)
    check("补出处后 RQG-05 PASS", item(rep6b, "RQG-05")["status"] == "PASS", str(val6b["problems"][:2]))

    print(f"test_synthetic_data 结果: PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
