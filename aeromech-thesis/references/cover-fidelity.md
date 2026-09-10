# Cover Fidelity（封面保真机制，aeromech-thesis v1.3.0）

> 溯源：OBS-007（thesis-test-4.0）——封面"单页化"压缩把含校徽的单元格段落
> （300/auto 行距）误压为 240/exact 固定行距，Word 对固定小行距内的 inline 大图按基线对齐
> 绘制，校徽整体被抬出页面上边距（渲染 rect.top < 0）造成顶部裁切/视觉消失。
> 本文档定义封面对象树保护规则与 CF-01~25 QA，防止同类回归。
>
> 溯源 OBS-008（thesis-test-4.0）：字段填值曾清除模板填写行整行横线（u=single 空格 run），
> 并把值写到悬空新行，破坏模板的固定横线字段布局。修复=fill-on-rule（值写在原横线上，
> 横线保留为线尾）+ 占位空行原样保留；新增 COVER_IMMUTABLE_REGION 与 CF-21~25。

## 1. 定义

学校模板第一页（封面）属于**固定模板区域**。Template Fidelity 生成过程对封面只能：
"保留整棵原始对象树 + 替换可变字段文本"，**禁止**对封面对象做任何结构调整、
行距压缩、删除、移动或重绘。

## 2. COVER_FIDELITY_MODE / COVER_IMMUTABLE_REGION 保护规则

**COVER_IMMUTABLE_REGION（v1.3.0）**：封面区为不可变区（immutable region），仅允许一类操作——
`replace placeholder text`（替换占位文本）。禁止：rebuild cover / recreate cover /
delete cover objects / flatten text boxes / convert floating shapes to paragraphs。

进入正文生成前（复制模板后、任何内容删除/插入前），封面区（首个分节锚之前）适用：

1. **零删除**：不得删除封面区任何 body 子元素（表格、段落、绘图对象）；
2. **对象树完整保留**：tables / paragraphs / text boxes / shapes / DrawingML（w:drawing、
   wp:inline、wp:anchor、a:graphic、pic:pic）/ VML（w:pict、v:shape、v:textbox）/
   图片 / relationships / z-order / position / size / wrap settings 全部原样；
3. **图片关系继承**：模板 document part rels 与 word/media 中的封面图片目标
   （rId→media 文件）必须出现在成品 rels 中且 target 文件存在；封面图片数必须等于模板封面图片数；
4. **字段替换**：只替换模板预留槽位（标签后空行/文本框占位文本）中的文本；
   缺失字段保留模板空槽，不虚构、不增删布局元素；
5. **文本框**：保留 position/width/height/anchor/wrap/rotation/alignment/font/size，
   只替换文本内容；
6. **横线（下划线占位线，OBS-008）**：标签行/填写行的 u=single 空格 run 属于模板结构，
   不得删除；字段填值必须在横线上完成（fill-on-rule：克隆横线 run 格式，文字带下划线
   写入横线 run 之前，原空格 run 缩短保留为线尾）；填写槽占位空行原样保留，
   不得把值写到悬空新行；任一模板横线在成品中消失 → CF-21 FAIL；
7. **禁止重绘**：不得从空白 Document 重建封面、不得用普通段落替代文本框、
   不得用 inline 图替代 floating 图、不得按截图手工重排封面。

## 3. 封面单页化的唯一合法手段

当 Word 版式下封面内容贴底临界（内容高 ≈ 页可用高，字段填值可能把表格行拆到第 2 页）时，
**允许且仅允许**以下两类微调，且必须逐段条件判断：

| 微调 | 条件（缺一不可） | 说明 |
|---|---|---|
| 空段行距收紧 | 段落文本 strip 为空 **且** 不含任何 w:drawing / w:pict | 300/auto → 240/exact |
| 标签行行距收紧 | 行距 700/exact **且** 行内所有 run 字号 ≤ 14pt（sz≤28）**且** 不含绘图对象 | 700 → 660（可再调但不得低于 600） |

**禁止**：压缩含图段（即使文本为空）、压缩大字号段（校名/日期等 >14pt）、
删除封面段落（TF-01 段落数一致性依赖 21/21）、修改 tblPr 结构属性。

