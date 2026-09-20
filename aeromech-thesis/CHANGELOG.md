# CHANGELOG — aeromech-thesis

## v1.6.5 — Academic Figure Quality & User-Configured Image Provider

**状态：已发布（2026-09-19）。发布验证：Phase 0 审计 + Phase 1 学术视觉系统 + Phase 2A 凭据/安全/回落 + Phase 2B 真实 OpenAI 兼容 Provider 与受控 AI 生图（实现+测试）；Release Readiness Check（九项证据 + HEAD 现势复核，RELEASE_READY=YES）+ 最终 Release 回归全绿 + test-8.0 全 QA PASS + Delivery Gate=PASS。tests/v1_6_5 124 断言 + v1_4/v1_4_1/v1_5/v1_6/test_a/test_b 全绿 + secret_leak_qa FAIL=0 + dev↔install IDENTICAL。版本升级 v1.6.0→v1.6.5（test_document_contract 版本态断言同步翻转到 v1.6.5 发布态）。**

已完成：

- **Academic Visual System**：`figure_style.py` 单一来源（3 轮量化验证的调色板/字号阶梯/间距/图类型注册）；`figkit.py` role= 语义角色色 + style_fingerprint 跨图家族一致；mermaid 回退 fail-closed（语义伪造移除，渲染失败=REJECTED 绝不假装成功）；自证式 PASS 移除（FIG-05/06 删除、GQ-15→SKIP 人工复核项）。
- **Visual QA**：`figure_visual_qa.py` VIS-01~12（可测项机器判定、主观项→NEEDS_HUMAN_REVIEW、分数永不覆盖 Critical）入 `thesis_build.py` QA 链 + `delivery_gate.py` figure_visual 域；graph_quality 渲染级测量校准（刻度标签带裁剪 + 数字墨高 0.72em——修复假 FAIL，未放松 9.5pt 标准）。
- **User-Configured Image Model API（可选增强，零阻塞）**：`image_config.py` 凭据解析链 process→skill→`~/.aeromech/.env`（用户级；project .env 默认关闭需 IMAGE_ALLOW_PROJECT_ENV=1；SecretStr 全掩码+指纹，to_public 不含值）；`image_cli.py` config/status/test/remove（status 无 Key=rc 0 正常态）。
- **OpenAI-Compatible Provider**：`image_backends.py` /images/generations（b64_json 解码、原子落盘、<1000B 判 GENERATION_FAILED）+ 8 类错误分类（INVALID_CREDENTIAL/RATE_LIMIT/MODEL_UNAVAILABLE/NETWORK_ERROR/TIMEOUT/PROVIDER_ERROR/CONTENT_POLICY_ERROR/GENERATION_FAILED；401 不伪装普通失败；错误文本落盘前 redact）+ 可注入 `_http` transport（回归测试零真实网络）。
- **No-Key Fallback**：无 Key=正常状态自动回落既有 Figure Pipeline（UNAVAILABLE≠错误；旧 spec 零 env 接触、与 v1.6.0 行为字节一致；五类确定性图恒 local 优先；仅 provider_required=external 且无凭据→NEEDS_HUMAN_REVIEW）。
- **Figure Plan Controlled Generation**：`ai_figure_gate.py` 九字段前置闸（缺失→FIGURE_PLAN_REQUIRED+零 HTTP）；确定性图类型禁 AI 接入；结构化溯源提示词（SYSTEM/PURPOSE/INTENDED_SECTION/SEMANTIC_CONTENT/SOURCE/MUST_SHOW/MUST_NOT_SHOW/STYLE 全部源自 Plan，prompt_hash=sha256[:16]）；provenance 白名单（provider/model/timestamp/prompt_hash/artifact_hash/source_material_refs 等，类 Key 字段名拒绝）；IMAGE_MAX_ATTEMPTS=3 成本闸（跨进程持久）+ 首次调用费用明示。
- **AI-Generated Visual ≠ Research Evidence**：generation_method=ai_image_model 禁标 verified/partial（RI-E-DISGUISE critical）；证据种子仅 E/DS/CALC/M；record/log 边界 redact（lifecycle/JSONL 落盘无凭据）。
- **Secret Security**：`secret_leak_qa.py` repo/diff/artifacts 三 scope（9 类 FAIL 正则 + 高熵 WARN；tests/ sk-TEST- 白名单 + 行级可审计豁免 secret-scan-exempt）；发布态 FAIL=0。
- **test-8.0 validation**：三图按视觉系统重绘（逻辑/数据 100% 不变，VIS 15 项 ALL PASS）；GQ-01b 图3-2 真实文本溢出修复（E6 框加宽）；pipeline 全阶段 PASS + Delivery Gate=PASS。

