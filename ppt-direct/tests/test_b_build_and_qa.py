# -*- coding: utf-8 -*-
"""Test B：构建 + QA（正例全过 / 负例逐项 FAIL / 校模提取 / md 输入源）

用法: python ppt-direct/tests/test_b_build_and_qa.py
退出码: 0=全过；1=有失败
"""
import json
import os
import shutil
import sys
import tempfile

import yaml

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_pptx
import ingest_source
import ppt_qa
import theme_extract

THEME = os.path.join(ROOT, "assets", "theme-default.yaml")
PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} | {detail}")


def write_deck(root, slides, tier="short"):
    deck = {"meta": {"title": "测试题目", "presenter": "张三",
                     "major": "飞行器维修工程技术", "page_tier": tier},
            "slides": slides}
    path = os.path.join(root, "deck.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(deck, f, allow_unicode=True)
    return path


def good_slides():
    return [
        {"layout": "cover", "notes": "开场"},
        {"layout": "toc", "notes": "介绍结构"},
        {"layout": "section", "no": 1, "title": "研究背景", "notes": "引入"},
        {"layout": "content", "title": "背景",
         "bullets": ["要点一", "要点二", [1, "二级要点"]], "notes": "讲 30 秒"},
        {"layout": "two_column", "title": "方法对比",
         "left": {"title": "FMEA", "bullets": ["正向枚举"]},
         "right": {"title": "FTA", "bullets": ["逆向追溯"]},
         "notes": "对比选型"},
        {"layout": "section", "no": 2, "title": "结果", "notes": "过渡"},
        {"layout": "content", "title": "结果",
         "bullets": ["发现一", "发现二"], "notes": "讲 1 分钟"},
        {"layout": "closing", "notes": "致谢"},
    ]


def build_and_qa(root, deck_path):
    pptx = os.path.join(root, "out.pptx")
    layout = os.path.join(root, "layout.json")
    build_pptx.build(deck_path, THEME, pptx, layout)
    qa_dir = os.path.join(root, "qa")
    code = ppt_qa.run_qa(pptx, layout, THEME, deck_path, qa_dir)
    report = open(os.path.join(qa_dir, "ppt-qa-report.md"),
                  encoding="utf-8").read()
    return code, report, pptx, layout


def main():
    tmp = tempfile.mkdtemp(prefix="ppd_build_")
    try:
        # --- 正例：全部 PASS ---
        d1 = os.path.join(tmp, "good")
        os.makedirs(d1)
        deck = write_deck(d1, good_slides())
        code, report, pptx, layout = build_and_qa(d1, deck)
        check("正例 QA 全过", code == 0, report)
        check("pptx 生成", os.path.getsize(pptx) > 5000)
        with open(layout, encoding="utf-8") as f:
            lj = json.load(f)
        check("layout sidecar 8 页", len(lj["pages"]) == 8)
        toc_body = next(s for s in lj["pages"][1]["shapes"]
                        if s.get("kind") == "body")
        check("toc 自动收集板块", toc_body["paras"] == 2,
              f"toc 段落数 {toc_body['paras']} != 2 个板块")

        # --- 负例：要点超限 + 占位符 + 缺备注 ---
        d2 = os.path.join(tmp, "bad")
        os.makedirs(d2)
        bad = good_slides()
        bad[3] = {"layout": "content", "title": "【待填】",
                  "bullets": [f"第{i}条要点内容" for i in range(9)],
                  "notes": ""}
        deck2 = write_deck(d2, bad)
        code, report, _, _ = build_and_qa(d2, deck2)
        check("负例 QA 退出码 1", code == 1)
        check("PPT-02 命中", "PPT-02: FAIL" in report)
        check("PPT-08 命中占位符", "PPT-08: FAIL" in report)
        check("PPT-10 命中缺备注", "PPT-10: FAIL" in report)

        # --- 负例：超长文本触发溢出估算 ---
        d3 = os.path.join(tmp, "overflow")
        os.makedirs(d3)
        ov = good_slides()
        ov[3] = {"layout": "content", "title": "溢出页",
                 "bullets": ["长" * 1000], "notes": "n"}
        code, report, _, _ = build_and_qa(d3, write_deck(d3, ov))
        check("PPT-04 命中溢出", "PPT-04: FAIL" in report, report)
        check("PPT-03 命中字数", "PPT-03: FAIL" in report)

        # --- 页数档位 ---
        d4 = os.path.join(tmp, "tier")
        os.makedirs(d4)
        code, report, _, _ = build_and_qa(
            d4, write_deck(d4, good_slides()[:5], tier="long"))
        check("PPT-01 命中页数不足", "PPT-01: FAIL" in report)

        # --- 校模提取（用正例 pptx 当模板） ---
        theme_out = os.path.join(tmp, "theme-school.yaml")
        info = theme_extract.extract(pptx)
        check("提取画幅 16:9", info["size"] == "16:9")
        check("提取到中文字体", bool(info["fonts"]["cjk"]))
        check("提取到主题色", "primary" in info["colors"])

        # --- md 输入源 ---
        md = os.path.join(tmp, "论文.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("# 绪论\n\n研究背景段落内容，超过十二个字的句子。\n\n"
                    "# 结论\n\n结论段落内容，也是超过十二个字的句子。\n")
        out_dir = os.path.join(tmp, "pptproj")
        argv = sys.argv
        sys.argv = ["ingest_source.py", "--md", md, "--out", out_dir]
        try:
            rc = ingest_source.main()
        finally:
            sys.argv = argv
        check("ingest 退出码 0", rc == 0)
        deck_draft = os.path.join(out_dir, ".pptdirect", "artifacts",
                                  "deck.yaml")
        with open(deck_draft, encoding="utf-8") as f:
            draft = yaml.safe_load(f)
        check("ingest 产出 deck 草稿",
              any(s["layout"] == "section" for s in draft["slides"]))
        check("ingest 保留占位符纪律",
              draft["meta"]["presenter"] == "【待填】")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n结果: {PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
