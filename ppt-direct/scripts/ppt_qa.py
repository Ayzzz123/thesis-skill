# -*- coding: utf-8 -*-
"""ppt_qa.py — 答辩 PPT 全片 QA（PPT-01~15）

检查真源：layout JSON sidecar（引擎绘制时输出的几何/文字量元数据）+
pptx slide XML（配色/字体/占位符/放映隐藏实测）。原则与 aeromech-thesis 一致：
先读对象、后下结论；估算项（溢出）由引擎声明、QA 校验，不重复发明算法。

PPT-01 页数档位        PPT-08 无占位符残留（【待填】）
PPT-02 每页要点数上限   PPT-09 无空页
PPT-03 每页可见字数上限 PPT-10 演讲备注覆盖
PPT-04 文本溢出估算     PPT-11 讲稿时长估算（250 字/分钟）
PPT-05 配色合规         PPT-12 表格规模（行≤12、列≤8）
PPT-06 同版式对齐一致   PPT-13 校模母版使用率（≥50%）
PPT-07 字体合规         PPT-14 标点/全半角一致性
                        PPT-15 附录页隐藏放映

用法: python ppt_qa.py --pptx 答辩PPT.pptx --layout layout.json
        --theme theme.yaml [--deck deck.yaml] --out <报告目录>
退出码: 0=全部 PASS；1=存在 FAIL
"""
import argparse
import json
import os
import re
import sys
import zipfile

import yaml

# 与 pptx_engine.SHRINK_FLOOR 保持一致（body/col_title 14pt、table 12pt）。
# 缩字触底仍有 est_overflow 说明该形状只能靠删字/拆页解决，属修复建议级告警。
SHRINK_FLOOR_REPORT = {"body": 14, "col_title": 14, "table": 12}
# 中文答辩语速经验值（字/分钟），用于 PPT-11 讲稿时长估算。
SPEECH_CPS = 250


def _safe_print(s):
    """控制台编码兜底（如 Windows GBK 打不出 • 等字符时降级替换，不崩）。"""
    try:
        print(s)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(s.encode(enc, "replace").decode(enc, "replace"))


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        _safe_print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "ppt-qa-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# PPT QA 报告（PPT-01~15）", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines += ["", f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def _slide_texts(pptx_path):
    """逐页提取全部文本（a:t）、配色/字体实测值、备注与放映隐藏标记。"""
    texts, colors, fonts, hiddens = [], set(), set(), []
    with zipfile.ZipFile(pptx_path) as zf:
        slide_names = sorted(
            (n for n in zf.namelist()
             if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"(\d+)", n).group(1)))
        for name in slide_names:
            xml = zf.read(name).decode("utf-8", "ignore")
            texts.append(re.findall(r"<a:t>([^<]*)</a:t>", xml))
            colors |= {c.upper() for c in
                       re.findall(r'srgbClr val="([0-9A-Fa-f]{6})"', xml)}
            fonts |= set(re.findall(r'typeface="([^"]+)"', xml))
            hiddens.append(bool(re.search(r'<p:sld\b[^>]*\bshow="0"', xml)))
        notes_names = [n for n in zf.namelist()
                       if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)]
        notes = []
        for name in sorted(notes_names,
                           key=lambda n: int(re.search(r"(\d+)", n).group(1))):
            xml = zf.read(name).decode("utf-8", "ignore")
            body = re.findall(r"<a:t>([^<]*)</a:t>", xml)
            notes.append("".join(t for t in body
                                 if not t.strip().isdigit()).strip())
    return texts, colors, fonts, notes, hiddens


# PPT-14 标点/全半角：CJK 含全角标点、中文、全角字母数字
_CJK_OR_FULL = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
_HALF_PUNCT = ",;:?!()\"'"
_FULL_DIGIT_LATIN = set("０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭ"
                        "ＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍ"
                        "ｎｏｐｑｒｓｔｕｖｗｘｙｚ．")


