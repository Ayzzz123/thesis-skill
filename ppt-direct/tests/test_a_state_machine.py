# -*- coding: utf-8 -*-
"""Test A：状态机（合法边/门禁/回退/override/里程碑/返程/备份轮换）

用法: python ppt-direct/tests/test_a_state_machine.py
退出码: 0=全过；1=有失败
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import state_util as su

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} | {detail}")


def expect_raise(name, fn, needle=""):
    global PASS, FAIL
    try:
        fn()
    except Exception as e:
        ok = needle in str(e)
        check(name, ok, f"异常信息不含 {needle!r}: {e}")
        return
    check(name, False, "未抛异常")


def main():
    root = tempfile.mkdtemp(prefix="ppd_state_")
    try:
        st = su.init(root)
        check("init 落在 S1", st["stage"]["current"] == "S1")
        check("init 记首条 history",
              st["stage"]["history"][0]["reason"] == "项目初始化")

        # 门禁：title/input_source 缺失 → S1→S2 拒绝
        expect_raise("S1→S2 门禁拒绝", lambda: su.transition(root, "S2", "x"),
                     "门禁未通过")
        st = su.load(root)
        st["project"]["title"] = "测试题目"
        st["project"]["input_source"] = "manual"
        su.save(root, st)
        st = su.transition(root, "S2", "需求已定")
        check("S1→S2 放行", st["stage"]["current"] == "S2")

        # 非法边
        expect_raise("S2→S5 非法边", lambda: su.transition(root, "S5", "x"),
                     "不在允许边")

        # S2→S3 需要 outline 落盘
        expect_raise("S2→S3 缺 outline", lambda: su.transition(root, "S3", "x"),
                     "outline.file")
        outline = os.path.join(root, ".pptdirect", "artifacts", "outline.yaml")
        os.makedirs(os.path.dirname(outline), exist_ok=True)
        open(outline, "w", encoding="utf-8").write("sections: [a]\n")
        st = su.load(root)
        st["outline"]["file"] = ".pptdirect/artifacts/outline.yaml"
        su.save(root, st)
        su.transition(root, "S3", "大纲定稿")
        check("S2→S3 放行", su.load(root)["stage"]["current"] == "S3")

        # 回退必须带触发源
        expect_raise("无理由回退拒绝",
                     lambda: su.transition(root, "S2", "", type_="revert"),
                     "触发源")
        st = su.transition(root, "S2", "预算失衡", type_="revert",
                           issue_id="ISS-001")
        check("S3→S2 回退", st["stage"]["current"] == "S2")
        d = os.path.join(root, ".pptdirect")
        check("回退产生备份", any(f.startswith("state.yaml.bak-revert-")
                                  for f in os.listdir(d)))

        # 返程：S2→S3 是 revert 逆边 → 合法
        st = su.transition(root, "S3", "问题修复返程")
        check("返程 S2→S3 合法", st["stage"]["current"] == "S3")

        # 里程碑
        st = su.transition(root, "S3", "deck 定稿")
        check("from==to 记 milestone",
              st["stage"]["history"][-1]["type"] == "milestone")

        # override：强行 S3→S6（非法边）→ 放行 + open_issue
        st = su.transition(root, "S6", "用户坚持", override=True)
        check("override 放行", st["stage"]["current"] == "S6")
        oi = st["stage"]["open_issues"]
        check("override 挂 open_issue",
              len(oi) == 1 and oi[0]["severity"] == "高")
        check("override history 一致",
              st["stage"]["history"][-1]["type"] == "override"
              and st["stage"]["history"][-1]["override"] is True)

        # S6→S7 门禁：有未关闭高严重问题 → 拒绝
        expect_raise("S6→S7 被问题阻塞",
                     lambda: su.transition(root, "S7", "x"), "未关闭")

        # status 摘要
        summary = su.status_summary(root)
        check("status 四行摘要", "【恢复】" in summary and "【未关闭问题】" in summary)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print(f"\n结果: {PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
