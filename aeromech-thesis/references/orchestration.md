# Full-Stack Orchestration（v1.6.0·编排层规则总纲）

> 定位：把 v1.0~v1.5 的既有能力串成**完整、可恢复、可交付**的毕业论文 Agent。本层只负责
> routing / state / coordination / checkpoint / recovery；研究判断（注册表/RQG/诊断/修复/Loop/评分）
> 与格式/文档（Template Fidelity/QA 链/母版原语）一律复用既有模块，编排层零业务逻辑复制。
> **规则真源 = 脚本实际行为**；本文与 `tests/v1_6/test_document_contract.py` 互为约束（文档写 A
> 而代码是 B → 测试 FAIL）。适用对象：`.aeromech/` 工作区内的论文项目。
> 状态：v1.6.0 已发布（2026-09-17，经 test-8.0 全栈冷启动 + 全回归 + 全 QA + 7/7 人工复核，delivery_gate=PASS）
> 待 test-8.0 + 全回归 + 全 QA 全 PASS 后升级。

## 1. 分层与模块地图

```
用户材料 ──► material_ingestion.py（登记/去重） ──► school_requirements.py（School Requirement Context）
                                    │
state.yaml ◄─► thesis_state.py（StateIO + Checkpoint + resume 视图）
研究注册表 ◄─► research_integrity.py / 研究上下文 = research_context.py（只读聚合，不重定义）
调度判定   ◄─► stage_routing.py（矩阵+门禁+交付五态，只判定不执行）
执行编排   ◄─► thesis_orchestrator.py（step/drive/resume/run-loop/apply-human/gate/actions）
文档构建   ◄─► thesis_build.py（build-contract → DOCX → pipeline → artifact-manifest）
图形接口   ◄─► figure_iface.py（FigureProvider 契约 + 生命周期，不复制 Figure Engine）
最终门禁   ◄─► delivery_gate.py（格式链+研究侧+图+文档+人工队列聚合 → 五态终局）
```

## 2. 主循环

```
LOAD STATE → LOAD CONTEXT → ROUTE → CHECK PREREQUISITES → EXECUTE → SAVE ARTIFACT
→ CHECKPOINT → VALIDATE → NEXT
失败：DETECT → DIAGNOSE → RECOVERY(auto-repair/rollback 等) → VALIDATE
NEEDS_HUMAN_REVIEW → human-review-queue.yaml（复用 v1.4.1/v1.5 双队列，不新建第三套）
CRITICAL → BLOCK（编排层停止，不得 retry 掩盖）
```

- `ROUTE` 判定全部来自 `stage_routing.route()`；编排层**不自行判断 S1-S10**、不自造迁移边。
- `EXECUTE` 仅两态含义：执行"路由已允许的"既有工具（见 §6）；阶段迁移只经 `thesis_state.transition`。
- 出口产物缺失（章节未写、注册未登记）→ `NEEDS_UPSTREAM_WORK`：补齐属 Agent/写作层职责，
  **编排不代做研究、不硬推进、不代写内容**。
- `drive` 有步数上限（默认 25，`--max-steps` 可调）——编排层防无限循环；阶段内轮次保护归 v1.5 loop。

## 3. StateIO（`thesis_state.py`）

- state.md §1~§15 全部规则的**程序化执行体**：允许边/回退/返程/门禁三态/open_issue 词表/备份
  （`.bak-<tag>-<ts>` 保留 5 份）。非法迁移**拒绝且不落盘**（history 只记实际迁移）；override 必须
  `--override-note`（确认记录）并自动挂 open_issue；revert 必须有触发源（reason/issue_id）。
- schema 兼容：支持 `schema_version` ∈ {1.0, 1.1}（1.1 仅新增附加键，无强制）；高版本 → 拒绝读取
  （只读保护）；未知字段原样保留；损坏 → 现场留档 `bak-corrupt` + 回退最近**可解析**备份。
- 附加键 `checkpoint: {last_id, file, ts}` 为 v1.6 additive（旧读取方忽略不报错）；**论文正文永不写入 state**。
- CLI：`init | status | validate | transition <TO> [--type --reason --evidence --issue --override-note] |
  issue <add|close> | checkpoint | latest | resume`；退出码 0 合法 / 1 拒绝或校验问题 / 2 无 .aeromech / 3 ERROR。

## 4. Checkpoint（`.aeromech/checkpoints/CK-XXX.yaml`）

字段（指令 §六最小集全实现）：

```
checkpoint_id · stage · task · ts · cursor(k/v) · artifacts{path: {exists, sha256}}
· registries（复用注册表引擎快照：present/count + _corrupt 清单）· qa_state{name: {status, report}}
· next_action · open_issues
```

