# -*- coding: utf-8 -*-
"""tests/v1_4_1/test_dev_install_sync.py — 开发/安装目录同步规程

验证：
1. 开发目录（本测试所在的项目根，由文件位置动态推导）存在；同步说明文件存在；
   若存在安装副本，则两侧由 sync.py --check 判定逐字节一致，且版本号一致；
2. SKILL.md / README.md / CHANGELOG.md 三处版本联动一致（发布漏改即失败）；
3. 同步器自身能力（临时目录负例）：--check 检出差异（rc 1）→ --to-install 后一致（rc 0）；
   --to-dev 可做反向救援。

路径来源（2026-10-01 B8b 修复）：
  旧实现把开发/安装目录硬编码为具体用户名下的 `Desktop\\thesis-skill` 与
  `.qoder-cn\\skills`，仓库迁移后两个路径都不存在 → 5 项断言**整体 SKIP 而套件
  仍报通过**（假绿）。现在：
    · DEV 默认由 `__file__` 反推（本副本即开发目录），仅在显式设置
      AEROMECH_DEV_ROOT 时才采用外部副本；不再出现任何用户名/Desktop 硬编码。
    · 开发目录不存在 = 环境错误 → **FAIL**，不再 SKIP（未执行≠通过）。
    · 安装副本不存在属正常情况（本机未部署）→ 与之相关的对照检查记
      SKIPPED_WITH_REASON，但**同步器负例与版本联动仍照常执行**，保证套件
      始终有真实断言产出，不出现"全 SKIP 即通过"。
运行：python tests/v1_4_1/test_dev_install_sync.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))   # 本副本（即开发目录）
PASS, FAIL, SKIP = 0, 0, 0


def _derive_dev_root():
    """开发目录：显式环境变量优先；否则由本文件位置动态推导（禁止硬编码用户名）。"""
    env = os.environ.get("AEROMECH_DEV_ROOT")
    if env:
        return os.path.abspath(env)
    return SKILL


def _derive_sync():
    """sync.py 位于开发目录的上一级（repo 根）。"""
    cand = os.path.join(os.path.dirname(DEV), "sync.py")
    if os.path.isfile(cand):
        return cand
    # 兜底：repo 根即包含 aeromech-thesis 的那一层，逐级上溯（最多 3 层）
    cur = DEV
    for _ in range(3):
        cur = os.path.dirname(cur)
        p = os.path.join(cur, "sync.py")
        if os.path.isfile(p):
            return p
    return cand


DEV = _derive_dev_root()
SYNC = _derive_sync()


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def skip(name, why):
    global SKIP
    SKIP += 1
    print("  SKIPPED_WITH_REASON", name, "|", why)


def run(args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       encoding="utf-8", env=env, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def skill_version(root):
    p = os.path.join(root, "SKILL.md")
    if not os.path.isfile(p):
        return None
    m = re.search(r"版本：v([0-9.]+)", open(p, encoding="utf-8").read())
    return m.group(1) if m else None


def resolve_install():
    """安装副本：显式环境变量优先；否则探测常见部署位置（存在才算数）。"""
    env = os.environ.get("AEROMECH_INSTALL_ROOT")
    if env:
        return os.path.abspath(env) if os.path.isdir(env) else None
    home = os.path.expanduser("~")
    for rel in (os.path.join(".qoder-cn", "skills", "aeromech-thesis"),
                os.path.join(".codex", "skills", "aeromech-thesis"),
                os.path.join(".claude", "skills", "aeromech-thesis")):
        cand = os.path.join(home, rel)
        if os.path.isdir(cand) and os.path.abspath(cand) != SKILL:
            return cand
    return None


def main():
    print("== test_dev_install_sync ==")
    print(f"  [env] DEV={DEV}")
    print(f"  [env] SYNC={SYNC}")

    # ---- 0) 路径动态推导自检（防回退到硬编码）----
    check("B8B-01 开发目录由文件位置推导（本副本即 DEV，未用外部硬编码）",
          os.path.abspath(DEV) == os.path.abspath(
              os.environ.get("AEROMECH_DEV_ROOT") or SKILL),
          DEV)
    check("B8B-02 推导路径不含用户名硬编码（无 '\\Users\\<name>\\Desktop\\thesis-skill' 形态）",
          not re.search(r"[\\/]Users[\\/][^\\/]+[\\/]Desktop[\\/]thesis-skill", DEV),
          DEV)
    check("B8B-03 开发目录真实存在（缺失即环境错误，不 SKIP）",
          os.path.isdir(DEV) and os.path.isfile(
              os.path.join(DEV, "SKILL.md")), DEV)
    if not (os.path.isdir(DEV) and os.path.isfile(os.path.join(DEV, "SKILL.md"))):
        print(f"test_dev_install_sync 结果: PASS={PASS} FAIL={FAIL} SKIP={SKIP}")
        return 1

    # ---- 1) 开发侧必备文件与版本联动 ----
    check("B8B-04 sync.py 存在（repo 根）", os.path.isfile(SYNC), SYNC)
    repo_root = os.path.dirname(DEV)
    for doc in ("DEV_SYNC.md", "INSTALL_SYNC.md"):
        check(f"B8B-05 {doc} 存在", os.path.isfile(os.path.join(repo_root, doc)))

    v_dev = skill_version(DEV)
    check("B8B-06 SKILL.md 版本号可解析", v_dev is not None, str(v_dev))
    rm = re.search(r"aeromech-thesis v(\d+\.\d+\.\d+)",
                   open(os.path.join(DEV, "README.md"), encoding="utf-8").read())
    clg = open(os.path.join(DEV, "CHANGELOG.md"), encoding="utf-8").read()
    cm = re.search(r"^## v(\d+\.\d+\.\d+)", clg, re.M)
    check("B8B-07 README 与 SKILL.md 版本一致", rm and v_dev == rm.group(1),
          f"skill={v_dev} readme={rm.group(1) if rm else None}")
    check("B8B-08 CHANGELOG 顶部版本与 SKILL.md 一致", cm and v_dev == cm.group(1),
          f"skill={v_dev} changelog={cm.group(1) if cm else None}")

    # ---- 2) 安装副本（存在才对照；不存在属正常，记 SKIP 不影响其余断言）----
    install = resolve_install()
    if install:
        check("B8B-09 安装副本 SKILL.md 版本与开发侧一致",
              skill_version(install) == v_dev and v_dev is not None,
              f"dev={v_dev} install={skill_version(install)}")
        if os.path.isfile(SYNC):
            rc, out = run([SYNC, "--check"], cwd=repo_root)
            check("B8B-10 两侧逐字节一致（sync.py --check rc=0）", rc == 0,
                  out.strip().splitlines()[-1][:90] if out.strip() else "")
    else:
        skip("B8B-09/10 安装副本对照",
             "未发现安装副本（本机未部署；可设 AEROMECH_INSTALL_ROOT 指定）")

    # ---- 3) 同步器自身能力（临时目录负例；不依赖安装副本，始终执行）----
    tmp = tempfile.mkdtemp(prefix="v141_sync_")
    a = os.path.join(tmp, "dev", "skill")
    b = os.path.join(tmp, "install", "skill")
    os.makedirs(a); os.makedirs(b)
    open(os.path.join(a, "f1.txt"), "w", encoding="utf-8").write("A")
    open(os.path.join(b, "f1.txt"), "w", encoding="utf-8").write("B")      # 内容不同
    open(os.path.join(b, "extra.txt"), "w", encoding="utf-8").write("X")   # 安装侧多余
    if os.path.isfile(SYNC):
        rc1, out1 = run([SYNC, "--check", "--dev", a, "--install", b])
        check("B8B-11 负例：--check 检出差异 rc=1", rc1 == 1, f"rc={rc1}")
        check("B8B-12 负例：列出 [different]/[only-install]",
              "[different]" in out1 and "[only-install]" in out1)
        rc2, out2 = run([SYNC, "--to-install", "--dev", a, "--install", b])
        check("B8B-13 负例：--to-install 后 rc=0 且一致",
              rc2 == 0 and "IDENTICAL" in out2, f"rc={rc2}")
        check("B8B-14 负例：镜像删除安装侧多余文件",
              not os.path.isfile(os.path.join(b, "extra.txt")))
        open(os.path.join(b, "f1.txt"), "w", encoding="utf-8").write("RESCUE")
        rc3, _ = run([SYNC, "--to-dev", "--dev", a, "--install", b])
        check("B8B-15 负例：--to-dev 反向救援",
              rc3 == 0 and open(os.path.join(a, "f1.txt"), encoding="utf-8").read() == "RESCUE")
    else:
        # sync.py 缺失是环境错误（B8B-04 已 FAIL），此处不重复计 SKIP
        check("B8B-11..15 同步器负例因 sync.py 缺失无法执行", False, SYNC)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_dev_install_sync 结果: PASS={PASS} FAIL={FAIL} SKIP={SKIP}")
    # 有 SKIP 但无 PASS（说明连基本环境都没跑起来）→ 视为失败，避免"全 SKIP 即通过"
    if FAIL == 0 and PASS == 0:
        print("  [FAIL] 无任何有效断言产出（全 SKIP 不得视为通过）")
        return 1
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
