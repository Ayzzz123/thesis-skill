# TEST_PLAN（08）

四个新测试文件（tests/v1_6_5/，并入 run_all.py），全部真实行为断言；
**假 Key 约定**：`sk-TEST-<32位>` 前缀，任何真实格式 Key 禁止出现在测试与仓库。
**离线默认**：HTTP 全部 mock（monkeypatch backend 的 `_http`），永不外呼。
**HOME 隔离**：每个测试 `tempfile.mkdtemp()` 造 HOME + `monkeypatch USERPROFILE/HOME`，
测后即删（证明用户隔离用两个 HOME 各放一把假 Key）。

## test_image_provider_config.py（解析器本体）

| 号 | 断言 |
|---|---|
| CFG-01 | 无任何配置：resolve_backend() 抛 NotConfigured（不猜默认后端/Key） |
| CFG-02 | 进程 env 设 IMAGE_BACKEND+OPENAI_API_KEY → resolve 成功，source=process |
| CFG-03 | 用户级 ~/.aeromech/.env（tempfile HOME）→ 命中，source=user |
| CFG-04 | 项目级 .env 默认禁用：存在也不读；IMAGE_ALLOW_PROJECT_ENV=1 才读且打警告 |
| CFG-05 | Skill 目录 .env 优先于用户级（搜索序正确） |
| CFG-06 | **只读第一个命中的 .env**：skill 有 BACKEND 无 KEY、user 有 KEY → NotConfigured（不跨文件拼） |
| CFG-07 | 语法：引号值/export 前缀/注释/空行/`$(cmd)` 字面量不执行；malformed 计数 |
| CFG-08 | provider-specific 不互借：backend=gemini 时 OPENAI_API_KEY 不算数 |
| CFG-09 | model 默认建议值存在（非敏感）；base_url 无默认（除官方常量） |
| CFG-10 | 诊断输出：image test 文本含 configured/***REDACTED***，**不含**任何 Key 子串（断言假 Key 的任意 6 字滑窗都不出现在 stdout） |

## test_image_provider_resolution.py（优先级+隔离+错误分类）

| 号 | 断言 |
|---|---|
| RES-01 | 进程 env 覆盖 .env（同名键，进程赢） |
| RES-02 | 键级独立：进程设 BACKEND、文件设 KEY → 合法组合（这是设计允许的最小级联） |
| RES-03 | 两"用户"（HOME_A/HOME_B）各一把假 Key → 各自 resolve 只见自己的（§十三 机器隔离证明） |
| RES-04 | 仓库扫描：git ls-files 中无 `.env`、无 `sk-` 值（SEC 联动） |
| RES-05 | 九类错误各自映射正确（401→INVALID_CREDENTIAL…），**不塌缩**成 GENERATION_FAILED |
| RES-06 | retryable 标记：NETWORK/TIMEOUT/5xx/429 可重试≤3；401/404/内容审核 不可 |
| RES-07 | 成本闸：同 figure_id 第 4 次外部调用请求→NHR（lifecycle attempts 持久，跨进程） |
| RES-08 | 首次外呼前费用提示恰好打一次（第二次调用不再打） |
| RES-09 | host_native：deferred→NHR；回填→GENERATED（07 文档 HN-01~04 在此落地） |
| RES-10 | user_asset：项目内素材登记成功；越界路径/非图片→拒绝 |

## test_image_provider_security.py（脱敏+泄漏扫描）

| 号 | 断言 |
|---|---|
| SEC-01 | redact() 全模式：Authorization/Bearer/sk-/AIza/key=查询串/JWT → 全 ***REDACTED***；普通文本不误伤（"Bearing 轴承"不被改） |
| SEC-02 | ImageError 源头脱敏：异常对象 str() 不含注入的假 Key（即使 message 里拼了 Key） |
| SEC-03 | record() 边界：reason 传入含 Key 文本 → 落盘 yaml 无 Key（双保险验证） |
| SEC-04 | log_action() 边界：input/output 含 Key → jsonl 无 Key |
| SEC-05 | Gemini URL 查询串脱敏：`?key=<假Key>` 出现在异常/日志均被洗 |
| SEC-06 | secret_leak_qa --scope diff：staged 假 Key 文件→BLOCK；`sk-TEST-` 仅 tests/ 豁免（项目内同样 BLOCK，防白名单滥用） |
| SEC-07 | secret_leak_qa --scope deliverables：构造含 Key 的 lifecycle/报告/图文件名→BLOCK；清洗后→PASS |
| SEC-08 | provenance 白名单：provider_meta 塞 api_key 字段→record 丢弃+告警（05 文档 §5） |
| SEC-09 | 高熵启发：随机 40 字符 base64ish→WARN；正常中文文本/UUID 列表→不误报 |
| SEC-10 | .gitignore 断言：含 .env/.env.*/!.env.example/*.secret/credentials.*/user-config.* |

## test_image_provider_integration.py（与既有系统共存）

| 号 | 断言 |
|---|---|
| INT-01 | 注册 image 后 `get_provider("local")` 全功能不变（跑通现有 figkit 图端到端） |
| INT-02 | 路由表：fault_tree/stat_bar 默认 local；spec.provider=image 才走外部（06 文档 §1） |
| INT-03 | 无 Key 环境跑既有 test-8.0 图全流程：结果与加 image 前逐字节一致（§七 零影响证明） |
| INT-04 | AI 图生命周期：GENERATED(provider_meta)→VALIDATED→VIS 链→gate G-FIG-01 正常 |
| INT-05 | VIS-13：数据/逻辑类图 type 配 ai_image 方法→FAIL critical；题注缺【AI 生成示意图】→FAIL |
| INT-06 | 研究完整性：evidence source_type=ai_generated_visual 强制 simulated 待遇；RI-E-DISGUISE 抓"AI 图称实测"；RQG-16 抓"claim 仅由 AI 图支撑"→NHR |
| INT-07 | gate 新域 G-SEC-01 接入：secret_leak_qa FAIL→终局 BLOCK；无 AI 图项目=NOT_APPLICABLE 不误伤 |
| INT-08 | 全量回归：v1_4/v1_4_1/v1_5/v1_6/v1_6_5 既有断言零修改零失败（§六 不破坏承诺） |

## 完成定义

4 文件全绿 + run_all 汇总 + 上述 INT-03/INT-08 是"不破坏既有"的硬证明。
实现顺序：config→resolution→security→integration（与依赖同序）。
