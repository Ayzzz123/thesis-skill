# -*- coding: utf-8 -*-
"""research_quality_qa.py — Research Quality Gate 检查器（aeromech-thesis v1.4.0）

对 Research Integrity 注册表（.aeromech/research/）与论文文本执行 RQG-01~15 检查、
Evidence Coverage 计算、结论可追溯与摘要一致性校验，输出评分与门禁结论。
用法：
  python research_quality_qa.py --project <root> [--pdf <final.pdf>] [--out <dir>]
退出码：0=RI Gate PASS；1=存在 Critical/High（RI Gate FAIL）；2=注册表未初始化（旧项目兼容）
"""
import argparse
import glob
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("需要 PyYAML")
    sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_integrity as RI

# 强断言 × 弱证据：Critical 模式（机队/实测/统计口径）
STRONG_PATTERNS_CRIT = ["机队", "实际运行", "实测", "试验表明", "试验测", "统计表明", "发生率为"]
# 强断言 × 弱证据：High 模式（推断强度超出证据）
STRONG_PATTERNS_HIGH = ["证明", "显著", "普遍", "必然", "充分说明"]
# 模拟数据不得使用的"实验口径"措辞
SYNTH_STRONG = ["实验结果表明", "实测发现", "统计显示", "试验结果表明"]
# 真实数据身份声明（模拟数据场景下出现即越界）
REAL_CLAIM = ["实测", "试验测得", "机队统计", "实际运行数据"]
# 否定语境（用于排除"不代表真实机队统计特征"式免责句）
NEG_RE = re.compile(r"(不|非|未|无|禁止|不能|无法)")

# v1.4.1 状态模型：PASS / WARN / FAIL / NEEDS_HUMAN_REVIEW（启发式 Critical 项不得自动 PASS）
ST_NHR = "NEEDS_HUMAN_REVIEW"

RQG_REMEDIATION = {
    "RQG-00": "修复注册表结构/引用问题（RI-* 见 research_integrity.py 的 remediation 输出）后重跑",
    "RQG-01": "在 rq.yaml 补齐研究问题 question/objective（≥8/≥4 字）后重跑",
    "RQG-02": "重写 objective 使其与研究问题共享核心实词（目标须直接回应问题）",
    "RQG-03": "为每个 RQ 建立方法链接并在正文中出现方法名",
    "RQG-04": "补齐方法选择依据 basis，并在正文写明方法选择论证",
    "RQG-05": "为数据集补齐 source；真实数据补 source_location",
    "RQG-06": "为模拟/假定数据集补齐 label=【假设/模拟·仅演示方法】并在正文/表注出现",
    "RQG-07": "为分析补齐 inputs（引用 DS/E/CALC）",
    "RQG-08": "为结论补齐 claims/analyses 回溯链",
    "RQG-09": "修正摘要与正文的不一致（数值/身份措辞/结论覆盖）；或按人工复核清单裁决后回填",
    "RQG-10": "下调表述强度/补充证据，或按人工复核清单裁决（violation 将保持 FAIL）",
    "RQG-11": "为图表补齐 related_rqs/analyses/claims 论证链接",
    "RQG-12": "让注册文献证据的引用编号在正文出现（或退回未注册状态）",
    "RQG-13": "为正文数字句补充引用编号/计算标注（提升至 ≥50%）",
    "RQG-14": "补齐计算的 inputs/formula/verification",
    "RQG-15": "补研究限制论述，并在限制中声明模拟数据边界",
    "RQG-HR": "按人工复核结论修改后重跑（记录保留在 human-review.yaml）",
    "RQG-ERR": "修复内部错误（常见：章节文件缺失/YAML 损坏）后重跑",
    "RQG-HR-WARN": "核对 human-review.yaml 键名与当前队列是否一致",
}


class Report:
    def __init__(self, out_dir):
        self.items = []
        self.out_dir = out_dir

    def add(self, code, name, status, severity, detail):
        self.items.append({"code": code, "name": name, "status": status,
                           "severity": severity, "detail": detail})
        print(f"  {code} {name}: {status} | {detail}")

    @property
    def fails(self):
        return [i for i in self.items if i["status"] == "FAIL"]

    @property
    def hard_fails(self):
        return [i for i in self.fails if i["severity"] in ("Critical", "High")]


# ---------------- 文本源 ----------------
def load_texts(root):
    ch_dir = os.path.join(root, ".aeromech", "artifacts", "chapters")
    texts = {"front": "", "conclusion": "", "chapters": "", "plan": ""}
    files = sorted(glob.glob(os.path.join(ch_dir, "*.md"))) if os.path.isdir(ch_dir) else []
    chapter_parts = []
    for f in files:
        t = open(f, encoding="utf-8").read()
        base = os.path.basename(f).lower()
        if "front" in base or "abstract" in base or "摘要" in base:
            texts["front"] += "\n" + t
        elif "conclusion" in base or "结论" in base:
            texts["conclusion"] += "\n" + t
        else:
            chapter_parts.append(t)
    texts["chapters"] = "\n".join(chapter_parts)
    plan = os.path.join(root, ".aeromech", "artifacts", "research-plan.md")
    if os.path.isfile(plan):
        texts["plan"] = open(plan, encoding="utf-8").read()
    texts["all"] = texts["front"] + "\n" + texts["chapters"] + "\n" + texts["conclusion"] + "\n" + texts["plan"]
    if not texts["all"].strip():
        pdf = os.path.join(root, "毕业论文.pdf")
        if os.path.isfile(pdf):
            import pymupdf
            doc = pymupdf.open(pdf)
            texts["all"] = "\n".join(doc[i].get_text() for i in range(len(doc)))
            texts["front"] = "\n".join(doc[min(i, 3)].get_text() for i in range(0, min(4, len(doc))))
            texts["chapters"] = texts["all"]
    return texts


