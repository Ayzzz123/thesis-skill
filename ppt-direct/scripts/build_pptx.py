# -*- coding: utf-8 -*-
"""build_pptx.py — 组装器：deck.yaml + theme.yaml → 答辩PPT.pptx

deck.yaml 是逐页内容真源（schema 见 references/deck-schema.md）。
用法: python build_pptx.py --deck deck.yaml --theme theme.yaml
        --out 答辩PPT.pptx [--layout layout.json]
退出码: 0=成功；1=deck/theme 校验失败；2=渲染失败
"""
import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx_engine import DeckBuilder, load_theme, PLACEHOLDER_MARK

LAYOUTS = {"cover", "toc", "section", "content", "two_column",
           "image_text", "closing"}


def _bullets(raw):
    """接受 "文本" / [level, 文本] / {level, text} 三种写法。"""
    out = []
    for b in raw or []:
        if isinstance(b, str):
            out.append((0, b))
        elif isinstance(b, (list, tuple)) and len(b) == 2:
            out.append((int(b[0]), str(b[1])))
        elif isinstance(b, dict):
            out.append((int(b.get("level", 0)), str(b.get("text", ""))))
        else:
            raise ValueError(f"无法识别的要点格式: {b!r}")
    return out


def build(deck_path, theme_path, out_pptx, layout_json=None):
    with open(deck_path, "r", encoding="utf-8") as f:
        deck = yaml.safe_load(f)
    if not isinstance(deck, dict) or "slides" not in deck:
        raise ValueError("deck.yaml 缺少 slides 段")
    meta = deck.get("meta", {})
    theme = load_theme(theme_path)
    d = DeckBuilder(theme)

    slides = deck["slides"]
    toc_items = None  # 自动从 section 页收集

    for i, s in enumerate(slides, 1):
        layout = s.get("layout")
        if layout not in LAYOUTS:
            raise ValueError(f"第 {i} 页 layout 未知: {layout!r}，合法值 {sorted(LAYOUTS)}")
        notes = s.get("notes", "")

        if layout == "cover":
            d.add_cover(title=s.get("title", meta.get("title", PLACEHOLDER_MARK)),
                        presenter=s.get("presenter", meta.get("presenter", "")),
                        major=s.get("major", meta.get("major", "")),
                        school=s.get("school", meta.get("school", "")),
                        advisor=s.get("advisor", meta.get("advisor", "")),
                        date=s.get("date", meta.get("date", "")), notes=notes)
        elif layout == "toc":
            items = s.get("items")
            if items is None:
                if toc_items is None:
                    toc_items = [x.get("title", "") for x in slides
                                 if x.get("layout") == "section"]
                items = toc_items
            d.add_toc(items, title=s.get("title", "目录"), notes=notes)
        elif layout == "section":
            d.add_section(int(s.get("no", 0)), s.get("title", PLACEHOLDER_MARK),
                          notes=notes)
        elif layout == "content":
            d.add_content(s.get("title", PLACEHOLDER_MARK),
                          _bullets(s.get("bullets")), notes=notes,
                          kicker=s.get("kicker", ""))
        elif layout == "two_column":
            left, right = s.get("left", {}), s.get("right", {})
            d.add_two_column(s.get("title", PLACEHOLDER_MARK),
                             left.get("title", ""), [t for _, t in _bullets(left.get("bullets"))],
                             right.get("title", ""), [t for _, t in _bullets(right.get("bullets"))],
                             notes=notes)
        elif layout == "image_text":
            d.add_image_text(s.get("title", PLACEHOLDER_MARK),
                             s.get("image", ""), [t for _, t in _bullets(s.get("bullets"))],
                             notes=notes, image_side=s.get("image_side", "left"),
                             caption=s.get("caption", ""))
        elif layout == "closing":
            d.add_closing(title=s.get("title", "恳请各位老师批评指正"),
                          sub=s.get("sub", "谢谢聆听"), notes=notes)

    d.save(out_pptx, layout_json)
    return out_pptx


def main():
    ap = argparse.ArgumentParser(description="deck.yaml + theme.yaml → .pptx")
    ap.add_argument("--deck", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--layout", default=None, help="layout JSON sidecar 输出路径")
    a = ap.parse_args()
    try:
        out = build(a.deck, a.theme, a.out, a.layout)
    except (ValueError, FileNotFoundError, yaml.YAMLError) as e:
        print(f"FAIL: {e}")
        return 1
    except Exception as e:  # 渲染层异常不打印堆栈，给 LLM 友好输出
        print(f"FAIL(render): {type(e).__name__}: {e}")
        return 2
    print(f"OK: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
