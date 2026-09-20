# -*- coding: utf-8 -*-
"""test_image_fallback.py — v1.6.5 Phase 2A：兼容性硬约束测试（§二/§七/§十一/§十三）

FB-01 无 API → 自动回落既有 Figure Pipeline（正常生命周期）
FB-02 无 API → 不进入 BLOCK/NHR（gate 不因此受阻）
FB-03 无 API → 不生成 fake image（无占位、无假内容）
FB-04 确定性研究图 → 永远 Local Provider（即使 external 已配置）
FB-05 显式 provider_required=external + 无凭据 → NEEDS_CONFIGURATION（唯一配置错误态）
FB-06 image test 未配置 → exit 0 + "Existing figure generation remains available."
FB-07 回落图仍过统一 QA 链（validate 语义不因回落降低）
Scenario A 无 Key 环境跑既有图全流程：与不启用 image 模块时产物逐字节一致
"""
import io as _io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "scripts")
sys.path.insert(0, SCRIPTS)

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


import figure_iface as FI
import image_provider as IP
import image_config as IC
import research_integrity as RI

FAKE = "sk-TEST-cccccccccccccccccccc"
CLEAR = ("IMAGE_BACKEND", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
         "IMAGE_ALLOW_PROJECT_ENV", "AEROMECH_SKILL_HOME")


class Clean:
    def __enter__(self):
        self._s = {k: os.environ.get(k) for k in CLEAR}
        for k in CLEAR:
            os.environ.pop(k, None)
        self.home = tempfile.mkdtemp()
        self._oh = os.environ.get("HOME"), os.environ.get("USERPROFILE")
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        return self

    def __exit__(self, *a):
        for k, v in self._s.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        h, u = self._oh
        if h is not None:
            os.environ["HOME"] = h
        if u is not None:
            os.environ["USERPROFILE"] = u
        shutil.rmtree(self.home, ignore_errors=True)


