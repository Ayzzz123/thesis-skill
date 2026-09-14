# -*- coding: utf-8 -*-
"""ppt_qa.py — 答辩 PPT 全片 QA（PPT-01~10）

检查真源：layout JSON sidecar（引擎绘制时输出的几何/文字量元数据）+
pptx slide XML（配色/字体/占位符实测）。原则与 aeromech-thesis 一致：
先读对象、后下结论；估算项（溢出）由引擎声明、QA 校验，不重复发明算法。

PPT-01 页数档位        PPT-06 同版式对齐一致
PPT-02 每页要点数上限   PPT-07 字体合规（latin+ea ∈ 主题声明）
PPT-03 每页可见字数上限 PPT-08 无占位符残留（【待填】）
PPT-04 文本溢出估算     PPT-09 无空页
PPT-05 配色合规         PPT-10 演讲备注覆盖

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


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, ok, detail):
        self.items.append((code, ok, detail))
        print(f"  {code} {'PASS' if ok else 'FAIL'} | {detail}")

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, "ppt-qa-report.md")
        fails = [c for c, ok, _ in self.items if not ok]
        lines = ["# PPT QA 报告（PPT-01~10）", ""]
        for code, ok, detail in self.items:
            lines.append(f"- {code}: {'PASS' if ok else 'FAIL'} | {detail}")
        lines += ["", f"结果: {'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def _slide_texts(pptx_path):
    """逐页提取全部文本（a:t）与配色/字体实测值。"""
    texts, colors, fonts = [], set(), set()
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
        notes_names = [n for n in zf.namelist()
                       if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)]
        notes = []
        for name in sorted(notes_names,
                           key=lambda n: int(re.search(r"(\d+)", n).group(1))):
            xml = zf.read(name).decode("utf-8", "ignore")
            body = re.findall(r"<a:t>([^<]*)</a:t>", xml)
            notes.append("".join(t for t in body
                                 if not t.strip().isdigit()).strip())
    return texts, colors, fonts, notes


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
    texts, used_colors, used_fonts, notes = _slide_texts(pptx_path)

    # PPT-01 页数档位
    tier_name = deck.get("meta", {}).get("page_tier", "standard")
    tier = theme.get("page_tiers", {}).get(tier_name)
    if tier:
        ok = tier["min"] <= len(pages) <= tier["max"]
        rep.add("PPT-01", ok,
                f"页数 {len(pages)}，档位 {tier_name} [{tier['min']},{tier['max']}]")
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
        if pg["layout"] in body_layouts:
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
        title = next((s for s in kinds if s.get("kind") == "title"), None)
        if title:
            title_pos.setdefault(pg["layout"], set()).add(
                (title["box_cm"][0], title["box_cm"][1]))

    rep.add("PPT-02", not bullet_over,
            f"要点超限页: {bullet_over or '无'}（上限 {limits.get('bullets_per_slide')}）")
    rep.add("PPT-03", not char_over,
            f"字数超限页: {char_over or '无'}（上限 {limits.get('chars_per_slide')}）")
    rep.add("PPT-04", not worst,
            f"估算溢出: {worst or '无'}")

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
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
