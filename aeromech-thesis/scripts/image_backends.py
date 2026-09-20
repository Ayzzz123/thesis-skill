# -*- coding: utf-8 -*-
"""image_backends.py — v1.6.5 最终阶段：真实 External Image Backend（仅 OpenAI-compatible）

范围纪律（任务 §二/§十七）：本次只实现一个真实 provider（OpenAI-compatible，
IMAGE_BACKEND=openai，OPENAI_API_KEY/MODEL/BASE_URL）；Gemini/Qwen/MiniMax 等经
同一 `OpenAICompatBackend` 配置驱动接入（base_url+前缀），**不逐厂商写代码**。
不新建框架：backend 由 image_provider.route() 选中、ai_figure_gate 把关后才到达这里。

安全（§九/§十二）：
  - ImageError.__str__ 源头脱敏（redact_text）——异常文本进 record/log_action 前已干净；
  - transport 注入点 self._http(method, url, headers, body, timeout) -> (status, dict)
    测试用 mock 注入（IMG-02/03/04 零真实网络）；普通回归绝不外呼（§十）。
错误分类（§九，8 类，401 不伪装成普通失败）：
  INVALID_CREDENTIAL / RATE_LIMIT / MODEL_UNAVAILABLE / NETWORK_ERROR /
  TIMEOUT / PROVIDER_ERROR / CONTENT_POLICY_ERROR / GENERATION_FAILED
"""
import base64
import json
import os
import socket
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from image_config import redact_text

DEFAULT_BASE_URL = {"openai": "https://api.openai.com/v1"}
DEFAULT_MODEL = {"openai": "gpt-image-2"}     # 文档级建议默认（用户可覆盖）
SMOKE_SIZE = "256x256"                          # image test 最小 smoke
DEFAULT_TIMEOUT = 120


class ImageError(Exception):
    """统一外部调用异常：code ∈ 8 类；retryable 决定是否允许自动重试。"""
    RETRYABLE = {"RATE_LIMIT", "NETWORK_ERROR", "TIMEOUT", "PROVIDER_ERROR"}

    def __init__(self, code, message="", retryable=None):
        self.code = code
        self.message = redact_text(str(message))[:300]
        self.retryable = (code in self.RETRYABLE) if retryable is None else retryable
        super().__init__(self.__str__())

    def __str__(self):
        return f"{self.code}: {self.message}"


def _transport_http(method, url, headers, body, timeout):
    """真实 HTTP（stdlib）。headers 含 Authorization——本函数不落日志不外传。"""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace") or "{}")
        except Exception:
            payload = {}
        return e.code, payload
    except socket.timeout:
        raise ImageError("TIMEOUT", f"request exceeded {timeout}s")
    except (urllib.error.URLError, OSError) as e:
        raise ImageError("NETWORK_ERROR", redact_text(str(e)))


class ImageBackend:
    """backend 抽象：generate(prompt)->bytes；check()->True（最小 smoke）。"""
    name = "abstract"

    def __init__(self, credential, model=None, base_url=None, timeout=DEFAULT_TIMEOUT):
        self._key = credential.reveal() if hasattr(credential, "reveal") else str(credential or "")
        self.model = model or DEFAULT_MODEL.get(self.name)
        self.base_url = (base_url or DEFAULT_BASE_URL.get(self.name) or "").rstrip("/")
        self.timeout = timeout
        self._http = _transport_http          # 测试注入点

    def _post_json(self, path, body):
        if not self._key:
            raise ImageError("INVALID_CREDENTIAL", "empty credential reached backend")
        url = self.base_url + path
        req = json.dumps(body).encode("utf-8")
        status, payload = self._http(
            "POST", url,
            {"Content-Type": "application/json",
             "Authorization": "Bearer " + self._key},
            req, self.timeout)
        return status, payload

    @staticmethod
    def _map_error(status, payload):
        """状态码→8 类错误（§九：401 不得伪装成普通生成失败）。"""
        msg = ""
        try:
            msg = str((payload or {}).get("error", {}))
            if isinstance((payload or {}).get("error"), dict):
                msg = str(payload["error"].get("message", msg)) + " " + \
                      str(payload["error"].get("code", ""))
        except Exception:
            pass
        low = msg.lower()
        if status in (401, 403):
            raise ImageError("INVALID_CREDENTIAL", f"HTTP {status}: {msg[:120]}")
        if status == 404:
            raise ImageError("MODEL_UNAVAILABLE", f"HTTP 404: {msg[:120]}")
        if status == 429:
            raise ImageError("RATE_LIMIT", f"HTTP 429: {msg[:120]}")
        if "safety" in low or "content_policy" in low or "moderation" in low or \
                "flagged" in low or status == 451:
            raise ImageError("CONTENT_POLICY_ERROR", f"HTTP {status}: {msg[:120]}")
        if status >= 500:
            raise ImageError("PROVIDER_ERROR", f"HTTP {status}: {msg[:120]}")
        raise ImageError("PROVIDER_ERROR", f"HTTP {status}: {msg[:120]}")

    def generate(self, prompt, size=None, out_path=None):
        raise NotImplementedError

    def check(self):
        """最小 smoke：真实生成一张极小图（仅用户主动 image test 调用）。"""
        png = self.generate("minimal academic diagram placeholder, single grey "
                            "rectangle on white background, no text", size=SMOKE_SIZE)
        return len(png) > 0


class OpenAICompatBackend(ImageBackend):
    """OpenAI-compatible /images/generations（b64_json）。qwen/zhipu 等兼容端点
    经 base_url 配置复用本类——新厂商=配置，不加代码（§二）。"""
    name = "openai"

    def generate(self, prompt, size=None, out_path=None):
        if not prompt or not str(prompt).strip():
            raise ImageError("GENERATION_FAILED", "empty prompt rejected at backend")
        body = {"model": self.model, "prompt": str(prompt), "n": 1,
                "size": size or "1024x1024", "response_format": "b64_json"}
        status, payload = self._post_json("/images/generations", body)
        if status not in (200, 201):
            self._map_error(status, payload)
        data = (payload or {}).get("data") or []
        b64 = (data[0].get("b64_json") if data and isinstance(data[0], dict) else None)
        if not b64:
            raise ImageError("GENERATION_FAILED",
                             "provider returned no image data")
        try:
            blob = base64.b64decode(b64)
        except Exception as e:
            raise ImageError("GENERATION_FAILED", f"undecodable image: {e}")
        if len(blob) < 1000:
            raise ImageError("GENERATION_FAILED",
                             f"response too small ({len(blob)}B), likely empty")
        if out_path:
            tmp = out_path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, out_path)          # 原子落盘，不留半截文件
        return blob


# 兼容端点复用同一实现（配置驱动；本次只 openai 为"已实现真实 provider"）
class QwenCompatBackend(OpenAICompatBackend):
    name = "qwen"


BACKENDS = {b.name: b for b in (OpenAICompatBackend, QwenCompatBackend)}


def get_backend(backend_name, credential, model=None, base_url=None):
    cls = BACKENDS.get((backend_name or "").lower())
    if cls is None:
        raise ImageError("MODEL_UNAVAILABLE",
                         f"backend {backend_name!r} 未实现真实调用"
                         f"（已实现 {sorted(BACKENDS)}；其余 Phase 后续按配置接入）")
    return cls(credential, model=model, base_url=base_url)
