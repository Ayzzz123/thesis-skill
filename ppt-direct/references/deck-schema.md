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
  - layout: closing
    title: "恳请各位老师批评指正"
    sub: "谢谢聆听"
```

规则：

1. `layout` 必填且只能是七种之一；未知值构建时报错（退出码 1）。
2. 可见文字遵守 `theme.yaml` 的 limits：`bullets_per_slide`（默认 7）、`chars_per_slide`（默认 150，不含 notes）。
3. **诚信**：bullets 只能写论文/输入源里有的内容；数据须与论文一致；无处安放的信息写【待填】，挂 open_issue（category=content），由用户补全，禁止编造。
4. `notes` 是本页讲稿口径（30~90 字/页为宜），会写入 pptx 备注页；含模拟数据的页面必须在 notes 里声明"方法演示，非真实结果"。
5. 页数预算 = 档位区间；cover/toc/closing 固定各占 1 页，其余预算分给 section 与内容页。
