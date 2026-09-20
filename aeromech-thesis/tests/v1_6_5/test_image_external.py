# -*- coding: utf-8 -*-
"""test_image_external.py — v1.6.5 最终阶段：真实 External Provider + 受控闸（IMG-01~14）

零真实网络：backend._http 全部注入 mock（§十：普通 regression 不自动调真实 API）。
覆盖任务 §十四 14 项：
  IMG-01 配置 API→provider 解析；IMG-02 请求构造（URL/头/体）；IMG-03 响应解析；
  IMG-04 401→INVALID_CREDENTIAL（不伪装普通失败）；IMG-05/06 无 Key→既有管线不 BLOCK；
  IMG-07 无 Figure Plan→ZERO HTTP；IMG-08 确定性图禁 external；IMG-09 概念图→external；
  IMG-10 provenance 完整且无凭据；IMG-11 AI 图≠研究证据；IMG-12 secret 不进日志；
  IMG-13 secret_leak_qa FAIL=0；IMG-14 attempts≤3 不无限重试。
"""
import base64
import contextlib
import io as _io
import json
import os
import shutil
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


import image_config as IC
import image_provider as IP
import image_backends as IB
import ai_figure_gate as G
import figure_iface as FI
import research_integrity as RI
import secret_leak_qa as SL

FAKE_KEY = "sk-TEST-9dF2aB7cE1hK4mP6qS8uW0xY2zA5cD7e"
PNG_MIN = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 3000).decode()


class Env:
    KEYS = ("IMAGE_BACKEND", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
            "IMAGE_ALLOW_PROJECT_ENV", "AEROMECH_SKILL_HOME", "IMAGE_MAX_ATTEMPTS")

    def __enter__(self):
        self.home = tempfile.mkdtemp()
        self._s = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        os.environ["AEROMECH_SKILL_HOME"] = self.home          # 无 skill .env
        return self

    def __exit__(self, *a):
        for k, v in self._s.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)


def configured_openai():
    os.environ["IMAGE_BACKEND"] = "openai"
    os.environ["OPENAI_API_KEY"] = FAKE_KEY
    os.environ["OPENAI_BASE_URL"] = "https://api.test.local/v1"


def mock_transport(canned):
    """canned: callable(method,url,headers,body)->(status, dict) 或 (status, dict) 常量"""
    calls = []

    def _http(method, url, headers, body, timeout):
        calls.append({"method": method, "url": url, "headers": headers,
                      "body": json.loads(body.decode("utf-8"))})
        if callable(canned):
            return canned(method, url, headers, body)
        return canned
    return _http, calls


def good_image():
    return 200, {"data": [{"b64_json": PNG_MIN}]}


def full_plan(fid="FIG-007"):
    return {"figure_id": fid, "figure_type": "conceptual_illustration",
            "purpose": "解释液压动力供应功能分层", "intended_section": "2.1",
            "semantic_content": "四层结构+能量流向",
            "source_material": ["E-008"], "research_link": {"related_rqs": ["RQ-01"]},
            "required_visual_elements": ["泵源层", "蓄压层", "传输层", "用压层"],
            "forbidden_elements": ["具体机型型号", "任何数值"],
            "provider": "image"}


