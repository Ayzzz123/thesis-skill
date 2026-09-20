# -*- coding: utf-8 -*-
"""image_cli.py — v1.6.5 Phase 2A：aeromech image config|status|test|remove

用户旅程（设计 09 文档 §4）：安装即用（无配置=既有管线）；想增强才 config。
Key 纪律（§十）：不回显、不打印、不进日志——本 CLI 任何输出只出现
configured / missing / fingerprint(sha256[:8])。
Phase 2A 无真实 backend：test 已配置时只报 "Credential configured"，
**绝不伪造 Connection: OK**（§八）；未配置 exit 0 + 既有能力可用提示（§十一）。

用法:
  python image_cli.py config  [--backend openai] [--model M] [--base-url U]
  python image_cli.py status
  python image_cli.py test
  python image_cli.py remove  --backend openai
退出码: 0=正常（含"未配置"）；1=配置无效（INVALID）；3=内部错误
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_config as IC


def _cmd_config(a):
    backend = a.backend or input("Image backend (openai/gemini/qwen/...): ").strip().lower()
    if not backend:
        print("aborted: no backend given")
        return 1
    if backend not in IC.KNOWN_BACKENDS:
        print(f"unknown backend {backend!r}（可用 {sorted(IC.KNOWN_BACKENDS)}）")
        return 1
    model = a.model or input(f"Model (default {IC.SUGGESTED_MODEL.get(backend, 'none')}): ").strip() or None
    base = a.base_url or input("Base URL (optional, Enter=skip): ").strip() or None
    key = None
    if backend != "host_native":
        # 不回显纪律：唯一入口 getpass（input() 会回显，禁止用于 Key）
        try:
            key = getpass.getpass("API Key (不回显, Enter=skip): ") or None
        except (EOFError, KeyboardInterrupt):
            key = None
    path, changed = IC.upsert_user_env(backend, api_key=key, model=model,
                                       base_url=base)
    print(f"wrote {len(set(changed))} keys to {path}")
    print("Note: 外部调用将使用您自己的 API Key，可能产生您的 API 费用。")
    return 0


def _cmd_status(_a):
    r = IC.resolve()
    pub = r.to_public()
    print(f"external provider: {pub['state'].lower()}")
    print("existing figure generation: available")
    if pub["state"] != IC.STATE_UNAVAILABLE:
        print(f"backend:    {pub['backend']}")
        print(f"model:      {pub['model'] or '(unset)'}")
        print(f"base_url:   {pub['base_url'] or '(default)'}")
        print(f"credential: {pub['credential']}"
              + (f" (fingerprint {pub['credential_fingerprint']})"
                 if pub['credential_fingerprint'] else ""))
        print(f"source:     {pub['source']}")
    if pub["reason"]:
        print(f"reason:     {pub['reason']}")
    if pub["malformed_lines"]:
        print(f"note:       {pub['malformed_lines']} malformed line(s) in env file")
    return {"AVAILABLE": 0, "UNAVAILABLE": 0, "INVALID": 1, "FAILED": 3}[pub["state"]]


def _cmd_test(_a):
    r = IC.resolve(required=True)
    if r.state == IC.STATE_UNAVAILABLE and not r.credential:
        print("No external image provider configured.")
        print("Existing figure generation remains available.")
        return 0
    pub = r.to_public()
    print(f"Backend:    {pub['backend']}")
    print(f"Model:      {pub['model'] or '(unset)'}")
    print(f"Credential: {pub['credential']}")
    print(f"Source:     {pub['source']}")
    if r.state == IC.STATE_AVAILABLE:
        print("Connection: not tested "
              "(external backend not implemented until Phase 2B — 不伪造 OK)")
        return 0
    print(f"State:      {r.state} | {pub['reason']}")
    return 1 if r.state == IC.STATE_INVALID else 0


def _cmd_remove(a):
    if not a.backend:
        print("usage: remove --backend <name>")
        return 1
    path, changed = IC.upsert_user_env(a.backend.lower(), drop_backend=True)
    print(f"removed {len(set(changed))} key(s) for backend {a.backend} from {path}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aeromech image",
                                 description="User-configured Image Model API（可选增强）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("config")
    c.add_argument("--backend"); c.add_argument("--model"); c.add_argument("--base-url")
    sub.add_parser("status")
    sub.add_parser("test")
    r = sub.add_parser("remove"); r.add_argument("--backend", required=True)
    a = ap.parse_args(argv)
    try:
        return {"config": _cmd_config, "status": _cmd_status,
                "test": _cmd_test, "remove": _cmd_remove}[a.cmd](a)
    except (EOFError, KeyboardInterrupt):
        print("\naborted")
        return 1
    except Exception as e:
        print(f"ERROR: {IC.redact_text(f'{type(e).__name__}: {e}')}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