def nz(s):
    return re.sub(r"\s+", "", s or "")


STOP = set("的 了 与 和 或 及 在 对 是 为 以 从 到 于 中 上 下 有 无 这 那 其 被 将 能 可 等 一个 一种 进行 分析 研究 该 本 文 章 节 并 而 且 也 都 还 要 应 须 得 之 所 由 向 把 使 让".split())


def keywords_of(text):
    """中文实词集合：2~6 字连续片段 + 其 2/3-gram 展开（避免 6 字窗口对齐失败）。"""
    words = re.findall(r"[\u4e00-\u9fff]{2,6}", text or "")
    kws = set()
    for w in words:
        if w not in STOP:
            kws.add(w)
        for n in (2, 3):
            for i in range(len(w) - n + 1):
                g = w[i:i + n]
                if g not in STOP:
                    kws.add(g)
    return kws


# 数值 + 可选单位/百分号（用于摘要↔正文数值一致性与数字可追溯）；英文单位用白名单避免误吞单词
_NUM_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([%％]|(?:MPa|kPa|GPa|kN|kW|MW|Hz|dB|kg|km|mm|cm|ms|min|m|s|h|g|t|V|A|N|W|Pa|J)\b"
    r"|[万千百亿倍类个条架次元米秒吨牛瓦安伏欧帕焦]|小时|分钟|年|月|日|天)?")


def numbers_of(text):
    """提取关键数值（含单位）；排除年份、无单位的 1~2 位短整数（小节号/序号）。
    v1.6 test-8.0：另排除标识符后缀——前一个字符为 '-' 或 '=' 的数字（E-008、M-001、
    DS-001、CCAR-145、seed=20260915 等）是 ID 不是数据声称，计入分母会稀释
    "重要数字可追溯率"这一指标的本意。"""
    out = set()
    for m in _NUM_RE.finditer(text or ""):
        num, unit = m.group(1), m.group(2)
        if re.fullmatch(r"(19|20)\d{2}", num):
            continue
        if "." not in num and len(num) <= 2 and not unit:
            continue
        # 无单位纯小数（4.1、5.2、3.3.1）= 小节交叉引用，非数据声称
        #（v1.6 test-8.0；带单位小数如 16.5cm/1.8次 仍计入）
        if "." in num and not unit:
            continue
        prev = text[m.start() - 1] if m.start() > 0 else ""
        if prev == "-":
            continue  # ID 后缀：E-008 / M-001 / MC-1 / CCAR-145
        if prev == "=" and m.start() > 1 and text[m.start() - 2].isascii() and text[m.start() - 2].isalpha():
            continue  # 具名参数赋值：seed=20260915（区别于计算输出 "E1=162" 的数字左值）
        out.add(num + (unit or ""))
    return out


def _claim_hits(text, words, neg_window=8):
    """返回未被否定语境覆盖的强断言词（'不代表真实机队统计特征' 不触发）。"""
    hits = []
    for w in words:
        start = 0
        while True:
            i = (text or "").find(w, start)
            if i < 0:
                break
            if not NEG_RE.search((text or "")[max(0, i - neg_window):i]):
                hits.append(w)
                break
            start = i + len(w)
    return hits


def _pdf_caption_stats(pdf_path):
    """从 PDF 提取图/表题注数量（用于图表注册 VS 文档一致性）。"""
    if not pdf_path or not os.path.isfile(pdf_path):
        return None
    try:
        import pymupdf
    except ImportError:
        return None
    doc = pymupdf.open(pdf_path)
    txt = "\n".join(doc[i].get_text() for i in range(len(doc)))
    figs = set(re.findall(r"图\s*(\d+)\s*[-–—.]\s*(\d+)", txt))
    tables = set(re.findall(r"表\s*(\d+)\s*[-–—.]\s*(\d+)", txt))
    return {"fig_captions": len(figs), "table_captions": len(tables)}


