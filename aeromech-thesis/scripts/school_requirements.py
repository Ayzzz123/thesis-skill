# -*- coding: utf-8 -*-
"""school_requirements.py — School Requirement Parser（aeromech-thesis v1.6.0）

规则真源：references/state.md §16.2（三层格式模型：general_principles / general_defaults /
school_specific_unknown；format_source: school_template|sample_thesis|general_default|unknown）。
本脚本把"学校要求"从 Agent 手读升格为结构化 School Requirement Context：
  材料目录扫描 → 正式模板/规范（official）与往届样文（sample）分离 → docx 结构性字段机械提取
  → 逐字段 provenance（official/sample/default/unknown）→ 写入 school-format.yaml（additive 字段
  `school_requirement`，不改 §16.2 既有键语义）。

硬纪律（指令 §九）：**样例论文永远不得标为 official**；提取不了的字段 = unknown，不猜、不落假值。
PDF/扫描件规范不做关键词猜测式解析（会产生"看似合理的错误数字"）：登记为 official_spec 来源，
字段保持 unknown，交人工/后续核对。

子命令：
  parse  <root> [--out <file.yaml>] [--json]   # 解析并写 .aeromech/school-format.yaml（合并保留既有键）
  show   <root>                                # 打印当前字段 provenance 摘要
退出码：0=成功（含"无模板，全 default/unknown"的合法结果）；1=材料冲突需人工；3=ERROR（依赖缺失/解析崩溃）
"""
import argparse
import datetime
import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

PROVENANCE_LEVELS = ["official", "sample", "default", "unknown"]
CM = 360000.0  # EMU per cm（python-docx Length.emu）

# 提取不了、但规范文本可能提及的字段清单（指令 §九 的覆盖表；一律先落 unknown）
FIELD_KEYS = ["page_size", "margins", "font_body", "font_size_body", "line_spacing",
              "heading_format", "abstract", "reference", "figure", "table", "cover",
              "page_number", "sections", "special"]


def _p(root, *parts):
    return os.path.join(root, ".aeromech", *parts)


def _school_dir(root):
    for cand in (os.path.join(root, "materials", "school"), _p(root, "materials", "school")):
        if os.path.isdir(cand):
            return cand
    return None


def _samples_dir(root):
    for cand in (os.path.join(root, "materials", "samples"), _p(root, "materials", "samples")):
        if os.path.isdir(cand):
            return cand
    return None


def _is_template_name(fn):
    return bool(re.search(r"模板|template", fn, re.I))


def _is_sample_name(fn):
    return bool(re.search(r"范文|样文|示例|往届", fn, re.I))


def extract_docx_struct(path):
    """从 .docx/.dotx 机械提取结构事实（页面/边距/正文样式/标题样式）。
    只提取 Word 对象树里真实存在的值；缺失即不落。返回 {field: value}。"""
    try:
        from docx import Document
        from docx.enum.style import WD_STYLE_TYPE
    except ImportError:
        raise RuntimeError("缺少 python-docx，无法解析模板（依赖缺失 = ERROR，不是 unknown）")
    doc = Document(path)
    out = {}
    sec = doc.sections[0]
    if sec.page_width and sec.page_height:
        w, h = sec.page_width / CM, sec.page_height / CM
        out["page_size"] = {"width_cm": round(w, 2), "height_cm": round(h, 2)}
    mg = {}
    for k, v in (("top", sec.top_margin), ("bottom", sec.bottom_margin),
                 ("left", sec.left_margin), ("right", sec.right_margin)):
        if v is not None:
            mg[k + "_cm"] = round(v / CM, 2)
    if mg:
        out["margins"] = mg
    try:
        st = doc.styles["Normal"]
        f = st.font
        val = {}
        if f.name:
            val["ascii"] = f.name
        rpr = st.element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts')
        if rpr is not None:
            ea = rpr.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia')
            if ea:
                val["east_asia"] = ea
        if f.size:
            val["size_pt"] = f.size.pt
        if val:
            out["font_body"] = val.get("east_asia") or val.get("ascii")
            if "size_pt" in val:
                out["font_size_body"] = val["size_pt"]
        pf = st.paragraph_format
        if pf.line_spacing:
            out["line_spacing"] = (round(pf.line_spacing, 2) if pf.line_spacing_rule is None or
                                   "MULTIPLE" in str(pf.line_spacing_rule) else str(pf.line_spacing_rule))
    except (KeyError, AttributeError):
        pass
    heads = {}
    for i in (1, 2, 3):
        try:
            hs = doc.styles[f"Heading {i}"]
            if hs.type != WD_STYLE_TYPE.PARAGRAPH:
                continue
            hv = {}
            if hs.font.size:
                hv["size_pt"] = hs.font.size.pt
            if hs.font.name:
                hv["ascii"] = hs.font.name
            rpr = hs.element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts')
            if rpr is not None:
                ea = rpr.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia')
                if ea:
                    hv["east_asia"] = ea
            if hv:
                heads[f"level{i}"] = hv
        except KeyError:
            continue
    if heads:
        out["heading_format"] = heads
    return out


