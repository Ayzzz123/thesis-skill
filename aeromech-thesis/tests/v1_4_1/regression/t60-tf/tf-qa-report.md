# TF-01~20 QA（tf_qa.py）
- 模板: （未提供 → 模板对照类检查记 NOT_APPLICABLE）
- DOCX: 毕业论文.docx
- PDF: 毕业论文.pdf

- TF-01 封面结构一致: NOT_APPLICABLE | 无模板项目：模板对照不可执行（FORMAT_RECONSTRUCTION）；如提供学校模板或规范文档后重跑本项
- TF-02 封面字段一致: NOT_APPLICABLE | 无模板项目：模板对照不可执行（FORMAT_RECONSTRUCTION）；如提供学校模板或规范文档后重跑本项
- TF-03 封面视觉层级一致: NOT_APPLICABLE | 无模板项目：模板对照不可执行（FORMAT_RECONSTRUCTION）；如提供学校模板或规范文档后重跑本项
- TF-04 声明页结构: NOT_APPLICABLE | 无模板对照：声明页原文一致性无法比对（成品声明页存在性见 QA 链其他检查）
- TF-05 中文摘要结构一致: PASS | 摘要标题+关键词行存在
- TF-06 英文摘要结构一致: PASS | ABSTRACT 标题+KEY WORDS 行存在
- TF-07 Heading继承模板: PASS | 章Heading1=6 节Heading2=19（样式来自模板 styles.xml）
- TF-08 正文字体字号: PASS | 正文区抽查 25 段（异常=[]）
- TF-09 行距/缩进: PASS | 固定20磅+首行2字符
- TF-10 图题样式: PASS | 图块=2 图题=2（图下中英文题注）
- TF-11 表题样式: PASS | 表题数=2（表上方；md 题注不得因空行丢失）
- TF-12 表格三线表: PASS | 无内线/竖线；顶底单线（表级或单元格级）bad=[]
- TF-13 页眉页脚: PASS | 页眉自节1起：民用飞机起落架刹车系统故障诊断与维修策略
- TF-14 页码: PASS | 前置页码模式=any 前置罗马页=[] 正文阿拉伯=[]...连续
- TF-15 目录样式: PASS | Word 原生目录域；样式继承模板 toc1/toc2
- TF-16 参考文献样式: PASS | 条目数=15(≥5)；不足如实披露不凑数
- TF-17 附录结构: PASS | 附录标题=['附录A 评分准则说明', '附录B 模拟数据集样本节选']（A/B/C 排序）
- TF-18 致谢结构: PASS | 致谢字数≈102（≤500）
- TF-19 页面尺寸/边距: NOT_APPLICABLE | 无模板页边距基准（成品 A4≈(21.0, 29.7) 边距 {(2.5, 2.5)}）；提供 --margins 规范值或学校模板后可核验
- TF-20 PDF视觉复核（渲染输出）: PASS | 成品关键页渲染 [('封面', 1), ('中文摘要', 2), ('ABSTRACT', 3), ('目录', 4), ('正文样例', 6), ('参考文献', 17), ('致谢', 19), ('附录', 20)]（render_*.png 供人工复核；规范驱动重建模式）

- 汇总: PASS=15 FAIL=0 NOT_APPLICABLE=5 SKIPPED_WITH_REASON=0