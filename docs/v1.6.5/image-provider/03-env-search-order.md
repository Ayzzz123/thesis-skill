# ENV_FILE_SEARCH_ORDER（03）

## 1. 优先级（§四，从高到低）

```
1. 当前进程环境变量（os.environ）           ← 临时覆盖/CI 注入/调试
2. 当前工作目录 .env（$CWD/.env）           ← 默认禁用（见 §3）
3. Skill 安装目录 .env                      ← 安装级共享配置（多项目共用 Skill 时）
4. 用户级 ~/.aeromech/.env                  ← 推荐持久位置（文档主路径）
```

首命中不合并（算法见 02 文档 §2）：文件层只认**第一个存在的文件**；
进程 env 对每个键单独最高优先。

## 2. 项目级 .env 的风险评估（§三 要求评估）

| 风险 | 说明 | 严重度 |
|---|---|---|
| 误提交 | 论文项目目录常被 zip/网盘/git 分享，Key 随论文源码外泄概率远高于 Skill 目录 | 高 |
| 语义误导 | 用户以为"论文项目里放 Key 是正规做法"，与"Key 不属于项目"的纪律冲突 | 中 |
| 多项目扩散 | 每项目一份 .env = 多份明文副本，轮换/删除困难 | 中 |
| 构建泄漏链 | 项目内文件会被 thesis_build/checkpoint 快照（CK-XXX 含 artifacts 哈希），Key 文件可能混入快照清单 | 低但真实 |

**结论（设计决定）**：项目级 .env **默认禁用**（`IMAGE_ALLOW_PROJECT_ENV=0`），
保留为逃生舱（某些 CI 场景确需），启用时：
- 解析器在 stderr 打警告（一次性）；
- `secret_leak_qa` 把项目内 `.env` 视为**高危文件**（存在即 WARN，含疑似 Key 即 BLOCK）；
- 文档推荐路径统一写 `~/.aeromech/.env`（§三 推荐一致）。

## 3. 各层路径规范

| 层 | 路径 | 权限/平台注意 |
|---|---|---|
| 进程 | `os.environ` | CI secrets 注入点；不落盘 |
| 项目 | `$CWD/.env` | 默认禁用；`.gitignore` 必含 `.env` |
| Skill | `<skill_home>/.env`，`skill_home = $AEROMECH_SKILL_HOME` 或 `~/.qoder-cn/skills/aeromech-thesis` | 安装目录被 sync.py 镜像管理——**Skill 级 .env 必须进 sync 排除清单**（否则 --to-install 删除对侧文件时误删/误同步 Key） |
| 用户 | `~/.aeromech/.env` | 推荐；`image config` 写入目标；建议 0600（Windows 提示 ACL） |

## 4. 与既有配置的边界

- `state.yaml`/`build-contract.yaml`/`materials.yaml`：**永不**存 Key（项目数据域）；
  契约可存 `image_backend: openai`（选择，非凭据）与 `model`（非敏感）。
- `AEROMECH_INSTALL_ROOT`（sync.py 既有）与本设计 `AEROMECH_SKILL_HOME` 分开：
  前者管开发镜像，后者管运行期解析，避免语义纠缠。

## 5. 验收映射（08 文档测试号）

- 优先级：RES-03（process 赢）、RES-04（cwd 默认禁用）、RES-05（skill 命中即停）、
  RES-06（user 兜底）
- 不合并：RES-07（两文件各半套键→NotConfigured 而非拼装）
- sync 排除：SEC-06（.env 不进镜像删除/复制清单）
