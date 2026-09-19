# SECURITY_MODEL（05）

## 0. 威胁模型一句话

**Key 的最大泄漏面不是被攻击，而是"顺手"：异常文本进日志、日志进项目、项目进 Git、
Git 进交付。** 因此所有防线都围绕"自由文本边界"设计，而不是围绕加密。

## 1. 八条禁令 → 可执行机制（§一 逐条）

| 禁令 | 机制 | 验证（08 文档） |
|---|---|---|
| 不内置真实 Key | 仓库扫描：`secret_leak_qa --scope repo`（全 tracked files 正则+熵检测） | SEC-01 |
| 不共享用户 Key | Key 只存本机（进程 env/用户级 .env）；无任何"上传/同步 Key"代码路径 | SEC-02（代码审查项+grep 断言） |
| 不上传 Key | 出站 HTTP 仅两类：`Authorization: Bearer <key>` / `?key=<key>`（协议必需）；遥测/analytics=零（本 Skill 无遥测，加 grep 断言防未来引入） | SEC-03 |
| 不写入项目 | 项目内 `.env` 默认禁用（03 文档）；`image config` 只写 `~/.aeromech/`；provenance 元数据白名单不含 Key | SEC-04 |
| 不写入 Git | `.gitignore` 补条目 + pre-commit 式扫描（secret_leak_qa 的 `--scope diff`，扫 `git diff --cached`） | SEC-05 |
| 不写入日志 | `record()`/`log_action()` 边界统一 `redact()`（F3）+ `ImageError.__str__` 源头脱敏（04 文档 §3） | SEC-06/07 |
| 不写入论文产物 | 交付前 `secret_leak_qa --scope deliverables`（docx 文本层+pdf 文本层+figures 目录+lifecycle/manifest） | SEC-08 |
| 不写入测试期望 | 测试只用假 Key（`sk-TEST-` 前缀+校验位），且 tempfile HOME 隔离，测后即删 | SEC-09 |

## 2. redact() 规格（单一实现，全边界复用）

`image_config.redact(text) -> text`，规则（大小写不敏感）：
```
Authorization: <anything>        → Authorization: ***REDACTED***
Bearer <token-ish>               → Bearer ***REDACTED***
sk-[A-Za-z0-9\-_]{8,}            → ***REDACTED***
AIza[0-9A-Za-z\-_]{20,}          → ***REDACTED***          # Google
key=<value>& / key=<value>$      → key=***REDACTED***      # URL 查询串（Gemini 风格）
api_key=<value> / token=<value>  → 同上
eyJ[A-Za-z0-9\-_]{20,}\.        → ***REDACTED***          # JWT 形态
```
- 宁可错杀不可漏放：误伤日志可读性可接受（都是排障文本）。
- 单元测试用**合成样本**（非真实 Key 格式）+ 一个故意长的假 Key 断言全灭。

## 3. secret_leak_qa（NEW 脚本，§十/§十一）

```
python secret_leak_qa.py <root> --scope repo|diff|deliverables|all [--strict]
```
- 表面：git tracked 文件、staged diff、项目 `.aeromech/**`（yaml/jsonl/md/log）、
  交付 docx/pdf 文本层、figures 目录文件名（`sk-…` 命名的图也算）。
- 检测：redact 同款正则族 + 高熵串启发（≥28 字符 base64ish 且含大小写数字混合→WARN）。
- 判定：疑似真实 Key → **FAIL/BLOCK**（gate 新域 G-SEC-01）；假 Key 测试样本经
  `sk-TEST-` 前缀白名单豁免（白名单本身写死在扫描器，防止"把真 Key 改名混过白名单"：
  白名单仅对 tests/ 目录生效）。
- `.gitignore` 是**辅助**不是唯一防线（§十一 明文）：扫描器对"被 ignore 但已 tracked"
  的文件同样扫（ignore 挡不住历史提交）。

## 4. 成本闸（§十四）

- `IMAGE_MAX_ATTEMPTS` 默认 3，**按 figure_id 累计外部调用**（lifecycle provider_meta.attempts），
  跨进程持久——重开终端不能"重置计数刷 API"。
- 自动 regeneration（figure_visual FAIL→重生成）对 `provider=image` 的图：
  attempts 达上限→NHR，**绝不静默第 4 次调用**。
- 首次外部调用前一次性提示："将使用您配置的 Image Model API Key 调用外部服务，
  可能产生 API 费用。"（CLI 与 orchestrator 路径都打；`--yes` 跳过）。
- QA 失败重试（v1.5 loop ≤5 轮）与成本闸**正交**：loop 轮次再少，单图外部调用也 ≤3。

## 5. 研究完整性边界（§十五，与 01 文档 §4 同源）

- AI 图 = `ai_generated_visual`（evidence 新枚举，verification_status 强制 simulated 待遇）；
- 永不自动成为：实验数据/测量结果/故障率/真实维修时间/真实工程性能/文献事实；
- 可记录：provider/model/generation_method/timestamp/artifact_hash/prompt_hash；
- 绝不记录：API Key（provenance 字段白名单硬编码，白名单外字段丢弃+告警）。

## 6. 传输与存储的残余风险（诚实声明）

- `~/.aeromech/.env` 是明文文件（与 ppt-master 等同类工具一致）——本项目**不承诺**
  OS 级密钥环集成；文档给出平台加固指引（chmod 0600 / Windows 加密文件夹 / 
  CI 用 secrets 注入进程 env 不落盘）。
- 若未来要接系统 keyring，接口已隔离在 `image_config.resolve()` 一处，可替换实现。
