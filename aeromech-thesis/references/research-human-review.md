# Research Human Review（研究语义人工复核，v1.4.1）

**定位**：启发式自动检查无法可靠判定的 **Critical 级研究语义问题**，一律进入人工复核队列——
自动检查**不得**给出 PASS。本文档定义复核维度、队列机制与裁决回填格式。

## 1. 为什么需要人工复核

RQG-01~15 中大多数检查是机械可判定的（引用存在性、label 强制、覆盖率等），但以下问题属于
**语义判断**，模式/关键词检测只能证伪、不能证实：

- 同义改写（"来自维修记录整理"绕过"实测"模式）
- 隐含口径（用"每年发生 X 次"暗示真实频率而不写"发生率"）
- 强度放大（用"充分说明""必然"弱化不确定性）
- 证据能力与结论范围的匹配（模拟 50 条样本 ≠ 机队统计）

因此 v1.4.1 规定：**弱证据（simulated/pending）语境下的 RQG-09（摘要身份一致性）与
RQG-10（证据越界）在未命中模式时输出 `NEEDS_HUMAN_REVIEW`**，并生成
`artifacts/qa/human-review-checklist.md`（含 claim / evidence / reason / uncertainty）。

## 2. 复核维度（七项，逐项检查）

### HR-1 核心结论是否真的被证据支持
- 对每条结论，沿 结论→分析→证据 链核对：证据内容（不是"存在"）是否足以支撑该结论的**强度与范围**。
- 例：模拟数据支持"方法链条可行"，不支持"该机型故障率最高"。

### HR-2 工程判断是否超过数据能力
- 工程判断（阈值、间隔、经验系数）必须标注为"本文设计值/工程经验值"，不得冒充标准/实测结论。
- 检查：正文是否给出取值来源与修正路径（如"须以真实数据修正"）。

### HR-3 模拟数据是否被误写成真实数据
- 全文检索式复核：摘要、正文、图表题注、结论、答辩稿中是否出现
  "实测/试验测定/机队统计/实际运行数据/来自维修记录"等真实口径描述模拟数据。
- 免责句（"不代表真实机队水平"）不能覆盖正文其他位置的误写。

### HR-4 研究方法是否真的能够回答研究问题
- 对每个 RQ：该方法输出（FMEA 排序/统计量/矩阵映射）与问题的信息需求是否同构。
- 例：问"发生率是多少"，FMEA 只能给"相对风险排序"，不能给"发生率"——须在正文显式限定。

### HR-5 摘要是否准确反映研究结论
- 摘要数值 ⊆ 正文数值（自动）；再用人工核对：摘要的结论方向、强度、限定语与正文/结论一致；
- 摘要不得省略对结论能力的关键限定（如"模拟条件下"）。

### HR-6 关键数字是否可信
- 抽查 RQG-13 标出的可追溯数字：引用内容是否真的支持该数字；计算数字能否按 CALC 条目复算；
- 单位/量纲/口径（每飞行小时 vs 每架年）是否明确。

### HR-7 文献是否真正支持对应论断
- 抽查引用：来源（题录级/摘要级/全文级）能支持到的表述强度；
- 题录级来源只能支持"已有资料报道"级表述，不得支撑具体数值结论。

## 3. 队列机制（自动 → 人工 → 回填）

1. **自动**：`research_quality_qa.py` 生成队列项与 `human-review-checklist.md`；
   Gate 状态为 `PASS_WITH_HUMAN_REVIEW`（允许交付流程继续，但**交付前必须完成复核**）。
2. **人工**：按第 2 节七维逐项复核，在清单上逐条裁决
   （`ok` 无越界 / `violation` 越界或不成立），并在评审记录中给出依据。
3. **回填**：把裁决写入 `.aeromech/research/human-review.yaml`：

```yaml
reviews:
- item: RQG-10:CL-003          # 与清单中的 item 键一致
  decision: ok                 # ok（无越界，解除队列）| violation（越界，触发 Critical FAIL）
  reviewer: <复核人>
  date: <YYYY-MM-DD>
  note: <判定依据（引用正文段落/证据条目）>
```

4. **重跑**：`research_quality_qa.py` 消费裁决：
   - 全部 `ok` → Gate `PASS`；
   - 任一 `violation` → Gate `FAIL`（Critical，须按复核结论修改正文/注册表后重跑）；
   - 未裁决项保持 `PASS_WITH_HUMAN_REVIEW`；
   - 未知键名/未知 decision → WARN（提示核对，不阻断）。

## 4. 什么时候必须升级为 violation

- 结论依赖模拟数据却声称真实口径（HR-3）；
- 方法输出与问题要求不同构且正文未限定（HR-4）；
- 摘要与正文结论方向/强度不一致（HR-5）；
- 数字引用不支持、计算不可复算、口径不明（HR-6）；
- 来源能力不足却支撑强表述（HR-7）。

## 5. 责任边界

- **Agent 不代签复核结论**：队列裁决必须来自人类复核者；Agent 只能生成清单、消费裁决、驱动回退。
- 复核记录随项目归档（`.aeromech/research/human-review.yaml`），作为交付证据的一部分。

## 6. 与 v1.5 Research Agent Loop 的衔接

v1.5 引入第二种人工复核载体（两者并行、互不替代）：

- **本文 §3 的 `human-review.yaml`**：针对 RQG-09/RQG-10 语义项（ok/violation 两值裁决）——机制不变。
- **`.aeromech/research/human-review-queue.yaml`**：由 `research_agent_loop.py` 生成，针对诊断引擎
  的 queue 类判定项（设计/方法/范围/冲突/数字人工核对项），裁决格式为
  `decision: approve|reject|modify` + `payload.replacement` + reviewer/date/note；
  由 `research_repair.py <root> apply-human` 消费：approve/modify → 执行并记 verified REP；
  reject → 诊断关闭（rejected_by_human）；不可文本化选项 → deferred（保持待复核，不静默）。
- queue 项未裁决期间 Gate 记 `PASS_WITH_HUMAN_REVIEW`（与 RQG NHR 语义一致）；
  交付前两种队列都必须清零或全部裁决（SKILL.md §16/§20、delivery-pipeline.md §8.3）。
- 七维复核清单（§2）同样适用于 loop 队列项：Agent 不得代签，不得把 deferred 当作通过。
