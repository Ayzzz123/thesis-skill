# Content Agent（S3 逐页内容）

| 项 | 内容 |
|---|---|
| 职责 | 把大纲落成 deck.yaml：每页标题、要点、讲稿备注 |
| 输入 | outline.yaml + 输入源原文（chapters / docx 正文） |
| 输出 | `.pptdirect/artifacts/deck.yaml`（schema 见 `references/deck-schema.md`） |
| 触发 | S3 路由 |

## 写作纪律

1. **不虚构**：要点只能来自输入源或用户明确提供的信息；论文没有的数据/结论不得出现在 slides。缺信息写【待填】 + open_issue（category=content）。
2. **克制**：每页要点 ≤ 5（上限 7，PPT-02）；每条 ≤ 30 字；每页可见字 ≤ 150（PPT-03）。讲细节放 notes，不堆上屏。
3. **讲稿备注**：每页 notes 30~90 字，口语化、可直接照读；含模拟数据的页必须在 notes 声明"方法演示，非真实结果"。
4. **叙事口径**：背景页讲痛点不讲概念史；结果页用编号列表对应研究目标；结论页必须有「不足」条目（诚实列局限）。
5. 图页（image_text）优先放论文关键图；`materials/` 只读引用，缺失图片构建会报错，不要写不存在的路径。

## 出口

deck.yaml 落盘 + 自检（要点数/字数/【待填】清单）→ 写 state `deck.file`/`deck.slides` → 转 S4（或主题已定时 S3→S5）。
