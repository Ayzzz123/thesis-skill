# -*- coding: utf-8 -*-
"""tests/v1_4_1/test_dev_install_sync.py — 开发/安装目录同步规程

验证：
1. 开发目录（Desktop\\thesis-skill\\aeromech-thesis）存在且与安装目录逐字节一致
   （由 sync.py --check 判定；开发目录缺失时本测试 SKIPPED_WITH_REASON，不伪造 PASS）；
2. DEV_SYNC.md / INSTALL_SYNC.md 存在，且两侧 SKILL.md 版本号一致（v1.4.1）；
3. 同步器自身能力（临时目录负例）：--check 检出差异（rc 1）→ --to-install 后一致（rc 0）；
   --to-dev 可做反向救援。
运行：python tests/v1_4_1/test_dev_install_sync.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))   # 本测试所在副本（dev 或 install）
DEV = os.environ.get("AEROMECH_DEV_ROOT", r"C:\Users\29603\Desktop\thesis-skill\aeromech-thesis")
INSTALL = os.environ.get("AEROMECH_INSTALL_ROOT", r"C:\Users\29603\.qoder-cn\skills\aeromech-thesis")
SYNC = os.path.join(os.path.dirname(DEV), "sync.py")
PASS, FAIL, SKIP = 0, 0, 0


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


def main():
    print("== test_dev_install_sync ==")
    global SKIP

    # ---- 1) 开发目录存在性与两侧一致性 ----
    if not os.path.isdir(DEV):
        skip("dev 目录存在", f"未找到 {DEV}（可设 AEROMECH_DEV_ROOT）")
        skip("DEV_SYNC/INSTALL_SYNC 说明", "同上")
        skip("两侧逐字节一致", "同上")
        skip("两侧版本号一致", "同上")
    elif not os.path.isfile(SYNC):
        check("sync.py 存在", False, SYNC)
    else:
        check("dev 目录存在", True, DEV)
        for doc in ("DEV_SYNC.md", "INSTALL_SYNC.md"):
            check(f"{doc} 存在", os.path.isfile(os.path.join(os.path.dirname(DEV), doc)))
        rc, out = run([SYNC, "--check"], cwd=os.path.dirname(DEV))
        check("两侧逐字节一致（sync.py --check rc=0）", rc == 0, out.strip().splitlines()[-1][:90])
        ins_dir = INSTALL if os.path.isdir(INSTALL) else SKILL
        v_dev, v_ins = skill_version(DEV), skill_version(ins_dir)
        check("两侧 SKILL.md 版本一致", v_dev == v_ins and v_dev is not None,
              f"dev={v_dev} install({ins_dir})={v_ins}")
        check("版本为 1.4.1", v_dev == "1.4.1", str(v_dev))
        check("install 侧含 research-human-review.md",
              os.path.isfile(os.path.join(ins_dir, "references", "research-human-review.md")))

    # ---- 2) 同步器自身能力（临时目录，不影响真实目录）----
    tmp = tempfile.mkdtemp(prefix="v141_sync_")
    a = os.path.join(tmp, "dev", "skill")
    b = os.path.join(tmp, "install", "skill")
    os.makedirs(a); os.makedirs(b)
    open(os.path.join(a, "f1.txt"), "w", encoding="utf-8").write("A")
    open(os.path.join(b, "f1.txt"), "w", encoding="utf-8").write("B")      # 内容不同
    open(os.path.join(b, "extra.txt"), "w", encoding="utf-8").write("X")   # 安装侧多余
    if os.path.isfile(SYNC):
        rc1, out1 = run([SYNC, "--check", "--dev", a, "--install", b])
        check("负例：--check 检出差异 rc=1", rc1 == 1, f"rc={rc1}")
        check("负例：列出 [different]/[only-install]",
              "[different]" in out1 and "[only-install]" in out1)
        rc2, out2 = run([SYNC, "--to-install", "--dev", a, "--install", b])
        check("负例：--to-install 后 rc=0 且一致", rc2 == 0 and "IDENTICAL" in out2, f"rc={rc2}")
        check("负例：镜像删除安装侧多余文件", not os.path.isfile(os.path.join(b, "extra.txt")))
        # 反向救援
        open(os.path.join(b, "f1.txt"), "w", encoding="utf-8").write("RESCUE")
        rc3, _ = run([SYNC, "--to-dev", "--dev", a, "--install", b])
        check("负例：--to-dev 反向救援",
              rc3 == 0 and open(os.path.join(a, "f1.txt"), encoding="utf-8").read() == "RESCUE")
    else:
        skip("同步器负例", "sync.py 不存在（dev 根目录缺失）")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_dev_install_sync 结果: PASS={PASS} FAIL={FAIL} SKIP={SKIP}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
