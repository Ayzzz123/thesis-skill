# Template Fidelity / Template-Driven Delivery（aeromech-thesis v1.1.0）

本文定义 DOCX 交付的两种生成模式与模板驱动（Template Fidelity）机制。机制源自 thesis-test-3.0
真实学校模板压力测试的已验证实现（OBS-006 修复），沉淀为本 Skill 正式规则。

## 1. Template Fidelity 定义

- 当用户提供**可编辑学校 Word 模板（.docx/.dotx）**时，原始模板就是交付文档的**母版**：
  不允许从空白 Document 重建整篇论文；不允许仅提取字号/字体/页边距后视为"模板接管"。
- 生成路径：`原始 Template.docx → 复制为项目副本 → 保留模板结构 → 在结构内插入/替换论文内容 → 更新 TOC 与页码 → 导出 PDF`。
- 模板是母版，不是格式说明书。

## 2. 两种模式（TEMPLATE_FIDELITY / FORMAT_RECONSTRUCTION）

| 条件 | 模式 | 说明 |
|---|---|---|
| 存在可编辑学校 Word 模板 | `TEMPLATE_FIDELITY` | 原始 DOCX 为母版；内容填充；TF-01~20 QA |
| 仅存在规范/样文/无 Word 模板 | `FORMAT_RECONSTRUCTION` | 规范解析→样式重建（旧路径）；不得冒充模板复制 |

模式选择器：`scripts/template_fidelity.py :: select_docx_mode(school_dir)`；
选择结果写入 `state.yaml`：

```yaml
document_generation:
  mode: template_fidelity        # 或 format_reconstruction
  template_file: "materials/school/xxx.docx"   # reconstruction 时为 null
```

## 3. DOCX 母版原则（至少保留）

封面结构、封面图片/校徽、封面表格、文本框；section 与 sectPr；页边距/gutter；页眉；页脚；
页码设置；styles.xml；Heading 样式；Normal 样式；TOC 样式；图表样式；声明页；摘要结构；
参考文献结构；附录结构；致谢结构。
做法：复制模板文件后，只做"删除样例内容 + 插入论文内容"，不重排模板固定部分。

## 4. 内容替换规则

- 固定内容（校名、校徽、声明原文、页眉文本、样式定义）：尽量原样保留。
- 可变字段（封面：题目/姓名/学号/学院/专业/指导教师/职称/日期等）：只替换需要的字段；
  信息缺失 → 保留模板空槽/占位符，**不得虚构、不得重新设计封面布局**。
- 样例内容（说明文字、××× 示例段、示例图表、示例公式）：删除并替换为真实内容。

## 5. section 与页码规则（防重启三查）

python-docx 的 `add_section()` 会**复制上一节 sectPr**（含 pgNumType 的 start），
直接使用会造成页码意外从 1 重启。规则：

1. 新节建立后先清除继承的 `w:pgNumType`（`clear_pgnum`）；
2. 需要延续格式的节显式写入 `fmt`（**不带 start**）：
   - 前置部分（摘要→ABSTRACT→目录）显式 `fmt=upperRoman`（首节带 `start=1`）；
   - 正文节 `fmt=decimal, start=1`；
   - 横向附录等后续节 `fmt=decimal`（无 start，延续正文计数）；
3. 每个"显示页码"的节只放一个 PAGE 域（footer 继承），页眉自正文节起；
   禁止因新建 section 使页码从 1 重开；header/footer 不得丢失（linked 或显式复制）。

## 6. 页码继承

模板/规范语义：前置部分罗马数字（封面/声明无码，摘要起 I、ABSTRACT II、目录续码），
正文/参考文献/附录/致谢阿拉伯数字连续（正文第 1 页起，附录延续不重开）。

## 7. 图表与题注规则

- 表题在上、图题在下；中英文题注；三线表；题注继承模板样式（克隆模板样例段落 pPr/rPr）。
- **题注不得因空行丢失**：md→DOCX 组装时表题行后的空行允许存在（解析器跨空行收集表行）。
- **相邻表格保护**：两个相邻表格之间必须有合法段落分隔，否则 Word 会把相邻表格自动合并。
  通用原语层已内置：`docx_engine.guard_table_gap`（`add_table`/`figure_block` 自动调用）。
- 图块（图+双行题注）整体不可拆分（1×1 无边框表 + cantSplit）。

## 8. 视觉保真 QA（TF-01~20）

机器可检查/人工复核双轨。脚本：`scripts/tf_qa.py`（`--template --docx [--pdf] [--out]`）。

- TF-01 封面结构 / TF-02 封面字段 / TF-03 封面视觉层级
- TF-04 声明页结构 / TF-05 中文摘要 / TF-06 英文摘要
- TF-07 Heading 样式继承模板 / TF-08 正文字体字号 / TF-09 行距缩进
- TF-10 图题样式 / TF-11 表题样式 / TF-12 三线表
- TF-13 页眉页脚 / TF-14 页码 / TF-15 目录
- TF-16 参考文献样式 / TF-17 附录结构 / TF-18 致谢结构
- TF-19 页面尺寸/边距 / TF-20 模板↔成品页面渲染对照（pair_*.png 人工复核）

TF-20 不允许只做 XML 属性检查：必须渲染原始模板与最终 DOCX/PDF 的对应页
（封面/声明/摘要/ABSTRACT/目录/正文章首/图表页/参考文献/附录/致谢），记录位置、层级、
字体、空白、页眉、页脚、页码与结构对应情况。

## 9. 冲突优先级与记录

```
学校正式规范 > 学校正式模板实际结构 > 模板示例文字 > Skill general defaults
```
- 模板示例与正式规范冲突 → 以学校正式规范为准，并把冲突记录为
  `template_vs_spec_conflict`（school-format.yaml 或交付报告），不得静默修改。
- 无模板（FORMAT_RECONSTRUCTION）时按既有 school-format 层级执行；
  `format_source` 取值不变：school_template / sample_thesis / general_default / unknown。

## 10. 允许的模板扩展与失败恢复

允许内容驱动扩展（新章节/表格/图/附录/横向宽表 section），但必须：
① 属于内容驱动扩展；② 不得声称来自学校模板；③ 记录为【模板扩展/非学校明文要求】；
④ 不得改动模板固定部分的基础结构。

失败恢复：先定位根因再修复后全流程重建——检查顺序建议：
相邻表格合并→查表间段落；页码重启/消失→查 pgNumType start 与 fmt；
题注丢失→查 md 题注空行解析；页眉页脚丢失→查 section 的 header/footer 引用链；
修复后重跑 TOC 更新→PDF 导出→pdf_qa→visual_regression→tf_qa。

## 构建脚本纪律（防硬编码）

- 通用层：`docx_engine.py`（排版原语）、`template_fidelity.py`（模板驱动原语与模式选择）、`tf_qa.py`。
- 项目层：每个论文项目在项目目录内写自己的 `build_docx_<project>.py`，引用通用层。
- 禁止把某个测试项目（thesis-test-*）的题目/图表/参考文献/路径硬编码进通用脚本；
  通用入口一律参数化（project_root/template_path/chapters/figures/materials/school-format）。
- 旧 `scripts/build_docx.py` 仅保留用于 FORMAT_RECONSTRUCTION 与旧项目兼容，不作为新项目默认入口。
