#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mermaid Renderer Wrapper for aeromech-thesis

自动检测 Mermaid CLI 环境并渲染 .mmd → PNG/SVG。
探测顺序：
1. mmdc 是否存在
2. 系统 Chrome (C:\Program Files\Google\Chrome\Application\chrome.exe 等)
3. Puppeteer chrome-headless-shell（动态扫描 ~/.cache/puppeteer）

v1.6.5 语义诚信重构（Phase 0 审计 D2）：mmdc 失败时**绝不**生成与真实模型无关的
"像模像样"假图（旧 generate_fallback_figure 已删除——它画通用 Top Event/Cause A/B
冒充真实故障树并以文件>5000B 判成功，属语义造假）。现在失败就是失败：
返回 FIGURE_ERROR；如需排查，只能显式生成带 DIAGNOSTIC 标记的诊断占位物
（generate_diagnostic_placeholder），它永远不被判为成功、永不进入论文。

用法:
    python render_mermaid.py input.mmd output.png [--bg transparent]

退出码:
    0 - 成功（仅 mmdc 真实渲染成功）
    1 - 用法错误
    2 - FIGURE_ERROR（渲染失败；上层必须按"生成失败"处理，不得进 VERIFIED）
"""

import os
import sys
import subprocess
import shutil
import glob


def find_chrome_executable():
    """查找系统 Chrome 可执行文件路径"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def find_puppeteer_chrome():
    """动态扫描 Puppeteer chrome-headless-shell，不写死版本号"""
    cache_dir = os.path.join(os.environ.get("USERPROFILE", ""), ".cache", "puppeteer")
    if not os.path.exists(cache_dir):
        return None
    
    # 递归查找所有 chrome-headless-shell.exe
    pattern = os.path.join(cache_dir, "**", "chrome-headless-shell.exe")
    matches = glob.glob(pattern, recursive=True)
    if matches:
        # 返回最新的一个
        matches.sort(key=os.path.getmtime, reverse=True)
        return matches[0]
    return None


def render_with_mmdc(input_mmd, output_png, bg="transparent"):
    """使用 mmdc 渲染 Mermaid 图表，自动探测浏览器并传递环境变量"""
    mmdc_path = shutil.which("mmdc")
    if not mmdc_path:
        return False, "mmdc not found in PATH", None, "NO_MMDC"

    # 探测浏览器，优先级：系统 Chrome → chrome-headless-shell
    browser_path = find_chrome_executable()
    if browser_path:
        print(f"[Mermaid] Found system Chrome: {browser_path}")
    else:
        browser_path = find_puppeteer_chrome()
        if browser_path:
            print(f"[Mermaid] Found chrome-headless-shell: {browser_path}")
        else:
            print("[Mermaid] Warning: No Chrome/chrome-headless-shell found.")

    # 构建环境变量，显式设置 PUPPETEER_EXECUTABLE_PATH
    env = os.environ.copy()
    if browser_path:
        env["PUPPETEER_EXECUTABLE_PATH"] = browser_path
        print(f"[Mermaid] Setting PUPPETEER_EXECUTABLE_PATH={browser_path}")
    else:
        print("[Mermaid] No browser found, mmdc may fail without PUPPETEER_EXECUTABLE_PATH.")

    cmd = [mmdc_path, "-i", input_mmd, "-o", output_png, "-b", bg]
    print(f"[Mermaid] Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=60, 
            env=env,
            cwd=os.path.dirname(os.path.abspath(input_mmd))
        )
        
        if result.returncode == 0 and os.path.exists(output_png) and os.path.getsize(output_png) > 1000:
            return True, f"Rendered successfully: {output_png} ({os.path.getsize(output_png)} bytes)", browser_path, "MERMAID_OK"
        else:
            stderr_full = result.stderr.strip() if result.stderr else "No stderr"
            stdout_full = result.stdout.strip() if result.stdout else "No stdout"
            error_msg = f"mmdc failed (exit code {result.returncode}).\nSTDOUT: {stdout_full}\nSTDERR: {stderr_full}"
            return False, error_msg, browser_path, "MERMAID_FAILED"
            
    except subprocess.TimeoutExpired:
        return False, "mmdc timeout after 60s", browser_path, "MERMAID_TIMEOUT"
    except Exception as e:
        return False, f"Exception: {str(e)}", browser_path, "MERMAID_EXCEPTION"


