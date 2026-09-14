# -*- coding: utf-8 -*-
"""text_fit.py — 字体度量级文本拟合（PIL 实测字形宽度）

替代引擎里 1em/0.52em 的经验折行估算：用系统真实字体文件（msyh.ttc 等）
逐字实测宽度，得到每段折行数与所需高度。字体文件缺失时回退旧启发式。

设计对齐 aeromech-thesis 的 SimSun 度量 ×1.045 安全系数思路，
但 ppt-direct 直接用 PIL 实测，不再需要系数猜测。

用法:
    from text_fit import Fitter
    f = Fitter()
    f.fit(paras, font_name, size_pt, box_w_cm, box_h_cm, floor_pt=14)
    → (size_pt_final, est_lines, need_h_cm, overflow, shrunk_from)
"""
import os

FONT_FILES = {
    # CJK
    "微软雅黑": [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"],
    "黑体": [r"C:\Windows\Fonts\simhei.ttf"],
    "宋体": [r"C:\Windows\Fonts\simsun.ttc"],
    # 西文
    "calibri": [r"C:\Windows\Fonts\calibri.ttf"],
    "arial": [r"C:\Windows\Fonts\arial.ttf"],
    "times new roman": [r"C:\Windows\Fonts\times.ttf"],
}

CM_PER_PT = 1 / 28.3465
SHRINK_STEP_PT = 2      # 自动缩字号步长
HEIGHT_PAD_CM = 0.12    # 文本框内边距余量


class Fitter:
    """按真实字体度量做折行与高度估算；可自动降字号直至适配或触底。"""

    def __init__(self):
        self._cache = {}

    def _font(self, name, size_pt):
        key = (name.lower(), size_pt)
        if key in self._cache:
            return self._cache[key]
        font = None
        for cand in FONT_FILES.get(name.lower(), []) + [name]:
            if os.path.isfile(cand):
                try:
                    from PIL import ImageFont
                    font = ImageFont.truetype(cand, size_pt)
                    break
                except Exception:
                    continue
        self._cache[key] = font
        return font

    def measure_w(self, text, name, size_pt):
        """整串文字宽度（pt）。无字体文件时回退启发式。"""
        font = self._font(name, size_pt)
        if font is None:
            w = 0.0
            for ch in text:
                w += size_pt * (1.0 if ord(ch) > 0x2E7F
                                else (0.3 if ch == " " else 0.52))
            return w
        try:
            return font.getlength(text)
        except Exception:
            return size_pt * len(text)

    def wrap_lines(self, text, name, size_pt, box_w_cm):
        """折行（CJK 逐字断，西文按词断），返回行数。"""
        box_w_pt = box_w_cm / CM_PER_PT - 2  # 2pt 内边距
        if self.measure_w(text, name, size_pt) <= box_w_pt:
            return 1
        font = self._font(name, size_pt)
        lines, cur = 1, ""
        if font is not None:
            from PIL import ImageFont
            # 混合文本按字切（词断对中文不成立）
            for ch in text:
                if font.getlength(cur + ch) > box_w_pt:
                    lines += 1
                    cur = ch
                else:
                    cur += ch
            return lines
        # 启发式回退
        w = 0.0
        for ch in text:
            cw = size_pt * (1.0 if ord(ch) > 0x2E7F
                            else (0.3 if ch == " " else 0.52))
            if w + cw > box_w_pt:
                lines += 1
                w = cw
            else:
                w += cw
        return lines

    def need_height(self, paras, name, size_pt, box_w_cm, line_spacing=1.22):
        lines = sum(self.wrap_lines(p, name, size_pt, box_w_cm) for p in paras)
        return lines * size_pt * line_spacing * CM_PER_PT + HEIGHT_PAD_CM, lines

    def fit(self, paras, name, size_pt, box_w_cm, box_h_cm,
            floor_pt=None, line_spacing=1.22):
        """返回 (final_size, est_lines, need_h_cm, overflow, shrunk_from)。"""
        floor_pt = floor_pt or size_pt
        shrunk_from = None
        cur = size_pt
        while True:
            need_h, lines = self.need_height(paras, name, cur, box_w_cm,
                                             line_spacing)
            if need_h <= box_h_cm or cur <= floor_pt:
                return cur, lines, round(need_h, 2), need_h > box_h_cm + 0.05, shrunk_from
            if cur - SHRINK_STEP_PT < floor_pt:
                cur = floor_pt
                continue
            if shrunk_from is None:
                shrunk_from = cur
            cur -= SHRINK_STEP_PT


_FITTER = None


def get_fitter():
    global _FITTER
    if _FITTER is None:
        _FITTER = Fitter()
    return _FITTER


if __name__ == "__main__":
    f = Fitter()
    r = f.fit(["起落架收放系统故障模式分析与维修策略研究" * 2], "微软雅黑",
              18, 8.0, 3.0, floor_pt=12)
    print("fit:", r)
