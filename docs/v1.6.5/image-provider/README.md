# v1.6.5 Image Model Provider — 架构审计与设计（Phase 设计稿，未实现）

日期：2026-09-19 ｜ 分支：feature-1.6.5-figure-optimization ｜ 基线：v1.6.0 (7aabc37) + phase1 视觉系统 (3f27c81)
性质：**只做审计与设计，零实现代码**。参考 ppt-master 的架构思想（用户级 .env +
provider-specific 配置 + 环境优先级），未复制其任何代码；与本项目
Figure Provider / Research Integrity / Agent Loop 深度结合。

## 文档索引

| 文件 | 内容 |
|---|---|
| 01-figure-system-audit.md | （前序）图形系统审计 |
| 02-visual-design-system.md | （前序）视觉系统 |
| image-provider/README.md | 本文件：KEEP/REFACTOR/NEW 总表 + 10 问回答 |
| image-provider/01-architecture.md | IMAGE_PROVIDER_ARCHITECTURE（分层 + 与生命周期/构建/门禁的接缝） |
| image-provider/02-credential-resolution.md | CREDENTIAL_RESOLUTION（解析算法、fail-closed、诊断输出脱敏） |
| image-provider/03-env-search-order.md | ENV_FILE_SEARCH_ORDER（4 级优先、首命中不合并、项目级风险处置） |
| image-provider/04-provider-interface.md | PROVIDER_INTERFACE（ImageModelProvider 抽象、adapter 契约、错误分类学） |
| image-provider/05-security-model.md | SECURITY_MODEL（8 条禁令的可执行化、redaction、secret-leak QA、成本闸） |
| image-provider/06-figure-type-routing.md | FIGURE_TYPE_ROUTING（确定性图→Local；视觉型→AI；用户素材；host-native） |
| image-provider/07-host-native.md | HOST_NATIVE_INTEGRATION（宿主原生生图零 Key 路径） |
| image-provider/08-test-plan.md | TEST_PLAN（4 个测试文件 × 15 项必测 + 负例设计） |
| image-provider/09-documentation-plan.md | DOCUMENTATION_PLAN（references/image-provider.md 目录 + 接线） |

## 审计事实（设计依据，全部可复核）

| # | 事实 | 证据 | 设计含义 |
|---|---|---|---|
| F1 | FigureProvider 契约完备：plan/generate/validate 三方法 + `PROVIDERS` 注册表 + `get_provider(name)` 按名切换 + 生命周期 PLANNED→…→VERIFIED/REJECTED/NHR | figure_iface.py:92-118, 59-61, 412 | **新 Provider 只需继承注册**，主线零改动（§六 架构天然满足） |
| F2 | 全仓无任何 dotenv/credential 读取代码；唯一 env 用法是 `THESIS_OUT`/`AEROMECH_INSTALL_ROOT`（非敏感） | grep `load_dotenv\|_API_KEY\|Authorization` = 空 | 凭据层是**全新面积**，无历史包袱，也**无任何现成脱敏** |
| F3 | 两处自由文本入盘：`record(..., reason=…)` → figure-lifecycle.yaml（项目内、会交付）；`log_action(input/output)` → actions.jsonl | figure_iface.py:173-188；thesis_orchestrator.py:82-97 | 异常文本可能携带 Authorization/Bearer → **必须在 record/log 边界统一 redact**，而非指望调用方自觉 |
| F4 | 追踪性种子 = E/DS/CALC/M；figures 是链上产物不是证据种子；`RI-E-DISGUISE` 已禁止模拟伪装实测 | research_integrity.py:539-560, 308 | AI 图 ≠ evidence 已有**结构基础**，只需显式化守卫（§十五） |
| F5 | .gitignore 现无 `.env` 条目 | cat .gitignore | 立即补，且**不作唯一防线**（§十一） |
| F6 | provider 在 generate 时刻选择（CLI/plan 记录），EMBEDDED 由 build 统一记 | figure_iface.py:362-386；thesis_build.py:395-397 | 路由决策放 provider 层，build 不感知 key |
| F7 | sync.py 已知安装目录解析（`~/.qoder-cn/skills/aeromech-thesis`，env 可覆盖） | sync.py:23,145 | "Skill 安装目录 .env" 路径可复用同一解析思想，但运行期脚本不能 import sync.py（仓库根文件）→ 用 `AEROMECH_HOME`+推导 |
| F8 | ppt-master 模式（仅思想）：`IMAGE_BACKEND` + `<PROVIDER>_API_KEY`；先 process env 再**首个命中**的 .env（cwd→skill→repo→~/.ppt-master/.env）；`.env.example` 模板；`--list-backends` 发现 | 其 README（本次 WebFetch 摘要） | 采纳：backend 选择、provider-specific 前缀、首命中不合并、example 模板、无 Key 发现命令；调整：用户级目录名 `~/.aeromech/.env`、项目级 .env 降权并警告 |
| F9 | 生命周期状态词表已固定七态，gate 的 G-FIG-01 按 REJECTED→critical、NHR→high 映射 | figure_iface.py:59-61；delivery_gate.py 图域 | "没配 Key" 不得新增状态词：用 **NEEDS_HUMAN_REVIEW + 结构化 reason 码**（IMAGE_PROVIDER_NOT_CONFIGURED）表达，gate 自然转 NHR，不 fake PASS |
| F10 | 自动重生成已有 loop 预算语义（v1.5 ≤5 轮；本次任务规定外部生图 max_generation_attempts=3） | SKILL §20/21 | 成本闸独立于 QA 重试：**按 figure_id 计外部 API 调用次数**，超限→NHR |

