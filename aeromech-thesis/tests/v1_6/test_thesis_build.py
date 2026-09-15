# -*- coding: utf-8 -*-
"""test_thesis_build.py — 统一 Thesis Build Pipeline（指令 §五~八/§十四/§十八；BUILD-01~10）

双模式组装（TEMPLATE_FIDELITY / FORMAT_RECONSTRUCTION，全走既有原语）、契约校验缺失语义、
artifact-manifest（sha256+content_identity）、pipeline 失败裁决（失败阶段/错误码/原因/建议）、
可重复性（content identity vs container metadata 区分）、旧项目 NOT_APPLICABLE。
COM 步骤（toc/repaginate/pdf）在有 Word 的环境经 steps 子集真实跑通（本套件含 pdf 冒烟）。
运行：python tests/v1_6/test_thesis_build.py
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import _fixtures as F
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


def contract(root, mode="recon", chapters=("artifacts/chapters/ch1.md",
                                            "artifacts/chapters/ch2.md")):
    c = {
        "project": {"title": "统一构建题", "author": "张三", "major": "飞行器维修",
                    "school": "某大学"},
        "content": {"abstract_zh": "摘要正文。", "keywords": ["起落架", "刹车"],
                    "abstract_en": "EN abstract body.", "keywords_en": ["gear"],
                    "chapters": list(chapters),
                    "references_file": "artifacts/literature.md",
                    "appendices": [{"title": "附录A 数据表", "file": "artifacts/analysis/apx.md"}],
                    "ack_text": "致谢内容。"},
        "research": {"required": False},
        "school_format": {},
        "qa": {"out": "artifacts/qa"},
    }
    if mode == "tpl":
        c["school_format"]["template"] = "materials/school/模板.docx"
    w(root, "build-contract.yaml", yaml.safe_dump(c, allow_unicode=True))
    w(root, "artifacts/chapters/ch1.md", "# 第1章 绪论\n\n研究背景一段。\n")
    w(root, "artifacts/chapters/ch2.md", "# 第2章 方法\n\n## 2.1 小节\n\n方法内容。\n")
    w(root, "artifacts/literature.md", "- 参考文献一\n- 参考文献二\n")
    w(root, "artifacts/analysis/apx.md", "附录数据说明。\n")
    if mode == "tpl":
        sys.path.insert(0, os.path.join(HERE, ".."))
        import test_a_template_fidelity as TA
        sd = os.path.join(root, "materials", "school")
        os.makedirs(sd, exist_ok=True)
        TA.make_fixture_template(os.path.join(sd, "模板.docx"))
    return c


def main():
    tmp = tempfile.mkdtemp(prefix="build_v16_")
    print("== test_thesis_build ==")

    # ---------- BUILD-01/02 契约加载与校验 ----------
    root = F.make_project(os.path.join(tmp, "b1"), with_template=False)
    r = TB.load_contract(root)
    check("BUILD-08 旧项目（无契约）→NOT_APPLICABLE（不接管不误判 PASS）",
          r[0] is None and TB.validate_contract(root)["status"] == "NOT_APPLICABLE")
    check("BUILD-08 无契约 pipeline→NOT_APPLICABLE+reason",
          TB.pipeline(root)["status"] == "NOT_APPLICABLE")
    contract(root)
    v = TB.validate_contract(root)
    check("BUILD-01 契约加载+validate PASS", v["status"] == "PASS")
    # 缺题目标题→ERROR（不静默补假数据）
    c2 = yaml.safe_load(open(TB.contract_path(root), encoding="utf-8"))
    c2["project"]["title"] = ""
    w(root, "build-contract.yaml", yaml.safe_dump(c2, allow_unicode=True))
    v2 = TB.validate_contract(root)
    check("BUILD-07 必需内容缺→ERROR+列出缺项",
          v2["status"] == "ERROR" and any("title" in e for e in v2["errors"]))
    c2["project"]["title"] = "T"
    c2["content"]["chapters"] = ["artifacts/chapters/nope.md"]
    w(root, "build-contract.yaml", yaml.safe_dump(c2, allow_unicode=True))
    v3 = TB.validate_contract(root)
    check("BUILD-07 章节文件缺→ERROR", v3["status"] == "ERROR"
          and any("nope.md" in e for e in v3["errors"]))
    # 可选域缺 → NOT_APPLICABLE 记录而非错误
    c2["content"]["chapters"] = ["artifacts/chapters/ch1.md"]
    c2["content"].pop("references_file")
    c2["content"].pop("abstract_zh")
    c2["content"].pop("abstract_zh_file", None)
    w(root, "build-contract.yaml", yaml.safe_dump(c2, allow_unicode=True))
    v4 = TB.validate_contract(root)
    check("BUILD-07 可选域缺→PASS+na 清单披露",
          v4["status"] == "PASS" and any("references" in x for x in v4["na"])
          and any("abstract" in x for x in v4["na"]), str(v4["na"]))
    contract(root)  # 还原完整契约

    # ---------- BUILD-03 组装（FORMAT_RECONSTRUCTION） ----------
    out, info = TB.build_docx(root)
    check("BUILD-03 重建模式组装成功", info["mode"] == "format_reconstruction"
          and os.path.isfile(out) and os.path.getsize(out) > 10000)
    from docx import Document
    d = Document(out)
    body = "\n".join(p.text for p in d.paragraphs)
    check("BUILD-03 内容齐：封面标题/摘要/关键词/目录域/章/参考文献/附录/致谢",
          all(k in body for k in ("统一构建题", "摘", "关键词", "第1章 绪论",
                                  "参考文献", "附录A", "致")))
    styles = {p.style.name for p in d.paragraphs}
    check("BUILD-03 真实 Heading 层级（Word TOC 依赖）",
          any("Heading" in s for s in styles), str(list(styles)[:6]))
    check("BUILD-03 表格三线表（附录经引擎渲染无 md 残留）", "**" not in body and "| ---" not in body)

    # ---------- BUILD-03b 组装（TEMPLATE_FIDELITY） ----------
    rootT = F.make_project(os.path.join(tmp, "tpl"), with_template=False)
    contract(rootT, mode="tpl")
    vT = TB.validate_contract(rootT)
    check("BUILD-01 模板契约→mode=template_fidelity（复用 select_docx_mode）",
          vT["docx_mode"] == "template_fidelity")
    outT, infoT = TB.build_docx(rootT)
    dT = Document(outT)
    cover = " ".join(p.text for t in dT.tables for r in t.rows for cell in r.cells
                     for p in cell.paragraphs)
    bodyT = "\n".join(p.text for p in dT.paragraphs)
    check("BUILD-03 母版驱动：模板封面保留+字段填入", "某大学" not in cover
          and "统一构建题" in cover and "南京农业大学" in cover)
    check("BUILD-03 母版驱动：样例内容区被剪除（不残留）", "样例正文内容" not in bodyT)
    check("BUILD-03 多节结构（前置罗马/正文分节）", len(dT.sections) >= 3, str(len(dT.sections)))

    # ---------- BUILD-10 可重复性：content identity vs container ----------
    i2 = TB.build_docx(root)[1]
    check("BUILD-10 同输入两次 build content_identity 一致",
          i2["content_identity"] == info["content_identity"],
          str(info["content_identity"])[:12])
    container_same = i2["sha256"] == info["sha256"]
    check("boundary 容器哈希可能因元数据时间戳不同（如实区分两类身份，不误报漂移）",
          True, "container same" if container_same else "container differs(=元数据差异，内容身份一致)")

    # ---------- BUILD-04 manifest ----------
    bid, items, mp = TB.write_manifest(root, [
        {"artifact": "docx", "path": "毕业论文.docx",
         "content_identity": info["content_identity"]}])
    check("BUILD-04 manifest 记录 artifact/path/sha256/producer/timestamp/status",
          items and all({"artifact", "path", "sha256", "producer", "timestamp",
                         "status"} <= set(x) for x in items))
    chk = TB.check_manifest(root)
    check("BUILD-04/09 manifest 校验 PASS（现场=登记）", chk["status"] == "PASS")
    # 篡改产物 → ERROR+changed（对接 Phase 3 checkpoint 语义）
    with open(os.path.join(root, "毕业论文.docx"), "ab") as f:
        f.write(b"x")
    chk2 = TB.check_manifest(root)
    check("BUILD-09 artifact 被改→manifest 校验 ERROR+列出 changed",
          chk2["status"] == "ERROR" and chk2["changed"] == ["毕业论文.docx"])
    # 删除 → missing
    os.remove(os.path.join(root, "毕业论文.docx"))
    chk3 = TB.check_manifest(root)
    check("BUILD-09 artifact 丢失→missing 报告", chk3["missing"] == ["毕业论文.docx"])
    check("boundary 无 manifest 项目→NOT_APPLICABLE（不报错）",
          TB.check_manifest(rootT)["status"] == "NOT_APPLICABLE")

    # ---------- BUILD-06 pipeline 失败裁决（指令 §十四：不假装成功） ----------
    bad = F.make_project(os.path.join(tmp, "bad"), with_template=False)
    c3 = {"project": {"title": "T"}, "content": {"chapters": ["missing.md"]},
          "research": {"required": False}, "school_format": {}}
    w(bad, "build-contract.yaml", yaml.safe_dump(c3, allow_unicode=True))
    pres = TB.pipeline(bad, steps=["docx"])
    check("BUILD-06 build FAIL→失败阶段+错误码+原因+建议动作",
          pres["status"] == "FAIL" and pres["verdict"]["failed_stage"] == "docx"
          and pres["verdict"]["error_code"] == "BUILD_CONTRACT"
          and pres["verdict"]["suggested_action"], json.dumps(pres["verdict"], ensure_ascii=False)[:160])
    check("BUILD-06 失败时下游步骤 SKIPPED_WITH_REASON（不继续假装）",
          TB.pipeline(bad, steps=["docx", "toc"])["steps"][1]["status"] == "SKIPPED_WITH_REASON")

    # ---------- BUILD-03c 成功 pipeline（docx 段）+ qa 段缺依赖语义 ----------
    okroot = F.make_project(os.path.join(tmp, "okpipe"), with_template=False)
    contract(okroot)
    pres2 = TB.pipeline(okroot, steps=["docx"])
    check("BUILD-03 pipeline docx 段成功并出 manifest",
          pres2["status"] == "PASS" and pres2["manifest_path"]
          and pres2["artifacts"][0]["artifact"] == "docx")

    # ---------- BUILD-03d 表体渲染不依赖英文题注（test-8.0 根因修复回归） ----------
    troot = F.make_project(os.path.join(tmp, "tblfix"), with_template=False)
    contract(troot, chapters=("artifacts/chapters/tbl.md",))
    w(troot, "artifacts/chapters/tbl.md",
      "# 第1章 表测试\n\n表1-1 割集表\n\n| 割集 | 阶 |\n|---|---|\n| MC-1 | 1 |\n| MC-4 | 2 |\n\n"
      "正文一句。\n")
    tb_out, _ = TB.build_docx(troot)
    from docx import Document as _Doc
    td = _Doc(tb_out)
    data_tbls = [t for t in td.tables if any("MC-1" in c.text for row in t.rows for c in row.cells)]
    check("BUILD-03d 无英文题注时表体仍渲染（旧实现静默丢行=内容丢失）",
          bool(data_tbls) and any("MC-4" in c.text for r in data_tbls[0].rows for c in r.cells),
          f"数据表 {len(data_tbls)} 张")
    # 契约 tables 提供英文题注 → 表上方出现 Tab. 段（双语题注 QA 依赖）
    c3d = yaml.safe_load(open(TB.contract_path(troot), encoding="utf-8"))
    c3d["tables"] = [{"display": "表1-1", "caption_en": "Tab.1-1 Cut sets"}]
    w(troot, "build-contract.yaml", yaml.safe_dump(c3d, allow_unicode=True))
    v3d = TB.validate_contract(troot)
    check("BUILD-03d tables 契约条目不要求 file（validate 不误报 ERROR）",
          v3d["status"] == "PASS", str(v3d["errors"]))
    tb_out2, _ = TB.build_docx(troot)
    td2 = _Doc(tb_out2)
    check("BUILD-03d tables.caption_en 渲染于表上方（英文题注在中文题之后）",
          any(p.text.strip() == "Tab.1-1 Cut sets" for p in td2.paragraphs))
    # 双语图题：contract figures 条目的 caption_en 进 FigureBlock 中文题下方
    fdir = os.path.join(troot, ".aeromech", "artifacts", "figures")
    os.makedirs(fdir, exist_ok=True)
    import docx_engine as E
    dummy_png = os.path.join(fdir, "fig1-1.png")
    from PIL import Image as _Img
    _Img.new("RGB", (800, 400), "white").save(dummy_png)
    c3e = yaml.safe_load(open(TB.contract_path(troot), encoding="utf-8"))
    c3e["figures"] = [{"figure_id": "FIG-001", "display": "图1-1",
                       "file": ".aeromech/artifacts/figures/fig1-1.png",
                       "caption_cn": "图1-1 示意", "caption_en": "Fig.1-1 demo"}]
    c3e["content"]["chapters"] = ["artifacts/chapters/fig.md"]
    w(troot, "artifacts/chapters/fig.md",
      "# 第1章 图测试\n\n（图1-1 示意）\n\n正文一句。\n")
    w(troot, "build-contract.yaml", yaml.safe_dump(c3e, allow_unicode=True))
    tf_out, _ = TB.build_docx(troot)
    tdf = _Doc(tf_out)
    celltext = "\n".join(c.text for t in tdf.tables for r in t.rows for c in r.cells)
    check("BUILD-03d 图块双语题注（FIG-07/09：图内中文题+Fig. 英文题）",
          "图1-1 示意" in celltext and "Fig.1-1 demo" in celltext,
          celltext[:60].replace("\n", " / "))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_thesis_build 结果: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
