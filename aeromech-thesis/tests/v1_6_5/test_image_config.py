# -*- coding: utf-8 -*-
"""test_image_config.py — v1.6.5 Phase 2A：凭据配置/解析测试（CFG-01~10）

假 Key 约定：sk-TEST-<hex>（仅测试内存/tempfile，测后即删）。
HOME 隔离：每用例 tempfile 造 HOME + patch USERPROFILE/HOME，绝不触碰真实 ~/.aeromech。
"""
import os
import sys
import tempfile
import shutil

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

FAKE = "sk-TEST-" + "a1b2c3d4e5f6a7b8c9d0"


class Env:
    """干净环境：tempfile HOME + 剥离全部相关进程 env。"""
    KEYS = ("IMAGE_BACKEND", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
            "GEMINI_API_KEY", "GEMINI_MODEL", "IMAGE_ALLOW_PROJECT_ENV",
            "AEROMECH_SKILL_HOME")

    def __enter__(self):
        self.home = tempfile.mkdtemp(prefix="imghome_")
        self.skill = tempfile.mkdtemp(prefix="imgskill_")
        self.cwd = tempfile.mkdtemp(prefix="imgcwd_")
        self._saved = {}
        for k in self.KEYS:
            self._saved[k] = os.environ.get(k)
            os.environ.pop(k, None)
        os.environ["HOME"] = self.home
        os.environ["USERPROFILE"] = self.home
        os.environ["AEROMECH_SKILL_HOME"] = self.skill
        self._oldcwd = os.getcwd()
        os.chdir(self.cwd)
        return self

    def __exit__(self, *a):
        os.chdir(self._oldcwd)
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for d in (self.home, self.skill, self.cwd):
            shutil.rmtree(d, ignore_errors=True)

    def user_env(self, text):
        p = os.path.join(self.home, ".aeromech")
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, ".env"), "w", encoding="utf-8") as f:
            f.write(text)

    def skill_env(self, text):
        with open(os.path.join(self.skill, ".env"), "w", encoding="utf-8") as f:
            f.write(text)

    def project_env(self, text):
        with open(os.path.join(self.cwd, ".env"), "w", encoding="utf-8") as f:
            f.write(text)


