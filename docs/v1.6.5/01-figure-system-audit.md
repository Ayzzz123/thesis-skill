# v1.6.5 Phase 0 — FIGURE_SYSTEM_AUDIT / COLLABORATOR_AUDIT / CAPABILITIES / DEFECTS

基线：`feature-1.6.5-figure-optimization` ← `master`(7aabc37, v1.6.0 release)。
审计对象：scripts/{figkit,graph_quality_qa,figure_iface,figure_table_qa,render_mermaid}.py、
references/agents/figure.md、tests/v1_6/test_figure_iface.py、test-8.0 实产物（fig3-1/3-2/4-1 + PDF p19/20/28）。

---

## 0. 第一性结论（回答"能生成 ≠ 生成得好"）

现有系统在**几何正确性**上是真实且有价值的（figkit 输出 layout JSON，graph_quality 做相交/穿字/间距实测），
但在**视觉质量**维度上几乎为零：没有颜色系统、没有字体系统、没有版式平衡/留白/密度/对比/和谐/跨图一致性的任何度量。
更关键的是存在**自证式 PASS**——若干 QA 项直接 `rep.add(..., True, ...)` 恒真（见 D1），
以及**语义造假**——Mermaid 渲染失败时的 fallback 会画一张与真实模型无关的"Top Event/OR Gate/Cause A/B"通用图并判通过（见 D2）。
因此"机器 PASS 但人看着丑/甚至错"完全可能，这正是 v1.6.5 要消灭的核心风险。

---

## 1. COLLABORATOR_IMPLEMENTATION_AUDIT（协作者实现审计）

**事实核查（可复现）**：
- `git ls-remote --heads origin` 只有：feature-1.6.0-full-stack-orchestration、featureyyy、
  featureyyy-ppt-direct、featurezzz、main、master。**v1.6 契约/文档中引用的
  `feature-1.6.0-figure-generation` 分支在远端不存在**（UNKNOWN/未交付）。
- `git diff master...origin/{featurezzz,featureyyy-ppt-direct,main} -- figkit.py graph_quality_qa.py
  figure_table_qa.py figure_iface.py` → **全部为空**：协作者分支的图形文件与 master 逐字节一致，
  不存在独立的 "Figure Engine" 实现可继承。
- `featureyyy-ppt-direct` 有 ppt 图形相关（docx 抽图/版式），但属答辩 PPT 域，非论文图形生成引擎。

**逐项判定**：
| 协作者产物 | 判定 | 理由 |
|---|---|---|
| Figure Engine 独立实现 | **不存在，无需继承** | 远端无该分支；勿默认继承任何"外部图形引擎"假设 |
| feature-1.6.0 figure_iface 契约（本仓） | **KEEP + 扩展** | 契约层设计正确（plan/generate/validate + 生命周期 + 研究链接硬关卡），但 validate 只到几何，不到视觉 |
| ppt-direct 抽图/溢出自愈思路 | **参考（不并入）** | 域不同；其"渲染级溢出检测"思想可借鉴到 VIS-10 |

结论：**没有需要"删除/重构"的协作者代码**（因为不存在独立实现）；v1.6.5 的图形引擎由本仓从零建视觉层，
复用 v1.6 契约骨架。任务书"不要默认继承协作者 figure 分支"得到满足——且实际上无可继承物。

---

## 2. CURRENT_FIGURE_CAPABILITIES（当前真实能力，逐项带证据）

**A. 生成**
- figkit.py：确定性程序化绘图（box/box2/note/arrow/arrow_poly）+ 绘制即产出 `*.layout.json`
  （框/边多段折线/文本 bbox 经 renderer 实测换算 cm）。→ 真实、可复核。**这是最有价值的资产。**
- render_mermaid.py：mmdc 自动探测 Chrome/chrome-headless-shell，设 PUPPETEER_EXECUTABLE_PATH；
  失败走 matplotlib fallback。
- figure_iface.py：FigureProvider 契约（plan/generate/validate）+ PROVIDERS 注册 +
  生命周期 PLANNED→GENERATED→VALIDATED→EMBEDDED→VERIFIED / REJECTED / NEEDS_HUMAN_REVIEW；
  研究链接硬关卡（无 RQ/AN/CL 不得 validate 过）。

**B. 几何 QA（真实）**
- graph_quality GQ-01 节点无重叠、GQ-01b 文本不溢出框（0.03 容差）、GQ-02 边无穿字、
  GQ-03 边不穿节点（多段线采样）、GQ-05 框距≥0.2cm、GQ-06 主流程方向一致。
- GQ-09 图内有效字号≥9pt（缩放×min_font 实测）、GQ-10 无裁剪、GQ-11 图题同页、
  GQ-12/13 间距、GQ-14 独立页占用率≥55%。
- GQ-16~20 统计图 300dpi 渲染级（标签簇数/中位高/不重叠/不贴边/留白/未被挤压）——**真实测量**。

**C. 文档级 QA（真实）**
- figure_table FIG-01~04、07~13（存在/完整/裁剪/字号/双语题注/同页/间距/引用/悬空引用）。
- 嵌入尺寸：test-8.0 三图均 14.4cm 显示（figkit 生成宽 16.5 → 缩放 0.87）。