已知限制：

- **LIVE_SMOKE_TEST = NOT_RUN（REASON = USER_CREDENTIAL_NOT_PROVIDED）**：发布时真实 API 冒烟未执行（用户未提供 Key），如实记录、绝不伪装 PASS。外部 Provider 代码路径经可注入 transport 全覆盖测试（IMG-01~14，26/26 断言）；用户配置 Key 后 `aeromech image test` 一次冒烟即可补验（调用前明示费用），非阻塞项。**（已于发布当日随用户完成真实凭据配置而解决——真实 Smoke PASS，见下方 Post-release 小节。）**

### Post-release 修复与真实验证（2026-09-20；HEAD = f8b7ceb，working tree clean）

发布当日用户完成真实凭据配置（`IMAGE_BACKEND=openai` + provider 专属 API Key 环境变量如 `OPENAI_API_KEY`，写入用户级 `~/.aeromech/.env`），随后仅两轮必要兼容修复与真实验证——未新增功能、未动 Figure Plan/Cost Guard/Visual QA/Academic Style QA/Research Boundary/Secret Leak 任何边界语义：

- **782ad0d — gpt-image 请求参数兼容**：gpt-image 系拒绝 `response_format` 参数与 256x256 尺寸（HTTP 400，真实中转站实测 PROVIDER_ERROR 根因）→ 按模型族判断：gpt-image 系不发 response_format、smoke 尺寸 1024x1024（DALL-E 等其他模型族行为原样保留）；`image test` 失败时输出 redact 后的 provider message（原先只打错误码）；成功时同一次调用落盘 `smoke_test_only` artifact + provenance 旁车（`~/.aeromech/smoke/`）；test_image_resolution `Clean()` 补 HOME 隔离（真实用户 env 不再泄漏进密封断言）。
- **f8b7ceb — url 形态成功响应兼容**：解析器审计确认 OpenAI-compatible 两种文档化成功形态中 `data[0].url` 未支持（URL 形态 200 会被误判 GENERATION_FAILED）→ 最小兼容：url 形态经**无凭据 GET** 取回已完成生成的产物（绝不向第三方 CDN host 携带 Authorization，IMG-GPT-06b 断言）；HTTP 200+非 JSON 归类 PROVIDER_ERROR（原为裸 JSONDecodeError）；data 缺失/`[]`/`[{}]`/`[None]` 一律 GENERATION_FAILED 不误判成功；b64_json 路径逐字节不变。离线 CASE A~E 回归（IMG-GPT-05~09，零真实网络）。
- **真实 API Smoke（各恰好 1 次调用，均成功，无重试）**：
  - `aeromech image test`：gpt-image-2 真实生成 OK（1024x1024 PNG，sha256 5e6d01bb…，provenance smoke_test_only）——**b64_json 真实链路验证 PASS**；
  - Figure Pipeline 端到端（独立临时项目，非 test-8.0）：Figure Plan Gate PASS（零 HTTP 授权）→ external/openai/gpt-image-2 路由 → 结构化提示词 → 1 次真实 POST → b64_json 解析 → GENERATED + provenance（prompt_hash 逐字节复算一致）；产物标记 smoke_test_only；像素审计 0.00% 霓虹像素 + 单色系学术蓝 + 白底；AI 图未进入任何研究证据（RI-E=0，evidence/DS/CALC/M 注册表零触碰）；全 scope 泄漏扫描 FAIL=0；正式 VIS 域对非 figkit 源按既定语义 VIS-00（layout 元数据不可用→PDF 级 QA 兜底），1 处疑似 CJK 字形小误列为人工确认项；出站凭据审计确认仅生成 POST 携带 Authorization。
