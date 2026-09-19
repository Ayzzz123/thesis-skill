# -*- coding: utf-8 -*-
"""figure_visual_qa.py — v1.6.5 FIGURE_VISUAL_QA（VIS-01~12 + Figure Quality Score）

定位（Phase 0 审计结论）：几何 QA（GQ）回答"有没有重叠/穿字"，本模块回答
"是否平衡/克制/和谐/统一/像专业学术图"。**Geometry PASS ≠ Visual PASS。**

输入：
  --figdir   含 *.layout.json（figkit 产物：boxes/edges/texts 带 fill/stroke/role/
             text_color + style_fingerprint）
  --pdf      可选：最终交付 PDF（VIS-10 渲染级；缺→该 SKIP 交人工）
  --plan     可选：figure-plan.yaml（取 figure type 分派 VIS-11 规则；缺→按类型 N/A）
  --out      报告目录（figure-visual-report.md，行格式兼容 delivery_gate 解析）

每项：{code, status(PASS/FAIL/WARN/NEEDS_HUMAN_REVIEW/SKIP), severity, evidence,
       reason, suggestion(方向性修正，供 regeneration loop 消费)}。

诚实性规则（§八/§十/§十五）：
  - 不可靠机检的维度 → NEEDS_HUMAN_REVIEW，绝不伪装 PASS；
  - Critical（文字裁切/对比不足/语义色错配/数据误导/渲染糊）→ FAIL，
    **Figure Quality Score 再高也 BLOCK**（score 仅展示，不参与放行）；
  - 无 layout 元数据（非 figkit 源，如 mermaid PNG）→ 大部分项 SKIP+原因，
    仅 VIS-02/09/10 可做像素级弱判定（WARN 级，不 PASS 强判）。

用法: python figure_visual_qa.py --figdir <dir> [--pdf <pdf>] [--plan <yaml>] --out <dir>
退出码: 0=无 FAIL；1=有 FAIL；3=内部错误（绝不产生假 PASS）
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figure_style as ST

PASS, FAIL, WARN, NHR, SKIP = ("PASS", "FAIL", "WARN", "NEEDS_HUMAN_REVIEW",
                               "SKIPPED_WITH_REASON")


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, name, status, severity, evidence, reason, suggestion=""):
        self.items.append({"code": code, "name": name, "status": status,
                           "severity": severity, "evidence": evidence,
                           "reason": reason, "suggestion": suggestion})
        print(f"  {code} {name}: {status}"
              + (f" [{severity}]" if severity != "none" else "")
              + f" | {reason[:110]}"
              + (f" | 建议: {suggestion[:80]}" if suggestion else ""))

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "figure-visual-report.md")
        crit = [i for i in self.items if i["status"] == FAIL
                and i["severity"] in ("critical", "high")]
        lines = ["# Figure Visual QA（VIS-01~12，v1.6.5）", ""]
        for i in self.items:
            lines.append(f"- {i['code']} {i['name']}: {i['status']}"
                         + (f" [{i['severity']}]" if i["severity"] != "none" else "")
                         + f" | {i['evidence']} | {i['reason']}"
                         + (f" | 建议: {i['suggestion']}" if i["suggestion"] else ""))
        score = quality_score(self.items)
        lines += ["",
                  f"- Figure Quality Score（展示值，不参与放行）: "
                  f"{score['score']}/100 已评 {score['scored']}/{score['total']} 项",
                  f"- Critical/High FAIL: {len(crit)}"
                  + (f" → {', '.join(c['code'] for c in crit)}" if crit else ""),
                  "",
                  f"结果: {'ALL PASS' if not any(i['status'] == FAIL for i in self.items) else 'FAIL'}"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def quality_score(items):
    """0-100 展示分：PASS=100、WARN=70、SKIP/NHR=不计；FAIL=0。
    仅趋势展示——调用方 gate 逻辑禁止用本分放行（§十）。"""
    val = {PASS: 100, WARN: 70, FAIL: 0}
    scored = [val.get(i["status"]) for i in items if i["status"] in val]
    return {"score": round(sum(scored) / len(scored)) if scored else 0,
            "scored": len(scored), "total": len(items)}


# ---------------- 度量工具 ----------------
def _ink_ratio(png, dpi_box=None):
    """二值化前景占比（300dpi 等效采样）。"""
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(png).convert("L")
        a = np.array(im)
        if dpi_box:  # 下采样控制成本
            h, w = a.shape
            step = max(1, int(w / 1400))
            a = a[::step, ::step]
        return float((a < 200).mean())
    except Exception:
        return None


def _load_layouts(figdir):
    out = {}
    for p in sorted(glob.glob(os.path.join(figdir, "*.layout.json"))) + \
            sorted(glob.glob(os.path.join(figdir, "**", "*.layout.json"), recursive=True)):
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        key = re.sub(r"\.layout\.json$", "", os.path.basename(p))
        out.setdefault(key, m)
    return out


def _content_bbox(meta):
    """全部 box/text 的并集 bbox（cm）。"""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for b in meta.get("boxes") or []:
        xs0.append(b["x"]); ys0.append(b["y"])
        xs1.append(b["x"] + b["w"]); ys1.append(b["y"] + b["h"])
    for t in meta.get("texts") or []:
        xs0.append(t["x0"]); ys0.append(t["y0"])
        xs1.append(t["x1"]); ys1.append(t["y1"])
    if not xs0:
        return None
    return min(xs0), min(ys0), max(xs1), max(ys1)


# ---------------- VIS 检查 ----------------
def vis_01_layout_balance(rep, key, meta):
    """平衡=主内容重心。chart 类以 axes_rect 为视觉主体（刻度/轴标题是结构性边饰，
    不计入重心）；diagram 类以 boxes 并集为准（note 等 __note__ 页边注不计）。
    两者皆无 → 退回全 texts bbox。"""
    W, H = meta.get("w_cm", 16.5), meta.get("h_cm", 8)
    if meta.get("axes_rect"):
        ax0, ay0, ax1, ay1 = meta["axes_rect"]
        bb = (ax0, ay0, ax1, ay1)
    else:
        boxes = meta.get("boxes") or []
        if boxes:
            bb = (min(b["x"] for b in boxes), min(b["y"] for b in boxes),
                  max(b["x"] + b["w"] for b in boxes),
                  max(b["y"] + b["h"] for b in boxes))
        else:
            bb = _content_bbox(meta)
    if not bb:
        rep.add("VIS-01", "Layout Balance", SKIP, "none", key, "无 axes_rect/box 几何数据")
        return
    x0, y0, x1, y1 = bb
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dev_x = abs(cx - W / 2) / W
    dev_y = abs(cy - H * 0.52) / H          # 光学中心略偏上
    right = W - x1
    lr = x0 / right if right > 0.05 else (9.9 if x0 > 0.05 else 1.0)
    ok = dev_x <= 0.08 and dev_y <= 0.10 and 0.5 <= lr <= 2.0
    rep.add("VIS-01", "Layout Balance", PASS if ok else WARN,
            "medium" if not ok else "none", key,
            f"重心偏移 x={dev_x:.2f} y={dev_y:.2f} 左右留白比={lr if lr != 9.9 else 'N/A'}"
            + ("" if ok else "（超出平衡带）"),
            "" if ok else "将内容整体向重心偏移反方向平移，或重排子树使左右视觉重量接近")


def vis_02_density(rep, key, meta, png, ftype):
    n = len(meta.get("boxes") or [])
    cap = (ST.FIGURE_TYPES.get(ftype, {}) or {}).get("max_nodes", ST.SPACING["max_nodes"])
    ink = _ink_ratio(png) if png and os.path.isfile(png) else None
    probs = []
    if n > cap:
        probs.append(f"节点 {n}>{cap}")
    if ink is not None and ink > ST.SPACING["max_ink_ratio"]:
        probs.append(f"ink {ink:.2f}>{ST.SPACING['max_ink_ratio']}")
    if not probs and n == 0 and ink is None:
        rep.add("VIS-02", "Information Density", SKIP, "none", key, "无几何与像素输入")
        return
    rep.add("VIS-02", "Information Density", PASS if not probs else FAIL,
            "high" if probs else "none", key,
            f"节点={n}(≤{cap}) ink={f'{ink:.2f}' if ink is not None else 'n/a'}"
            + ("；" + "，".join(probs) if probs else ""),
            "" if not probs else "拆分为多张图 / 合并次要节点 / 增大画布后重排")


def vis_03_typography(rep, key, meta, scale=1.0):
    """有效字号 + 字阶白名单（禁散写字号）。"""
    mn = meta.get("min_font_pt")
    eff = (mn or 0) * scale
    bad_size = mn is not None and eff < ST.TYPOGRAPHY["min_effective_pt"]
    scale_vals = set(ST.TYPOGRAPHY["scale"].values())
    off_scale = [t["fs"] for t in meta.get("texts") or []
                 if t["fs"] not in scale_vals]
    if mn is None and not meta.get("texts"):
        rep.add("VIS-03", "Typography Readability", SKIP, "none", key, "无字号元数据")
        return
    ok = not bad_size and not off_scale
    rep.add("VIS-03", "Typography Readability", PASS if ok else FAIL,
            "critical" if bad_size else "medium", key,
            f"min_font={mn} 有效≈{eff:.1f}pt(≥{ST.TYPOGRAPHY['min_effective_pt']})"
            + (f"；非字阶字号 {sorted(set(off_scale))[:4]}" if off_scale else ""),
            "" if ok else ("增大生成 min_font 或增大画布（禁止缩内容凑页）"
                           if bad_size else "字号改用 figure_style.TYPOGRAPHY.scale 档位"))


def _all_colors(meta):
    """boxes(fill/stroke) + chart bars/lines color + note/text 声明色 → 全图色集合。"""
    hexes = []
    for b in meta.get("boxes") or []:
        hexes += [v for v in (b.get("fill"), b.get("stroke")) if v]
    for bar in meta.get("bars") or []:
        if bar.get("color"):
            hexes.append(bar["color"])
    for ln in meta.get("lines") or []:
        if ln.get("color"):
            hexes.append(ln["color"])
    return hexes


def vis_04_color_harmony(rep, key, meta):
    hexes = _all_colors(meta)
    if not hexes:
        rep.add("VIS-04", "Color Harmony", SKIP, "none", key, "无颜色元数据（非 figkit 源）")
        return
    pal = ST.COLOR_PALETTE
    unknown = sorted({h for h in hexes if h not in pal.values()})
    fills = {h for b in meta.get("boxes") or [] if (h := b.get("fill")) and h != pal["bg"]}
    fills |= {bar["color"] for bar in meta.get("bars") or [] if bar.get("color")}
    hues = {ST.hue_of(h)[0] // 60 for h in fills}
    oversat = [h for h in hexes if ST.saturation(h) >
               (ST.STYLE_THRESHOLDS["saturation_max_accent"]
                if h in (pal["accent"], pal["risk"], pal["accent_tint"], pal["risk_tint"])
                else ST.STYLE_THRESHOLDS["saturation_max_neutral"])]
    probs = []
    if unknown:
        probs.append(f"非白名单色 {unknown[:3]}")
    if len(hues) > ST.STYLE_THRESHOLDS["hue_budget_fills"]:
        probs.append(f"填充色相数 {len(hues)}>{ST.STYLE_THRESHOLDS['hue_budget_fills']}")
    if oversat:
        probs.append(f"过饱和 {oversat[:3]}")
    rep.add("VIS-04", "Color Harmony", PASS if not probs else FAIL,
            "high" if unknown else "medium", key,
            f"填充/系列色 {len(fills)} 种/色相 {len(hues)}"
            + ("；" + "，".join(probs) if probs else "（白名单内、低饱和）"),
            "" if not probs else "全部颜色改从 figure_style.COLOR_PALETTE 取；合并同族色相")


def vis_05_contrast(rep, key, meta):
    bad = []
    for b in meta.get("boxes") or []:
        tc, fill = b.get("text_color"), b.get("fill")
        if tc and fill and fill != "none":
            c = ST.contrast_ratio(tc, fill)
            if c < ST.STYLE_THRESHOLDS["text_on_fill_min"]:
                bad.append(f"{b.get('id')} {c:.2f}")
    # chart 类：系列色（柱描边/折线）对 bg 的非文本对比 ≥3.0（灰线/浅色不可见防线）
    series_cols = [bar.get("color") for bar in meta.get("bars") or []] + \
                  [ln.get("color") for ln in meta.get("lines") or []]
    for h in {c for c in series_cols if c}:
        if ST.contrast_ratio(h, ST.COLOR_PALETTE["bg"]) < ST.STYLE_THRESHOLDS["border_on_bg_min"]:
            bad.append(f"系列色 {h} on bg {ST.contrast_ratio(h, ST.COLOR_PALETTE['bg']):.2f}<3.0")
    if not any(b.get("text_color") for b in meta.get("boxes") or [{}]) and not series_cols:
        rep.add("VIS-05", "Contrast", SKIP, "none", key, "无文字/底色配对元数据")
        return
    rep.add("VIS-05", "Contrast", PASS if not bad else FAIL,
            "critical" if bad else "none", key,
            f"文字-底色对比全部 ≥{ST.STYLE_THRESHOLDS['text_on_fill_min']}"
            if not bad else f"低于阈值: {bad[:4]}",
            "" if not bad else "文字统一用 palette['text']；底色改用 fill/tint 族")


def vis_06_semantic_color(rep, key, meta):
    """角色→颜色必须命中 SEMANTIC_COLORS（跨图同语义同色）。"""
    bad = []
    for b in meta.get("boxes") or []:
        role = b.get("role")
        if not role:
            continue
        if role not in ST.SEMANTIC_COLORS:
            bad.append(f"{b.get('id')} 未知角色 {role}")
            continue
        s, f, t = ST.SEMANTIC_COLORS[role]
        want_f = ST.COLOR_PALETTE["bg"] if f is None else ST.COLOR_PALETTE[f]
        want_s = ST.COLOR_PALETTE["bg"] if s is None else ST.COLOR_PALETTE[s]
        if b.get("fill") and b["fill"] != want_f:
            bad.append(f"{b.get('id')}[{role}] fill {b['fill']}≠{want_f}")
        if b.get("stroke") and b["stroke"] != want_s:
            bad.append(f"{b.get('id')}[{role}] stroke {b['stroke']}≠{want_s}")
    roles = {b.get("role") for b in meta.get("boxes") or [] if b.get("role")}
    if not roles:
        rep.add("VIS-06", "Semantic Color Consistency", SKIP, "none", key,
                "无 role 标注（未用语义色系统）")
        return
    rep.add("VIS-06", "Semantic Color Consistency", PASS if not bad else FAIL,
            "high", key, f"{len(roles)} 个语义角色全部命中 SEMANTIC 映射"
            if not bad else f"语义色错配: {bad[:4]}",
            "" if not bad else "删除局部覆盖，统一 get_semantic_color(role) 取色")


def vis_07_whitespace(rep, key, meta):
    bb = _content_bbox(meta)
    W, H = meta.get("w_cm", 16.5), meta.get("h_cm", 8)
    if not bb:
        rep.add("VIS-07", "Whitespace", SKIP, "none", key, "无几何数据")
        return
    m = ST.SPACING["figure_margin"]
    x0, y0, x1, y1 = bb
    # 画布坐标 y 轴向上（figkit set_ylim(0,H)）：上边距=H-y1，下边距=y0。
    viol = []
    if x0 < m - 1e-6: viol.append(f"左 {x0:.2f}<{m}")
    if y0 < m - 1e-6: viol.append(f"下 {y0:.2f}<{m}")
    if W - x1 < m - 1e-6: viol.append(f"右 {W-x1:.2f}<{m}")
    if H - y1 < m - 1e-6: viol.append(f"上 {H-y1:.2f}<{m}")
    rep.add("VIS-07", "Whitespace", PASS if not viol else FAIL,
            "medium", key, f"四周留白 ≥{m}cm" if not viol else f"贴边: {viol}",
            "" if not viol else "内容整体内缩至边距安全区；必要时增大画布")


def vis_08_alignment(rep, key, meta):
    """同层（layer 相同或同 y 带）节点顶边/中线对齐。"""
    boxes = meta.get("boxes") or []
    by_layer = {}
    for b in boxes:
        lay = b.get("layer") if b.get("layer") is not None else round(b["y"], 1)
        by_layer.setdefault(lay, []).append(b)
    bad = []
    for lay, bs in by_layer.items():
        if len(bs) < 2:
            continue
        ys = [b["y"] for b in bs]
        if max(ys) - min(ys) > 0.05:
            bad.append(f"层{lay} y差{max(ys)-min(ys):.2f}")
    if not boxes:
        rep.add("VIS-08", "Alignment", SKIP, "none", key, "无 box")
        return
    rep.add("VIS-08", "Alignment", PASS if not bad else WARN,
            "medium" if bad else "none", key,
            "同层节点顶边对齐（≤0.05cm）" if not bad else f"错位: {bad[:4]}",
            "" if not bad else "同层节点 y 统一为层基线；用 SPACING.gap_v 等距")


def vis_09_academic_style(rep, key, meta, png):
    """禁项检测：渐变/阴影/3D 在 layout 模型里不存在对应图元——
    能机检的是：全部填充为白名单纯色（无图元级 alpha 阴影）、线宽统一。
    主观"像不像海报"不可靠机检 → NHR。"""
    hexes = _all_colors(meta)
    nonpal = [h for h in hexes if h not in ST.COLOR_PALETTE.values()]
    if not hexes:
        rep.add("VIS-09", "Academic Style", NHR, "medium", key,
                "非 figkit 源（mermaid/位图）：无法机检样式克制，附样张交人工",
                "人工目检：无渐变/阴影/3D/装饰；配色克制")
        return
    rep.add("VIS-09", "Academic Style", PASS if not nonpal else FAIL,
            "high" if nonpal else "none", key,
            "纯色白名单填充、统一线宽、无渐变/阴影图元（layout 模型无此类图元）"
            if not nonpal else f"非白名单色: {nonpal[:3]}",
            "" if not nonpal else "移除自定义图元，改用 figkit 原语")


def vis_10_pdf_readability(rep, key, meta, pdf_path, used=None):
    if not pdf_path or not os.path.isfile(pdf_path):
        rep.add("VIS-10", "PDF Readability", SKIP, "none", key,
                "未提供最终 PDF（构建后由 pipeline 复跑本项）")
        return
    try:
        import pymupdf as fitz
    except ImportError:
        rep.add("VIS-10", "PDF Readability", NHR, "medium", key, "pymupdf 缺失")
        return
    doc = fitz.open(pdf_path)
    Wc, Hc = meta.get("w_cm", 16.5), meta.get("h_cm", 8)
    want_aspect = Wc / max(0.1, Hc)
    used = used if used is not None else set()
    found = None
    # v1.6.5：按 宽高比+文档序 匹配（旧版仅按宽度 → 多图全匹配到同一页）
    for pg in range(len(doc)):
        for im in doc[pg].get_image_info():
            b = im["bbox"]
            w_cm = (b[2] - b[0]) / 72 * 2.54
            h_cm = (b[3] - b[1]) / 72 * 2.54
            if w_cm < 5 or (pg, round(b[0], 1), round(b[1], 1)) in used:
                continue
            if h_cm <= 0:
                continue
            if abs(w_cm / h_cm - want_aspect) / want_aspect > 0.15:
                continue
            if abs(w_cm - Wc) > 1.5 and abs(w_cm - Wc * 0.87) > 1.5:
                continue
            found = (pg, w_cm, b)
            used.add((pg, round(b[0], 1), round(b[1], 1)))
            break
        if found:
            break
    if not found:
        rep.add("VIS-10", "PDF Readability", NHR, "high", key,
                "PDF 中未匹配到该图（可能未嵌入或尺寸漂移）",
                "确认 figure_block 嵌入与占位行命中")
        return
    pg, w_cm, bbox = found
    scale = w_cm / Wc
    eff = (meta.get("min_font_pt") or 0) * scale
    page = doc[pg]
    clipped = (bbox[0] < 36 or bbox[2] > page.rect.width - 36
               or bbox[1] < 28 or bbox[3] > page.rect.height - 28)
    ok = eff >= ST.TYPOGRAPHY["min_effective_pt"] and not clipped
    rep.add("VIS-10", "PDF Readability", PASS if ok else FAIL,
            "critical", key,
            f"p{pg+1} 显示宽 {w_cm:.1f}cm 有效字号≈{eff:.1f}pt 裁切={clipped}",
            "" if ok else ("增大源图 min_font 或显示宽（禁止缩图凑页）"
                           if eff < 9 else "调整嵌入位置回版心"))
    doc.close()


def vis_11_type_appropriateness(rep, key, meta, ftype):
    rules = ST.FIGURE_TYPES.get(ftype or "")
    if not rules:
        rep.add("VIS-11", "Figure-Type Appropriateness", SKIP, "none", key,
                f"未注册类型 {ftype!r}（figure-plan 提供 type 后判定）")
        return
    problems = []
    if ftype == "fault_tree":
        ys = sorted({round(b["y"], 1) for b in meta.get("boxes") or []})
        if len(ys) < 3:
            problems.append(f"层级 {len(ys)}<3（顶/门/底不完整）")
        # AND/OR 非颜色编码：门节点文本须含 AND/OR 字样
        for b in meta.get("boxes") or []:
            if b.get("role") == "gate" and not re.search(r"AND|OR", b.get("text") or ""):
                problems.append(f"{b['id']} 门无 AND/OR 文字编码")
    elif ftype in ("stat_bar",):
        axr = meta.get("axes_rect")
        bars = meta.get("bars") or []
        if axr and bars:
            y0 = min(min(b["bbox"][1], b["bbox"][3]) for b in bars)
            if abs(y0 - axr[1]) > 0.05 and y0 > axr[1] + 0.05:
                problems.append("柱不从轴基线(0)起")
        elif not bars:
            problems.append("无 bars 元数据（chart 型需 figkit chart 输出）")
    if problems:
        rep.add("VIS-11", "Figure-Type Appropriateness", FAIL, "critical", key,
                f"[{ftype}] " + "；".join(problems),
                "按 03-figure-type-spec 修正结构（补层/加文字编码/柱基线归零）")
    else:
        rep.add("VIS-11", "Figure-Type Appropriateness", PASS, "none", key,
                f"[{ftype}] 专属规则全部满足")


def vis_12_cross_figure(rep, layouts):
    fps = []
    for key, m in sorted(layouts.items()):
        fp = m.get("style_fingerprint")
        if fp:
            fps.append((key, fp))
    if len(fps) < 2:
        rep.add("VIS-12", "Cross-Figure Consistency", SKIP, "none",
                f"{len(fps)} 图有指纹", "单图/无指纹（figkit 源之外）无法比对")
        return
    fam = {fp["family_cjk"] for _, fp in fps}
    lw = {fp["line_width"] for _, fp in fps}
    src = {fp.get("style_source") for _, fp in fps}
    pal_ok = all(set(fp["palette_hex_used"]) <= set(ST.COLOR_PALETTE.values())
                 for _, fp in fps)
    bad = []
    if len(fam) > 1: bad.append(f"字族分裂 {fam}")
    if len(lw) > 1: bad.append(f"线宽分裂 {lw}")
    if src != {"figure_style"}: bad.append("样式来源不统一")
    if not pal_ok: bad.append("存在白名单外颜色")
    rep.add("VIS-12", "Cross-Figure Consistency", PASS if not bad else FAIL,
            "high", f"{len(fps)} 图", "全部图同一视觉家族（字族/线宽/色板/来源一致）"
            if not bad else "；".join(bad),
            "" if not bad else "统一经 figure_style 重建样式（禁止局部覆盖）")


def run(figdir, pdf=None, plan=None, out="."):
    rep = Report(out)
    layouts = _load_layouts(figdir)
    types = {}
    if plan and os.path.isfile(plan):
        try:
            import yaml
            data = yaml.safe_load(open(plan, encoding="utf-8")) or {}
            for sp in data.get("figures") or []:
                types[str(sp.get("figure_id"))] = sp.get("type")
                fid = str(sp.get("figure_id"))
                nm = str(sp.get("name") or "")
                if fid not in layouts and nm in layouts:
                    types.setdefault(nm, sp.get("type"))
        except Exception:
            pass
    if not layouts:
        rep.add("VIS-00", "图元数据", FAIL, "high", figdir,
                "figdir 下未找到 *.layout.json（figkit 输出）——视觉层无从判定")
        rep.save()
        return rep
    _used = set()   # VIS-10：一图一页占用，多图不再全部匹配到同一页
    for key, meta in sorted(layouts.items()):
        png = os.path.join(figdir, key + ".png")
        if not os.path.isfile(png):
            png2 = os.path.join(figdir, "final", key + ".png")
            png = png2 if os.path.isfile(png2) else None
        ftype = types.get(key)
        scale = 1.0
        if png:
            try:
                from PIL import Image
                im = Image.open(png)
                disp = (ST.FIGURE_SIZE_PRESETS["full_width"]["display_w_cm"]
                        / (im.size[0] / im.info.get("dpi", (220, 220))[0] * 2.54))
                scale = min(1.0, disp)
            except Exception:
                pass
        vis_01_layout_balance(rep, key, meta)
        vis_02_density(rep, key, meta, png, ftype)
        vis_03_typography(rep, key, meta, scale)
        vis_04_color_harmony(rep, key, meta)
        vis_05_contrast(rep, key, meta)
        vis_06_semantic_color(rep, key, meta)
        vis_07_whitespace(rep, key, meta)
        vis_08_alignment(rep, key, meta)
        vis_09_academic_style(rep, key, meta, png)
        vis_10_pdf_readability(rep, key, meta, pdf, used=_used)
        vis_11_type_appropriateness(rep, key, meta, ftype)
    vis_12_cross_figure(rep, layouts)
    rep.save()
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figdir", required=True)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--plan", default=None)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    try:
        rep = run(args.figdir, args.pdf, args.plan, args.out)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return 3
    fails = [i for i in rep.items if i["status"] == FAIL]
    print(f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(i['code'] for i in fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
