# -*- coding: utf-8 -*-
"""test_omml_word_compat.py — OMML 生成 Word 兼容性锁（v1.6 生成链，自 .codex/thesis-1.0 迁移）

背景：Word 对 OMML 做 schema 严格校验——m:sSub/m:sSup/m:sSubSup 的基底（第一个
实义子元素）必须是 m:e；生成器曾把 m:acc/m:d 裸放为基底（LibreOffice 宽容接受，
Word 报"文件可能已经损坏"，且"打开并修复"也无法恢复）。已在 thesis-1.0 真实
论文上经 Word COM 实证：仅修复 3 处裸基底后 Word OPEN = PASS。

本测试静态生成全部公式结构并断言 schema 形状：
  OMML-01 _math_sub / _math_sup 基底 = m:e（既有正确行为回归）
  OMML-02 _math_yhat_sub 基底 = m:e（修复：裸 acc → e(acc)）
  OMML-03 _math_squared_difference 基底 = m:e（修复：裸 d → e(d)）
  OMML-04 _append_omml_equation 全部公式端到端无裸基底
  OMML-05 通用 checker：scan_bare_math_bases 全文 = 0（负例可检出）
运行：python tests/v1_6/test_omml_word_compat.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


import template_fidelity as TF
from docx.oxml.ns import qn
from lxml import etree

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def first_arg(el):
    """m:sSub/sSup/sSubSup 的第一个实义子元素（跳过 *Pr）。"""
    for c in el:
        if not etree.QName(c).localname.endswith("Pr"):
            return etree.QName(c).localname, c
    return None, None


def scan_bare_math_bases(el):
    """扫描 el 内所有 sSub/sSup/sSubSup：基底非 m:e → 违规列表。"""
    bad = []
    for tag in ("sSub", "sSup", "sSubSup"):
        for s in el.iter(f"{{{M}}}{tag}"):
            name, _ = first_arg(s)
            if name != "e":
                bad.append((tag, name))
    return bad


class _Sink:
    """最小 parent 桩：append 后可取回最后一个元素。"""

    def __init__(self):
        self.children = []

    def append(self, el):
        self.children.append(el)


def main():
    print("== test_omml_word_compat ==")
    check("前置 _math_* 生成器存在", all(hasattr(TF, n) for n in
          ("_math_sub", "_math_sup", "_math_yhat_sub", "_math_squared_difference",
           "_append_omml_equation")))

    s = _Sink()
    TF._math_sub(s, "y", "i")
    name, el = first_arg(s.children[-1])
    t = el.find(f"{{{M}}}r/{{{M}}}t") if el is not None else None
    check("OMML-01a _math_sub 基底=m:e（含 y run）",
          name == "e" and t is not None and t.text == "y", name)
    s = _Sink()
    TF._math_sup(s, "N", "2")
    name, el = first_arg(s.children[-1])
    check("OMML-01b _math_sup 基底=m:e", name == "e", name)

    s = _Sink()
    TF._math_yhat_sub(s)
    name, el = first_arg(s.children[-1])
    check("OMML-02 _math_yhat_sub 基底=m:e（e>acc 结构）",
          name == "e" and etree.QName(el[0]).localname == "acc",
          "%s>%s" % (name, etree.QName(el[0]).localname if el is not None else None))

    s = _Sink()
    TF._math_squared_difference(s)
    name, el = first_arg(s.children[-1])
    check("OMML-03 _math_squared_difference 基底=m:e（e>d 结构）",
          name == "e" and etree.QName(el[0]).localname == "d",
          "%s>%s" % (name, etree.QName(el[0]).localname if el is not None else None))

    # OMML-04 端到端：全部公式进真实 docx 段落（函数消费 Paragraph 对象），全文扫描
    import docx as _docx
    d = _docx.Document()
    src = open(TF.__file__, encoding="utf-8").read()
    import re as _re
    kinds_found = sorted(set(_re.findall(r'kind == "(\w+)"', src)))
    kinds = []
    for k in kinds_found:
        p = d.add_paragraph()
        try:
            TF._append_omml_equation(p, k)      # 传 Paragraph 对象（内部用 p._p）
            kinds.append(k)
        except Exception as e:
            print("  [warn] kind=%s 生成失败: %s" % (k, e))
    check("OMML-04a 公式 kinds 生成成功", len(kinds) >= 2, "found=%s ok=%s" % (kinds_found, kinds))
    bad = scan_bare_math_bases(d.element.body)
    check("OMML-04b 全部公式端到端无裸基底", not bad, str(bad[:4]))
    check("OMML-04c 生成含 oMath（OMML 未被降级删除）",
          len(d.element.body.findall(f".//{{{M}}}oMath")) >= len(kinds) and len(kinds) >= 2)

    # OMML-05 通用 checker 可用性（负例：人工构造裸基底必须被抓到）
    from docx.oxml import OxmlElement
    ssub = OxmlElement("m:sSub")
    acc = OxmlElement("m:acc")
    ssub.append(acc)
    sub = OxmlElement("m:sub")
    ssub.append(sub)
    holder = OxmlElement("w:p")
    holder.append(ssub)
    check("OMML-05 checker 负例（裸 acc 被识别）",
          scan_bare_math_bases(holder) == [("sSub", "acc")])

    print(f"test_omml_word_compat 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