**标题过长（COVER-TITLE-OVERFLOW）**：题目超过模板槽位单行宽度时，优先：
① 在槽位内自然换行；② 缩小题号字号至槽位内单行（12pt 为默认尝试值）；
**禁止**拉长文本框/改变字段位置/移出模板区域。处理后仍无法容纳 → 记录
COVER-TITLE-OVERFLOW 到交付报告并说明人工处理项。

## 4. Word COM 规范化防护（tblPr 恢复）

Word COM（更新目录/重排页并保存）会把封面表格 tblPr 规范化：移除模板的
`w:tblStyle` 与 `w:tblCellMar` 并追加 `w:tblLook`。交付链顺序：

```
build（母版复制+字段填充+内容组装）
  → update_toc（Word COM，两轮）
  → restore_cover_tblpr（把模板封面表 tblPr 的 tblStyle/tblCellMar 重新注入成品，
     cover_fidelity.py :: restore_cover_tblpr）
  → export_pdf（Word COM 导出 PDF，不再回写 docx）
  → pdf_qa / visual_regression / tf_qa / cover_fidelity_qa
```

`restore_cover_tblpr` 只复制 tblStyle/tblCellMar 两个子元素（模板封面表存在时），
不触碰其它属性；成品无模板同款样式引用时注入无效样式会破坏文档 → 注入前校验
模板 styles.xml 中存在对应 styleId，否则跳过并记 WARN。

## 5. Cover Fidelity QA（CF-01~20）

`python scripts/cover_fidelity.py --template <模板.docx> --template-pdf <模板.pdf>
--docx <成品.docx> --pdf <成品.pdf> --out <qa目录>`

机器检查（docx/PDF 双证据），全部必须 PASS，否则不得进入 Delivery Gate：

| 编号 | 检查 | 证据 |
|---|---|---|
| CF-01 | 模板封面页存在（首表在封面区，模板与成品均非空） | docx |
| CF-02 | 封面图片数量一致（首表内 w:drawing 计数模板==成品） | docx |
| CF-03 | 圆形校徽存在（封面第 1 张图渲染于 PDF p1 且尺寸 ≥100px） | docx+pdf |
| CF-04 | 校名字样存在（封面图 ≥2 或封面文本含校名） | docx |
| CF-05 | 主标题"本科生毕业论文（设计）"存在 | docx |
| CF-06~13 | 字段存在：题目/姓名/学号/学院/专业/指导教师/职称/日期标签 | docx |
| CF-14 | 封面表格结构一致（行/列、tblW、tblLayout；模板 tblStyle/cellMar 存在时成品须已恢复） | docx |
| CF-15 | 封面文本框结构一致（封面区 v:textbox/w:txbxContent 计数模板==成品） | docx |
| CF-16 | 图片位置一致（PDF p1 图像 rect x0/y0 差 <2pt） | pdf |
| CF-17 | 图片尺寸一致（rect 宽高差 <1pt） | pdf |
| CF-18 | 封面视觉布局一致（关键文本行 y 差 <6pt：校名/主标题/日期行） | pdf |
| CF-19 | 封面第一页无内容缺失（模板 p1 非空像素在成品 p1 的覆盖率 ≥98%） | pdf |
| CF-20 | 封面视觉回归（CF-16~19 汇总 + 模板↔成品 pair_cover.png 输出供人工复核） | pdf |
| CF-21 | 原始模板第一页对象树与最终 DOCX 第一页对象树一致（元素序列/段落数/绘图对象/横线 u=single/标签签名）——横线或绘图丢失直接 FAIL | docx |
| CF-22 | 模板图片数量与最终 DOCX 第一页图片数量一致（独立编号证据） | docx |
| CF-23 | 模板固定图片位置/尺寸与最终 PDF 位置/尺寸一致（rect 偏移 <2pt、宽高差 <1pt、越界裁切检测） | pdf |
| CF-24 | 模板固定文本框数量与最终 DOCX 一致（v:textbox/w:txbxContent 计数） | docx |
| CF-25 | 最终 PDF 第一页与模板第一页视觉回归通过（全页前景覆盖 ≥95% + 固定区 ≥98% + 校徽/书法图像区域 ≥98%；校徽或书法字样缺失直接 FAIL） | pdf |

报告输出 markdown（含 CF 逐项结果与 pair 图路径）。退出码 0=全 PASS，1=存在 FAIL。

**图片裁切检测**：任何封面图 rect.top < 0 或 rect.bottom > 页高 → CF-16 FAIL
（此即 OBS-007 的机器化判据）。
