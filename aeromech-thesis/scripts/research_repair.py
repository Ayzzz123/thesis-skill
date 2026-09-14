# -*- coding: utf-8 -*-
"""research_repair.py — Repair Plan Registry + Auto Repair Executor（aeromech-thesis v1.5.0）

按 §10/§11 建立修复计划并执行**白名单**自动修复；白名单之外一律人工（绝不捏造/扩范围/替换方法）。
白名单操作：论断强度降级（REVISE_CLAIM/CONCLUSION/ABSTRACT）、摘要数字同步、计算重执行（recompute）、
模拟标签回填。全部修复记录 before/after 并可复核。

用法：
  python research_repair.py <root> plan [--diagnosis-json <json>]
  python research_repair.py <root> execute [--ids REP-001,…] [--dry-run]
  python research_repair.py <root> apply-human [--queue <yaml>]
  python research_repair.py <root> status
退出码：0=成功；1=有失败/被拒修复；2=未初始化；3=ERROR
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_integrity as RI
import research_quality_qa as RQ
import yaml

# 强度/身份降级变换（长模式优先；只改“表述强度/口径”，不改技术事实）
DOWNGRADE_MAP = [
    ("试验结果表明", "模拟结果显示"),
    ("实验结果表明", "模拟结果显示"),
    ("实测发现", "模拟结果显示"),
    ("试验测得", "模拟生成"),
    ("在机队中的", "在模拟样本中的"),
    ("机队统计", "模拟数据统计"),
    ("机队中的", "模拟样本中的"),
    ("机队", "模拟样本"),
    ("实际运行数据", "模拟数据"),
    ("统计表明", "模拟结果提示"),
    ("统计显示", "模拟结果提示"),
    ("发生率为", "发生频率约为"),
    ("必然导致", "可能导致"),
    ("显著导致", "可能导致"),
    ("充分说明", "初步说明"),
    ("必然", "可能"),
    ("证明", "表明"),
    ("显著", "较为明显"),
    ("一定是", "可能是"),
    ("实测", "模拟"),
]
SIM_QUALIFIER = "（模拟条件下的初步判断）"

AUTO_OPERATIONS = {"downgrade_wording", "number_sync", "recompute", "fix_synth_label"}


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _chapters_files(root):
    d = os.path.join(root, ".aeromech", "artifacts", "chapters")
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".md")]


def _front_path(root):
    """摘要/前置材料文件（文件名因项目而异，判定规则与 RQG.load_texts 一致）。"""
    for p in _chapters_files(root):
        base = os.path.basename(p).lower()
        if "front" in base or "abstract" in base or "摘要" in base:
            return p
    return None


def _pkey(payload):
    """修复载荷的稳定可比键（用于跨轮次去重）。"""
    if not payload:
        return ""
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        return str(payload)


def downgrade_text(text):
    out = text
    for old, new in DOWNGRADE_MAP:
        if old in out:
            out = out.replace(old, new)
    return out


def _apply_text_replacement(root, old, new):
    """在章节 md 中做精确子串替换；返回改动文件列表。"""
    changed = []
    if not old or old == new:
        return changed
    for p in _chapters_files(root):
        s = open(p, encoding="utf-8").read()
        if old in s:
            open(p, "w", encoding="utf-8").write(s.replace(old, new))
            changed.append(os.path.relpath(p, root).replace("\\", "/"))
    return changed


# ---------------- 计划 ----------------
def plan(root, diagnoses=None):
    """由诊断生成 REP 条目（仅 auto_repairable 进入 proposed；人工项留在队列，不建 REP）。"""
    if diagnoses is None:
        jp = os.path.join(root, ".aeromech", "artifacts", "analysis", "research-diagnosis.json")
        if not os.path.isfile(jp):
            print("缺少诊断 JSON：请先运行 research_diagnosis.py")
            return []
        diagnoses = json.load(open(jp, encoding="utf-8")).get("diagnoses") or []
    existing = {(str(r.get("diagnosis_id")), str(r.get("operation")))
                for r in (RI.load_registry(root, "repairs") or [])}
    # 同一（操作, 目标, 载荷）已建过自动修复单：白名单变换是确定性的，重跑不会改善，
    # 且诊断规则来源可能换（diagnosis_id 变）导致重复建单 → 不再重复产出 REP
    tried = {(str(r.get("operation")), str((r.get("target_nodes") or [""])[0]), _pkey(r.get("payload")))
             for r in (RI.load_registry(root, "repairs") or []) if r.get("auto")}
    created = []
    planned = set()
    for d in diagnoses:
        if not d.get("auto_repairable"):
            continue
        rec = d.get("recommended_repair") or {}
        op = rec.get("operation")
        if op not in AUTO_OPERATIONS:
            continue
        if (d["diagnosis_id"], op) in existing:
            continue
        tgt = str((d.get("affected_nodes") or [rec.get("target")])[0])
        tkey = (op, tgt, _pkey(rec.get("payload") or {}))
        if tkey in tried or tkey in planned:
            continue  # 同一问题的多规则命中只建一条修复单
        planned.add(tkey)
        entry = {
            "diagnosis_id": d.get("diagnosis_id", ""),
            "target_nodes": d.get("affected_nodes") or [rec.get("target")],
            "repair_type": rec.get("repair_type", "REVISE_CLAIM"),
            "operation": op,
            "before": {"text": str(d.get("detail", ""))[:120]},
            "after": None,
            "payload": rec.get("payload") or {},
            "rationale": f"{d.get('issue_type', '')}："
                         + str(d.get("root_cause") or d.get("detail") or "")[:100],
            "expected_effect": f"消除 {d.get('issue_type', '')}（复检规则 {d.get('rule', '')}）",
            "risk": "低（白名单文本/数值操作，before/after 留痕）",
            "auto": True,
            "status": "proposed",
            "timestamp": _now(),
        }
        rid = RI.add_entry(root, "repairs", entry)
        created.append(rid)
    return created


# ---------------- 自动执行 ----------------
def _find_claim_like(root, reg, nid):
    items = RI.load_registry(root, reg) or []
    return next((x for x in items if str(x.get("id")) == str(nid)), None)


def _save_items(root, reg, items):
    RI.save_registry(root, reg, items)


def _execute_downgrade(root, rep):
    """论断/结论/摘要 强度降级。target_nodes 决定对象。"""
    payload = rep.get("payload") or {}
    results = {"registry_updates": [], "text_changes": [], "qualifier": False}
    target = str(payload.get("claim_id") or "")
    if target.startswith("CL-"):
        items = RI.load_registry(root, "claims") or []
        it = next((x for x in items if str(x.get("id")) == target), None)
        if not it:
            return False, "未找到目标 claim", results
        old = str(it.get("claim", ""))
        new = downgrade_text(old)
        if "模拟" not in new and payload.get("sim_context", True):
            new = new + SIM_QUALIFIER
            results["qualifier"] = True
        it["claim"] = new
        it["claim_strength"] = "C2"
        it["strength_note"] = "v1.5 自动降级（弱证据语境）"
        _save_items(root, "claims", items)
        results["registry_updates"].append(f"claims.yaml/{target}")
        results["text_changes"] = _apply_text_replacement(root, old, new)
        return True, f"claim {target} 降级", results
    if target.startswith("CON-"):
        items = RI.load_registry(root, "conclusions") or []
        it = next((x for x in items if str(x.get("id")) == target), None)
        if not it:
            return False, "未找到目标 conclusion", results
        old = str(it.get("conclusion", ""))
        new = downgrade_text(old)
        if "模拟" not in new and payload.get("sim_context", True):
            new = new + SIM_QUALIFIER
            results["qualifier"] = True
        it["conclusion"] = new
        _save_items(root, "conclusions", items)
        results["registry_updates"].append(f"conclusions.yaml/{target}")
        results["text_changes"] = _apply_text_replacement(root, old, new)
        return True, f"conclusion {target} 降级", results
    # 摘要身份措辞（RQG-09b）
    front = _front_path(root)
    if not front:
        return False, "未找到摘要文件", results
    s = open(front, encoding="utf-8").read()
    new = downgrade_text(s)
    if new == s:
        return False, "摘要未命中可降级措辞", results
    open(front, "w", encoding="utf-8").write(new)
    rel = os.path.relpath(front, root).replace("\\", "/")
    results["registry_updates"].append(rel)
    results["text_changes"] = [rel]
    return True, "摘要身份措辞降级", results


def _execute_number_sync(root, rep):
    payload = rep.get("payload") or {}
    old, new = str(payload.get("old", "")), str(payload.get("new", ""))
    results = {"registry_updates": [], "text_changes": []}
    if not old or not new:
        return False, "number_sync 缺少 old/new", results
    front = _front_path(root)
    if not front:
        return False, "未找到摘要文件", results
    s = open(front, encoding="utf-8").read()
    # 数字边界替换：避免把 1176 / 176.5 等其它数值一并改掉
    pat = re.compile(r"(?<![\d.])" + re.escape(old) + r"(?![\d.])")
    hits = len(pat.findall(s))
    if not hits:
        return False, f"摘要中未找到独立数值 {old}", results
    open(front, "w", encoding="utf-8").write(pat.sub(new, s))
    rel = os.path.relpath(front, root).replace("\\", "/")
    results["registry_updates"].append(rel)
    results["text_changes"] = [rel]
    return True, f"摘要数字 {old} → {new}（{hits} 处）", results


# ---------------- recompute 受控执行模型（B7 信任边界，v1.5.0） ----------------
# 为什么需要执行外部计算：CALC 注册条目（computations.yaml.recompute.cmd）声明"如何重算"；
#   修复器执行它把 output 从"登记值"升级为"可复算值"，是计算可复现规则（RQG-14）的闭环手段。
# 输入来源：命令文本仅来自本项目的注册表（用户/Agent 登记，非外部输入）；执行前按下列约束校验。
# 命令白名单：仅允许 `<python解释器> <项目内相对路径>.py [参数…]` 一种形态；
#   解释器一律替换为当前 sys.executable（忽略登记值），拒绝 shell 元字符、绝对路径、.. 越界、
#   `-c`/模块运行等任意代码入口。工作目录固定为 project_root；超时 180s；
#   子进程环境继承（无提权），失败/超时/退出码非零一律记 False 并留痕，绝不静默。
RECOMPUTE_CMD_RE = re.compile(r"^(?:python|python3|py)\s+(\S+\.py)((?:\s+\S+)*)$")


def _validate_recompute_cmd(root, cmd):
    """把登记的命令规约为 (argv 列表) 或 None（不合格）。禁止 shell=True 执行任意串。"""
    m = RECOMPUTE_CMD_RE.match(str(cmd).strip())
    if not m:
        return None
    script, extra = m.group(1), m.group(2).strip()
    if os.path.isabs(script) or ".." in script.replace("\\", "/").split("/"):
        return None
    script_abs = os.path.realpath(os.path.join(root, script))
    root_abs = os.path.realpath(root)
    if not script_abs.startswith(root_abs + os.sep) or not os.path.isfile(script_abs):
        return None
    argv = [sys.executable, script_abs] + (extra.split() if extra else [])
    return argv


def _execute_recompute(root, rep):
    payload = rep.get("payload") or {}
    cid = str(payload.get("calc_id") or "")
    rec = payload.get("recompute")
    results = {"registry_updates": [], "text_changes": []}
    if not rec or not cid:
        return False, "recompute 缺少 cmd/calc_id", results
    cmd = rec.get("cmd") if isinstance(rec, dict) else str(rec)
    if not cmd:
        return False, "recompute.cmd 为空", results
    argv = _validate_recompute_cmd(root, cmd)
    if argv is None:
        return False, ("recompute 命令不符合受控白名单（仅允许 `python <项目内相对路径>.py`，"
                       "禁 shell 元字符/绝对路径/越界），拒绝执行"), results
    try:
        p = subprocess.run(argv, shell=False, cwd=root, capture_output=True, text=True,
                           encoding="utf-8", timeout=180)
    except subprocess.TimeoutExpired:
        return False, "recompute 超时（>180s）", results
    if p.returncode != 0:
        return False, f"recompute 退出码 {p.returncode}: {(p.stderr or '')[:120]}", results
    out_line = ""
    for line in (p.stdout or "").splitlines():
        if line.startswith("OUTPUT="):
            out_line = line[len("OUTPUT="):].strip()
    items = RI.load_registry(root, "computations") or []
    it = next((x for x in items if str(x.get("id")) == cid), None)
    if not it:
        return False, f"未找到 {cid}", results
    if out_line:
        it["output"] = out_line
    it["verified"] = True
    it["verification"] = f"recompute 通过（{cmd}，{_now()}）"
    _save_items(root, "computations", items)
    results["registry_updates"].append(f"computations.yaml/{cid}")
    return True, f"{cid} 已重算" + (f"，output 更新为 {out_line[:60]}" if out_line else ""), results


def _execute_fix_label(root, rep):
    payload = rep.get("payload") or {}
    dsids = [str(x) for x in (payload.get("datasets") or [])]
    results = {"registry_updates": [], "text_changes": []}
    items = RI.load_registry(root, "datasets") or []
    fixed = []
    for it in items:
        if str(it.get("id")) in dsids:
            it["label"] = RI.SYNTH_LABEL
            fixed.append(str(it.get("id")))
    if not fixed:
        return False, "未找到目标数据集", results
    _save_items(root, "datasets", items)
    results["registry_updates"].append(f"datasets.yaml/{fixed}")
    return True, f"label 回填 {fixed}", results


def _verify_downgrade(root, rep):
    """复检：降级后文本不得再命中强断言/身份越界模式。"""
    payload = rep.get("payload") or {}
    target = str(payload.get("claim_id") or "")
    if target.startswith("CL-"):
        it = _find_claim_like(root, "claims", target)
        if not it:
            return False, f"复检失败：{target} 不在 claims 注册表"
        text = str(it.get("claim", ""))
    elif target.startswith("CON-"):
        it = _find_claim_like(root, "conclusions", target)
        if not it:
            return False, f"复检失败：{target} 不在 conclusions 注册表"
        text = str(it.get("conclusion", ""))
    else:
        front = _front_path(root)
        if not front:
            return False, "复检失败：未定位到摘要文件（不得据空文本判 PASS）"
        text = open(front, encoding="utf-8").read()
    hits = RQ._claim_hits(text, RQ.STRONG_PATTERNS_CRIT + RQ.STRONG_PATTERNS_HIGH)
    id_hits = RQ._claim_hits(text, RQ.REAL_CLAIM)
    ok = not hits and not id_hits
    return ok, f"复检：强断言命中={hits or '无'}；身份越界={id_hits or '无'}"


def _verify_number_sync(root, rep):
    payload = rep.get("payload") or {}
    old = str(payload.get("old", ""))
    front = _front_path(root)
    if not front:
        return False, "复检失败：未定位到摘要文件（不得据空文本判 PASS）"
    s = open(front, encoding="utf-8").read()
    ok = old not in RQ.numbers_of(s)
    return ok, f"复检：摘要不再含 {old}={ok}"


def _verify_recompute(root, rep):
    cid = str((rep.get("payload") or {}).get("calc_id") or "")
    it = next((x for x in (RI.load_registry(root, "computations") or [])
               if str(x.get("id")) == cid), None)
    ok = bool(it and it.get("verified"))
    return ok, f"复检：{cid} verified={bool(it and it.get('verified'))}"


def _verify_fix_label(root, rep):
    """复检：目标数据集 label 已为规定模拟标签。"""
    dsids = [str(x) for x in ((rep.get("payload") or {}).get("datasets") or [])]
    items = RI.load_registry(root, "datasets") or []
    missing = [d for d in dsids
               if not any(str(x.get("id")) == d and x.get("label") == RI.SYNTH_LABEL
                          for x in items)]
    ok = bool(dsids) and not missing
    return ok, f"复检：label 齐备={ok}" + (f"，缺失={missing}" if missing else "")


def execute(root, ids=None, dry_run=False):
    """执行 proposed 自动修复。返回 (done[], failed[])。"""
    items = RI.load_registry(root, "repairs") or []
    done, failed = [], []
    for it in items:
        rid = str(it.get("id"))
        if ids and rid not in ids:
            continue
        if str(it.get("status")) != "proposed" or not it.get("auto"):
            continue
        op = str(it.get("operation"))
        if op not in AUTO_OPERATIONS:
            continue
        if dry_run:
            done.append((rid, f"[dry-run] would execute {op}"))
            continue
        fn = {"downgrade_wording": _execute_downgrade, "number_sync": _execute_number_sync,
              "recompute": _execute_recompute, "fix_synth_label": _execute_fix_label}.get(op)
        try:
            ok, msg, res = fn(root, it)
        except Exception as e:
            ok, msg, res = False, f"异常 {type(e).__name__}: {e}", {}
        it["after"] = {"result": msg, "changes": res}
        it["status"] = "applied" if ok else "rejected"
        # 复检
        verify_fn = {"downgrade_wording": _verify_downgrade, "number_sync": _verify_number_sync,
                     "recompute": _verify_recompute, "fix_synth_label": _verify_fix_label}.get(op)
        if ok and verify_fn:
            vok, vmsg = verify_fn(root, it)
            it["verification"] = vmsg
            if vok:
                it["status"] = "verified"
            else:
                it["status"] = "applied"
                msg += "；" + vmsg
        if ok:
            done.append((rid, msg))
        else:
            failed.append((rid, msg))
        it["timestamp"] = _now()
    RI.save_registry(root, "repairs", items)
    return done, failed


# ---------------- 人工裁决执行（§24）----------------
def apply_human(root, queue_path=None, create_reps=True):
    """消费 human-review-queue.yaml：approve/modify 执行文本类修复；reject 记录为例外。"""
    qp = queue_path or os.path.join(root, ".aeromech", "research", "human-review-queue.yaml")
    results = {"applied": [], "rejected": [], "deferred": [], "needs_input": []}
    if not os.path.isfile(qp):
        return results
    q = yaml.safe_load(open(qp, encoding="utf-8")) or {}
    entries = q.get("queue") or []
    changed = False
    for e in entries:
        dec = str(e.get("decision") or "").strip().lower()
        if not dec:
            continue
        did = str(e.get("diagnosis_id"))
        payload = e.get("payload") or {}
        replacement = str(payload.get("replacement") or "")
        if str(e.get("applied_status") or "") in ("applied", "deferred", "rejected_by_human"):
            continue  # 已消费过的裁决不重复执行（幂等：避免重复 REP / 误判 needs_input）
        if dec == "reject":
            e["applied_status"] = "rejected_by_human"
            results["rejected"].append(did)
            changed = True
            continue
        if dec in ("approve", "modify"):
            rt = str(e.get("repair_type") or "")
            opt = str(e.get("option") or "")
            # 通道1：注册表字段更新（通用）：payload={registry, id, values:{field:value,…}}
            reg = str(payload.get("registry") or "")
            reg_id = str(payload.get("id") or "")
            reg_values = payload.get("values") or {}
            files = []
            if reg and reg_id and reg_values and reg in RI.REGISTRY_SPECS:
                items = RI.load_registry(root, reg) or []
                hit = None
                for it in items:
                    if str(it.get("id")) == reg_id:
                        it.update({k: v for k, v in reg_values.items()})
                        hit = it
                if hit is not None:
                    _save_items(root, reg, items)
                    files = [f"{reg}.yaml/{reg_id}"]
            # 通道2：文本替换（章节 md / 注册表单字段）
            elif rt in ("REWRITE_SECTION", "REVISE_CLAIM", "REVISE_CONCLUSION", "REVISE_ABSTRACT",
                        "REFRAME_RQ", "LIMIT_SCOPE"):
                if not replacement:
                    e["applied_status"] = "needs_input"
                    results["needs_input"].append(did)
                    changed = True
                    continue
                old_text = str(payload.get("old") or e.get("before_text") or "")
                files = _apply_text_replacement(root, old_text, replacement) if old_text else []
                if not files:
                    target = str(payload.get("target") or "")
                    for r2, key in (("conclusions", "conclusion"), ("claims", "claim"),
                                    ("rq", "question")):
                        items = RI.load_registry(root, r2) or []
                        hit = False
                        for it in items:
                            if target and str(it.get("id")) == target and key in it:
                                it[key] = replacement
                                hit = True
                        if hit:
                            _save_items(root, r2, items)
                            files = [f"{r2}.yaml"]
                            break
            if files:
                e["applied_status"] = "applied"
                results["applied"].append(f"{did}（{rt}{'/' + opt if opt else ''}）")
                if create_reps:
                    RI.add_entry(root, "repairs", {
                        "diagnosis_id": did,
                        "target_nodes": e.get("target_nodes") or ["（人工任务）"],
                        "repair_type": rt if rt in RI.REPAIR_TYPES else "REWRITE_SECTION",
                        "operation": None,
                        "before": {"text": (str(payload.get("old") or e.get("before_text") or ""))[:120]},
                        "after": {"changes": files,
                                  "text": (replacement or str(reg_values))[:120]},
                        "payload": payload, "rationale": f"人工裁决（{dec}）：{e.get('note', '')}",
                        "expected_effect": "按人工裁决修正研究与文本",
                        "risk": "由人工裁定；记录留痕", "auto": False, "status": "verified",
                        "verification": f"reviewer={e.get('reviewer', '?')}", "timestamp": _now()})
            elif rt not in ("REWRITE_SECTION", "REVISE_CLAIM", "REVISE_CONCLUSION",
                            "REVISE_ABSTRACT", "REFRAME_RQ", "LIMIT_SCOPE"):
                # 非文本类选项（ADD_EVIDENCE/CHANGE_METHOD/…）：人工承诺后续处理 → deferred
                e["applied_status"] = "deferred"
                results["deferred"].append(f"{did}（{rt}：{e.get('action', '')}）")
                if create_reps:
                    RI.add_entry(root, "repairs", {
                        "diagnosis_id": did, "target_nodes": e.get("target_nodes") or ["（人工任务）"],
                        "repair_type": rt if rt in RI.REPAIR_TYPES else "REQUEST_HUMAN_REVIEW",
                        "operation": None, "before": {"text": e.get("detail", "")[:120]},
                        "after": {"text": "deferred：由人工后续处理（记录留痕）"},
                        "payload": payload, "rationale": f"人工裁决（{dec}）：需人力/外部材料",
                        "expected_effect": "人工承担后续动作（非自动可修）", "risk": "需人工跟进",
                        "auto": False, "status": "applied",
                        "verification": f"reviewer={e.get('reviewer', '?')}", "timestamp": _now()})
            else:
                e["applied_status"] = "needs_input"
                results["needs_input"].append(did + "（未定位替换目标）")
            changed = True
        elif dec not in ("reject",):
            pass  # 未知 decision 忽略（队列文档已提示允许值）
    if changed:
        yaml.safe_dump(q, open(qp, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    return results


def status(root):
    items = RI.load_registry(root, "repairs") or []
    from collections import Counter
    c = Counter(str(x.get("status")) for x in items)
    return {"total": len(items), "by_status": dict(c)}


def main():
    ap = argparse.ArgumentParser(description="Repair Plan Registry & Executor（v1.5）")
    ap.add_argument("project_root")
    ap.add_argument("action", choices=["plan", "execute", "apply-human", "status"])
    ap.add_argument("--diagnosis-json", default=None)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--queue", default=None)
    args = ap.parse_args()
    root = args.project_root
    if not RI.initialized(root):
        print("注册表未初始化：.aeromech/research/ 不存在")
        return 2
    try:
        if args.action == "plan":
            diags = None
            if args.diagnosis_json:
                if not os.path.isfile(args.diagnosis_json):
                    print(f"ERROR: 诊断 JSON 不存在 {args.diagnosis_json}")
                    return 3
                diags = json.load(open(args.diagnosis_json, encoding="utf-8")).get("diagnoses")
            created = plan(root, diagnoses=diags)
            print("proposed:", created or "(无新计划)")
            return 0
        if args.action == "execute":
            ids = args.ids.split(",") if args.ids else None
            done, failed = execute(root, ids=ids, dry_run=args.dry_run)
            for rid, msg in done:
                print(f"  ✓ {rid} {msg}")
            for rid, msg in failed:
                print(f"  ✗ {rid} {msg}")
            return 1 if failed else 0
        if args.action == "apply-human":
            res = apply_human(root, queue_path=args.queue)
            print("applied:", res["applied"] or "[]")
            print("rejected:", res["rejected"] or "[]")
            print("deferred:", res["deferred"] or "[]")
            print("needs_input:", res["needs_input"] or "[]")
            return 0
        print("status:", status(root))
        return 0
    except RI.RegistryError as e:
        print(f"ERROR: 注册表损坏 {e.path}: {e.detail}")
        return 3
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"REPAIR ERROR: {type(e).__name__}: {e}（未产生 PASS 结论）")
        return 3


if __name__ == "__main__":
    sys.exit(main())
