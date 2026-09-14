# QA Agent（S6 全片检查）

| 项 | 内容 |
|---|---|
| 职责 | 跑 PPT-01~15，按严重度分级，驱动回退修复 |
| 输入 | 答辩PPT.pptx + layout.json + theme.yaml + deck.yaml |
| 输出 | `.pptdirect/artifacts/qa/ppt-qa-report.md` + open_issues |
| 触发 | S6 路由；每次 S5 构建后必跑 |

执行：`python scripts/ppt_qa.py --pptx <pptx> --layout <layout.json> --theme <theme.yaml> --deck <deck.yaml> --out .pptdirect/artifacts/qa`（退出码 0 才可进 S7）。

## 检查项与回退映射

| 项 | 内容 | severity | 回退 |
|---|---|---|---|
| PPT-01 | 正文页数在档位区间（附录页不占档位） | 高 | S2（预算失衡）或 S1（档位选错） |
| PPT-02 | 每页要点数 ≤ 上限（附录页豁免） | 高 | S3 |
| PPT-03 | 每页可见字数 ≤ 上限（附录页豁免） | 高 | S3 |
| PPT-04 | 无估算文本溢出（引擎字体度量 + 自动缩字号） | 严重 | S3（删字/拆页）或 S4（调字号） |
| PPT-05 | 实测颜色 ∈ 主题调色板 | 高 | S4 |
| PPT-06 | 同版式标题位置一致（附录页豁免） | 一般 | S5（引擎问题，报 bug） |
| PPT-07 | 实测字体 ∈ 主题声明 | 高 | S4 |
| PPT-08 | 无【待填】占位符残留 | 严重 | S3（补内容或用户确认留空） |
| PPT-09 | 无空页 | 高 | S3 |
| PPT-10 | 每页有讲稿备注 | 一般 | S3 |
| PPT-11 | 讲稿时长估算（备注字数÷250字/分）在档位 duration_min 的 [0.5×,1.3×] 内；deck.meta.duration_min 可覆盖档位默认 | 一般 | S3（补/删讲稿） |
| PPT-12 | 表格规模 行≤12、列≤8 | 高 | S3（拆表或精简列） |
| PPT-13 | 模板模式下母版驱动页 ≥50%（theme 有 template_layouts 时启用） | 一般 | S4（配版式名）或 S5 |
| PPT-14 | 标点/全半角一致：半角 `,;:?!()"` 紧邻中文、全角数字/拉丁字母/句点（可见文字与备注都查） | 一般 | S3（改标点，不触内容） |
| PPT-15 | 附录页放映隐藏（实测 pptx show 属性：appendix 页必隐藏、正片必不隐藏） | 一般 | S5（引擎未设 show 属性，报 bug） |

## 规则

- 每个 FAIL 挂 open_issue（category/target_stage 按上表），修复后重跑 QA，PASS 才关闭。多数检查的 detail 已内置修复建议（如"补 N 页或降档至 short""触底仍溢出（需删字或拆页）"），挂 issue 时直接引用。
- PPT-04 是引擎侧字体度量估算（PIL 实测字形宽度 + 逐行折行），引擎会自动缩字号（body 下限 14pt、col_title 14pt、table 12pt），sidecar 记录 shrink_from；估算存在误差，用户肉眼复核发现误报/漏报时先核 text_fit.py 的度量参数，不得直接放宽阈值。
- PPT-14 只查紧邻中文的半角标点与全角数字/拉丁字母，西文缩写、公式、数字小数点在合法白名单内不误报；如报"半角','"多半是中文语境误用英文逗号，改成全角即可。
- 严重/高未 closed 禁止进 S7；一般/建议可带问题交付但必须在交付说明中披露。
