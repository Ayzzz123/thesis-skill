# v1.6.5 Phase 1 — 进度快照（2026-09-17 日终保存，次日续接用）

分支：feature-1.6.5-figure-optimization（本地，未 push；master 未动）
Phase 0 commit：11b1b24（审计文档，已提交）
Phase 1 状态：进行中，本次保存为 WIP commit（消息见 git log）

## 已完成（本日）

1. **scripts/figure_style.py（新）** — 视觉单一来源
   - 调色板经三轮量化验证固化（text-on-fill ≥4.5 实测 9.9–14.8；描边-on-fill ≥3.0；
     相邻填充灰度 ≥0.12；饱和 ≤0.45/强调 ≤0.55）；`validate_palette()` 返回 [] 才允许固化
   - SEMANTIC_COLORS（角色→stroke/fill/text）、TYPOGRAPHY（XL–XS 字阶，底线 9pt）、
     LINE_STYLES、SPACING、FIGURE_SIZE_PRESETS、FIGURE_TYPES（9 类）、
     contrast_ratio/grayscale_delta/saturation/hue_of、scan_hardcoded_styles（散写 HEX 扫描器）
2. **figkit 迁移** — 全部颜色/字号/线宽取自 figure_style；box/box2 新增 role=（兼容旧 fc/ec）；
   layout JSON 输出 fill/stroke/text_color/role + style_fingerprint（VIS-12 输入）；hex 扫描=0
3. **§六 Critical：mermaid fallback 语义造假根除**
   - generate_fallback_figure（画通用假故障树+size>5000 判成功）→ 删除
   - 新增 generate_diagnostic_placeholder：永远返回 (False,...)，DIAGNOSTIC 大字标记，永不判成功
   - figure_iface._gen_mermaid：mmdc 失败 → 清理残缺文件 → REJECTED（FIGURE_ERROR，不 VERIFIED）
   - CLI 退出码语义更新：0 仅真实渲染；2=FIGURE_ERROR
4. **§七 自证 PASS 删除**
   - figure_table FIG-05/06：恒 True → SKIP（有 layout 元数据→指向 GQ-01/02/03 真测；无→人工目检）
   - graph_quality GQ-15：恒 True → SKIP（人工步骤，机器不判定）
   - 两文件退出逻辑本就 ok or skip，保持绿
5. **scripts/figure_visual_qa.py（新）** — VIS-01~12 第一版
   - 可测：VIS-01 平衡、02 密度(ink 实测)、03 字阶+有效字号、04 白名单+色相预算+饱和、
     05 对比、06 语义色、07 留白、08 对齐、09 禁项(纯色白名单代理)、10 PDF 渲染(比例+文档序
     匹配修复：多图不再全配同页)、11 类型适配、12 跨图指纹
   - 不可靠机检 → NEEDS_HUMAN_REVIEW/SKIP（不伪装 PASS）；每项带方向性 suggestion
   - quality_score 仅展示；FAIL 存在时退出码 1
   - 报告行格式兼容 delivery_gate 的 `- CODE 名称: ST | ev` 解析

## 首跑真实结果（test-8.0 旧图，未重绘前）——这是 §十四 的工作清单

- VIS-10 三图 PASS（p19/p20/p28 各自匹配，有效字号 9.6–10.5pt，无裁切）
- **VIS-07 三图 FAIL**：旧图元素贴边/越界（fig3-1 左 0.10/下 -0.01/上 0.30 <0.45cm；
  fig3-2 上 0.30；fig4-1 下 0.13）——旧脚本本就贴边，重绘时按 SPACING.figure_margin 内缩
- VIS-01 fig3-1/3-2 WARN：左右留白比失衡（E5 绕行线拉宽右缘）→ 重绘时修路由
- VIS-04/05/06/09 SKIP、VIS-12 SKIP：旧 layout JSON 无颜色/role/指纹元数据（重绘后自动激活）
- VIS-11 SKIP：figure-plan 无 type 字段 → 重绘时在 plan 登记 type

## 明日续接（按序）

1. **§十三 golden samples**：tests/v1_6_5/golden/ 生成 4 类样张（fault_tree/stat_bar/tech_route/
   stat_line），用 figkit role API 忠实绘制 + 布局守 SPACING（顺带作为 §14 重绘的版式模板）
2. **§十六 tests/v1_6_5/**：STY（含 scan 负例）、color 验证、typography、
   **MERMAID-FALLBACK-CRITICAL**（render_with_mmdc 失败→figure_iface 必须 REJECTED、
   不落 VERIFIED、placeholder 返回 False）、VIS 合成负例（贴边→FAIL、非白名单色→FAIL、
   语义错配→FAIL、单页匹配）、golden 一致性（VIS-12 PASS）
3. **§十四 test-8.0 三图重绘**（只改视觉不改研究数据）：
   - fig3-1：E5 绕行线改内部路由/缩短、内容内缩 ≥0.45cm、左右平衡
   - fig3-2：上边距修正；两树同版式同指纹
   - fig4-1：去四边框（仅左/底 spine）、y 轴从 0、留白达标
   - 重跑 pipeline → VIS 全绿（VIS-09/12 激活）→ 人工目检 pair 样张
4. **接入**：figure_visual_qa 挂入 thesis_build qa 链（第 11 步 figure_visual）+
   delivery_gate FORMAT_REPORTS 增 figure-visual-report.md 域 + orchestration.md/SKILL 文档同步
5. 全量回归（v1_4/4_1/5/6 + a/b + test-8.0 gate）→ Phase 1 报告 → 停止等指令

## 边界遵守记录

未 push/merge/PR/release；未改研究结论/数据/测试期望值；test-8.0 论文正文未动
（重绘仅换图形 PNG/脚本，图题与数据口径不变）。