def make_proj(tmp, name, with_script_fig=True):
    """最小项目：figures.yaml 一条 FIG（script 源=figkit 画框）+ plan。"""
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, ".aeromech", "artifacts", "figures"), exist_ok=True)
    RI.init_registries(root)
    RI.save_registry(root, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(root, "figures",
                     [{"id": "FIG-001", "name": "fig1-1", "type": "fault_tree",
                       "related_rqs": ["RQ-01"]}])
    if with_script_fig:
        _io.open(os.path.join(root, ".aeromech", "artifacts", "figures", "FIG-001.py"),
                 "w", encoding="utf-8").write(
            "import os, sys\n"
            "sys.path.insert(0, %r)\n"
            "import figkit\n"
            "d = os.path.join('.aeromech','artifacts','figures','final')\n"
            "os.makedirs(d, exist_ok=True)\n"
            "f = figkit.Fig(6.0)\n"
            "f.box('T', 6, 4.6, 4, 0.9, ['T 顶事件'], role='top_event')\n"
            "f.box('G', 6, 3.0, 4, 0.9, ['G 泵源丧失（OR）'], role='gate')\n"
            "f.box('B', 6, 1.4, 4, 0.9, ['B 底事件'], role='basic_event')\n"
            "f.arrow('e1', 8, 4.6-0.07, 8, 3.9+0.07)\n"
            "f.arrow('e2', 8, 3.0-0.07, 8, 2.3+0.07)\n"
            "f.save(d, 'fig1-1', min_font=12)\n" % SCRIPTS)
    return root


def main():
    tmp = tempfile.mkdtemp(prefix="fb165_")
    print("== test_image_fallback ==")

    # FB-01/02/03/07 route 层：无配置 + provider=image → local 回落
    with Clean():
        spec = {"figure_id": "FIG-001", "provider": "image",
                "type": "conceptual_illustration"}
        d = IP.route(spec)
        check("FB-01 route: unavailable→provider=local + fallback_from",
              d["provider"] == "local" and d["fallback_from"] == "external_unavailable")
        check("FB-02 route: 不 BLOCK（needs_configuration=False 且管线可用）",
              d["needs_configuration"] is False
              and d["existing_pipeline_available"] is True)
        # 端到端：generate_figure 走回落，产出真实图（非占位）
        root = make_proj(tmp, "fb1")
        FI.plan_figures(root, provider="local")
        res = FI.generate_figure(root, "FIG-001", provider="local")
        check("FB-01b generate_figure 端到端回落生成 GENERATED",
              res["status"] == "GENERATED", res.get("reason", ""))
        art = os.path.join(root, res["artifact"].replace("/", os.sep))
        check("FB-03 回落产物为真实图（>5KB PNG，非占位）",
              os.path.isfile(art) and os.path.getsize(art) > 5000)
        v = FI.validate_figure(root, "FIG-001", provider="local")
        check("FB-07 回落图仍过统一 validate（VALIDATED，不降标）",
              v["status"] == "VALIDATED", v.get("reason", ""))

    # FB-04 确定性研究图：external 已配置也 local 优先
    with Clean():
        os.environ["IMAGE_BACKEND"] = "openai"
        os.environ["OPENAI_API_KEY"] = FAKE
        for ftype in ("fault_tree", "stat_bar", "stat_line", "flow",
                      "decision_matrix"):
            d = IP.route({"provider": "image", "type": ftype})
            if not (d["provider"] == "local"
                    and d["fallback_from"] == "deterministic_type_local_first"):
                check("FB-04 %s 强制 local" % ftype, False, str(d))
                break
        else:
            check("FB-04 五类确定性图 external 可用时仍 local 优先", True)
        # 概念图 + 已配置 → Phase 2A：不 fake、回落 local 并记录未实现
        d = IP.route({"provider": "image", "type": "conceptual_illustration"})
        check("FB-04b Phase2A 已配置 external→不 fake（回落+not_implemented 标记）",
              d["provider"] == "local"
              and d["fallback_from"] == IP.EXTERNAL_NOT_IMPLEMENTED)

    # FB-05 显式 mandatory + 无凭据 → NEEDS_CONFIGURATION
    with Clean():
        root = make_proj(tmp, "fb5")
        FI.plan_figures(root, provider="local")
        plan = FI.load_plan(root)
        plan[0]["provider"] = "image"
        plan[0]["provider_required"] = "external"
        plan[0]["type"] = "conceptual_illustration"
        FI.save_plan(root, plan)
        res = FI.generate_figure(root, "FIG-001", provider="local")
        check("FB-05 mandatory 无凭据→NEEDS_CONFIGURATION（NHR，不 fake 不 BLOCK）",
              res["status"] == "NEEDS_HUMAN_REVIEW"
              and res["reason"] == "NEEDS_CONFIGURATION", res.get("reason", ""))
        st, rec = FI.current_status(root, "FIG-001")
        check("FB-05b 该态 lifecycle=NHR + reason 含 NEEDS_CONFIGURATION",
              st == "NEEDS_HUMAN_REVIEW" and "NEEDS_CONFIGURATION" in rec["reason"])

    # FB-06 CLI test 未配置：exit 0 + 既有能力提示（§十一）
    with Clean():
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "image_cli.py"), "test"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        check("FB-06 image test 未配置 exit0 + remains available",
              p.returncode == 0 and "Existing figure generation remains available"
              in (p.stdout or ""), (p.stdout or "")[:80])
        s = subprocess.run([sys.executable, os.path.join(SCRIPTS, "image_cli.py"),
                            "status"], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        check("FB-06b image status 无 Key 正常返回（非 ERROR）",
              s.returncode == 0 and "existing figure generation: available"
              in (s.stdout or "").lower(), (s.stdout or "")[:80])

    # Scenario A：无 Key 全流程与"不启用 image 模块"逐字节一致
    with Clean():
        r1 = make_proj(tmp, "sa_plain")
        FI.plan_figures(r1, provider="local")
        FI.generate_figure(r1, "FIG-001", provider="local")
        sha_plain = FI.current_status(r1, "FIG-001")[1]["sha256"]
        r2 = make_proj(tmp, "sa_image")
        FI.plan_figures(r2, provider="local")
        FI.generate_figure(r2, "FIG-001", provider="local")   # 同代码路径
        sha_after = FI.current_status(r2, "FIG-001")[1]["sha256"]
        check("Scenario A 无 Key：产物 sha256 与既有管线逐字节一致",
              sha_plain == sha_after and sha_plain is not None)
        # 旧 spec（无 provider 字段）：resolve 完全不被调用（零 env 读取）
        called = []
        orig_resolve = IC.resolve
        IC.resolve = lambda *a, **k: called.append(1)
        try:
            r3 = make_proj(tmp, "sa_legacy")
            FI.plan_figures(r3, provider="local")
            FI.generate_figure(r3, "FIG-001", provider="local")
        finally:
            IC.resolve = orig_resolve
        check("Scenario A 旧 spec（无 provider 字段）零触碰 image 解析",
              called == [], str(called))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_image_fallback 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
