# CONTROLLED_AI_FIGURE_GENERATION（10）— 受控的论文图形生成

正式硬约束（v1.6.5 文档级承诺，§十三 补充要求逐字落入）：

> 1. **AI Image Model 是受控的 visual generation provider，不是自由内容生成器。**
> 2. **论文中的 AI-generated visual 必须经过 Figure Plan、研究边界、语义 QA、
>    视觉 QA 和 PDF QA，才能进入最终交付物。**
> 3. **能够通过确定性方法准确生成的研究图，不应使用 AI Image Model 替代。**

## 1. Figure Plan 前置（§一：没有 Plan 就没有生成）

外部调用前，`ai_figure_gate.py` 强制校验 spec 携带完整 Figure Plan（九字段），
**任一缺失 → 拒绝调用外部 API**（返回 `PLAN_INCOMPLETE`，生命周期 NHR，
绝不"先画了再补材料"）：

```yaml
figure_plan:
  figure_id: FIG-007
  figure_type: conceptual_illustration      # 只允许 06 文档路由表中的 AI 适用类型
  purpose: 解释液压动力供应系统功能分层       # 论文中承担的功能（§二）
  intended_section: "2.1"
  semantic_content: 四层功能结构+能量流向     # 必须表达什么
  source_material: [E-008, scope:SCOPE-001]  # 视觉元素的研究来源（§四）
  research_link: {rqs: [RQ-01], analyses: [AN-001]}   # 复用既有硬关卡
  expected_visual_structure: layered-block-diagram
  required_labels: [泵源层, 蓄压层, 传输层, 用压层]
  forbidden_content: [具体机型型号, 任何数值, 真实设备照片风格]   # §三/§七
```

## 2. 结构化 prompt（§四：禁止开放式）

prompt 由 gate 从 Plan + Research Context + 注册表 + 用户素材**组装**，
不接受自由文本直传：

```
SYSTEM: academic technical figure for engineering thesis
PURPOSE: <plan.purpose>
SOURCE: <plan.source_material 的登记摘要（哈希锚定，非全文）>
MUST_SHOW: <plan.expected_visual_structure + required_labels>
MUST_NOT_INVENT: <forbidden_content> + 一切数值/型号/参数/标准条款
STYLE: academic minimal; natural restrained low-saturation palette;
       white background; clean vector-like technical drawing;
       consistent with figure_style.PALETTE/TYPOGRAPHY（02 视觉系统）
```
- prompt_hash（sha256）入 provenance；组装逻辑确定性 → 同 Plan 同 prompt（可复现审计）。
- 完全开放式请求（无 Plan 字段支撑的句子）在组装层直接拒绝——"请生成一个很专业的
  飞机液压系统图"这类 prompt **构造不出来**，因为每个槽位都要求来源。

## 3. 生成后语义 QA（§五：幻觉九检，Critical→BLOCK）

`SEMANTIC_QA`（在 Data/Visual QA 之前执行，图先要"对"再谈"好看"）：

| 检 | 内容 | 判定 |
|---|---|---|
| SEM-1 | 出现 Plan 未定义的关键工程对象（图中文字标签/组件 vs required_labels+semantic_content 白名单） | 机检标签层（OCR/VLM 辅助）→ 命中→BLOCK 候选，NHR 复核 |
| SEM-2 | 虚构型号（正则+型号词表：A320/B737/YPXX…出现在非授权标签） | **BLOCK** |
| SEM-3 | 虚构数据（图中出现数值标注而 Plan 无 data_source） | **BLOCK** |
| SEM-4 | 虚构参数（压力/温度/尺寸数字同上） | **BLOCK** |
| SEM-5 | 无法追溯的工程关系（箭头连接的对象对不在 source_material 关系集内） | NHR |
| SEM-6 | 错误箭头关系（与逻辑注册表矛盾，如 AND 画成 OR 语义） | **BLOCK** |
| SEM-7 | 研究范围外内容（scope.excluded 词命中） | NHR |
| SEM-8 | 示意图画成真实设备照片风格（photorealistic 标志/照片纹理检测） | **BLOCK**（§六：不得貌似真实） |
| SEM-9 | 易误解为真实测量的视觉元素（刻度尺/仪表读数/误差棒出现在概念图） | **BLOCK** |

