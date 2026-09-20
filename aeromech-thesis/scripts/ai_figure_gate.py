# -*- coding: utf-8 -*-
"""ai_figure_gate.py — v1.6.5：受控 AI 生图闸（任务 §五/§六/§七；设计 10 文档）

"AI Image Model 是受控的 visual generation provider，不是自由内容生成器。"

两道闸（顺序执行，任一不过 → 零 HTTP 调用）：
  1. plan_gate(spec)      —— Figure Plan 九字段齐备才放行；缺 → FIGURE_PLAN_REQUIRED
  2. assemble_prompt(...) —— prompt 只能由 Plan + 登记素材摘要 + 学术视觉规范组装；
                             拒绝任意自由文本（§六：禁止"请生成一个很专业的…"式直传）

provenance（§七）：build_provenance() 产出 10 字段登记（provider/model/timestamp/
prompt_hash/artifact_hash/source_material_refs/purpose/figure_type/…）；
白名单硬编码——api_key/authorization/token 等字段名一律拒收（丢弃+告警）。
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figure_style as ST
from image_config import redact_text

# Figure Plan 必备九字段（任务 §五；设计文档别名为 required_labels/forbidden_content）
PLAN_FIELDS = ("figure_id", "figure_type", "purpose", "intended_section",
               "semantic_content", "source_material", "research_link",
               "required_visual_elements", "forbidden_elements")
PLAN_ALIASES = {"required_labels": "required_visual_elements",
                "forbidden_content": "forbidden_elements"}

# 确定性研究图类型（§四：永不交给 AI；与 image_provider.DETERMINISTIC_TYPES 同源）
DETERMINISTIC_TYPES = {"fault_tree", "stat_bar", "stat_line", "research_result",
                       "calculation_plot", "flow", "tech_route", "decision_matrix",
                       "architecture", "comparison", "framework", "fmea_rpn"}
# AI 适用类型（§四：明确适合 image model 的视觉资产）
EXTERNAL_ELIGIBLE_TYPES = {"conceptual_illustration", "visual_explanatory",
                           "apparatus_sketch", "photo_like", "cover_artwork"}

PROVENANCE_WHITELIST = ("figure_id", "generation_method", "provider", "model",
                        "timestamp", "prompt_hash", "artifact_hash",
                        "source_material_refs", "purpose", "figure_type",
                        "attempts", "backend")
SECRETISH = ("key", "token", "authorization", "secret", "credential", "bearer")


class PlanError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = redact_text(str(message))[:200]
        super().__init__(f"{self.code}: {self.message}")


def normalize_plan(spec):
    """别名归一 + 空值剔除（返回新 dict，不改原 spec）。
    兼容 figures.yaml 既有字段：type→figure_type、related_*→research_link、
    data_source→source_material。"""
    plan = dict(spec or {})
    for alias, canon in PLAN_ALIASES.items():
        if alias in plan and canon not in plan:
            plan[canon] = plan[alias]
    if not plan.get("figure_type") and plan.get("type"):
        plan["figure_type"] = plan["type"]
    if not plan.get("research_link"):
        links = {k: plan.get(k) for k in ("related_rqs", "related_analyses",
                                          "related_claims") if plan.get(k)}
        if links:
            plan["research_link"] = links
    if not plan.get("source_material") and plan.get("data_source"):
        plan["source_material"] = plan["data_source"]
    return plan


def plan_gate(spec):
    """第一道闸。返回 (ok, plan_or_error_dict)。
    - 类型守卫：确定性研究图 → DETERMINISTIC_TYPE_LOCAL_ONLY（§四，禁 AI 接管）
    - 非 AI 适用类型 → TYPE_NOT_ELIGIBLE（保守：未知类型不默认放行外部）
    - 九字段任一缺失/空 → FIGURE_PLAN_REQUIRED（§五：ZERO HTTP）
    """
    plan = normalize_plan(spec)
    ftype = str(plan.get("figure_type") or plan.get("type") or "").strip().lower()
    if not ftype:
        return False, {"code": "FIGURE_PLAN_REQUIRED",
                       "missing": ["figure_type"],
                       "message": "Figure Plan 缺 figure_type（外部生图必须先声明类型）"}
    if ftype in DETERMINISTIC_TYPES:
        return False, {"code": "DETERMINISTIC_TYPE_LOCAL_ONLY",
                       "message": f"type={ftype} 属确定性研究图，必须 Local Provider"
                                  f"（数据/逻辑完整性，§四）"}
    if ftype not in EXTERNAL_ELIGIBLE_TYPES:
        return False, {"code": "TYPE_NOT_ELIGIBLE",
                       "message": f"type={ftype} 不在 AI 适用白名单 {sorted(EXTERNAL_ELIGIBLE_TYPES)}"}
    plan["figure_type"] = ftype
    missing = [f for f in PLAN_FIELDS if not plan.get(f)]
    if missing:
        return False, {"code": "FIGURE_PLAN_REQUIRED", "missing": missing,
                       "message": "Figure Plan 九字段不完整（无 Plan 禁外部调用，§五）"}
    return True, plan


def assemble_prompt(plan, material_summaries=None):
    """第二道闸：结构化 prompt。每个槽位必须来自 Plan/登记素材/学术视觉规范；
    不接受 plan 之外的自由描述直传（material_summaries 只接受 {id: 一句话摘要}，
    摘要来自注册表/素材登记，不来自用户临时长文本）。
    返回 (prompt, prompt_hash)。"""
    ok, res = plan_gate(plan)
    if not ok:
        raise PlanError(res["code"], res["message"])
    plan = res
    ms = material_summaries or {}
    refs = plan.get("source_material") or []
    src_lines = []
    for r in refs:
        rid = str(r)
        src_lines.append(f"- {rid}: {ms.get(rid, '(registered material, summary on file)')}")
    pal = ST.COLOR_PALETTE
    style = (f"academic minimal; clean vector-like technical drawing; white background "
             f"({pal['bg']}); restrained low-saturation palette (primary {pal['primary']}, "
             f"secondary {pal['secondary']}, fill {pal['fill']}, text {pal['text']}); "
             f"no gradients, no shadows, no 3D, no decorative elements, no photorealism; "
             f"labels in Chinese + English where given")
    parts = [
        "SYSTEM: academic technical figure for an engineering thesis (visual asset only, "
        "not measured data).",
        "PURPOSE: " + str(plan["purpose"]).strip(),
        "INTENDED_SECTION: " + str(plan["intended_section"]).strip(),
        "SEMANTIC_CONTENT: " + str(plan["semantic_content"]).strip(),
        "SOURCE (registered research materials; do NOT invent beyond these):",
        *src_lines,
        "MUST_SHOW: " + "; ".join(str(x) for x in plan["required_visual_elements"]),
        "MUST_NOT_SHOW: " + "; ".join(str(x) for x in plan["forbidden_elements"]) +
        "; any numbers, device models, standards clauses or measurements not listed above",
        "STYLE: " + style,
    ]
    prompt = "\n".join(parts)
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return prompt, "sha256:" + h[:16]


def build_provenance(plan, provider, model, prompt_hash, artifact_hash, timestamp,
                     attempts=1, generation_method="ai_image_model", extra=None):
    """§七 provenance 登记：白名单字段；疑似凭据字段名直接拒收（不入库）。
    返回 (provenance_dict, rejected_keys)。"""
    src = {"figure_id": plan.get("figure_id"), "generation_method": generation_method,
           "provider": provider, "model": model, "timestamp": timestamp,
           "prompt_hash": prompt_hash, "artifact_hash": artifact_hash,
           "source_material_refs": plan.get("source_material") or [],
           "purpose": plan.get("purpose"), "figure_type": plan.get("figure_type"),
           "attempts": attempts}
    for k, v in (extra or {}).items():
        src[k] = v
    prov, rejected = {}, []
    for k, v in src.items():
        if k not in PROVENANCE_WHITELIST:
            rejected.append(k)
            continue
        if any(s in str(k).lower() for s in SECRETISH):
            rejected.append(k)
            continue
        prov[k] = v
    return prov, rejected
