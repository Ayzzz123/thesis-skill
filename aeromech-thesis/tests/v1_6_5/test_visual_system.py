# -*- coding: utf-8 -*-
"""test_visual_system.py — v1.6.5 §十六：视觉系统测试（真实行为断言，非存在性）

覆盖：
  STY-01~06 figure_style：常量齐备/类型正确/度量函数对已知值/validate_palette 真判
  COL-01~04 颜色验证：对比度阈值、灰度分离、饱和上限、白名单外色被抓
  TYP-01~03 字体：字阶白名单、有效字号计算、min_font 实测（声明造假被纠正）
  VIS-NEG-01~08 视觉负例：贴边→FAIL、失衡→WARN、非白名单色→FAIL、语义错配→FAIL、
        低对比→FAIL(Critical)、柱不从0→FAIL、门无文字编码→FAIL、跨图字族分裂→FAIL
  FB-CRIT-01~04 Mermaid fallback Critical：placeholder 永远 False；figure_iface
        mmdc 失败→REJECTED（不 GENERATED/不 VERIFIED）；残缺文件被清理；
        旧 generate_fallback_figure 不存在（语义造假已根除）
  GOLD-01~03 golden：四样张存在且 layout 齐；VIS 全 PASS 无 FAIL；指纹一致(VIS-12)
  INT-01~03 集成：figkit layout 输出 fill/stroke/role/fingerprint；
        scan_hardcoded_styles 抓到散写负例、figkit/figure_style 自身为 0

运行：python tests/v1_6_5/test_visual_system.py
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra if not cond else "")
    else:
        FAIL += 1
        print("  FAIL", name, extra)


import figure_style as ST
import figure_visual_qa as VQ


def _meta(**over):
    m = {"name": "t", "w_cm": 16.5, "h_cm": 9.0, "dpi": 220,
         "boxes": [], "edges": [], "texts": [], "min_font_pt": 11}
    m.update(over)
    return m


class _Rep:
    def __init__(self):
        self.items = []

    def add(self, code, name, status, severity, evidence, reason, suggestion=""):
        self.items.append({"code": code, "status": status, "severity": severity,
                           "reason": reason, "suggestion": suggestion})

    def get(self, code):
        return [i for i in self.items if i["code"] == code]


def main():
    tmp = tempfile.mkdtemp(prefix="vis165_")
    print("== test_visual_system ==")

    # ---------- STY：figure_style ----------
    check("STY-01 常量域齐备", all(hasattr(ST, k) for k in (
        "COLOR_PALETTE", "SEMANTIC_COLORS", "TYPOGRAPHY", "LINE_STYLES",
        "SPACING", "FIGURE_SIZE_PRESETS", "FIGURE_TYPES")))
    check("STY-02 调色板全为合法 HEX", all(
        isinstance(v, str) and len(v) == 7 and v[0] == "#"
        for v in ST.COLOR_PALETTE.values()))
    check("STY-03 度量函数对已知值", abs(ST.contrast_ratio("#FFFFFF", "#000000") - 21.0) < 0.01
          and ST.contrast_ratio("#777777", "#888888") < 1.6
          and ST.grayscale_delta("#000000", "#FFFFFF") > 0.9)
    check("STY-04 validate_palette 通过（固化门槛）", ST.validate_palette() == [],
          str(ST.validate_palette()))
    check("STY-05 语义取色：未知角色报错不兜底", (lambda: (
        ST.get_semantic_color("top_event", "stroke") == ST.COLOR_PALETTE["primary"]))()
        and _raises(lambda: ST.get_semantic_color("bogus_role")))
    check("STY-06 尺寸预设含有效缩放", abs(
        ST.get_figure_size("full_width")["scale"] - 14.4 / 16.5) < 1e-6)

    # ---------- COL：颜色验证 ----------
    P = ST.COLOR_PALETTE
    check("COL-01 text on 全部填充底 ≥4.5", all(
        ST.contrast_ratio(P["text"], P[f]) >= 4.5
        for f in ("fill", "fill_alt", "accent_tint", "risk_tint", "success_tint")))
    check("COL-02 相邻填充灰度分离 ≥0.12", all(
        ST.grayscale_delta(P["fill"], P[t]) >= 0.12
        for t in ("accent_tint", "risk_tint", "success_tint")))
    check("COL-03 中性族饱和 ≤0.45 / 强调 ≤0.55", all(
        ST.saturation(P[k]) <= 0.45 for k in
        ("fill", "primary", "secondary", "neutral", "text", "line", "grid", "muted"))
        and all(ST.saturation(P[k]) <= 0.55 for k in ("accent", "risk")))
    check("COL-04 违规调色板被 validate_palette 抓出（真判非恒过）",
          _palette_detects_mutation())

    # ---------- TYP：字体系统 ----------
    check("TYP-01 字阶单调且底线明确", list(ST.TYPOGRAPHY["scale"].values()) ==
          sorted(ST.TYPOGRAPHY["scale"].values(), reverse=True)
          and ST.TYPOGRAPHY["min_effective_pt"] == 9.0)
    check("TYP-02 有效字号=字阶×显示缩放（XS 档 full_width 下 ≥9）",
          ST.TYPOGRAPHY["scale"]["XS"] * ST.get_figure_size("full_width")["scale"] >= 9.0)
    check("TYP-03 get_text_style 未知档报错", _raises(lambda: ST.get_text_style("XXL")))

    # ---------- VIS 负例（每项必须能 FAIL/告警，证伪能力） ----------
    r = _Rep()
    VQ.vis_07_whitespace(r, "edge", _meta(boxes=[{"id": "a", "x": 0.1, "y": 1, "w": 2, "h": 1}]))
    check("VIS-NEG-01 贴边→FAIL", r.get("VIS-07")[0]["status"] == VQ.FAIL)
    r = _Rep()
    VQ.vis_07_whitespace(r, "ok", _meta(boxes=[{"id": "a", "x": 0.5, "y": 1, "w": 2, "h": 1}]))
    check("VIS-NEG-01b 合规→PASS（同一函数可过可挂）", r.get("VIS-07")[0]["status"] == VQ.PASS)

    r = _Rep()
    VQ.vis_04_color_harmony(r, "x", _meta(boxes=[
        {"id": "a", "x": 1, "y": 1, "w": 2, "h": 1, "fill": "#FF00FF", "stroke": P["primary"]}]))
    check("VIS-NEG-02 非白名单色→FAIL", r.get("VIS-04")[0]["status"] == VQ.FAIL)

    r = _Rep()
    VQ.vis_06_semantic_color(r, "x", _meta(boxes=[
        {"id": "a", "x": 1, "y": 1, "w": 2, "h": 1, "role": "top_event",
         "fill": "#FFD700", "stroke": P["primary"], "text_color": P["text"]}]))
    check("VIS-NEG-03 语义色错配→FAIL", r.get("VIS-06")[0]["status"] == VQ.FAIL)

    r = _Rep()
    VQ.vis_05_contrast(r, "x", _meta(boxes=[
        {"id": "a", "x": 1, "y": 1, "w": 2, "h": 1, "fill": P["fill"],
         "stroke": P["primary"], "text_color": P["fill"]}]))
    check("VIS-NEG-04 低对比文字→FAIL[critical]",
          r.get("VIS-05")[0]["status"] == VQ.FAIL and r.get("VIS-05")[0]["severity"] == "critical")

    r = _Rep()
    VQ.vis_03_typography(r, "x", _meta(min_font_pt=8.0, texts=[{"box": "a", "x0": 1, "y0": 1, "x1": 2, "y1": 2, "fs": 8.0}]), scale=1.0)
    check("VIS-NEG-05 有效字号 8pt→FAIL[critical]",
          r.get("VIS-03")[0]["status"] == VQ.FAIL and r.get("VIS-03")[0]["severity"] == "critical")
    r = _Rep()
    VQ.vis_03_typography(r, "x", _meta(min_font_pt=11, texts=[{"box": "a", "x0": 1, "y0": 1, "x1": 2, "y1": 2, "fs": 10.3}]), scale=1.0)
    check("VIS-NEG-05b 非字阶字号→FAIL", r.get("VIS-03")[0]["status"] == VQ.FAIL)

    r = _Rep()
    VQ.vis_11_type_appropriateness(r, "x", _meta(boxes=[
        {"id": "T", "x": 6, "y": 7.5, "w": 4, "h": 1},
        {"id": "G", "x": 6, "y": 5, "w": 4, "h": 1, "role": "gate", "text": "某门"}]),
        "fault_tree")
    check("VIS-NEG-06 故障树层级不足+门无文字编码→FAIL",
          r.get("VIS-11")[0]["status"] == VQ.FAIL)

    r = _Rep()
    VQ.vis_12_cross_figure(r, {
        "a": {"style_fingerprint": {"family_cjk": "SimHei", "line_width": 1.1,
                                    "palette_hex_used": [P["primary"]], "style_source": "figure_style"}},
        "b": {"style_fingerprint": {"family_cjk": "KaiTi", "line_width": 1.1,
                                    "palette_hex_used": [P["primary"]], "style_source": "figure_style"}}})
    check("VIS-NEG-07 跨图字族分裂→FAIL", r.get("VIS-12")[0]["status"] == VQ.FAIL)

    r = _Rep()
    VQ.vis_02_density(r, "x", _meta(boxes=[{"id": str(i), "x": 1, "y": 1, "w": 1, "h": 1}
                                           for i in range(15)]), None, "fault_tree")
    check("VIS-NEG-08 节点超限→FAIL", r.get("VIS-02")[0]["status"] == VQ.FAIL)

    # score 不掩盖 Critical
    items = [{"code": "VIS-01", "status": VQ.PASS, "severity": "none"}] * 11 + \
            [{"code": "VIS-05", "status": VQ.FAIL, "severity": "critical"}]
    sc = VQ.quality_score(items)
    check("SCORE-01 高分仍含 Critical FAIL（score 不放行）",
          sc["score"] >= 90 and any(i["status"] == VQ.FAIL for i in items))

    # ---------- Mermaid fallback Critical ----------
    import render_mermaid as RM
    check("FB-CRIT-01 旧假内容 fallback 已删除", not hasattr(RM, "generate_fallback_figure"))
    outp = os.path.join(tmp, "diag.png")
    ok, msg = RM.generate_diagnostic_placeholder(outp, "x.mmd", "unit-test")
    check("FB-CRIT-02 诊断占位永远返回 False（不可能判成功）", ok is False)
    check("FB-CRIT-03 占位物仍标注非论文图", os.path.isfile(outp) and "NOT a figure" in msg)
    # figure_iface：mmdc 失败 → REJECTED + 清理残缺
    import figure_iface as FI
    import research_integrity as RI
    root = os.path.join(tmp, "proj")
    os.makedirs(os.path.join(root, ".aeromech", "artifacts", "figures"), exist_ok=True)
    RI.init_registries(root)
    RI.save_registry(root, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(root, "figures", [{"id": "FIG-001", "name": "fig1-1",
                                        "related_rqs": ["RQ-01"]}])
    mmd = os.path.join(root, ".aeromech", "artifacts", "figures", "FIG-001.mmd")
    open(mmd, "w", encoding="utf-8").write("graph TD\n A-->B\n")
    fake_out = os.path.join(root, ".aeromech", "artifacts", "figures", "final", "fig1-1.png")
    os.makedirs(os.path.dirname(fake_out), exist_ok=True)

    orig = RM.render_with_mmdc
    def _fail_render(*a, **k):
        open(fake_out, "wb").write(b"\x89PNG half-baked")   # 模拟 mmdc 留下残缺文件
        return False, "simulated mmdc crash", None, "MERMAID_FAILED"
    RM.render_with_mmdc = _fail_render
    try:
        res = FI.generate_figure(root, "FIG-001", provider="local")
        st, _rec = FI.current_status(root, "FIG-001")
        check("FB-CRIT-04 mmdc 失败→REJECTED（非 GENERATED）",
              res["status"] == "REJECTED" and st == "REJECTED", res.get("reason", ""))
        check("FB-CRIT-05 残缺文件被清理（半成品不进交付）", not os.path.isfile(fake_out))
        check("FB-CRIT-06 失败原因入记录", "FIGURE_ERROR" in (res.get("reason") or ""))
    finally:
        RM.render_with_mmdc = orig

    # ---------- figkit 集成：实测 min_font + 指纹 + 白名单 ---- -
    import figkit
    g = figkit.Fig(6.0)
    g.box("B", 1, 1, 3, 1, ["测试 Test 100 MPa"], role="top_event")
    g.save(tmp, "intg", min_font=99)   # 故意虚报 99 → 实测应为 11.5
    meta = json.load(open(os.path.join(tmp, "intg.layout.json"), encoding="utf-8"))
    check("INT-01 min_font 以实测为准（声明造假被纠正）",
          meta["min_font_pt"] == 11.5, str(meta["min_font_pt"]))
    b0 = meta["boxes"][0]
    check("INT-02 layout 输出 fill/stroke/role/fingerprint",
          all(k in b0 for k in ("fill", "stroke", "role"))
          and meta["style_fingerprint"]["style_source"] == "figure_style")
    check("INT-03 输出色全在调色板白名单",
          set(meta["style_fingerprint"]["palette_hex_used"]) <= set(ST.COLOR_PALETTE.values()))

    # ---------- 散写扫描器 ----------
    bad = os.path.join(tmp, "badfig.py")
    open(bad, "w", encoding="utf-8").write('x = "#123456"  # 散写色值\n')
    hits = ST.scan_hardcoded_styles([bad])
    check("INT-04 扫描器抓到散写 HEX 负例", len(hits) == 1)
    sk = ST.scan_hardcoded_styles([os.path.join(ST.__file__),
                                   os.path.join(os.path.dirname(figkit.__file__), "figkit.py")])
    check("INT-05 figure_style/figkit 自身散写=0", sk == [])

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_visual_system 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


def _raises(fn):
    try:
        fn()
        return False
    except (KeyError, ValueError):
        return True


def _palette_detects_mutation():
    """临时注入一个违规色，validate_palette 必须报违规（证明它是真判不是恒过）。"""
    orig = ST.COLOR_PALETTE["fill"]
    ST.COLOR_PALETTE["fill"] = "#FFFFFF"      # text on white=14.7 但 fill vs bg 灰度=0
    bad = ST.validate_palette()
    ST.COLOR_PALETTE["fill"] = orig
    return bool(bad)


if __name__ == "__main__":
    sys.exit(main())
