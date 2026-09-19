# HOST_NATIVE_INTEGRATION（07）

## 1. 定位（§八/§十六）

Agent Host（运行本 Skill 的宿主，如带原生生图能力的 IDE/agent 运行时）本身能生图时，
**不需要任何 provider API Key**——这是四条生成路径之一：

```
Host-native image generation   ← 零 Key，宿主能力
Configured external provider   ← 用户自己的 Key（02/04 文档）
Local deterministic provider   ← figkit/mermaid（既有，默认）
User-provided image            ← user_asset（04 文档 §7）
```

## 2. 机制：请求-回执协议（不假装生成）

`host_native.py` 不发 HTTP、不持 Key。它的 `generate()` 返回一个**结构化请求**：

```
BackendResult(ok=False, deferred=True, code="HOST_NATIVE_REQUESTED",
              payload={prompt, size, out_path, figure_id, prompt_hash})
```

`ImageModelProvider` 识别 `deferred=True` → 生命周期记
`NEEDS_HUMAN_REVIEW`，reason=`HOST_NATIVE_REQUESTED`，并把 payload 写入
`figure-lifecycle.yaml` 的 `provider_meta`（宿主侧可读）。

**宿主完成生成后回填**（两条合法路径）：
1. 宿主把图写到 `out_path` → 重跑 `figure_iface validate --figure FIG-XXX`：
   发现 artifact 在场 → 记 GENERATED（method=host_native）→ 继续 VIS/GQ；
2. `aeromech image host-accept --figure FIG-XXX --artifact <path>`（显式回执命令，
   校验 artifact 哈希后 record，防"随便指个文件"）。

## 3. 为什么不用"检测到宿主就自动算成功"

- 检测不到生成结果就记 GENERATED = 语义造假（v1.6.5 D2 同族红线）；
- deferred→NHR 保证：**没有真图就没有真通过**，与 §八"没有 Key→fake image→PASS"
  禁令一致；
- 宿主若不提供生图，路径自然落空 → 用户改用 external provider 或 local 或 user_asset。

## 4. 能力探测（可选，不依赖）

`aeromech image status` 增列 `host_native: available|unknown`（读约定 env 标志
`AEROMECH_HOST_IMAGE=1`，由宿主注入）。探测只影响**建议**（提示用户可选此路），
不改变任何判定逻辑——探测失败绝不 BLOCK（§八 允许而非要求 host-native）。

## 5. 测试锚点（08 文档）

- HN-01：host_native backend 无 Key 可 resolve（不触发 MISSING_CREDENTIAL）
- HN-02：generate 返回 deferred，生命周期=NHR，不落任何假图文件
- HN-03：artifact 回填后 validate 通过→GENERATED→VIS 正常跑
- HN-04：host-accept 拒绝不在项目内/哈希不符的 artifact
