# AeroMech Thesis — 项目架构地图（维护审计版）

> 生成：2026-09-14（第一阶段只读审计）；审计基线：dev 与 install 副本逐字节一致（diff -r 零漂移，除忽略项）。
> 证据来源：SKILL.md / README.md / CHANGELOG.md / references/14 文件 / scripts/30 脚本 / tests/ / 6 个测试项目 / DEV_SYNC.md / INSTALL_SYNC.md / sync.py。

## 1. 总体分层

```
User（提供学校模板/资料/题目）
 ↓ SKILL.md frontmatter description = 领域触发判据（机械/维修词，而非流程词）
Skill Router（SKILL.md §4 意图→阶段→模块表；§3 按需加载表——禁止一次性全读）
 ↓
State Machine（references/state.md；真源 = 项目内 .aeromech/state.yaml，schema 1.0）
 │  S1 题目分析 · S2 智能选题 · S3 研究方案 · S4 文献研究 · S5 工程分析
 │  S6 数据分析 · S7 章节写作 · S8 图表规整 · S9 全文QA · S10 答辩
 │  可回退：revert 须由 open_issue/依据缺口触发，history 记 from/to/type/reason/evidence
 │  S7 门禁按 paper_type（research/review/design）三态：passed/conditional/failed
 ↓
Material Layer（.aeromech/materials.yaml：MAT-XXX 登记，authority L1–L5，verification_status；
 │              .aeromech/school-format.yaml：三层格式档案 general_principles /
 │              general_defaults(仅fallback) / school_specific_unknown；原始材料禁止修改）
 ↓
Research Layer（Agent 角色卡 references/agents/*.md：topic/research/engineering/data/
 │              writing/figure/citation/qa/defense；产物落 .aeromech/artifacts/*）
 ↓
Integrity Layer
 │  ├─ integrity.md：十条红线 + 标注体系（【待核实】/【假设/模拟·仅演示方法】/【已核实】）
 │  └─ research-integrity.md（v1.4）：.aeromech/research/ 10 注册表
 │      rq/methods/evidence/datasets/analyses/computations/claims/conclusions/figures/conflicts
 │      引擎 scripts/research_integrity.py（init/validate/trace/coverage）
 │      门禁 scripts/research_quality_qa.py（RQG-00~15 + NHR 人工复核，v1.4.1）
 ↓
Intelligence Layer（v1.5 —— 代码已存在，未发布/未接入路由）
 │  design.yaml + scope.yaml + repairs.yaml（3 新注册表，RI 引擎 REGISTRY_SPECS 扩展）
 │  research_design.py（设计一致性/方法选择审计/RF-01~10 可行性）
 │  research_diagnosis.py（19 类 issue_type 诊断 + 根因 + auto/queue/block 分流）
 │  research_repair.py（REP-XXX 计划 + 白名单 4 操作自动修复 + apply-human 裁决执行）
 │  research_agent_loop.py（PLAN→…→ACCEPT ≤5 轮闭环 + loop-log + 终态）
 │  research_quality_score.py（8 维 0-100，Critical/High 未解决 blocked=True）
 │  规则书 references/research-intelligence.md（⚠ SKILL.md §3 加载表未收录）
 ↓
Document Layer（交付链，references/delivery-pipeline.md + template-fidelity.md + cover-fidelity.md）
 │  build（docx_engine.py / template_fidelity.py 原语 + 项目层 build_docx_<project>.py）
 │  → update_toc.py（Word COM 两轮）
 │  → cover_fidelity.py --restore（tblPr 恢复）→ repaginate_tables.py（表启动块硬校验）
 │  → export_pdf.py → finalize_metadata.py（元数据中性化）
 ↓
QA 层（22 个脚本，全部带 CLI+退出码+报告落盘）
 │  tf_qa TF-01~20 · cover_fidelity CF-01~25 · cover_align 01~16 · cover_fill 01~14
 │  color_fidelity COLOR-01~16 · page_fidelity HF/AF/AT/RF · figure_table FIG/TAB
 │  content_purity MD/INT/PRM/APX/TABCAP · graph_quality GQ-01~20(+figkit layout)
 │  table_readability TR-01~14 · pdf_qa 16 项+TOC-01~10 · visual_regression 占用率 A/B 类
 ↓
Delivery Gate（delivery-pipeline.md §7-8：Critical 禁交付/High 禁终稿/Medium 披露/Low 记录）
 │  = Format+Visual+Purity+Citation+Data QA + RQG(注册表存在时) [+ v1.5 Loop——仅写在
 │    research-intelligence.md §9，SKILL.md §16 未集成]
 ↓
最终交付：毕业论文.docx + 毕业论文.pdf（PDF 为最终真值；图表嵌入文档，不单独交付）
```

