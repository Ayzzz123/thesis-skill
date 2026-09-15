# -*- coding: utf-8 -*-
"""test_figure_iface.py — Figure Provider 接口与生命周期（指令 §一~四/§十五）

FIGIF-01 provider 注册与抽象契约 / 02 plan / 03 generate / 04 validate /
05 failure(REJECTED，不落占位图) / 06 NHR / 07 研究链接(RQ→AN→CL→FIG) / 08 artifact hash。
使用 mock provider（协作者代码不参与主线单测）。
运行：python tests/v1_6/test_figure_iface.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
import _fixtures as F
import figure_iface as FI
import research_integrity as RI

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


# ---------- mock provider（指令 §二十：主线测试不依赖协作者） ----------

class MockProvider(FI.FigureProvider):
    name = "mock"

    def plan(self, root, specs=None):
        return specs or [{"figure_id": "FIG-001", "name": "mock图", "kind": "mock",
                          "source": None, "out": ".aeromech/artifacts/figures/final/FIG-001.png",
                          "related_rqs": ["RQ-01"], "related_analyses": ["AN-001"],
                          "related_claims": ["CL-001"]}]

    def generate(self, root, spec):
        fid = spec["figure_id"]
        rel = spec["out"]
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if fid == "FIG-BAD":
            rec = FI.record(root, fid, "REJECTED", artifact=rel, reason="mock 生成失败",
                            provider="mock")
            return {"figure_id": fid, "status": "REJECTED", "artifact": rel,
                    "sha256": None, "reason": "mock 生成失败", "quality": [],
                    "provider": "mock", "timestamp": rec["ts"]}
        with open(p, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n mockbytes " + fid.encode())
        sha = FI._sha(p)
        rec = FI.record(root, fid, "GENERATED", artifact=rel, reason="mock ok",
                        provider="mock", sha=sha)
        return {"figure_id": fid, "status": "GENERATED", "artifact": rel,
                "sha256": sha, "reason": "mock ok", "quality": [],
                "provider": "mock", "timestamp": rec["ts"]}

    def validate(self, root, spec):
        fid = spec["figure_id"]
        rel = spec["out"]
        linked_ok = bool(spec.get("related_rqs") or spec.get("related_analyses")
                         or spec.get("related_claims"))
        st = "VALIDATED" if linked_ok else "NEEDS_HUMAN_REVIEW"
        rec = FI.record(root, fid, st, artifact=rel,
                        reason="mock validate", provider="mock")
        return {"figure_id": fid, "status": st, "artifact": rel, "sha256": None,
                "reason": rec["reason"], "quality": [], "provider": "mock",
                "timestamp": rec["ts"]}


FI.register_provider(MockProvider)


def make_root(tmp, name, with_registry=True):
    root = F.make_project(os.path.join(tmp, name), with_template=False)
    if with_registry:
        RI.init_registries(root)
        RI.save_registry(root, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
        RI.save_registry(root, "figures", [
            {"id": "FIG-001", "name": "图1-1 示意图", "related_rqs": ["RQ-01"],
             "related_analyses": ["AN-001"], "related_claims": ["CL-001"]}])
    return root


def main():
    tmp = tempfile.mkdtemp(prefix="figif_v16_")
    print("== test_figure_iface ==")

    # ---------- FIGIF-01 provider 注册 ----------
    check("FIGIF-01 local 默认可用且继承契约", isinstance(FI.get_provider("local"), FI.FigureProvider))
    check("FIGIF-01 mock 注册后按名解析", isinstance(FI.get_provider("mock"), MockProvider))
    try:
        FI.get_provider("collaborator-x")
        check("FIGIF-01 未注册 provider→明确报错（不静默回退）", False)
    except KeyError:
        check("FIGIF-01 未注册 provider→明确报错（不静默回退）", True)
    try:
        FI.FigureProvider().plan(tmp)
        check("FIGIF-01 抽象基类三方法未实现即报错", False)
    except NotImplementedError:
        check("FIGIF-01 抽象基类三方法未实现即报错", True)

    # ---------- FIGIF-02 plan ----------
    root = make_root(tmp, "plan")
    specs = FI.plan_figures(root, provider="mock")
    check("FIGIF-02 plan 产出机读清单", specs and specs[0]["figure_id"] == "FIG-001")
    check("FIGIF-02 计划落盘 figure-plan.yaml（机读格式）",
          os.path.isfile(FI.plan_path(root)))
    st, _ = FI.current_status(root, "FIG-001")
    check("FIGIF-02 新图入 PLANNED 状态", st == "PLANNED", st)
    # local provider 从 v1.4 figures.yaml 推导（无注册表图→空计划但成功）
    root2 = make_root(tmp, "nolist", with_registry=False)
    sp2 = FI.plan_figures(root2, provider="local")
    check("boundary 无注册表→local plan 返回空（不误造计划）", sp2 == [])

    # ---------- FIGIF-03/08 generate + artifact hash ----------
    res = FI.generate_figure(root, "FIG-001", provider="mock")
    check("FIGIF-03 generate→GENERATED", res["status"] == "GENERATED", str(res)[:80])
    check("FIGIF-08 输出含 artifact 路径与 sha256",
          res["artifact"] and len(res["sha256"] or "") == 64)
    hist = FI.load_lifecycle(root)["FIG-001"]
    check("FIGIF-03 生命周期逐步记录（figure_id/ts/artifact/status/reason）",
          len(hist) == 2 and hist[1]["status"] == "GENERATED"
          and all({"figure_id", "ts", "status", "reason"} <= set(h) for h in hist))
    check("FIGIF-08 记录带生成时 sha256（artifact 身份）", hist[1]["sha256"] == res["sha256"])

    # ---------- FIGIF-04 validate ----------
    res = FI.validate_figure(root, "FIG-001", provider="mock")
    check("FIGIF-04 validate（研究链接齐）→VALIDATED", res["status"] == "VALIDATED")
    # EMBEDDED / VERIFIED 由构建链显式记录（主线不自动伪造）
    FI.record(root, "FIG-001", "EMBEDDED", artifact=res["artifact"], reason="进入 DOCX")
    FI.record(root, "FIG-001", "VERIFIED", artifact=res["artifact"], reason="PDF 级 QA 通过")
    st, _ = FI.current_status(root, "FIG-001")
    check("FIGIF-03 生命周期五步贯通 PLANNED→…→VERIFIED",
          [h["status"] for h in FI.load_lifecycle(root)["FIG-001"]] ==
          ["PLANNED", "GENERATED", "VALIDATED", "EMBEDDED", "VERIFIED"], str(st))

    # ---------- FIGIF-05 failure → REJECTED（不落占位图） ----------
    spec_bad = [{"figure_id": "FIG-BAD", "name": "坏图", "kind": "mock", "source": None,
                 "out": ".aeromech/artifacts/figures/final/FIG-BAD.png",
                 "related_rqs": ["RQ-01"], "related_analyses": [], "related_claims": []}]
    FI.plan_figures(root, provider="mock", specs=spec_bad)
    rbad = FI.generate_figure(root, "FIG-BAD", provider="mock")
    check("FIGIF-05 生成失败→REJECTED", rbad["status"] == "REJECTED")
    check("FIGIF-05 失败不落任何产物文件（禁止 placeholder）",
          not os.path.exists(os.path.join(root, spec_bad[0]["out"])))
    check("FIGIF-05 REJECTED 有 reason 与记录",
          FI.current_status(root, "FIG-BAD")[1]["reason"])

    # ---------- FIGIF-06 NHR：无生成源 / 无链接 / 来历不明 ----------
    FI.record(root, "FIG-NOSRC", "PLANNED", reason="x")
    r_nosrc = FI.generate_figure(root, "FIG-NOSRC", provider="mock")
    check("FIGIF-06 计划外图 generate→REJECTED 不静默",
          r_nosrc["status"] == "REJECTED", str(r_nosrc)[:80])
    r_unplanned = FI.validate_figure(root, "FIG-GHOST", provider="mock")
    check("FIGIF-06 校验来历不明图→NEEDS_HUMAN_REVIEW（§四 精神）",
          r_unplanned["status"] == "NEEDS_HUMAN_REVIEW")
    # local provider：mermaid 缺源 → NHR（不伪造输入）
    root3 = make_root(tmp, "mmdmissing")
    RI.save_registry(root3, "figures", [
        {"id": "FIG-009", "name": "图9 缺源", "related_rqs": ["RQ-01"]}])
    FI.plan_figures(root3, provider="local")
    sp9 = [s for s in FI.load_plan(root3) if s["figure_id"] == "FIG-009"][0]
    check("boundary local plan：无 mmd/script 源→kind=None", sp9["kind"] is None)
    r9 = FI.generate_figure(root3, "FIG-009", provider="local")
    check("FIGIF-06 缺源图→NEEDS_HUMAN_REVIEW（人工/协作者 Provider 处理）",
          r9["status"] == "NEEDS_HUMAN_REVIEW")

    # local validate：孤儿图（无 RQ/AN/CL 链接）→ NHR，即便产物在
    root4 = make_root(tmp, "orphan")
    RI.save_registry(root4, "figures", [{"id": "FIG-001", "name": "孤儿图",
                                         "related_rqs": [], "related_analyses": [],
                                         "related_claims": []}])
    specs_orphan = FI.plan_figures(root4, provider="local")
    out4 = [s for s in specs_orphan if s["figure_id"] == "FIG-001"][0]["out"]
    p4 = os.path.join(root4, out4)
    os.makedirs(os.path.dirname(p4), exist_ok=True)
    with open(p4, "wb") as f:
        f.write(b"\x89PNG fake")
    ro = FI.validate_figure(root4, "FIG-001", provider="local")
    check("FIGIF-07 研究链接缺失→validate 不得过（禁止生成一张图但不知服务谁）",
          ro["status"] == "NEEDS_HUMAN_REVIEW" and "研究链接" in ro["reason"],
          ro["status"] + " " + ro["reason"][:80])
    # 链接齐（figures.yaml 注册表来源）→ 进入下一关（无 layout 元数据→NHR 兜底，不装懂）
    RI.save_registry(root4, "figures", [{"id": "FIG-001", "name": "孤儿图",
                                         "related_rqs": ["RQ-01"]}])
    FI.plan_figures(root4, provider="local")
    ro2 = FI.validate_figure(root4, "FIG-001", provider="local")
    check("FIGIF-07 链接齐→通过研究链接关（进入几何/元数据关）",
          ro2["status"] in ("VALIDATED", "NEEDS_HUMAN_REVIEW")
          and "研究链接" not in ro2["reason"], ro2["status"] + " " + ro2["reason"][:60])

    # ---------- 状态汇总（供 Delivery Gate 消费） ----------
    lst = FI.lifecycle_state(root)
    check("status 汇总：has_plan + 每图最终态",
          lst["has_plan"] and lst["figures"]["FIG-001"]["status"] == "VERIFIED"
          and lst["figures"]["FIG-BAD"]["status"] == "REJECTED")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_figure_iface 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
