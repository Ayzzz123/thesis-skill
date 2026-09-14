# -*- coding: utf-8 -*-
"""material_ingestion.py — 统一材料进入流程（aeromech-thesis v1.6.0）

规则真源：references/state.md §16（materials.yaml schema、目录契约、来源等级）。
本脚本把"登记"从纯手工升格为程序化流程：扫描 → SHA256 → 去重（已登记且未变更 = 不再读取）
→ 类型推断 → 注册 → 确认。原始文件只读不改（§16 规则 3）。

子命令：
  scan     <root> [--json]     # 现场材料与登记表比对（新增/变更/缺失/已登记）
  register <root> (--add rel:type:authority ... | --all) [--notes N] [--json]
      --all 把全部未登记文件按推断类型注册（verification_status=pending）；--add 显式指定。
      同哈希重复内容不注册（WARN），由人工处置。
  check    <root> [--json]     # 现场=登记？（供 Orchestrator 前置条件使用）
用法示例：
  python material_ingestion.py <root> scan
  python material_ingestion.py <root> register --add "materials/school/模板.docx:school_template:school"
  python material_ingestion.py <root> register --all --notes "冷启动扫描注册"
退出码：0=成功/一致；1=有差异（未登记/变更/缺失）或参数错误；3=ERROR（materials.yaml 损坏）
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

# state.md §16 type 枚举 + v1.6 指令 §八 扩展（school notice/task book/proposal）。只增不改。
MATERIAL_TYPES = ["school_template", "school_notice", "task_book", "proposal", "literature_pdf",
                  "technical_manual", "standard_doc", "project_data", "sample_thesis"]
AUTHORITY = ["school", "user_provided", "public_verified", "secondary", "model_knowledge"]
AVAILABILITY = ["uploaded", "pending", "missing"]
VERIFICATION = ["verified", "pending", "unverified"]

# 目录 → 推断类型（与 state.md §16.3 目录契约一致）
DIR_TYPE = {
    "school": "school_template",
    "literature": "literature_pdf",
    "technical_manual": "technical_manual",
    "standard": "standard_doc",
    "project_data": "project_data",
    "samples": "sample_thesis",
}
# school 目录内文件名细分（优先级高于目录默认值）
NAME_TYPE = [(re.compile(p, re.I), t) for p, t in [
    (r"模板|template", "school_template"),
    (r"任务书", "task_book"),
    (r"开题", "proposal"),
    (r"通知|须知|要求|规范|规定|notice", "school_notice"),
]]


def _p(root, *parts):
    return os.path.join(root, ".aeromech", *parts)


def materials_yaml_path(root):
    return _p(root, "materials.yaml")


def _hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_materials(root):
    """返回条目列表；文件不存在→None（未初始化）；损坏→RuntimeError（CLI 转退出码 3）。"""
    p = materials_yaml_path(root)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(f"materials.yaml 损坏: {e}")
    if not isinstance(data, dict):
        raise RuntimeError("materials.yaml 顶层应为映射（含 materials 键）")
    items = data.get("materials")
    if items is None:
        items = []
    if not isinstance(items, list):
        raise RuntimeError("materials 应为列表")
    return items


def save_materials(root, items):
    p = materials_yaml_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump({"materials": items}, f, allow_unicode=True, sort_keys=False)


def scan_disk(root):
    """遍历 materials/（新契约）与 .aeromech/materials/（旧结构兼容，标记 legacy）。"""
    found = []
    for base, is_legacy in ((os.path.join(root, "materials"), False),
                            (_p(root, "materials"), True)):
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if fn.startswith("."):
                    continue
                ap = os.path.join(dirpath, fn)
                rel = os.path.relpath(ap, root).replace("\\", "/")
                sub = os.path.relpath(dirpath, base).replace("\\", "/")
                top = sub.split("/", 1)[0] if sub != "." else ""
                mtype = None
                if top == "school":
                    for pat, t in NAME_TYPE:
                        if pat.search(fn):
                            mtype = t
                            break
                if mtype is None:
                    mtype = DIR_TYPE.get(top)
                found.append({"rel": rel, "filename": fn, "top_dir": top,
                              "inferred_type": mtype, "legacy": is_legacy,
                              "sha256": _hash(ap), "size": os.path.getsize(ap)})
    return found


def _norm_hash(entry):
    ho = str(entry.get("hash_or_identifier") or "")
    return ho[7:] if ho.startswith("sha256:") else ""


def classify(root):
    """返回 (unchanged, new, changed, missing, legacy)。
    去重键：sha256 优先，回落登记 filename 路径。已登记且哈希一致 → 不重复读取。"""
    disk = scan_disk(root)
    reg = load_materials(root)
    if reg is None:
        return [], disk, [], [], {d["rel"] for d in disk if d["legacy"]}
    by_hash, by_name = {}, {}
    for e in reg:
        if e.get("availability") == "uploaded":
            h = _norm_hash(e)
            if h:
                by_hash[h] = e
            fn = str(e.get("filename") or "").replace("\\", "/")
            if fn:
                by_name.setdefault(fn, e)
    unchanged, new, changed = [], [], []
    for d in disk:
        hit = by_hash.get(d["sha256"]) or by_name.get(d["rel"])
        if hit is None:
            new.append(d)
        elif _norm_hash(hit) and _norm_hash(hit) != d["sha256"]:
            changed.append({**d, "material_id": hit.get("material_id")})
        else:
            unchanged.append({**d, "material_id": hit.get("material_id")})
    missing = [e for e in reg
               if e.get("availability") == "uploaded" and e.get("filename")
               and not os.path.isfile(os.path.join(root, str(e["filename"]).replace("\\", "/")))]
    return unchanged, new, changed, missing, {d["rel"] for d in disk if d["legacy"]}


def _next_material_id(existing):
    used = {str(e.get("material_id", "")) for e in existing}
    n = 1
    while f"MAT-{n:03d}" in used:
        n += 1
    return f"MAT-{n:03d}"


def register(root, add=None, all_new=False, notes=""):
    unchanged, new, changed, missing, legacy = classify(root)
    reg = list(load_materials(root) or [])
    disk = {d["rel"]: d for d in scan_disk(root)}
    existing_hashes = {_norm_hash(e) for e in reg if _norm_hash(e)}
    added, warn = [], []

    def mk(d, mtype, auth):
        eid = _next_material_id(reg + added)
        return {"material_id": eid, "filename": d["rel"], "availability": "uploaded",
                "type": mtype, "source": "", "authority": auth,
                "date": datetime.date.today().isoformat(),
                "hash_or_identifier": f"sha256:{d['sha256']}", "used_by": [],
                "verification_status": "pending",
                "notes": notes or "自动扫描注册，来源待人工确认"}

    targets = []
    if all_new:
        targets += [(d, d["inferred_type"] or "project_data",
                     "school" if d["top_dir"] == "school" else "user_provided") for d in new]
    for spec in add or []:
        parts = spec.split(":")
        rel = parts[0].replace("\\", "/")
        mtype = parts[1] if len(parts) > 1 and parts[1] else None
        auth = parts[2] if len(parts) > 2 and parts[2] else "user_provided"
        d = disk.get(rel)
        if d is None:
            warn.append(f"跳过（磁盘无此文件）：{rel}")
            continue
        targets.append((d, mtype or d["inferred_type"] or "project_data", auth))
    for d, mtype, auth in targets:
        if mtype not in MATERIAL_TYPES:
            warn.append(f"跳过（未知类型 {mtype}，允许 {MATERIAL_TYPES}）：{d['rel']}")
            continue
        if auth not in AUTHORITY:
            warn.append(f"跳过（未知来源等级 {auth}）：{d['rel']}")
            continue
        if d["sha256"] in existing_hashes:
            warn.append(f"{d['rel']} 与已登记材料内容重复（同哈希），未注册")
            continue
        e = mk(d, mtype, auth)
        reg.append(e)
        added.append(e)
        existing_hashes.add(d["sha256"])
    save_materials(root, reg)
    return added, warn, unchanged, changed, missing


def report(root):
    unchanged, new, changed, missing, legacy = classify(root)
    lines = [f"materials.yaml 登记条目：{len(load_materials(root) or [])}",
             f"磁盘扫描：已登记完好 {len(unchanged)} · 未登记 {len(new)} · 内容变更 {len(changed)} · 登记但文件缺失 {len(missing)}"]
    for d in new:
        lines.append(f"  [new]     {d['rel']} type={d['inferred_type']}")
    for d in changed:
        lines.append(f"  [changed] {d['rel']}（哈希与登记 {d['material_id']} 不符：材料可能被替换，"
                     f"人工确认后更新登记，本工具不自动改写）")
    for e in missing:
        lines.append(f"  [missing] {e.get('filename')}（登记 {e.get('material_id')} 存在，文件缺失）")
    if legacy:
        lines.append("  [legacy]  检出旧结构 .aeromech/materials/（兼容读取；建议迁移至根目录 materials/）")
    consistent = not new and not changed and not missing
    return lines, consistent


def main(argv=None):
    ap = argparse.ArgumentParser(description="Material Ingestion（v1.6）")
    ap.add_argument("root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--json", action="store_true")
    r = sub.add_parser("register")
    r.add_argument("--add", action="append", default=[], help="relpath:type:authority，可重复")
    r.add_argument("--all", action="store_true")
    r.add_argument("--notes", default="")
    r.add_argument("--json", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    try:
        if a.cmd == "scan":
            unchanged, new, changed, missing, legacy = classify(root)
            if a.json:
                print(json.dumps({"unchanged": [d["rel"] for d in unchanged],
                                  "new": [{"rel": d["rel"], "inferred_type": d["inferred_type"],
                                           "sha256": d["sha256"]} for d in new],
                                  "changed": [d["rel"] for d in changed],
                                  "missing": [e.get("filename") for e in missing],
                                  "legacy": sorted(legacy)}, ensure_ascii=False))
            else:
                print("\n".join(report(root)[0]))
            return 0
        if a.cmd == "register":
            if not a.add and not a.all:
                print("register 需要 --add 或 --all")
                return 1
            added, warn, *_ = register(root, a.add, a.all, a.notes)
            for w in warn:
                print("WARN:", w)
            if a.json:
                print(json.dumps({"added": [f"{e['material_id']}:{e['filename']}" for e in added],
                                  "warnings": warn}, ensure_ascii=False))
            else:
                print(f"已注册 {len(added)} 条：" + (", ".join(e["material_id"] for e in added) or "（无新增）"))
            return 0
        if a.cmd == "check":
            lines, consistent = report(root)
            if a.json:
                print(json.dumps({"consistent": consistent, "lines": lines}, ensure_ascii=False))
            else:
                print("\n".join(lines))
                print("check:", "PASS（现场=登记）" if consistent else "FAIL（有差异）")
            return 0 if consistent else 1
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
