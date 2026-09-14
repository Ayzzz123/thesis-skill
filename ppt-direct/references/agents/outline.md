# Outline Agent（S2 大纲规划）

| 项 | 内容 |
|---|---|
| 职责 | 把论文结构映射为答辩叙事板块，做页数预算 |
| 输入 | ingest 草稿（outline.yaml / deck.yaml）或用户口述结构 |
| 输出 | `.pptdirect/artifacts/outline.yaml` 定稿 |
| 触发 | S2 路由 |

## 答辩叙事骨架（按论文类型裁剪）

标准四板块：研究背景与意义 → 研究内容与方法 → 分析过程与结果 → 结论与展望。

- 综述型：「分析过程」改为「文献综合与对比」；
- 设计型：「分析过程」拆为「方案设计」+「计算/仿真校核」；
- 页数预算：cover 1 + toc 1 + closing 1，内容页 = 档位中值 − 3 − 板块数；单板块内容页不超过档位上限（short 1 / standard 2 / long 3）。

## 规则

- 章节→板块映射参考 `ingest_source.py` 的 SECTION_HINTS；用户不认映射时以用户口径为准。
- 页数预算超档位 → 合并板块或降档，不允许超上限进 S3。
- 出口：outline.yaml 落盘（sections 列表 + page_budget + tier），写 state `outline.file` 后转 S3。