def _punct_issues(page_texts, notes):
    """返回 (页号, 片段) 列表：半角标点紧邻中文、全角数字/拉丁字母/句点。"""
    issues = []
    for i, page in enumerate(page_texts, 1):
        text = "".join(page)   # 跨 run 拼接后再查邻接，避免 run 切分漏检
        for m in re.finditer(r"[,;:?!()\"']", text):
            j = m.start()
            prev = text[j - 1] if j else ""
            nxt = text[j + 1] if j + 1 < len(text) else ""
            if _CJK_OR_FULL.match(prev) or _CJK_OR_FULL.match(nxt):
                issues.append((i, f"半角{m.group(0)!r} {text[max(0, j - 5):j + 6]!r}"))
                break
        for ch in text:
            if ch in _FULL_DIGIT_LATIN:
                issues.append((i, f"全角{ch!r}"))
                break
    for i, note in enumerate(notes, 1):
        for m in re.finditer(r"[,;:?!()\"']", note):
            j = m.start()
            prev = note[j - 1] if j else ""
            nxt = note[j + 1] if j + 1 < len(note) else ""
            if _CJK_OR_FULL.match(prev) or _CJK_OR_FULL.match(nxt):
                issues.append((f"备注P{i}", f"半角{m.group(0)!r} {note[max(0, j - 5):j + 6]!r}"))
                break
    return issues