## KEEP / REFACTOR / NEW 总表

### KEEP（原样复用，零改动）
- `FigureProvider` 抽象 + `register_provider`/`get_provider` + `PROVIDERS` 注册表（F1）
- 生命周期七态词表 + `record()`/`current_status()`/`lifecycle_state()` 机制（F9）
- `research_integrity` 追踪性种子模型与 RI-E-DISGUISE（F4）
- `LocalProvider` 全部现有能力（figkit 确定性图、mermaid 真实渲染、受控脚本执行）——**绝不因加 AI 生图削弱**（§七）
- delivery_gate 五态聚合、G-FIG-01 映射、v1.6.5 figure_visual QA（AI 图同样要过 VIS/PDF 渲染级检查）
- 受控执行模型（项目根内相对 .py、无 shell）与 v1.5 recompute 信任边界

### REFACTOR（小步改造，接口兼容）
- `figure_iface.record()`：reason 写入前统一过 `redact()`（F3）；`_result()` 增加
  `provider_meta`（provider_used/generation_method，§十六）——旧记录无该字段=兼容
- `LocalProvider.plan()`：spec 增加可选 `provider_hint`/`type` 路由字段（F6，缺省行为不变）
- `thesis_orchestrator.log_action()`：input/output 落盘前过同一个 `redact()`（F3）
- `.gitignore`：补 `.env`/`.env.*`/`!.env.example`/`*.secret`/`credentials.*`/`user-config.*`（F5）
- `figure_visual_qa`/`graph_quality_qa`：对"位图无 layout JSON"的 AI 图维持 NHR 语义，
  新增 provenance 检查钩子（VIS-13 候选，见 04 文档）

### NEW（全新，全部隔离在新文件）
- `scripts/image_config.py` —— .env 解析 + 4 级优先级 + provider-specific 读取 + 脱敏诊断（纯 stdlib，无第三方 dotenv 依赖）
- `scripts/image_providers/`（包）—— `base.py`（ImageModelProvider 抽象 + 错误分类学）、
  `openai_images.py`、`gemini_images.py`、`openai_compat.py`（qwen/zhipu/minimax/volcengine 共用
  OpenAI-compatible 端点，配置驱动不逐家写死）、`host_native.py`
- `scripts/figure_iface.py` 内注册 `ImageModelProvider`（薄适配器：契约→image_providers）
- `scripts/secret_leak_qa.py` —— 全表面扫描（git diff/staged/日志/artifacts/tests/reports），
  疑似真实 Key→BLOCK（§十/§十一）
