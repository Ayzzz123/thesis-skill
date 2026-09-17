# v1.6.5 — V1.6.5_REGENERATION_LOOP（生成→检查→重生成闭环）

目标：把一次性 generate 升级为带反馈的闭环，Agent 能自判"这张图是否真的好"，
且**不无限循环、不靠改期望蒙混**。

## 流程（任务 §十一 落地）

```
PLAN (figure_iface.plan_figures，含 type 分派)
  ↓
SELECT_FIGURE_TYPE  ← FIGURE_TYPES[type] 载入结构参数+阈值+专属 Critical 规则
  ↓
GENERATE            ← provider 从 figure_style 取样式常量（禁散写 HEX/字号）
  ↓
SEMANTIC_QA         ← 图题/节点/引用 vs 正文（FIG-12/13 + RQG）
  ↓
DATA_QA             ← data_source 回环重算（04 文档 DATA 层，D10）
  ↓
GEOMETRY_QA         ← GQ-01~14（复用，不重造）
  ↓
VISUAL_QA           ← VIS-01~12（04 文档）
  ↓
ACADEMIC_STYLE_QA   ← VIS-04/06/09/12（克制+语义色+跨图一致）
  ↓
PDF_RENDER_QA       ← VIS-10（最终 PDF 300dpi 实测，§十三）
  ↓
PASS  → record VERIFIED（含视觉合格，非仅几何）
```

## 失败处理：REGENERATE（≤3 次）

- 任一 **Critical**（VIS-03 缺字/裁切、VIS-10 裁切/糊、VIS-11 误导、DATA 不一致）→ 立即不可 PASS，
  进入 REGENERATE。
- 每次重生成**必须携带失败反馈**（不是盲目重跑）：
  - 拥挤/超密度（VIS-02）→ 自动动作：拆图 / 减节点 / 转置方向 / 缩标签；
  - 交叉（故障树）→ 重排子树或拆图；
  - 有效字号不足（VIS-03/GQ-09）→ 增大生成宽或提高 min_font（不缩内容）；
  - 对比/灰度不达标（VIS-05）→ 从 PALETTE 换更安全的语义色（仍在白名单内）；
  - 数据不符（DATA）→ **不改数据迁就图**，回退到源重画（源错则 NEEDS_UPSTREAM_WORK）。
- 迭代计数存 figure-lifecycle（RETRY 记录，含 reason+attempt n/3）；**最多 3 次**。
- 3 次后仍 FAIL → `NEEDS_HUMAN_REVIEW`（附最后一次样张 + 未通过 VIS 项 + 建议动作），
  **不得无限循环、不得自动降标准、不得改测试期望**（§十五-7）。

## 与 Orchestrator/Loop 的边界

- 复用 v1.6 figure_iface 生命周期与 thesis_orchestrator 的 RUN_PENDING/AI 挂载机制；
  不新建第二套状态词（沿用 v1.4.1 七态 + gate 五态）。
- S8 出口门禁升级：从"figures_registry + figure_plan"到"每图 VERIFIED(含视觉) 或已 NHR 挂起"。
- delivery_gate 的 figure 域消费 VIS 结果（04 文档），Critical→BLOCK。

## 可观测性

- 每次 attempt 产 `out/v1.6.5/<fid>_a{n}.png` + 对应 VIS 报告，留 pair；
  重生成链可追溯（哪次因何失败、用了哪个自动动作）——禁止静默（沿用 Action 模型精神）。
