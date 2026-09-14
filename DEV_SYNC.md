# DEV_SYNC — 开发目录同步规程（权威编辑源）

## 目录角色

| 角色 | 路径 | 说明 |
|---|---|---|
| **开发（权威源）** | `C:\Users\29603\Desktop\thesis-skill\aeromech-thesis` | 唯一允许编辑的位置 |
| 安装（运行副本） | `C:\Users\29603\.qoder-cn\skills\aeromech-thesis` | Skill 实际加载处，只由同步器写入 |

**禁止把安装目录当作开发源**：在 `~\.qoder-cn\skills\` 内的手改会被下一次同步覆盖。

## 标准工作流

```bash
# 1) 在开发目录改代码/文档
# 2) 跑测试（开发侧）
python tests/v1_4/run_all.py && python tests/v1_4_1/run_all.py && python tests/v1_5/run_all.py
# 3) 预览将要发生的变更（不落盘）
python sync.py --to-install --dry-run
# 4) 同步到安装目录并校验
python sync.py --to-install
python sync.py --check        # 期望输出 IDENTICAL，rc=0
# 5) 安装侧回归（真实加载路径）
```

## 同步器安全护栏（v1.5.0）

`sync.py` 是镜像同步：新增 + 覆盖 + 删除目标侧多余文件。v1.4.1 版本曾发生一次**误删开发目录**事件
（2026-09-12 22:58，一次 `--to-install` 之后 dev 侧 191 个文件被清除；安装目录完好，未造成成果丢失，
已用整树复制恢复）。v1.5.0 起加入四道护栏：

1. 删除只允许发生在目标侧，逐条断言路径不在源树内，越界即抛错中止；
2. 单次删除超过 10 个文件时跳过删除并要求 `--force`；
3. 源目录不存在或为空时拒绝执行（防止"空源镜像"清空目标）；
4. `--dry-run` 只打印计划。

事故当时的根因未能复现定位（涉事 sync.py 与事件同时丢失），因此按"最坏假设"加固而非声称已定位。

## 比对忽略规则

`__pycache__/`、`*.pyc|*.pyo|*.log`、`.DS_Store`，以及 `tests/v1_4/regression/**`
（回归证据只留在开发目录，`regression-report.md` 参与比对）。

## 版本一致性

两侧 `SKILL.md` 的版本行必须一致；`sync.py --check` 与 `tests/v1_4_1/test_dev_install_sync.py` 都会校验。