- `aeromech image config|test|status` CLI 入口（`scripts/image_cli.py`，Key 不回显）
- `references/image-provider.md` 文档 + SKILL 加载表/路由表接线
- 测试：`tests/v1_6_5/test_image_provider_{config,resolution,security,integration}.py`

## 10 个重点问题（简答，细节在各分文档）

1. **哪部分可直接复用 FigureProvider？** 全部契约层（F1）：新 image provider = 继承
   `FigureProvider` 实现三方法 + `@register_provider`。plan 复用注册表推导；validate 复用
   研究链接硬关卡 + VIS/GQ（AI 图无 layout JSON → 几何 SKIP、渲染级+人工照旧）；生命周期、
   gate 映射、build EMBEDDED 全部零改动可用。
2. **.env 搜索路径？** 进程 env → `$CWD/.env`（警告级）→ Skill 安装目录 `.env` →
   `~/.aeromech/.env`（推荐）。**首命中即停，绝不跨文件合并 secret**（03 文档）。
3. **不同用户自己的 Key？** Key 只存在于本机用户级文件/进程 env；仓库只有
   `.env.example`；机器 A/B 各读各的 `~/.aeromech/.env`，互不可见（§十三，测试 RES-13）。
4. **防 Key 进 Git？** 四道：.gitignore 补条目（非唯一）→ secret_leak_qa 扫 diff/staged/
   产物 → record/log_action 边界 redact（源头不写入）→ 交付前 gate 域（SEC-01~05）。
5. **没 Key 仍能用 Local？** 默认路由本就是 Local（确定性图全部本地）；AI 仅当 figure 显式
   声明 `provider=image` 才走外部；未配置→`NEEDS_HUMAN_REVIEW` +
   `IMAGE_PROVIDER_NOT_CONFIGURED` 码，**绝不 fake 图 PASS**（§八，06 文档）。
6. **Host-native 接入？** `host_native.py` 不持 Key、不发 HTTP：返回
   `HOST_NATIVE_REQUESTED` 结构（prompt+尺寸+落盘路径），由 Agent Host 用原生能力生成后
   `figure_iface record` 补 artifact；无 host 能力时同样 NHR（07 文档）。
7. **OpenAI-compatible 作为一个 Provider？** `openai_compat.py` 单实现 + 配置驱动
   （`<BACKEND>_BASE_URL/<BACKEND>_API_KEY/<BACKEND>_MODEL`），qwen/zhipu/minimax/volcengine
   经同一 adapter 接入，新增厂商=加配置不加代码（04 文档 §端点矩阵）。
8. **限制自动重生成的 API 成本？** 三重闸：`IMAGE_MAX_ATTEMPTS`（默认 3，按 figure_id 在
   lifecycle 计数）超限→NHR；首次外部调用前一次性费用提示（CLI 与 agent 路径都有）；
   orchestrator 重试策略对 `image` provider 禁 retry（05 文档 §成本闸）。
9. **AI 图不成 research evidence？** 结构守卫：evidence 注册表 `source_type` 无
   `ai_generated_image` 值（新增枚举 `ai_generated_visual` 且 verification_status 强制
   `simulated` 同等待遇→RI-E-DISGUISE 自动禁伪装）；figures.yaml 记
   `generation_method: ai_image:<provider>` + prompt_hash；追踪性种子不变（F4）；
   RQG 增检"AI 图被 claim 直接当事实引用"→NHR（01/04 文档 §研究完整性）。
10. **clone/install 后不改源码即可配置？** 三步：复制 `.env.example` → `~/.aeromech/.env`
    （或跑 `aeromech image config` 交互写入，Key 不回显）→ `aeromech image test` 验证
    （输出只报 configured/***REDACTED***/Connection）。零源码修改、零项目内文件（09 文档）。

## 边界声明

本阶段无实现代码、无测试改动（除文档）、未 push/merge/PR/release。
实现阶段按 08-test-plan 的 T0~T4 顺序推进，先 security 骨架后具体 adapter。
