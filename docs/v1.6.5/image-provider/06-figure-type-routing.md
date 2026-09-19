# FIGURE_TYPE_ROUTING（06）

## 1. 路由总表（§十六；默认永远保守——确定性优先）

| 图类型（figure_style.FIGURE_TYPES） | 默认 provider | 理由 |
|---|---|---|
| fault_tree | **local**（figkit） | 逻辑必须 100% 可核（DATA/VIS-11），AI 图会画错门/线 |
| flow / tech_route | **local** | 同上，文字精确性 |
| stat_bar / stat_line | **local** | 数据完整性红线（§九：不许为美观改数据） |
| decision_matrix / architecture / comparison / framework | **local** | 结构图=逻辑图 |
| conceptual_illustration（概念示意） | **image**（可选 host_native） | 非数据、非逻辑，视觉表达价值高 |
| photo_like / apparatus_sketch（装置示意/外观） | **image** 或 **user_asset** | 实物外观类 |
| 用户已有图片 | **user_asset** | 一等公民（04 文档 §7） |

**规则**：`provider` 字段缺省=local；AI 只用于"不承载数据/逻辑/结论"的视觉型图。
承载研究内容的图走 AI = 路由违规（VIS-13 检查：type∈数据/逻辑类 且
generation_method=ai_image → FAIL critical，"AI 图不得充当证据图"）。

## 2. 决策点与覆盖

- 规划期（S8，Figure Agent）：按上表给 figures.yaml 条目写 `provider` + `type`；
- 用户显式覆盖：contract/figures.yaml `provider: image`（人工决定，Agent 不推翻）；
- 严格模式 `provider_required: external`（**默认不设**）：只有此模式下缺 Key 才
  NEEDS_CONFIGURATION；默认模式缺 Key→自动回落 local（§十四"不阻塞"）；
- build/generate 期零决策（只读 spec）——路由错误在 plan 期暴露，最便宜。

## 3. 与 v1.6.5 视觉系统的闭环

AI 图同样过：研究链接硬关卡（无 RQ/AN/CL 不得 validate 过）→ VIS-02/09/10
（密度/禁项/PDF 渲染）→ VIS-13 新检查（类型-方法一致性 + 题注【AI 生成示意图】标签）
→ gate figure_visual 域。**AI 不降低任何视觉质量门槛，只改变生成方式。**

## 4. 成本护栏（与 05 文档 §4 呼应）

路由表即第一道成本闸：绝大多数论文 80%+ 的图走 local=零 API 费；
概念示意图通常 ≤2 张/篇 → 典型外部调用量个位数。

## 5. 受控生成硬约束（v1.6.5 正式措辞，细则见 10 文档）

- "AI Image Model 是**受控的 visual generation provider，不是自由内容生成器**。"
- "论文中的 AI-generated visual 必须经过 **Figure Plan、研究边界、语义 QA、
  视觉 QA 和 PDF QA**，才能进入最终交付物。"
- "**能够通过确定性方法准确生成的研究图，不应使用 AI Image Model 替代。**"
- 外部未配置 → 回落既有管线，任何 provider 的缺席不阻塞 Figure Pipeline。
