# -*- coding: utf-8 -*-
"""sync.py — aeromech-thesis 开发目录 ↔ 安装目录同步器（v1.4.1 建立，v1.5.0 加固）

约定：开发目录（DEV）为唯一权威编辑源；安装目录（INSTALL）是运行副本。
  python sync.py --check                 比对两侧（rc=0 一致 / rc=1 有差异）
  python sync.py --to-install            DEV → INSTALL（镜像：新增/覆盖，并删除 INSTALL 侧多余文件）
  python sync.py --to-dev                INSTALL → DEV（事故救援；镜像删除 DEV 侧多余文件）

安全护栏（v1.5.0，针对 2026-09-12 一次镜像同步误删开发目录事件的加固）：
  1) 任何删除只允许发生在**目标侧**，逐条断言路径不在源侧树内；
  2) 单次删除超过 DELETE_CAP(10) 个文件时必须显式 --force，否则跳过删除并 rc=1；
  3) 源侧为空/不存在时直接拒绝执行（防止把"源为空"误镜像成"目标清空"）；
  4) --dry-run 只打印计划不落盘。
退出码：0=一致/同步完成；1=存在差异或删除被跳过；3=参数或环境错误
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEV = os.path.join(HERE, "aeromech-thesis")
DEFAULT_INSTALL = os.path.join(os.path.expanduser("~"), ".qoder-cn", "skills", "aeromech-thesis")
IGNORE_DIRS = {"__pycache__", ".git", ".DS_Store", ".mimosa"}  # .mimosa=安全插件运行时状态（基线快照），与 .env 同性质不入镜像
IGNORE_SUFFIX = (".pyc", ".pyo", ".log")
IGNORE_NAMES = {".DS_Store", ".env"}   # v1.6.5：用户凭据文件不参与镜像（不复制、不删除）
REGRESSION_DIR = os.path.join("tests", "v1_4", "regression")
DELETE_CAP = 10


def _ignored(rel):
    parts = rel.replace("\\", "/").split("/")
    if any(p in IGNORE_DIRS or p == ".ipynb_checkpoints" for p in parts[:-1]):
        return True
    base = parts[-1]
    if base in IGNORE_NAMES or base.endswith(IGNORE_SUFFIX):
        return True
    # 回归证据（报告/PNG）只在开发目录留存，不参与一致性比对
    if rel.replace("\\", "/").startswith(REGRESSION_DIR.replace("\\", "/")) and \
            base != "regression-report.md":
        return True
    return False


def walk(root):
    out = set()
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for f in filenames:
            rel = os.path.relpath(os.path.join(dirpath, f), root)
            if not _ignored(rel):
                out.add(rel.replace("\\", "/"))
    return out


def _same_file(a, b):
    """逐字节比较（不使用 filecmp，避免同尺寸文件的缓存误判）。"""
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            while True:
                x, y = fa.read(1 << 20), fb.read(1 << 20)
                if x != y:
                    return False
                if not x:
                    return True
    except OSError:
        return False


def compare(dev, ins):
    a, b = walk(dev), walk(ins)
    only_dev = sorted(a - b)
    only_ins = sorted(b - a)
    diff = sorted(r for r in (a & b)
                  if not _same_file(os.path.join(dev, r), os.path.join(ins, r)))
    return only_dev, only_ins, diff


def _assert_dst_only(root_src, root_dst, rel):
    """删除护栏：目标侧路径必须位于目标树内，且不得等于/位于源树内。"""
    target = os.path.abspath(os.path.join(root_dst, rel))
    src_abs = os.path.abspath(root_src) + os.sep
    if not target.startswith(os.path.abspath(root_dst) + os.sep):
        raise RuntimeError(f"拒绝删除越界路径：{target}")
    if target.startswith(src_abs):
        raise RuntimeError(f"拒绝删除源侧文件：{target}")
    return target


def sync(dev, ins, direction, dry_run=False, force=False):
    src, dst = (dev, ins) if direction == "to-install" else (ins, dev)
    if not os.path.isdir(src):
        print(f"ERROR: 源目录不存在 {src}")
        return 3
    if not walk(src):
        print(f"ERROR: 源目录为空（拒绝把空源镜像到 {dst}）")
        return 3
    only_src, only_dst, diff = compare(dev, ins)
    adds = only_src if direction == "to-install" else only_dst
    dels = only_dst if direction == "to-install" else only_src
    plan = [f"copy    {r}" for r in adds + diff] + [f"delete  {r}" for r in dels]
    for line in plan:
        print(("DRY " if dry_run else "") + line,
              "[only-src]" if line.startswith("copy") and line.split()[-1] in adds else
              ("[different]" if line.startswith("copy") else ""), sep="")
    if dry_run:
        print(f"计划 {len(plan)} 项（copy={len(adds) + len(diff)} delete={len(dels)}）未执行")
        return 0
    skipped = []
    if len(dels) > DELETE_CAP and not force:
        print(f"WARN: 待删除 {len(dels)} 个文件超过上限 {DELETE_CAP}，已跳过删除（需 --force）")
        skipped = dels
        dels = []
    copied = 0
    for rel in adds + diff:
        s, t = os.path.join(src, rel), os.path.join(dst, rel)
        os.makedirs(os.path.dirname(t), exist_ok=True)
        shutil.copy2(s, t)
        copied += 1
    deleted = 0
    for rel in dels:
        target = _assert_dst_only(src, dst, rel)
        os.remove(target)
        deleted += 1
    rc_now, _ = 0, None
    o2, d2, f2 = compare(dev, ins)
    if not (o2 or d2 or f2) and not skipped:
        rc_now = 0
        verdict = "IDENTICAL"
    else:
        rc_now = 1
        verdict = f"REMAIN different={len(f2)} only-dev={len(o2)} only-install={len(d2)}"
    print(f"同步完成: copy={copied} delete={deleted} skipped_delete={len(skipped)}  "
          f"{verdict}: {dev} ↔ {dst}")
    return rc_now


def main():
    ap = argparse.ArgumentParser(description="aeromech-thesis dev/install 同步器")
    ap.add_argument("--dev", default=os.environ.get("AEROMECH_DEV_ROOT", DEFAULT_DEV))
    ap.add_argument("--install", default=os.environ.get("AEROMECH_INSTALL_ROOT", DEFAULT_INSTALL))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--to-install", action="store_true")
    g.add_argument("--to-dev", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="允许超过删除上限的镜像删除")
    args = ap.parse_args()
    dev, ins = os.path.abspath(args.dev), os.path.abspath(args.install)
    if args.check:
        o1, o2, f = compare(dev, ins)
        for r in o1:
            print(f"[only-dev]      {r}")
        for r in o2:
            print(f"[only-install]  {r}")
        for r in f:
            print(f"[different]     {r}")
        same = not (o1 or o2 or f)
        print(("IDENTICAL" if same else f"DIFFERENT dev={dev} install={ins}")
              + f"  (different={len(f)} only-dev={len(o1)} only-install={len(o2)})")
        return 0 if same else 1
    direction = "to-install" if args.to_install else "to-dev"
    return sync(dev, ins, direction, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