- **结论：本阶段完成；后续不继续扩展 Image Provider，转入真实论文项目端到端验证。**（url 响应形态已有离线测试覆盖；真实验证仅使用 b64_json 形态，各 1 次调用。）

## v1.6.0 — Full-Stack Thesis Orchestration

**状态：已发布（2026-09-17）。发布验证：Phase 0~5 实现+测试；Phase 6 = test-8.0 全栈冷启动（新校模板、四断点恢复实测、隐藏缺陷自查含 2 项 DETECTION FAILED 修复复验、人工复核 7/7、delivery_gate=PASS）；Phase 7 = RC 报告与版本升级 v1.5.0→v1.6.0。tests/v1_6 395 断言 + v1_4/v1_4_1/v1_5/test_a/test_b 全绿 + t30~t70 外部回归 + dev↔install IDENTICAL。**

已完成（Phase 0~4，实现+测试；各 Phase 报告见仓库 .aeromech/artifacts/analysis/）：

- Phase 0 审计：`v1.6-gap-analysis.md`（10 检查点逐项 + 目标→差距矩阵）+ `v1.6-implementation-plan.md`。
- Phase 1 核心数据层：`scripts/thesis_state.py`（StateIO：state.md §3~§11 程序化迁移校验；
  Checkpoint 工件 CK-XXX：stage/task/cursor/artifacts+sha256/registries 快照/qa_state/next_action；
  resume 视图：from_start=false、成果完好性比对）；`material_ingestion.py`（scan/SHA256 去重/类型推断
  注册/check——"不得重复读取"程序化；schema=state.md §16.1，type 枚举扩展 school_notice/task_book/proposal）；
  `school_requirements.py`（模板 docx 结构字段机械提取 + 逐字段 provenance∈official/sample/default/unknown；
  样文永不冒充 official；PDF 规范不猜测；合并写 school-format.yaml additive `school_requirement`）。
- Phase 2 上下文与调度：`research_context.py`（13 注册表只读聚合视图：RQ/objectives/methods/evidence/
  data/analysis/claims/conclusions/scope/assumptions/limitations + coverage/validate/traceability 直接复用
  引擎；OK/NOT_APPLICABLE/ERROR）；`stage_routing.py`（调度矩阵=MATRIX 数据；route() 只判定不执行；
  门禁 item 级 v1.4.1 七态；交付五态 delivery_gate_status；回退映射表 CATEGORY_TARGET/ISSUE_TYPE_TARGET；
  设计门禁 INFEASIBLE→blocked stay；证据缺=SKIPPED_WITH_REASON）。
- Phase 3 Orchestrator：`thesis_orchestrator.py`（status/step/drive/resume/run-loop/apply-human/gate/actions；
  Action 模型 JSONL 留痕禁止静默执行；RUN_PENDING 执行既有 AI 工具；迁移只经 thesis_state；
  classify_recovery 五策略=issue_type+severity+v1.5 disposition+阶段映射共同决定（retry 上限 1/
  REPAIR 复用白名单/ROLLBACK 经 StateIO+恢复前 checkpoint/HUMAN_REVIEW 双队列不代签/BLOCK Critical）；
  drift_checks：STATE_DRIFT/REGISTRY_DRIFT/ARTIFACT_MISSING/ARTIFACT_CHANGED 不静默覆盖）。
- Phase 4 交付层：`figure_iface.py`（FigureProvider 契约 plan/generate/validate + PROVIDERS 注册；
  生命周期 PLANNED→GENERATED→VALIDATED→EMBEDDED→VERIFIED / REJECTED / NEEDS_HUMAN_REVIEW；
  研究链接硬关卡（RQ/AN/CL）；LocalProvider 复用 render_mermaid/受控脚本执行/graph_quality_qa；
  不复制协作者 Figure Engine）；`thesis_build.py`（build-contract.yaml 七域契约：required 缺=ERROR/
  optional 缺=NOT_APPLICABLE 不补假数据；双模式组装走 docx_engine/template_fidelity；
  pipeline 固定顺序 docx→toc→repaginate→pdf→finalize→qa 全调既有脚本、失败输出
  {failed_stage,error_code,reason,suggested_action}；artifact-manifest.yaml sha256+content_identity
  （排除 docProps/.rels 的内容身份 vs 容器哈希分离））；`delivery_gate.py`（聚合格式链 md 报告+pipeline
  步骤+Document/manifest 一致性+Figure 生命周期+研究侧复用 routing+人工双队列 → 五态终局，
  每项 {gate_id,domain,status,severity,evidence,reason,remediation}；缺证据=BLOCK；ERROR 不透 PASS；
  总分不参与放行；旧项目域 N/A 不误伤）。
