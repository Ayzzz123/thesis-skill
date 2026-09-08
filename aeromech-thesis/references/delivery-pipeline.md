# 交付流水线规范（Delivery Pipeline）

**本卡为 v1.0.0 delivery pipeline stabilization 的已验证规则集**。以下流程已在真实测试论文（39 页 PDF）上通过：页面流优化 PASS、PDF 真实 TOC PASS、TOC 页码一致性 10/10、PDF 页码正常、图+题注同页 PASS、主要异常空白消除。任何偏离须以重新渲染后的实际 PDF 为准。

## 1. 正式交付 Pipeline

```
S1–S7 研究/写作
  → S8 Figure Generation（scripts/render_mermaid.py + 数据图）
  → S9 QA（文本层）
  → DOCX Assembly（scripts/build_docx.py，内容层由 Agent 依论文结构生成）
  → PAGE_FLOW_OPTIMIZER（内置 docx 引擎）
  → Visual Regression（scripts/visual_regression.py）
  → TOC Update（scripts/update_toc.py，Word COM 两轮）
  → PDF Export（scripts/export_pdf.py）
  → PDF Structural QA（scripts/pdf_qa.py）
  → PDF Visual QA（scripts/visual_regression.py --pdf）
  → Delivery Gate（见 §7）
  → 毕业论文.docx + 毕业论文.pdf
```

S10 答辩能力独立，不受交付层影响。

## 2. PAGE_FLOW_OPTIMIZER 规则（已验证）

整体原则：**以整体页面流为目标，不堆叠局部 keep 规则**。

1. 普通正文不得默认 keep_together；允许自然跨页。
2. H1/H2/H3 使用适度 `keep_with_next`（标题不得孤立页底）。
3. 不使用全局强制分页解决页面空白；H1 分页仅用于章节/封面/摘要/目录/方向切换。
4. FigureBlock（图片+图题）必须作为不可拆分整体（无边框单列表格 + 行 cantSplit）。
5. 表格行 cantSplit；长表允许跨页且表头 tblHeader 重复。
6. 优先调整图块尺寸而非压缩正文/缩小字体。
7. 页面优化以正文自然连续流动为目标。

图块尺寸（**推荐值，非机械硬上限**——可按版式调整，高分辨率源图可保持，显示尺寸以可读性为准）：

| 图型 | 高度建议 | 说明 |
|---|---|---|
| 常规框图/统计图/故障树 | ≤ 9.5 cm | 一页可容纳图+正文，正文自然连续 |
| 超高窄图（aspect < 0.4，如纵向技术路线图） | ≤ 12.5 cm | 窄图纵贯，缩小会牺牲文字 |
| 横向页内图 | ≤ 10 cm | 横向页面高度有限 |

配置点：`scripts/docx_engine.py` 中 `calc_image_width_cm()` 的高度分级常量。

## 3. 章节结束页例外（B 类低占用）

**低页面占用 ≠ 排版错误。** 区分两类：

- **A 布局异常（需修复）**：图被推下页致前页大空白；标题被不合理推后；1–3 行孤立段落页；keep 规则造成的巨大空白；表格分页导致的异常空白；正文中断处出现 >1/3 页无意义空白。
- **B 内容型低占用（允许）**：致谢/声明等天然内容少；章节自然结束；下一章按论文结构正常换页；段落跨页的自然尾巴（Word 流式排版固有）。

B 类不得被强行填满。Visual Regression 对 B 类页面豁免或标记为 review-with-reason。

## 4. TOC Pipeline（已验证）

- TOC 必须为 Word 原生目录域：`TOC \o "1-3" \h \z \u`；标题必须用真实 Word Heading 1/2/3。
- 流程：DOCX Assembly → 确认 Heading 层级 → 保留/插入原生 TOC Field → Word COM `TablesOfContents.Update()` → `Repaginate()` → **第二轮再 Update** → 保存 DOCX → 重新 Export PDF。
- 禁止：普通文本伪造目录、手工输入页码、直接修改旧 PDF 目录文字、按旧页码简单替换。
- 以最终 PDF 实际页码为最终结果。
- 实现：`scripts/update_toc.py`（两轮 COM 更新 + 保存）；页码字段只在第一个 section 添加一次（footer 继承），避免 888/101010 重复页码。

## 5. PDF 才是最终真值

DOCX ≠ 最终验收对象；**Final PDF 为交付真值**。DOCX 的分页、目录域、字体替换、图表分页可能在 PDF 导出阶段变化，以下必须逐项在 PDF 层复检：页码、TOC、Figure、Table、分页、空白页、标题位置、图题位置。

## 6. PDF QA 检查项（scripts/pdf_qa.py）