def make_proj(tmp, name, plan_specs):
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, ".aeromech", "artifacts", "figures"), exist_ok=True)
    RI.init_registries(root)
    RI.save_registry(root, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    FI.save_plan(root, plan_specs)
    return root


def main():
    tmp = tempfile.mkdtemp(prefix="ext165_")
    print("== test_image_external ==")

    # IMG-01 配置 API → provider 正确解析
    with Env():
        configured_openai()
        r = IC.resolve()
        check("IMG-01 配置解析 AVAILABLE/openai",
              r.available and r.backend == "openai" and r.base_url.endswith("/v1"))

        # IMG-02 请求构造正确（URL/Authorization/模型/提示词/尺寸/格式）
        b = IB.get_backend("openai", r.credential, model="gpt-image-2",
                           base_url="https://api.test.local/v1")
        b._http, calls = mock_transport(good_image())
        b.generate("test prompt", size="1024x1024")
        c = calls[0]
        check("IMG-02a POST /images/generations 端点+URL",
              c["method"] == "POST" and c["url"] ==
              "https://api.test.local/v1/images/generations")
        check("IMG-02b Authorization Bearer 头 + JSON 体字段（gpt-image 系不发 response_format）",
              c["headers"]["Authorization"] == "Bearer " + FAKE_KEY and
              c["body"]["model"] == "gpt-image-2" and
              "response_format" not in c["body"] and c["body"]["n"] == 1)

        # IMG-03 响应解析：b64 → PNG bytes；过小/缺 data → GENERATION_FAILED
        blob = b.generate("p2")
        check("IMG-03a 正常响应解码为图片字节", len(blob) > 3000 and blob[:4] == b"\x89PNG")
        b._http, _ = mock_transport((200, {"data": []}))
        check("IMG-03b 空 data→GENERATION_FAILED",
              _raises_code(b.generate, "GENERATION_FAILED", "p3"))
        b._http, _ = mock_transport((200, {"data": [{"b64_json": "QUJD"}]}))
        check("IMG-03c 过小响应→GENERATION_FAILED（不静默半图）",
              _raises_code(b.generate, "GENERATION_FAILED", "p4"))

        # IMG-04 401 → INVALID_CREDENTIAL（不伪装普通失败；retryable=False）
        for status, code in ((401, "INVALID_CREDENTIAL"), (403, "INVALID_CREDENTIAL"),
                             (429, "RATE_LIMIT"), (404, "MODEL_UNAVAILABLE"),
                             (500, "PROVIDER_ERROR"), (451, "CONTENT_POLICY_ERROR")):
            b._http, _ = mock_transport((status, {"error": {"message": "denied x"}}))
            ok = _raises_code(b.generate, code, "p")
            if not ok:
                check(f"IMG-04 HTTP {status}→{code}", False)
                break
        else:
            check("IMG-04 六状态码精确分类（401 不塌缩）", True)
            b._http, _ = mock_transport((401, {"error": {"message": "bad"}}))
            try:
                b.generate("p")
            except IB.ImageError as e:
                check("IMG-04b INVALID_CREDENTIAL 不可自动重试", e.retryable is False)

    # IMG-07 无 Figure Plan → ZERO HTTP（端到端）
    with Env():
        configured_openai()
        root = make_proj(tmp, "noplan", [dict(full_plan(), purpose=None)])  # 缺字段
        hits = []
        orig = IB.OpenAICompatBackend._post_json
        IB.OpenAICompatBackend._post_json = lambda *a, **k: hits.append(1)
        try:
            res = FI.generate_figure(root, "FIG-007", provider="local")
        finally:
            IB.OpenAICompatBackend._post_json = orig
        check("IMG-07a 无完整 Plan→NEEDS_HUMAN_REVIEW(FIGURE_PLAN_REQUIRED)",
              res["status"] == "NEEDS_HUMAN_REVIEW" and
              res["reason"] == "FIGURE_PLAN_REQUIRED", res.get("reason", ""))
        check("IMG-07b ZERO HTTP 调用", hits == [])
        st, rec = FI.current_status(root, "FIG-007")
        check("IMG-07c lifecycle 记录含缺字段清单+零 HTTP 声明",
              "FIGURE_PLAN_REQUIRED" in rec["reason"] and "purpose" in rec["reason"]
              and "零 HTTP" in rec["reason"], rec["reason"][:80])

    # IMG-08 确定性研究图 → 禁 external（端到端零 HTTP）
    with Env():
        configured_openai()
        spec = full_plan("FIG-008")
        spec["figure_type"] = spec["type"] = "fault_tree"
        root = make_proj(tmp, "det", [spec])
        hits = []
        orig = IB.OpenAICompatBackend._post_json
        IB.OpenAICompatBackend._post_json = lambda *a, **k: hits.append(1)
        try:
            res = FI.generate_figure(root, "FIG-008", provider="local")
        finally:
            IB.OpenAICompatBackend._post_json = orig
        check("IMG-08 fault_tree 配 provider=image→零 HTTP + 既有管线处理",
              hits == [] and res["status"] in ("NEEDS_HUMAN_REVIEW", "GENERATED"),
              str(res)[:80])
        # route 层直接断言 local-first
        d = IP.route({"provider": "image", "type": "fault_tree"})
        check("IMG-08b route: fault_tree→local（DETERMINISTIC 保护）",
              d["provider"] == "local" and
              d["fallback_from"] == "deterministic_type_local_first")

    # IMG-09/10/12 概念图端到端 external 生成（mock）+ provenance + 无凭据落盘
    with Env():
        configured_openai()
        root = make_proj(tmp, "ok", [full_plan()])
        b_orig = IB.get_backend
        injected = {}

        def patched(name, cred, model=None, base_url=None):
            bk = b_orig(name, cred, model=model, base_url=base_url)
            bk._http, calls = mock_transport(good_image())
            injected["calls"] = calls
            return bk
        IB.get_backend = patched
        try:
            res = FI.generate_figure(root, "FIG-007", provider="local")
        finally:
            IB.get_backend = b_orig
        check("IMG-09a 概念图+已配置→external 生成 GENERATED",
              res["status"] == "GENERATED", str(res)[:100])
        check("IMG-09b 真实一次 HTTP（mock）且 prompt 结构化",
              len(injected.get("calls", [])) == 1 and
              "MUST_SHOW" in injected["calls"][0]["body"]["prompt"] and
              "MUST_NOT_SHOW" in injected["calls"][0]["body"]["prompt"] and
              "SOURCE" in injected["calls"][0]["body"]["prompt"])
        st, rec = FI.current_status(root, "FIG-007")
        prov = rec.get("provider_meta") or {}
        need = ("figure_id", "generation_method", "provider", "model", "timestamp",
                "prompt_hash", "artifact_hash", "source_material_refs", "purpose",
                "figure_type")
        check("IMG-10a provenance 十字段完整",
              all(k in prov for k in need) and
              prov["generation_method"] == "ai_image_model" and
              prov["artifact_hash"] == res["sha256"])
        body = open(FI.lifecycle_path(root), encoding="utf-8").read()
        check("IMG-10b/IMG-12 lifecycle 落盘无 Key/Authorization",
              FAKE_KEY not in body and "Bearer" not in body and "api_key" not in body.lower())
        check("IMG-12 prompt_hash 可复算（确定性组装）",
              prov["prompt_hash"].startswith("sha256:") and
              prov["prompt_hash"] == G.assemble_prompt(G.normalize_plan(full_plan()))[1])

    # IMG-05/06 无 Key 端到端：概念图也走既有管线，不 BLOCK 不 fake
    with Env():
        root = make_proj(tmp, "nokey", [full_plan("FIG-009")])
        # 概念图无本地源 → 既有管线诚实 NHR（v1.6.0 原行为），不是 BLOCK/不是 fake
        res = FI.generate_figure(root, "FIG-009", provider="local")
        check("IMG-05 无 Key→route 回落既有管线（不 fake 生成）",
              res["status"] in ("NEEDS_HUMAN_REVIEW", "GENERATED"), str(res)[:80])
        st, rec = FI.current_status(root, "FIG-009")
        check("IMG-06 无 Key 不 BLOCK：决策为 NHR/生成而非 REJECTED",
              st != "REJECTED", str(st))
        # 带本地 script 源的确定性图：无 Key 完全正常生成（v1.6.0 行为）
        root2 = make_proj(tmp, "nokey2", [dict(full_plan("FIG-010"),
                                               figure_type="flow", type="flow",
                                               provider="image", kind="script",
                                               source=".aeromech/artifacts/figures/FIG-010.py",
                                               out=".aeromech/artifacts/figures/final/fig10.png")])
        _io.open(os.path.join(root2, ".aeromech", "artifacts", "figures",
                              "FIG-010.py"), "w", encoding="utf-8").write(
            "import os, sys\n"
            "sys.path.insert(0, %r)\n"
            "import figkit\n"
            "d = os.path.join('.aeromech','artifacts','figures','final')\n"
            "os.makedirs(d, exist_ok=True)\n"
            "f = figkit.Fig(6.0)\n"
            "f.box('A', 6, 4.6, 4, 0.9, ['A'], role='main_flow')\n"
            "f.box('B', 6, 3.0, 4, 0.9, ['B'], role='stage')\n"
            "f.box('C', 6, 1.4, 4, 0.9, ['C'], role='stage')\n"
            "f.arrow('e1', 8, 4.6-0.07, 8, 3.9+0.07)\n"
            "f.arrow('e2', 8, 3.0-0.07, 8, 2.3+0.07)\n"
            "f.save(d, 'fig10', min_font=12)\n" % SCRIPTS)
        res2 = FI.generate_figure(root2, "FIG-010", provider="local")
        check("IMG-05b 无 Key + 本地源：既有管线正常 GENERATED",
              res2["status"] == "GENERATED", str(res2)[:80])

    # IMG-11 AI 图 ≠ 研究证据（注册表守卫）
    ev = [{"id": "E-100", "source": "AI 概念图", "source_type": "ai_generated_visual",
           "verification_status": "verified", "claim_supported": []}]
    root3 = make_proj(tmp, "evi", [])
    RI.save_registry(root3, "evidence", ev)
    v = RI.validate(root3)
    dis = [p for p in v["problems"] if p["code"] == "RI-E-DISGUISE"]
    check("IMG-11a ai_generated_visual 标 verified→critical（禁成证据）",
          len(dis) == 1 and dis[0]["severity"] == "critical", str(dis))
    ev[0]["verification_status"] = "pending"
    RI.save_registry(root3, "evidence", ev)
    v2 = RI.validate(root3)
    check("IMG-11b 合法状态（pending/simulated）不误伤",
          not any(p["code"] == "RI-E-DISGUISE" for p in v2["problems"]))

    # IMG-14 成本闸：attempts≤3，第 4 次自动回落 local（零新 HTTP）
    with Env():
        configured_openai()
        os.environ["IMAGE_MAX_ATTEMPTS"] = "3"
        root4 = make_proj(tmp, "cost", [full_plan("FIG-011")])
        # 预置 3 次已用记录
        for i in (1, 2, 3):
            FI.record(root4, "FIG-011", "REJECTED", provider="external_image",
                      reason=f"external NETWORK_ERROR（第 {i} 次）",
                      provider_meta={"generation_method": "ai_image_model",
                                     "attempts": i})
        hits = []
        orig = IB.OpenAICompatBackend._post_json
        IB.OpenAICompatBackend._post_json = lambda *a, **k: hits.append(1)
        try:
            res = FI.generate_figure(root4, "FIG-011", provider="local")
        finally:
            IB.OpenAICompatBackend._post_json = orig
        st, rec = FI.current_status(root4, "FIG-011")
        check("IMG-14 第 4 次请求→零 HTTP + 成本闸回落记录",
              hits == [] and "成本闸" in rec["reason"], rec["reason"][:60])

    # IMG-GPT gpt-image 参数兼容（真实中转站 PROVIDER_ERROR 根因修复；全部离线 mock）
    with Env():
        configured_openai()
        r = IC.resolve()
        # IMG-GPT-01 gpt-image 系请求不含 response_format（恒返 b64；参数被 400 拒绝）
        b = IB.get_backend("openai", r.credential, model="gpt-image-2",
                           base_url="https://api.test.local/v1")
        b._http, calls = mock_transport(good_image())
        b.generate("p", size="1024x1024")
        check("IMG-GPT-01 gpt-image-2 请求不含 response_format",
              "response_format" not in calls[0]["body"], str(calls[0]["body"])[:90])
        # IMG-GPT-02 gpt-image 系 smoke 尺寸=1024x1024
        b2 = IB.get_backend("openai", r.credential, model="gpt-image-2",
                            base_url="https://api.test.local/v1")
        b2._http, calls2 = mock_transport(good_image())
        b2.check()
        check("IMG-GPT-02 gpt-image smoke size=1024x1024（256x256 会被 400 拒绝）",
              calls2[0]["body"]["size"] == "1024x1024")
        # IMG-GPT-03 非 gpt-image 模型族保留原兼容行为
        b3 = IB.get_backend("openai", r.credential, model="dall-e-3",
                            base_url="https://api.test.local/v1")
        b3._http, calls3 = mock_transport(good_image())
        b3.generate("p")
        b3._http, calls4 = mock_transport(good_image())
        b3.check()
        check("IMG-GPT-03a 非 gpt-image 仍发送 response_format=b64_json",
              calls3[0]["body"].get("response_format") == "b64_json")
        check("IMG-GPT-03b 非 gpt-image smoke 保留 SMOKE_SIZE",
              calls4[0]["body"]["size"] == IB.SMOKE_SIZE)
        # IMG-GPT-04 CLI 失败输出：显示 redact 后 provider message，无 Key 泄漏
        import image_cli as ICM
        be = IB.get_backend("openai", r.credential, model="gpt-image-2",
                            base_url="https://api.test.local/v1")
        be._http, _ = mock_transport((400, {"error": {
            "message": "Unknown parameter; credential=" + FAKE_KEY,
            "code": "unknown_parameter"}}))

        class _R:
            state = IC.STATE_AVAILABLE
            backend = "openai"
            model = "gpt-image-2"
            base_url = "https://api.test.local/v1"
            credential = r.credential

            def to_public(self):
                return {"backend": "openai", "model": "gpt-image-2",
                        "credential": "configured", "source": "test",
                        "reason": "", "malformed_lines": 0}

        o_resolve, o_get, o_smoke = ICM.IC.resolve, IB.get_backend, ICM._smoke_dir
        ICM.IC.resolve = lambda required=True: _R()
        IB.get_backend = lambda *a, **k: be
        ICM._smoke_dir = lambda: os.path.join(tmp, "smokehome")
        buf = _io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = ICM._cmd_test(type("A", (), {"no_network": False})())
        finally:
            ICM.IC.resolve, IB.get_backend, ICM._smoke_dir = o_resolve, o_get, o_smoke
        out = buf.getvalue()
        check("IMG-GPT-04a CLI 失败显示 PROVIDER_ERROR + redact 后 message",
              rc == 1 and "PROVIDER_ERROR" in out and "Message:" in out
              and "Unknown parameter" in out, out[:130])
        check("IMG-GPT-04b 输出无 Key/Authorization 泄漏",
              FAKE_KEY not in out and "Bearer " + FAKE_KEY not in out
              and "credential=sk-" not in out.replace("credential=" + IC.REDACTED, ""))

        # IMG-GPT-05~09 响应解析器完整性（OpenAI-compatible 两种成功形态 + 三种失败形态；
        # 全部离线 mock，零真实网络）
        PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 3000
        # CASE A: data[0].b64_json → 正常出图（既有行为回归，不改）
        ba = IB.get_backend("openai", r.credential, model="gpt-image-2",
                            base_url="https://api.test.local/v1")
        ba._http, ca = mock_transport((200, {"data": [{"b64_json": PNG_MIN}]}))
        art_a = os.path.join(tmp, "caseA.png")
        blob_a = ba.generate("p", out_path=art_a)
        check("IMG-GPT-05 CASE A b64_json → 图片字节+artifact 落盘",
              blob_a[:4] == b"\x89PNG" and os.path.isfile(art_a))
        # CASE B: data[0].url → parser 识别 url 并经注入 fetcher 取回（不真实下载）
        bb = IB.get_backend("openai", r.credential, model="gpt-image-2",
                            base_url="https://api.test.local/v1")
        bb._http, cb = mock_transport((200, {"data": [
            {"url": "https://example.test/image.png"}]}))
        o_fetch, fetched = IB._fetch_url_bytes, []

        def _fake_fetch(u, t):
            fetched.append(str(u))
            return 200, PNG_BYTES
        IB._fetch_url_bytes = _fake_fetch
        try:
            blob_b = bb.generate("p")
        finally:
            IB._fetch_url_bytes = o_fetch
        check("IMG-GPT-06 CASE B url 形态 → 识别并取回字节（GET 产物，非新生成）",
              blob_b == PNG_BYTES and fetched == ["https://example.test/image.png"])
        # url 下载请求不得携带 Authorization（URL host 可能是第三方 CDN）
        captured = {}

        def _cap_urlopen(req, timeout=None):
            captured["hdrs"] = {k.lower() for k, _v in req.header_items()}

            class _R2:
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return PNG_BYTES
            return _R2()
        o_uo2 = IB.urllib.request.urlopen
        IB.urllib.request.urlopen = _cap_urlopen
        try:
            st2, blob2 = IB._fetch_url_bytes("https://example.test/x.png", 5)
        finally:
            IB.urllib.request.urlopen = o_uo2
        check("IMG-GPT-06b url 下载不带 Authorization（不向 CDN 泄露凭据）",
              st2 == 200 and blob2 == PNG_BYTES
              and "authorization" not in captured.get("hdrs", {"authorization"}))
        # CASE C: data=[] → GENERATION_FAILED（绝不 PASS）
        bc = IB.get_backend("openai", r.credential, model="gpt-image-2",
                            base_url="https://api.test.local/v1")
        bc._http, _ = mock_transport((200, {"data": []}))
        check("IMG-GPT-07 CASE C data=[] → GENERATION_FAILED",
              _raises_code(bc.generate, "GENERATION_FAILED", "p"))
        # CASE D: data=[{}] → GENERATION_FAILED（指明缺 b64_json/url）
        bd = IB.get_backend("openai", r.credential, model="gpt-image-2",
                            base_url="https://api.test.local/v1")
        bd._http, _ = mock_transport((200, {"data": [{}]}))
        try:
            bd.generate("p")
            okd = False
        except IB.ImageError as e:
            okd = (e.code == "GENERATION_FAILED"
                   and "neither b64_json nor url" in e.message)
        check("IMG-GPT-08 CASE D data=[{}] → GENERATION_FAILED + 缺失字段说明", okd)
        # CASE E: HTTP 200 + 非 JSON → PROVIDER_ERROR（归类失败，绝不 PASS）
        be2 = IB.get_backend("openai", r.credential, model="gpt-image-2",
                             base_url="https://api.test.local/v1")

        class _FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"<html>gateway error page</html>"
        o_uo = IB.urllib.request.urlopen
        IB.urllib.request.urlopen = lambda req, timeout=None: _FakeResp()
        try:
            be2._http = IB._transport_http     # 真实 transport（urlopen 已离线劫持）
            oke = _raises_code(be2.generate, "PROVIDER_ERROR", "p")
        finally:
            IB.urllib.request.urlopen = o_uo
        check("IMG-GPT-09 CASE E 200+非JSON → PROVIDER_ERROR（归类失败）", oke)

    # IMG-13 secret_leak_qa：本阶段全部新文件+项目 artifacts FAIL=0
    hits_repo = []
    for fn in ("image_backends.py", "ai_figure_gate.py", "image_provider.py",
               "image_config.py", "figure_iface.py", "image_cli.py"):
        p = os.path.join(SCRIPTS, fn)
        hits_repo += SL.scan_text(open(p, encoding="utf-8").read(), "scripts/" + fn)
    check("IMG-13a 新代码零 FAIL（FAKE_KEY 为测试合成值不在 scripts）",
          not any(s == "FAIL" for _, s, _, _ in hits_repo),
          str([h for h in hits_repo if h[1] == "FAIL"][:2]))
    res5 = SL.run(os.path.join(tmp, "ok"), scope="artifacts")
    check("IMG-13b external 生成项目 artifacts 扫描 PASS",
          res5["status"] == "PASS", str(res5["failures"][:2]))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_image_external 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


def _raises_code(fn, code, *a, **k):
    try:
        fn(*a, **k)
        return False
    except IB.ImageError as e:
        return e.code == code
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