- 测试：`tests/v1_6/`（Phase1~4 共 13 文件 317 断言；全部旧套件 v1_4 11/11、v1_4_1 5/5、v1_5 13/13
  418 断言、test_a/test_b、t30~t70 外部回归持续绿；dev↔install IDENTICAL 规程维持）。
- 本 Phase（5）文档收口：`references/orchestration.md` 规则总纲；SKILL.md §21/加载表/路由/§7/§16；
  state.md §18 + schema additive（checkpoint 键、读取兼容 1.1）；delivery-pipeline.md §1 流程图更新 +
  §8.4/§8.5；README v1.6 development/roadmap；`test_document_contract.py`（文档=代码=测试一致性锁）。

- Phase 6 test-8.0 全栈冷启动（新材料/新题目：中国民用航空飞行学院官方模板 + GB/T 7713.1/7714；
  S3/S5/S7/S9 四断点恢复实测全部 RESUMED；Template+Research+Loop+Figure+Build+Gate 联合触发；
  交付物 delivery_gate=PASS；报告 `.aeromech/artifacts/qa/test-8.0-final-report.md`）。
- Phase 7 发布：全回归复跑 + `v1.6-release-report.md` + RC PASS 判定 + 版本三联动升级
  （SKILL/README/CHANGELOG v1.5.0→v1.6.0；test_document_contract 版本态断言同步翻转到发布态）。

Test-8.0 期间发现并修复的根因缺陷（8 类，全部回归锁定，不针对单篇特例）：
① parse_md 表体静默丢失（英文题注缺失时）；② 契约 tables 域未接通 + 图/表双语题注分流；
③ 图生命周期误含 TABLE-* 条目；④ 封面填充/对照 QA 硬编码旧校口径（新增 cover_profile 风格画像
images/grid/lines + 契约驱动 cover_fields/cover_tables/cover_text_fills）；⑤ QA 检测器硬编码章数/
附录字母/目录窗口/正文起点（改为从文本派生）；⑥ Word COM 往返剥 w:sz/tblStyle（有效字号回退 +
cover_restore 步骤）；⑦ 检测缺口：正文级强断言（RQG-10 正文 HIGH 词扫描→NHR）与悬空图引用
（FIG-13→FAIL）——两项 DETECTION FAILED 如实记录后根因修复并复验；⑧ HTML 实体残留（通用
unescape_text 接全部 DOCX 文本入口 + content_purity ENT-01 兜底）。

## v1.5.0 — Research Intelligence & Agent Loop

**目标：在 v1.4.1 稳定基线之上新增研究智能层（发现→诊断→根因→修复→重分析→再验证闭环），只增不破：不改既有 RQG/QA 语义，旧项目（无 design/scope/repairs）全部 NOT_APPLICABLE / 不阻塞。**

**新增**

- Research Intelligence 规则总纲 `references/research-intelligence.md`（设计注册表 Schema、RF-01~10、
  C1~C4×ES1~ES4、issue_type×severity×auto/queue/block 矩阵、白名单与 recompute 受控执行模型、
  Loop 契约、8 维评分规范、Delivery Gate 集成、条款映射表）。
- 三个注册表（`.aeromech/research/`，随 research_integrity.py 引擎）：`design.yaml`（DESIGN-XXX：
  rq_requirements 的 needs/evidence_requirement）、`scope.yaml`（SCOPE-XXX：included/excluded/assumptions）、
  `repairs.yaml`（REP-XXX：diagnosis_id/operation/before/after/payload/rationale/risk/status）。
