# -*- coding: utf-8 -*-
"""thesis_state.py — 项目状态机程序化读写（StateIO）+ Checkpoint 模型（aeromech-thesis v1.6.0）

规则真源：references/state.md（本脚本是其程序化执行体，不改 schema 语义，只增 checkpoint 工件）。
能力：
  - StateIO：load/save/validate state.yaml（损坏→备份+补默认；未知字段原样保留；schema 高版本只读）
  - transition：允许边/回退/返程/override 校验 + history 追加 + 备份规则（§11，保留 5 份）
  - open_issue：追加/关闭（§7 词表校验）
  - Checkpoint：`.aeromech/checkpoints/CK-XXX.yaml`（checkpoint_id/stage/task/ts/cursor/artifacts
    [存在性+sha256]/registries[条目数+validate 状态]/qa_state/next_action）
  - resume：最新 checkpoint + 现场比对 → 当前阶段/已完成/未完成/需重跑（不从头重启）
用法：
  python thesis_state.py <project_root> init
  python thesis_state.py <project_root> status
  python thesis_state.py <project_root> validate [--json]
  python thesis_state.py <project_root> transition <TO> [--type forward|revert|milestone|override]
      [--reason R] [--evidence p1,p2] [--issue ISS-001] [--override-note N]
  python thesis_state.py <project_root> issue <add|close> [--id ISS-001 --severity 高 --category data
      --target-stage S6 --desc D --close-condition C]
  python thesis_state.py <project_root> checkpoint [--task T] [--cursor K=V,..] [--artifacts p1,p2]
      [--next-action A] [--qa name=STATUS[@report]] [--json]
  python thesis_state.py <project_root> latest
  python thesis_state.py <project_root> resume [--json]
退出码：0=成功/迁移合法；1=校验发现问题/迁移拒绝；2=环境（无 .aeromech/）；3=ERROR（损坏/高版本只读冲突等）
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

import research_integrity as RI  # 复用注册表引擎读取（不重复实现）

SUPPORTED_SCHEMA = {"1.0", "1.1"}          # 1.1 仅新增 checkpoint 相关字段（additive）
STAGES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]
SEVERITY = ["严重", "高", "一般", "建议"]
CATEGORIES = ["structure", "academic", "citation", "engineering", "data", "figure", "writing", "integrity"]
ISSUE_STATUS = ["open", "in_progress", "closed"]
HISTORY_TYPES = ["forward", "revert", "milestone", "migrate", "override"]
GATE_STATES = ["passed", "conditional", "failed"]
PAPER_TYPES = ["research", "review", "design"]
EVIDENCE_TYPE_BY_PAPER = {"research": "data_or_analysis", "review": "literature", "design": "design_basis"}

# ---- 允许边（state.md §3；返程=回退逆边一律合法；S1→S3/S4→S7 等类型特例在前置条件里判）----
FORWARD = {
    ("S1", "S2"), ("S2", "S1"),
    ("S2", "S3"), ("S1", "S3"),
    ("S3", "S4"), ("S4", "S3"),
    ("S3", "S5"), ("S4", "S5"),
    ("S5", "S6"), ("S6", "S5"),
    ("S5", "S7"), ("S6", "S7"), ("S3", "S7"), ("S4", "S7"),
    ("S7", "S8"), ("S8", "S9"), ("S9", "S10"),
}
REVERT = ({(f, t) for f in ("S5", "S6", "S7", "S8") for t in ("S3", "S4", "S5", "S6") if f != t}
          | {("S8", "S7")}
          | {(f, t) for f in ("S9",) for t in ("S3", "S4", "S5", "S6", "S7")})
RETURN = {(t, f) for (f, t) in REVERT}   # 返程总规则

REMEDIATION = {
    "ST-SCHEMA": "按 state.md §10 迁移协议升级（先备份），或升级 Skill",
    "ST-FIELD": "补齐该字段（骨架见 state.md §15）",
    "ST-ENUM": "使用 state.md §1/§2 许可枚举值",
    "ST-EDGE": "查 state.md §3 允许边表；需要跳步请用 override（须二次确认+挂 open_issue）",
    "ST-PRECOND": "补齐 state.md §3/§5 所列前置产物后重试",
    "ST-REVERT": "回退必须由 QA 未关闭问题或依据缺口触发（state.md §3/§4）",
    "ST-RETURN": "返程须先把触发回退的 open_issue 全部 closed（state.md §3 返程总规则）",
    "ST-CORRUPT": "已从备份修复；若仍损坏请从 .bak-* 恢复后重跑 validate",
}


class StateError(Exception):
    """state.yaml 损坏/不可解析（稳定错误模型，绝不静默当空状态）。"""

    def __init__(self, path, detail):
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _p(root, *parts):
    return os.path.join(root, ".aeromech", *parts)


SKELETON = {
    "schema_version": "1.0",
    "project": {"title": "", "major": "", "paper_type": None, "composite": "", "direction": "",
                "object": "", "question": "", "school_requirement": ""},
    "stage": {"current": None, "history": [], "open_issues": []},
    "research": {"topic_card_file": "", "plan_file": "", "outline_file": "", "literature_file": "",
                 "literature_status": "none", "notes": ""},
    "data": {"status": "none", "registry": []},
    "writing": {"status": "not_started", "gate_evidence": {}, "chapters": {}},
    "document_generation": {},
    "qa": {"reports": [], "findings": []},
    "last_updated": "",
}


def _merge_defaults(target, skeleton, repaired, prefix=""):
    """骨架补缺失字段（只增不删；未识别字段原样保留，state.md §10）。"""
    if not isinstance(target, dict):
        return skeleton
    for k, v in skeleton.items():
        if k not in target or (target.get(k) is None and v is not None):
            target[k] = json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v
            repaired.append(prefix + k)
        elif isinstance(v, dict) and isinstance(target[k], dict):
            _merge_defaults(target[k], v, repaired, prefix + k + ".")
        elif isinstance(v, dict) and not isinstance(target[k], dict):
            repaired.append(prefix + k)     # 类型错→用默认替换（保留告知义务）
            target[k] = json.loads(json.dumps(v))
    return target


def _restore_from_backups(root):
    """按 mtime 新→旧尝试历史备份，返回 (data, 来源)；全部失败返回 (None, None)。"""
    p = _p(root, "state.yaml")
    for bak in sorted(glob.glob(p + ".bak-*"), key=os.path.getmtime, reverse=True):
        try:
            with open(bak, encoding="utf-8") as f:
                d = yaml.safe_load(f)
            if isinstance(d, dict):
                return d, bak
        except (yaml.YAMLError, OSError):
            continue
    return None, None


def load_state(root):
    """返回 (state, repaired_fields)。不存在→StateError；损坏→备份现场+回退最近可解析备份
    （无可用备份则按骨架补默认，state.md §12；repaired 非空供调用方告知）。"""
    p = _p(root, "state.yaml")
    if not os.path.isfile(p):
        raise StateError(p, "state.yaml 不存在")
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        _backup(root, "corrupt")                     # 现场留档（§11）
        restored, src = _restore_from_backups(root)
        if restored is None:
            raise StateError(p, f"YAML 解析失败且无可用备份: {e}")
        repaired = [f"<restored-from:{os.path.basename(src)}>"]
        state = _merge_defaults(restored, SKELETON, repaired)
        return state, repaired
    if not isinstance(data, dict):
        raise StateError(p, "顶层结构应为映射")
    sv = str(data.get("schema_version", ""))
    if sv and sv not in SUPPORTED_SCHEMA:
        raise StateError(p, f"schema_version={sv} 高于本 Skill 支持范围（只读运行，不写入）")
    repaired = []
    state = _merge_defaults(data, SKELETON, repaired)
    return state, repaired


def save_state(root, state):
    state["last_updated"] = _now()
    p = _p(root, "state.yaml")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(state, f, allow_unicode=True, sort_keys=False)
    return p


def _backup(root, tag):
    """state.md §11：命名 bak-<tag>-<ts>，全部 .bak-* 保留最近 5 份。"""
    p = _p(root, "state.yaml")
    if not os.path.isfile(p):
        return None
    dst = p + f".bak-{tag}-{datetime.datetime.now():%Y%m%d%H%M%S}"
    with open(p, "rb") as s, open(dst, "wb") as d:
        d.write(s.read())
    baks = sorted(glob.glob(p + ".bak-*"), key=os.path.getmtime)
    for old in baks[:-5]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


# ---------------- validate ----------------

def validate_state(state, root=None):
    """结构校验（§1/§2/§6/§7 词表），返回 problems[{code,field,reason,remediation}]。"""
    problems = []

    def bad(code, field, reason):
        problems.append({"code": code, "field": field, "reason": reason,
                         "remediation": REMEDIATION[code]})

    if str(state.get("schema_version", "")) not in SUPPORTED_SCHEMA:
        bad("ST-SCHEMA", "schema_version", f"应为 {sorted(SUPPORTED_SCHEMA)}")
    cur = (state.get("stage") or {}).get("current")
    if cur is not None and cur not in STAGES:
        bad("ST-ENUM", "stage.current", f"应为 S1..S10，实为 {cur!r}")
    pt = (state.get("project") or {}).get("paper_type")
    if pt is not None and pt not in PAPER_TYPES:
        bad("ST-ENUM", "project.paper_type", f"应为 {PAPER_TYPES}")
    for i, h in enumerate((state.get("stage") or {}).get("history") or []):
        f, t = h.get("from"), h.get("to")
        if t is not None and t not in STAGES or f is not None and f not in STAGES:
            bad("ST-ENUM", f"stage.history[{i}]", f"from/to 非法：{f}->{t}")
        if h.get("type") not in HISTORY_TYPES:
            bad("ST-ENUM", f"stage.history[{i}].type", f"应为 {HISTORY_TYPES}")
    for i, iss in enumerate((state.get("stage") or {}).get("open_issues") or []):
        if iss.get("severity") not in SEVERITY:
            bad("ST-ENUM", f"open_issues[{i}].severity", f"应为 {SEVERITY}")
        if iss.get("category") not in CATEGORIES:
            bad("ST-ENUM", f"open_issues[{i}].category", f"应为 {CATEGORIES}")
        if iss.get("status") not in ISSUE_STATUS:
            bad("ST-ENUM", f"open_issues[{i}].status", f"应为 {ISSUE_STATUS}")
        ts = iss.get("target_stage")
        if ts is not None and ts not in STAGES:
            bad("ST-ENUM", f"open_issues[{i}].target_stage", "应为 S1..S10")
    gp = ((state.get("writing") or {}).get("gate_evidence") or {}).get("gate_passed")
    if gp is not None and gp not in GATE_STATES:
        bad("ST-ENUM", "writing.gate_evidence.gate_passed", f"应为 {GATE_STATES}")
    ls = (state.get("research") or {}).get("literature_status")
    if ls is not None and ls not in ["none", "tracking", "collecting", "reviewed"]:
        bad("ST-ENUM", "research.literature_status", "应为 none/tracking/collecting/reviewed")
    if root is not None:
        for i, h in enumerate((state.get("stage") or {}).get("history") or []):
            for ev in h.get("evidence") or []:
                if isinstance(ev, str) and ev and not os.path.isabs(ev):
                    if not os.path.exists(_p(root, ev)) and not os.path.exists(os.path.join(root, ev)):
                        bad("ST-FIELD", f"stage.history[{i}].evidence", f"证据路径不存在：{ev}")
    return problems


# ---------------- 门禁证据（state.md §5 结构化部分） ----------------

def check_gate_evidence(state, root):
    """返回 (status ∈ passed|conditional|failed, problems)。只做可机械判定项；
    「证据完成判据」逐条语义核验仍属 Agent/RQG 职责。"""
    problems = []
    ge = ((state.get("writing") or {}).get("gate_evidence") or {})
    ptype = (state.get("project") or {}).get("paper_type")
    if not ge:
        return "failed", [{"code": "ST-PRECOND", "reason": "writing.gate_evidence 为空（S7 前必填，state.md §1/§5）"}]
    expect = EVIDENCE_TYPE_BY_PAPER.get(ptype)
    et = ge.get("evidence_type")
    if expect and et != expect:
        problems.append({"code": "ST-PRECOND",
                         "reason": f"paper_type={ptype} 要求 evidence_type={expect}，实为 {et!r}"})
    files = ge.get("evidence_files") or []
    if not files:
        problems.append({"code": "ST-PRECOND", "reason": "evidence_files 缺失或为空"})
    for rel in files:
        if not (os.path.exists(os.path.join(root, rel)) or os.path.exists(_p(root, rel))):
            problems.append({"code": "ST-PRECOND", "reason": f"证据文件不存在：{rel}"})
        elif os.path.getsize(os.path.join(root, rel) if os.path.exists(os.path.join(root, rel))
                             else _p(root, rel)) == 0:
            problems.append({"code": "ST-PRECOND", "reason": f"证据文件为空：{rel}"})
    if ptype == "review":
        if (state.get("research") or {}).get("literature_status") != "reviewed":
            problems.append({"code": "ST-PRECOND", "reason": "review 型要求 literature_status=reviewed"})
        lf = (state.get("research") or {}).get("literature_file") or "artifacts/literature.md"
        path = os.path.join(root, ".aeromech", lf) if not os.path.isabs(lf) else lf
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            problems.append({"code": "ST-PRECOND", "reason": "文献登记表缺失/为空"})
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            if "【已核实】" not in txt and "【用户提供·未核实】" not in txt:
                problems.append({"code": "ST-PRECOND", "reason": "登记表无【已核实】/【用户提供·未核实】条目"})
    declared = ge.get("gate_passed")
    if problems:
        status = "failed"
    elif declared == "conditional":
        if not ge.get("open_issues"):
            problems.append({"code": "ST-PRECOND", "reason": "conditional 必须挂 open_issues（state.md §5）"})
            status = "failed"
        else:
            status = "conditional"
    else:
        status = "passed"
    return status, problems


# ---------------- transition ----------------

def _edge_kinds(f, t):
    kinds = set()
    if (f, t) in FORWARD:
        kinds.add("forward")
    if (f, t) in REVERT:
        kinds.add("revert")
    if (f, t) in RETURN:
        kinds.add("return")     # 回退逆边（type 仍记 forward，state.md §3）
    if f == t:
        kinds.add("milestone")
    return kinds


def _open_issues(state, only_severe=False):
    out = []
    for iss in (state.get("stage") or {}).get("open_issues") or []:
        if iss.get("status") in ("open", "in_progress"):
            if only_severe and iss.get("severity") not in ("严重", "高"):
                continue
            out.append(iss)
    return out


def preconditions(state, root, f, t, kind):
    """目标阶段前置条件（state.md §3/§5 + §17.1 可机械判定项），返回 problems[]。"""
    problems = []
    proj = state.get("project") or {}
    res = state.get("research") or {}
    if t == "S3" and not proj.get("title"):
        problems.append("project.title 为空：题目未确定（§3 S2→S3 前置）")
    if f == "S1" and t == "S3" and not res.get("topic_card_file"):
        problems.append("S1→S3 要求题目卡片已产出（research.topic_card_file）")
    if t == "S4" and f == "S3" and not res.get("plan_file"):
        problems.append("S3→S4 要求研究方案已落盘（research.plan_file）")
    if t == "S7":
        status, gp = check_gate_evidence(state, root)
        if status == "failed":
            problems.extend(f"门禁证据不通过：{x['reason']}" for x in gp)
    if f == "S4" and t == "S7" and res.get("literature_status") != "reviewed":
        problems.append("S4→S7 要求 literature_status=reviewed（§3）")
    if t == "S8" and (state.get("writing") or {}).get("status") not in ("draft_done", "final"):
        problems.append("S7→S8 要求章稿完成（writing.status ∈ draft_done/final）")
    if t == "S9":
        if (state.get("writing") or {}).get("status") not in ("draft_done", "final"):
            problems.append("S8→S9 要求全稿齐备（writing.status）")
    if t == "S10" and f == "S9":
        for iss in _open_issues(state, only_severe=True):
            problems.append(f"未关闭严重/高问题 {iss.get('id')}（severity={iss.get('severity')}）：S9→S10 拒绝")
    if kind == "return":
        # 返程条件（触发回退的 open_issue 全部 closed 才能前进）：逐边 issue→阶段追溯
        # 由 Phase 3 orchestrator 基于 history/issue_id 实施；此处保持词表级检查。
        pass
    return problems


def transition(root, to, htype=None, reason="", evidence=None, issue_id=None, override_note=""):
    """执行迁移校验与写入。返回 (ok, result dict)。非法迁移不落盘（§9）。"""
    state, repaired = load_state(root)
    f = (state.get("stage") or {}).get("current")
    if f is None:
        return False, {"reason": "stage.current 为空，项目未初始化阶段", "repaired": repaired}
    kinds = _edge_kinds(f, to)
    if to not in STAGES:
        return False, {"reason": f"目标 {to} 不是合法阶段", "repaired": repaired}
    requested = htype or ("milestone" if f == to else ("forward" if kinds else None))
    ok_edge = (
        requested == "milestone" and "milestone" in kinds or
        requested == "forward" and (kinds & {"forward", "return"}) or
        requested == "revert" and ("revert" in kinds or (f, to) in FORWARD) or
        requested == "override")
    if not ok_edge:
        return False, {"reason": f"{f}→{to} 不在允许边内（请求 type={requested}）；合法路径见 state.md §3",
                       "repaired": repaired}
    kind = "return" if (requested == "forward" and (f, to) in RETURN and (f, to) not in FORWARD) else requested
    if requested == "revert":
        if not (reason or issue_id):
            return False, {"reason": "回退必须有触发源（reason 或 issue_id，state.md §4 第 4 步）",
                           "repaired": repaired}
    if requested == "milestone":
        probs = []          # 阶段内里程碑不重复校验进入该阶段的前置（state.md §6）
    else:
        probs = preconditions(state, root, f, to, kind)
    if requested == "override" and probs:
        # 强行推进：需 note（二次确认记录）+ 挂 open_issue（§9）
        if not override_note:
            return False, {"reason": "override 必须提供 --override-note（用户确认记录）且缺项转 open_issue",
                           "missing": probs, "repaired": repaired}
    elif probs:
        return False, {"reason": "前置条件不满足", "missing": probs, "repaired": repaired}

    if requested == "revert":
        _backup(root, "revert")            # §11 回退前备份
    hist = {"from": f, "to": to, "type": "forward" if kind == "return" else requested,
            "reason": reason or (override_note if requested == "override" else ""),
            "evidence": list(evidence or []), "issue_id": issue_id,
            "override": requested == "override", "ts": _now()}
    if hist["reason"] and requested == "override":
        hist["reason"] += f"（override：{override_note}）"
    state["stage"]["history"].append(hist)
    if requested != "milestone":
        state["stage"]["current"] = to
    if requested == "override":
        detail = f"：{'；'.join(probs)}" if probs else "（无缺项记录，用户坚持推进/跳门禁校验）"
        iss = _add_issue_dict(state, severity="高", category="structure",
                              target_stage=to, desc=f"强行推进 {f}→{to}{detail}")
        hist["issue_id"] = iss["id"]
    save_state(root, state)
    return True, {"from": f, "to": to, "type": hist["type"], "history": hist, "repaired": repaired}


def _next_id(state, key, fmt):
    n = 1
    ids = {str(x.get("id", "")) for x in state["stage"].get(key) or []}
    while fmt.format(n) in ids:
        n += 1
    return fmt.format(n)


def _add_issue_dict(state, **kw):
    iss = {"id": _next_id(state, "open_issues", "ISS-{:03d}"), "severity": kw["severity"],
           "category": kw["category"], "target_stage": kw.get("target_stage"),
           "desc": kw["desc"], "close_condition": kw.get("close_condition", ""),
           "status": "open", "raised_at": (state.get("stage") or {}).get("current"),
           "closed_at": None}
    state["stage"].setdefault("open_issues", []).append(iss)
    return iss


def add_issue(root, **kw):
    state, _ = load_state(root)
    iss = _add_issue_dict(state, **kw)
    save_state(root, state)
    return iss


def close_issue(root, issue_id):
    state, _ = load_state(root)
    for iss in state["stage"].get("open_issues") or []:
        if iss.get("id") == issue_id:
            if iss.get("status") == "closed":
                return iss
            iss["status"] = "closed"
            iss["closed_at"] = _now()
            save_state(root, state)
            return iss
    return None


# ---------------- Checkpoint（v1.6 新增工件；不改 state schema 既有语义） ----------------

def checkpoint_dir(root):
    return _p(root, "checkpoints")


def _sha(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _registry_snapshot(root):
    """复用注册表引擎：条目数 + 损坏标记（不重复实现校验）。"""
    errs = []
    snap = {}
    try:
        data = RI.load_all(root, collect_errors=errs)
    except RI.RegistryError as e:      # pragma: no cover
        errs.append(e)
        data = {}
    for name, items in data.items():
        snap[name] = {"count": len(items) if items is not None else None,
                      "present": items is not None}
    snap["_corrupt"] = sorted({str(e.path) for e in errs})
    return snap


def latest_checkpoint_id(root):
    items = load_checkpoints(root)
    return items[-1]["checkpoint_id"] if items else None


def load_checkpoints(root):
    out = []
    for p in sorted(glob.glob(os.path.join(checkpoint_dir(root), "CK-*.yaml"))):
        try:
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            continue                     # 单个损坏不拖垮 resume 视图（报告中标 missing-checkpoint）
        for cp in data.get("checkpoints") or []:
            cp["_file"] = p
            out.append(cp)
    return out


def create_checkpoint(root, stage=None, task=None, cursor=None, artifacts=None,
                      qa_state=None, next_action=""):
    state, _ = load_state(root)
    stage = stage or (state.get("stage") or {}).get("current")
    ids = [str(cp.get("checkpoint_id", "")) for cp in load_checkpoints(root)]
    n = 1
    while f"CK-{n:03d}" in ids:
        n += 1
    ckpt = {
        "checkpoint_id": f"CK-{n:03d}",
        "stage": stage,
        "task": task or "",
        "ts": _now(),
        "cursor": dict(cursor or {}),
        "artifacts": {},
        "registries": _registry_snapshot(root),
        "qa_state": dict(qa_state or {}),
        "next_action": next_action,
        "open_issues": [iss.get("id") for iss in _open_issues(state)],
    }
    for rel in artifacts or []:
        ap = os.path.join(root, rel) if not os.path.isabs(rel) else rel
        ckpt["artifacts"][rel.replace("\\", "/")] = {
            "exists": os.path.isfile(ap),
            "sha256": _sha(ap) if os.path.isfile(ap) else None,
        }
    os.makedirs(checkpoint_dir(root), exist_ok=True)
    p = os.path.join(checkpoint_dir(root), ckpt["checkpoint_id"] + ".yaml")
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump({"checkpoints": [ckpt]}, f, allow_unicode=True, sort_keys=False)
    # v1.6 additive：state 里记最新 checkpoint 引用（旧字段不动）
    state.setdefault("checkpoint", {})
    state["checkpoint"] = {"last_id": ckpt["checkpoint_id"], "file": f"checkpoints/{ckpt['checkpoint_id']}.yaml",
                           "ts": ckpt["ts"]}
    save_state(root, state)
    return ckpt


def _compare_checkpoint(root, cp):
    """现场 vs checkpoint：missing（产物丢失）/ changed（内容变化）/ ok。"""
    ok, missing, changed = [], [], []
    for rel, info in (cp.get("artifacts") or {}).items():
        ap = os.path.join(root, rel)
        if not info.get("exists") and not os.path.isfile(ap):
            ok.append(rel)                          # 登记时就缺，保持现状一致
            continue
        if not os.path.isfile(ap):
            missing.append(rel)
            continue
        cur = _sha(ap)
        (changed if cur != info.get("sha256") else ok).append(rel)
    return ok, missing, changed


def resume_view(root):
    """断点恢复视图（state.md §12 的程序化版本）：绝不从 S1 重启。"""
    state, repaired = load_state(root)
    cps = load_checkpoints(root)
    cp = cps[-1] if cps else None
    view = {
        "stage": (state.get("stage") or {}).get("current"),
        "title": (state.get("project") or {}).get("title", ""),
        "paper_type": (state.get("project") or {}).get("paper_type"),
        "open_issues": _open_issues(state),
        "repaired_fields": repaired,
        "checkpoint": cp.get("checkpoint_id") if cp else None,
        "checkpoint_stage": cp.get("stage") if cp else None,
        "next_action": (cp or {}).get("next_action") or "",
        "cursor": (cp or {}).get("cursor") or {},
        "qa_state": (cp or {}).get("qa_state") or {},
        "artifacts_ok": [], "artifacts_missing": [], "artifacts_changed": [],
        "checkpoint_behind": bool(cp and cp.get("stage")
                                  != (state.get("stage") or {}).get("current")),
    }
    if cp:
        view["artifacts_ok"], view["artifacts_missing"], view["artifacts_changed"] = \
            _compare_checkpoint(root, cp)
    probs = validate_state(state, root)
    view["state_problems"] = probs
    return view


# ---------------- CLI ----------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Thesis StateIO + Checkpoint（v1.6）")
    ap.add_argument("root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("validate").add_argument("--json", action="store_true")
    t = sub.add_parser("transition")
    t.add_argument("to")
    t.add_argument("--type", dest="htype", choices=HISTORY_TYPES)
    t.add_argument("--reason", default="")
    t.add_argument("--evidence", default="")
    t.add_argument("--issue", dest="issue_id", default=None)
    t.add_argument("--override-note", dest="override_note", default="")
    i = sub.add_parser("issue")
    i.add_argument("action", choices=["add", "close"])
    i.add_argument("--id", default=None)
    i.add_argument("--severity", choices=SEVERITY, default="高")
    i.add_argument("--category", choices=CATEGORIES, default="structure")
    i.add_argument("--target-stage", dest="target_stage", default=None)
    i.add_argument("--desc", default="")
    i.add_argument("--close-condition", dest="close_condition", default="")
    c = sub.add_parser("checkpoint")
    c.add_argument("--task", default="")
    c.add_argument("--cursor", default="", help="k=v,k2=v2")
    c.add_argument("--artifacts", default="", help="逗号分隔项目根相对路径")
    c.add_argument("--next-action", dest="next_action", default="")
    c.add_argument("--qa", action="append", default=[], help="name=STATUS[@report-path]，可重复")
    c.add_argument("--json", action="store_true")
    sub.add_parser("latest")
    r = sub.add_parser("resume")
    r.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)

    if not os.path.isdir(_p(root)) and a.cmd != "init":
        print(f"未找到 .aeromech/：{root}")
        return 2

    if a.cmd == "init":
        os.makedirs(_p(root, "artifacts", "analysis"), exist_ok=True)
        os.makedirs(_p(root, "artifacts", "chapters"), exist_ok=True)
        os.makedirs(_p(root, "artifacts", "qa"), exist_ok=True)
        os.makedirs(_p(root, "artifacts", "defense"), exist_ok=True)
        p = _p(root, "state.yaml")
        if os.path.isfile(p):
            print("state.yaml 已存在，不覆盖（用 status 查看）")
            return 0
        st = json.loads(json.dumps(SKELETON))
        st["stage"]["history"].append({"from": None, "to": "S1", "type": "forward",
                                       "reason": "项目初始化", "evidence": [], "issue_id": None,
                                       "override": False, "ts": _now()})
        st["stage"]["current"] = "S1"
        save_state(root, st)
        print(f"已初始化 {p}")
        return 0

    try:
        if a.cmd == "status":
            state, repaired = load_state(root)
            v = validate_state(state, root)
            print(f"stage.current={state['stage'].get('current')} title={state['project'].get('title')!r} "
                  f"paper_type={state['project'].get('paper_type')} 未关闭问题={len(_open_issues(state))} "
                  f"history={len(state['stage'].get('history') or [])} 校验问题={len(v)}"
                  + (f" repaired={repaired}" if repaired else ""))
            return 1 if v else 0
        if a.cmd == "validate":
            state, repaired = load_state(root)
            probs = validate_state(state, root)
            if a.json:
                print(json.dumps({"ok": not probs, "repaired": repaired, "problems": probs},
                                 ensure_ascii=False))
            else:
                for pr in probs:
                    print(f"[{pr['code']}] {pr['field']}: {pr['reason']}")
                print(f"validate: {'PASS' if not probs else f'{len(probs)} 问题'}"
                      + (f"（已补默认 {repaired}）" if repaired else ""))
            return 1 if probs else 0
        if a.cmd == "transition":
            ev = [x for x in (a.evidence or "").split(",") if x]
            ok, res = transition(root, a.to, a.htype, a.reason, ev, a.issue_id, a.override_note)
            if ok:
                print(f"迁移 {res['from']}→{res['to']} type={res['type']} 完成（history +1，"
                      f"last_updated 已刷新）")
                return 0
            print(f"迁移拒绝：{res.get('reason')}")
            for m in res.get("missing") or []:
                print(f"  - 缺：{m}")
            return 1
        if a.cmd == "issue":
            if a.action == "add":
                iss = add_issue(root, severity=a.severity, category=a.category,
                                target_stage=a.target_stage, desc=a.desc,
                                close_condition=a.close_condition)
                print(f"已挂 {iss['id']}（severity={iss['severity']} target={iss['target_stage']}）")
                return 0
            iss = close_issue(root, a.id)
            if iss is None:
                print(f"未找到问题 {a.id}")
                return 1
            print(f"{iss['id']} 已关闭（closed_at={iss['closed_at']}）")
            return 0
        if a.cmd == "checkpoint":
            cur = {}
            for kv in filter(None, (a.cursor or "").split(",")):
                k, _, v = kv.partition("=")
                cur[k] = v
            qa = {}
            for item in a.qa:
                name, _, val = item.partition("=")
                st, _, rep = val.partition("@")
                qa[name] = {"status": st, "report": rep or None}
            arts = [x for x in (a.artifacts or "").split(",") if x]
            arts += _auto_artifacts(root)
            ck = create_checkpoint(root, task=a.task or None, cursor=cur or None,
                                   artifacts=arts, qa_state=qa or None,
                                   next_action=a.next_action)
            if a.json:
                ck.pop("_file", None)
                print(json.dumps(ck, ensure_ascii=False))
            else:
                print(f"{ck['checkpoint_id']} @ {ck['stage']} 已写入 "
                      f"（artifacts={len(ck['artifacts'])} registries="
                      f"{sum(1 for v in ck['registries'].values() if isinstance(v, dict) and v.get('present'))} "
                      f"qa={len(ck['qa_state'])}）")
            return 0
        if a.cmd == "latest":
            cps = load_checkpoints(root)
            if not cps:
                print("无 checkpoint")
                return 2
            cp = cps[-1]
            print(f"{cp['checkpoint_id']} @ {cp.get('stage')} ts={cp.get('ts')} "
                  f"next_action={cp.get('next_action') or '-'}")
            return 0
        if a.cmd == "resume":
            v = resume_view(root)
            if a.json:
                print(json.dumps(v, ensure_ascii=False))
            else:
                print(f"【恢复】题目：{v['title'] or '（未定）'}（{v['paper_type']}）")
                print(f"【阶段】{v['stage']}（checkpoint {v['checkpoint']}@{v['checkpoint_stage']}"
                      + ("，注意：checkpoint 与当前阶段不一致" if v["checkpoint_behind"] else "") + "）")
                print(f"【产物】完好 {len(v['artifacts_ok'])} · 丢失 {len(v['artifacts_missing'])} "
                      f"· 变化 {len(v['artifacts_changed'])}")
                for x in v["artifacts_missing"]:
                    print(f"  丢失：{x}")
                for x in v["artifacts_changed"]:
                    print(f"  变化：{x}")
                for iss in v["open_issues"]:
                    print(f"  未关闭：{iss['id']} [{iss['severity']}] {iss['desc']}")
                print(f"【下一步】{v['next_action'] or '（checkpoint 未记录，按 state.md §3 推荐）'}")
                print(f"【校验】state 问题 {len(v['state_problems'])}"
                      + (f"，已修复字段 {v['repaired_fields']}" if v["repaired_fields"] else ""))
            return 1 if v["state_problems"] or v["artifacts_missing"] else 0
    except StateError as e:
        print(f"ERROR: {e}")
        return 3
    except RI.RegistryError as e:
        print(f"ERROR(registry): {e}")
        return 3
    return 3


def _auto_artifacts(root):
    """常规阶段产物：存在即入 checkpoint（供 resume 比对，不硬编码题目相关内容）。"""
    candidates = [".aeromech/research/rq.yaml", ".aeromech/research/design.yaml",
                  ".aeromech/research/scope.yaml", ".aeromech/materials.yaml",
                  ".aeromech/school-format.yaml", ".aeromech/research/traceability.json"]
    return [c for c in candidates if os.path.isfile(os.path.join(root, c))]


if __name__ == "__main__":
    sys.exit(main())