def run_qa(pptx_path, layout_path, theme_path, deck_path, out_dir):
    rep = Report(out_dir)
    with open(theme_path, encoding="utf-8") as f:
        theme = yaml.safe_load(f)
    with open(layout_path, encoding="utf-8") as f:
        layout = json.load(f)
    deck = {}
    if deck_path and os.path.isfile(deck_path):
        with open(deck_path, encoding="utf-8") as f:
            deck = yaml.safe_load(f)
    limits = theme.get("limits", {})
    pages = layout["pages"]
    texts, used_colors, used_fonts, notes, hiddens = _slide_texts(pptx_path)

    # PPT-01 页数档位（附修复建议；问答备份等附录页不占档位）
    tier_name = deck.get("meta", {}).get("page_tier", "standard")
    tiers = theme.get("page_tiers", {}) or {}
    tier = tiers.get(tier_name)
    appendix_n = sum(1 for pg in pages if pg.get("appendix"))
    body_n = len(pages) - appendix_n
    if tier:
        ok = tier["min"] <= body_n <= tier["max"]
        hint = ""
        if not ok:
            # 档位按 min 页数语义排序（不依赖 YAML 键序，防手写主题乱序）
            ordered = sorted(tiers.keys(), key=lambda k: tiers[k].get("min", 0))
            idx = ordered.index(tier_name)
            if body_n > tier["max"]:
                nxt = ordered[idx + 1] if idx < len(ordered) - 1 else None
                hint = f"；建议：删 {body_n - tier['max']} 页" + \
                       (f"或升档至 {nxt}" if nxt else "")
            else:
                prev = ordered[idx - 1] if idx > 0 else None
                hint = f"；建议：补 {tier['min'] - body_n} 页" + \
                       (f"或降档至 {prev}" if prev else "")
        page_str = (f"页数 {len(pages)}（正文 {body_n} + 附录备份 {appendix_n}）"
                    if appendix_n else f"页数 {len(pages)}")
        rep.add("PPT-01", ok,
                f"{page_str}，档位 {tier_name} [{tier['min']},{tier['max']}]{hint}")
    else:
        rep.add("PPT-01", True, f"未声明档位（{tier_name}），跳过区间校验")

    # PPT-02/03/04/06/09 逐页几何与文字量
    body_layouts = {"content", "two_column", "image_text", "toc"}
    worst = []
    bullet_over, char_over, empty_pages = [], [], []
    title_pos = {}
    for pg in pages:
        kinds = [s for s in pg["shapes"] if s.get("kind") != "deco"]
        body = [s for s in kinds if s.get("kind") == "body"]
        visible = sum(s.get("chars", 0) for s in kinds)
        if pg["layout"] in body_layouts and not pg.get("appendix"):
            n_bul = sum(s.get("paras", 0) for s in body)
            if "bullets_per_slide" in limits and n_bul > limits["bullets_per_slide"]:
                bullet_over.append((pg["page"], n_bul))
            if "chars_per_slide" in limits and visible > limits["chars_per_slide"]:
                char_over.append((pg["page"], visible))
        for s in kinds:
            if s.get("est_overflow"):
                worst.append((pg["page"], s["kind"], s["est_need_h_cm"],
                              s["box_cm"][3]))
        if not kinds or visible == 0 and not any(s.get("kind") == "image"
                                                 for s in pg["shapes"]):
            empty_pages.append(pg["page"])
        if pg.get("appendix"):
            continue    # 附录备份页不参与正片对齐一致性
        title = next((s for s in kinds if s.get("kind") == "title"), None)
        if title:
            title_pos.setdefault(pg["layout"], set()).add(
                (title["box_cm"][0], title["box_cm"][1]))

    rep.add("PPT-02", not bullet_over,
            f"要点超限页: {bullet_over or '无'}（上限 {limits.get('bullets_per_slide')}）")
    rep.add("PPT-03", not char_over,
            f"字数超限页: {char_over or '无'}（上限 {limits.get('chars_per_slide')}）")
    shrinks = [(pg["page"], s["kind"], s["shrink_from"], s["font_pt"])
               for pg in pages for s in pg["shapes"]
               if s.get("shrink_from")]
    bottom_out = [(pg["page"], s["kind"], s["font_pt"]) for pg in pages
                  for s in pg["shapes"]
                  if s.get("est_overflow") and s.get("shrink_from")
                  and s["font_pt"] <= SHRINK_FLOOR_REPORT.get(s.get("kind"), 14)]
    detail = f"估算溢出: {worst or '无'}"
    if shrinks:
        detail += f"；自动缩字号 {len(shrinks)} 处（如 {shrinks[0]}）"
    if bottom_out:
        detail += f"；触底仍溢出（需删字或拆页）: {bottom_out}"
    rep.add("PPT-04", not worst, detail)

    # PPT-05 配色合规：实测颜色必须 ∈ 主题调色板（+黑白）
    palette = {v.upper() for v in theme.get("colors", {}).values()}
    allowed = palette | {"FFFFFF", "000000"}
    bad = sorted(used_colors - allowed)
    rep.add("PPT-05", not bad,
            f"调色板外颜色: {bad or '无'}（实测 {len(used_colors)} 色）")

    # PPT-06 同版式标题位置一致
    drift = {k: v for k, v in title_pos.items() if len(v) > 1}
    rep.add("PPT-06", not drift,
            f"标题位置漂移版式: {sorted(drift) or '无'}")

    # PPT-07 字体合规
    declared = {theme["fonts"]["latin"], theme["fonts"]["cjk"], ""}
    bad_fonts = sorted(used_fonts - declared - {"+mn-lt", "+mn-ea",
                                                "+mj-lt", "+mj-ea"})
    declared_show = sorted(f for f in declared if f)
    rep.add("PPT-07", not bad_fonts,
            f"声明外字体: {bad_fonts or '无'}（声明 {declared_show}）")

    # PPT-08 占位符残留
    residue = [i + 1 for i, ts in enumerate(texts)
               if any("【待填】" in t for t in ts)]
    rep.add("PPT-08", not residue, f"占位符残留页: {residue or '无'}")

    # PPT-09 无空页
    rep.add("PPT-09", not empty_pages, f"空页: {empty_pages or '无'}")

    # PPT-10 备注覆盖
    if limits.get("notes_required", True):
        missing = [i + 1 for i in range(len(pages))
                   if i >= len(notes) or not notes[i]]
        rep.add("PPT-10", not missing, f"缺备注页: {missing or '无'}")
    else:
        rep.add("PPT-10", True, "limits.notes_required=false，跳过")

    # PPT-11 讲稿时长估算（时长来源：deck.meta.duration_min > 档位默认 > 跳过）
    dur = deck.get("meta", {}).get("duration_min")
    dur_src = "deck 声明"
    if not dur:
        tinfo = theme.get("page_tiers", {}).get(
            deck.get("meta", {}).get("page_tier", ""))
        if isinstance(tinfo, dict) and tinfo.get("duration_min"):
            dur = tinfo["duration_min"]
            dur_src = f"档位 {tinfo.get('label', '')} 默认".strip()
    if dur:
        total_chars = sum(len(n) for n in notes)
        est_min = total_chars / SPEECH_CPS
        ok = 0.5 * dur <= est_min <= 1.3 * dur
        hint = ""
        if est_min < 0.5 * dur:
            hint = f"；建议：补讲稿约 {int((0.5 * dur - est_min) * SPEECH_CPS)} 字"
        elif est_min > 1.3 * dur:
            hint = f"；建议：精简讲稿约 {int((est_min - 1.3 * dur) * SPEECH_CPS)} 字"
        rep.add("PPT-11", ok,
                f"备注总字数 {total_chars}，按 {SPEECH_CPS} 字/分钟估 {est_min:.1f} 分钟，"
                f"{dur_src}时长 ≥{dur} 分钟（判定区间 [{0.5 * dur:.1f},{1.3 * dur:.1f}]）{hint}")
    else:
        rep.add("PPT-11", True, "未声明 duration_min，跳过时长校验")

    # PPT-12 表格规模（行≤12、列≤8，超出在投影仪上必糊）
    table_over = [(pg["page"], s["rows"], s["cols"]) for pg in pages
                  for s in pg["shapes"]
                  if s.get("kind") == "table"
                  and (s.get("rows", 0) > 12 or s.get("cols", 0) > 8)]
    rep.add("PPT-12", not table_over,
            f"超规表格: {table_over or '无'}（上限 行12×列8）")

    # PPT-13 校模母版使用率（仅当 theme 声明 template_layouts，即模板模式）
    if "template_layouts" in theme:
        tpl_modes = [pg.get("mode", "") for pg in pages]
        tpl_used = sum(1 for m in tpl_modes if m.startswith("template:"))
        ratio = tpl_used / len(pages) if pages else 0.0
        ok = ratio >= 0.5
        rebuilt = [pg["page"] for pg in pages
                   if not pg.get("mode", "").startswith("template:")]
        hint = f"；重建页（未匹配校模版式）: {rebuilt or '无'}"
        rep.add("PPT-13", ok,
                f"母版驱动 {tpl_used}/{len(pages)} 页（{ratio:.0%}，要求 ≥50%）{hint}")
    else:
        rep.add("PPT-13", True, "未启用模板模式（theme 无 template_layouts），跳过")

    # PPT-14 标点/全半角一致性（一般；可见文字 + 备注都查）
    punct = _punct_issues(texts, notes)
    detail = ("、".join(f"{pg} {snip}" for pg, snip in punct[:8])
              + (f"…等 {len(punct)} 处" if len(punct) > 8 else "")) or "无"
    rep.add("PPT-14", not punct, f"标点/全半角问题: {detail}")

    # PPT-15 附录页隐藏放映（实测 pptx show 属性，不信任 sidecar 自报）
    appendix_hidden_missing = [
        pg["page"] for i, pg in enumerate(pages)
        if pg.get("appendix") and not (i < len(hiddens) and hiddens[i])]
    body_hidden = [
        pg["page"] for i, pg in enumerate(pages)
        if not pg.get("appendix") and i < len(hiddens) and hiddens[i]]
    ok = not appendix_hidden_missing and not body_hidden
    rep.add("PPT-15", ok,
            f"附录页未隐藏: {appendix_hidden_missing or '无'}；"
            f"正片被误隐藏: {body_hidden or '无'}")

    rep.save()
    return 0 if all(ok for _, ok, _ in rep.items) else 1


def main():
    ap = argparse.ArgumentParser(description="答辩 PPT 全片 QA")
    ap.add_argument("--pptx", required=True)
    ap.add_argument("--layout", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--deck", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        return run_qa(a.pptx, a.layout, a.theme, a.deck, a.out)
    except Exception as e:
        _safe_print(f"FAIL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