- `scripts/research_design.py`：设计一致性审计（needs⊆provides → RQ_METHOD_MISMATCH；
  evidence_requirement×实际数据 → DESIGN_EVIDENCE_MISMATCH；方法候选≥2+理由 → METHOD_SELECTION_WEAK）
  + Research Feasibility Gate RF-01~10 → FEASIBLE / CONDITIONALLY_FEASIBLE / INFEASIBLE（rc 0/1/2/3）。
- `scripts/research_diagnosis.py`：统一诊断引擎——合并设计审计/可行性/范围控制/数字一致性/冲突/RQG 结果
  为 DIAG-XXX 条目（severity 归一小写；稳定 ID 含 severity+payload 消歧），19 类 issue_type，
  disposition 三通道（auto=白名单可修 / queue=人工判定（含 CITATION_GAP 派生自 RQG-12）/ block=完整性失败）。
- `scripts/research_repair.py`：Repair Plan Registry + 白名单自动修复执行器——仅 4 操作
  （downgrade_wording 强度降级变换 / number_sync 摘要数字同步 / recompute 受控执行 / fix_synth_label 标签回填），
  全部 before/after 留痕 + 复检（applied→verified/rejected）；`apply-human` 消费 human-review-queue.yaml
  （approve/modify→注册表/文本执行并记 verified REP；reject→rejected_by_human；非文本→deferred，不静默）。
- `scripts/research_agent_loop.py`：PLAN→ANALYZE→DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→VALIDATE→ACCEPT；
  MAX_ITERATIONS=5（1~20 可调）；签名无改善即停；每轮 loop-log 记录 issues_before/repairs/issues_after/
  improvement/remaining + 规则命中/严重度依据/修复选择（仅事实与规则，不含内部推理）；
  终态 BLOCK(rc=1) / PASS_WITH_HUMAN_REVIEW / WARN / PASS_WITH_WARNINGS / PASS；已裁决条目持久保留。
- `scripts/research_quality_score.py`：8 维（Research Design/Evidence/Data/Analysis/Argumentation/
  Conclusion/Citation/Coherence）各 0~100，扣分来自诊断未解决项 + Evidence Coverage 折算；
  未映射类型兜底计入 Coherence（标 UNMAPPED）；Critical/High 未解决 → blocked=True，总分不构成交付依据。
- 集成：SKILL.md §3 加载表 / §4 路由表 / §16 Delivery Gate v1.5 条款 / 新增 §20；
  `references/state.md` §17.1（S3 feasibility 前置、S7/S9 loop 门禁，不改 schema）；
  `references/delivery-pipeline.md` §8.3；`references/research-human-review.md` §6（双队列衔接）。
- `tests/v1_5/`：13 个测试文件（418 断言，PASS/FAIL/boundary/repair 四段式）+ _fixtures（14 缺陷变体）
  + run_all；`tests/v1_5/v1.5-baseline-report.md` / `v1.5-bugfix-log.md` / `v1.5-regression-report.md`。
- **test-7.0 端到端验收**（`Desktop\thesis-test-7.0`）：冷启动完整论文（3 RQ/主辅 3 方法/10 证据/模拟数据集
  /4 计算/4 论断/4 结论/3 图 3 表），植入 7 类缺陷（A 方法不匹配+real 数据声明、B 模拟写实测、C 结论断链越界、
  D 摘要 450 vs 正文 425.4、E scope creep 飞控×3、F 手册300/教材500 冲突、G AN-003 空 inputs）——
  全部被诊断捕获并正确分流：自动修复 REP-001/002（verified，含 before/after）、人工队列 7 项裁决
  （approve/modify/reject 三通道）、BLOCK→解除路径（blockdemo 副本：Critical 未解 → BLOCK score76；
  仅补证据仍 BLOCK；补人工设计决策后解除）；终态 loop PASS、score 100、交付链全 PASS（无模板→tf N/A）、
  污染扫描 0 命中。`thesis-test-7.0-blockdemo/` 为 BLOCK 演示证据副本。

**修复（发布前审计 B1~B10，均有回归锁）**