def main():
    print("== test_image_config ==")

    # CFG-01 无配置 = UNAVAILABLE（正常态，不抛错、不 needs_configuration）
    with Env():
        r = IC.resolve()
        check("CFG-01 无配置→UNAVAILABLE 正常态（非异常）",
              r.state == IC.STATE_UNAVAILABLE and not r.needs_configuration)
        r2 = IC.resolve(required=True)
        check("CFG-01b required=True→needs_configuration（唯一配置错误入口）",
              r2.state == IC.STATE_UNAVAILABLE and r2.needs_configuration)

    # CFG-02 进程 env 配置成功
    with Env():
        os.environ["IMAGE_BACKEND"] = "openai"
        os.environ["OPENAI_API_KEY"] = FAKE
        r = IC.resolve()
        check("CFG-02 process env→AVAILABLE source=process",
              r.available and r.source == "process" and r.credential.reveal() == FAKE)

    # CFG-03 用户级 ~/.aeromech/.env
    with Env() as e:
        e.user_env("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\nOPENAI_MODEL=gpt-image-x\n" % FAKE)
        r = IC.resolve()
        check("CFG-03 user .env→AVAILABLE source=user",
              r.available and r.source == "user" and r.model == "gpt-image-x")

    # CFG-04 项目级 .env 默认关闭；IMAGE_ALLOW_PROJECT_ENV=1 才开
    with Env() as e:
        e.project_env("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\n" % FAKE)
        r = IC.resolve()
        check("CFG-04a 项目 .env 默认禁用（UNAVAILABLE）", r.state == IC.STATE_UNAVAILABLE)
        os.environ["IMAGE_ALLOW_PROJECT_ENV"] = "1"
        r = IC.resolve()
        check("CFG-04b IMAGE_ALLOW_PROJECT_ENV=1 才读取", r.available and r.source == "project")

    # CFG-05 skill 目录优先于 user（搜索序）
    with Env() as e:
        e.skill_env("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\n" % FAKE)
        e.user_env("IMAGE_BACKEND=gemini\nGEMINI_API_KEY=%s\n" % FAKE)
        r = IC.resolve()
        check("CFG-05 skill .env 先命中（backend=openai 非 gemini）",
              r.available and r.backend == "openai" and r.source == "skill")

    # CFG-06 首命中不合并：skill 有 BACKEND 无 KEY、user 有 KEY → UNAVAILABLE
    with Env() as e:
        e.skill_env("IMAGE_BACKEND=openai\n")
        e.user_env("OPENAI_API_KEY=%s\n" % FAKE)
        r = IC.resolve()
        check("CFG-06 不跨 .env 拼 secret（首命中即停）",
              r.state == IC.STATE_UNAVAILABLE)

    # CFG-07 语法：引号/export/注释/$(…) 字面量/malformed 计数
    with Env() as e:
        e.user_env('# c\nexport IMAGE_BACKEND="openai"\nOPENAI_API_KEY=%s\n\n'
                   'JUNK LINE NO EQUALS\nOPENAI_MODEL=$(whoami)\n' % FAKE)
        r = IC.resolve()
        check("CFG-07a export/引号/注释解析", r.available and r.backend == "openai")
        check("CFG-07b $(…) 字面量不执行", r.model == "$(whoami)")
        check("CFG-07c malformed 计数不静默", r.malformed_lines == 1)

    # CFG-08 provider-specific 不互借
    with Env() as e:
        e.user_env("IMAGE_BACKEND=gemini\nOPENAI_API_KEY=%s\n" % FAKE)
        r = IC.resolve()
        check("CFG-08 backend=gemini 时 OPENAI_API_KEY 不算数",
              r.state == IC.STATE_UNAVAILABLE)

    # CFG-09 未知 backend → INVALID（不猜）
    with Env() as e:
        e.user_env("IMAGE_BACKEND=dall-e-9000\n")
        r = IC.resolve()
        check("CFG-09 未知 backend→INVALID", r.state == IC.STATE_INVALID)

    # CFG-10 诊断视图零 Key：任意 6 字滑窗不出现在公开输出
    import json
    with Env() as e:
        e.user_env("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\n" % FAKE)
        r = IC.resolve()
        pub = json.dumps(r.to_public(), ensure_ascii=False) + repr(r) + str(r) + "%s" % r
        windows = {FAKE[i:i + 6] for i in range(len(FAKE) - 5)}
        check("CFG-10 to_public/repr/str/format 全掩码",
              not any(w in pub for w in windows) and "configured" in pub)
        # fingerprint 是设计允许的唯一 Key 派生输出（sha256[:8]，不可反推）；
        # 断言：稳定、8 位、且 ≠ Key 任何前缀（不是截断泄漏）
        fp = r.credential.fingerprint()
        check("CFG-10b fingerprint 稳定/8位/非 Key 截断",
              fp == r.credential.fingerprint() and len(fp) == 8
              and not FAKE.upper().startswith(fp.upper())
              and fp in r.to_public()["credential_fingerprint"])

    # CFG-11 upsert 合并式写入：保留其它 backend 行；remove 只删该 backend
    with Env() as e:
        e.user_env("IMAGE_BACKEND=openai\nOPENAI_API_KEY=%s\n"
                   "GEMINI_API_KEY=sk-TEST-geminiplaceholder0000\n" % FAKE)
        path, changed = IC.upsert_user_env("openai", model="m2")
        body = open(path, encoding="utf-8").read()
        check("CFG-11a upsert 增改目标键", "OPENAI_MODEL=m2" in body)
        check("CFG-11b upsert 保留其它 backend", "GEMINI_API_KEY" in body
              and FAKE in body)
        IC.upsert_user_env("openai", drop_backend=True)
        body = open(path, encoding="utf-8").read()
        check("CFG-11c remove 只删该 backend", FAKE not in body
              and "GEMINI_API_KEY" in body)

    print(f"test_image_config 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
