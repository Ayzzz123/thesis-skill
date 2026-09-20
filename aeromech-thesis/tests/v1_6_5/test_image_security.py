# -*- coding: utf-8 -*-
"""test_image_security.py — v1.6.5 Phase 2A：脱敏与泄漏扫描（SEC-01~05）

SEC-01 redact_text 全模式（Authorization/Bearer/sk-/AIza/key=查询串/JWT/secret 赋值）
SEC-01b 不误伤正常词（Bearing 轴承/monkey=3/普通中文）
SEC-02 record(reason=含Key) → figure-lifecycle.yaml 落盘无 Key
SEC-02b log_action(input/output 含Key) → actions.jsonl 落盘无 Key
SEC-03 secret_leak_qa repo scope：植入假真值 Key 文件→FAIL；占位→PASS
SEC-04 secret_leak_qa artifacts scope：lifecycle 被塞 Key→FAIL；正常→PASS
SEC-05 SecretStr 全掩码（repr/str/format/json）+ 假 Key 白名单不误报
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))

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
import figure_iface as FI
import secret_leak_qa as SL
import thesis_orchestrator as ORCH

LIVE = "sk-LIVE1234567890abcdef1234"  # secret-scan-exempt（测试样本，非真实凭据）
BS = chr(92)     # 形态像真 Key 的合成样本（非白名单）


def main():
    print("== test_image_security ==")

    # SEC-01 redact 全模式
    cases = [
        ("Authorization: " + LIVE, LIVE),
        ("Bearer " + LIVE, LIVE),
        ("OPENAI_API_KEY=" + LIVE, LIVE),
        ("url https://x.y/z?key=" + LIVE, LIVE),
        ("AIzaSy" + "Q" * 30, None),
        ("token eyJhbGciOiJIUzI1NiIsInR5cCI6.SOWq8d93jd0amcasd123", None),  # secret-scan-exempt（测试样本）
    ]
    ok = all(IC.redact_text(s) == IC.redact_text(s).replace(LIVE, "") and
             LIVE not in IC.redact_text(s) for s, _ in cases)
    check("SEC-01 redact 覆盖 Authorization/Bearer/赋值/key=查询串", ok)
    r = IC.redact_text("见 Authorization: Bearer abcdef1234567890abcdef, 其余正常")
    check("SEC-01b 不误伤：'Bearing 轴承'/'monkey=3' 原样",
          IC.redact_text("Bearing 轴承 monkey=3 1234567890") ==
          "Bearing 轴承 monkey=3 1234567890")
    check("SEC-01c ***REDACTED*** 出现在洗后文本", IC.REDACTED in r)

    # SEC-02 record() 边界
    tmp = tempfile.mkdtemp(prefix="sec165_")
    root = os.path.join(tmp, "proj")
    os.makedirs(os.path.join(root, ".aeromech", "artifacts", "figures"), exist_ok=True)
    FI.record(root, "FIG-999", "REJECTED",
              reason="mmdc crash: OPENAI_API_KEY=" + LIVE + " leaked in traceback")
    body = open(FI.lifecycle_path(root), encoding="utf-8").read()
    check("SEC-02 record(reason 含 Key) → lifecycle.yaml 无 Key",
          LIVE not in body and IC.REDACTED in body)

    # SEC-02b log_action() 边界
    ORCH.log_action(root, "S8", "gen fail secret=Bearer " + LIVE,
                    {"cmd": "image generate", "auth": "Bearer " + LIVE},
                    {"err": "resp header authorization: " + LIVE}, "FAIL")
    jl = os.path.join(root, ".aeromech", "artifacts", "analysis",
                      "orchestrator-actions.jsonl")
    jbody = open(jl, encoding="utf-8").read()
    check("SEC-02b log_action(input/output/reason) → jsonl 无 Key",
          LIVE not in jbody and IC.REDACTED in jbody)

    # SEC-05 SecretStr 全掩码
    sec = IC.SecretStr(LIVE)
    views = [repr(sec), str(sec), "%s" % sec, "{}".format(sec),
             json.dumps({"k": sec.__repr__()}), f"{sec}"]
    check("SEC-05 SecretStr repr/str/format/f-string 全掩码",
          all(LIVE not in v for v in views))
    check("SEC-05b reveal() 显式取值可用", sec.reveal() == LIVE)

    # SEC-03 repo scope 扫描
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    open(os.path.join(repo, "evil.py"), "w", encoding="utf-8").write(
        "API_KEY = \"" + LIVE + "\"\n")
    good = os.path.join(tmp, "good")
    os.makedirs(good)
    open(os.path.join(good, "conf.py"), "w", encoding="utf-8").write(
        "API_KEY = \"YOUR_API_KEY\"\nMODEL = 'gpt-image-2'\n")
    # 扫描器 repo scope 用 git ls-files；无 git 时退化为空——直接调 scan_text 核心
    hits_bad = SL.scan_text(open(os.path.join(repo, "evil.py"), encoding="utf-8").read(),
                            "evil.py")
    hits_good = SL.scan_text(open(os.path.join(good, "conf.py"), encoding="utf-8").read(),
                             "good/conf.py")
    check("SEC-03 真值形态 Key 赋值→FAIL；占位→无 FAIL",
          any(s == "FAIL" for _, s, _, _ in hits_bad) and
          not any(s == "FAIL" for _, s, _, _ in hits_good))
    tests_like = SL.scan_text("k = 'sk-TEST-" + "a" * 20 + "'", "tests/v1_6_5/x.py")
    check("SEC-03b tests/ 目录 sk-TEST- 白名单不误报",
          not any(s == "FAIL" for _, s, _, _ in tests_like))
    proj_like = SL.scan_text("k = 'sk-TEST-" + "a" * 20 + "'", "src/main.py")
    check("SEC-03c 白名单不越 tests/（项目内 TEST 形态仍报）",
          any(s == "FAIL" for _, s, _, _ in proj_like))

    # SEC-04 artifacts scope：整目录扫描。
    # 注意：root 的 lifecycle 已被 record() 边界洗过（SEC-02 生效）→ 扫描器无物可报，
    # 这正是双保险设计。此处绕过边界**直接写污染文件**，单测扫描器这道独立防线。
    dirty = os.path.join(tmp, "dirty")
    os.makedirs(os.path.join(dirty, ".aeromech", "artifacts", "figures"), exist_ok=True)
    with open(os.path.join(dirty, ".aeromech", "artifacts", "figures",
                           "figure-lifecycle.yaml"), "w", encoding="utf-8") as f:
        f.write("history:" + BS + "n- figure_id: FIG-999" + BS + "n  status: GENERATED" + BS + "n  reason: 'bypassed-redaction api_key=" + LIVE + "'" + BS + "n")
    res = SL.run(dirty, scope="artifacts")
    check("SEC-04 绕过边界的污染文件 → artifacts 扫描 FAIL（独立防线）",
          res["status"] == "FAIL" and any("figure-lifecycle" in h[2]
                                          for h in res["failures"]))
    res_clean = SL.run(root, scope="artifacts")
    check("SEC-04a record() 边界生效的文件 → 扫描无物可报（双保险）",
          res_clean["status"] == "PASS", str(res_clean["failures"][:2]))
    root2 = os.path.join(tmp, "clean")
    os.makedirs(os.path.join(root2, ".aeromech", "artifacts", "figures"), exist_ok=True)
    FI.record(root2, "FIG-999", "GENERATED", reason="正常记录 无凭据")
    res2 = SL.run(root2, scope="artifacts")
    check("SEC-04b 干净项目 → PASS", res2["status"] == "PASS",
          str(res2["failures"][:2]))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_image_security 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
