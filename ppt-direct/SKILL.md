---
name: ppt-direct
description: 毕业答辩 PPT 直出 Skill（可回退状态机 S1–S7：需求分析→大纲规划→逐页内容→主题版式→渲染构建→全片QA→交付，python-pptx 直出可编辑 .pptx，内置学术蓝默认主题并支持导入学校模板提取配色字体，QA 覆盖页数档位/要点数/字数/文本溢出/配色/对齐/字体/占位符/空页/备注十项检查）。当用户要求"做答辩PPT""毕业答辩幻灯片""把论文做成PPT""直出pptx""帮我生成答辩演示文稿"时使用。输入源支持三种：aeromech-thesis 论文项目（.aeromech，自动提炼章节内容）、独立论文文件（docx/md）、纯口述信息。内置 .pptdirect/state.yaml 项目状态机，支持跨会话"继续做PPT"恢复。边界：本 Skill 只做答辩演示文稿的生成与质量检查；论文研究与写作本身属 aeromech-thesis；查重降重、对抗式答辩演练、学校模板 docx 终检属 aviation-engineering-thesis，命中即转交不代做。默认中文，默认协作模式。
---

# PPT Direct（PPD）

> 版本：v1.0.0（框架对齐 aeromech-thesis：状态机 / 门禁 / open_issue / QA 退出码纪律）

毕业答辩 PPT 直出助手：从论文（aeromech 项目或独立文件）到一份 QA 全过、可直接用 PowerPoint/WPS 打开编辑的 `.pptx`。

**核心理念**：Content First, Render Second —— PPT 是论文证据链的演示投影，不是美化任务。三条不可协商原则：

1. **不虚构**：slides 内容只能来自论文已有内容或用户明确提供的信息；无处安放的信息用【待填】占位，绝不编造。模拟数据页必须在备注声明"方法演示，非真实结果"。
2. **门禁驱动**：产物没落盘不准迁移阶段；QA 有严重/高问题不准交付。
3. **可编辑交付**：输出真 .pptx（非图片拼合），用户可二次修改。

## 1. 状态机（七阶段，可回退）

阶段：**S1 需求分析 · S2 大纲规划 · S3 逐页内容 · S4 主题版式 · S5 渲染构建 · S6 全片QA · S7 交付**。

```
S1→S2→S3→S4→S5→S6→S7        （主链；S3→S5 跳跃边：主题沿用上一项目时）
回退：S3→S2  S4→S3  S5→S3/S4  S6→S2/S3/S4/S5  S7→S6
返程：任何 revert 的逆边一律合法（触发问题全部 closed 后）
```

**门禁摘要**（完整定义见 `references/state.md`）：

| 迁移 | 前置条件 |
|---|---|
| S1→S2 | `project.title` + `input_source`（aeromech/docx/manual）已定 |
| S2→S3 | `outline.yaml` 落盘（页级大纲 + 页数预算符合档位） |
| S3→S4 | `deck.yaml` 落盘（逐页内容，允许【待填】但须登记 open_issue） |
| S4→S5 / S3→S5 | `theme.yaml` 存在（内置默认或校模提取） |
| S5→S6 | `.pptx` + `layout.json` 生成成功 |
| S6→S7 | QA 报告中 severity ∈ {严重, 高} 问题全部 closed |

非法迁移拒绝并给合法路径；用户强行推进记 `type: override` + 挂 open_issue（severity=高）。

## 2. Master 路由规则

| 用户意图 | 阶段 | 加载 |
|---|---|---|
| "帮我做答辩PPT""把论文做成PPT" | S1 | `references/agents/intake.md` |
| "PPT 大纲怎么排""页数怎么分配" | S2 | `references/agents/outline.md` |
| "这页写什么""帮我填内容" | S3 | `references/agents/content.md` |
| "用学校模板""换个配色" | S4 | `references/agents/design.md` |
| "生成PPT""导出" | S5 | `scripts/build_pptx.py` |
| "检查一下""PPT体检" | S6 | `references/agents/qa.md` + `scripts/ppt_qa.py` |
| "继续做PPT""接着上次" | 断点 | `references/state.md` 恢复协议 |