def parse(root):
    """返回 (school_requirement dict, meta dict)。不写文件。"""
    school = _school_dir(root)
    samples = _samples_dir(root)
    fields = {k: {"value": None, "provenance": "unknown", "source_material": None} for k in FIELD_KEYS}
    conflicts = []
    docs = []
    if school:
        for fn in sorted(os.listdir(school)):
            low = fn.lower()
            if low.startswith("~$") or not low.endswith((".docx", ".dotx", ".doc", ".pdf")):
                continue
            docs.append((os.path.join(school, fn), "school"))
    sample_docs = []
    if samples:
        sample_docs = [os.path.join(samples, fn) for fn in sorted(os.listdir(samples))
                       if fn.lower().endswith((".docx", ".pdf", ".doc")) and not fn.startswith("~$")]

    def apply(flds, prov, src):
        for k, v in flds.items():
            if v is None:
                continue
            cur = fields.get(k)
            if cur is None:
                continue
            if cur["value"] is not None and cur["provenance"] != prov:
                # 低层级来源不得覆盖高层级；同级冲突须记录
                conflicts.append({"field": k, "kept": cur["source_material"],
                                  "ignored": src, "reason": f"{cur['provenance']} 优先于 {prov}"})
                continue
            fields[k] = {"value": v, "provenance": prov, "source_material": src}

    official_template = None
    fields.setdefault("_notes", {"value": [], "provenance": "unknown", "source_material": None})
    for path, _ in docs:
        fn = os.path.basename(path)
        rel = os.path.relpath(path, root).replace("\\", "/")
        if path.lower().endswith((".docx", ".dotx")):
            # 目录契约：materials/school/ 下的文件是学校提供的；命名像样文的按 sample 降级
            prov = "sample" if _is_sample_name(fn) else "official"
            try:
                flds = extract_docx_struct(path)
            except RuntimeError:
                raise
            except Exception as e:
                conflicts.append({"field": "*", "kept": None, "ignored": rel,
                                  "reason": f"docx 解析失败（保持 unknown）：{e}"})
                continue
            apply(flds, prov, rel)
            if _is_template_name(fn) and prov == "official":
                official_template = path
        elif path.lower().endswith(".pdf"):
            # PDF/扫描件规范：不猜字段（避免"看似合理的错误数字"）；登记来源，字段保持 unknown
            fields["_official_spec_documents"] = {
                "value": (fields.get("_official_spec_documents", {}).get("value") or []) + [rel],
                "provenance": "official", "source_material": rel}
            fields["_notes"]["value"].append(
                f"PDF 规范未做字段提取（避免猜测），相关字段保持 unknown，待人工核对后录入：{rel}")
        else:  # legacy .doc：需 Word COM 转换（convert_legacy_doc），本工具不静默处理
            fields["_notes"]["value"].append(f"旧格式 .doc 需先 convert_legacy_doc 再解析：{rel}")

    for path in sample_docs:
        if not path.lower().endswith((".docx", ".dotx")):
            continue
        try:
            flds = extract_docx_struct(path)
        except RuntimeError:
            raise
        except Exception:
            continue
        # 样文永远只补 unknown 字段，且 provenance=sample（不得冒充正式要求）
        for k, v in flds.items():
            if fields[k]["value"] is None:
                fields[k] = {"value": v, "provenance": "sample",
                             "source_material": os.path.relpath(path, root).replace("\\", "/")}

    # 模式判定与母版选择：复用 template_fidelity.select_docx_mode（不另造规则）
    import template_fidelity as TF
    mode, tpl = TF.select_docx_mode(_school_dir(root))
    if tpl and _is_template_name(os.path.basename(tpl)):
        official_template = tpl
    template = official_template or (tpl if mode == TF.MODE_TEMPLATE_FIDELITY else None)

    any_official = any(f["provenance"] == "official" for f in fields.values())
    any_sample = any(f["provenance"] == "sample" for f in fields.values())
    extracted = [k for k in FIELD_KEYS if fields[k]["value"] is not None]
    full = len(extracted) == len(FIELD_KEYS)
    fmt_source = ("school_template" if template else
                  "sample_thesis" if any_sample and not any(f["provenance"] == "official"
                                                            for k, f in fields.items()
                                                            if not k.startswith("_") and f["value"] is not None) else
                  "general_default" if not (any_official or any_sample) else
                  "school_template" if any_official else "unknown")
    meta = {"format_source": fmt_source,
            "format_status": "complete" if full else ("partial" if extracted else "missing"),
            "docx_mode": mode, "template_file": template,
            "parsed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    return fields, meta, conflicts


def write_school_format(root, fields, meta, conflicts):
    """合并写入：保留 §16.2 既有键（存在则不破坏），additive 更新 school_requirement/format_*。"""
    p = _p(root, "school-format.yaml")
    data = {}
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    base = data if isinstance(data, dict) else {}
    base["format_source"] = meta["format_source"]
    base["format_status"] = meta["format_status"]
    if "general_principles" not in base:
        base["general_principles"] = ["图表必须有编号和题注", "标题需要有层级（至少三级）",
                                      "参考文献需要统一格式（如 GB/T 7714）",
                                      "正文、图表、参考文献应保持一致性",
                                      "摘要需包含研究背景、方法、结果、结论四要素"]
    base["school_requirement"] = {
        "parsed_at": meta["parsed_at"],
        "docx_mode": meta["docx_mode"],
        "template_file": meta["template_file"],
        "fields": fields,
        "source_conflicts": conflicts,
    }
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(base, f, allow_unicode=True, sort_keys=False)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description="School Requirement Parser（v1.6）")
    ap.add_argument("root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("parse")
    pp.add_argument("--json", action="store_true")
    sh = sub.add_parser("show")
    sh.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    try:
        if a.cmd == "parse":
            fields, meta, conflicts = parse(root)
            p = write_school_format(root, fields, meta, conflicts)
            if a.json:
                print(json.dumps({"out": p, "meta": meta,
                                  "extracted": [k for k, v in fields.items() if isinstance(v, dict) and v.get("value") is not None],
                                  "unknown": [k for k, v in fields.items() if isinstance(v, dict) and v.get("value") is None],
                                  "conflicts": conflicts}, ensure_ascii=False))
            else:
                print(f"已写入 {p}")
                print(f"format_source={meta['format_source']} format_status={meta['format_status']} "
                      f"docx_mode={meta['docx_mode']}")
                for k, v in fields.items():
                    if k.startswith("_"):
                        continue
                    tag = v["provenance"]
                    print(f"  {k:<14} {tag:<8} {v['value'] if v['value'] is not None else '（unknown）'}")
                for c in conflicts:
                    print(f"  [conflict] {c['field']}: {c['reason']}")
            return 1 if conflicts else 0
        if a.cmd == "show":
            p = _p(root, "school-format.yaml")
            if not os.path.isfile(p):
                print("无 school-format.yaml（尚未 parse）")
                return 2
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            sr = data.get("school_requirement") or {}
            print(json.dumps({"format_source": data.get("format_source"),
                              "format_status": data.get("format_status"),
                              "fields": sr.get("fields"),
                              "conflicts": sr.get("source_conflicts")}, ensure_ascii=False, indent=1))
            return 0
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
