# -*- coding: utf-8 -*-
"""image_config.py — v1.6.5 Phase 2A：用户级 Image Model 凭据配置与解析（可选增强）

核心兼容承诺（设计基线 docs/v1.6.5/image-provider/ rev2）：
  外部 Image API = 可选增强。未配置 = `UNAVAILABLE`（**正常状态，不是错误**）→
  调用方沿用原有 Figure Pipeline（LocalProvider；host-native 属 Phase 2B+，当前代码
  不存在该路径，不虚构）。任何情况下不 BLOCK、不 fake image。

职责：
  1. redact_text()          —— 全仓统一脱敏（record()/log_action() 边界复用）
  2. SecretStr              —— Key 只存运行时对象；repr/str/format 全掩码
  3. load_env_file()        —— 最小 .env 方言（无插值/无命令替换，$(…) 为字面量）
  4. env_sources()          —— 搜索序：process env → [project(默认禁用)] → skill → ~/.aeromech
                              首个存在的 .env 为唯一文件源，**绝不跨文件合并**
  5. resolve()              —— ResolutionResult：AVAILABLE / UNAVAILABLE / INVALID / FAILED
  6. 指纹/公开视图           —— 诊断输出永不含 Key（fingerprint=sha256[:8]）

禁止：本模块不 import requests/urllib 发起任何外部调用（Phase 2A 无网络面）。
"""
import hashlib
import os
import re
import sys

REDACTED = "***REDACTED***"

# ---------------- 1. redact ----------------
_REDACT_RULES = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*)\S+"), r"\1" + REDACTED),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]{8,}=*"), r"\1" + REDACTED),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{8,}"), REDACTED),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}"), REDACTED),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), REDACTED),
    (re.compile(r"\beyJ[A-Za-z0-9\-_]{12,}\.[A-Za-z0-9\-_]{8,}[^,\s\"']*"), REDACTED),
    (re.compile(r"(?i)(\bkey\s*[=:]\s*)([^&\s\"']{6,})"), r"\1" + REDACTED),
    (re.compile(r"(?i)(\b(?:api[_-]?key|access[_-]?token|secret)\s*[=:]\s*)([^&\s\"']{6,})"),
     r"\1" + REDACTED),
]


def redact_text(text):
    """统一脱敏：宁可错杀不可漏放（都是排障文本）。
    不误伤：'Bearing 轴承'（无 bearer+空白token 形态）、'monkey=3'（\\bkey 不匹配词内）。"""
    if text is None:
        return text
    out = str(text)
    for rx, rep in _REDACT_RULES:
        out = rx.sub(rep, out)
    return out


def redact_obj(obj):
    """递归脱敏 dict/list/str 结构（log_action input/output 用）。"""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, SecretStr):
        return str(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(x) for x in obj]
    return obj


# ---------------- 2. SecretStr ----------------
class SecretStr:
    """Key 的运行时容器：repr/str/format 全掩码，真值只能 reveal() 显式取。
    故意不继承 str——str 子类在 f-string/__format__ 下会泄漏原值。"""
    __slots__ = ("_v",)

    def __init__(self, v):
        self._v = str(v) if v is not None else ""

    def reveal(self):
        return self._v

    def __bool__(self):
        return bool(self._v)

    def __repr__(self):
        return "SecretStr(%s)" % (REDACTED if self._v else "empty")

    def __str__(self):
        return repr(self)

    def __format__(self, spec):
        return str(self)

    def fingerprint(self):
        """sha256 前 8 位：可判断"是不是同一把 Key"，不可反推。"""
        if not self._v:
            return None
        return hashlib.sha256(self._v.encode("utf-8")).hexdigest()[:8]


# ---------------- 3. .env 最小方言 ----------------
_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def load_env_file(path):
    """返回 ({KEY: value}, malformed_count)。值去首尾成对引号；
    无插值、无命令替换：$(…) 原样字面量（.env 不是脚本，防注入面）。"""
    vals, malformed = {}, 0
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s or s.startswith("#"):
                    continue
                m = _LINE_RE.match(s)
                if not m:
                    malformed += 1
                    continue
                v = m.group(2).strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                vals[m.group(1)] = v
    except OSError:
        pass
    return vals, malformed


