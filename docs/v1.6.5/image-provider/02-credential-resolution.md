# CREDENTIAL_RESOLUTION（02）

模块：`scripts/image_config.py`（纯 stdlib，不引入 python-dotenv 依赖——避免给
Skill 运行环境加第三方要求；解析器 30 行内自含）。

## 1. 配置模型（§五：provider-specific，拒绝三全局变量）

```
IMAGE_BACKEND = openai | gemini | qwen | zhipu | minimax | volcengine | host_native | <future>

# 每个后端一组自己的前缀（大写规范化：provider.upper()）：
OPENAI_API_KEY / OPENAI_MODEL / OPENAI_BASE_URL
GEMINI_API_KEY / GEMINI_MODEL / GEMINI_BASE_URL
QWEN_API_KEY   / QWEN_MODEL   / QWEN_BASE_URL
…（新后端=新前缀约定，零代码；OpenAI 兼容端点共用 openai_compat 适配器）

IMAGE_MAX_ATTEMPTS = 3        # 成本闸（§十四，可覆盖）
IMAGE_ALLOW_PROJECT_ENV = 0   # 项目级 .env 默认禁用（§三 风险评估结论，见 03 文档）
```

解析规则：
- `resolve_backend()`：取 `IMAGE_BACKEND`；未设→返回 `unavailable`（**正常状态不是错误**：
  调用方自动回落既有 Figure Pipeline，§七/§十四）；不猜默认后端、更不猜 Key。
  仅当调用方声明 `required=True`（用户显式 `provider_required: external`）才报
  `IMAGE_PROVIDER_NOT_CONFIGURED`→NEEDS_CONFIGURATION。
- `resolve_credential(backend)`：只认 `<BACKEND>_API_KEY` 一个键；缺失→
  `MISSING_CREDENTIAL`（错误分类学见 04 文档）。
- `resolve_model/base_url(backend)`：`<BACKEND>_MODEL` 有默认建议值（非敏感，可内置，
  如 openai→`gpt-image-1`）；`<BACKEND>_BASE_URL` 无默认（除官方端点常量）。
- **不同后端的键绝不互相回退**（OPENAI_API_KEY 不会被当作 GEMINI_API_KEY 用）。

## 2. 解析算法（首命中不合并，§四）

```
sources = [
  ("process",  None),                       # 1. 当前进程环境变量（最高优先）
  ("cwd",      $CWD/.env),                  # 2. 当前工作目录（默认禁用，见 03）
  ("skill",    <skill_install_dir>/.env),   # 3. Skill 安装目录
  ("user",     ~/.aeromech/.env),           # 4. 用户级（推荐持久位置）
]

resolve(key):
    for (scope, path) in sources:
        if scope == "process":
            if os.environ.get(key): return value, "process"
            continue
        if path exists and path 是本请求首次命中的文件:
            # 关键语义：命中第一个存在的 .env 后，文件间不再级联
            v = parse(path).get(key) or os.environ.get(key if scope=="process")
            if v: return v, path
    raise NotConfigured
```

**"只读取第一个命中的 .env"的精确含义**（§四）：
- 进程 env 永远单独最高优先（每个键独立判断）；
- 文件层：按搜索序取**第一个存在的文件**作为唯一文件源，不再把后面文件的同名键
  合并进来；同一文件内也不覆盖进程 env；
- 由此杜绝"项目 .env 半套键 + 用户 .env 半套键拼出一个谁都没配过的组合"。

skill 安装目录解析：`AEROMECH_SKILL_HOME` env > `~/.qoder-cn/skills/aeromech-thesis`
（与 sync.py DEFAULT_INSTALL 同源约定，但不 import sync.py——仓库根文件不属于
Skill 运行包）。

## 3. 键值文件语法（最小方言，严格）

```
KEY=VALUE          # 支持；值可带引号
# 注释、空行忽略
export KEY=VALUE   # 容忍（去 export 前缀）
```
- 拒绝多行值/插值/命令替换（`$(…)` 原样为字面量）——.env 不是脚本，防注入面。
- 解析失败行：跳过并计数，`image test` 报 `malformed_lines: N`（不静默）。

## 4. 诊断与测试（§九，脱敏输出）

`aeromech image test` 输出契约（**唯一允许的观察面**）：
```
Backend:    openai
Model:      gpt-image-1
Credential: configured            # 或 missing
Source:     ~/.aeromech/.env      # 键来自哪个 scope（路径不泄值）
Fingerprint: sha256:1a2b3c4d      # Key 的哈希前 8 位——可比较"是不是同一把 Key"，
                                   # 不可反推
Connection: OK | AUTH_FAILED | NETWORK_ERROR | RATE_LIMIT | …（分类见 04）
```
- 任何模式都不输出长度、前缀、后缀、掩码字符串（连 `sk-…abcd` 都不要——指纹已够）。
- `aeromech image test` 未配置时：**不算失败**（exit 0），输出
  "No external image provider configured. Existing figure generation remains available."
  （§十一）；
- `aeromech image status`：列出所有已检测后端（configured/not-configured），无值。
- `aeromech image config`：交互式写入 `~/.aeromech/.env`（0400 权限建议 + Windows
  提示），Key 输入不回显（`getpass`），写完立即 `redact` 自检。

## 5. 删除（文档 §九-9）

`aeromech image remove`：从用户级 .env 删除该后端三行（保留其他后端），
不碰进程 env。删除后 `image test` 必须报 missing（测试 RES-12）。

## 6. 隔离证明（§十三）

- 仓库内（git ls-files）不得存在任何 `*.env`/`*API_KEY*` 值——secret_leak_qa 扫描。
- 测试用假 Key（`sk-test-…` 前缀 + 校验和格式）且只存在于 tempfile HOME（08 文档），
  CI/本机永不真实调用外部 API（`--offline` 默认，connection 测试 mock HTTP）。
