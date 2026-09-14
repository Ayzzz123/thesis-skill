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

# 答辩叙事顺序：章节标题命中关键词时映射为答辩板块，未命中保留原标题。
# 注意「分析/识别」类词先于「方法/方案」判定：如「故障识别与分析方法」
# 属分析过程板块，而「研究方案/方法路线」属研究内容与方法板块。
SECTION_HINTS = [
    (r"绪论|引言|背景|意义", "研究背景与意义"),
    (r"分析|识别|仿真|计算|试验|实验|数据|结果|对比", "分析过程与结果"),
    (r"方案|方法|技术路线|理论|原理", "研究内容与方法"),
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

# aeromech-thesis S10 答辩产物目录（pptx 侧仅读，不写回）
DEFENSE_DIR = os.path.join(".aeromech", "artifacts", "defense")


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


def _extract_docx_images(docx_path, materials_dir):
    """docx 内嵌图片 → materials/figNN.ext（按文档内顺序编号）。
    只搬运原图，不自动生成图片页（配图放哪由 S3 人工决定）。返回抽出张数。"""
    from docx import Document
    doc = Document(docx_path)
    os.makedirs(materials_dir, exist_ok=True)
    n = 0
    for rel in doc.part.rels.values():
        if not rel.reltype.endswith("/image"):
            continue
        try:
            ext = os.path.splitext(rel.target_part.partname)[1] or ".png"
        except Exception:
            ext = ".png"
        n += 1
        out = os.path.join(materials_dir, f"fig{n:02d}{ext}")
        with open(out, "wb") as f:
            f.write(rel.target_part.blob)
    return n


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


# ---------------- aeromech S10 联动：答辩产物 → 板块顺序 + 问答备份页 ----------------

def _board_titles(text):
    """ppt-structure.md → 板块标题候选（按出现顺序，best-effort 解析）。"""
    titles = []
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        s = re.sub(r"^[-*+]\s+", "", s)
        s = re.sub(r"^(?:\d+|[一二三四五六七八九十]+)[、.．)）]\s*", "", s)
        s = s.strip()
        if 2 <= len(s) <= 24 and not s.startswith(("|", "```", "PPT", "页")):
            titles.append(s)
    return titles


def _qa_entries(text):
    """qa-bank.md → [(问题, 回答逻辑)]，支持表格行与列表项，上限 12 条。"""
    entries = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells or cells[0] in ("类别", "类型"):
                continue
            q = cells[1] if len(cells) > 1 else ""
            logic = cells[2] if len(cells) > 2 else ""
            if q and len(q) >= 4:
                entries.append((q, logic))
        else:
            m = re.match(r"^[-*]\s*(?:Q\d*\s*[:：.])?\s*(.{6,80})$", s)
            if m:
                entries.append((m.group(1), ""))
        if len(entries) >= 12:
            break
    return entries


def _read_defense(root):
    """读取 S10 答辩产物：ppt-structure.md 板块顺序 + qa-bank.md 预测问题库。
    两文件均缺失时返回空（不报错），走默认章节顺序、无问答备份页。"""
    ddir = os.path.join(root, DEFENSE_DIR)
    structure = []
    sp = os.path.join(ddir, "ppt-structure.md")
    if os.path.isfile(sp):
        with open(sp, encoding="utf-8") as f:
            structure = _board_titles(f.read())
    qa_items = []
    qp = os.path.join(ddir, "qa-bank.md")
    if os.path.isfile(qp):
        with open(qp, encoding="utf-8") as f:
            qa_items = _qa_entries(f.read())
    return structure, qa_items


def _order_sections(blocks, structure):
    """结构稿的板块顺序做偏向重排；未命中的板块保持原序。
    先做子串直接匹配（结构稿板块名优先），失败再走章节标题映射表。"""
    if not structure:
        return blocks
    ordered, rest = [], list(blocks)
    for cand in structure:
        c = _CH_PREFIX.sub("", cand).strip()
        matched = None
        if c:
            for b in rest:
                if c in b[0] or b[0] in c:
                    matched = b
                    break
        if matched is None:  # 兜底：按章节标题关键词映射
            name = _section_name(cand)
            for b in rest:
                if b[0] == name:
                    matched = b
                    break
        if matched is not None:
            ordered.append(matched)
            rest.remove(matched)
    return ordered + rest


def build_draft(chapters, meta, tier, structure=None, qa_items=None):
    per = TIER_BUDGET.get(tier, 2)
    blocks, seen = [], set()
    for title, body in chapters:
        sec = _section_name(title)
        if sec in seen:      # 同板块多章合并
            continue
        seen.add(sec)
        blocks.append((sec, _chapter_points(body, cap=4 * per)))
    blocks = _order_sections(blocks, structure or [])

    slides = [{"layout": "cover"}, {"layout": "toc"}]
    for no, (sec, pts) in enumerate(blocks, 1):
        slides.append({"layout": "section", "no": no, "title": sec,
                       "notes": ""})
        chunks = [pts[i:i + 4] for i in range(0, len(pts), 4)] or [[]]
        for j, chunk in enumerate(chunks[:per]):
            slides.append({
                "layout": "content",
                "title": sec if j == 0 else f"{sec}（续）",
                "bullets": chunk,      # 空则留给 S3 补全
                "notes": "",
            })
    slides.append({"layout": "closing"})

    # 问答备份页（附录，不占档位页数，置于致谢页之后）
    appendix = []
    for i in range(0, len(qa_items or []), 2):
        bullets = []
        for q, logic in (qa_items or [])[i:i + 2]:
            bullets.append(q)
            if logic:
                bullets.append(f"答：{logic[:60]}")
        appendix.append({
            "layout": "content", "kicker": "问答备份",
            "title": f"预测问答（{i // 2 + 1}）",
            "bullets": bullets,
            "notes": "问答备份页：被问到相关问题时翻至此页参考。",
            "appendix": True,
        })
    slides.extend(appendix)

    deck = {"meta": {"title": meta.get("title", "【待填】"),
                     "presenter": "【待填】", "major": meta.get("major", ""),
                     "school": "", "advisor": "", "date": "",
                     "page_tier": tier,
                     "appendix_pages": len(appendix)},
            "slides": slides}
    outline = {"sections": [s["title"] for s in slides
                            if s["layout"] == "section"],
               "page_budget": len(slides), "tier": tier,
               "appendix_pages": len(appendix),
               "defense_linked": bool(structure or qa_items)}
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
        structure, qa_items = [], []
        n_img = 0
        if a.aeromech:
            chapters, meta = _read_chapters_aeromech(a.aeromech)
            structure, qa_items = _read_defense(a.aeromech)
        elif a.docx:
            chapters, meta = _read_docx(a.docx)
            n_img = _extract_docx_images(
                a.docx, os.path.join(a.out, "materials"))
        else:
            chapters, meta = _read_md(a.md)
        if not chapters:
            print("FAIL: 未从输入源解析到任何章节")
            return 1
        deck, outline = build_draft(chapters, meta, a.tier,
                                    structure, qa_items)
        adir = os.path.join(a.out, ".pptdirect", "artifacts")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, "deck.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(deck, f, allow_unicode=True, sort_keys=False)
        with open(os.path.join(adir, "outline.yaml"), "w",
                  encoding="utf-8") as f:
            yaml.safe_dump(outline, f, allow_unicode=True, sort_keys=False)
        print(f"OK: {len(chapters)} 章 → {len(deck['slides'])} 页草稿 "
              f"（{adir}）")
        if n_img:
            print(f"OK: docx 抽出 {n_img} 张图 → "
                  f"{os.path.join(a.out, 'materials')}")
        return 0
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