def generate_diagnostic_placeholder(output_png, title, reason="mmdc render failed"):
    """v1.6.5（D2 修复）：仅供人工排查的**诊断占位物**，不是论文图。

    与旧 generate_fallback_figure 的本质区别：
    1. 不画任何冒充真实模型的内容（旧版画通用 Top Event/OR Gate/Cause A/B=语义造假）；
    2. 返回值永远 (False, ...)——调用方不可能把它当成功；
    3. 图内以 DIAGNOSTIC 大字 + 原因 + 源文件名明示非正式身份；
    4. 上层拿到 False 后走 REJECTED/NEEDS_HUMAN_REVIEW，lifecycle 永不因此 VERIFIED，
       最终 DOCX/PDF 禁止纳入。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        ax.add_patch(plt.Rectangle((0.02, 0.02), 0.96, 0.96, fill=False,
                                   edgecolor="#9E4337", lw=2, linestyle="--"))
        ax.text(0.5, 0.66, "DIAGNOSTIC PLACEHOLDER", ha="center", va="center",
                fontsize=16, family="SimHei", color="#9E4337", weight="bold")
        ax.text(0.5, 0.5, "【诊断占位物—非论文图，禁止进入交付】",
                ha="center", va="center", fontsize=11, family="SimHei", color="#9E4337")
        ax.text(0.5, 0.38, f"source: {title}", ha="center", va="center",
                fontsize=9, family="SimHei", color="#6B7A88")
        ax.text(0.5, 0.28, f"reason: {str(reason)[:90]}", ha="center", va="center",
                fontsize=9, family="SimHei", color="#6B7A88")
        fig.savefig(output_png, dpi=120)
        plt.close(fig)
        return False, (f"diagnostic placeholder written to {output_png}; "
                       "NOT a figure; caller must treat render as FAILED")
    except ImportError:
        return False, "matplotlib not available; no placeholder written"
    except Exception as e:
        return False, f"placeholder generation exception: {e}"

def main():
    if len(sys.argv) < 3:
        print("Usage: python render_mermaid.py input.mmd output.png [--bg transparent]")
        sys.exit(1)

    input_mmd = sys.argv[1]
    output_png = sys.argv[2]
    bg = sys.argv[3] if len(sys.argv) > 3 else "transparent"

    if not os.path.exists(input_mmd):
        print(f"Error: Input file not found: {input_mmd}")
        sys.exit(1)

    # 从文件名推断图表类型
    basename = os.path.basename(input_mmd).lower()
    if "roadmap" in basename or "flow" in basename:
        diagram_type = "flowchart"
    elif "fault" in basename or "tree" in basename:
        diagram_type = "fault_tree"
    else:
        diagram_type = "general"

    print(f"[Mermaid] Rendering: {input_mmd} → {output_png}")
    print(f"[Mermaid] Background: {bg}")
    print(f"[Mermaid] Diagram type: {diagram_type}")
    print("-" * 60)

    # 尝试 mmdc 渲染
    success, msg, browser_used, status_code = render_with_mmdc(input_mmd, output_png, bg)
    
    if success:
        print(f"[Mermaid] SUCCESS: {msg}")
        if browser_used:
            print(f"[Mermaid] Browser used: {browser_used}")
        print("[Mermaid] Status: MERMAID_OK - Using Mermaid-generated figure")
        sys.exit(0)
    else:
        print(f"[Mermaid] mmdc FAILED ({status_code}):")
        print(msg[:500])  # 限制输出长度
        if browser_used:
            print(f"[Mermaid] Browser attempted: {browser_used}")
        
        # v1.6.5：失败即失败——不再生成可冒充的 fallback 图（D2 语义造假根除）。
        print("\n[Mermaid] No semantic fallback is attempted "
              "(v1.6.5: fake-content fallback removed).")
        print("[Mermaid] Status: FIGURE_ERROR - render failed; figure must NOT enter the thesis.")
        print("[Mermaid] ACTION REQUIRED: lifecycle -> REJECTED/NEEDS_HUMAN_REVIEW; "
              "regenerate via faithful source (figkit role-based) or fix mmdc env.")
        sys.exit(2)  # 退出码 2 表示 FIGURE_ERROR


if __name__ == "__main__":
    main()
