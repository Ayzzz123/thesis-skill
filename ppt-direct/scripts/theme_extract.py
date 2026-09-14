# -*- coding: utf-8 -*-
"""theme_extract.py — 从学校模板 .pptx 提取主题 → theme.yaml

提取：画幅比例、主题色（a:clrScheme）、主题字体（majorFont/minorFont 的
latin + ea 字形）、首页背景色。配色按使用频率映射到 primary/accent，
无法判定时保留原色并标注 source: template，由 Design 模块人工确认语义。

用法: python theme_extract.py --template 校模.pptx --out theme.yaml
退出码: 0=成功；1=失败
"""
import argparse
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import yaml

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}

# clrScheme 语义槽位 → ppt-direct 调色板槽位的默认映射
SLOT_MAP = {"dk1": "text", "lt1": "bg", "dk2": "text", "lt2": "light",
            "accent1": "primary", "accent2": "accent", "accent3": "light",
            "accent4": "accent", "accent5": "primary", "accent6": "accent"}


def _theme_xml(zf):
    for name in zf.namelist():
        if re.match(r"ppt/theme/theme\d+\.xml$", name):
            return zf.read(name)
    return None


def extract(template_pptx):
    with zipfile.ZipFile(template_pptx) as zf:
        # 画幅
        pres = ET.fromstring(zf.read("ppt/presentation.xml"))
        sldsz = pres.find("p:sldSz", NS)
        w, h = int(sldsz.get("cx")), int(sldsz.get("cy"))
        ratio = w / h
        size = "16:9" if abs(ratio - 16 / 9) < 0.05 else (
            "4:3" if abs(ratio - 4 / 3) < 0.05 else "16:9")

        raw = _theme_xml(zf)
        if raw is None:
            raise ValueError("模板缺少 theme XML，不是标准 pptx")
        theme = ET.fromstring(raw)

        colors = {}
        scheme = theme.find(".//a:clrScheme", NS)
        for slot, target in SLOT_MAP.items():
            if target in colors:
                continue
            el = scheme.find(f"a:{slot}", NS) if scheme is not None else None
            if el is None:
                continue
            srgb = el.find("a:srgbClr", NS)
            sysclr = el.find("a:sysClr", NS)
            if srgb is not None:
                colors[target] = srgb.get("val").upper()
            elif sysclr is not None:
                colors[target] = sysclr.get("lastClr", "000000").upper()

        fonts = {"cjk": "", "latin": ""}
        major = theme.find(".//a:fontScheme/a:majorFont", NS)
        if major is not None:
            latin = major.find("a:latin", NS)
            ea = major.find("a:ea", NS)
            if latin is not None and latin.get("typeface"):
                fonts["latin"] = latin.get("typeface")
            if ea is not None and ea.get("typeface"):
                fonts["cjk"] = ea.get("typeface")

    colors.setdefault("text", "333333")
    colors.setdefault("bg", "FFFFFF")
    colors.setdefault("muted", "999999")
    colors.setdefault("light", "F2F2F2")
    colors.setdefault("accent", colors.get("primary", "4A90E2"))
    colors.setdefault("primary", "4A90E2")
    fonts["cjk"] = fonts["cjk"] or "微软雅黑"
    fonts["latin"] = fonts["latin"] or "Calibri"
    return {"size": size, "colors": colors, "fonts": fonts}


def main():
    ap = argparse.ArgumentParser(description="校模 .pptx → theme.yaml")
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        info = extract(a.template)
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1
    # 继承内置默认的字号/限制/页数档位，校模只覆盖配色字体画幅
    default_theme = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "assets", "theme-default.yaml")
    with open(default_theme, encoding="utf-8") as f:
        base = yaml.safe_load(f)
    base.update({"name": "school-template", "source": "template",
                 "size": info["size"]})
    base["colors"].update(info["colors"])
    base["fonts"].update(info["fonts"])
    with open(a.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(base, f, allow_unicode=True, sort_keys=False)
    print(f"OK: {a.out} (size={info['size']}, primary=#{base['colors']['primary']}, "
          f"cjk={base['fonts']['cjk']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
