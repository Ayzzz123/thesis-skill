# INSTALL_SYNC — 安装目录（运行副本）规程

安装目录是 Skill 实际被加载的位置，**不是编辑对象**：

```
C:\Users\29603\.qoder-cn\skills\aeromech-thesis
```

## 规则

1. 安装目录内容只能由 `python sync.py --to-install`（在开发目录根执行）写入；
   在此目录内的任何手改都会在下次同步时被覆盖，且不会进入测试与版本记录。
2. 每次同步后必须 `python sync.py --check` 得到 `IDENTICAL`（rc=0），否则视为未同步完成。
3. 反向恢复只在开发目录被误删/损坏时使用：`python sync.py --to-dev`（会镜像删除开发侧多余文件，
   超过 10 个删除需 `--force`；先 `--dry-run` 看计划）。
4. 交付前的完整 QA（tf_qa / pdf_qa / cover / graph / RQG / agent loop）应在**安装目录的脚本**上跑一遍，
   因为它才是用户实际执行的代码；开发目录侧的测试用于快速迭代。
5. 忽略比对：`__pycache__/`、`*.pyc|*.pyo|*.log`、`.DS_Store`、`tests/v1_4/regression/**`（除 `regression-report.md`）。

角色、工作流与 v1.5.0 删除护栏详见同目录 `DEV_SYNC.md`。
