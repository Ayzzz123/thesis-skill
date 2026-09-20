# v1.6.5 — V1.6.5_VISUAL_QA_SPEC（FIGURE_VISUAL_QA：VIS-01~12 + Figure Quality Score）

原则：
1. **七层分离**：Semantic / Data / Geometry / Readability / Academic / Aesthetic / PDF-fidelity
   各自独立判定，几何 PASS ≠ 视觉 PASS。
2. **可机检优先，不可机检诚实降级**：每项标注 `[M]`=machine、`[H]`=human-needed；
   `[H]` 项一律 NEEDS_HUMAN_REVIEW 或 SKIP——**绝不允许恒 True**（消灭 D1 自证式 PASS）。
3. **Critical 短路**：任何 Critical 规则 FAIL → 该图 BLOCK，总分再高也无效。
4. 新模块 `scripts/figure_visual_qa.py`（实现阶段），输入=PNG + layout JSON + 源数据 + 正文引用；
   输出=VIS 报告（item 级 v1.4.1 七态）+ Figure Quality Score（展示值，不参与放行）。

---

## VIS 检查项定义

| ID | 名称 | 层 | 判定方法（候选） | 级别 |
|---|---|---|---|---|
| VIS-01 | Layout Balance 版式平衡 | Aesthetic | `[M]` 内容包围盒重心 vs 画布光学中心偏移 ≤8%；左右/上下留白比 ∈[0.6,1.7]；分支子树节点数差（故障树）≤1 | WARN→NHR |
| VIS-02 | Information Density 信息密度 | Readability | `[M]` ink 面积比 ≤45%（300dpi 二值化实测）；节点数 ≤ 类型上限；文字覆盖 ≤55%；拥挤度=min(框距, 字距) 归一 | FAIL(超上限)/WARN |
| VIS-03 | Typography Readability 文字可读 | Readability | `[M]` 有效字号≥9pt（GQ-09 复用）；**必测样例集**：中文/English/数字/单位/数学符号/上下标/DOI/标准号 渲染无缺字（tofu 检测：字体覆盖比对）、无断行歧义 | **Critical**（缺字/裁切）|
| VIS-04 | Color Harmony 色彩和谐 | Aesthetic | `[M]` 填充色相数 ≤3；全部填充色 ∈ figure_style.PALETTE（白名单，禁随手 HEX）；饱和度上限（HSL S≤0.45，强调色除外） | WARN |
| VIS-05 | Contrast 对比度 | Readability | `[M]` 文字/底 WCAG ≥4.5（正文）/≥3（大字）；相邻区域灰度差 ≥0.12（02-A-3 实测公式） | FAIL |
| VIS-06 | Semantic Color Consistency 语义色一致 | Academic | `[M]` 图中出现的每个"角色→颜色"对必须命中 SEMANTIC 字典；同角色跨图同色（与 VIS-12 联动） | FAIL |
| VIS-07 | Whitespace 留白 | Aesthetic | `[M]` 图内四周绘制留白 ≥0.4cm；题注-图距、图-正文距（GQ-12/13 复用）；无元素贴画布边 ≥0.08cm（GQ-18 复用） | WARN |
| VIS-08 | Alignment 对齐 | Academic | `[M]` 同层节点顶边/中线 y 差 ≤0.05cm；框左右边对齐栅格（x 量化残差 ≤0.05cm）；标签居中偏差 ≤0.1cm | WARN |
| VIS-09 | Academic Style 学术克制 | Aesthetic | `[M]` 禁用元素检测：渐变（多段色带）、阴影（offset 重复轮廓）、3D、装饰图标；数据墨水比代理=信息元素/总墨量 ≥0.6；`[H]` 主观"是否像海报"→NHR 附样张 | FAIL(禁项)/NHR |
| VIS-10 | PDF Readability 最终渲染 | PDF-fidelity | `[M]` 在最终 PDF 300dpi 渲染页上实测：标签簇数/行高（GQ-16/17 复用扩展到全类型）、显示宽 ∈ 目标区间、无裁切（GQ-10）、DPI 有效分辨率 ≥300dpi 等效 | **Critical**（裁切/糊）|
| VIS-11 | Figure-Type Appropriateness 类型适配 | Semantic | `[M]` 按 FIGURE_TYPES[type] 的专属规则：柱状图 y 轴必须含 0；对比图共享尺度；故障树三层完整+AND/OR 有非颜色编码；框架图节点⊆注册表 | **Critical**（误导类）|
| VIS-12 | Cross-Figure Consistency 跨图一致 | Academic | `[M]` 同论文全部图：字体族一致、字号档一致、PALETTE 白名单一致、线宽/箭头一致、题注格式一致（figure_style 常量比对 + 渲染样张度量）；同类型图结构参数一致 | FAIL |

**Semantic/Data 前置层（非 VIS 编号，但同链）**：
- SEM：图题/节点/引用与正文一致（FIG-12/13、RQG 已有，保留）。
- **DATA（D10 修复）**：`data_source` 回环核对——QA 重新读取图声明的源数据（CSV/注册表），
  重算图中数值标签/柱高比例/类别顺序，与渲染结果比对（柱高相对误差 ≤2%、顺序一致、无缺类）。
  FAIL=BLOCK（数据不一致是学术问题，不是美观问题）。

---

## Figure Quality Score（展示，不放行）

- 各 VIS 项按阈值给 0–100 子分，加权平均=总分；**与 v1.5 Research Quality Score 同规则**：
  仅作趋势展示，**不参与 gate 放行**；Critical/FAIL 项存在时总分照常显示但 gate=BLOCK——
  报告必须同时呈现"总分 92 / 但 VIS-03 Critical FAIL"，禁止掩盖（§十五-10）。

## 与现有 QA 的关系（不重复建设）

- GQ-01~14（几何/间距/字号/裁剪）**保留为 Geometry 层输入**，VIS 项复用其测量函数，不另造。
- FIG-05/06、GQ-15 三个恒 True 项（D1）：**重构**——有 layout JSON 的图改为真测（复用 GQ 函数），
  无元数据的位图改判 NEEDS_HUMAN_REVIEW（附 pair 样张），**删除无条件 True 路径**。
- delivery_gate 新增 `figure_visual` 域：任一 VIS FAIL/Critical → 该域 FAIL → 终局 BLOCK；
  仅 `[H]` 项未裁决 → PASS_WITH_HUMAN_REVIEW（沿用五态，不新增状态词）。
