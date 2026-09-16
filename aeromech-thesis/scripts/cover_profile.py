# -*- coding: utf-8 -*-
"""cover_profile.py — 封面风格画像与模板首页定位（v1.6 test-8.0 通用化根因件）

背景：cover_align/cover_fill/cover_fidelity/color_fidelity 原假设封面=
"校徽/校名图片行 + 下划线填空横线"（BUG-021 场景=南农式封面）。换校即全线失效：
中飞院官方模板是**表格式封面**（值槽在表格单元格内、校名为文本非图片）。
本模块把两种合法封面风格抽象为画像，供各 QA 分派检查：
  style=lines   : 存在校徽类图片（bbox 近方形，w/h∈[0.8,1.25]）→ 图片行/横线/漂移类检查照常
  style=grid    : 无校徽类图片，封面主体为表格网格线 → 图片类与下划线类检查记 SKIP，
                  转由"表格网格逐格偏移一致"承担结构保真
resolve_page：模板 PDF 的封面页不一定是第 0 页（"规范+封面样例"合一母版），
  按"含标题关键词且含标签字段"评分选页，缺省页 0（v1.5 行为兼容）。
"""
import re

TITLE_TOKENS = ["毕业设计", "毕业论文", "学位论文"]
LABEL_TOKENS = ["姓名", "学号", "专业", "学院", "题目", "班级", "指导教师", "设计人"]


def _label_count(text):
    t = text.replace(" ", "").replace("　", "")
    return sum(1 for k in LABEL_TOKENS if k in t)


def resolve_page(doc, title_token=None):
    """返回 (page_index, detail)。评分：标题关键词 + 标签字段数；全 0 则回页 0。"""
    toks = [title_token] if title_token else TITLE_TOKENS
    best, best_score = 0, -1
    limit = min(len(doc), 12)
    for i in range(limit):
        t = doc[i].get_text().replace(" ", "").replace("　", "")
        s = 0
        if any(tok in t for tok in toks):
            s += 2
        s += _label_count(t)
        if s > best_score:
            best, best_score = i, s
    if best_score <= 0:
        return 0, "封面页定位失败（评分 0），按页 0 处理"
    return best, f"封面页=第 {best + 1} 页（评分 {best_score}）"


def images_of(page):
    out = []
    for im in page.get_images(full=True):
        for r in page.get_image_rects(im[0]):
            out.append((round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)))
    return sorted(out, key=lambda z: (z[1], z[0]))


def emblem_count(page):
    """校徽类图片=近方形 bbox（宽高比 0.8~1.25 且边长 ≥18pt）。"""
    n = 0
    for (x0, y0, x1, y1) in images_of(page):
        w, h = x1 - x0, y1 - y0
        if h > 18 and 0.8 <= w / h <= 1.25:
            n += 1
    return n


def profile(page):
    """返回 {style, emblems, gridlines}；gridlines=表格式封面的水平长线段数。"""
    em = emblem_count(page)
    if em:
        return {"style": "lines", "emblems": em}
    # 表格式封面：统计近全宽水平线段（表格横线）
    h_wide = 0
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.height < 3 and r.width > page.rect.width * 0.5:
            h_wide += 1
    style = "grid" if h_wide >= 4 else "lines"
    return {"style": style, "emblems": 0, "gridlines": h_wide}


def underline_rows(page):
    """下划线填空横线（窄高、宽>30pt）——lines 式封面字段行。"""
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.height < 2.5 and r.width > 30:
            out.append((round(r.x0, 1), round(r.x1, 1), round(r.y0, 1)))
    return sorted(out, key=lambda z: z[2])
