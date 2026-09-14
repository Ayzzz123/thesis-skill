# AeroMech Thesis — 当前项目状态报告（第一阶段只读审计）

> 审计人：新维护 Agent（接手理解阶段）。审计日：2026-09-14。
> 全程只读：未修改任何 Skill 代码/文档/注册表；未运行 sync 或任何脚本（仅 diff/find/read）。

## 1. 当前版本是什么

- **发布口径（文档声明）：v1.4.1 — Stability & Production Hardening**
  （SKILL.md 版本行、README.md §11、CHANGELOG.md 顶部条目三者一致）。
- **代码实际状态：v1.5.0（Research Intelligence & Agent Loop）已实现但未发布**——
  5 个新脚本自标 v1.5.0（research_design/diagnosis/repair/agent_loop/quality_score），
  research_integrity.py 已扩至 13 注册表，references/research-intelligence.md 规则书在，
  tests/v1_5/ 16 个文件在，sync.py 护栏注明"v1.5.0 加固"。
  **但 CHANGELOG 无 v1.5.0 条目，SKILL.md 未接入 v1.5（§3 加载表/§4 路由/§16 Gate 均不提），
  tests/v1_5/ 无任何运行证据（无 report/log/pycache）。**
- 结论：v1.4.1 = 已验证发布基线；v1.5.0 = 代码完成、验证与集成缺失的在制品（WIP）。

## 2. 当前代码在哪里

- 权威开发源（DEV）：`C:\Users\29603\Desktop\thesis-skill\aeromech-thesis`
  （SKILL.md + README + CHANGELOG + references/14文件+agents9+knowledge6+templates3 + scripts/30 + tests/）。
