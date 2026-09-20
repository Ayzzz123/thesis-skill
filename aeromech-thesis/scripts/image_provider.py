# -*- coding: utf-8 -*-
"""image_provider.py — v1.6.5 Phase 2A：Provider Resolution + Fallback Contract

范围（§一）：只做"解析与路由契约"，**不实现真实 OpenAI/Gemini HTTP 调用**（Phase 2B）。
本模块不发起任何网络请求。

Fallback 硬规则（§二/§七/§十/§十四）：
  A. external provider unavailable（未配置/无后端）——不是错误：
        external_image_provider = unavailable
        fallback_to_existing_figure_pipeline = true     ← 继续走**原有** Figure Pipeline
  B. 原有 pipeline 的实际所指（§三，以代码行为为准，不凭文档猜）：
     当前 aeromech-thesis 代码中真实存在的生成路径 = figure_iface LocalProvider
     （kind=mermaid → render_mmdc；kind=script → figkit/matplotlib 受控执行）
     + 人工/协作者 provider（NEEDS_HUMAN_REVIEW 分支）。
     **Host-native 在现有代码中不存在**（grep 证实）——本模块预留枚举位但不虚构其行为；
     旧系统默认行为零改变：spec 不带 provider 字段时路由结果恒为 local。
  C. 确定性研究图（§十一）：fault_tree/stat_*/flow/matrix/architecture/…
     永远优先 local（数据/逻辑完整性），即使 external 已配置。
  D. 已配置 external 但 Phase 2A 尚无真实 backend：route() 返回
     external_configured=True, external_implemented=False → 调用方按"回落既有管线 +
     reason 记录"处理；**不 fake 生成、不 BLOCK**（Phase 2B 接入真实调用后此分支消失）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_config as IC

# 确定性研究图类型（figure_style.FIGURE_TYPES 的数据/逻辑子集）——永远 local 优先
DETERMINISTIC_TYPES = {
    "fault_tree", "flow", "tech_route", "stat_bar", "stat_line",
    "decision_matrix", "architecture", "comparison", "framework",
}
# AI 适用类型（概念/视觉解释；Phase 2B 起在已配置时走 external）
EXTERNAL_ELIGIBLE_TYPES = {"conceptual_illustration", "visual_explanatory",
                           "apparatus_sketch", "photo_like"}

EXTERNAL_NOT_IMPLEMENTED = "external_backend_not_implemented(phase2b)"


def route(spec, required=None):
    """Figure Plan → 生成路由决策（纯函数，不落盘、不生成）。
    spec 关键字段：provider（缺省 None=local，旧行为）、type、
    provider_required=="external"（严格模式，唯一可 BLOCK 到 NHR 的入口）。
    返回 dict：
      provider        : "local" | "external_image"
      external_state  : image_config Result.state
      fallback_from   : 回落原因（None=未回落）
      needs_configuration : True 时调用方记 NEEDS_HUMAN_REVIEW(NEEDS_CONFIGURATION)
      existing_pipeline_available : 恒 True（LocalProvider 在代码中始终存在）——
                                    任何外部状态都不关闭既有管线
    """
    spec = spec or {}
    want = (spec.get("provider") or "local").strip().lower()
    ftype = (spec.get("type") or "").strip().lower()
    required = (required if required is not None
                else str(spec.get("provider_required") or "").lower() == "external")
    base = {"external_state": IC.STATE_UNAVAILABLE, "fallback_from": None,
            "needs_configuration": False,
            "existing_pipeline_available": True, "reason": ""}

    # 旧默认路径：spec 不带 provider（或显式 local）→ 与 v1.6.0 行为逐字节一致
    if want in ("", "local"):
        return {**base, "provider": "local"}

    if want not in ("external_image", "image", "external"):
        # 未知 provider 名：不猜、不 BLOCK 既有管线——回落 local + 记录原因
        return {**base, "provider": "local",
                "fallback_from": f"unknown_provider:{want}",
                "reason": f"未知 provider {want!r}，回落既有管线"}

    # 确定性研究图：即使 external 可用也 local 优先（§十一/AC-IMG-09）
    r = IC.resolve(required=required)
    if ftype in DETERMINISTIC_TYPES:
        return {**base, "provider": "local",
                "external_state": r.state,
                "fallback_from": "deterministic_type_local_first",
                "reason": f"type={ftype} 属确定性研究图，local 优先（数据/逻辑完整性）"}

    if r.state == IC.STATE_UNAVAILABLE:
        if r.needs_configuration:      # 显式 mandatory + 无凭据 → 唯一配置错误态
            return {**base, "provider": None, "external_state": r.state,
                    "needs_configuration": True,
                    "reason": "NEEDS_CONFIGURATION: " + r.reason}
        return {**base, "provider": "local", "external_state": r.state,
                "fallback_from": "external_unavailable",
                "reason": "未配置外部 Image API（正常状态）→ 沿用既有 Figure Pipeline"}
    if r.state in (IC.STATE_INVALID, IC.STATE_FAILED):
        if required:
            return {**base, "provider": None, "external_state": r.state,
                    "needs_configuration": True, "reason": r.reason}
        return {**base, "provider": "local", "external_state": r.state,
                "fallback_from": f"external_{r.state.lower()}",
                "reason": "外部配置异常（" + IC.redact_text(r.reason)[:80] +
                          "）→ 回落既有管线，不阻塞交付"}
    # AVAILABLE：Phase 2A 尚无真实 backend——不 fake、不 BLOCK，回落既有管线并记录
    return {**base, "provider": "local", "external_state": r.state,
            "external_configured": True, "external_backend": r.backend,
            "fallback_from": EXTERNAL_NOT_IMPLEMENTED,
            "reason": "external 已配置（backend=%s）；Phase 2A 未接入真实调用，"
                      "回落既有管线（Phase 2B 启用）" % r.backend}


def describe(res):
    """路由决策的公开摘要（可安全入日志：无凭据面）。"""
    return {k: res.get(k) for k in ("provider", "external_state", "fallback_from",
                                    "needs_configuration", "existing_pipeline_available",
                                    "reason")}