**D. 生命周期与真相一致（部分）**
- test-8.0 三图 VERIFIED，理由="GQ 全 PASS + figure_table 无 FAIL"——**但该 VERIFIED 建立在
  D1 自证项 + 无视觉层之上**，故"VERIFIED"当前只等价于"几何+文档级通过"，不等价"视觉合格"。

---

## 3. CURRENT_FIGURE_DEFECTS（缺陷清单，按严重度，带行号证据）

### Critical（正确性/诚信，必须先修）

- **D2 Mermaid fallback 语义造假**（render_mermaid.py:110–176）：mmdc 失败时，`generate_fallback_figure`
  对 fault_tree 画的是**通用占位内容**"Top Event / OR Gate / Cause A / Cause B"，与论文真实故障树
  （T1/供压丧失/G1/泵源丧失/E1…E5）**完全无关**，却因 `size>5000` 返回 True（判成功）。
  → 一张**内容错误**的图可进入最终论文。违反"数据真实/逻辑与研究数据一致"第一原则。
  现状缓解：test-8.0 用了 figkit 脚本路径（非 mermaid），未触发；但契约允许 mermaid 图，风险真实存在。
- **D1 自证式 PASS**（三处）：
  - figure_table_qa.py:190 `FIG-05 节点无重叠 = True`（注释"位图不可机器判→人工目检已确认"）
  - figure_table_qa.py:191 `FIG-06 箭头不穿文字 = True`
  - graph_quality_qa.py:300 `GQ-15 人工视觉复核 = True`（"对照图已输出…人工目检：无重叠/无穿字/留白充分"）
  → 恒真项让"通过"与"质量"脱钩，且**测试无法证伪**（test 只断言这些项存在/为 True）。
  必须改为：能测则真测（figkit 有 layout JSON → 可复用 GQ 几何），不能测则 **NEEDS_HUMAN_REVIEW/SKIP**，绝不无条件 True。

### High（视觉质量系统缺失——v1.6.5 主战场）

- **D3 无颜色系统**：figkit 硬编码 `#eef2fa`(填充)/`#4a6fa5`(描边)/`#1a1a1a`/`#333333`(文字)/
  `#444444`(note)/`#333333`(箭头)（figkit.py:36–98）；mermaid 用默认主题（紫/蓝）；
  fallback 用 `blue/lightblue/red/yellow/lightgreen/gray`（render_mermaid.py:135–160，**彩虹且刺眼**）。
  无语义调色板、无"同语义同色"、无黑白打印退化设计。
- **D4 无字体系统**：figkit 固定 SimHei + 散点字号（fs_main=11/10、fs_sub=9.5、note 9.5）；
  mermaid 默认字体；无统一 type scale、无中英数/单位/上下标/技术串（DOI/标准号）一致规则；
  fallback 用 `fontsize=9/14/11` 混排。
- **D5 无任何视觉质量度量**：现有 GQ/FIG 全是几何+文档级，**零**覆盖：版式平衡、信息密度、留白、
  对比度、色彩和谐、语义色一致、学术风格、跨图一致性、图类型适配性。
- **D6 无跨图一致性检查**：test-8.0 三图恰好都走 figkit 才统一；一旦混用 mermaid（不同字体/配色）
  或不同脚本作者手填字号，视觉家族立刻分裂，且无 QA 能发现。
- **D8 Mermaid 图绕过几何校验**（figure_iface.py validate：mermaid 无 layout JSON → 直接 NHR，
  交"PDF 级 VERIFIED 兜底"，但兜底只有 GQ-09 字号，无几何/视觉）→ mermaid 图质量近乎无检。

### Medium（流程/闭环）

- **D7 无生成→检查→重生成闭环**：figure_iface 一次性 generate；失败即 REJECTED/NHR，
  不自动按失败原因重排（改方向/拆图/缩标签）重试。任务要求的 ≤3 次再生成缺失。
- **D9 生命周期 VERIFIED 与视觉合格解耦**：VERIFIED 由外部 build QA 记录，当前只保证几何+文档级；
  应升级为"含 VISUAL_QA 通过"才 VERIFIED。
- **D10 图↔研究数据完整性无强校验**：RQG 管正文数字可追溯，但"图内绘制的数值/类别/顺序
  是否等于 datasets/analyses 登记值"无专项检查（fig4-1 靠作者手抄 CSV 计数，无回环核对）。

### 观察（非缺陷，但约束设计）

- O1 figkit 固定画布宽 16.5cm、dpi=220；缩放 0.87 后有效字号贴 9pt 线（test-8.0 已把 min_font 提到 12 才过）。
  → 尺寸系统要把"生成宽 vs 版心宽 vs 有效字号"作为一等约束。
- O2 现有测试（test_figure_iface 24 项）覆盖契约/生命周期/诚实性（缺源→NHR、孤儿图→NHR、
  失败不落 placeholder）**质量良好，KEEP**；但**零视觉质量断言**——不能指望它挡住"丑图"。

---

## 4. 审计方法学声明（防止"为 PASS 降标准"）

- 本次审计**未修改任何测试期望值**、未改论文内容/结论。
- 所有缺陷均给出**文件:行号**可复核证据；协作者"无可继承实现"以 `git diff`/`ls-remote` 实证。
- test-8.0 三图 VERIFIED 的"名不副实"（只几何不含视觉）如实记录，不为其补写"视觉合格"。
- 下一步设计（见 02/03 文档）针对 D1–D10 逐条给出可证伪的验收标准，避免"程序绿=图好"。
