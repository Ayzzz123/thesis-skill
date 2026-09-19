# PROVIDER_INTERFACE（04）

## 1. 两层抽象（§六）

```
figure_iface.FigureProvider（既有契约，KEEP）
        ▲
        │ 继承
ImageModelProvider（薄适配，NEW，注册名 "image"）
        │ 持有
        ▼
image_providers.base.ImageBackend（NEW 抽象，真正碰 HTTP 的层）
```

- `ImageModelProvider` 只做：plan 委托、backend 选择、生命周期记录、provenance 组装、
  成本闸计数、错误→状态映射。**它自己不发 HTTP、不解析 Key。**
- `ImageBackend` 才是厂商适配器接口。

## 2. ImageBackend 抽象（image_providers/base.py）

```python
class ImageBackend:
    name = "abstract"                 # openai / gemini / openai_compat / host_native
    def capabilities(self) -> dict    # {"sizes":[…], "max_n":4, "auth_style":"bearer|query"}
    def generate(self, *, prompt, size, n=1, out_path, ref_image=None) -> "BackendResult":
        """成功：写 out_path（bytes 落盘由基类统一做），返回 BackendResult(ok=True, model=…, raw_meta=…)
        失败：抛 ImageError(code=<§3 分类>, retryable=bool)。
        禁止：返回半截文件；禁止把 api_key 放进 raw_meta。"""
    def check(self) -> "BackendResult"  # 轻量探活（image test 用），同样只抛 ImageError
```

基类 `ImageBackend` 提供公共实现：HTTP 超时（默认 120s）、响应大小上限（防内存炸）、
落盘原子性（tmp→rename）、`raw_meta` 白名单过滤（只允许 model/id/size/created 字段过，
**header/authorization 一律丢弃**）。

## 3. 错误分类学（§十七，九类 + retryable 标记）

| code | 触发 | retryable | 生命周期映射 |
|---|---|---|---|
| MISSING_CREDENTIAL | resolve 无 `<B>_API_KEY` | 否 | **默认：回落既有管线（不是错误、不是 NHR）**；仅显式 mandatory→NEEDS_CONFIGURATION（§十四） |
| INVALID_CREDENTIAL | 401/403 | 否 | REJECTED（配错 Key，需人修配置） |
| NETWORK_ERROR | DNS/连接失败 | 是（≤3） | 重试后仍败→REJECTED |
| RATE_LIMIT | 429 | 是（退避） | 超限→NHR（成本闸） |
| MODEL_UNAVAILABLE | 404/模型名错 | 否 | REJECTED（配置问题） |
| PROVIDER_ERROR | 5xx | 是（≤3） | 重试后仍败→REJECTED |
| TIMEOUT | 120s | 是（≤3） | 重试后仍败→REJECTED |
| CONTENT_POLICY_ERROR | 内容审核拒 | 否 | REJECTED + 提示改 prompt |
| GENERATION_FAILED | 响应成功但无图/解码失败 | 否 | REJECTED |

- 分类在 adapter 内完成（各厂商状态码→统一 code 的映射表是 adapter 的一部分）。
- **统一异常 `ImageError`**：`str(e)` 即脱敏文本（基类 `__str__` 强制过 redact）——
  这是 record/log_action 边界外的第一道源头防线（F3）。
- 禁止把九类塌缩成 `IMAGE_GENERATION_FAILED` 一类（§十七 明文）。

## 4. OpenAI-compatible 统一适配器（重点问题 7）

`openai_compat.py` 一个类服务所有 OpenAI 兼容端点：
```
backend 名 → (base_url 默认, auth 头风格, 请求体形状)
qwen    → dashscope compatible-mode /v1    bearer  images/generations 或 chat 形状可配
zhipu   → open.bigmodel.cn/api/paas/v4     bearer
minimax → api.minimaxi.com/…               bearer
volcengine → ark.cn-beijing.volces.com/api/v3 bearer
```
- 请求体差异用 `capabilities()["request_shape"]` 声明（`images` vs `chat-image`），
  不逐厂商写类；新厂商=配置+一行 capabilities 表项。
- `openai_images.py` 与 `gemini_images.py` 独立（Gemini 是 generativelanguage 原生
  REST，非 OpenAI 兼容，auth 用 `?key=` 查询参数——**该参数即 secret**，redact 规则
  必须覆盖 URL 查询串，SEC-04）。

## 5. ImageModelProvider.generate 流程（含成本闸）

```
1. spec.provider == "image"?  否→拒绝（路由错，交回 06 文档）
2. resolve_backend() → 不可用→**自动回落 LocalProvider 生成**（reason 记
   fallback_from=external_unavailable）；仅 spec.provider_required=="external"→
   NHR(NEEDS_CONFIGURATION)
3. attempts = count_external_calls(root, fid)   # lifecycle 里 provider_meta.backend 计数
   if attempts >= IMAGE_MAX_ATTEMPTS(默认3) → 可本地绘制类型回落 local；否则 NHR("成本闸")
4. 首次外部调用前（该 root 无历史 image GENERATED）→ 打印费用提示（§十四）
5. prompt = 组装（含 figure 的 caption/type/研究链接上下文，长度上限）
6. backend.generate(...) → ImageError 按 §3 映射；成功→
7. record(GENERATED, provider_meta={backend, model, prompt_hash, attempts+1, …})
8. validate()：复用既有（研究链接硬关卡 + VIS/GQ；AI 位图几何 SKIP→渲染级+人工）
```

## 6. 与 LocalProvider 共存（§七 硬要求）

- 注册名不同（`local`/`image`/`host_native`/`user_asset`），`get_provider` 按名取；
- **默认永远 local**：未显式 `provider: image` 的图绝不走外部（省钱+确定性图更优）；
- LocalProvider 代码路径零改动；测试 INT-03 证明加 image 后 local 全绿不变；
- **两类失败严格区分（§七/§十四）**：①外部能力不可用（未配置/无后端）→
  **自动回落 Local**（路由行为，lifecycle 记 fallback_from，图照常全量 QA）；
  ②调用失败（网络/审核/模型错误）→ **不自动降级假 AI 效果**，失败就是失败
  （REJECTED/NHR，D2 纪律），Agent 可显式改 spec 重 plan。共同底线：绝不假图假过。

## 7. UserAssetProvider（§八 第四路径）

极薄：spec 带 `source_asset`（项目 materials 内文件，复用 material_ingestion 的
SHA256 登记）→ 校验存在+格式+尺寸 → record(GENERATED, method=user_asset)。
不生成、不联网、无 Key。用户已有图片=一等公民路径。
