# State Manager（ppt-direct 状态机）

`.pptdirect/state.yaml` 是 PPT 项目的状态机真源，实现为 `scripts/state_util.py`。本文件定义字段、允许边、门禁与操作纪律。设计对齐 aeromech-thesis `references/state.md`，阶段语义换为答辩 PPT 生产流程。

## 1. Schema v1.0

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | `"1.0"`；高于 Skill 支持版本 → 只读 |
| `project.title / presenter / major / school / advisor / date` | string | 封面与扉页字段 |
| `project.page_tier` | enum | `short` / `standard` / `long`（10/15/20 页档） |
| `project.duration_min` | int | 答辩时长（分钟） |
| `project.input_source` | enum | `aeromech` / `docx` / `manual` |
| `project.source_path` | path | 输入源位置 |
| `stage.current` | enum | `S1`…`S7` |
| `stage.history` | list | 迁移记录（from/to/type/reason/evidence/issue_id/override/ts） |
| `stage.open_issues` | list | 未关闭问题（id/severity/category/target_stage/desc/close_condition/status/raised_at/closed_at） |
| `outline.file / sections` | path/int | S2 产物 |
| `deck.file / slides` | path/int | S3 产物（deck.yaml 为逐页内容真源） |
| `theme.file / mode` | path/enum | S4 产物；mode ∈ `builtin` / `template` |
| `build.pptx_file / layout_file` | path | S5 产物 |
| `qa.reports` | list | S6 报告 `{file, ts, summary}` |
| `last_updated` | string | ISO 8601，任何写入都刷新 |

约束：讲稿正文、逐页要点全文**不得**写入 state.yaml，只写路径与计数。

## 2. 允许边与门禁

主链 `S1→S2→S3→S4→S5→S6→S7`；跳跃边 `S3→S5`（主题沿用既有 theme.yaml 时）。
回退边：`S3→S2`、`S4→S3`、`S5→S3/S4`、`S6→S2/S3/S4/S5`、`S7→S6`。
**返程总规则**：任何 revert 的逆边合法，前置 = 触发的 open_issue 全部 closed。

前进门禁（`state_util.gate_missing` 实现）：

| to | 前置条件 |
|---|---|
| S2 | title + input_source 已定 |
| S3 | outline.yaml 落盘 |
| S4 | deck.yaml 落盘 |
| S5 | deck.yaml + theme.yaml 落盘 |
| S6 | pptx_file 落盘 |
| S7 | severity ∈ {严重, 高} 的 open_issue 全部 closed |

## 3. 迁移纪律

1. 产物落盘（路径写入对应字段）后才允许改 `stage.current`。
2. 回退必须先备份（`state.yaml.bak-revert-<ts>`），必须写 reason 或 issue_id。
3. 非法迁移/门禁不过 → 拒绝，输出合法路径与缺失项；被拒绝的迁移**不写入 history**，改记 `context.md` 拒绝区。
4. 用户强行推进 → 二次确认 → `type: override` + open_issue（severity=高）。
5. `from == to` 合法，`type: milestone`（如"deck.yaml 定稿"），current 不变。
6. 备份保留最近 5 份，超出删最旧。

## 4. open_issues

severity 枚举：严重 / 高 / 一般 / 建议。category → target_stage 映射：

| category | 典型问题 | target_stage |
|---|---|---|
| structure | 板块缺失、叙事顺序错、页数预算失衡 | S2 |
| content | 要点超上限、内容与论文不符、【待填】未补 | S3 |
| design | 配色/字体偏离校模、版式不一致 | S4 |
| render | 构建失败、图片缺失、layout 元数据异常 | S5 |
| qa | PPT-01~10 未过项 | 按检查项映射（见 qa.md） |
| integrity | 虚构结果/数据 | S3，severity 一律「严重」 |

新增即 append；处理中置 `in_progress` 并触发回退；关闭写 `closed_at` 并记返程 forward。severity=严重 未关闭禁止进 S7。

## 5. 恢复协议（"继续做PPT"）

1. 定位工程目录（当前目录向上最多 2 级找 `.pptdirect/`）。
2. 读 state.yaml；损坏 → 备份后按 schema 补默认值并告知。
3. 输出四行恢复摘要（`state_util.py status`）：题目 | 当前阶段+输入源+档位 | 已定产物 | 未关闭问题。
4. 禁止重复询问 state 已定字段；缺失项标【假设】继续。
5. open_issues 非空 → 先处理回退再前进。

## 6. 初始化

`state_util.py init <工程目录>`：创建 `.pptdirect/artifacts/qa/`，`stage.current: S1`，history 记首条 `from: null, to: S1, type: forward, reason: "项目初始化"`。
