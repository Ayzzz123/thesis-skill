# -*- coding: utf-8 -*-
"""figure_iface.py — Figure Provider 接口与生命周期（aeromech-thesis v1.6.0，Phase 4）

定位（指令 §一/§二十）：主线只定义**契约与适配层**，不复制 Figure Engine。协作者分支
feature-1.6.0-figure-generation 提供新 Provider 时，只需实现 FigureProvider 三方法并在
contract/命令行里 --provider 切换；本文件不 import 任何协作者代码。

契约（指令 §一/§二）：
  FigureProvider.plan(root, specs=None)      -> [FigureSpec]         # 规划清单（机读）
  FigureProvider.generate(root, spec)        -> FigureResult        # 出图（artifact 落盘）
  FigureProvider.validate(root, spec/result) -> FigureResult        # 几何/可读性校验

FigureSpec（输入）：figure_id, name, kind, source, out, display_number,
                   related_rqs/related_analyses/related_claims/data_source（研究链接，§四）
FigureResult（输出）：figure_id, status, artifact, sha256, quality（checks 列表）,
                     reason, provider, timestamp（§三/§十五）

生命周期（指令 §三）：PLANNED → GENERATED → VALIDATED → EMBEDDED → VERIFIED；
失败分支 REJECTED / NEEDS_HUMAN_REVIEW。每一步追加记录到
  <root>/.aeromech/figures/figure-lifecycle.yaml
  {figure_id, ts, artifact, sha256, status, reason, provider}
研究真值仍在 v1.4 figures.yaml（本模块只读引用 + 生命周期日志，不改注册表写入路径）。

默认 LocalProvider：
  kind=mermaid → 复用 scripts/render_mermaid.py（仅 mmdc 真实渲染可 GENERATED；v1.6.5：假内容 fallback 已删除，FIGURE_ERROR→REJECTED 且清理残留文件，不落占位图）
  kind=script  → 项目内生成脚本（figkit/matplotlib），受控执行（同 v1.5 recompute 信任边界：
                 仅 sys.executable 跑项目根内相对 .py，无 shell，cwd=root，180s 超时）
  validate     → 复用 graph_quality_qa.check_graphs（单图几何检查，基于 figkit layout JSON）；
                 无 layout 证据 → NEEDS_HUMAN_REVIEW（机器判不了不装懂）

用法：
  python figure_iface.py <root> plan [--provider local] [--json]
  python figure_iface.py <root> generate --figure FIG-001 [--provider local]
  python figure_iface.py <root> generate-all [--provider local]
  python figure_iface.py <root> validate --figure FIG-001 [--json]
  python figure_iface.py <root> status [--json]
  python figure_iface.py <root> record --figure FIG-001 --status EMBEDDED [--reason R] [--artifact p]
退出码：0=全部 OK；1=存在 REJECTED/NEEDS_HUMAN_REVIEW（判定成功但流程受阻）；2=无计划（NOT_APPLICABLE）；3=ERROR
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML（pip install pyyaml）")
    sys.exit(2)

import research_integrity as RI

LIFECYCLE = ["PLANNED", "GENERATED", "VALIDATED", "EMBEDDED", "VERIFIED",
             "REJECTED", "NEEDS_HUMAN_REVIEW"]
STATUS_OK = ("PLANNED", "GENERATED", "VALIDATED", "EMBEDDED", "VERIFIED")


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _sha(path):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def figures_dir(root):
    return os.path.join(root, ".aeromech", "figures")


def plan_path(root):
    return os.path.join(figures_dir(root), "figure-plan.yaml")


def lifecycle_path(root):
    return os.path.join(figures_dir(root), "figure-lifecycle.yaml")


# ---------------- Provider 抽象与注册 ----------------

class FigureProvider:
    """协作者/第三方实现只需继承本类并注册：PROVIDERS["name"] = cls。"""
    name = "abstract"

    def plan(self, root, specs=None):
        raise NotImplementedError

    def generate(self, root, spec):
        raise NotImplementedError

    def validate(self, root, spec):
        raise NotImplementedError


PROVIDERS = {}


def register_provider(cls):
    PROVIDERS[getattr(cls, "name", cls.__name__)] = cls
    return cls


def get_provider(name="local"):
    cls = PROVIDERS.get(name)
    if cls is None:
        raise KeyError(f"未注册的 FigureProvider: {name}（可用 {sorted(PROVIDERS)}）")
    return cls()


# ---------------- 计划读写（机读格式；figure-plan.md 仍是人读产物） ----------------

def load_plan(root):
    p = plan_path(root)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("figures") or []


def save_plan(root, specs, provider="local"):
    os.makedirs(figures_dir(root), exist_ok=True)
    with open(plan_path(root), "w", encoding="utf-8") as f:
        yaml.safe_dump({"provider": provider, "figures": specs}, f,
                       allow_unicode=True, sort_keys=False)


def research_links(root, figure_id):
    """§四 研究可追溯：figures.yaml（v1.4 注册表，只读）里的论证链接。"""
    try:
        items = RI.load_registry(root, "figures") or []
    except RI.RegistryError:
        return None
    for it in items:
        if str(it.get("id")) == figure_id:
            return {"related_rqs": it.get("related_rqs") or [],
                    "related_analyses": it.get("related_analyses") or [],
                    "related_claims": it.get("related_claims") or []}
    return {}


def linked(links):
    if not links:
        return False
    return any(links.get(k) for k in ("related_rqs", "related_analyses", "related_claims"))


# ---------------- 生命周期记录 ----------------

def load_lifecycle(root):
    p = lifecycle_path(root)
    if not os.path.isfile(p):
        return {}
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = {}
    for rec in data.get("history") or []:
        out.setdefault(rec.get("figure_id"), []).append(rec)
    return out


def record(root, figure_id, status, artifact=None, reason="", provider="local",
           sha=None):
    if status not in LIFECYCLE:
        raise ValueError(f"非法生命周期状态 {status}（允许 {LIFECYCLE}）")
    ap = os.path.join(root, artifact) if artifact and not os.path.isabs(artifact) else artifact
    hist = load_lifecycle(root)
    # v1.6.5 Phase 2A（§九）：自由文本边界统一脱敏——异常文本可能携带凭据，
    # lifecycle.yaml 会进交付项目，落盘前必须过 redact_text。
    try:
        from image_config import redact_text
        reason = redact_text(reason)
    except ImportError:
        pass
    rec = {"figure_id": figure_id, "ts": _now(), "status": status,
           "artifact": artifact.replace("\\", "/") if artifact else None,
           "sha256": sha or (_sha(ap) if ap else None), "reason": reason,
           "provider": provider}
    hist.setdefault(figure_id, []).append(rec)
    os.makedirs(figures_dir(root), exist_ok=True)
    with open(lifecycle_path(root), "w", encoding="utf-8") as f:
        yaml.safe_dump({"history": [r for lst in hist.values() for r in lst]},
                       f, allow_unicode=True, sort_keys=False)
    return rec


def current_status(root, figure_id):
    hist = load_lifecycle(root)
    lst = hist.get(figure_id) or []
    return lst[-1]["status"] if lst else None, (lst[-1] if lst else None)


# ---------------- Local Provider（复用既有脚本函数，不复制逻辑） ----------------

class LocalProvider(FigureProvider):
    name = "local"

    def plan(self, root, specs=None):
        """无显式 specs → 从 v1.4 figures.yaml 注册表 + 磁盘 mmd/script 推导计划。
        仅图（FIG-*）进入图像生命周期；TABLE-* 表条目无图像产物，不记 lifecycle
        （v1.6 test-8.0 修复：表条目以 NEEDS_HUMAN_REVIEW 污染 G-FIG-01 域）。"""
        out = []
        try:
            reg = RI.load_registry(root, "figures") or []
        except RI.RegistryError as e:
            raise RuntimeError(str(e))
        fdir = os.path.join(root, ".aeromech", "artifacts", "figures")
        for it in reg:
            fid = str(it.get("id"))
            if not fid.startswith("FIG-"):
                continue
            mmd = os.path.join(fdir, fid + ".mmd")
            script = os.path.join(fdir, fid + ".py")
            png = os.path.join(fdir, "final", os.path.basename(str(it.get("name", ""))[:20]) + ".png")
            kind, source = None, None
            if os.path.isfile(mmd):
                kind, source = "mermaid", os.path.relpath(mmd, root).replace("\\", "/")
            elif os.path.isfile(script):
                kind, source = "script", os.path.relpath(script, root).replace("\\", "/")
            out.append({"figure_id": fid, "name": it.get("name", fid), "kind": kind,
                        "source": source, "out": os.path.relpath(png, root).replace("\\", "/"),
                        "type": it.get("type"),   # v1.6.5：图类型分派（VIS-11 输入）
                        "related_rqs": it.get("related_rqs") or [],
                        "related_analyses": it.get("related_analyses") or [],
                        "related_claims": it.get("related_claims") or []})
        if specs:
            out = list(specs)
        return out

    def generate(self, root, spec):
        fid = spec.get("figure_id")
        kind = spec.get("kind")
        rel_out = spec.get("out") or os.path.join(
            ".aeromech", "artifacts", "figures", "final", fid + ".png")
        out = rel_out if os.path.isabs(rel_out) else os.path.join(root, rel_out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if kind == "mermaid":
            return self._gen_mermaid(root, spec, out, rel_out)
        if kind == "script":
            return self._gen_script(root, spec, out, rel_out)
        rec = record(root, fid, "NEEDS_HUMAN_REVIEW",
                     reason=f"无法自动出图：kind={kind!r} 无对应生成路径（不产占位图）",
                     provider=self.name)
        return _result(fid, "NEEDS_HUMAN_REVIEW", rel_out, None, rec,
                       reason="无机器生成路径，需人工/协作者 Provider 处理")

    def _gen_mermaid(self, root, spec, out, rel_out):
        import render_mermaid as RM
        mmd = os.path.join(root, spec["source"]) if spec.get("source") else None
        fid = spec.get("figure_id")
        if not mmd or not os.path.isfile(mmd):
            rec = record(root, fid, "NEEDS_HUMAN_REVIEW", artifact=rel_out,
                         reason="缺少 .mmd 源（不伪造输入）", provider=self.name)
            return _result(fid, "NEEDS_HUMAN_REVIEW", rel_out, None, rec,
                           reason="mmd 源缺失")
        ok, msg, _br, code = RM.render_with_mmdc(mmd, out, "transparent")
        if ok:
            return self._ok(root, fid, rel_out, out, reason="mermaid 渲染成功")
        # v1.6.5（D2）：失败即失败。不生成任何可冒充真实模型的 fallback；
        # mmdc 失败可能留下残缺文件——清理，防止半成品混进交付。
        if os.path.isfile(out):
            try:
                os.remove(out)
            except OSError:
                pass
        rec = record(root, fid, "REJECTED", artifact=None,
                     reason=f"FIGURE_ERROR：mmdc 渲染失败（{code}；{str(msg)[:80]}）；"
                            f"假内容 fallback 已废除（v1.6.5），该图需修复环境或改用"
                            f"忠实源（figkit 脚本）重生成；不得进入最终论文",
                     provider=self.name)
        return _result(fid, "REJECTED", None, None, rec, reason="FIGURE_ERROR")

    def _gen_script(self, root, spec, out, rel_out):
        fid = spec.get("figure_id")
        script = spec.get("source") or ""
        sp = os.path.join(root, script) if not os.path.isabs(script) else script
        # 受控执行模型（同 v1.5 recompute 信任边界）：项目根内相对 .py，无 shell
        rel = os.path.relpath(sp, root).replace("\\", "/")
        if not script or rel.startswith("..") or os.path.isabs(script) or not rel.endswith(".py") \
                or not os.path.isfile(sp) or any(c in rel for c in "&|;<>`$"):
            rec = record(root, fid, "NEEDS_HUMAN_REVIEW", artifact=rel_out,
                         reason=f"生成脚本不合法（越界/非项目内 .py）：{script}", provider=self.name)
            return _result(fid, "NEEDS_HUMAN_REVIEW", rel_out, None, rec, reason="脚本校验失败")
        try:
            p = subprocess.run([sys.executable, rel], cwd=root, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=180)
        except subprocess.TimeoutExpired:
            rec = record(root, fid, "REJECTED", artifact=rel_out, reason="生成脚本超时 180s",
                         provider=self.name)
            return _result(fid, "REJECTED", rel_out, None, rec, reason="timeout")
        if p.returncode != 0 or not os.path.isfile(out):
            rec = record(root, fid, "REJECTED", artifact=rel_out,
                         reason=f"脚本失败 rc={p.returncode}: {p.stderr[-160:] or p.stdout[-160:]}",
                         provider=self.name)
            return _result(fid, "REJECTED", rel_out, None, rec, reason="script error")
        return self._ok(root, fid, rel_out, out, reason="项目生成脚本执行成功")

    def _ok(self, root, fid, rel_out, out, reason):
        sha = _sha(out)
        rec = record(root, fid, "GENERATED", artifact=rel_out,
                     reason=reason, provider=self.name, sha=sha)
        return _result(fid, "GENERATED", rel_out, sha, rec, reason=reason)

    def validate(self, root, spec):
        """几何校验复用 graph_quality_qa.check_graphs（单图，需 figkit layout JSON）。
        mermaid 渲染图无 layout JSON → 几何检查不适用，交 PDF 级 QA（VERIFIED 阶段）判定。"""
        fid = spec.get("figure_id")
        rel_out = spec.get("out") or os.path.join(".aeromech", "artifacts", "figures",
                                                  "final", fid + ".png")
        out = rel_out if os.path.isabs(rel_out) else os.path.join(root, rel_out)
        if not os.path.isfile(out):
            rec = record(root, fid, "REJECTED", artifact=rel_out,
                         reason="validate：artifact 不存在", provider=self.name)
            return _result(fid, "REJECTED", rel_out, None, rec, reason="artifact missing")
        if not linked(research_links(root, fid)) and not linked(spec):
            rec = record(root, fid, "NEEDS_HUMAN_REVIEW", artifact=rel_out,
                         reason="研究链接缺失：图未关联任何 RQ/Analysis/Claim（§四 禁止孤儿图表进文）",
                         provider=self.name)
            return _result(fid, "NEEDS_HUMAN_REVIEW", rel_out, _sha(out), rec,
                           reason="研究链接缺失：图未关联任何 RQ/Analysis/Claim")
        layout = os.path.splitext(out)[0] + ".layout.json"
        if not os.path.isfile(layout):
            layout = os.path.join(root, ".aeromech", "artifacts", "figures",
                                  fid + ".layout.json")
        if not os.path.isfile(layout):
            rec = record(root, fid, "NEEDS_HUMAN_REVIEW", artifact=rel_out,
                         reason="无 figkit layout JSON：机器几何检查不可用，"
                                "由 PDF 级 QA（GQ/FIG 渲染检查）在 VERIFIED 阶段兜底",
                         provider=self.name)
            return _result(fid, "NEEDS_HUMAN_REVIEW", rel_out, _sha(out), rec,
                           reason="no layout metadata")
        import graph_quality_qa as GQ
        figs = GQ.discover_figs(os.path.dirname(layout))
        rep = GQ.Report(tempfile.mkdtemp(prefix="figif_"))
        GQ.check_graphs(rep, figs)
        checks = [{"code": c, "ok": ok, "detail": d} for c, ok, d, sk in rep.items
                  if not sk]
        bad = [c for c in checks if not c["ok"]]
        if bad:
            rec = record(root, fid, "REJECTED", artifact=rel_out,
                         reason="几何检查失败：" + "; ".join(x["code"] for x in bad),
                         provider=self.name)
            return _result(fid, "REJECTED", rel_out, _sha(out), rec,
                           reason="geometry fail", quality=checks)
        rec = record(root, fid, "VALIDATED", artifact=rel_out,
                     reason=f"几何检查 {len(checks)} 项全过", provider=self.name)
        return _result(fid, "VALIDATED", rel_out, _sha(out), rec, reason="ok", quality=checks)


def _result(fid, status, artifact, sha, rec, reason="", quality=None):
    return {"figure_id": fid, "status": status, "artifact": artifact,
            "sha256": sha, "reason": reason, "quality": quality or [],
            "provider": (rec or {}).get("provider"), "timestamp": (rec or {}).get("ts")}


# ---------------- 模块函数（主线调用点） ----------------

def plan_figures(root, provider="local", specs=None):
    prov = get_provider(provider)
    out = prov.plan(root, specs=specs)
    save_plan(root, out, provider=provider)
    for sp in out:
        if current_status(root, sp["figure_id"])[0] is None:
            reason = ("ok" if sp.get("kind") else
                      "无生成源（mmd/script）：等待人工提供或由其他 Provider 生成")
            stt = "PLANNED" if sp.get("kind") else "NEEDS_HUMAN_REVIEW"
            record(root, sp["figure_id"], stt, artifact=sp.get("out"), reason=reason,
                   provider=provider)
    return out


def generate_figure(root, figure_id, provider="local"):
    prov = get_provider(provider)
    specs = load_plan(root)
    if specs is None:
        specs = prov.plan(root)
        save_plan(root, specs, provider=provider)
    for sp in specs:
        if str(sp.get("figure_id")) == figure_id:
            # v1.6.5 Phase 2A fallback 契约（image_provider.route）：
            # 仅当 spec 显式声明 provider 字段才走路由解析——旧 spec（无该字段）
            # 与 v1.6.0 行为逐字节一致（不读任何 env、不触碰 ~/.aeromech）。
            if sp.get("provider") and sp["provider"] != "local":
                import image_provider as IP
                dec = IP.route(sp)
                if dec["needs_configuration"]:
                    rec = record(root, figure_id, "NEEDS_HUMAN_REVIEW",
                                 artifact=sp.get("out"),
                                 reason="NEEDS_CONFIGURATION: " + dec["reason"],
                                 provider=sp["provider"])
                    return _result(figure_id, "NEEDS_HUMAN_REVIEW", sp.get("out"),
                                   None, rec, reason="NEEDS_CONFIGURATION")
                if dec["provider"] == "local":
                    res = get_provider("local").generate(root, sp)
                    if res.get("status") in STATUS_OK and dec.get("fallback_from"):
                        record(root, figure_id, res["status"],
                               artifact=res.get("artifact"),
                               reason="fallback_to_existing_pipeline: "
                                      + str(dec["fallback_from"]),
                               provider="local")
                    return res
                # Phase 2A 无真实 external backend：route 只会返回 local/None，
                # 走到这里属实现缺口 → 明确失败，绝不 fake image。
                rec = record(root, figure_id, "REJECTED",
                             reason="external backend 未实现（Phase 2B），不 fake 生成",
                             provider=sp["provider"])
                return _result(figure_id, "REJECTED", None, None, rec,
                               reason="EXTERNAL_NOT_IMPLEMENTED")
            return prov.generate(root, sp)
    return {"figure_id": figure_id, "status": "REJECTED", "artifact": None,
            "reason": f"计划中无 {figure_id}", "sha256": None, "quality": []}


def validate_figure(root, figure_id, provider="local"):
    prov = get_provider(provider)
    specs = load_plan(root) or []
    sp = next((x for x in specs if str(x.get("figure_id")) == figure_id), None)
    if sp is None:
        rec = record(root, figure_id, "NEEDS_HUMAN_REVIEW",
                     reason="validate：不在计划内（不得校验来历不明的图）", provider=provider)
        return _result(figure_id, "NEEDS_HUMAN_REVIEW", None, None, rec, reason="not planned")
    return prov.validate(root, sp)


def lifecycle_state(root):
    """供 Delivery Gate/聚合器消费：每图最终状态 + 计划存在性。"""
    hist = load_lifecycle(root)
    plan = load_plan(root)
    out = {"figures": {}, "has_plan": plan is not None}
    ids = set(hist) | {str(s.get("figure_id")) for s in (plan or [])}
    for fid in sorted(ids):
        st, rec = current_status(root, fid)
        out["figures"][fid] = {"status": st, "last": rec}
    return out


register_provider(LocalProvider)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Figure Interface（v1.6，契约+适配层）")
    ap.add_argument("root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--provider", default="local"); p.add_argument("--json", action="store_true")
    g = sub.add_parser("generate"); g.add_argument("--figure", required=True); g.add_argument("--provider", default="local")
    ga = sub.add_parser("generate-all"); ga.add_argument("--provider", default="local")
    v = sub.add_parser("validate"); v.add_argument("--figure", required=True); v.add_argument("--provider", default="local")
    s = sub.add_parser("status"); s.add_argument("--json", action="store_true")
    r = sub.add_parser("record"); r.add_argument("--figure", required=True)
    r.add_argument("--status", required=True, choices=LIFECYCLE)
    r.add_argument("--artifact", default=None); r.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    try:
        if a.cmd == "plan":
            specs = plan_figures(root, provider=a.provider)
            print(json.dumps(specs, ensure_ascii=False, indent=1) if a.json
                  else f"计划 {len(specs)} 图（provider={a.provider}）")
            return 0 if specs else 2
        if a.cmd == "generate":
            res = generate_figure(root, a.figure, provider=a.provider)
            print(json.dumps(res, ensure_ascii=False))
            return 0 if res["status"] in STATUS_OK else (2 if res["status"] == "NOT_APPLICABLE" else 1)
        if a.cmd == "generate-all":
            fails = 0
            for sp in load_plan(root) or []:
                res = generate_figure(root, str(sp.get("figure_id")), provider=a.provider)
                print(f"{res['figure_id']}: {res['status']} {res['reason']}")
                fails += 0 if res["status"] in STATUS_OK else 1
            return 1 if fails else 0
        if a.cmd == "validate":
            res = validate_figure(root, a.figure, provider=a.provider)
            print(json.dumps(res, ensure_ascii=False, default=str))
            return 0 if res["status"] in STATUS_OK else 1
        if a.cmd == "status":
            st = lifecycle_state(root)
            print(json.dumps(st, ensure_ascii=False, indent=1) if a.json else st)
            bad = [f for f, x in st["figures"].items()
                   if x["status"] in ("REJECTED", "NEEDS_HUMAN_REVIEW")]
            return 1 if bad else 0
        if a.cmd == "record":
            rec = record(root, a.figure, a.status, artifact=a.artifact, reason=a.reason)
            print(json.dumps(rec, ensure_ascii=False))
            return 0
    except (RuntimeError, KeyError) as e:
        print(f"ERROR: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
