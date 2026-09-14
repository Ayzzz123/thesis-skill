# Color Fidelity QA（COLOR-01~16）

- COLOR-01 校名字样对象类型与模板一致: PASS | 双方均为 inline 图片对象（PNG），媒体字节一致 sha=b59ebe2bf5430fe2…
- COLOR-02 校名字样颜色来源与模板一致: PASS | 效果链一致: <a:biLevel thresh="50000"/> <a:grayscl/> <a:lum bright="-6000" contrast="18000"/>
- COLOR-03 校名字样没有被重新着色: PASS | 校名区像素差异 mean|Δ|=0.000/255，>40 差异像素=0.000%（与模板逐像素一致）
- COLOR-04 校徽颜色与模板一致: PASS | 校徽区像素差异 mean|Δ|=0.000/255，>40 差异像素=0.000%
- COLOR-05 主标题颜色与模板要求一致: PASS | 主标题文字颜色=纯黑（模板 0x000000 / 成品 0x000000，字号 36pt）
- COLOR-06 普通正文颜色符合学校打印要求: PASS | 全 39 页文本 span 颜色均为纯黑（合计 32782 字）
- COLOR-07 封面颜色视觉对照通过: PASS | 整页 >40 差异像素 0.490%（≤4%，仅来自合法填入的题目/专业值）；校名/校徽/主标题均逐像素一致
- COLOR-08 封面颜色差异在允许范围: PASS | 除填入值行外：mean|Δ|=0.000/255，>40 差异像素 0.000%（对象完全继承模板）
- COLOR-09 校名字样源对象与模板一致: PASS | pic:pic XML 归一化后逐字节一致（792B；含 blip 效果/裁剪/变换/尺寸）
- COLOR-10 校名字样媒体 sha 一致: PASS | 模板=b59ebe2bf5430fe2dfa8b30f3669ca3c0ae7ca5d8608c9019f14938ea492520c
　　成品=b59ebe2bf5430fe2dfa8b30f3669ca3c0ae7ca5d8608c9019f14938ea492520c
- COLOR-11 校名字样DrawingML效果链一致: PASS | 效果链一致: <a:biLevel thresh="50000"/> <a:grayscl/> <a:lum bright="-6000" contrast="18000"/>
- COLOR-12 校名字样最终PDF渲染颜色与模板一致: PASS | PDF 内嵌熔合图 sha 一致（41b9248583e2f34f…，612×131px，Word 应用效果链后为纯黑）；区域像素 Δ=0.000
- COLOR-13 校徽对象与模板一致: PASS | 媒体 sha 一致（a4634e49da4f0319…）+ 熔合图 sha 一致（54fc146c6a9f12b4…）+ 区域像素 Δ=0.000
- COLOR-14 固定模板对象没有被重新着色: PASS | 校名与校徽全链路一致：媒体字节、pic:pic XML、效果链、PDF 熔合图、区域像素（无任何重着色步骤）
- COLOR-15 正文普通文字符合黑色打印要求: PASS | 全 39 页文本 span 颜色均为纯黑（32782 字）
- COLOR-16 封面视觉颜色对照通过: PASS | 校名 Δ=0.000｜校徽 Δ=0.000｜主标题同黑｜整页 >40 差异仅 0.490%（均来自填入值）

结果: ALL PASS