def _run_impl(root, out_dir=None, pdf=None, verbose=True):
    """执行 RQG-01~15；返回 (summary, Report)。"""
    out_dir = out_dir or os.path.join(root, ".aeromech", "artifacts", "qa")
    rep = Report(out_dir)
    review_items = []   # v1.4.1 人工复核队列（NEEDS_HUMAN_REVIEW 项）

    if not RI.initialized(root):
        rep.add("RQG-00", "注册表初始化", "WARN", "Medium",
                "Research Integrity 注册表未初始化（旧项目兼容：不阻塞交付；"
                "建议按 references/research-integrity.md 建立 .aeromech/research/）")
        summary = {"gate": "not_initialized", "reason": "registries missing"}
        _save(rep, out_dir, None, summary)
        return summary, rep

    data = RI.load_all(root)
    texts = load_texts(root)
    val = RI.validate(root)
    cov = RI.coverage(root)

    rq = data.get("rq") or []
    methods = data.get("methods") or []
    evidence = data.get("evidence") or []
    datasets = data.get("datasets") or []
    analyses = data.get("analyses") or []
    calcs = data.get("computations") or []
    claims = data.get("claims") or []
    cons = data.get("conclusions") or []
    figs = data.get("figures") or []

    ev_by_id = {str(e.get("id")): e for e in evidence}
    ds_by_id = {str(d.get("id")): d for d in datasets}

    all_text = texts["all"]
    all_nz = nz(all_text)

    # ---- RQG-00 注册表结构校验（Critical/High → 阻止门禁）----
    if val.get("has_critical"):
        rep.add("RQG-00", "注册表结构校验", "FAIL", "Critical",
                f"{len(val['problems'])} 个问题（含 Critical）: "
                + "；".join(f"{p['code']}@{p['where']}" for p in val["problems"][:5]))
    elif val.get("has_high"):
        rep.add("RQG-00", "注册表结构校验", "FAIL", "High",
                f"{len(val['problems'])} 个问题: "
                + "；".join(f"{p['code']}@{p['where']}" for p in val["problems"][:5]))
    else:
        rep.add("RQG-00", "注册表结构校验", "PASS", "High",
                f"结构/引用完整（{sum(val['stats'].values())} 条记录）")

    # ---- RQG-01 研究问题明确 ----
    ok = bool(rq)
    details = []
    for r in rq:
        q, o = str(r.get("question", "")).strip(), str(r.get("objective", "")).strip()
        if len(q) < 8 or len(o) < 4:
            ok = False
            details.append(f"{r.get('id')} 问题/目标过短")
    rep.add("RQG-01", "研究问题明确", "PASS" if ok else "FAIL", "High",
            f"RQ 注册 {len(rq)} 条" + ("，字段完整" if ok else f"；问题: {details}"))

    # ---- RQG-02 目标与问题对应 ----
    bad2 = []
    for r in rq:
        inter = keywords_of(r.get("question")) & keywords_of(r.get("objective"))
        if not inter:
            bad2.append(str(r.get("id")))
    rep.add("RQG-02", "研究目标与研究问题对应", "PASS" if not bad2 else "FAIL", "High",
            "目标与问题文本关联（共享实词）" if not bad2 else f"无关联实词: {bad2}")

    # ---- RQG-03 方法能回答研究问题 ----
    method_names = {str(m.get("id")): str(m.get("name", "")) for m in methods}
    bad3, warn3 = [], []
    for r in rq:
        refs = r.get("related_methods") or []
        if not refs:
            bad3.append(str(r.get("id")) + " 无方法链接")
            continue
        for ref in refs:
            name = method_names.get(str(ref), "")
            if name and nz(name) not in all_nz:
                warn3.append(f"{ref}({name}) 未见于研究文本")
    status3 = "FAIL" if bad3 else ("WARN" if warn3 else "PASS")
    rep.add("RQG-03", "研究方法能够回答研究问题", status3, "High",
            "方法链接齐备且见于文本" if status3 == "PASS" else f"{bad3} {warn3}")

    # ---- RQG-04 方法选择依据 ----
    bad4, warn4 = [], []
    for m in methods:
        basis = str(m.get("basis", "")).strip()
        if len(basis) < 10:
            bad4.append(str(m.get("id")) + " basis 缺失")
    if not re.search(r"(选型|选择依据|选择说明|适配|方法选择|为什么.{0,6}选择|比较.{0,10}方法|方法对比)", all_text):
        warn4.append("研究文本未见方法选择论证表述")
    status4 = "FAIL" if bad4 else ("WARN" if warn4 else "PASS")
    rep.add("RQG-04", "研究方法有明确选择依据", status4, "High",
            f"方法 {len(methods)} 个，依据齐备" if status4 == "PASS" else f"{bad4} {warn4}")

    # ---- RQG-05 核心数据有来源 ----
    bad5 = []
    for d in datasets:
        if not str(d.get("source", "")).strip():
            bad5.append(str(d.get("id")) + " 无 source")
        elif d.get("type") not in ("simulated", "assumption") and not str(d.get("source_location", "")).strip():
            bad5.append(str(d.get("id")) + " 真实数据缺 source_location")
    rep.add("RQG-05", "核心数据有来源", "PASS" if not bad5 else "FAIL", "High",
            f"数据集 {len(datasets)} 个来源齐备" if not bad5 else f"{bad5}")

    # ---- RQG-06 模拟数据有明确标记 ----
    synth = [d for d in datasets if d.get("type") in ("simulated", "assumption")]
    bad6, warn6 = [], []
    for d in synth:
        label = str(d.get("label", ""))
        if RI.SYNTH_LABEL not in label:
            bad6.append(str(d.get("id")) + " label 缺失")
        elif nz(RI.SYNTH_LABEL) not in all_nz:
            warn6.append(str(d.get("id")) + " 标记未出现在文档文本（正文/表题/表注）")
    if bad6:
        status6, sev6 = "FAIL", "Critical"
    elif warn6:
        status6, sev6 = "FAIL", "High"
    else:
        status6, sev6 = "PASS", "High"
    rep.add("RQG-06", "模拟数据有明确标记", status6, sev6,
            f"模拟数据集 {len(synth)} 个，label 完整且见于文档" if status6 == "PASS"
            else f"{bad6} {warn6}")

    # ---- RQG-07 核心分析有数据/证据支撑 ----
    bad7 = [str(a.get("id")) for a in analyses if not (a.get("inputs") or [])]
    status7 = "PASS" if (analyses and not bad7) else ("FAIL" if bad7 else "WARN")
    rep.add("RQG-07", "核心分析有数据/证据支撑", status7, "High",
            f"分析 {len(analyses)} 个输入齐备" if status7 == "PASS"
            else (f"缺输入: {bad7}" if bad7 else "未注册分析"))

    # ---- RQG-08 核心结论可追溯到分析 ----
    bad8 = [str(c.get("id")) for c in cons if not (c.get("claims") or c.get("analyses"))]
    status8 = "PASS" if (cons and not bad8) else "FAIL"
    rep.add("RQG-08", "核心结论可以追溯到分析", status8, "High",
            f"结论 {len(cons)} 条链路齐备" if status8 == "PASS" else f"断链: {bad8 or '未注册结论'}")

    simulated_only = bool(datasets) and all(d.get("type") in ("simulated", "assumption") for d in datasets)

    # ---- RQG-09 摘要结论与正文结论一致 ----
    front = texts["front"] or all_text[:2000]
    body = texts["chapters"] + "\n" + texts["conclusion"] + "\n" + texts["plan"]
    issues9, hard9, sev9 = [], False, "High"
    # a) 摘要数值 ⊆ 正文数值
    fnums = numbers_of(front)
    bnums = numbers_of(body)
    extra = sorted(n for n in fnums if n not in bnums)
    if extra:
        issues9.append(f"摘要含正文未出现的数值: {extra[:6]}")
        hard9 = True
    # b) 摘要真实声称 × 数据身份（模拟数据不得写成真实实验）
    if simulated_only:
        real_hits = _claim_hits(front, REAL_CLAIM)
        if real_hits:
            issues9.append(f"摘要出现{real_hits}但全部数据为模拟（禁止把模拟写成真实）")
            sev9 = "Critical"
            hard9 = True
    # c) 结论关键词在摘要中的覆盖（软检查）
    if cons:
        cover_ok = 0
        for c in cons:
            kw = keywords_of(c.get("conclusion"))
            if kw and len(kw & keywords_of(front)) / len(kw) >= 0.4:
                cover_ok += 1
        if cover_ok < len(cons):
            issues9.append(f"结论条目在摘要中的关键词覆盖 {cover_ok}/{len(cons)}（<0.4）")
            if sev9 != "Critical" and not hard9:
                sev9 = "Medium"
    status9 = "FAIL" if hard9 else ("WARN" if issues9 else "PASS")
    if status9 == "PASS" and simulated_only:
        # v1.4.1：Critical 级语义检查（模拟身份是否被误写为真实）为启发式，无命中不得自动 PASS
        status9 = ST_NHR
        review_items.append({
            "item": "RQG-09:ABSTRACT", "check": "RQG-09",
            "claim": "（摘要↔正文一致性）",
            "claim_text": "摘要对模拟数据身份与结论的表述",
            "evidence": [f"{d.get('id')}({d.get('type')})" for d in datasets],
            "reason": "启发式（数值域/关键词覆盖/否定语境）未发现把模拟写成真实的模式命中；"
                      "但摘要与正文、结论的语义一致性无法由模式可靠判定",
            "uncertainty": "改写式表述（如“来自维修记录整理”）、隐含因果、强度放大可能绕过模式检测",
        })
    rep.add("RQG-09", "摘要结论与正文结论一致", status9, sev9,
            ("摘要数值域⊆正文；无身份越界措辞" if status9 == "PASS"
             else ("已通过自动启发式检查；模拟身份/结论一致性须人工复核（见 human-review-checklist.md）"
                   if status9 == ST_NHR else "；".join(issues9[:3]))))

    # ---- RQG-10 不存在超出证据范围的结论 ----
    def evidence_statuses_of(refs, analysis_ids):
        sts = []
        for r in refs:
            e = ev_by_id.get(str(r))
            if e:
                sts.append(str(e.get("verification_status")))
            elif str(r) in ds_by_id:
                dt = ds_by_id[str(r)].get("type")
                sts.append("simulated" if dt in ("simulated", "assumption") else "verified")
        for a in analysis_ids or []:
            an = next((x for x in analyses if str(x.get("id")) == str(a)), None) or {}
            for inp in an.get("inputs") or []:
                if isinstance(inp, dict) and str(inp.get("ref")) in ds_by_id:
                    dt = ds_by_id[str(inp["ref"])].get("type")
                    sts.append("simulated" if dt in ("simulated", "assumption") else "verified")
                elif isinstance(inp, dict) and str(inp.get("ref")) in ev_by_id:
                    sts.append(str(ev_by_id[str(inp["ref"])].get("verification_status")))
        return sts

    bad10, sev10 = [], "High"
    weak_targets = []   # v1.4.1：弱证据且无强断言命中 → 进人工复核队列
    for c in claims:
        sts = evidence_statuses_of(c.get("evidence_ids") or [], c.get("analysis_ids") or [])
        weak = bool(sts) and all(s in ("simulated", "pending") for s in sts)
        text = str(c.get("claim", ""))
        if weak:
            if _claim_hits(text, STRONG_PATTERNS_CRIT):
                bad10.append(f"{c.get('id')} 强断言×模拟/未核实证据（越界）: {text[:24]}")
                sev10 = "Critical"
            elif _claim_hits(text, STRONG_PATTERNS_HIGH):
                bad10.append(f"{c.get('id')} 强断言×弱证据: {text[:24]}")
            else:
                weak_targets.append(("claim", str(c.get("id")), text, sts,
                                     c.get("evidence_ids") or [], c.get("analysis_ids") or []))
    for c in cons:
        sts = evidence_statuses_of(c.get("evidence") or [], c.get("analyses") or [])
        text = str(c.get("conclusion", ""))
        weak = bool(sts) and all(s in ("simulated", "pending") for s in sts)
        if weak and _claim_hits(text, STRONG_PATTERNS_CRIT):
            bad10.append(f"{c.get('id')} 结论越界: {text[:24]}")
            sev10 = "Critical"
        elif weak:
            weak_targets.append(("conclusion", str(c.get("id")), text, sts,
                                 c.get("evidence") or [], c.get("analyses") or []))
    # 文本级：模拟数据场景下不得使用"实验口径"措辞
    if simulated_only:
        synth_hits = _claim_hits(all_text, SYNTH_STRONG)
        if synth_hits:
            bad10.append(f"正文出现{synth_hits}但数据为模拟")
            sev10 = "Critical"

    # 文本级（v1.6 test-8.0 补，P3 类缺口）：模拟口径场景下正文句子的强断言词。
    # 注册表级扫描只覆盖 claims/conclusions 字段，正文句子（如"本文证明了…"）
    # 原本不受检——正文才是读者读到的东西。命中不自动 FAIL（否定语序/合法引用
    # 模式无法靠词表区分），进人工复核队列；机器判不了不装懂，但也绝不静默。
    NEG_RE2 = re.compile(r"(不|非|未|无|没有|禁止|不能|无法)")

    def body_claim_hits(txt, words, win=16):
        hits = []
        for w in words:
            start = 0
            while True:
                i = (txt or "").find(w, start)
                if i < 0:
                    break
                pre = txt[max(0, i - win):i]
                post = txt[i + len(w):i + len(w) + win]
                if not (NEG_RE2.search(pre) or NEG_RE2.search(post)):
                    hits.append(w)
                    break
                start = i + len(w)
        return hits

    body_hits = []
    if simulated_only and (texts["chapters"].strip() or texts["conclusion"].strip()):
        body_text = texts["chapters"] + "\n" + texts["conclusion"]
        # 只扫 HIGH（强度词：证明/显著/普遍/必然）——CRIT 是数据身份词，在背景陈述、
        # 拒绝句式、RQ 描述中合法高频出现，正文级扫描误报率过高；身份声称风险由
        # 注册表级 claim 扫描 + SYNTH_STRONG 文本级扫描覆盖（v1.5 机制，不动）。
        for group, words in (("HIGH", STRONG_PATTERNS_HIGH),):
            h = body_claim_hits(body_text, words)
            if h:
                body_hits.append((group, h))
    if bad10:
        status10 = "FAIL"
        detail10 = "；".join(bad10[:4])
    elif weak_targets or body_hits:
        # 启发式未命中强断言模式，但存在弱证据支撑的核心论断/结论或正文强断言词：
        # 不得自动 PASS
        status10 = ST_NHR
        for kind, cid, text, sts, refs, alinks in weak_targets:
            review_items.append({
                "item": f"RQG-10:{cid}", "check": "RQG-10", "claim": cid,
                "claim_text": text[:80],
                "evidence": [f"{r}({s})" for r, s in zip(refs, sts)] or
                            [f"analysis:{a}" for a in alinks],
                "reason": f"该{'论断' if kind == 'claim' else '结论'}的证据全为 simulated/pending："
                          "启发式未命中强断言模式，但其表述强度是否超出证据能力须人工判定",
                "uncertainty": "强断言模式表覆盖有限（同义改写、隐含口径、放大表述可能漏检）",
            })
        for group, h in body_hits:
            review_items.append({
                "item": f"RQG-10:BODY-{group}", "check": "RQG-10",
                "claim": "（正文强断言词）", "claim_text": "、".join(h)[:80],
                "evidence": [f"{d.get('id')}({d.get('type')})" for d in datasets],
                "reason": "全部数据集为模拟口径，正文出现"
                          + ("强断言" if group == "HIGH" else "真实数据身份")
                          + f"词 {h}（否定窗内未排除）：表述强度是否超出证据能力须人工判定",
                "uncertainty": "窗口外否定/合法背景陈述可能命中；逐句人工核对语境",
            })
        dparts = []
        if weak_targets:
            dparts.append(f"{len(weak_targets)} 项弱证据论断/结论")
        if body_hits:
            dparts.append("正文强断言词待核（" + "；".join(
                f"{'×'.join(h)}" for _, h in body_hits) + "）")
        detail10 = "自动检查未见越界模式；" + "、".join(dparts) + \
                   "待人工复核（见 human-review-checklist.md）"
    else:
        status10 = "PASS"
        detail10 = "未发现证据越界表述；核心论断证据无全弱风险"
    rep.add("RQG-10", "不存在超出证据范围的结论", status10, sev10, detail10)

    # ---- RQG-11 图表参与论证 ----
    fig_entries = [f for f in figs if str(f.get("id", "")).startswith("FIG-")]
    table_entries = [f for f in figs if str(f.get("id", "")).startswith("TABLE-")]
    if not figs:
        status11, sev11, d11 = "WARN", "Medium", "figures.yaml 无注册（论文含图表时应注册论证链接）"
    else:
        orphans = [f.get("id") for f in figs
                   if not ((f.get("related_rqs") or []) + (f.get("related_analyses") or []) + (f.get("related_claims") or []))]
        ratio = len(orphans) / len(figs)
        if ratio == 0:
            status11, sev11, d11 = "PASS", "Medium", f"图表 {len(figs)} 个均具论证链接"
        elif ratio > 0.5:
            status11, sev11, d11 = "FAIL", "High", f"{len(orphans)}/{len(figs)} 图表无论证链接（装饰性过多）: {orphans[:5]}"
        else:
            status11, sev11, d11 = "WARN", "Medium", f"无链接图表: {orphans[:5]}"
    caps = _pdf_caption_stats(pdf)
    if caps and figs:
        note = []
        if caps["fig_captions"] > len(fig_entries):
            note.append(f"PDF 图题 {caps['fig_captions']} > 注册 FIG {len(fig_entries)}")
        if caps["table_captions"] > len(table_entries):
            note.append(f"PDF 表题 {caps['table_captions']} > 注册 TABLE {len(table_entries)}")
        if note:
            d11 += "；" + "；".join(note)
            if status11 == "PASS":
                status11, sev11 = "WARN", "Medium"
    rep.add("RQG-11", "图表参与论证（非孤立存在）", status11, sev11, d11)

    # ---- RQG-12 关键参考文献确实被正文使用 ----
    lit_refs, used, unused = [], 0, []
    for e in evidence:
        if e.get("source_type") != "literature":
            continue
        text = f"{e.get('source', '')} {e.get('source_location', '')}"
        m = re.findall(r"\[(\d+)\]", str(text))
        if not m:
            continue
        for num in m:
            lit_refs.append(num)
            if f"[{num}]" in nz(texts["chapters"]):
                used += 1
            else:
                unused.append(num)
    if not lit_refs:
        status12, sev12, d12 = "WARN", "Medium", "未注册可定位编号的文献证据（source 未含 [n]）"
    elif not unused:
        status12, sev12, d12 = "PASS", "High", f"注册文献证据 {used} 条均在正文被引用"
    elif used == 0:
        status12, sev12, d12 = "FAIL", "High", f"注册文献证据均未在正文引用: {sorted(set(unused))[:8]}"
    else:
        status12, sev12, d12 = "WARN", "Medium", f"部分注册文献未被引用: {sorted(set(unused))[:8]}"
    rep.add("RQG-12", "关键参考文献确实被正文使用", status12, sev12, d12)

    # ---- RQG-13 正文重要数字可追溯 ----
    calc_numbers = set()
    for c in calcs:
        calc_numbers |= numbers_of(str(c.get("output", "")))
    num_sentences, traceable = 0, 0
    untraced_examples = []
    for sent in re.split(r"[。；\n]", texts["chapters"] + "\n" + texts["conclusion"]):
        if re.match(r"^\s*#{0,6}\s*\d+(\.\d+)+\s", sent or ""):
            continue  # 小节标题（如 "3.1 系统组成"）不计
        s_nums = numbers_of(sent)
        if not s_nums:
            continue
        num_sentences += 1
        has_ref = bool(re.search(r"\[\d+\]", sent)) or ("【" in sent and "】" in sent)
        has_calc = any(n in calc_numbers for n in s_nums)
        has_calc_marker = bool(re.search(r"(计算|CALC|式\s*[（(]|\d+-\d+[）)])", sent))
        if has_ref or has_calc or has_calc_marker:
            traceable += 1
        elif len(untraced_examples) < 5:
            untraced_examples.append(sent.strip()[:28])
    r13 = traceable / num_sentences if num_sentences else 1.0
    status13 = "PASS" if r13 >= 0.5 else "WARN"
    rep.add("RQG-13", "正文重要数字可追溯", status13, "Medium",
            f"含数字句 {num_sentences}，可追溯 {traceable}（{r13*100:.0f}%，>=50%）"
            + ("" if status13 == "PASS" else f"；示例: {untraced_examples}"))

    # ---- RQG-14 计算结果可追溯到输入 ----
    bad14 = []
    for c in calcs:
        ins = c.get("inputs") or []
        kinds = {i.get("kind") for i in ins if isinstance(i, dict)}
        # B8：computation 与 calculation 为文档同义词（research-integrity.md §7/§8 kind ∈
        # evidence|dataset|computation|reasoning，示例亦见 calculation 写法），两者等价计入
        # 数据来源；不构成降标——仍要求至少一个指向注册数据/证据/计算的输入。
        if not ins:
            bad14.append(str(c.get("id")) + " 无输入")
        elif not (kinds & {"dataset", "evidence", "calculation", "computation"}):
            bad14.append(str(c.get("id")) + " 输入无数据/证据来源")
        if not str(c.get("formula", "")).strip():
            bad14.append(str(c.get("id")) + " 缺公式")
        if not str(c.get("verification", "")).strip():
            bad14.append(str(c.get("id")) + " 缺验证方式")
    status14 = "PASS" if (calcs and not bad14) else ("FAIL" if bad14 else "WARN")
    rep.add("RQG-14", "计算结果可以追溯到输入", status14, "High",
            f"计算 {len(calcs)} 个输入/公式/验证齐备" if status14 == "PASS"
            else (f"{bad14[:5]}" if bad14 else "未注册计算"))

    # ---- RQG-15 研究限制与证据能力匹配 ----
    lim_hit = re.search(r"(局限|限制|不足之处|研究局限)", all_text)
    bad15 = []
    if not lim_hit:
        bad15.append("文本未见研究限制论述")
    if simulated_only and lim_hit:
        win = all_text[max(0, lim_hit.start() - 200): lim_hit.start() + 400]
        if not re.search(r"(模拟|演示|不代表|构造)", win):
            bad15.append("模拟数据未在限制论述中声明")
    status15 = "PASS" if not bad15 else ("FAIL" if "未见研究限制" in bad15[0] else "WARN")
    rep.add("RQG-15", "研究限制与证据能力匹配", status15, "Medium" if not bad15 else "High",
            "限制论述存在且与证据身份匹配" if not bad15 else "；".join(bad15))

    # ---- 人工复核队列（v1.4.1）：消费 human-review.yaml 裁决；未裁决项 → NEEDS_HUMAN_REVIEW ----
    reviews, review_err = _load_reviews(root)
    if review_err:
        rep.add("RQG-HR", "人工复核记录", "WARN", "Medium",
                f"{review_err}；remediation: 修复 .aeromech/research/human-review.yaml 后重跑")
    resolved, violations, unresolved = [], [], []
    queue_keys = {it["item"] for it in review_items}
    for it in review_items:
        r = reviews.get(it["item"])
        if not r:
            unresolved.append(it)
            continue
        d = str(r.get("decision", "")).strip().lower()
        if d in ("ok", "confirmed_ok", "supported", "通过", "无越界"):
            it["decision"] = d
            resolved.append(it["item"])
        elif d in ("violation", "overreach", "越界", "fail", "不成立"):
            it["decision"] = d
            violations.append((it["item"], r))
        else:
            unresolved.append(it)
            rep.add("RQG-HR-WARN", f"复核记录告警：{it['item']}", "WARN", "Low",
                    f"未知 decision={r.get('decision')!r}（允许: ok|violation）；视为未裁决")
    for key in reviews:
        if key not in queue_keys:
            rep.add("RQG-HR-WARN", f"复核记录告警：{key}", "WARN", "Low",
                    "复核记录未匹配当前队列项（可能已修复或键名错误）")
    for item, r in violations:
        rep.add("RQG-HR", f"人工复核裁定：{item}", "FAIL", "Critical",
                f"复核判定为越界/不成立（reviewer={r.get('reviewer', '?')}）：{str(r.get('note', ''))[:60]}；"
                "remediation: 按复核结论下调表述强度或补充证据，修改后重跑 RQG")
    if review_items:
        if unresolved:
            rep.add("RQG-HR", "人工复核队列", ST_NHR, "High",
                    f"{len(unresolved)} 项待人工复核：{[it['item'] for it in unresolved]}；"
                    "清单见 human-review-checklist.md（按 references/research-human-review.md 执行）")
        else:
            rep.add("RQG-HR", "人工复核队列", "PASS", "High",
                    f"队列 {len(review_items)} 项均已裁决（resolved={len(resolved)}, violations={len(violations)}）")

    # ---- 汇总 ----
    hard = rep.hard_fails
    if hard:
        gate = "FAIL"
    elif unresolved:
        gate = "PASS_WITH_HUMAN_REVIEW"
    else:
        gate = "PASS"
    checklist_path = None
    if review_items:
        checklist_path = _write_checklist(out_dir, review_items, unresolved)
    summary = {
        "gate": gate,
        "rq_count": len(rq), "evidence_count": len(evidence), "claims": len(claims),
        "conclusions": len(cons), "datasets": len(datasets),
        "coverage": cov,
        "registry_validation": {"ok": val["ok"], "problems": len(val["problems"]),
                                "critical": val.get("has_critical", False),
                                "high": val.get("has_high", False)},
        "needs_human_review": [it["item"] for it in unresolved],
        "review_resolved": resolved,
        "review_violations": [k for k, _ in violations],
        "human_review_checklist": checklist_path,
        "fails": [(f["code"], f["severity"], f["detail"][:80]) for f in rep.fails],
    }
    _save(rep, out_dir, cov, summary)
    return summary, rep