1. 页数检查
2. 页码连续性（页脚区域单一数字，无重复）
3. TOC 检查（TOC-01~TOC-10，见下）
4. Heading 检查（H1/H2/H3 层级存在）
5. Figure 数量检查
6. Figure + Caption 同页检查（题注文本与图片同页）
7. Table 数量检查
8. 表头重复检查（跨页表各页首行含表头关键词）
9. 表格异常分页检查（单记录断裂）
10. 占位文字检查（"将在 Word 中更新域后生成"等）
11. 路径泄露检查（无本机绝对路径）
12. 模拟数据标签检查（【假设/模拟·仅演示方法】存在且不冒充真实）
13. 【待核实】状态检查
14. 文献编号/引用完整性
15. PDF 文本可提取性
16. 视觉回归检查（另走 visual_regression.py）

### TOC QA（TOC-01~10）

- TOC-01 无目录占位文字
- TOC-02 目录存在真实条目
- TOC-03 目录页码与 PDF 实际章节起始页一致
- TOC-04 Heading 层级与目录缩进正确
- TOC-05 目录可见可读
- TOC-06 目录更新不产生异常空白页
- TOC-07 PDF 页数变化可解释
- TOC-08 DOCX 更新后重导 PDF 与 DOCX 内容一致
- TOC-09 页码格式正常（单数字）
- TOC-10 全部通过才进入 Delivery Gate

## 7. Visual Regression 规则（scripts/visual_regression.py）

不只看"能生成 PDF"。检查页面类型：封面、摘要、目录第一/二页、每章起始页、含 FigureBlock 页面、含长表页面、横向附录页、致谢页、最后一页。

页面占用率为辅助指标：<40% review、40–60% normal、60–90% ideal、>90% review；目录/致谢/声明/章节自然结束页豁免或 review-with-reason。实现：按 y 范围统计排除页脚的内容占用率，并对低占用页列出原因分类（A/B）。

## 8. Delivery Gate（失败等级）

- **Critical**：禁止交付（如虚构数据/文献入稿、正文缺失、占位目录残留）
- **High**：禁止正式终稿交付（如 TOC 页码不一致、图+题注跨页、重复页码）
- **Medium**：允许测试交付，报告中披露
- **Low**：允许交付，记录为优化项

**研究证据层限制不得因排版成功而被覆盖**：无真实故障数据、无受控手册、文献全文未获取、机型未绑定等，仍属 Integrity 机制约束，必须如实披露。

## 9. 脚本工程要求

1. 清晰命令行入口（`python xxx.py <project_root>`）
2. 明确退出码（0=成功，非 0=失败并给出原因）
3. 失败输出可读错误信息
4. 不生成 placeholder 并偷偷进入最终论文
5. 临时文件进临时目录
6. 交付目录只留必要产物（毕业论文.docx/.pdf）
7. 不泄露本机绝对路径到论文正文
8. Windows 可运行
9. 避免手工环境变量（Mermaid wrapper 保留 Chrome 自动检测）
10. 现有脚本只修改不重复创建

## 10. Front Matter / AbstractBlock 规则（已验证）

问题背景：中文摘要与英文摘要连续排版时，若 Abstract 标题被放入中文摘要页剩余空间，英文摘要主段可能跨页并在短语级（如列举项 "up-lock," / "down-lock,"）断裂。

规则（AbstractBlock）：
1. **"摘 要" 与 "Abstract" 各自独立成页**：Abstract 标题设 `page_break_before`，使中/英文摘要各自独占一页；中文摘要页底部自然留白属内容型结束（B 类豁免），不强行填充。
2. Abstract 标题 `keep_with_next`（与首段同页）；英文摘要主段不设段落级 keep_together（允许自然流动，但因其独占一页，正常长度下不再跨页）。
3. Keywords 与摘要主体同页；不得让 Keywords 单独孤立成页。
4. 中文摘要正文允许跨页（若超长），但标题不得孤立页底。
5. 实现：`scripts/build_docx.py` 中 `h1_no_break(text, page_break=True)`。

### Abstract QA（ABSTRACT-01~06）

- ABSTRACT-01 Abstract 标题页存在且标题后正文非孤立（同页正文行数 ≥3）
- ABSTRACT-02 英文摘要无短语级跨页断裂（Abstract 标题、主体、Keywords 同页即 PASS；跨页需人工判定断裂点是否自然）
- ABSTRACT-03 英文摘要内容完整（Keywords 存在且与 Abstract 主体同页）
- ABSTRACT-04 Keywords 不被异常孤立
- ABSTRACT-05 修复后目录页码仍与实际一致（TOC-03 覆盖，Abstract 页码须 = 实际标题页）
- ABSTRACT-06 修复不引入新的正文页面流异常（visual_regression 覆盖）
