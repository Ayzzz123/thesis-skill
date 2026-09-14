# -*- coding: utf-8 -*-
"""ingest_source.py — 输入源解析：.aeromech 项目 / 论文 docx / md → 大纲 + deck 草稿

诚信守卫：只搬运用户已有内容（章节标题、首句、结论条目），不生成新论断；
无内容可搬运的页面保留空 bullets + 【待填】标记，由 S3 逐页内容阶段人工补全。

用法:
  python ingest_source.py --aeromech <论文工程目录> --out <ppt工程目录>
  python ingest_source.py --docx 论文.docx --out <ppt工程目录>
  python ingest_source.py --md 论文.md --out <ppt工程目录>
退出码: 0=成功；1=失败
"""
import argparse
import glob
import os
import re
import sys

import yaml

# 答辩叙事顺序：章节标题命中关键词时映射为答辩板块，未命中保留原标题
SECTION_HINTS = [
    (r"绪论|引言|背景|意义", "研究背景与意义"),
    (r"方案|方法|技术路线|理论|原理", "研究内容与方法"),
    (r"分析|识别|仿真|计算|试验|实验|数据|结果|对比", "分析过程与结果"),
    (r"策略|优化|设计|建议|应用|改进", "方案与建议"),
    (r"结论|总结|展望", "结论与展望"),
]

_CH_PREFIX = re.compile(r"^第\s*[0-9一二三四五六七八九十]+\s*[章部分编]\s*")


def _section_name(title):
    for pat, name in SECTION_HINTS:
        if re.search(pat, title):
            return name
    return _CH_PREFIX.sub("", title).strip() or title

TIER_BUDGET = {"short": 1, "standard": 2, "long": 3}  # 每板块内容页数上限


# 非正文文件：答辩叙事不覆盖前置页/参考文献/附录
SKIP_FILES = re.compile(r"front|reference|appendix|appendices", re.I)


def _read_chapters_aeromech(root):
    ch_dir = os.path.join(root, ".aeromech", "artifacts", "chapters")
    files = sorted(glob.glob(os.path.join(ch_dir, "*.md")))
    chapters = []
    for fp in files:
        if SKIP_FILES.search(os.path.basename(fp)):
            continue
        with open(fp, encoding="utf-8") as f:
            body = f.read()
        m = re.search(r"(?m)^#\s+(.+)$", body)
        title = m.group(1).strip() if m else os.path.basename(fp)
        chapters.append((title, body))
    state_fp = os.path.join(root, ".aeromech", "state.yaml")
    meta = {}
    if os.path.isfile(state_fp):
        with open(state_fp, encoding="utf-8") as f:
            st = yaml.safe_load(f)
        p = st.get("project", {})
        meta = {"title": p.get("title", ""), "major": p.get("major", "")}
    return chapters, meta


def _read_docx(path):
    from docx import Document
    doc = Document(path)
    chapters, cur = [], None
    for para in doc.paragraphs:
        style = (para.style.name or "") if para.style else ""
        text = para.text.strip()
        if not text:
            continue
        if style.startswith("Heading 1") or style == "标题 1":
            cur = [text, []]
            chapters.append(cur)
        elif cur is not None:
            cur[1].append(text)
    return [("# " + t, "\n".join(ps)) for t, ps in chapters], {}


def _read_md(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"(?m)^# ", text)
    chapters = []
    for p in parts[1:]:
        title, _, body = p.partition("\n")
        chapters.append((title.strip(), body))
    return chapters, {}


def _section_name(title):
    for pat, name in SECTION_HINTS:
        if re.search(pat, title):
            return name
    return title[:14]


def _chapter_points(body, cap):
    """从章节正文提取要点：二级标题 + 各段首句，截断 cap 条。"""
    points = [m.strip() for m in re.findall(r"(?m)^##\s+(.+)$", body)]
    if len(points) < cap:
        for para in re.split(r"\n\s*\n", body):
            s = para.strip().split("。")[0].strip()
            if 12 <= len(s) <= 60 and not s.startswith(("#", "|", "!")):
                points.append(s)
            if len(points) >= cap * 2:
                break
    return points[:cap]


def build_draft(chapters, meta, tier):
    per = TIER_BUDGET.get(tier, 2)
    slides = [{"layout": "cover"}, {"layout": "toc"}]
    no = 0
    seen = set()
    for title, body in chapters:
        sec = _section_name(title)
        if sec in seen:      # 同板块多章合并
            continue
        seen.add(sec)
        no += 1
        slides.append({"layout": "section", "no": no, "title": sec,
                       "notes": ""})
        pts = _chapter_points(body, cap=4 * per)
        chunks = [pts[i:i + 4] for i in range(0, len(pts), 4)] or [[]]
        for j, chunk in enumerate(chunks[:per]):
            slides.append({
                "layout": "content",
                "title": sec if j == 0 else f"{sec}（续）",
                "bullets": chunk,      # 空则留给 S3 补全
                "notes": "",
            })
    slides.append({"layout": "closing"})
    deck = {"meta": {"title": meta.get("title", "【待填】"),
                     "presenter": "【待填】", "major": meta.get("major", ""),
                     "school": "", "advisor": "", "date": "",
                     "page_tier": tier},
            "slides": slides}
    outline = {"sections": [s["title"] for s in slides
                            if s["layout"] == "section"],
               "page_budget": len(slides), "tier": tier}
    return deck, outline


def main():
    ap = argparse.ArgumentParser(description="输入源 → 大纲 + deck 草稿")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--aeromech")
    g.add_argument("--docx")
    g.add_argument("--md")
    ap.add_argument("--out", required=True, help="ppt 工程目录")
    ap.add_argument("--tier", default="standard",
                    choices=["short", "standard", "long"])
    a = ap.parse_args()
    try:
        if a.aeromech:
            chapters, meta = _read_chapters_aeromech(a.aeromech)
        elif a.docx:
            chapters, meta = _read_docx(a.docx)
        else:
            chapters, meta = _read_md(a.md)
        if not chapters:
            print("FAIL: 未从输入源解析到任何章节")
            return 1
        deck, outline = build_draft(chapters, meta, a.tier)
        adir = os.path.join(a.out, ".pptdirect", "artifacts")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, "deck.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(deck, f, allow_unicode=True, sort_keys=False)
        with open(os.path.join(adir, "outline.yaml"), "w",
                  encoding="utf-8") as f:
            yaml.safe_dump(outline, f, allow_unicode=True, sort_keys=False)
        print(f"OK: {len(chapters)} 章 → {len(deck['slides'])} 页草稿 "
              f"（{adir}）")
        return 0
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