def _load_reviews(root):
    """读取 .aeromech/research/human-review.yaml（人工复核裁决）。返回 (reviews, error)。"""
    p = os.path.join(RI.research_dir(root), "human-review.yaml")
    if not os.path.isfile(p):
        return {}, None
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {}, f"human-review.yaml 解析失败: {e}"
    out = {}
    for r in (data.get("reviews") or []):
        if isinstance(r, dict) and r.get("item"):
            out[str(r["item"])] = r
    return out, None


def _write_checklist(out_dir, review_items, unresolved):
    """生成人工复核清单（供逐项裁决；结果回填 human-review.yaml）。"""
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "human-review-checklist.md")
    lines = [
        "# 人工复核清单（Human Review Checklist）",
        "",
        "> 本清单由 research_quality_qa.py 自动生成（v1.4.1）。以下项目为**启发式自动检查无法可靠判定**",
        "> 的 Critical 级研究语义问题：自动检查**不得**判定为 PASS，须按 `references/research-human-review.md`",
        "> 逐项人工复核。复核结论写入 `.aeromech/research/human-review.yaml` 后重跑 RQG。",
        "",
        "## 复核要点（详见 references/research-human-review.md）",
        "1. 核心结论是否真的被证据支持；2. 工程判断是否超过数据能力；3. 模拟数据是否被误写成真实数据；",
        "4. 研究方法是否真的能够回答研究问题；5. 摘要是否准确反映研究结论；6. 关键数字是否可信；",
        "7. 文献是否真正支持对应论断。",
        "",
        "## 待复核队列",
        "",
    ]
    for n, it in enumerate(review_items, 1):
        mark = "（已裁决）" if it.get("decision") and it.get("decision") in ("ok", "confirmed_ok", "supported", "通过", "无越界") else ""
        lines.append(f"### HR-{n:03d} {it['item']} {mark}")
        lines.append(f"- check（检查项）: {it['check']}")
        lines.append(f"- claim（对象）: {it['claim']}")
        lines.append(f"- claim_text（文本）: {it['claim_text']}")
        lines.append(f"- evidence（证据）: {', '.join(it['evidence']) if it['evidence'] else '（无直接证据引用）'}")
        lines.append(f"- reason（风险原因）: {it['reason']}")
        lines.append(f"- uncertainty（不确定性）: {it['uncertainty']}")
        lines.append("- 裁决: [ ] 无越界（ok）  [ ] 越界/不成立（violation）　复核人：________　日期：________")
        lines.append(f"  备注/依据: ____________________________________________________")
        lines.append("")
    lines.append("## 记录方式（写入 .aeromech/research/human-review.yaml）")
    lines.append("")
    lines.append("```yaml")
    lines.append("reviews:")
    for it in review_items[:3]:
        lines.append(f"- item: {it['item']}")
        lines.append("  decision: ok   # ok（无越界）| violation（越界/不成立，将触发 Critical FAIL）")
        lines.append("  reviewer: <复核人>")
        lines.append("  date: <YYYY-MM-DD>")
        lines.append("  note: <判定依据>")
    if len(review_items) > 3:
        lines.append("# …（其余条目同格式）")
    lines.append("```")
    lines.append("")
    lines.append(f"**当前状态：{'仍有 ' + str(len(unresolved)) + ' 项待裁决' if unresolved else '全部已裁决'}**")
    open(p, "w", encoding="utf-8").write("\n".join(lines))
    return p


