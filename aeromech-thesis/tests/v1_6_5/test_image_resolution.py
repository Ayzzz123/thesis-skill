# -*- coding: utf-8 -*-
"""test_image_resolution.py — v1.6.5 Phase 2A：provider-specific 解析 + 用户隔离

RES-01 provider-specific resolution（不同 backend 各读各前缀）
RES-02 model（建议默认 / 用户覆盖）
RES-03 base_url
RES-04 User A / User B 完全隔离（§十三 Scenario C）
RES-05 进程 env 每键独立最高优先（设计允许的级联，02 文档）
RES-06 host_native 后端无需 Key 即 AVAILABLE（零 Key 路径预留，不虚构行为）
"""
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

KEY_A = "sk-TEST-aaaaaaaaaaaaaaaaaaaa"
KEY_B = "sk-TEST-bbbbbbbbbbbbbbbbbbbb"
CLEAR = ("IMAGE_BACKEND", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
         "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_BASE_URL",
         "IMAGE_ALLOW_PROJECT_ENV", "AEROMECH_SKILL_HOME")


class Clean:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in CLEAR + ("HOME", "USERPROFILE")}
        for k in CLEAR:
            os.environ.pop(k, None)
        # 隔离用户级 ~/.aeromech/.env：真实机器上用户可能已配置（本测试必须与
        # 环境无关地验证"无配置时"行为——与 test_image_external.Env 同口径）
        self._home = tempfile.mkdtemp(prefix="clean165_")
        os.environ["HOME"] = os.environ["USERPROFILE"] = self._home
        os.environ["AEROMECH_SKILL_HOME"] = self._home
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self._home, ignore_errors=True)


def make_home(backend_lines):
    home = tempfile.mkdtemp(prefix="iso_")
    d = os.path.join(home, ".aeromech")
    os.makedirs(d)
    with open(os.path.join(d, ".env"), "w", encoding="utf-8") as f:
        f.write(backend_lines)
    return home


def main():
    print("== test_image_resolution ==")

    # RES-01 不同 backend 各读各前缀
    with Clean():
        os.environ["IMAGE_BACKEND"] = "openai"
        os.environ["OPENAI_API_KEY"] = KEY_A
        os.environ["GEMINI_API_KEY"] = KEY_B
        r = IC.resolve()
        check("RES-01a backend=openai 只读 OPENAI_*",
              r.available and r.credential.reveal() == KEY_A)
        os.environ["IMAGE_BACKEND"] = "gemini"
        r = IC.resolve()
        check("RES-01b backend=gemini 只读 GEMINI_*",
              r.available and r.credential.reveal() == KEY_B)

    # RES-02 model：建议默认 + 用户覆盖
    with Clean():
        os.environ["IMAGE_BACKEND"] = "openai"
        os.environ["OPENAI_API_KEY"] = KEY_A
        r = IC.resolve()
        check("RES-02a 未设 MODEL→建议默认（非敏感，可文档推荐）",
              r.model == IC.SUGGESTED_MODEL["openai"])
        os.environ["OPENAI_MODEL"] = "my-image-1"
        check("RES-02b 用户覆盖生效", IC.resolve().model == "my-image-1")

    # RES-03 base_url 无建议默认（除官方常量外不猜）
    with Clean():
        os.environ["IMAGE_BACKEND"] = "openai"
        os.environ["OPENAI_API_KEY"] = KEY_A
        check("RES-03a base_url 缺省 None", IC.resolve().base_url is None)
        os.environ["OPENAI_BASE_URL"] = "https://proxy.example/v1"
        check("RES-03b base_url 可配置（代理/私有端点）",
              IC.resolve().base_url == "https://proxy.example/v1")

    # RES-04 Scenario C：用户 A / 用户 B 完全隔离
    homeA = make_home("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\n" % KEY_A)
    homeB = make_home("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\n" % KEY_B)
    try:
        with Clean():
            os.environ["HOME"] = os.environ["USERPROFILE"] = homeA
            rA = IC.resolve()
            check("RES-04a User A 读到 KEY_A",
                  rA.available and rA.credential.reveal() == KEY_A)
            check("RES-04b A 环境视图无 KEY_B 痕迹",
                  KEY_B not in repr(rA.to_public()))
            os.environ["HOME"] = os.environ["USERPROFILE"] = homeB
            rB = IC.resolve()
            check("RES-04c User B 读到 KEY_B（且非 A）",
                  rB.available and rB.credential.reveal() == KEY_B)
            check("RES-04d 两把 Key 指纹不同（各读各的）",
                  rA.credential.fingerprint() != rB.credential.fingerprint())
    finally:
        shutil.rmtree(homeA, ignore_errors=True)
        shutil.rmtree(homeB, ignore_errors=True)

    # RES-05 进程 env 每键独立最高优先（文件给假值、进程给真值→进程赢）
    home = make_home("IMAGE_BACKEND=openai\nOPENAI_API_KEY=sk-TEST-fromfile0000000000\n")
    try:
        with Clean():
            os.environ["HOME"] = os.environ["USERPROFILE"] = home
            os.environ["OPENAI_API_KEY"] = KEY_A
            r = IC.resolve()
            check("RES-05 进程 env 覆盖文件同名键",
                  r.available and r.credential.reveal() == KEY_A
                  and r.source == "process")
    finally:
        shutil.rmtree(home, ignore_errors=True)

    # RES-06 host_native 零 Key
    with Clean():
        os.environ["IMAGE_BACKEND"] = "host_native"
        r = IC.resolve()
        check("RES-06 host_native 无需 Key→AVAILABLE",
              r.available and r.credential is None)

    print(f"test_image_resolution 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