- 机检手段分层：标签/文字用 OCR（PaddleOCR/tesseract 可选依赖，缺失→NHR 不假过）；
  风格类（SEM-8/9）用启发式+VLM 辅助，**任何不确定→NHR，绝不强制 PASS**（§十二）。
- BLOCK 的图：不落交付目录、不进 DOCX/PDF；lifecycle=REJECTED + hallucination 码。

## 4. 示意性标识（§六/§七）

- AI 生成图题注默认含【示意图】/【概念示意】/【基于本文功能抽象】之一
  （按 Plan.purpose 选择）；`AI-assisted generated visual` 字样是否出现
  **由论文规范与用户决定**（contract `image_label_style: mandatory|optional|custom`）。
- 删除标识的权力在人不在 Agent：任何自动流程不得移除示意性标注（VIS-13 联动：
  题注与 provider_meta.generation_method 一致性机检）。
- 工程主题（aircraft/engine/hydraulic/flight control/landing gear/maintenance/
  mechanical structure，§七）：无证据来源的结构细节一律 `Functional abstraction`
  或 `Conceptual schematic` 口径；"这是某真实型号的准确结构"= 违规措辞（SEM 检）。

## 5. 评价顺序（§十：漂亮排最后）

```
Semantic correctness → Research boundary → Data integrity
→ Visual readability → Academic style → Aesthetic quality
```
实现为 QA 链执行顺序：SEMANTIC_QA →（RQG-16 边界）→ DATA_QA → GEOMETRY/VISUAL →
PDF_QA。**"图片很漂亮"不构成任何通过理由**；VIS 评分高但 SEM 有 Critical → BLOCK。

## 6. Provenance 登记（§十一，01 文档 §3 的 AI 子集）

必填：figure_id / generation_method=ai_image_model / provider / model / timestamp /
prompt_hash / artifact_hash / source_material_refs / purpose / figure_type。
**绝不登记：API Key（provenance 白名单硬编码，越白名单字段丢弃+告警）。**

## 7. 人工审核触发（§十二：不能强制 PASS）

以下任一 → NEEDS_HUMAN_REVIEW（附样张+触发的 SEM 检号+建议动作）：
工程结构正确性无法机器判定 / 疑似虚构组件 / AI 标签不确定 /
图中出现研究材料未定义对象 / 图形与论文结论关系不明确。
人工裁决走既有人工双队列机制（不代签）。

## 8. AI 图与确定性图（§八，06 文档路由表的硬化）

| 类别 | 路由 | 强制级别 |
|---|---|---|
| Data Figure / Logic Figure / Engineering Calculation / Fault Tree / Research Result | **Local** | VIS-13：type∈此表 且 method=ai_image → **FAIL critical** |
| Conceptual Illustration / Visual explanatory figure | AI（可选）或 local | 须过 §1-§7 全链 |
| User-provided figure | user_asset | 不生成，登记校验 |

## 9. 与成本闸/回落的接缝

- 外部未配置 → 概念图也照常生成：回落 = local figkit 画"结构化示意框图"
  （质量略逊但正确、可追溯、零费用）；lifecycle 记 fallback_from。
- attempts 超限（3）→ 同上回落或 NHR；**绝不因"AI 更好看"绕过成本闸**。

## 10. 验收映射（08 文档测试号）

无 Plan 禁调用=AI-FIG-SEM-01；数据图/FTA 路由 Local=AI-FIG-ROUTING-01；
幻觉九检 BLOCK=AI-FIG-HALLUCINATION-01；范围=AI-FIG-SCOPE-01；
provenance 齐+无 Key 字段=AI-FIG-PROVENANCE-01；AI≠evidence=AI-FIG-SEM-02；
统一 QA 链（SEM→VIS→PDF）=AI-FIG-SEM-03。