def run(root, out_dir=None, pdf=None, verbose=True):
    """执行 RQG-01~15；返回 (summary, Report)。内部异常绝不产生 PASS（gate=ERROR，退出码 3）。"""
    try:
        return _run_impl(root, out_dir=out_dir, pdf=pdf, verbose=verbose)
    except Exception as e:
        import traceback
        traceback.print_exc()
        out_dir = out_dir or os.path.join(root, ".aeromech", "artifacts", "qa")
        rep = Report(out_dir)
        rep.add("RQG-ERR", "执行异常", "FAIL", "Critical",
                f"内部异常 {type(e).__name__}: {e}；未产生 PASS 结论；"
                "remediation: 修复后重跑（检查注册表/章节文件完整性）")
        summary = {"gate": "ERROR", "reason": f"{type(e).__name__}: {e}",
                   "needs_human_review": [], "fails": [("RQG-ERR", "Critical", str(e)[:80])]}
        _save(rep, out_dir, None, summary)
        return summary, rep


def _save(rep, out_dir, cov, summary):
    os.makedirs(out_dir, exist_ok=True)
    md = os.path.join(out_dir, "research-quality-report.md")
    lines = ["# Research Quality Gate 报告（RQG-01~15）", ""]
    for i in rep.items:
        line = f"- {i['code']} {i['name']}: {i['status']} [{i['severity']}] | {i['detail']}"
        if i["status"] == "FAIL":
            rem = RQG_REMEDIATION.get(i["code"],
                                      "按 references/research-integrity.md 与人工复核清单修复后重跑")
            line += f" | remediation: {rem}"
        lines.append(line)
    if cov:
        lines.append("")
        lines.append(f"- Evidence Coverage Ratio: {cov['evidence_coverage_ratio']} "
                     f"({cov['claims_covered']}/{cov['claims_need_evidence']})；证据状态分布 {cov['evidence_by_status']}")
    if summary is not None:
        nhr = summary.get("needs_human_review") or []
        if nhr:
            lines.append("")
            lines.append(f"- 待人工复核（NEEDS_HUMAN_REVIEW）: {nhr}")
        if summary.get("human_review_checklist"):
            lines.append(f"- 人工复核清单: {summary['human_review_checklist']}")
    hard = rep.hard_fails
    gate = (summary or {}).get("gate", "FAIL" if hard else "PASS")
    lines.append("")
    lines.append(f"**RI Gate: {gate}**"
                 + (f"（Critical/High: {[(f['code'], f['severity']) for f in hard]}）" if hard else "")
                 + ("（存在待人工复核项：交付前须完成复核并回填 human-review.yaml）"
                    if gate == "PASS_WITH_HUMAN_REVIEW" else ""))
    open(md, "w", encoding="utf-8").write("\n".join(lines))
    if summary is not None:
        with open(os.path.join(out_dir, "research-quality.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)
    print("report:", md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    summary, rep = run(args.project, out_dir=args.out, pdf=args.pdf)
    gate = summary["gate"]
    if gate == "not_initialized":
        return 2
    if gate == "ERROR":
        return 3
    return 0 if gate in ("PASS", "PASS_WITH_HUMAN_REVIEW") else 1


if __name__ == "__main__":
    sys.exit(main())
