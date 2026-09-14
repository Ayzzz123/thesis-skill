# v1.4.1 回归测试报告（Stability & Production Hardening）

**日期**：2026-09-12
**范围**：验证 v1.4.1 未破坏任何既有能力，且新状态模型在真实项目上落地。
**环境**：安装副本 `C:\Users\29603\.qoder-cn\skills\aeromech-thesis`（与开发副本经 sync.py --check 判定 IDENTICAL）。

## 1. Skill 自身测试

| 套件 | 结果 |
|---|---|
| tests/v1_4（11 文件，162 断言） | **11/11 PASS**（期望值按 v1.4.1 语义更新：全模拟夹具 → PASS_WITH_HUMAN_REVIEW / RQG-09 NHR） |
| tests/v1_4_1（5 文件：NOT_APPLICABLE / 人工复核 / Gate 状态 / 目录同步 / 防伪 PASS） | **5/5 PASS** |
| tests/test_a_template_fidelity.py | **PASS=12 FAIL=0** |
| tests/test_b_format_reconstruction.py | **PASS=6 FAIL=0** |

## 2. Template Fidelity —— 无回归

| 项目 | 命令 | 结果 |
|---|---|---|
| test-3.0（南农模板母版） | `tf_qa --template <南农模板.docx>` | **PASS=20 FAIL=0**（TF-01~20） |
| test-4.0（南农模板母版） | 同上 | **PASS=20 FAIL=0** |
| test-5.0（哈工程规范驱动，无母版） | `tf_qa --template <规范.docx> --cover-tokens … --front-numbering none --margins 2.8,2.5` | **PASS=18 FAIL=0 + SKIPPED_WITH_REASON=2** |
| test-6.0（无任何模板/规范，v1.4.1 新增能力） | `tf_qa --docx … --pdf …`（省略 --template） | **PASS=15 FAIL=0 + NOT_APPLICABLE=5**（TF-01~04/TF-19 记 N/A 附 reason，交付 Gate 不因无模板失败） |

## 3. Cover / Graph / Table / PDF QA —— 无回归

| QA | test-3.0 | test-4.0 | test-5.0 | test-6.0 |
|---|---|---|---|---|
| pdf_qa | PASS(0/0) | PASS(0/0) | PASS(0/0) | PASS(0/0) |
| cover_fidelity | —（模板对照见下） | **PASS=25 FAIL=0** | **PASS=25 FAIL=0**（自检） | PASS=25 FAIL=0 |
| figure_table | （v1.4.0 回归已验） | **PASS=22 FAIL=0** | **PASS=22 FAIL=0** | PASS=22 FAIL=0 |
| table_readability | — | （v1.4.0 回归已验：TR-10 修复后 PASS；残留 TR-06/07/08 为既有差异） | **PASS=11 FAIL=0** | PASS=11 FAIL=0 |
| graph_quality | — | **FAIL=0** | **PASS=68 FAIL=0** | PASS=23（3 SKIP 设计内） |
| visual_regression | PASS | PASS | PASS | PASS |

（test-3.0 的 cover/table/graph 明细与既有差异见 `tests/v1_4/regression/regression-report.md`：其 pair-cover 槽位偏移、
无 figkit layout 元数据、TAB-06 单字格等均为 **v1.4.1 未修改检查**与更早期产物的既有差异。）

## 4. Research Quality / Delivery Gate —— 无回归（含语义升级说明）

| 项目 | v1.4.0 行为 | v1.4.1 行为 | 结论 |
|---|---|---|---|
| test-6.0（全模拟数据项目） | RQG 全 PASS，gate=PASS | RQG-09/RQG-10 → **NEEDS_HUMAN_REVIEW**（不得自动 PASS），gate=**PASS_WITH_HUMAN_REVIEW**（rc=0）；生成 human-review-checklist（4 项：RQG-09:ABSTRACT / RQG-10:CL-003 / RQG-10:CL-006 / RQG-10:CON-002） | **语义升级（非回归）**：启发式清洁不再等于自动 PASS；裁决回路实测（4 项全 ok → gate 回到 PASS；本报告取证后已移除裁决文件，项目保持"待人工复核"的诚实状态） |
| test-5.0（无注册表旧项目） | rc=2 not_initialized 不阻塞 | rc=2 not_initialized 不阻塞 | 无回归 |
| RQG 机械检查（cover/数值/label/链路等） | 不变 | 不变（v1_4 套件 11/11 验证） | 无回归 |
| 强断言越界（overreach） | FAIL Critical | FAIL Critical（未被 NHR 软化） | 无回归 |
| 损坏注册表 / 内部异常 | 崩溃或不确定 | **ERROR rc=3，绝不 PASS**（tests/v1_4_1/test_false_pass_prevention 验证） | 加固 |

## 5. 清理与遗留

- test-6.0 的 RQG 报告已恢复为**待人工复核**状态（human-review.yaml 为演示后移除，未代替人类签字）。
- test-1.0/2.0 的既有 pdf_qa 差异（v1.0 时代产物的页脚页码位置）与 v1.4.1 无关，保持既有披露。