## 2. 状态流

- 唯一机器真源：`<项目>/.aeromech/state.yaml`（正文/文献/数据只写路径引用，禁止内嵌）。
- 迁移校验算法在 state.md §3~§5；拒绝记录进 context.md（非 history）；override 须二次确认+open_issue。
- 备份协议 state.md §11（bak-v<ver>/bak-corrupt/bak-revert/bak-preqa，留 5 份）。
- 恢复协议 SKILL.md §7 / state.md §12（禁止重复询问已定字段；缺失标【假设】不停摆）。

## 3. 数据流（研究链，v1.4 核心）

```
RQ-XX → M-XXX(方法 basis/选择) → E-XXX(证据 verified|partial|pending|simulated)
      → DS-XXX(数据；模拟必填 reason/assumptions/generation_method/limitations/label)
      → CALC-XXX(inputs/formula/verification 三件套)
      → AN-XXX(inputs→DS/E/CALC, outputs→TABLE/FIG)
      → CL-XXX(claim_type+evidence_ids) → CON-XXX(claims/analyses/evidence 回链)
      → 摘要一致性（RQG-09 数值⊆正文/身份措辞/覆盖度）
traceability.json（引擎生成，不手写）+ Evidence Coverage（simulated 绝不并入 verified）
```
v1.5 在此链上叠加：design.yaml（needs⊆provides / evidence_requirement 事前审计）→
DIAG-XXX（稳定哈希 ID）→ REP-XXX（before/after 留痕）→ loop-log → score。

## 4. 文件流（关键产物位置）

| 流 | 位置 |
|---|---|
| 原始材料（只读） | `<项目>/materials/{school,literature,technical_manual,standard,project_data,samples}` |
| 状态 | `.aeromech/state.yaml` + `materials.yaml` + `school-format.yaml` + `context.md` |
| 研究注册表 | `.aeromech/research/*.yaml` + `traceability.json` + `human-review.yaml`（v1.4.1）+ `human-review-queue.yaml`（v1.5 loop） |
| 阶段产物 | `.aeromech/artifacts/{topic-card,research-plan,thesis-outline,literature,chapters/,analysis/,figures.md,computation/,qa/,defense/}` |
| QA 报告 | `.aeromech/artifacts/qa/`（tf-qa-report.md、research-quality-report.md、human-review-checklist.md、research-loop-log.md 等） |
| 最终交付 | 项目根：`毕业论文.docx`、`毕业论文.pdf` |

## 5. 模块调用关系（脚本层，静态 import 确认）

```
research_integrity ← research_quality_qa ← research_diagnosis ← research_agent_loop
        ↑                 (in-process run())        ↑                ├→ research_repair
research_design ─────────→(feasibility/audit)───────┘                └→ research_quality_score
build_docx(项目层) → docx_engine ← template_fidelity ← tf_qa
交付链 CLI 顺序：build → update_toc → cover_fidelity --restore → repaginate_tables
→ export_pdf → {pdf_qa, visual_regression, tf_qa, cover_*, color, page, figure_table,
content_purity, graph_quality, table_readability} → finalize_metadata → Delivery Gate
```

## 6. Skill 仓库自身的元结构（本目录）

```
Desktop/thesis-skill/               ← 开发工作区（非 git 仓库）
├── aeromech-thesis/                ← DEV（权威编辑源）
│   ├── SKILL.md v1.4.1(49KB) README.md CHANGELOG.md(至 v1.4.1)
│   ├── references/（14 md + agents/9 + knowledge/6 + templates/3）
│   ├── scripts/（30 py：7 研究层 + 23 交付/QA层）
│   └── tests/（test_a/test_b + v1_4(13) + v1_4_1(7) + v1_5(16，未运行证据)）
├── sync.py（v1.4.1 建立，v1.5.0 加固：4 道删除护栏 + dry-run + --force）
├── DEV_SYNC.md / INSTALL_SYNC.md（同步规程 + 2026-09-12 事故记录）
└── .aeromech/artifacts/analysis/   ← 本审计产物目录
~/.qoder-cn/skills/aeromech-thesis/  ← INSTALL（运行副本，实际加载处；与 dev 零漂移）
```
