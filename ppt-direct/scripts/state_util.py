# -*- coding: utf-8 -*-
"""state_util.py — ppt-direct 状态机（.pptdirect/state.yaml 唯一真源）

规则文本见 references/state.md；本文件是实现。对齐 aeromech-thesis 的设计：
允许边校验、产物落盘后才迁移、回退需触发源、备份轮换、override 记 open_issue。

用法:
  python state_util.py init <工程目录>
  python state_util.py status <工程目录>
  python state_util.py transition <工程目录> --to S3 --reason "大纲定稿" \
      [--type forward|revert|milestone|override] [--issue ISS-001]
退出码: 0=成功；1=校验失败/非法迁移
"""
import argparse
import datetime
import os
import shutil
import sys

import yaml

SCHEMA_VERSION = "1.0"
STAGES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]

FORWARD = {("S1", "S2"), ("S2", "S3"), ("S3", "S4"), ("S4", "S5"),
           ("S3", "S5"), ("S5", "S6"), ("S6", "S7")}
REVERT = {("S3", "S2"), ("S4", "S3"), ("S5", "S3"), ("S5", "S4"),
          ("S6", "S2"), ("S6", "S3"), ("S6", "S4"), ("S6", "S5"),
          ("S7", "S6")}
RETURN = {(b, a) for a, b in REVERT}  # 返程总规则：revert 逆边合法

SKELETON = {
    "schema_version": SCHEMA_VERSION,
    "project": {"title": "", "presenter": "", "major": "", "school": "",
                "advisor": "", "date": "", "page_tier": "standard",
                "duration_min": 8, "input_source": None, "source_path": ""},
    "stage": {"current": None, "history": [], "open_issues": []},
    "outline": {"file": "", "sections": 0},
    "deck": {"file": "", "slides": 0},
    "theme": {"file": "", "mode": None},
    "build": {"pptx_file": "", "layout_file": ""},
    "qa": {"reports": []},
    "last_updated": "",
}


def state_path(root):
    return os.path.join(root, ".pptdirect", "state.yaml")


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load(root):
    path = state_path(root)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"state 不存在: {path}（先 init）")
    with open(path, encoding="utf-8") as f:
        st = yaml.safe_load(f)
    if st.get("schema_version", "0") > SCHEMA_VERSION:
        raise RuntimeError("schema_version 高于当前 Skill，只读运行")
    return st


def save(root, st):
    st["last_updated"] = _now()
    path = state_path(root)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(st, f, allow_unicode=True, sort_keys=False)


def backup(root, tag):
    src = state_path(root)
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M")
    dst = f"{src}.bak-{tag}-{ts}"
    shutil.copy2(src, dst)
    d = os.path.dirname(src)
    olds = sorted(f for f in os.listdir(d) if f.startswith("state.yaml.bak-"))
    for f in olds[:-5]:  # 保留最近 5 份
        os.remove(os.path.join(d, f))
    return dst


def init(root, start="S1"):
    os.makedirs(os.path.join(root, ".pptdirect", "artifacts",
                             "qa"), exist_ok=True)
    st = yaml.safe_load(yaml.safe_dump(SKELETON))  # 深拷贝
    st["stage"]["current"] = start
    st["stage"]["history"].append({
        "from": None, "to": start, "type": "forward",
        "reason": "项目初始化", "evidence": [], "issue_id": None,
        "override": False, "ts": _now()})
    save(root, st)
    return st


def _file_ok(root, rel):
    return bool(rel) and os.path.isfile(os.path.join(root, rel))