- B1 Citation 评分维恒 100：RQG-12 派生改产出独立 CITATION_GAP 并计入 Citation 维（v1_5 +3 断言）。
- B2 REDUNDANT_CONTENT 被评分静默丢弃：显式映射 Coherence + 未映射类型兜底（标 UNMAPPED 不丢失）。
- B3 research_repair `--diagnosis-json` 死参数接线（文件缺失=rc 3）；fix_synth_label 补 _verify（4/4 操作可复检）。
- B4 docstring `--quiet-rqg` 改 `--no-rqg`；research-intelligence.md 加条款映射表（§4/§13/§24 等编号可追溯）。
- B5 color_fidelity_qa 头注释 COLOR 范围与实现对齐。
- B6 pdf_qa：环境/配置错误（缺 PDF/缺依赖/参数）退出码改 3（不占用内容码 1/2）；docstring 写明旧 0/1/2 语义。
- B7 recompute shell=True → **受控执行模型**：仅 `python <项目内相对路径>.py`、解释器强制 sys.executable、
  拒绝 shell 元字符/绝对路径/越界/-c 入口、cwd=项目根、180s 超时、失败留痕不伪标 verified（v1_5 +8 断言）。
- B8 RQG-14 不识别文档词表 `computation`（与 `calculation` 同义）→ 等价接受且不降标（v1_4 +2 断言）。
- B9/B9b diagnosis_id 哈希键补 severity+payload（同规则不同严重度/不同越界词可分别裁决，v1_5 +2 断言）。
- B10 agent loop 重建队列丢弃已裁决关闭条目 → rejected/deferred 条目持久保留（人工驳回不再复活）。
- 伴生：diagnosis severity 入口统一小写（RQG 派生 "Critical/High" 不再漏计）；
  QC-01 数字同步基准改为"计算出处优先、相对差最小"（不再取先遇到的近似值）；
  apply_human 未知 decision 从队列消失改为 needs_input 留队可修。

**交付门禁变更**

- Delivery Gate 追加 Research Intelligence 门禁（delivery-pipeline.md §8.3）：design.yaml 存在时
  loop 终态 BLOCK 禁止交付、PASS_WITH_HUMAN_REVIEW 须队列清零后交付、评分随报告输出不作放行依据；
  旧项目 not_initialized 不阻塞。
- sync.py v1.5.0 加固（2026-09-12 事故后）：删除仅限目标树+逐条断言、>10 删除需 --force、
  空源拒绝、--dry-run；四道护栏经负例测试。开发仓初始化 git（v1.4.1 基线 9826193 → v1.5.0）。

**验证汇总**：tests/v1_4 11/11 + v1_4_1 5/5 + v1_5 13/13（418 断言）+ test_a/b 全绿；
t30~t60 交付链逐项与 v1.4.1 基线一致（tf 20/20/15+5N/A/15+5N/A，pdf_qa/visual/cover/gq/ft 全 PASS）；
test-7.0 端到端 PASS；dev↔install IDENTICAL。

## v1.4.1 — Stability & Production Hardening

**目标：不新增大型功能，将 v1.4.0 的 Research Integrity / QA 能力产品化、稳定化。**

**新增**

- `references/research-human-review.md`：研究语义人工复核规程（七维复核清单：
  结论证据支持/工程判断边界/模拟身份/方法与问题匹配/摘要准确/数字可信/文献支持；
  NHR 队列机制与 human-review.yaml 裁决格式）。
- `tests/v1_4_1/`（5 个测试文件 + run_all）：
  `test_not_applicable_qa` / `test_human_review` / `test_gate_state` / `test_dev_install_sync` / `test_false_pass_prevention`。
- 开发/安装目录规程：`Desktop\thesis-skill\aeromech-thesis`（权威开发源）+
  `sync.py`（--check / --to-install / --to-dev，镜像语义；逐字节比较）
  + `DEV_SYNC.md` / `INSTALL_SYNC.md`。

**状态模型（v1.4.1）**