写入时点（每个重要 Action 之后）：阶段完成 `stage:S?→S?`；AI 证据 `ai:<mount>`；Agent Loop 完成
`agent-loop`；**失败恢复之前** `recovery-before-repair|rollback:<issue>`。单文件损坏不拖垮
resume 视图（跳过并如实报告）。

## 5. Resume 与 Drift（中断恢复）

`thesis_orchestrator.py <root> resume` → 输出 `{status, stage, checkpoint, next(route 完整判定),
artifacts_ok, qa_state, cursor, next_action, from_start: false}`。**`from_start` 恒 false——禁止从
S1 重启**；恢复依据 = state.yaml + checkpoints/ + research/ + artifacts/ + QA 状态。

Resume/Step 前置漂移检查（`drift_checks()`，发现差异**绝不静默覆盖**）：

| code | 触发条件 | 处置 |
|---|---|---|
| `STATE_DRIFT` | checkpoint.stage ≠ state.stage | NEEDS_HUMAN_REVIEW（人工确认差异） |
| `REGISTRY_DRIFT` | 注册表推断阶段超前 state.stage **≥2**（相邻半拍如 S5↔S6 双向工作属 state.md §3 合法重叠；提前注册 claims/conclusions/figures 这类写作期产物则触发） | NEEDS_HUMAN_REVIEW（不得静默改 state） |
| `ARTIFACT_MISSING` | checkpoint 登记产物丢失 | ERROR（rc3） |
| `ARTIFACT_CHANGED` | 产物 sha256 与登记不符（构建/检查点后被改动） | NEEDS_HUMAN_REVIEW（不得默默继续） |
| `STATE_INVALID` | state 词表校验违规 | ERROR |

注册表→阶段推断（drift 判定数据，非业务逻辑）：rq/methods/design/scope/repairs→S3，
evidence/conflicts→S4，analyses→S5，datasets/computations→S6，claims/conclusions→S7，figures→S8。
已完成且 hash 未变的产物**不重做**；需重跑 = 失败阶段 + 其下游受影响 QA。

## 6. Action Model（禁止静默执行）

每个动作追加一条记录到 `artifacts/analysis/orchestrator-actions.jsonl`：
`{action_id: ACT-XXXX, stage, reason, input, output, status, timestamp}`（`actions --last N` 可查）。

| action | 含义 |
|---|---|
| `RUN_PENDING` | route 返回 SKIPPED_WITH_REASON → 执行该挂载点对应既有工具（每步一个，保持粒度） |
| `ADVANCE` | 出口齐+门禁过 → thesis_state.transition(forward) + checkpoint |
| `ADVANCE_REJECTED` | transition 被 StateIO 拒绝（非法边/缺前置/缺确认记录），不落盘 |
| `NEEDS_UPSTREAM_WORK` | 出口产物缺失（属 Agent 职责的写作/登记），rc=1 停止推进 |
| `RETRY` / `RETRY_EXHAUSTED` | pending 工具瞬时失败重试（上限 1）；二次仍失败→停止交人工，不无限 retry |
| `REPAIR` | auto 类 finding → 白名单修复（research_repair.plan/execute，全留痕）+ 重诊断 |
| `ROLLBACK` | 设计类 finding → checkpoint(失败恢复之前) → 挂 open_issue → revert（经 StateIO） |
| `HUMAN_REVIEW` | queue/冲突类 → 指向 human-review-queue.yaml；编排不消费不代签 |
| `BLOCK` | Critical/High 完整性未解决 → 停，不改阶段不伪修复 |
| `FINALIZE` / `STATE_DRIFT` / `ERROR` | 交付门禁放行披露 / drift 硬错 / 环境异常 |

step/resume/drive 退出码：0=动作成功；1=流程受阻（BLOCK/待人工/上游缺料/迁移拒绝）；2=无 .aeromech；3=ERROR。

## 7. Route 与阶段调度矩阵（stage_routing.py，数据化）

`python stage_routing.py <root> route|matrix|gate`。**矩阵即配置**：每阶段 {name, exit[{id,desc,probe}],
ai[{id,tool,gate,evidence}], forward[{to,prereq,types,revert}]}，`matrix` 子命令可导出 JSON。

Research Intelligence 挂载点（指令 §十一对照）：

