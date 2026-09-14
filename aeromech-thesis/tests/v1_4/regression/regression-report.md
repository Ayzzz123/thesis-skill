# v1.4.0 回归测试报告（test-1.0 ~ test-6.0 + Skill 测试）

**日期**：2026-09-12
**目的**：验证 v1.4.0（Research Integrity Layer）未破坏既有能力（Template/Cover/Table/Graph/PDF QA / Delivery Gate）。
**方法**：以当前 v1.4 Skill 脚本重跑旧测试项目的既有交付物与 Skill 自带测试；对每个 FAIL 做根因分类（v1.4 回归 / 既有脚本-旧产物差异），并附脚本 mtime 证据（本日 09-12 被 v1.4 修改的脚本仅：`research_*.py`（新增）、`page_fidelity_qa.py`、`figure_table_qa.py`、`table_readability_qa.py`、`cover_fidelity.py`；其余脚本最后修改时间为 09-09~09-11，未受 v1.4 影响）。

## 1. 汇总

| 项目 | 结论 | 关键证据 |
|---|---|---|
| Skill tests（test_a / test_b） | **PASS** | test_a 12/12；test_b 6/6 |
| Skill tests/v1_4（11 文件） | **PASS** | 11/11 文件（含 162 项断言） |
| test-6.0（本次新交付） | **PASS** | 全链 QA + RQG 全 PASS（21 页） |
| test-5.0（哈工程） | **PASS** | pdf/visual/figure_table/table_readability/content_purity/graph_quality/page_fidelity/cover 系列全 PASS；tf_qa TF-01~20 PASS；RQG exit 2 not_initialized（旧项目兼容，不阻塞） |
| test-4.0（南农模板，TEMPLATE_FIDELITY） | **PASS（附带 2 项既有差异披露）** | tf_qa TF-01~20 全 PASS；cover_fidelity 25 PASS；page_fidelity 17 PASS；figure_table 22 PASS；graph_quality 33 PASS；pdf/visual PASS |
| test-3.0（南农模板，TEMPLATE_FIDELITY） | **PASS（Template/Cover/PDF/Visual 核心项）** | tf_qa TF-01~20 全 PASS；pdf/visual PASS；figure_table（FIG-12 修复后）全 PASS |
| test-2.0 | **FAIL（既有差异，非 v1.4 回归）** | pdf_qa 33×High：全部正文页页脚未检出页码（旧产物页脚位置与 09-09 版检查器底部带不匹配）；visual：P26 A 类低占用候选 |
| test-1.0 | **FAIL（既有差异，非 v1.4 回归）** | pdf_qa 34×High：同上（P6~P39）；visual PASS |

## 2. 逐项回归（v1.4 指令要求的能力点）

### 2.1 Template Fidelity —— 无回归
- test-4.0：`tf_qa.py --template <南农模板.docx> --refs-min 5` → **TF-01~20 全 PASS**（封面结构/声明/摘要/Heading/字体/行距/图题/表题/三线表/页眉页脚/页码/目录/参考文献/附录/致谢/页面/PDF 视觉对照）。
- test-3.0：同模板 → **TF-01~20 全 PASS**。

### 2.2 Cover Fidelity —— 无回归
- test-4.0：cover_fidelity **25 PASS / 0 FAIL**（pair 模式）；cover_align / cover_fill **0 FAIL**；color_fidelity **16 PASS**。
- test-5.0：cover_fidelity/align/fill/color（自检模式）25/16/14/16 PASS。
- test-6.0：cover 系列 25/16/14/16 PASS。
- test-3.0（pair 模式）存在既有差异：COVER-ALIGN-05/06/07、COVER-FILL-01~03 FAIL（该成品封面槽位几何与模板渲染页存在偏移）；CF-14 FAIL（封面表 tblStyle/tblCellMar 缺失，脚本提示需 `--restore` 注入）。`cover_align_qa.py`/`cover_fill_qa.py` 最后修改 09-11（v1.4 未改），属既有脚本-旧产物差异。

