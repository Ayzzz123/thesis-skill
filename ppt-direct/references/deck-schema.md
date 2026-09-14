# deck.yaml Schema（逐页内容真源）

`deck.yaml` 是 S3 的产物、S5 的唯一输入。字段全集：

```yaml
meta:
  title: "论文题目"            # 必填；未定写【待填】并挂 open_issue
  presenter: "姓名"
  major: "专业"
  school: "学校"
  advisor: "指导教师"
  date: "2026-06"
  page_tier: standard          # short | standard | long（PPT-01 校验依据）
  duration_min: 8              # 可选：讲稿时长下限（分钟），覆盖档位默认；PPT-11 校验依据
  appendix_pages: 2            # 可选：问答备份附录页数（ingest 自动写入，不占档位）
slides:
  - layout: cover              # 字段默认取 meta，可逐项覆盖
    notes: "开场白"
  - layout: toc
    items: ["板块一", ...]      # 可省略：自动收集所有 section 页标题
    title: "目录"               # 可选
  - layout: section
    no: 1                      # 板块序号（显示为大号数字）
    title: "研究背景与意义"
  - layout: content
    title: "页标题"
    kicker: "可选眉标"          # 小字灰条，如"第 2 章"
    bullets:
      - "一级要点"
      - [1, "二级要点"]         # [level, text]；level ∈ {0,1}
    notes: "本页讲稿（PPT-10 要求非空）"
  - layout: two_column
    title: "方法对比"
    left:  { title: "FMEA", bullets: ["…"] }
    right: { title: "FTA",  bullets: ["…"] }
  - layout: image_text
    title: "系统组成"
    image: "materials/fig.png" # 相对工程目录；缺失则构建报错（不静默跳过）
    image_side: left           # left | right
    caption: "图1 收放系统组成"
    bullets: ["…"]
  - layout: table              # v1.1.0 表格版式
    title: "FMEA 关键行"
    kicker: "可选眉标"
    table:
      headers: ["故障模式", "RPN"]
      rows: [["模式一", "168"], …]        # 行数 ≤12、列数 ≤8（PPT-12）
      highlight_rows: [0]                  # 可选：高亮数据行（0 起）
      col_weights: [3, 1]                  # 可选：列宽权重，默认均分
    notes: "…"
  - layout: flow               # v1.3.0 技术路线图
    title: "技术路线"
    kicker: "可选眉标"
    direction: h                # h=横排（steps ≤6）| v=纵排（7~8 条）
    steps: ["功能结构分析", "故障树建模", "FMEA 排序", "维修策略"]  # 每条 ≤12 字
    notes: "…"
  - layout: closing
    title: "恳请各位老师批评指正"
    sub: "谢谢聆听"
  - layout: content            # 问答备份附录页（ingest 自动生成，也可手写）
    kicker: "问答备份"
    title: "预测问答（1）"
    bullets: ["为什么选 FMEA？", "答：…"]
    notes: "问答备份页：被问到相关问题时翻至此页参考。"
    appendix: true             # 附录标记：不占档位页数，豁免 PPT-02/03/06；
                               # 构建时自动设放映隐藏（show=0），被问到按页码直达
```

规则：

1. `layout` 必填且只能是九种之一（cover/toc/section/content/two_column/image_text/table/flow/closing）；未知值构建时报错（退出码 1）。flow 页 `steps` 必填，横排 ≤6 条、纵排 ≤8 条，超限构建时报错。
2. 可见文字遵守 `theme.yaml` 的 limits：`bullets_per_slide`（默认 7）、`chars_per_slide`（默认 150，不含 notes）。附录页（appendix: true）豁免这两项与 PPT-06 对齐检查。
3. **诚信**：bullets 只能写论文/输入源里有的内容；数据须与论文一致；无处安放的信息写【待填】，挂 open_issue（category=content），由用户补全，禁止编造。
4. `notes` 是本页讲稿口径（30~90 字/页为宜），会写入 pptx 备注页；含模拟数据的页面必须在 notes 里声明"方法演示，非真实结果"。
5. 页数预算 = 档位区间；cover/toc/closing 固定各占 1 页，其余预算分给 section 与内容页；附录页不占预算。
6. 长文本不必手工拆短：引擎按字体度量自动缩字号（body 下限 14pt、表格 12pt），sidecar 记录 shrink_from；触底仍溢出才需要删字或拆页（PPT-04 会提示）。
