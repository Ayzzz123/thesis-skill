# -*- coding: utf-8 -*-
"""speech_export.py — deck.yaml → 逐字讲稿 .md（答辩排练用）

每页输出：页号、版式、标题、预估时长（notes 字数 / 250 字/分钟）与讲稿原文；
附录页（appendix: true）标注【备份页·放映隐藏】。只读 deck.yaml，不回写 state。

用法: python speech_export.py --deck deck.yaml [--out speech.md] [--cps 250]
退出码: 0=成功；1=deck 缺失或解析失败
"""
import argparse
import os
import sys

import yaml

SPEECH_CPS = 250   # 与 ppt_qa.PPT-11 同口径（中文答辩语速，字/分钟）


def _page_title(slide, meta):
    if slide.get("title"):
        return slide["title"]
    layout = slide.get("layout", "")
    if layout == "cover":
        return meta.get("title", "封面")
    if layout == "closing":
        return slide.get("sub", "致谢")
    if layout == "toc":
        return "目录"
    return layout


def export(deck_path, out_path, cps=SPEECH_CPS):
    with open(deck_path, encoding="utf-8") as f:
        deck = yaml.safe_load(f)
    meta = deck.get("meta", {})
    slides = deck.get("slides", [])
    total_chars = sum(len(s.get("notes", "")) for s in slides)
    lines = ["# 答辩讲稿（逐字稿）", ""]
    lines.append("- 题目：{}".format(meta.get("title", "【待填】")))
    lines.append("- 档位：{} · 共 {} 页 · 讲稿 {} 字 · 按 {} 字/分钟估 {:.1f} 分钟".format(
        meta.get("page_tier", "standard"), len(slides), total_chars, cps,
        total_chars / cps))
    lines.append("")
    for i, s in enumerate(slides, 1):
        notes = s.get("notes", "")
        tag = "【备份页·放映隐藏】" if s.get("appendix") else ""
        lines.append("## P{} · {} · {}（约 {:.1f} 分钟）{}".format(
            i, s.get("layout", ""), _page_title(s, meta), len(notes) / cps, tag))
        lines.append("")
        lines.append(notes if notes else "（本页无讲稿备注）")
        lines.append("")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return total_chars


def main():
    ap = argparse.ArgumentParser(description="deck.yaml → 逐字讲稿 .md（排练用）")
    ap.add_argument("--deck", required=True)
    ap.add_argument("--out", default=None,
                    help="输出路径；默认与 deck 同目录 speech.md")
    ap.add_argument("--cps", type=int, default=SPEECH_CPS)
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.deck)),
                                "speech.md")
    try:
        total = export(a.deck, out, a.cps)
        print("OK: {}（{} 字 · 估 {:.1f} 分钟）".format(out, total, total / a.cps))
        return 0
    except Exception as e:
        print("FAIL: {}: {}".format(type(e).__name__, e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
