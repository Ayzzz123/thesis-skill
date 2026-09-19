# DOCUMENTATION_PLAN（09）

## 1. 新增 `references/image-provider.md`（唯一新规则文档）

目录（§十八 十三项全覆盖）：

```
1.  为什么每个用户自己配置 Key（信任模型：Skill 不持密、不代付、不共享）
2.  推荐配置位置（~/.aeromech/.env；进程 env 用于 CI；项目级默认禁用及原因）
3.  .env.example 模板（仓库内唯一合法模板，全占位值）
4.  用户级 .env 写法（完整示例，含多后端并存）
5.  Provider 配置方式（IMAGE_BACKEND + <PROVIDER>_API_KEY 前缀约定）
6.  Model 配置（<PROVIDER>_MODEL；默认建议值表）
7.  Base URL 配置（<PROVIDER>_BASE_URL；代理/私有端点场景）
8.  配置测试（aeromech image test 输出解读；Connection 错误分类表）
9.  删除 Key（aeromech image remove；轮换流程：先写新再删旧再 test）
10. 安全说明（八条禁令的用户视角；日志/产物永不含 Key 的机制承诺）
11. API 成本说明（计费归属用户、max_attempts=3、首次提示、哪些图类型不花 API 费）
12. Host-native image generation（零 Key 路径、deferred/NHR 语义、host-accept 回执）
13. Local Provider（确定性图默认路径；与 AI 的分工表——引用 06 文档路由表）
14. AI Image 与 Research Evidence 的区别（红线清单：AI 图不能证明什么；
    【AI 生成示意图】题注要求；ai_generated_visual 证据类型语义）
```

## 2. 既有文档接线（小改，不重写）

| 文件 | 改动 |
|---|---|
| SKILL.md | 加载表 +1 行（Image Provider → references/image-provider.md）；§21 要点补"provider 路由四路径"一段；§18.3 图形规则加一句"AI 图不降低 VIS 门槛" |
| references/orchestration.md | 矩阵 S8 行：AI 挂载点说明（provider=image 时经 image_config，缺失→NHR 非 BLOCK）；CLI 速查表加 image 子命令 |
| references/agents/figure.md | 步骤2 规划表加 `provider` 列；新增"§路由：何时用 AI/何时必须 local"（指向 image-provider.md §13） |
| references/delivery-pipeline.md | §8.5 gate 域清单加 G-SEC-01（secret 泄漏）与 figure_visual 已有域的说明 |
| README.md | §11 当前版本段补一句 v1.6.5 图形系统（视觉系统 + 用户级 Image Provider） |
| CHANGELOG.md | v1.6.5 条目（实现阶段写，设计阶段不动） |

## 3. 仓库模板文件

- `aeromech-thesis/.env.example`（新）：全部键名 + 占位值 + 注释（"复制为
  ~/.aeromech/.env 后填真实值"）；**不含任何真实/可用格式 Key**。
- 文档内所有示例 Key 一律 `sk-TEST-xxxxxxxx` 形态并标注"示例假值"。

## 4. 用户旅程（§十九 写入 image-provider.md 开头）

```
需要 AI 生图 → aeromech image status（检测：无配置）
→ 提示"请配置您自己的 Image Model API Key（将产生您的 API 费用）"
→ aeromech image config（交互：选后端→贴 Key[不回显]→model[可默认]→写入 ~/.aeromech/.env）
→ aeromech image test（Backend/Credential: configured/Connection: OK）
→ S8 规划把概念示意图标 provider=image → 生成 → VIS/GQ → 交付
（任一环节失败：明确错误码 + 下一步建议；绝不假图假过）
```

## 5. 验收

- 新用户按文档从 clone 到首张 AI 图 ≤4 条命令、零源码修改（重点问题 10）；
- 文档中 grep 不到任何真实 Key 形态；.env.example 通过 secret_leak_qa --scope repo。