- 工作区上层：`C:\Users\29603\Desktop\thesis-skill\`（sync.py、DEV_SYNC.md、INSTALL_SYNC.md）。

## 3. 当前安装版在哪里

- `C:\Users\29603\.qoder-cn\skills\aeromech-thesis`（Qoder CN 技能加载目录）。
- 独立核验（未跑 sync）：`diff -r`（排除 __pycache__/pyc/log/regression证据）结果 **零差异 = IDENTICAL**；
  两侧 SKILL.md 版本行均为 v1.4.1。
- 注意区分：`C:\Users\29603\.agents\skills\aviation-engineering-thesis`（v1.3.0，另一门"大类写作交付"
  Skill，SKILL.md §14 定义了共存分工）；`latex-thesis-zh` 亦无关。本会话的 ZCode 技能列表里
  触发的是 aviation-engineering-thesis，aeromech-thesis 不在 ZCode 的 .agents/skills 下——
  如未来要求在 ZCode 内直接触发本 Skill，需要额外安装/链接（当前未做，属 UNKNOWN：是否有此需求）。

## 4. 当前 Git 状态

- **无 git 仓库**：`thesis-skill/` 及 aeromech-thesis 下均无 `.git`；`git status` 报 not a repository。
- 版本管理完全靠 CHANGELOG + dev/install 双副本 + 文件 mtime。
- 风险注记：全部文件 mtime 统一为 2026-09-12 23:12~23:15（事故恢复整树复制的指纹）；
  无 git 意味着"事故再发生 = 只剩 install 一份"。建议（不强制）：第二阶段初始化 git。

## 5. 已完成能力（有实现+有测试证据）

见 capability-matrix.md A/B 段。摘要：
- v1.0 交付流水线（build→toc→pdf→qa→gate）；v1.1 Template Fidelity（TF-01~20+Test A/B）；
  v1.2/1.3.0 Cover Fidelity（CF-01~25）；v1.3.1 页级保真；v1.3.2 图表版式+内容净化；
  v1.3.3 图形拓扑 GQ+figkit；v1.3.4~5 表启动块；v1.3.6~7 横向宽表 TR；v1.3.7~8 封面填写保真；
  v1.3.9~10 颜色保真；v1.3.11 legacy .doc+QA通用化；v1.4.0 Research Integrity（10注册表+
  RQG-00~15+traceability+coverage）；v1.4.1 状态模型（7态/severity/reason/remediation、
  NHR 人工复核回路、NOT_APPLICABLE、错误不伪造PASS）+ dev/install 同步规程 + 5 测试。
- 回归基线（2026-09-12，tests/v1_4_1/regression/regression-report.md）：v1_4 11/11、
  v1_4_1 5/5、test_a 12/0、test_b 6/0、test-3.0~6.0 交付链全 PASS。

## 6. 未完成能力

1. **v1.5 集成三件套**：SKILL.md（加载表/路由表/Gate/命令清单）未接入 intelligence 层；
   Delivery Gate 未消费 loop 终态；README/CHANGELOG 未发布 v1.5.0。
2. **v1.5 验证**：tests/v1_5/run_all.py 从未（有证据地）执行过；无 v1.5-final-report.md；
   test-7.0 端到端项目（gap-analysis §3.9 已给规格：3 RQ+植入5类问题+1冲突）未建。
3. v1.5 代码已知瑕疵（静态审计发现，见 §7 Bug 清单 B1~B6）。
4. SKILL.md §8 降级对照表与 §2 MVP 边界仍停留在早期口径（QA/Defense/Figure 早已实现，文档未更新）。
5. aviation-engineering-thesis（旧姊妹 Skill）仍停在 v1.3.0 —— 两 Skill 分工边界是否随
   aeromech v1.4/1.5 能力扩张需要重划，属产品决策，未处理。

## 7. 已知 Bug（静态审计新发现，均不在 CHANGELOG 中）

| # | 位置 | 问题 | 级别 |
|---|---|---|---|
| B1 | research_quality_score.py | "Citation" 维度无 issue 类型映射 → 恒 100，评分虚高 | Medium |
| B2 | research_quality_score.py | REDUNDANT_CONTENT（diagnosis 会产出）缺 ISSUE_DIMENSION 映射 → 静默不计分 | Medium |
| B3 | research_repair.py | `plan --diagnosis-json` CLI 标志从未被读取（死参数）；fix_synth_label 无 verify 函数 | Low/Medium |
| B4 | research_diagnosis.py | docstring 写 `--quiet-rqg`，实现为 `--no-rqg`（文档/代码矛盾）；引用的 §13/§16/§24 在 research-intelligence.md 中不存在（该文件只有11节）——规格追溯断链 | Low |
| B5 | color_fidelity_qa.py | 头注释 COLOR-01~08 vs 报告标题 COLOR-01~16 | Low |
| B6 | 交付脚本退出码不统一 | pdf_qa rc=2 表示 Critical，而 v1.4.1+ 规范 2=not_initialized/3=ERROR；跨层混用有歧义 | Low |
| B7 | research_repair recompute | 对项目 YAML 内注册命令 shell=True 执行，"受信输入"假设未在任何文档声明 | Medium(安全设计声明) |
| 既有 | test-1.0/2.0 pdf_qa 页码 FAIL | 已作为"非回归的既有差异"永久披露，不修 | 披露 |

## 8. 技术债

- evidence_statuses_of 等状态解析逻辑在 research_integrity / research_quality_qa /
  research_diagnosis 三处近似重复 → 一致性漂移风险。
- RQG 检查器单函数 ~370 行，不可逐检查单测；RQG-01~05 在 diagnosis 里粗并为 TRACEABILITY_GAP。
- visual_regression B类豁免 EXEMPT={0,3}+6章硬编码——泛化边界。
- 无 git、无包管理/依赖清单（requirements.txt/pyproject 不存在；依赖 pymupdf、python-docx、
  pywin32/Word COM、matplotlib 均为隐式）。
- README §11 自称"不得为宣传提前声明未实现功能"——但 SKILL/README 当前也未声明已实现的
  v1.5（反向漂移），发布流程缺"版本号三处联动更新"检查项（可加进 test_dev_install_sync）。

## 9. 当前风险（排序）

1. **同步事故复发（最高优先）**：2026-09-12 22:58 `--to-install` 后 dev 侧 191 文件被清；根因
   **未能复现定位**（涉事旧 sync.py 与事件同灭），现为"最坏假设"加固版。静态审计四道护栏均真实
   存在且逻辑正确（见 §10），但护栏 #1~#3 只防"删错树/删太多/空源"，若当年事故根因在别处
   （如外部进程/编辑器行为），现有护栏未必拦截。**无 git + 恢复未做前后清单核对 = 无法证明当前树
   与事故前逐字节等价**。缓解建议：第二阶段第一件事初始化 git（可逆、非破坏）。
2. **v1.5 未验证即可能被误当"已完成"**：本任务书称 v1.5 为"下一阶段目标"，实际代码已在仓——
   若后续按"从零开发 v1.5"计划会造成重复劳动；若按"已可用"直接使用又缺测试通过证据。两头都危险，
   必须先跑 tests/v1_5 + test-7.0 建立验证基线。
3. install 目录是 ZCode 会话外另一宿主（Qoder CN）的加载路径；本环境技能列表显示的是
   aviation-engineering-thesis，说明当前 ZCode 会话并未加载 aeromech-thesis——跨宿主行为差异
   未测试（UNKNOWN）。

## 10. 同步事故当前状态（专项结论）

1. sync.py 存在（工作区根，dev 之外，不参与同步比对本体）。
2. 实现：镜像同步（copy+覆盖+删目标侧多余），逐字节比较（filecmp 缓存 Bug 已在 v1.4.1 修）。
3. 删除源文件风险：**代码路径审计未见可达路径**——`_assert_dst_only` 逐条断言目标在 dst 树内
   且不等于/不位于 src 树内；`dels` 只会取 compare 的"仅存在于 dst"集合。逻辑上不可能删 src 侧。
4. `--to-install`：静态审计安全（护栏 1-4 生效）；⚠仍是镜像语义，INSTALL 侧多出的文件会被删——
   属预期行为。5. `--to-dev`：同样受护栏保护，但方向危险（会用 install 覆盖 dev）——仅限事故救援。
6. `--check`：**纯只读**（只 compare+打印，无写操作）✔。
7. `--mirror`：不存在（镜像语义内置于 --to-install/--to-dev）。8. `--dry-run`：存在✔。
9. SHA256 identity check：**不存在**——用逐字节流比较替代（等价强度，非哈希但无缓存缺陷）。
10. sync tests：tests/v1_4_1/test_dev_install_sync.py 存在（含 filecmp 负例回归）✔；
    但未见针对 4 道删除护栏本身的负例测试（护栏 #2/#3 的行为仅 DEV_SYNC.md 声明）——小缺口。
11. 备份机制：sync.py 本身无备份；事故时靠"install 完整"整树恢复。无 git。
12. dev/install 当前一致性：**IDENTICAL（本次 diff -r 独立复核）**。
- 总判定：SYNC SAFETY = **静态审计通过（代码层面未发现删除源文件的可执行路径）**，
  但保留"根因未定位"的原始警示；执行任何写方向同步前必须先 --dry-run，且建议先建 git。

## 11. 下一步最合理是什么

见 v1.5-implementation-plan.md。一句话：**先"验证与收编"已有的 v1.5，而不是重新开发它**——
跑 tests/v1_5 → 修 B1~B7 → 接入 SKILL.md/Gate → 建 test-7.0 端到端 → 发布 v1.5.0；
同步风险用 git 初始化先行对冲。
