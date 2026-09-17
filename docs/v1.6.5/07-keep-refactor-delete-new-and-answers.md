# v1.6.5 — KEEP / REFACTOR / DELETE / NEW 清单 + 八个必答问题

## KEEP（保留，真实有价值）

| 资产 | 理由 |
|---|---|
| `figkit.py` 核心机制（程序化布局 + 绘制即输出 layout JSON + renderer 实测 bbox） | 全系统最有价值资产：几何可测的前提。保留并接入 figure_style 常量源 |
| `graph_quality_qa.py` GQ-01~14 几何/间距/字号/裁剪/独立页度量 | 真实测量，作为 VIS 的 Geometry 层输入复用，不重造 |
| GQ-16~20 统计图 300dpi 渲染级度量 | 已是"PDF 最终真相"的雏形，扩展为 VIS-10 的通用实现 |
| `figure_iface.py` Provider 契约 + 生命周期 + 研究链接硬关卡 + 诚实性（缺源 NHR/孤儿 NHR/失败不落 placeholder） | v1.6 正确设计，v1.6.5 在其上挂视觉层与闭环 |
| `figure_table_qa.py` FIG-01~13（存在/完整/双语题注/引用/悬空引用） | 文档级真实检查，保留 |
| `render_mermaid.py` 的 mmdc/Chrome 探测与环境传递 | 环境适配正确；仅 fallback 部分要改（见 DELETE） |
| `test_figure_iface.py` 24 项契约/生命周期/诚实性断言 | 质量良好；视觉断言另加（tests/v1_6_5），不改动既有期望 |
| `references/agents/figure.md` 规则1/2（无真实数据不画真实图；图必有正文引用）、figure-plan 表结构 | 诚信与追踪规则正确，保留并补视觉规范引用 |
| SKILL §18.3 GRAPHICAL_READABILITY_FIRST（有效字号≥9pt、禁缩图塞页、重设计拓扑优先） | 原则正确，升级为 ACADEMIC_VISUAL_QUALITY_FIRST 的基座 |

## REFACTOR（重构，方向对但实现不足）

| 对象 | 现状问题 | 重构方向 |
|---|---|---|
| figkit 样式常量 | 散写 `#eef2fa/#4a6fa5/#1a1a1a/#333333/#444444`、fs=11/10/9.5 硬编码 | 全部改从 `figure_style.py` 取（PALETTE/SEMANTIC/FONT/FONTSIZE）；figkit 增加 `role=` 参数按语义取色 |
| figure_iface.LocalProvider.validate | 只到几何；mermaid 图无 layout JSON 直接放行到"NHR 兜底"近乎无检（D8） | validate 链扩展：几何→VISUAL→（有元数据时）；mermaid 渲染后强制走渲染级度量（栅格分析），无元数据不再"裸 VERIFIED" |
| 生命周期 VERIFIED 语义 | 现="几何+文档级过"，名不副实（D9） | VERIFIED 必须含 VISUAL_QA+PDF_RENDER_QA 通过；闭环失败 3 次→NEEDS_HUMAN_REVIEW |
| render_mermaid 的 mmdc 调用 | `-b transparent` 裸主题，字体/配色不受控 | 提供 mermaid init 主题（fontFamily/themeVariables 绑定 PALETTE），使 mermaid 与 figkit 同一视觉家族；仍失败→REJECTED（不 fallback 造假） |
| graph_quality `discover_figs`/layout 目录约定 | 依赖文件名解析、目录约定脆弱（final/ vs 根） | 统一 layout JSON 目录约定 + 显式 manifest 映射（fid→layout），消除"按名猜" |
| 测试策略 | 只测"契约/状态机"，零视觉可证伪断言 | 新增 tests/v1_6_5 合成负例（T2/T3/T4），每项 VIS 必须有 FAIL 用例 |

## DELETE（删除/移除）

| 对象 | 理由 |
|---|---|
| figure_table_qa FIG-05/06 恒 `True` 自证路径（:190-191） | 有 layout JSON 即真测（复用 GQ-01/02），无元数据→NHR/SKIP；**无条件 True 路径删除**（D1） |
| graph_quality GQ-15 恒 `True`（:300） | 同上：pair 输出保留，但判定改 NHR（人工裁决）或并入 VIS-01/02 度量 |
| render_mermaid `generate_fallback_figure` 的 fault_tree/flowchart 通用假内容分支（:127-160） | **语义造假**（D2）：画"Top Event/Cause A/B"与真实模型无关却判成功。删除"画个像模像样的假图"能力；mmdc 失败→FIGURE_ERROR→REJECTED→闭环改走 figkit 忠实重绘（用真实节点/边数据）或 NHR。`size>5000=成功` 判据一并废除 |
| fallback 的 red/yellow/lightgreen/blue 彩虹色 | 违反 §十五-3；随上项一并删除 |
| "占位图仅测试用途"的灰色地带 | 明确：placeholder 永不进 DOCX/PDF（现有注释已声明，落成强制断言） |

## NEW（v1.6.5 新增）