- 统一状态词表：`PASS / WARN / FAIL / NEEDS_HUMAN_REVIEW / NOT_APPLICABLE / SKIPPED_WITH_REASON / ERROR`；
  FAIL 输出携带 severity + reason + remediation；退出码：0=PASS/PASS_WITH_HUMAN_REVIEW、1=FAIL、
  2=not_initialized（旧项目兼容）、3=ERROR。
- RQG-09/RQG-10（Critical 级语义项）：弱证据（全 simulated/pending）语境下未命中强断言模式时
  **不得自动 PASS** → `NEEDS_HUMAN_REVIEW` + `human-review-checklist.md`
  （claim/evidence/reason/uncertainty）+ Gate `PASS_WITH_HUMAN_REVIEW`；
  `human-review.yaml` 裁决（ok→PASS；violation→FAIL Critical；未裁决保持 NHR）。
- tf_qa：`--template` 可省略（或 none）→ 模板对照项（TF-01~04、TF-19）记 `NOT_APPLICABLE`（附 reason），
  自含检查照常执行，退出码 0；`--template` 指向不存在文件 = 配置错误（退出码 3，不静默降级）。
- research_integrity：注册表损坏 → `RI-CORRUPT`（critical + remediation，validate rc 1；
  trace/coverage rc 3）；全部问题项补齐 reason/remediation 字段。

**修复**

- `tf_qa` TF-13：无页眉时消息 f-string 提前求值导致 TypeError 崩溃（hdr=None）→ 延迟构造消息
  （由 test_false_pass_prevention 捕获）。
- `sync.py`：`filecmp` 缓存（键不含 mtime）导致同尺寸文件覆盖后仍报差异 → 改逐字节比较
  （由 test_dev_install_sync 负例捕获）。
- `research_quality_qa`：人工复核清单字段改双语标注（claim/evidence/reason/uncertainty 可直接检索）。

## v1.4.0 — Research Integrity & Evidence Traceability

**新增（研究完整性层，不破坏既有能力）**

- `references/research-integrity.md`：研究完整性规则总纲（架构分层、10 类注册表 Schema、ID 规则、
  RQG-01~15 定义表、Evidence Coverage 公式、材料优先级、冲突处理、通用性纪律）。
- `scripts/research_integrity.py`：注册表引擎（init/validate/trace/coverage，退出码 0/1/2）。
  - 结构校验：ID 唯一/格式、必填字段、悬空引用、`RI-E-DISGUISE`（simulation/assumption 证据伪装 verified → Critical）、
    模拟数据集 label 强制（`RI-DS-LABEL` → Critical）。
  - Research Traceability Graph：RQ→Method→Evidence/Data→Analysis→Figure/Table→Claim→Conclusion 边的构建与
    orphans（无链路核心论断/结论）检测，输出 `traceability.json`。
  - Evidence Coverage Ratio：核心 Claim 覆盖率 + verified/partial/pending/simulated 四分类
    （simulated 单列，不并入 verified）。
- `scripts/research_quality_qa.py`：Research Quality Gate 检查器（RQG-00 注册表校验 + RQG-01~15），
  Evidence Coverage 汇总、摘要↔正文一致性（数值域/身份措辞/结论覆盖，否定语境豁免）、
  证据越界检测（强断言口径 × 全模拟/未核实证据 → Critical）、正文数字可追溯率（≥50%）、
  图表论证链接统计（可选 PDF 题注数交叉核对）。退出码 0=PASS / 1=Critical/High FAIL / 2=未初始化（旧项目兼容，不阻塞）。
- `tests/v1_4/`：11 个专项测试文件（PASS/FAIL/boundary，共 162 项断言）+ `_fixtures.py`（含 26 种变异）
  + `run_all.py`；覆盖 RQ/Evidence/Claim/Traceability/SyntheticData/Computation/Conclusion/Abstract/Coverage/Gate/Conflict。
- SKILL.md §19 + 路由/加载/交付门禁集成；`references/state.md` §17 阶段职责（S3 起注册，
  S9 前 RQG 全量；`writing.gate_evidence` 升级前不得有 Critical/High）。

**修复**

- `research_integrity._require`：空列表/空字典此前不被视为"缺失字段"（`inputs: []` 可通过校验）；
  现按缺失处理（由 tests/v1_4/test_computation_provenance.py 捕获）。