| 阶段 | 挂载点 | 执行器（复用） |
|---|---|---|
| S1 | feasibility（题目级，design 未建→N/A） | research_diagnosis.diagnose+save |
| S3 | feasibility（设计/方法选择） | 同上（证据= research-diagnosis.json） |
| S4 | coverage（证据覆盖） | research_quality_qa.run |
| S5 | diagnosis（首轮诊断） | research_diagnosis |
| S6 | data_integrity（数据/计算完整性） | research_diagnosis |
| S7 | agent_loop（论断/摘要一致性闭环） | research_agent_loop.run_loop（含 RQG 报告落盘） |
| S8 | figure_traceability（图表论证链接） | research_integrity.save_traceability + diagnosis |
| S9 | full_qa（交付前终检） | research_quality_qa + research_agent_loop |

S2 无挂载点（选题阶段语义判断归 Agent）。**前进纪律**：出口产物齐 + 本阶段 AI 证据在位才 advance；
证据缺 → `SKIPPED_WITH_REASON`（编排必须先 run_pending，不得跳过、不得猜）。S1~S6 阶段 RQG/loop 的
FAIL 不作为阶段阻塞（提前评估）；设计可行性（INFEASIBLE）**全阶段硬把关**（§十三）。
回退目标映射：`CATEGORY_TARGET`（state.md §8）+ `ISSUE_TYPE_TARGET`（v1.5 19 类 issue_type；
未知类型回落类别映射不崩溃）。

## 8. Failure Recovery 五策略

`classify_recovery(findings, state)` 由 **issue_type + severity + disposition（v1.5 权威通道）+
routing 阶段映射 + 当前 state** 共同决定，输出按 `block > rollback > human_review > repair > retry`
排序取最重执行：

| 场景（指令 §九） | 策略 | 执行 |
|---|---|---|
| 计算/工具瞬时失败 | **RETRY** | 同 pending 重跑一次；上限 1，超限 `RETRY_EXHAUSTED` 停止 |
| 普通输出错误（disposition=auto：论断降级/数字同步/受控 recompute/模拟标签） | **REPAIR** | recovery-before checkpoint → research_repair plan+execute（白名单、before/after 留痕）→ 重诊断 |
| 证据冲突/人工判定类（disposition=queue、UNRESOLVED_CONFLICT） | **HUMAN_REVIEW** | 队列等待裁决；`apply-human` 委托 research_repair.apply_human；不代签、reject 持久不复活 |
| 研究设计不可行/方法不匹配/范围（FEASIBILITY_BLOCK、RQ_METHOD_MISMATCH、SCOPE_*…） | **ROLLBACK** | checkpoint → 挂 open_issue（category 映射）→ transition(revert)；若已在目标阶段→设计修复仅限人工决策（REFRAME/LIMIT/ADD） |
| Critical 完整性（disposition=block ∧ critical/high，如证据伪装 RI-E-DISGUISE） | **BLOCK** | 停止；不改阶段、不产 PASS、**评分/总分绝不参与放行** |

纪律：Critical 不得用 retry 掩盖；rollback 必须过 StateIO（非法边照拒）；恢复动作本身全部写 Action 日志。

## 9. Agent Loop 集成

编排调用既有 `research_agent_loop.run_loop`（**不重写 loop**）：DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→
VALIDATE→ACCEPT，`MAX_ITERATIONS=5`（沿用 v1.5 旋钮，可调 1~20）；每轮 loop-log 记录
issues_before/repairs/issues_after/improvement + 规则命中（无改善即停，防死循环）。终态消费：
PASS/PASS_WITH_WARNINGS→放行+checkpoint；PASS_WITH_HUMAN_REVIEW→队列 NHR 门禁；BLOCK→§8 恢复。
超限/无改善的停止由 loop 自身 `stopped_reason` 记录；编排另有 `drive --max-steps` 外层保护。

## 10. Figure Interface（figure_iface.py，契约与适配层）

**主线只定义契约，不复制 Figure Engine**；第三方/协作者 Provider = 实现 `FigureProvider`
三方法 + 注册进 `PROVIDERS`（`--provider <name>` 切换）。模块级入口即指令约定的接口：
`plan_figures(root, provider, specs)` / `generate_figure(root, figure_id, provider)` /
`validate_figure(root, figure_id, provider)`。

- 输入 FigureSpec：figure_id/name/kind/source/out + related_rqs/related_analyses/related_claims/data_source；
  输出 FigureResult：`{figure_id, status, artifact, sha256, quality[], reason, provider, timestamp}`。
- 生命周期（每步落 `.aeromech/figures/figure-lifecycle.yaml`）：

```
PLANNED → GENERATED → VALIDATED → EMBEDDED → VERIFIED      （成功链）
REJECTED / NEEDS_HUMAN_REVIEW                                （失败分支）
```

  EMBEDDED 由统一构建在**章节占位行真实命中且图文件在场**时记录（不伪造）；VERIFIED 由
  build 链 QA（GQ/FIG 渲染级）判定后 record 显式写入。