| 对象 | 内容 |
|---|---|
| `scripts/figure_style.py` | 视觉系统单一来源：PALETTE/SEMANTIC/FONT/FONTSIZE/SPACING/LINE/FIGURE_TYPES + contrast_ratio/grayscale_delta/ink_ratio/hue_count 纯函数（色值经实测固化） |
| `scripts/figure_visual_qa.py` | VIS-01~12（04 文档）+ Figure Quality Score（展示不放行）；机检/人检分离，Critical 短路 |
| REGENERATION 闭环（figure_iface 扩展 + orchestrator 挂载） | SELECT_TYPE→GENERATE→SEM→DATA→GEOM→VIS→STYLE→PDF→PASS/REGENERATE(≤3)→NHR（05 文档） |
| DATA 回环核对 | 图↔源数据重算比对（D10），篡改/缺类/乱序可测 |
| mermaid 主题注入 | init 主题绑定 PALETTE/字体，使 mermaid 与 figkit 同家族（仍无忠实性则 REJECTED） |
| `tests/v1_6_5/` | T1~T6（06 文档），含反自证负例与 test-8.0 端到端双轨（machine+目检） |
| 九类图参考样张（golden samples） | 每类 1 张 + layout JSON，作视觉回归基线与"同一家族"参照 |
| `references/figure-visual-system.md` | 02/03/04/05 文档的 Skill 内化版；SKILL §18.3 升级引用 |

---

## 八个必答问题

**1. 为什么现在"技术上能生成图"但不一定"生成得好看"？**
因为整条链只在**几何层**闭环（相交/穿字/间距/字号），视觉质量的六个维度——色彩、字体、平衡、密度、留白、风格克制——**没有任何定义、没有单一来源、没有度量**。figkit 的硬编码蓝灰"碰巧不丑"，mermaid 默认主题和 fallback 彩虹色"碰巧能看"，全靠运气。且三处恒 True 自证项让"通过"与"质量"解耦。

**2. 协作者哪些工作值得保留？**
实证结论：远端不存在独立 Figure Engine（`feature-1.6.0-figure-generation` 无此分支；三个协作者分支的图形文件与 master 零差异）。因此**没有协作者代码需要取舍**；真正值得保留的是 v1.6 本仓资产：figkit 的 layout JSON 机制、GQ 几何度量、figure_iface 契约与生命周期、诚实性测试。ppt-direct 分支的"渲染级溢出检测"思想可借鉴到 VIS-10，但不并入其实现。

**3. 哪些必须重写？**
① mermaid fallback（语义造假，DELETE 后由"忠实重绘或 REJECTED"替代）；② 三处恒 True 自证项；③ figkit/脚本内散写样式（改常量源）；④ validate 的"无元数据≈无检"路径；⑤ VERIFIED 的语义（必须含视觉+PDF 层）。

**4. v1.6.5 应新增哪些视觉能力？**
figure_style 单一来源系统（02 文档 A-J）、VIS-01~12 视觉度量（04）、DATA 回环（D10）、REGENERATION 闭环（05）、mermaid 主题注入、跨图一致性检查、九类图规范与样张基线。

**5. 怎样让颜色真正自然、简约、高级？**
有限白名单（9 角色）+ 语义映射（同语义同色）+ 三条硬约束机器化：色相预算（填充 ≤3）、WCAG 对比（Text/Fill=13.21 实测）、灰度退化（相邻填充 Δgray≥0.12，Secondary/Primary=0.096 即禁作相邻对——已暴露候选色需实测微调）。强调色每图 ≤1 用途；禁彩虹、禁渐变。色值不拍脑袋：候选基线→渲染样张+灰度+打印模拟三实测→固化。

**6. 怎样保证整篇论文图形视觉统一？**
结构上杜绝分叉：所有 provider 从同一 `figure_style` 取常量（STY-05 扫描散写即 FAIL）；VIS-12 跨图一致性机检（字体族/字阶/线宽/色板/题注格式）；同类型图共享 FIGURE_TYPES 结构参数；mermaid 也注入同主题；golden samples 作家族参照。统一性成为 gate 域，不靠自觉。

**7. 怎样让 Agent 自己判断"这张图是否真的好"？**
七层 QA 链每层可证伪（T2 每项带 FAIL 负例），REGENERATION 闭环让 Agent 依据具体失败项做**有方向的**修正（拆图/转置/换安全色/忠实重绘）而非重掷骰子；3 次不过诚实升级 NHR。Agent 的"好"= 通过全部可机检层 + 无 Critical + 目检样张待确认——而不是"程序没报错"。

**8. 怎样避免"机器测试 PASS，但人看起来很丑"？**
三道防线：①**度量诚实**——不可机检项一律 NHR/SKIP，删除一切恒 True（丑图无法从自证项拿分）；②**代理度量**——丑的可量化面（密度、留白、平衡、对比、色相数、禁项）全部 VIS 化并有负例；③**双轨验收**——E2E 强制 machine QA + 人目检样张（pair/golden 对照），VERIFIED 含视觉层；主观面（"像不像海报"）明确交给人，不假装机器能判。丑不再能藏在"PASS"后面。