- `research_quality_qa` RQG-09：数值不一致（High）曾被覆盖度软检查降级为 Medium 致 Gate 误放行；
  现仅当无硬问题时才降级。
- `research_quality_qa` numbers_of：英文单位正则过度捕获（"213 flight" → "213fligh"）；改英文单位白名单 + 词边界。
- `figure_table_qa` TAB-06：实现提示语承诺的"等级列合法单字豁免"（等级/级别/风险组/组别/评分/评级列）。
- `figure_table_qa` FIG-12：正文图引用匹配改为分隔符/空白归一化（图1-1 ≡ 图1.1 ≡ 图 1-1），消除全图"缺引用"误报。
- `page_fidelity_qa` AT-03/AT-04：无附录数据表时与 AT-02/AT-05 一致 SKIP（原为空集误 FAIL）。
- `table_readability_qa` TR-10：英文题注定位兼容 Tab.2.1 / Tab. 2-1 / Tab2-1 分隔符风格（原仅认点号无空格）。
- `cover_fidelity` 自检 CF-05：去除题名关键词硬编码（原绑定 test-5.0 题目短语），改为封面最长文本行题名候选判定。
- 封面下划线槽：新增 `w:ulTrailSpace` 兼容设置说明（`docx_engine`/项目组装器层面），确保"学号/密级"空格槽下划线在 Word 渲染中被绘制。

**交付门禁变更**

- Delivery Gate 增加 RI Gate：项目存在 `.aeromech/research/` 时，RQG Critical/High 阻止交付；
  注册表缺失的旧项目记 `not_initialized`，不阻塞（回归兼容）。

## v1.3.11

- Legacy `.doc` 学校材料处理：`detect_legacy_docs` / `convert_legacy_doc`（Word COM 转换，见 `references/template-fidelity.md` §11）。
- QA 通用化修复批次：`guard_table_gap` 过滤 body 级 sectPr（修复相邻表合并守卫失效）；
  `tf_qa` / `page_fidelity_qa` / `figure_table_qa` / `content_purity_qa` / `graph_quality_qa` 泛化（去除硬编码）；
  cover 系列（cover_align/cover_fill/cover_fidelity/color_fidelity）支持无母版自检模式。
- 新增 `scripts/finalize_metadata.py`（交付前 DOCX/PDF 元数据中性化）。

## v1.3.0 ~ v1.3.10

- v1.3.0 Cover Fidelity（COVER_FIDELITY_MODE / COVER_IMMUTABLE_REGION / CF-01~25）。
- v1.3.1 页级保真（page_fidelity_qa：HF/AF/AT/RF）。
- v1.3.2 图表版式与内容净化（figure_table_qa FIG/TAB、content_purity_qa MD/INT/PRM/APX）。
- v1.3.3 图形拓扑质量（graph_quality_qa GQ-01~15 + figkit.py layout 几何元数据）。
- v1.3.4~v1.3.5 TABLE_START_BLOCK；v1.3.6~v1.3.7 横向宽表独立节（TABLE_LANDSCAPE_SECTION）。
- v1.3.7~v1.3.8 封面字段填写保真（COVER-FILL-ALIGN + COVER_FILL_CENTERING）。
- v1.3.9~v1.3.10 封面颜色保真（COLOR Fidelity COLOR-01~16；效果链语义 > 学校要求 > 默认）。

## v1.2.0

- Cover Fidelity 引入（封面对象树保真、零删除/零压缩、图片继承、fill-on-rule 横线保留）。

## v1.1.0

- Template Fidelity 双模式（TEMPLATE_FIDELITY / FORMAT_RECONSTRUCTION）、模板母版驱动、
  页码防重启/表格分隔/题注跨空行纪律、tf_qa.py（TF-01~20）、Test A/B。

## v1.0.x

- Delivery stabilization：`docx_engine.py`、`update_toc.py`、`export_pdf.py`、`pdf_qa.py`、`visual_regression.py`、
  Delivery Gate 分级、PDF 为最终真值原则（真实 39 页论文 PDF 验证）。