- 研究可追溯硬规则：validate 首先检查图关联 RQ/Analysis/Claim（读 v1.4 figures.yaml，只引用），
  无链接 → NEEDS_HUMAN_REVIEW——**不允许生成一张图但不知它服务于哪个研究节点**。
- 默认 LocalProvider 复用既有件：mermaid→render_mermaid（FIGURE_ERROR→REJECTED，不落占位图）；
  script→受控执行（同 v1.5 recompute 信任边界：仅 `sys.executable` + 项目根内相对 .py，无 shell、
  180s 超时）；validate→graph_quality_qa.check_graphs 单图几何（无 figkit layout 证据→NHR，
  由 PDF 级 QA 在 VERIFIED 兜底）。
- 生命周期只管图像产物（FIG-*）；figures.yaml 中的 TABLE-* 表条目不参与（无图像可生成，
  不记 NHR 以免污染 G-FIG-01 域）。
- 计划机读件 `.aeromech/figures/figure-plan.yaml`；`status` 子命令供 Gate 消费。
  退出码 0=正常 / 1=REJECTED 或 NHR / 2=无计划 / 3=ERROR。

## 11. Unified Thesis Build（thesis_build.py）

项目不再手写 builder：`python thesis_build.py <root> validate|build|pipeline|manifest`。

**Build Contract** `.aeromech/build-contract.yaml`：

```yaml
project: {title, author, major, school}          # title 必填（缺→ERROR，不占位）
content: {abstract_zh|abstract_zh_file, keywords, abstract_en|abstract_en_file, keywords_en,
          chapters: [相对 .aeromech 路径], references_file, appendices: [{title, file}],
          ack_text|ack_file}                     # chapters 必填非空；文件缺失/空=ERROR
research: {required: false}                      # 注册表在场性由引擎判定（缺席=N/A 不伪造）
school_format: {template, template_pdf, cover_tables: [0,1],      # 缺→FORMAT_RECONSTRUCTION
                 cover_fields: {封面标签: project.<k>|content.<k>|字面量},
                 cover_text_fills: {占位文本: 取值}}   # template_pdf=封面参考页 PDF；
                                                 # cover_tables=保留母版封面区表索引（其余节剪除）；
                                                 # cover_fields/cover_text_fills 通用封面填充（v1.6）
figures: [{figure_id, display, file, caption_cn, caption_en}]   # display 归一；图英文题注进图块（双语）
tables: [{display, caption_en}] | {captions: [...]}  # 表体由章节 md 的"表题行+管道行"经
                                                 # parse_md 渲染（v1.6 接通：本字段只提供
                                                 # 英文题注，图 QA 双语题注需要它）
output: {docx: 毕业论文.docx, pdf: 毕业论文.pdf}
qa: {out: artifacts/qa, tables_min: 5}          # tables_min=figure_table 表数下限（默认 15）
```

缺失语义：**required 缺→ERROR（列出全部缺项）；optional 缺→NOT_APPLICABLE 如实披露；
任何静默补假数据禁止**。旧项目无契约 → 全链 `NOT_APPLICABLE`（各自 builder 交付不受影响）。

流水线（顺序即 `ALL_STEPS`，全部调既有脚本，不重复实现）：

```
docx → toc → repaginate → pdf → finalize → qa
```

qa 段含 pdf_qa/visual_regression/tf_qa/cover_fidelity/content_purity（有图目录时加
figure_table/graph_quality）。任一步失败 → 输出 **{failed_stage, error_code, reason, suggested_action}**
且下游步骤记 SKIPPED_WITH_REASON——**不得继续假装交付成功**。Word COM 步骤环境失败记 ERROR（非内容结论）。

**Artifact Manifest** `.aeromech/artifacts/build/artifact-manifest.yaml`：每产物
{artifact, path, sha256, content_identity, producer, timestamp, status} + meta.steps（各步 rc）。
与 Phase 3 checkpoint 同构（sha256 一致性校验、missing/changed 报告）。