# ---------------- 4. 搜索序（首命中不合并） ----------------
STATE_AVAILABLE = "AVAILABLE"
STATE_UNAVAILABLE = "UNAVAILABLE"
STATE_INVALID = "INVALID"
STATE_FAILED = "FAILED"

KNOWN_BACKENDS = {"openai", "gemini", "qwen", "zhipu", "minimax", "volcengine",
                  "host_native"}
# 非敏感建议默认值（文档可推荐；用户 <B>_MODEL 可覆盖；不写死调用面）
SUGGESTED_MODEL = {"openai": "gpt-image-2", "gemini": "gemini-3.1-flash-image"}


def skill_home():
    env = os.environ.get("AEROMECH_SKILL_HOME")
    if env:
        return env
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_sources(cwd=None):
    """搜索序（§五/§十二）：project（默认禁用）→ skill → user。
    进程 env 在 _get() 中每键独立最高优先。"""
    cwd = cwd or os.getcwd()
    files = []
    if os.environ.get("IMAGE_ALLOW_PROJECT_ENV") == "1":
        files.append(("project", os.path.join(cwd, ".env")))
    files.append(("skill", os.path.join(skill_home(), ".env")))
    files.append(("user", os.path.join(os.path.expanduser("~"), ".aeromech", ".env")))
    return files


_project_warned = [False]


class Result:
    """ResolutionResult（§十契约）。state ∈ AVAILABLE/UNAVAILABLE/INVALID/FAILED。
    UNAVAILABLE 不是错误：needs_configuration 仅当调用方 required=True。"""

    def __init__(self, state, backend=None, model=None, base_url=None,
                 credential=None, source=None, reason="", needs_configuration=False,
                 malformed_lines=0):
        self.state = state
        self.backend = backend
        self.model = model
        self.base_url = base_url
        self.credential = credential          # SecretStr | None
        self.source = source                  # process/skill/user/project
        self.reason = reason
        self.needs_configuration = needs_configuration
        self.malformed_lines = malformed_lines

    @property
    def available(self):
        return self.state == STATE_AVAILABLE

    def to_public(self):
        """公开视图：永不含 Key 值（诊断/CLI/日志唯一出口）。"""
        return {
            "state": self.state,
            "backend": self.backend,
            "model": self.model,
            "base_url": self.base_url,
            "credential": ("configured" if self.credential else "missing"),
            "credential_fingerprint": (self.credential.fingerprint()
                                       if self.credential else None),
            "source": self.source,
            "reason": redact_text(self.reason),
            "needs_configuration": self.needs_configuration,
            "malformed_lines": self.malformed_lines,
        }

    def __repr__(self):
        return "Result(%s)" % self.to_public()

    def __str__(self):
        return repr(self)

    def __format__(self, spec):
        return repr(self)


def _get(key, envfile):
    """进程 env 每键独立最高优先；文件层只认已选中的那一个 envfile（不合并）。"""
    v = os.environ.get(key)
    if v not in (None, ""):
        return v, "process"
    if envfile and envfile["vals"].get(key) not in (None, ""):
        return envfile["vals"][key], envfile["scope"]
    return None, None