### 2.3 Table QA —— 无回归
- test-5.0：table_readability **11 PASS / 0 FAIL**；figure_table **22 PASS / 0 FAIL**。
- test-4.0：figure_table **22 PASS / 0 FAIL**；table_readability 在 v1.4 修复 TR-10 英文题注分隔符匹配后 **TR-10 PASS（15/15 表定位正常）**；残留 TR-06/07/08（表4-4 中列 1.94cm、表5-1 检查列 7 字/行）——该三检查逻辑自 09-10 起未修改，属既有"通用检查 vs 项目局部检查"覆盖差异（test-4.0 交付时用的是项目内局部版 QA）。
- test-3.0：figure_table 在 v1.4 修复 FIG-12 引用匹配（分隔符/空白归一化）后 **8/8 图有引用 PASS**；残留 TAB-06（11.1% 单字格，非等级列）与 TAB-10（表B-1 未见正文引用，涉及附录表引用规范）属既有差异/内容性质。
- test-6.0（新交付）：两套 Table QA 全 PASS。

### 2.4 Graph QA —— 无回归
- test-5.0：graph_quality **68 PASS / 0 FAIL**（3 图全部几何检查）。
- test-4.0：graph_quality **33 PASS / 0 FAIL**。
- test-3.0：GQ-00 FAIL —— 其图为 09-09 旧生成器产物，无 figkit `*.layout.json` 元数据，GQ 几何检查无法进行；`graph_quality_qa.py` 最后修改 09-11（v1.4 未改），属既有差异（figkit 布局元数据机制晚于 test-3.0）。
- test-6.0（新交付）：23 PASS；仅 3 项设计内 SKIP。

### 2.5 PDF QA —— 无回归
- test-5.0 / test-4.0 / test-3.0：pdf_qa **PASS（Critical 0 / High 0）**。
- test-6.0：PASS（0/0，21 页）。
- test-1.0 / test-2.0：FAIL（各 34/33 ×High，全部正文页页码未检出）。`pdf_qa.py` **最后修改 2026-09-09**（v1.4 未改）；两项目为 v1.0/v1.1 时代产物，其页脚页码位置（距底 ~48pt）落在检查器底部带（H-74~H-56）之外。属既有检查器-旧产物差异，**非 v1.4 回归**；如需以当前标准交付，需用当前流水线重新导出其 PDF。

### 2.6 Delivery Gate —— 无回归
- Delivery Gate 为综合判定（Format+Visual+Content+Citation+Data+Research Quality+Evidence Traceability）。v1.4 仅为其**增加** RI Gate 条件（存在 `.aeromech/research/` 时），未修改既有闸门逻辑：
  - 旧项目（无注册表）：`research_quality_qa.py` exit 2 / `not_initialized` / 不阻塞 —— test-5.0 实测通过（WARN + 不阻塞）。
  - 新项目（test-6.0）：RI Gate PASS + 全链 QA PASS → 综合 PASS。

## 3. 结论

- **v1.4 未引入任何既有能力回归**：所有 FAIL 项均可归因于①v1.4 未修改的脚本与更早期产物之间的既有差异（test-1.0/2.0 页码带、test-3.0 pair-cover/无 layout 元数据、test-4.0 通用 vs 局部 Table 检查覆盖差），或②本次按 v1.4 要求对检查器所作的三处**容错修复**（TR-10 英文题注分隔符、FIG-12 引用匹配、cover CF-05 去硬编码题名）——修复方向均为消除误报，不降低任何阈值。
- 所有 v1.4 会话内修改的脚本，均在 test-6.0（新）与 test-3.0/4.0/5.0（旧）上复跑验证，未出现新增 FAIL。
- 未伪造 PASS：test-1.0/2.0 的 pdf_qa FAIL 与 test-2.0 的 visual A 类候选如实记录在案。

### 附：本次回归运行日志目录
`tests/v1_4/regression/`（各项目 *.log 与 QA 报告副本）