**可重复性**：`content_identity`（排除 docProps/*.rels 的 zip 条目归并哈希）与容器 sha256 分离——
同输入重复构建 content_identity 一致；时间戳等容器元数据差异**不算内容漂移**；PDF 侧
`pdf_text_identity`（逐页文本+图像字节）。

## 12. Delivery Gate 聚合（delivery_gate.py）

最终统一门禁：`python delivery_gate.py <root> [--json] [--write]`（编排 `gate` 子命令即此，
并写 `artifacts/qa/gate-summary.json` + `gate-report.md`）。消费域：

- **格式 QA**：tf/cover/cover_align/cover_fill/color/page/figure_table/graph/table/content_purity 的 md 报告；
- **pipeline 步骤**：pdf_qa/visual_regression/toc/repaginate/pdf_export/finalize（取自 manifest meta.steps）；
- **Document/PDF**：交付物存在性 + manifest sha256 一致性（漂移/丢失=critical FAIL；旧项目无契约=文档域 N/A）；
- **Figure**：生命周期聚合（REJECTED=critical；待裁决=NHR；无计划=N/A）；
- **Research QA / Evidence / Data**：复用 stage_routing 聚合（不重算 RQG/loop）；
- **Human Review**：双队列未裁决计数。

每项记录 `{gate_id, domain, status, severity, evidence(项目根相对路径), reason, remediation}`。

**聚合规则**：ERROR > Critical/High FAIL(BLOCK) > NEEDS_HUMAN_REVIEW > WARN > PASS。
终局五态 `PASS / PASS_WITH_WARNINGS / PASS_WITH_HUMAN_REVIEW / BLOCK / ERROR`：
Critical/High 未解决→BLOCK；任一 ERROR→ERROR（绝不透 PASS）；人工队列/PHR→PASS_WITH_HUMAN_REVIEW
（交付前必须清零）；仅 WARN/medium→PASS_WITH_WARNINGS（披露放行）；全项 N/A/无决定性证据→BLOCK
（未执行≠通过）。**Research Quality Score 总分不参与放行判定**（总分不得掩盖 Critical）。
无模板 → 模板对照项由 tf_qa 自身输出 NOT_APPLICABLE（不伪造 PASS、不 BLOCK、不强制 N/A）。
退出码：0=三种 PASS 态；1=BLOCK；3=ERROR。

## 13. 状态词表（统一，不造新状态）

- **item 级（v1.4.1 七态，所有 QA/注册表/门禁输出沿用）**：
  `PASS / WARN / FAIL / NEEDS_HUMAN_REVIEW / NOT_APPLICABLE / SKIPPED_WITH_REASON / ERROR`
- **gate 级终局（五态，仅 Delivery Gate / loop 终态 / 编排 gate 用）**：
  `PASS / PASS_WITH_WARNINGS / PASS_WITH_HUMAN_REVIEW / BLOCK / ERROR`——**BLOCK 只出现在 gate 级**。
- Figure 生命周期状态（`PLANNED / GENERATED / VALIDATED / EMBEDDED / VERIFIED / REJECTED / NEEDS_HUMAN_REVIEW`）
  是工件生命周期而非 QA 结果，两套词表不混用。
- Research Context 视图可用态：`OK / NOT_APPLICABLE / ERROR`（上下文可用性，非 QA 结论）。
- 退出码惯例：0=成功/可放行；1=内容性 FAIL/受阻（判定本身成功）；2=环境/未初始化（N/A 族）；3=ERROR。

## 14. 通用性纪律

1. 矩阵、映射、执行器全部数据化/注册表化——**不得为任何题目/学校/测试项目写特例分支**；
2. 编排层不得 import 业务逻辑重实现（注册表读写、RQG 判定、loop 轮次、修复白名单一律复用原模块）；
3. 不得删除/覆盖已有 artifact 与 state（恢复动作前必 checkpoint；拒绝即不落盘）；
4. 不得把"没跑过"当"通过"：缺证据=SKIPPED_WITH_REASON（编排补跑）或 BLOCK（交付门禁）；
5. 文档=代码=测试：本文所述任何字段/状态/路径若与脚本行为不一致，`tests/v1_6/test_document_contract.py` 必须 FAIL；
6. 协作者 Figure Engine 仅经 §10 契约接入；其分支合入前主线以 LocalProvider/mock 自足。

## 15. CLI 速查

```bash
python scripts/thesis_state.py <root> init|status|validate|transition|issue|checkpoint|latest|resume
python scripts/material_ingestion.py <root> scan|register|check
python scripts/school_requirements.py <root> parse|show
python scripts/research_context.py <root> [--json] [--refresh-trace]
python scripts/stage_routing.py <root> route|matrix|gate
python scripts/thesis_orchestrator.py <root> status|step|drive [--until S9] [--max-steps 25]
    |resume|run-loop|apply-human|gate|actions
python scripts/figure_iface.py <root> plan|generate|generate-all|validate|status|record [--provider local]
python scripts/thesis_build.py <root> validate|build|pipeline [--steps docx,toc,repaginate,pdf,finalize,qa]|manifest
python scripts/delivery_gate.py <root> [--json] [--write]
```