def resolve(required=False, cwd=None):
    """解析外部 Image 配置。
    required=True（用户显式 provider_required: external）时，未配置→
    UNAVAILABLE + needs_configuration=True（→上层 NEEDS_CONFIGURATION/NHR）。
    默认 required=False：未配置=UNAVAILABLE=正常回落既有管线。"""
    try:
        envfile = None
        for scope, path in env_sources(cwd):
            if os.path.isfile(path):
                vals, malformed = load_env_file(path)
                envfile = {"scope": scope, "path": path, "vals": vals,
                           "malformed": malformed}
                if scope == "project" and not _project_warned[0]:
                    _project_warned[0] = True
                    print("[image_config] WARNING: project-level .env enabled "
                          "(IMAGE_ALLOW_PROJECT_ENV=1) — 项目目录可能被分享/提交，"
                          "推荐改用 ~/.aeromech/.env", file=sys.stderr)
                break            # 首命中即停：后面的文件不再读取、不合并
        backend, bsrc = _get("IMAGE_BACKEND", envfile)
        backend = (backend or "").strip().lower() or None
        malformed = envfile["malformed"] if envfile else 0
        if not backend:
            return Result(STATE_UNAVAILABLE,
                          reason="IMAGE_BACKEND not set（未配置外部 Image API=正常状态，"
                                 "沿用既有 Figure Pipeline）",
                          needs_configuration=bool(required),
                          malformed_lines=malformed)
        if backend not in KNOWN_BACKENDS:
            return Result(STATE_INVALID, backend=backend,
                          reason=f"unknown IMAGE_BACKEND {backend!r}"
                                 f"（可用 {sorted(KNOWN_BACKENDS)}）",
                          malformed_lines=malformed)
        pref = backend.upper()
        key, ksrc = _get(pref + "_API_KEY", envfile)
        model, _ = _get(pref + "_MODEL", envfile)
        model = model or SUGGESTED_MODEL.get(backend)
        base, _ = _get(pref + "_BASE_URL", envfile)
        source = ksrc or bsrc
        if backend == "host_native":
            # 宿主原生生成路径：零凭据（§八 host-native 无需 API key）；
            # 实际生成能力由宿主在 Phase 2B+ 接入，此处仅解析配置态。
            return Result(STATE_AVAILABLE, backend=backend, model=model,
                          base_url=None, credential=None, source=source,
                          malformed_lines=malformed)
        if not key:
            return Result(STATE_UNAVAILABLE, backend=backend, model=model,
                          base_url=base, source=source,
                          reason=f"{pref}_API_KEY not set（未配置=正常状态，"
                                 "沿用既有 Figure Pipeline）",
                          needs_configuration=bool(required),
                          malformed_lines=malformed)
        cred = SecretStr(key)
        return Result(STATE_AVAILABLE, backend=backend, model=model, base_url=base,
                      credential=cred, source=source, malformed_lines=malformed)
    except Exception as e:            # 解析器自身缺陷 → FAILED（绝不冒泡打断管线）
        return Result(STATE_FAILED, reason=redact_text(f"{type(e).__name__}: {e}"))


# ---------------- 用户级 .env 写入（CLI config/remove 用） ----------------
def user_env_path():
    return os.path.join(os.path.expanduser("~"), ".aeromech", ".env")


def upsert_user_env(backend, api_key=None, model=None, base_url=None,
                    set_backend=True, drop_backend=False):
    """合并式写 ~/.aeromech/.env：只增改该 backend 的行，保留其它 backend 行。
    返回 (path, changed_keys)。api_key 只在参数里短暂存在，不打印。"""
    path = user_env_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    if os.path.isfile(path):
        lines = open(path, encoding="utf-8").read().splitlines()
    pref = backend.upper()
    wanted = {}
    if set_backend:
        wanted["IMAGE_BACKEND"] = backend
    if not drop_backend and api_key:
        wanted[pref + "_API_KEY"] = api_key
    if not drop_backend and model:
        wanted[pref + "_MODEL"] = model
    if not drop_backend and base_url:
        wanted[pref + "_BASE_URL"] = base_url
    drop_keys = set() if not drop_backend else {pref + "_API_KEY", pref + "_MODEL",
                                                pref + "_BASE_URL"}
    out, seen, changed = [], set(), []
    for ln in lines:
        m = _LINE_RE.match(ln.strip()) if ln.strip() and not ln.strip().startswith("#") else None
        if m and m.group(1) in drop_keys:
            changed.append(m.group(1))
            continue
        if m and m.group(1) in wanted:
            out.append(f"{m.group(1)}={wanted[m.group(1)]}")
            seen.add(m.group(1))
            changed.append(m.group(1))
        else:
            out.append(ln)
    for k, v in wanted.items():
        if k not in seen:
            out.append(f"{k}={v}")
            changed.append(k)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip("\n") + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass                          # Windows：提示由 CLI 负责
    return path, changed
