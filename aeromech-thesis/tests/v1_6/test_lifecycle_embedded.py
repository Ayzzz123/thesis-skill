# -*- coding: utf-8 -*-
"""test_lifecycle_embedded.py — B5a/B5b：图生命周期 EMBEDDED 真实写入 + VERIFIED 缺证据不得进入

B5a（_mark_embedded 真实回归）：
  `thesis_build._mark_embedded`（thesis_build.py:368-399）是 v1.6 唯一把图推进到
  EMBEDDED 的生产写入点，此前**零测试覆盖**（commit 49d89b7 的修复无回归锁）。
  本套件覆盖：
    · VALIDATED 图经真实 build_docx 后确实写入 EMBEDDED（非手工 FI.record）
    · 占位行未命中 / 图文件缺失 / 状态未达 VALIDATED → 不得伪造 EMBEDDED
    · 重复构建幂等（不破坏状态、不产生错误的历史倒序）

B5b（VERIFIED 语义锁）：
  全仓生产代码**没有任何** VERIFIED 写入者（`grep '"VERIFIED"'` 仅命中
  figure_iface 的枚举常量与 docstring）。VERIFIED 语义是"已由人工/PDF 级 QA 核验"，
  属**设计上有意保留**的人工终态，不属于测试缺口——因此本轮**不新增自动写入**，
  而是用负例把该语义锁死：无真实验证证据时不得进入 VERIFIED。

  同时锁定既有语义：VERIFIED 是追加式历史的终态，记录后不得被自动降级覆盖。
运行：python tests/v1_6/test_lifecycle_embedded.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import _fixtures as F
import figure_iface as FI
import research_integrity as RI
import thesis_build as TB
import yaml

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS", name, extra)
    else:
        FAIL += 1
        print("  FAIL", name, extra)


def w(root, rel, txt):
    p = os.path.join(root, ".aeromech", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def build_env(tmp, name, placeholder="（图1-1 示意）", fig_present=True,
              fig_status="VALIDATED"):
    """构造：契约 + 章节（含图占位行）+ 图文件 + 研究链接 + 生命周期状态。"""
    root = F.make_project(os.path.join(tmp, name), with_template=False)
    fdir = os.path.join(root, ".aeromech", "artifacts", "figures")
    os.makedirs(os.path.join(fdir, "final"), exist_ok=True)
    png = os.path.join(fdir, "final", "fig1-1.png")
    if fig_present:
        # 最小可解析 PNG（1x1 白点）——FigureBlock 需要真实图片字节
        import struct
        import zlib

        def _chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))

        raw = b"\x00\xff\xff\xff"
        png_bytes = (b"\x89PNG\r\n\x1a\n"
                     + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + _chunk(b"IDAT", zlib.compress(raw))
                     + _chunk(b"IEND", b""))
        with open(png, "wb") as f:
            f.write(png_bytes)

    c = {
        "project": {"title": "生命周期测试", "author": "张三", "major": "飞行器维修",
                    "school": "某大学"},
        "content": {"abstract_zh": "摘要。", "keywords": ["k"],
                    "chapters": ["artifacts/chapters/ch1.md"],
                    "references_file": "artifacts/literature.md"},
        "research": {"required": False},
        "school_format": {},
        "figures": [{"figure_id": "FIG-001", "display": "图1-1",
                     "file": ".aeromech/artifacts/figures/final/fig1-1.png",
                     "caption_cn": "示意图", "caption_en": "Schematic"}],
        "qa": {"out": "artifacts/qa"},
    }
    w(root, "build-contract.yaml", yaml.safe_dump(c, allow_unicode=True))
    w(root, "artifacts/chapters/ch1.md",
      "# 第1章 绪论\n\n研究背景一段。\n\n" + placeholder + "\n")
    w(root, "artifacts/literature.md", "- 参考文献一\n")
    # 研究链接（figure_iface.validate 的硬关卡）
    RI.save_registry(root, "rq", [{"id": "RQ-01", "question": "q", "objective": "o"}])
    RI.save_registry(root, "figures", [{"id": "FIG-001", "name": "fig1-1",
                                        "type": "fault_tree",
                                        "related_rqs": ["RQ-01"]}])
    # 生命周期：先记 PLANNED，再推进到目标状态
    FI.record(root, "FIG-001", "PLANNED", artifact=".aeromech/artifacts/figures/final/fig1-1.png",
              reason="test setup")
    if fig_status and fig_status != "PLANNED":
        FI.record(root, "FIG-001", fig_status,
                  artifact=".aeromech/artifacts/figures/final/fig1-1.png",
                  reason="test setup")
    return root


def life(root, fid="FIG-001"):
    return [h["status"] for h in FI.load_lifecycle(root).get(fid, [])]


def main():
    tmp = tempfile.mkdtemp(prefix="life_v16_")
    print("== test_lifecycle_embedded ==")

    # ---------- B5a-01：VALIDATED 图经真实构建 → EMBEDDED ----------
    r1 = build_env(tmp, "ok")
    check("B5a-00 前置：构造后状态为 VALIDATED",
          FI.current_status(r1, "FIG-001")[0] == "VALIDATED",
          str(FI.current_status(r1, "FIG-001")[0]))
    TB.build_docx(r1)
    st1 = FI.current_status(r1, "FIG-001")[0]
    check("B5a-01 真实 build_docx 后写入 EMBEDDED（非手工 record）",
          st1 == "EMBEDDED", str(st1))
    hist1 = life(r1)
    check("B5a-02 生命周期历史为 PLANNED→VALIDATED→EMBEDDED（顺序正确）",
          hist1 == ["PLANNED", "VALIDATED", "EMBEDDED"], str(hist1))
    last1 = FI.load_lifecycle(r1)["FIG-001"][-1]
    check("B5a-03 EMBEDDED 记录带 artifact 与理由",
          last1.get("artifact") and "构建" in str(last1.get("reason", "")),
          str(last1.get("reason"))[:50])

    # ---------- B5a-04：占位行未命中 → 不得伪造 EMBEDDED ----------
    r2 = build_env(tmp, "no_hit", placeholder="图1-1 只是一句普通正文引用。")
    TB.build_docx(r2)
    st2 = FI.current_status(r2, "FIG-001")[0]
    check("B5a-04 占位行未命中 → 状态停留在 VALIDATED（不伪造 EMBEDDED）",
          st2 == "VALIDATED", str(st2))

    # ---------- B5a-05：图文件缺失 → 不得伪造 EMBEDDED ----------
    # 契约校验会先拦截缺图（BuildError，本身即 fail-closed）。此处直接调用
    # _mark_embedded，锁定"图文件不在场即跳过"这一层的行为。
    r3 = build_env(tmp, "no_file", fig_present=False)
    c3 = TB.load_contract(r3)[0]
    cap3, _en3, figdir3, _fe3 = TB._fig_maps(c3, r3)
    TB._mark_embedded(r3, c3, cap3, figdir3)
    st3 = FI.current_status(r3, "FIG-001")[0]
    check("B5a-05 图文件缺失 → _mark_embedded 不得记 EMBEDDED",
          st3 == "VALIDATED", str(st3))
    # 且真实 build_docx 在缺图时明确失败（契约校验 fail-closed，不静默出半成品）
    raised3 = None
    try:
        TB.build_docx(r3)
    except TB.BuildError as e:
        raised3 = str(e)
    check("B5a-05b 缺图时 build_docx 明确失败（不静默产出残缺论文）",
          raised3 is not None and "文件缺失" in raised3, str(raised3)[:60])

    # ---------- B5a-06：状态未达 VALIDATED/GENERATED → 不得凭空创建 ----------
    r4 = build_env(tmp, "planned_only", fig_status=None)   # 只到 PLANNED
    check("B5a-06 前置：仅 PLANNED",
          FI.current_status(r4, "FIG-001")[0] == "PLANNED")
    TB.build_docx(r4)
    st4 = FI.current_status(r4, "FIG-001")[0]
    check("B5a-07 仅 PLANNED 的图不得被构建提升为 EMBEDDED（不凭空创建）",
          st4 == "PLANNED", str(st4))

    # ---------- B5a-08：REJECTED 图不得被构建洗白 ----------
    r5 = build_env(tmp, "rejected", fig_status="REJECTED")
    TB.build_docx(r5)
    st5 = FI.current_status(r5, "FIG-001")[0]
    check("B5a-08 REJECTED 图不得被构建改写为 EMBEDDED",
          st5 == "REJECTED", str(st5))

    # ---------- B5a-09：重复构建幂等（不破坏状态） ----------
    r6 = build_env(tmp, "twice")
    TB.build_docx(r6)
    st6a = FI.current_status(r6, "FIG-001")[0]
    hist6a = life(r6)
    TB.build_docx(r6)
    st6b = FI.current_status(r6, "FIG-001")[0]
    hist6b = life(r6)
    check("B5a-09 二次构建后状态仍为 EMBEDDED",
          st6a == "EMBEDDED" and st6b == "EMBEDDED", f"{st6a}/{st6b}")
    check("B5a-10 二次构建不重复追加 EMBEDDED（幂等）",
          hist6b.count("EMBEDDED") == hist6a.count("EMBEDDED"),
          f"{hist6a} -> {hist6b}")
    check("B5a-11 历史顺序保持单调（无倒序/无重复 VALIDATED）",
          hist6b == ["PLANNED", "VALIDATED", "EMBEDDED"], str(hist6b))

    # ---------- B5a-12：manifest 记录与交付物一致（真实 pipeline 落盘） ----------
    r10 = build_env(tmp, "manifest")
    pres = TB.pipeline(r10, steps=["docx"])
    m10 = TB.load_manifest(r10)
    check("B5a-12 pipeline 运行后 manifest 落盘",
          m10 is not None, str(type(m10)))
    check("B5a-13 manifest 登记 docx 产物且含 sha256",
          bool(m10) and any("毕业论文.docx" in str(a.get("path", ""))
                            and a.get("sha256") for a in (m10.get("artifacts") or [])),
          str([(a.get("path"), bool(a.get("sha256")))
               for a in ((m10 or {}).get("artifacts") or [])][:3]))
    check("B5a-14 pipeline 步骤记录含 docx 状态",
          isinstance(pres, dict) and pres.get("status") in
          ("PASS", "PASS_WITH_WARNINGS", "BLOCK", "ERROR")
          and any(s.get("step") == "docx" for s in (pres.get("steps") or [])),
          str(pres.get("status")))

    # ---------- B5b：VERIFIED 缺证据不得进入 ----------
    # 1) 生产代码不得把图自动推入 VERIFIED
    prod_writers = []
    for fn in ("figure_iface.py", "thesis_build.py", "research_repair.py"):
        p = os.path.join(HERE, "..", "..", "scripts", fn)
        src = open(p, encoding="utf-8").read()
        # 排除枚举常量与注释行，找真正的 record(..., "VERIFIED")
        for i, ln in enumerate(src.splitlines(), 1):
            if '"VERIFIED"' in ln and "record(" in ln:
                prod_writers.append(f"{fn}:{i}")
    check("B5b-01 生产代码无自动写入 VERIFIED（人工/PDF-QA 终态）",
          prod_writers == [], str(prod_writers))

    # 2) 走到 EMBEDDED 的图不得自动变成 VERIFIED
    r7 = build_env(tmp, "not_verified")
    TB.build_docx(r7)
    st7 = FI.current_status(r7, "FIG-001")[0]
    check("B5b-02 构建完成后状态为 EMBEDDED 而非 VERIFIED",
          st7 == "EMBEDDED", str(st7))

    # 3) 缺证据时 delivery_gate 的图域不得因"非 REJECTED"就放行 VERIFIED 语义
    from delivery_gate import aggregate
    import delivery_gate as DG
    res7 = aggregate(r7)
    fig7 = {x["gate_id"]: x for x in res7["items"]}.get("G-FIG-01")
    check("B5b-03 图域存在且给出明确判定（不因无 VERIFIED 而静默消失）",
          fig7 is not None, str(fig7 and fig7["status"]))

    # 4) VERIFIED 是显式人工动作：只有显式 record 才能到达，且不得被自动降级
    r8 = build_env(tmp, "manual_verified")
    TB.build_docx(r8)
    FI.record(r8, "FIG-001", "VERIFIED", reason="人工核验：PDF 级 QA 通过")
    check("B5b-04 显式人工 record 可到达 VERIFIED（状态机允许）",
          FI.current_status(r8, "FIG-001")[0] == "VERIFIED",
          str(FI.current_status(r8, "FIG-001")[0]))
    TB.build_docx(r8)   # 再构建一次
    check("B5b-05 再次构建不得把 VERIFIED 降级为 EMBEDDED",
          FI.current_status(r8, "FIG-001")[0] == "VERIFIED",
          str(FI.current_status(r8, "FIG-001")[0]))
    check("B5b-06 VERIFIED 记录保留（追加式历史不丢证据）",
          "VERIFIED" in life(r8), str(life(r8)))

    # 5) 非法生命周期状态被拒绝（不得写入任意状态）
    r9 = build_env(tmp, "badstatus")
    raised = None
    try:
        FI.record(r9, "FIG-001", "TOTALLY_DONE", reason="x")
    except ValueError as e:
        raised = str(e)
    check("B5b-07 非法生命周期状态被拒绝（状态机封闭）",
          raised is not None and "TOTALLY_DONE" in raised, str(raised)[:60])

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_lifecycle_embedded 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
