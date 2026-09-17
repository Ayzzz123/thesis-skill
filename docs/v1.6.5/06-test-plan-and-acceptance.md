# v1.6.5 — TEST_PLAN + ACCEPTANCE_CRITERIA

## 一、测试分层（新增 `tests/v1_6_5/`，不改既有测试期望值）

**T1 单元（figure_style 纯函数，无渲染）**
- STY-01 PALETTE/SEMANTIC/FONT/FONTSIZE 常量齐备且类型正确
- STY-02 contrast_ratio 已知对（Text/Fill=13.2、Accent/Fill=3.44）与手算一致
- STY-03 grayscale_delta 阈值判定（Secondary/Primary=0.096<0.12 触发"不可作相邻填充"）
- STY-04 ink_ratio / 色相计数 / 饱和度上限 纯函数边界
- STY-05 **禁散写检查**：扫描 figkit/provider 源码，出现字面 HEX/裸 fontsize= 而未经
  figure_style → FAIL（结构防回潮，堵 D3/D4）

**T2 VIS 度量（合成 layout JSON + 合成 PNG，可证伪）**
- VIS-01 平衡：故意把内容堆一角 → 偏移超阈 FAIL；居中 → PASS
- VIS-02 密度：塞 20 节点/ink>45% → FAIL；正常 → PASS
- VIS-03 可读：注入缺字（tofu）样例 / 有效字号 8pt → **Critical**；正常样例集（中英数/单位/
  上下标/DOI/标准号）→ PASS
- VIS-05 对比：白字浅底 → FAIL；Text on Fill → PASS
- VIS-06 语义色：同角色跨图异色 → FAIL；同 SEMANTIC → PASS
- VIS-09 禁项：合成含渐变/阴影图元 → FAIL
- VIS-11 类型适配：柱状图 y 轴不含 0 → **Critical**；故障树 AND/OR 仅靠颜色（无文字/形状）→ FAIL
- VIS-12 跨图：两图字体族不同 → FAIL
- **反自证测试**：构造"无 layout JSON 的位图"→ FIG-05/06/GQ-15 必须 NHR/SKIP，
  **不得返回 True**（堵 D1；这是回归锁，防退化回恒真）

**T3 DATA 回环（D10）**
- DATA-01 柱高与源 CSV 重算比对：一致→PASS；篡改柱高→FAIL；改顺序→FAIL；缺类→FAIL
- DATA-02 数据源缺失/不可读 → ERROR（不猜、不 PASS）

**T4 闭环（REGENERATION）**
- LOOP-01 首次 FAIL(拥挤)→自动拆图→第2次 PASS，attempt 记录完整
- LOOP-02 连续 3 次仍 Critical → NEEDS_HUMAN_REVIEW，**不再第 4 次**（不无限循环）
- LOOP-03 数据不符 → 回退源重画，绝不"改数据迁就图"

**T5 端到端（真实样本，任务 §十四）**
- E2E-01 test-8.0 三图重跑：fig3-1/3-2（故障树）+fig4-1（柱状）经 VIS 全链，
  产出 VIS 报告 + 样张；VERIFIED 现含视觉合格
- E2E-02 生成→DOCX 嵌入→**最终 PDF 300dpi** 实测（VIS-10）：三图无裁切、有效字号达标、
  显示宽在目标区间
- E2E-03 跨图一致性：test-8.0 三图字体/配色/线宽/题注同源（VIS-12 PASS）
- E2E-04 **machine QA + 人工目检双轨**：自动全 PASS 后，仍出 pair 样张交人确认
  "是否像专业学术图"（§十六 要求；不可仅 unit test）

**T6 回归（不破坏既有）**
- 全量：v1_4 / v1_4_1 / v1_5 / v1_6 / test_a / test_b / test_document_contract 保持绿
- test-8.0 delivery_gate 保持 PASS（新增 figure_visual 域不得把已验收图误判 FAIL；
  若误判=度量太严，调**度量**而非降标准/改期望）
- dev↔install IDENTICAL

## 二、ACCEPTANCE_CRITERIA（v1.6.5 成功判据，逐条可验）

AC-01 figure_style.py 单一来源；全仓图形脚本零散写 HEX/字号（STY-05 扫描通过）
AC-02 D1 三处恒 True 项已消除：能测则真测、不能测则 NHR/SKIP（反自证测试 T2 通过）
AC-03 D2 mermaid fallback 语义造假已消除：fallback 不得产出与真实模型无关的图；
       无法忠实渲染→FIGURE_ERROR/REJECTED，绝不 size>5000 即判成功
AC-04 VIS-01~12 全部实现且可证伪（T2 每项有 FAIL 负例）
AC-05 DATA 回环（D10）实现，篡改数据能被测出（T3）
AC-06 REGENERATION ≤3 次 + NHR 出口（T4），不无限循环
AC-07 跨图一致性（D6）：test-8.0 三图 VIS-12 PASS；混入异风格样图能被测 FAIL
AC-08 PDF 最终真相（§十三）：VIS-10 在导出 PDF 上实测，非仅 PNG
AC-09 Critical 不被总分掩盖：构造"高分+一个 Critical"样图 → gate=BLOCK
AC-10 九类图各有 FIGURE_TYPES 规范 + 至少每类 1 张参考样张（golden sample）
AC-11 全量回归绿 + test-8.0 delivery_gate=PASS + dev↔install IDENTICAL
AC-12 未改任何既有测试期望值/论文结论（diff 审查 + 记录）

## 三、明确不做（边界）
- 不 push / merge / PR / GitHub Release（任务 §一-5）
- 不为单篇/单例写特判（§十五-8/9）
- 不引入渐变/阴影/3D/彩虹（§十五-1..6）
- 不默认继承"协作者 Figure Engine"（审计已证：无独立实现可继承）
- 不修改 TEST-8.0 论文研究结论（§一-6）
