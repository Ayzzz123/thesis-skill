# Design Agent（S4 主题版式）

| 项 | 内容 |
|---|---|
| 职责 | 确定 theme.yaml：内置默认 or 校模提取；校模则同时启用母版驱动 |
| 输入 | `materials/` 下的校模 .pptx（若有） |
| 输出 | `.pptdirect/artifacts/theme.yaml`，state `theme.mode` |
| 触发 | S4 路由 |

## 模式选择

- `materials/` 存在可编辑校模 .pptx → **必须** `template` 模式：
  `python scripts/theme_extract.py --template <校模.pptx> --out .pptdirect/artifacts/theme.yaml`
  （提取画幅/主题色/主题字体/版式清单 `template_layouts`，继承内置默认的字号与 limits）
- 否则 → `builtin` 模式：复制 `assets/theme-default.yaml` 为 theme.yaml。

## 规则

1. 提取出的配色按 clrScheme 槽位自动映射（accent1→primary 等）；映射语义存疑时在 theme.yaml 上方加注释说明并由用户确认，不静默改色。
2. 用户口头改色（"换成绿色系"）→ 直接改 theme.yaml 的 colors，但仍受 PPT-05 调色板约束。
3. 字号与 limits 默认沿用内置值；用户有明确学校要求（如"标题必须黑体"）→ 改 fonts/sizes 并在 theme.yaml 注释来源。
4. **母版驱动**（v1.1.0）：template 模式下 S5 构建必须带 `--template <校模.pptx>`，引擎按版式名启发式匹配校模版式（封面→"标题幻灯片/封面"、正文→"标题和内容/内容"、节→"节标题"等），匹配不上的页面走重建。PPT-13 要求母版驱动页 ≥50%，不达标优先按 `template_layouts` 清单调整版式名或用「两栏/图文」页。
5. 出口：theme.yaml 落盘 → 写 state `theme.file`/`theme.mode` → 转 S5。