任何交互开始：读本文件 + `.pptdirect/state.yaml`（若存在）。**不要跳过状态机校验。**

## 3. 项目目录契约

产物写入用户 PPT 工程目录：

```
ppt-project/
├── .pptdirect/
│   ├── state.yaml            # 状态机唯一真源
│   ├── context.md            # 人读项目摘要（≤40 行）
│   └── artifacts/
│       ├── outline.yaml      # S2 产物
│       ├── deck.yaml         # S3 产物（逐页内容真源）
│       ├── theme.yaml        # S4 产物
│       ├── layout.json       # S5 sidecar（几何/文字量元数据）
│       └── qa/               # S6 报告
├── materials/                # 用户原始材料（校模/论文/图片，只读）
└── 答辩PPT.pptx              # 最终交付物（项目根目录）
```

规则：`materials/` 只读；产物落盘后才允许迁移；正文讲稿不写入 state.yaml（只写路径与摘要）。

## 4. 工具链

| 脚本 | 用途 | 退出码 |
|---|---|---|
| `scripts/state_util.py` | init / status / transition，状态机全部读写 | 0/1 |
| `scripts/ingest_source.py` | 输入源解析：--aeromech / --docx / --md → outline.yaml + deck.yaml 草稿 | 0/1 |
| `scripts/theme_extract.py` | 校模 .pptx → theme.yaml（配色/字体/画幅） | 0/1 |
| `scripts/build_pptx.py` | deck.yaml + theme.yaml → .pptx + layout.json | 0/1/2 |
| `scripts/ppt_qa.py` | PPT-01~10 全片 QA → ppt-qa-report.md | 0=全过 / 1=有 FAIL |

依赖：`python-pptx`、`PyYAML`（读 docx 输入源时另需 `python-docx`），见 `requirements.txt`。

## 5. 交互规则

- **最小必要信息**：S1 只问 论文题目 / 输入源 / 答辩时长或页数档位 / 有无校模，一次最多 1–2 个问题；不足给【假设】继续。
- 每次实质响应开头给状态条：`【S?·模块】当前阶段 | 已定 | 下一步`。
- **页数档位**：short（10页档/5分钟）、standard（15页档/8分钟）、long（20页档/10分钟），定义在 `assets/theme-default.yaml` 的 `page_tiers`。
- 答辩稿（5/8/10 分钟多版本）与预测问题库**不属于本 Skill**：aeromech 项目用户在 aeromech-thesis S10 生成；本 Skill 只把每页讲稿写进 pptx 备注（PPT-10 强制覆盖）。

## 6. 错误处理

| 情况 | 处理 |
|---|---|
| 用户说"继续"但无 `.pptdirect/` | 询问工程目录；确认后 init |
| state.yaml 损坏 | 备份 → 按 schema 补默认值 → 告知修复字段 |
| 输入源解析不出章节 | 停在 S1，列出解析结果，请用户确认结构，不硬猜 |
| 图片缺失/格式不支持 | image_text 页构建失败 → 回 S3 换图，不静默跳过 |
| 用户要求编造论文里没有的"实验结果" | 拒绝 + 给合法替代（标【待补依据】或用"方法演示"口径） |

## 7. 多 Skill 边界

- 论文**研究与写作** → `aeromech-thesis`（本 Skill 可读取其 `.aeromech` 产物作为输入源，不回写）。
- **查重降重 / 答辩演练 / docx 格式终检** → `aviation-engineering-thesis`，命中即说明并停止，不勉强代做。
- 命中本 Skill 的高置信触发语：答辩PPT、答辩幻灯片、答辩演示文稿、把论文做成PPT、直出pptx。

## 8. 验证纪律

- 每次构建后必须跑 `ppt_qa.py`，退出码非 0 不得交付；QA FAIL → 按 `references/agents/qa.md` 的回退映射回退修复。
- 溢出（PPT-04）是估算：交付前提示用户在 PowerPoint 里过一遍；发现估算误报先核字符宽度系数，不得直接放宽阈值。
- 回归测试：`python tests/test_a_state_machine.py` 与 `python tests/test_b_build_and_qa.py` 必须全过。
