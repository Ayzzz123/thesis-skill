# IMAGE_PROVIDER_ARCHITECTURE（01）

## 1. 分层（§六 要求，落到本项目真实接缝）

```
Figure Generator（Agent 决策 / build 调用）
        │  generate_figure(root, fid, provider=<name>)
        ▼
figure_iface.FigureProvider  ← 既有契约（plan/generate/validate + 生命周期）【KEEP】
        │
        ├─ LocalProvider【KEEP，默认】── figkit / render_mmdc / 受控脚本（确定性图）
        │
        ├─ ImageModelProvider【NEW 薄适配】
        │       │  resolve() → 选后端；不持 Key、不发 HTTP
        │       ▼
        │   image_providers.base.ImageBackend（抽象）
        │       ├─ OpenAIImageBackend   【NEW】
        │       ├─ GeminiImageBackend   【NEW】
        │       ├─ OpenAICompatBackend  【NEW，qwen/zhipu/minimax/volcengine 配置驱动】
        │       └─ HostNativeBackend    【NEW，零 Key，见 07】
        │
        └─ UserAssetProvider【NEW 极薄】── 用户提供图片登记（不生成）
```

要点：
- **Generator 不碰 Key**（§六）。Key 只在 `image_config.resolve()` 与具体
  `ImageBackend.generate()` 内部出现，且后者拿到的是**进程内字符串**，绝不回传给
  figure_iface 层。
- `ImageModelProvider` 是 `FigureProvider` 的子类（F1）：
  - `plan()`：委托 LocalProvider 推导（同一注册表），对 `provider=image` 的条目保留；
  - `generate()`：调 backend → 成功则写 artifact + `record(GENERATED, provider_meta=…)`；
    未配置/失败按 §八/§十七 分类返回，**不落任何占位图**（与 v1.6.5 D2 修复同一纪律）；
  - `validate()`：复用研究链接硬关卡；AI 位图无 figkit layout → 几何 SKIP、
    `figure_visual_qa` VIS-02/09/10 像素级 + 人工 NHR（既有语义，不另造）。

## 2. 与生命周期/构建/门禁的接缝（全部复用，不新增状态词）

| 接缝 | 机制 | 新增行为 |
|---|---|---|
| 生命周期 | PLANNED→GENERATED→VALIDATED→EMBEDDED→VERIFIED / REJECTED / NEEDS_HUMAN_REVIEW【KEEP】 | GENERATED 记录附 `provider_meta`（见 §3）；未配置→NHR + 结构化 reason 码 |
| build EMBEDDED | thesis_build 在占位行命中时 record【KEEP】 | 不感知 provider/key |
| gate G-FIG-01 | REJECTED→critical、NHR→high【KEEP】 | 无改动；IMAGE_PROVIDER_NOT_CONFIGURED 的图自然停在 NHR，**交付门禁不放行未配置图**（防"没 Key 也交付"） |
| figure_visual | VIS-01~12【KEEP】 | AI 图同样过（尤其 VIS-09 禁项：渐变/阴影滥用恰是 AI 图常见病） |
| research traceability | 种子=E/DS/CALC/M【KEEP】 | 见 §4 守卫 |

## 3. provenance 元数据（§十五，可记录 vs 绝不记录）

`figure-lifecycle.yaml` 的 GENERATED/VALIDATED 记录新增可选字段：
```
provider_meta:
  provider_used: image            # local | image | host_native | user_asset
  generation_method: ai_image     # figkit_script | mermaid_mmdc | ai_image | host_native | user_asset
  backend: openai                 # 具体后端名
  model: gpt-image-1              # 模型名（非敏感）
  prompt_hash: sha256:…           # 提示词哈希（可复现审计，不存原文长文）
  artifact_hash: sha256:…         # 既有 sha256 字段复用
  timestamp: …                    # 既有
  attempts: 2                     # 本图第几次外部调用（成本闸计数依据）
```
**绝不记录**：api_key、authorization、base_url 查询参数中的 token、请求头任何值。
`record()` 边界统一 `redact()`（F3），即使调用方误传也会被洗掉——双保险。

## 4. AI 图 ≠ research evidence（§十五 守卫，三条）

1. **注册表守卫**（research_integrity 小改）：evidence.source_type 新枚举值
   `ai_generated_visual`，其 `verification_status` 强制 ∈ {simulated}（同
   simulation/assumption 的 RI-E-DISGUISE 规则扩展）→ AI 图声称"实测/真实"直接
   critical FAIL。datasets/analyses 不接受该类型（数据结构不变）。
2. **引用守卫**（RQG 新检 RQG-16，WARN→NHR）：正文中 claim 的 evidence 链若仅由
   `ai_generated_visual` 支撑 → NEEDS_HUMAN_REVIEW（"AI 示意图不能作为事实依据"）。
3. **呈现守卫**：AI 生成图题注必须含【AI 生成示意图】标签（figure_visual 增
   VIS-13：题注与 provider_meta.generation_method 一致性，机检）。

## 5. 路由入口（§十六，细节见 06）

`figures.yaml` 条目新增可选 `provider` 字段（缺省 local）：
```
{id: FIG-007, name: 概念示意图, provider: image, type: conceptual_illustration, …}
```
Agent 在 S8 规划时按类型路由表决定；用户可显式覆盖。build 阶段零决策。

## 6. 文件清单（实现阶段）

```
scripts/image_config.py            NEW  解析/优先级/脱敏诊断（纯 stdlib）
scripts/image_providers/__init__.py NEW 注册表
scripts/image_providers/base.py     NEW 抽象+错误分类学（§十七 九类）
scripts/image_providers/openai_images.py / gemini_images.py / openai_compat.py / host_native.py
scripts/image_cli.py                NEW  aeromech image config|test|status
scripts/secret_leak_qa.py           NEW  全表面泄漏扫描
scripts/figure_iface.py             REFACTOR record() redact + provider_meta + 注册 ImageModelProvider
scripts/research_integrity.py       REFACTOR source_type 枚举 + DISGUISE 扩展
scripts/research_quality_qa.py      REFACTOR RQG-16（AI 图证据守卫）
scripts/thesis_orchestrator.py      REFACTOR log_action redact
.gitignore                          REFACTOR env/secret 条目
references/image-provider.md        NEW    文档（09 计划）
tests/v1_6_5/test_image_provider_*.py  NEW  四测试文件（08 计划）
```

## 7. 设计红线（对齐任务 §一/§八/§十五/§二十一）

- Skill 仓库零真实 Key、零默认 Key、零共享 Key（§一）
- 无 Key → 明确 NHR/NEEDS_CONFIGURATION，绝不 fake image PASS（§八）
- AI 图永不自动成为实验数据/测量/故障率/文献事实（§十五）
- 本设计阶段不写实现、不 push/merge/PR/release（§二十一）
