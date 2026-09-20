# -*- coding: utf-8 -*-
"""secret_leak_qa.py — v1.6.5 Phase 2A：凭据泄漏扫描（§九/§十/§十一）

扫描面（--scope）：
  repo         git tracked 文件（工作树内容）
  diff         git diff --cached（staged，即将进 commit 的内容）
  artifacts    项目 .aeromech/** 全部文本 + 交付 docx/pdf 文本层 + figures 文件名
  all          以上全部（交付前推荐）

判定：
  疑似真实凭据 → FAIL（gate 域 BLOCK 用）；高熵可疑串 → WARN。
  白名单：仅 tests/ 目录内允许 `sk-TEST-` 前缀合成样本（防"把真 Key 改名混过白名单"
  ——白名单不作用于 repo 之外的 scope 语义，也不作用于 tests/ 里的非 TEST 形态）。
  .gitignore 是辅助不是唯一防线：被 ignore 但已 tracked 的文件同样扫（repo scope）。

用法:
  python secret_leak_qa.py <root> [--scope repo|diff|artifacts|all] [--json]
退出码: 0=无发现 1=FAIL（疑似真实 Key） 2=WARN（仅高熵可疑） 3=内部错误
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

ENTROPY_MIN = 3.5
LONG_RUN = 20

_PATTERNS = [
    ("api_key_assign", re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
        r"secret[_-]?key|openai_api_key|gemini_api_key)\b\s*[=:]\s*"
        r"[\"']?(?!\*{3}|YOUR_|<$|\{\{|sk-TEST-)([A-Za-z0-9\-_./+]{16,})")),
    ("sk_key", re.compile(r"(?<!TEST-)\bsk-[A-Za-z0-9\-_]{16,}")),
    ("google_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws_like", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9\-_]{12,}\.[A-Za-z0-9\-_]{8,}")),
    ("bearer_live", re.compile(r"(?i)bearer\s+(?!\*{3}|<)[A-Za-z0-9\-._~+/]{24,}=*")),
    ("url_key_param", re.compile(r"(?i)[?&]key=(?!\*{3}|<)[A-Za-z0-9\-_]{16,}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]
_PLACEHOLDER_OK = re.compile(r"(?i)(your[_-]|xxx+|example|placeholder|<[^>]+>|\*REDACTED)")


def _shannon_entropy(s):
    import math
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def scan_text(text, name):
    """返回 [(kind, severity, name, snippet)]；severity ∈ FAIL/WARN。"""
    hits = []
    for kind, rx in _PATTERNS:
        for m in rx.finditer(text):
            val = m.group(m.lastindex or 0) if m.lastindex else m.group(0)
            if _PLACEHOLDER_OK.search(val):
                continue
            if "tests/" in name and "sk-TEST-" in m.group(0):
                continue                     # 合成样本白名单（仅 tests/ 目录）
            hits.append((kind, "FAIL", name, m.group(0)[:60].replace("\n", " ")))
    # 高熵启发（不判 FAIL，只 WARN 供人工）
    for m in re.finditer(r"\b[A-Za-z0-9+/_\-]{%d,}\b" % LONG_RUN, text):
        tok = m.group(0)
        # 降噪：路径/文件名形态不参与高熵启发（凭据极少长成路径；
        # FAIL 级规则面不受影响——这是精度改进，不是降标准）。
        if "/" in tok or "." in tok or tok.lower().startswith(("test", "v1_")):
            continue
        # 真实凭据几乎必混大小写；纯小写连字符 slug（分支名/词组）不参与启发。
        if not (any(c.isupper() for c in tok) and any(c.islower() for c in tok)):
            continue
        if re.search(r"[0-9]", tok) and re.search(r"[A-Za-z]", tok) and \
                _shannon_entropy(tok) > ENTROPY_MIN and \
                not _PLACEHOLDER_OK.search(tok):
            hits.append(("high_entropy", "WARN", name, tok[:40]))
    return hits


_BINARY_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".docx", ".pptx",
                ".xlsx", ".ico", ".ttf", ".woff", ".woff2", ".pyc")


def _iter_git_tracked(root):
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                             timeout=60)
        files = [f for f in out.stdout.decode("utf-8", "replace").split("\0") if f]
    except Exception:
        return
    for f in files:
        p = os.path.join(root, f)
        if os.path.isfile(p):
            if f.lower().endswith(_BINARY_EXTS):
                # 二进制：只扫文件名（Key 也可能藏在文件名里）；
                # 文本层（docx/pdf）由 artifacts scope 负责提取扫描。
                yield f + " (name-only)", f
                continue
            try:
                yield f, open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                pass


def _iter_staged_diff(root):
    try:
        out = subprocess.run(["git", "diff", "--cached", "-U0"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
        yield "git:staged-diff", out.stdout
    except Exception:
        pass


def _iter_artifacts(root):
    am = os.path.join(root, ".aeromech")
    for dirpath, _dirs, files in os.walk(am):
        for fn in files:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if fn.endswith((".yaml", ".yml", ".json", ".md", ".txt", ".jsonl",
                            ".log", ".csv")):
                try:
                    yield rel, open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    pass
            elif fn.endswith((".docx", ".pdf", ".png", ".jpg", ".jpeg")):
                yield rel + " (name-only)", rel          # 文件名本身也可能带 Key
    for cand in ("毕业论文.docx", "毕业论文.pdf"):
        p = os.path.join(root, cand)
        if not os.path.isfile(p):
            continue
        try:
            if cand.endswith(".pdf"):
                import pymupdf
                doc = pymupdf.open(p)
                yield cand, "\n".join(doc[i].get_text() for i in range(len(doc)))
            else:
                import docx as _docx
                d = _docx.Document(p)
                txt = "\n".join(x.text for x in d.paragraphs)
                for t in d.tables:
                    for r in t.rows:
                        for c in r.cells:
                            txt += "\n" + c.text
                yield cand, txt
        except Exception as e:
            yield cand + " (unreadable)", ""


def run(root, scope="all"):
    all_hits = []
    if scope in ("repo", "all"):
        for name, txt in _iter_git_tracked(root):
            all_hits += scan_text(txt, name)
    if scope in ("diff", "all"):
        for name, txt in _iter_staged_diff(root):
            all_hits += scan_text(txt, name)
    if scope in ("artifacts", "all"):
        for name, txt in _iter_artifacts(root):
            all_hits += scan_text(txt, name)
    fails = [h for h in all_hits if h[1] == "FAIL"]
    warns = [h for h in all_hits if h[1] == "WARN"]
    return {"status": "FAIL" if fails else ("WARN" if warns else "PASS"),
            "failures": fails[:40], "warnings": warns[:20],
            "scanned_scope": scope}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--scope", default="all",
                    choices=["repo", "diff", "artifacts", "all"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="可选：写 secret-leak-report.md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    try:
        res = run(root, a.scope)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return 3
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        lines = ["# Secret Leak QA（v1.6.5）", "",
                 f"- SEC-SCAN 凭据泄漏扫描: {res['status']} | scope={res['scanned_scope']} "
                 f"FAIL={len(res['failures'])} WARN={len(res['warnings'])}"]
        for k, sev, name, snip in res["failures"]:
            lines.append(f"  - [FAIL] {k} @ {name}: {snip}")
        for k, sev, name, snip in res["warnings"]:
            lines.append(f"  - [WARN] {k} @ {name}: {snip}")
        with io.open(a.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json
          else f"secret-leak: {res['status']} (fail={len(res['failures'])} "
               f"warn={len(res['warnings'])})")
    return {"PASS": 0, "WARN": 2, "FAIL": 1}[res["status"]]


if __name__ == "__main__":
    sys.exit(main())