def gate_missing(root, st, to):
    """前进边前置条件；返回缺失项列表（空=通过）。"""
    miss = []
    if to == "S2":
        if not st["project"]["title"]:
            miss.append("project.title")
        if not st["project"]["input_source"]:
            miss.append("project.input_source（aeromech/docx/manual）")
    elif to == "S3":
        if not _file_ok(root, st["outline"]["file"]):
            miss.append("outline.file（页级大纲落盘）")
    elif to == "S4":
        if not _file_ok(root, st["deck"]["file"]):
            miss.append("deck.file（逐页内容落盘）")
    elif to == "S5":
        if not _file_ok(root, st["deck"]["file"]):
            miss.append("deck.file")
        if not _file_ok(root, st["theme"]["file"]):
            miss.append("theme.file（内置默认或校模提取）")
    elif to == "S6":
        if not _file_ok(root, st["build"]["pptx_file"]):
            miss.append("build.pptx_file（渲染产物）")
    elif to == "S7":
        blocking = [i for i in st["stage"]["open_issues"]
                    if i.get("severity") in ("严重", "高")
                    and i.get("status") != "closed"]
        if blocking:
            miss.append("未关闭的严重/高问题: "
                        + ", ".join(i["id"] for i in blocking))
    return miss


def transition(root, to, reason, type_="forward", issue_id=None,
               override=False):
    st = load(root)
    cur = st["stage"]["current"]
    if to not in STAGES:
        raise ValueError(f"未知阶段 {to}，合法值 {STAGES}")

    if cur == to:
        type_ = "milestone"
    else:
        edge = (cur, to)
        legal = (edge in FORWARD or edge in REVERT or
                 (type_ == "forward" and edge in RETURN))
        if not legal and not override:
            raise ValueError(
                f"当前 {cur}，请求 {to}，该迁移不在允许边内。"
                f"合法路径: {sorted(e for e in FORWARD | REVERT if e[0] == cur)}")
        if type_ == "forward" and edge in FORWARD:
            miss = gate_missing(root, st, to)
            if miss and not override:
                raise ValueError(f"门禁未通过，缺失: {'; '.join(miss)}")
        if type_ == "revert" and not (reason or issue_id):
            raise ValueError("回退必须有触发源（reason 或 issue_id）")

    if type_ == "revert":
        backup(root, "revert")
    if override:
        n = len(st["stage"]["open_issues"]) + 1
        st["stage"]["open_issues"].append({
            "id": f"ISS-{n:03d}", "severity": "高", "category": "process",
            "target_stage": cur, "desc": f"用户强行推进 {cur}→{to}：{reason}",
            "close_condition": "补齐该阶段门禁证据", "status": "open",
            "raised_at": cur, "closed_at": None})
        type_ = "override"

    st["stage"]["history"].append({
        "from": cur, "to": to, "type": type_, "reason": reason,
        "evidence": [], "issue_id": issue_id, "override": bool(override),
        "ts": _now()})
    st["stage"]["current"] = to
    save(root, st)
    return st


def status_summary(root):
    st = load(root)
    open_issues = [i for i in st["stage"]["open_issues"]
                   if i.get("status") != "closed"]
    lines = [
        f"【恢复】题目：{st['project']['title'] or '（未定）'}",
        f"【阶段】当前 {st['stage']['current']} · 输入源 "
        f"{st['project']['input_source'] or '未定'} · 档位 "
        f"{st['project']['page_tier']}",
        f"【已定】大纲 {st['outline']['file'] or '无'} · deck "
        f"{st['deck']['file'] or '无'}({st['deck']['slides']}页) · 主题 "
        f"{st['theme']['mode'] or '未定'} · 产物 {st['build']['pptx_file'] or '无'}",
        "【未关闭问题】" + (", ".join(
            f"{i['id']}({i['severity']})" for i in open_issues) or "无"),
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="ppt-direct 状态机")
    ap.add_argument("cmd", choices=["init", "status", "transition"])
    ap.add_argument("root")
    ap.add_argument("--to")
    ap.add_argument("--reason", default="")
    ap.add_argument("--type", default="forward",
                    choices=["forward", "revert", "milestone", "override"])
    ap.add_argument("--issue", default=None)
    ap.add_argument("--override", action="store_true")
    a = ap.parse_args()
    try:
        if a.cmd == "init":
            init(a.root)
            print(f"OK: 初始化 {state_path(a.root)}")
        elif a.cmd == "status":
            print(status_summary(a.root))
        else:
            if not a.to:
                print("FAIL: transition 需要 --to")
                return 1
            st = transition(a.root, a.to, a.reason, a.type, a.issue,
                            a.override)
            print(f"OK: → {st['stage']['current']}")
        return 0
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
