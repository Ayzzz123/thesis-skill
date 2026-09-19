# -*- coding: utf-8 -*-
"""test_golden_samples.py — v1.6.5 §十三：golden samples 基线测试

golden 是视觉系统的"合同"：
  GOLD-01 四样张 + layout + manifest 齐备（缺→先生成）
  GOLD-02 每个 golden 自身过 VIS 全链（无 FAIL；不可测项只允许 SKIP/NHR）
  GOLD-03 跨样张视觉家族一致（VIS-12 PASS：字族/线宽/色板白名单/来源）
  GOLD-04 语义角色覆盖（fault_tree 样张必须用 top_event/gate/basic_event 三角色）
  GOLD-05 chart 样张带 axes_rect/bars/lines 元数据（GQ chart 检查与 VIS-11 输入）
  GOLD-06 重生成幂等（同代码两次生成 layout 数值一致 → 视觉回归基线可信）

运行：python tests/v1_6_5/test_golden_samples.py
"""
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
GOLDEN = os.path.join(HERE, "golden")

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def main():
    print("== test_golden_samples ==")
    # GOLD-01：存在性（缺失则生成一次）
    if not glob.glob(os.path.join(GOLDEN, "*.layout.json")):
        import make_golden_samples
        make_golden_samples.main()
    layouts = sorted(glob.glob(os.path.join(GOLDEN, "*.layout.json")))
    check("GOLD-01 四样张+manifest 齐备", len(layouts) == 4
          and os.path.isfile(os.path.join(GOLDEN, "golden-manifest.json")))

    import figure_visual_qa as VQ
    import figure_style as ST

    # GOLD-02：每个 golden 自身过 VIS（无 FAIL）
    class Rep:
        def __init__(self): self.items = []
        def add(self, code, name, status, severity, evidence, reason, suggestion=""):
            self.items.append({"code": code, "status": status, "severity": severity,
                               "evidence": evidence})
    ok2 = True
    detail = []
    types = {"golden_fault_tree": "fault_tree", "golden_stat_bar": "stat_bar",
             "golden_tech_route": "tech_route", "golden_stat_line": "stat_line"}
    for key, ftype in types.items():
        meta = json.load(open(os.path.join(GOLDEN, key + ".layout.json"), encoding="utf-8"))
        png = os.path.join(GOLDEN, key + ".png")
        r = Rep()
        VQ.vis_01_layout_balance(r, key, meta)
        VQ.vis_02_density(r, key, meta, png, ftype)
        VQ.vis_03_typography(r, key, meta, scale=14.4 / meta.get("w_cm", 16.5))
        VQ.vis_04_color_harmony(r, key, meta)
        VQ.vis_05_contrast(r, key, meta)
        VQ.vis_06_semantic_color(r, key, meta)
        VQ.vis_07_whitespace(r, key, meta)
        VQ.vis_08_alignment(r, key, meta)
        VQ.vis_09_academic_style(r, key, meta, png)
        VQ.vis_11_type_appropriateness(r, key, meta, ftype)
        fails = [i for i in r.items if i["status"] == VQ.FAIL]
        if fails:
            ok2 = False
            detail.append(f"{key}: {[(f['code'], f['evidence']) for f in fails]}")
    check("GOLD-02 golden 自身过 VIS 全链（无 FAIL）", ok2, "; ".join(detail))

    # GOLD-03：跨样张家族一致
    metas = {os.path.basename(p)[:-12]: json.load(open(p, encoding="utf-8"))
             for p in layouts}
    r = Rep()
    VQ.vis_12_cross_figure(r, metas)
    check("GOLD-03 跨样张视觉家族一致（VIS-12 PASS）",
          r.items and r.items[0]["status"] == VQ.PASS,
          str(r.items[0] if r.items else None))

    # GOLD-04：语义角色覆盖
    ft = metas.get("golden_fault_tree", {})
    roles = {b.get("role") for b in ft.get("boxes") or []}
    check("GOLD-04 故障树样张含三层语义角色",
          {"top_event", "gate", "basic_event"} <= roles, str(roles))

    # GOLD-05：chart 元数据
    bar = metas.get("golden_stat_bar", {})
    line = metas.get("golden_stat_line", {})
    check("GOLD-05 chart 样张带 axes_rect/bars/lines",
          bool(bar.get("axes_rect")) and len(bar.get("bars") or []) == 6
          and bool(line.get("axes_rect")) and len(line.get("lines") or []) == 2)

    # GOLD-06：幂等重生成
    tmp = os.path.join(HERE, "_regen_check")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    sys.path.insert(0, HERE)
    import make_golden_samples as MG
    orig_out = MG.OUT
    MG.OUT = tmp
    try:
        MG.fault_tree()
    finally:
        MG.OUT = orig_out
    a = json.load(open(os.path.join(GOLDEN, "golden_fault_tree.layout.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(tmp, "golden_fault_tree.layout.json"), encoding="utf-8"))
    keyf = lambda m: (m["boxes"], m["min_font_pt"], m["style_fingerprint"])
    check("GOLD-06 重生成幂等（boxes/min_font/指纹一致）", keyf(a) == keyf(b))
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"test_golden_samples 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
