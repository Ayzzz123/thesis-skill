# v1.6.5 — V1.6.5_FIGURE_TYPE_SPEC（九类图专门规范）

每类图定义六要素：visual structure / color rule / typography rule / spacing rule /
hierarchy rule / label rule（+ caption rule 统一引用 02-G）。
所有规范值从 `figure_style.py` 取，类型差异体现为**阈值与结构参数**，不是各自散写样式。

---

## 1. Fault Tree（故障树）— 本项目重点

- **visual structure**：严格三层——顶事件（Top）→ 中间事件/门（Gate）→ 底事件（Basic Event）。
  垂直流（顶在上），同层水平排列；子树左右平衡（节点数差 ≤1）。
- **hierarchy rule**：三层视觉权重递减——Top 用 `Primary` 描边+`Fill` 底+12pt；
  Gate 用 `Secondary` 描边+11pt；Basic 用 `Neutral` 描边+11pt。**一眼可辨层级**。
- **AND/OR 区分**：门节点标注文字 "（AND）/（OR）"（test-8.0 已验证有效）+ 形状差异
  （AND 拱形/方框、OR 月牙/圆角框），**不靠颜色**（灰度可辨）。
- **connector routing**：正交折线优先；禁止交叉（交叉→重排子树或拆图）；
  连线不穿任何文本/节点框（GQ-02/03 已测，保留）。
- **color rule**：默认全中性蓝灰族；仅当某底事件是"最小割集强调对象"时用一次 `Accent`
  或 `Risk`（每图 ≤1 语义）。
- **label rule**：底事件="编号 短名"（E1 EDP磨损内泄），编号与正文表（如表2-1）一致（D10 核对）。
- **密度上限**：底事件 ≤ 10、门 ≤ 6；超出→拆成多棵树（如 T1/T2 分树，test-8.0 做法正确）。
- **caption**：双语题注 + 逻辑式引用（"完整树形如图3-1所示，逻辑式（3-1）"）。

## 2. Flow / Technical Route（技术路线图）

- 单向主干（自上而下或自左而右，全论文统一）；阶段框等宽；分支仅在有真实并行时出现。
- 主干 `Primary`，阶段底 `Fill`，产物/输出节点 `Secondary`；箭头 `Line`。
- 每框 ≤2 行文字；阶段编号（S1/S2…）与正文技术路线小节一致。
- 禁止把"目录式罗列"画成图——每框必须是流程节点（有入/出语义）。

## 3. Statistical Chart（通用统计图）/ 4. Bar Chart（柱状图）

- **Data Integrity 最高优先**：数值/类别/顺序与 datasets 登记一致（D10 回环核对：
  QA 从图脚本的源数据文件重算 → 与图中柱高/标签比对）。
- 柱：单色 `Primary` 或 `Fill+Primary 描边`；**禁止每柱一色**（类别已由 x 轴标签给出）。
  强调柱（如最高风险）允许一次 `Accent`。
- 轴：仅左轴+底轴（去顶/右 spine，minimal）；网格线 `Grid` 横向细线，不加密。
- y 轴从 0 起（柱状图截断 y 轴=误导，Critical）；刻度 4–6 个；单位入轴标题。
- 数值标签：柱顶直标（test-8.0 做法保留），字号 ≥10，不与邻柱碰。
- 模拟数据：图内水印行"【假设/模拟·仅演示方法】构造演示数据，不代表真实统计"（诚信，题注同步）。

## 5. Line Chart（折线/曲线图，如可靠性 R(t)）

- 每条线=一个语义系列；系列 ≤4；线型（实/虚/点/点划）+ 标记（●■▲◆）双编码，
  颜色仅做次要区分（同族蓝灰明度阶）。
- 轴同 §4；曲线不截断 y 轴；置信带（如有）用 `Fill` 低透明，不抢主线。
- 图例放右上或图外，禁压线（GQ 图例覆盖检查已有）。

## 6. Decision Matrix（决策矩阵/象限图）

- 2×2 或 n×m 网格：单元格底 `Fill`，行列头 `Secondary` 描边；
  象限语义色**最多 2 档**（如"双高"= `Risk` 浅底、其余中性），避免四象限四色。
- 单元格内文字 ≤2 行；轴标题给出排序依据（如"诊断序↑/策略序↑"）。
- 与正文表（如表4-3）内容一致（D10）。

## 7. Architecture / System Diagram（系统结构图）

- 分层/分块：功能层用等距水平带；组件框 `Fill`+`Primary` 描边；层名 `Secondary` 11pt。
- 接口线 `Line`，方向=能量/信号流；禁止无方向装饰线。
- 与正文"系统组成"小节逐项对应（D10）。

## 8. Comparison Diagram（对比图，如方法对比/前后对比）

- 左右或上下并置，共享轴/共享尺度（不共享尺度=误导，Critical）。
- 两方案用 `Primary` vs `Neutral`（或实线 vs 虚线），**不用红绿对立**。

## 9. Research Framework Diagram（研究框架图）

- RQ→方法→数据→结论的映射网：节点按角色着色（RQ=`Primary`、方法=`Secondary`、
  数据=`Neutral`、结论=`Accent` 一次），边=支撑关系。
- 与 rq/design/scope 注册表一致（D10 可机核：节点标签 ⊆ 注册表 id/名称）。

---

## 类型分派与验收钩子

- `figure_style.FIGURE_TYPES[type]` 给出该类型的：结构参数（层数/密度上限）、
  色预算、字阶、间距阈值、专属 Critical 规则（如柱状图 y 轴从 0、对比图共享尺度）。
- VIS-11（类型适配性）按类型选规则；VIS-12（跨图一致性）检查同论文同类型图参数同源。
- 每类图各建 1 张**参考样张**（golden sample，含 layout JSON），作为视觉回归基线（06 文档）。
