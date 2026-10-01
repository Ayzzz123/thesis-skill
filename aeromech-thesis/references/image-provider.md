# Image Provider（v1.6.5）— 外部生图规则

**定位**：外部 Image Model API 是**可选增强**。不配置任何键 = `UNAVAILABLE`
（**正常状态，不是错误**）→ Skill 照常使用既有 Figure Pipeline（figkit/mermaid
确定性图形）生成论文图，零阻塞、零费用。

本篇是 v1.6.5 Image Provider 的规则总纲。实现见 `scripts/`：
`image_config.py`（凭据解析）、`image_provider.py`（路由契约）、
`image_backends.py`（真实 HTTP 调用）、`ai_figure_gate.py`（受控生图闸）、
`image_cli.py`（用户命令）、`secret_leak_qa.py`（泄漏扫描）。

---

## 1. Provider 路由（四路径）

`image_provider.route(spec)` 是唯一路由判定点，返回：
`provider`（local / external）、`external_configured`、`external_implemented`、
`fallback_from`、`reason`。

| 情形 | 路由结果 |
|---|---|
| 无 `IMAGE_BACKEND` / 无凭据 | `UNAVAILABLE` → **回落 local**（`fallback_to_existing_figure_pipeline=true`） |
| 凭据格式非法 / 解析失败 | `INVALID` / `FAILED` → 回落 local，**除非** spec 显式要求 `provider_required=external` |
| 确定性研究图类型 | **恒 local**（即使 external 已配置） |
| AI 适用类型 + 已配置 | 走 external（未实现的 backend → `MODEL_UNAVAILABLE`） |
| `provider_required=external` 且无凭据 | `NEEDS_HUMAN_REVIEW`（不静默降级） |

**旧系统行为零改变**：spec 不带 `provider` 字段时路由结果恒为 `local`。

## 2. Local 优先（恒优先，不可配置覆盖）

`image_provider.DETERMINISTIC_TYPES` 与 `ai_figure_gate.DETERMINISTIC_TYPES`
覆盖：`fault_tree / stat_bar / stat_line / flow / tech_route / decision_matrix /
architecture / comparison / framework`（gate 侧另含 `research_result /
calculation_plot / fmea_rpn`）。

这些图**必须**保持数据正确、逻辑正确、结构可复现，因此**永不交给 AI 生成**。
`ai_figure_gate.plan_gate()` 在**任何 HTTP 调用之前**驳回确定性类型：
零 HTTP、零费用。

> 已知不一致（待收敛，见 §9）：两处 `DETERMINISTIC_TYPES` 与
> `EXTERNAL_ELIGIBLE_TYPES` 集合尚未合并到 `figure_style.FIGURE_TYPES`
> 单一来源，当前 gate 侧多 3 类确定性类型、多 1 类 eligible 类型。

## 3. External Eligible（允许交给 AI 的类型）

`conceptual_illustration`（概念示意图）、`visual_explanatory`（视觉说明）、
`apparatus_sketch`（装置草图）、`photo_like`（图像类素材）。
gate 侧另含 `cover_artwork`。

**这些图只能是插图性质的视觉资产**，不得承载研究数据、数值或结论。

## 4. 无 Key = UNAVAILABLE（正常状态）

`image_config.resolve()` 返回四态：`AVAILABLE / UNAVAILABLE / INVALID / FAILED`。

- **未配置不是错误**：`image_cli.py status` 在无 Key 时返回 **rc=0**；
- 不 BLOCK、不 fake image、不影响任何既有流程；
- 诊断输出永不含 Key（仅 `fingerprint = sha256[:8]`）。

## 5. 凭据解析链（搜索序）

`image_config.env_sources()` 的优先级（**首个命中即停，绝不跨文件合并**）：

```
runtime process env
  → project/.env        （默认禁用，需 IMAGE_ALLOW_PROJECT_ENV=1）
  → skill 级 .env       （AEROMECH_SKILL_HOME，默认 ~/.aeromech）
  → 用户级 ~/.aeromech/.env   ← 推荐
```

**project `.env` 默认关闭**：项目目录常被分享/提交，读它会把用户 Key 带进论文仓库。

**每后端前缀独立，不存在全局 `IMAGE_API_KEY`**。已登记的 backend 名：
`openai / gemini / qwen / zhipu / minimax / volcengine / host_native`；
变量形如 `<PREFIX>_API_KEY` / `<PREFIX>_MODEL` / `<PREFIX>_BASE_URL`。

**建议默认模型**（非敏感，可由用户 `<PREFIX>_MODEL` 覆盖）：
`openai → gpt-image-2`、`gemini → gemini-3.1-flash-image`。

**已实现真实 HTTP 调用的 backend**：仅 `openai`（`OpenAICompatBackend`）。
`qwen` 继承同一基类。其余（gemini/zhipu/minimax/volcengine）**仅解析配置，
未实现调用**——调用时会抛 `MODEL_UNAVAILABLE`，不伪装成功。
`host_native` **只解析配置态（零凭据）**，生成能力由宿主后续接入，当前不存在。

### 用户命令

```bash
python scripts/image_cli.py config    # 交互式写入 ~/.aeromech/.env（Key 不回显）
python scripts/image_cli.py status    # 查看配置态（无 Key = rc 0 正常）
python scripts/image_cli.py test      # 真实调用冒烟（--no-network 可离线检查）
python scripts/image_cli.py remove --backend openai
```

## 6. 错误分类（8 类）

`image_backends.ImageError.code`，401 **不伪装普通失败**：

| code | 触发 | 可重试 |
|---|---|---|
| `INVALID_CREDENTIAL` | 空凭据 / HTTP 401 | 否 |
| `RATE_LIMIT` | HTTP 429 | 是 |
| `MODEL_UNAVAILABLE` | HTTP 404 / backend 未实现 | 否 |
| `NETWORK_ERROR` | URLError / OSError | 是 |
| `TIMEOUT` | 请求或下载超时（默认 120s） | 是 |
| `PROVIDER_ERROR` | 其他 4xx/5xx、响应非 JSON | 是 |
| `CONTENT_POLICY_ERROR` | 内容策略拒绝 | 否 |
| `GENERATION_FAILED` | `data` 缺失/空/非 dict/不可解码、图像 <1000 字节 | 否 |

**成功形态**：`b64_json` 解码，或 `url` 形态经**无凭据 GET** 下载
（绝不对第三方 CDN 发送 `Authorization`）。

## 7. 成本闸

- `IMAGE_MAX_ATTEMPTS`（默认 **3**）限制**每图**外部调用次数；
- 计数**跨进程持久**：写入 `figures/figure-lifecycle.yaml` 的
  `provider_meta.attempts`，重启后不归零；
- 达到上限 → 零 HTTP 回落 local；
- **首次调用向用户明示**：将使用您配置的 Image Model API Key 调用外部服务，
  可能产生 API 费用。

> 注意：`image_cli.py test` 是**真实生成**冒烟，不计入该成本闸（用户主动触发）。

## 8. Secret 脱敏与泄漏扫描

三层防护：

1. **`SecretStr`**：Key 只存运行时对象，`repr/str/format` 全掩码；
2. **`redact_text()` / `redact_obj()`**：8 条规则覆盖 `Authorization`、`Bearer`、
   `sk-*`、`AIza*`、`ghp_*`、JWT、`api_key=` 等形态；
   `figure_iface.record()` / `thesis_orchestrator.log_action()` 边界统一调用；
3. **`secret_leak_qa.py`**：三 scope 扫描
   （`repo` / `diff` / `artifacts`），疑似真实凭据 → FAIL，高熵可疑串 → WARN。

**Key 不得进入**：Git、论文项目、`.aeromech` 产物、JSONL、报告、DOCX/PDF、日志。
仓库只保存 `.env.example`（全部占位值）。

## 9. Provenance（溯源登记）

`ai_figure_gate.build_provenance()` 产出 10 字段白名单登记：
`figure_id / generation_method / provider / model / timestamp / prompt_hash /
artifact_hash / source_material_refs / purpose / figure_type`。

- **字段名黑名单**：`SECRETISH`（key/token/authorization/secret/credential/bearer）
  的字段一律拒收；
- `prompt_hash = sha256[:16]`，可复算但不可逆；
- 生成提示词只能由 Figure Plan + 登记素材摘要 + 学术视觉规范组装，
  **拒绝任意自由文本直传**。

## 10. 受控生图（两道闸）

`ai_figure_gate.py`：**任一闸不过 → 零 HTTP 调用**。

1. **Figure Plan 九字段前置**（`plan_gate`）：
   `figure_id / figure_type / purpose / intended_section / semantic_content /
   source_material / research_link / required_visual_elements /
   forbidden_elements`。缺失 → `FIGURE_PLAN_REQUIRED`。
2. **结构化提示词组装**（`assemble_prompt`）：字段全部源自 Plan。

## 11. AI 生成视觉 ≠ 研究证据（硬规则）

- `research_integrity.EVIDENCE_TYPES` 含 `ai_generated_visual`，但该类型的
  `verification_status` **禁 `verified` / `partial`**，违反 → `RI-E-DISGUISE`
  **critical**；
- 证据种子仅限 `E / DS / CALC / M`；
- AI 图**不得**注册为证据（E）、数据源（DS）、计算（CALC）或方法（M）；
- AI 图**不得**被表述为实验结果或实测数据。

## 12. 文档与配置模板

- 用户配置模板：`aeromech-thesis/.env.example`（仓库内唯一，全占位值）；
- 设计文档：`docs/v1.6.5/image-provider/01-10`（开发文档，不随 Skill 分发）；
- 本文件是 Agent 运行时读取的**规则**，与设计文档冲突时以代码行为为准。

---

## 13. 已知限制（如实记录）

1. 仅 `openai` 后端实现真实 HTTP 调用；其余 backend 名可解析但调用会
   `MODEL_UNAVAILABLE`。
2. `host_native` 仅有配置态解析，无生成实现。
3. `DETERMINISTIC_TYPES` / `EXTERNAL_ELIGIBLE_TYPES` 在 `image_provider.py` 与
   `ai_figure_gate.py` 各有一份且已漂移（见 §2 注）。
4. `IMAGE_MAX_ATTEMPTS` 计数载体是项目内 `figure-lifecycle.yaml`——删除/更换
   项目根即归零。
5. 真实网络冒烟（`image_cli.py test`）需用户自备凭据；无凭据时该项记为
   `LIVE_SMOKE_TEST=NOT_RUN`，不阻塞交付。
