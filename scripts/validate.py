#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py — 口播分镜稿确定性校验

用法：
    python validate.py script.json
    python validate.py script.json --json out/report.json
    python validate.py --selftest

判据分五组，共 29 项：
    A 可渲染性（5）  B 视觉预算（9）  C 故事与留存（7）  D 去 AI 感（3）  R 渲染契约（5）

退出码：0 全过；1 有未通过项；2 输入不可用。

断言只增不改口径。要让检查变绿，改稿，不改这里。
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.normpath(os.path.join(HERE, "..", "tests"))

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
NON_WORD = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")
MD_CHARS = ["**", "＊", "`", "#", "<", ">", "~~"]

TYPES = ("statement", "bullets", "stat", "image", "title", "quote")
ENTERS = ("slide-from-bottom", "scale-up", "fade-up", "none")
SPRINGS = ("bouncy", "snappy", "smooth", "none")
BEATS = ("hook", "conflict", "progressive_breakdown", "midpoint_hook",
         "viewpoint", "cta")
DIRECTIONS = ("up", "down", "flat")

TURN_WORDS = ("但", "可是", "然而", "关键是", "更狠的是", "真正", "其实",
              "问题是", "反过来", "不算什么", "不止", "难得的是", "真正变的是")
SAVE_WORDS = ("用得上", "用得着", "收藏", "留着", "存下", "存起来", "回头翻")
DECOR_WORDS = ("spin", "rotate", "blink", "flash", "shake", "pulse")

CPS_MIN, CPS_MAX = 3.2, 8.0
SUB_LINE_MAX = 16
SUB_LINES_MAX = 2
HOOK_FRAMES = 90          # 3 秒
CORE_MIN_SEC, CORE_MAX_SEC = 10.0, 20.0
ASSUME_TOL = 0.15


def speak_len(text):
    """可念字数：汉字 + 英文单词。标点不计。"""
    return len(CJK.findall(text or "")) + len(LATIN_WORD.findall(text or ""))


def norm(text):
    return NON_WORD.sub("", text or "")


class Report(object):
    def __init__(self):
        self.findings = []

    def check(self, cid, ok, msg, fix=""):
        self.findings.append({"id": cid, "group": cid[0], "ok": bool(ok),
                              "msg": msg, "fix": fix})
        return bool(ok)

    def group_stat(self, group):
        items = [f for f in self.findings if f["group"] == group]
        return len([f for f in items if f["ok"]]), len(items)

    def fails(self):
        return [f for f in self.findings if not f["ok"]]


def load(path):
    with io.open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


# --------------------------------------------------------------- 主校验

def validate(doc, verbose=True):
    rep = Report()

    # ---------- 结构前置
    meta = doc.get("meta") or {}
    scenes = doc.get("scenes") or []
    transitions = doc.get("transitions") or []
    if not isinstance(scenes, list) or not scenes:
        raise SystemExit("[FAIL] scenes 为空，无法校验")
    fps = meta.get("fps")
    if not isinstance(fps, int) or fps <= 0:
        raise SystemExit("[FAIL] meta.fps 缺失或不是正整数")

    ids = [str(s.get("scene_id", "")) for s in scenes]
    durs = [int(s.get("durationInFrames") or 0) for s in scenes]
    tdur = {}
    dup = []
    for t in transitions:
        a = str(t.get("after_scene", ""))
        if a in tdur:
            dup.append(a)
        tdur[a] = int(t.get("durationInFrames") or 0)

    # ================= A 可渲染性 =================
    a_bad = []
    if dup:
        a_bad.append("同一场挂了多条转场: %s" % ",".join(sorted(set(dup))))
    for t in transitions:
        a = str(t.get("after_scene", ""))
        d = int(t.get("durationInFrames") or 0)
        if a not in ids:
            a_bad.append("after_scene 不存在: %s" % a)
            continue
        i = ids.index(a)
        if i == len(ids) - 1:
            a_bad.append("末场之后不能有转场: %s" % a)
        elif d < 2:
            a_bad.append("%s 的转场只有 %d 帧" % (a, d))
        elif d > min(durs[i], durs[i + 1]) / 2.0:
            a_bad.append("%s 转场 %d 帧超过相邻场景时长的一半" % (a, d))
    rep.check("A1", not a_bad,
              "转场合法（%d 条）" % len(transitions) if not a_bad else "；".join(a_bad),
              "转场时长不超过相邻场景的一半，末场后不挂转场，同一场只挂一条")

    total_decl = doc.get("totalCompositionFrames")
    total_calc = sum(durs) - sum(tdur.values())
    rep.check("A2", total_decl == total_calc,
              "净时长核算一致（%s 帧）" % total_calc if total_decl == total_calc
              else "总帧数对不上：声明 %s，实算 %d（Σ 场景 %d − Σ 转场 %d）"
                   % (total_decl, total_calc, sum(durs), sum(tdur.values())),
              "改成 Σ scene.duration − Σ transition.duration")

    start_bad = []
    cursor = 0
    for i, s in enumerate(scenes):
        got = int(s.get("startFrame") if s.get("startFrame") is not None else -1)
        if got != cursor:
            start_bad.append("%s 应为 %d 实为 %s" % (ids[i], cursor, got))
        cursor = got if got >= 0 else cursor
        cursor = cursor + durs[i] - tdur.get(ids[i], 0)
    rep.check("A3", not start_bad,
              "起帧递推正确（末帧 %d）" % total_calc if not start_bad
              else "起帧未按转场重叠递推: " + "；".join(start_bad[:3]),
              "startFrame[i] = startFrame[i-1] + duration[i-1] − transition(i-1)")

    s0 = scenes[0]
    a0 = s0.get("animation") or {}
    ef = int(a0.get("enterFrames") or 0)
    ok_a4 = (s0.get("first_frame_visible") is True and ef <= 18
             and str(a0.get("enter", "")) in ENTERS)
    rep.check("A4", ok_a4,
              "首帧可见（enter=%s，%d 帧内到位）" % (a0.get("enter"), ef) if ok_a4
              else "第 0 帧不是有效画面（first_frame_visible=%s，enterFrames=%s）"
                   % (s0.get("first_frame_visible"), ef),
              "首场 first_frame_visible 设 true，enterFrames 不超过 18 帧")

    last = scenes[-1]
    ok_a5 = int(last.get("durationInFrames") or 0) >= 60 and last.get("narrative_beat") == "cta"
    rep.check("A5", ok_a5,
              "收口停留 %d 帧" % int(last.get("durationInFrames") or 0) if ok_a5
              else "收口不足 60 帧或末场不是 cta",
              "末场 narrative_beat 设 cta，时长不低于 60 帧")

    # ================= B 视觉预算 =================
    bad_type = [i for i, s in zip(ids, scenes) if s.get("type") not in TYPES]
    rep.check("B1", not bad_type,
              "type 全在白名单内" if not bad_type else "type 越界: %s" % ",".join(bad_type),
              "只能是 " + "/".join(TYPES))

    bad_enter = []
    for i, s in zip(ids, scenes):
        e = (s.get("animation") or {}).get("enter")
        if e not in ENTERS:
            bad_enter.append("%s(%s)" % (i, e))
    rep.check("B2", not bad_enter,
              "animation.enter 全在白名单内" if not bad_enter
              else "enter 越界: %s" % ",".join(bad_enter),
              "只能是 " + "/".join(ENTERS))

    bad_spring = []
    for i, s in zip(ids, scenes):
        sp = (s.get("animation") or {}).get("spring")
        if sp not in SPRINGS:
            bad_spring.append("%s(%s)" % (i, sp))
    rep.check("B3", not bad_spring,
              "spring 全在白名单内" if not bad_spring
              else "spring 越界: %s" % ",".join(bad_spring),
              "只能是 " + "/".join(SPRINGS))

    bad_mb = []
    for i, s in zip(ids, scenes):
        mb = s.get("motion_budget")
        if not isinstance(mb, (int, float)) or mb < 0 or mb > 3:
            bad_mb.append("%s(%s)" % (i, mb))
    rep.check("B4", not bad_mb,
              "motion_budget 全在 0 到 3" if not bad_mb
              else "motion_budget 越界: %s" % ",".join(bad_mb),
              "每场填 0 到 3 的数字，主动运动元素数量")

    bouncy = [i for i, s in zip(ids, scenes)
              if (s.get("animation") or {}).get("spring") == "bouncy"]
    rep.check("B5", len(bouncy) <= 2,
              "bouncy 入场 %d 处" % len(bouncy) if len(bouncy) <= 2
              else "bouncy 用了 %d 处（上限 2）: %s" % (len(bouncy), ",".join(bouncy)),
              "只给钩子与观点回扣两处峰值")

    down = [s for s in scenes if (s.get("emotion") or {}).get("direction") == "down"]
    d_bad = [str(s.get("scene_id")) for s in down
             if (s.get("animation") or {}).get("spring") == "bouncy"]
    rep.check("B6", not d_bad,
              "情绪回落处无 bouncy（%d 场）" % len(down) if not d_bad
              else "down 场景用了 bouncy: %s" % ",".join(d_bad),
              "回落处改 smooth 或 none")

    d_mb = [str(s.get("scene_id")) for s in down
            if float(s.get("motion_budget") or 0) > 1]
    rep.check("B7", not d_mb,
              "回落处运动预算收紧" if not d_mb
              else "down 场景 motion_budget 超过 1: %s" % ",".join(d_mb),
              "回落处 motion_budget 设 1 或 0，留白让口播承担信息")

    mid_idx = [i for i, s in enumerate(scenes)
               if s.get("narrative_beat") == "midpoint_hook"]
    b8_bad = []
    for i in mid_idx:
        nb = [float(scenes[j].get("motion_budget") or 0)
              for j in (i - 1, i + 1) if 0 <= j < len(scenes)]
        if nb:
            limit = 0.5 * min(nb)
            if float(scenes[i].get("motion_budget") or 0) > limit:
                b8_bad.append("%s 预算 %s 超过邻场一半（%.1f）"
                              % (ids[i], scenes[i].get("motion_budget"), limit))
    rep.check("B8", not b8_bad,
              "微型钩子动效克制" if not b8_bad else "；".join(b8_bad),
              "钩子靠文案留人，motion_budget 压到相邻功能场的一半以内")

    active = sum(d for i, d in enumerate(durs)
                 if float(scenes[i].get("motion_budget") or 0) >= 2)
    ratio = active / float(total_calc or 1)
    rep.check("B9", ratio <= 0.6,
              "主动运动占比 %.0f%%" % (ratio * 100) if ratio <= 0.6
              else "主动运动占比 %.0f%%，超过 60%%" % (ratio * 100),
              "把中低强度场景的 motion_budget 降到 1 以下")

    # ================= C 故事与留存 =================
    viewpoint = str(meta.get("viewpoint") or "").strip()
    vnorm = norm(viewpoint)
    hit = bool(vnorm) and any(vnorm in norm(s.get("voiceover_text", "")) for s in scenes)
    rep.check("C1", hit,
              "观点句原句已复述" if hit else "观点句没有原句出现在稿中（或 meta.viewpoint 为空）",
              "在观点回扣段原句复述，一个字都不要改")

    bd = [s for s in scenes if s.get("narrative_beat") == "progressive_breakdown"]
    c2_bad = []
    for s in bd[1:]:
        txt = str(s.get("voiceover_text", ""))
        if not any(w in txt for w in TURN_WORDS):
            c2_bad.append(str(s.get("scene_id")))
    rep.check("C2", not c2_bad,
              "功能点之间是递进（%d 个功能场）" % len(bd) if not c2_bad
              else "这些功能场没有转折词，还在并列: %s" % ",".join(c2_bad),
              "插入但问题是/关键是/更狠的是/真正 这类转折")

    core_lo, core_hi = CORE_MIN_SEC * fps, CORE_MAX_SEC * fps
    c3_ok = False
    for i in mid_idx:
        st = int(scenes[i].get("startFrame") or 0)
        if core_lo <= st <= core_hi:
            c3_ok = True
    rep.check("C3", c3_ok,
              "微型钩子落在 %.0f 到 %.0f 秒" % (CORE_MIN_SEC, CORE_MAX_SEC) if c3_ok
              else "10 到 20 秒区间内没有 midpoint_hook 场景",
              "调整 startFrame，让钩子落在 %d 到 %d 帧" % (core_lo, core_hi))

    has_down = bool(down)
    rep.check("C4", has_down,
              "情绪曲线有一次回落" if has_down else "全片没有 direction=down 的场景，一路在喊",
              "在冲突兑现段末尾设一场 direction=down，让观众听清")

    vp_scenes = [s for s in scenes if s.get("narrative_beat") == "viewpoint"]
    c5_ok = any(any(w in str(s.get("voiceover_text", "")) for w in SAVE_WORDS)
                for s in vp_scenes)
    rep.check("C5", c5_ok,
              "结尾给了收藏理由" if c5_ok else "观点回扣段没有收藏暗示，等于放弃收藏这一档",
              "补半句“这条你以后会用得上”这类可截图的收藏理由")

    s_first = scenes[0]
    ok_first = (s_first.get("narrative_beat") == "hook"
                and int(s_first.get("startFrame") or 0) == 0
                and int(s_first.get("durationInFrames") or 0) <= HOOK_FRAMES)
    ok_last = (last.get("narrative_beat") == "cta"
               and int(last.get("durationInFrames") or 0) >= 60)
    parts = []
    if not ok_first:
        parts.append("首屏不是 3 秒内结束的 hook")
    if not c3_ok:
        parts.append("核心停留段缺钩子")
    if not ok_last:
        parts.append("收口不是 cta 或不足 60 帧")
    rep.check("C6", not parts,
              "三段完播对齐（首屏/核心/收口）" if not parts else "；".join(parts),
              "三段各自补设计，见 references/story-framework.md")

    c7_bad = [str(scenes[i].get("scene_id")) for i in mid_idx
              if speak_len(scenes[i].get("voiceover_text")) > 15]
    rep.check("C7", not c7_bad,
              "微型钩子都在 15 字内" if not c7_bad
              else "微型钩子超过 15 字: %s" % ",".join(c7_bad),
              "压到 15 字以内，它只负责让人多留 3 秒")

    # ================= D 去 AI 感 =================
    springs = [(s.get("animation") or {}).get("spring") for s in scenes]
    run, prev, longest = 0, None, 0
    for sp in springs:
        if sp == prev:
            run += 1
        else:
            run, prev = 1, sp
        longest = max(longest, run)
    rep.check("D1", longest <= 2,
              "spring 无连续复读" if longest <= 2
              else "连续 %d 场用了同一种 spring，节奏发木" % longest,
              "相邻场景换 spring 或改 none")

    tw = [i for i, s in zip(ids, scenes) if s.get("typewriter") is True]
    rep.check("D2", len(tw) <= 2,
              "打字机 %d 处" % len(tw) if len(tw) <= 2
              else "打字机用了 %d 处（上限 2）: %s" % (len(tw), ",".join(tw)),
              "只留关键句，其余用整段入场")

    deco = []
    for i, s in zip(ids, scenes):
        blob = json.dumps(s.get("visual") or {}, ensure_ascii=False).lower()
        for w in DECOR_WORDS:
            if w in blob:
                deco.append("%s(%s)" % (i, w))
    rep.check("D3", not deco,
              "无装饰性动画" if not deco else "视觉里出现装饰性动画: %s" % ",".join(deco),
              "删掉旋转、闪烁、抖动这类纯装饰")

    # ================= R 渲染契约 =================
    w, h = meta.get("width"), meta.get("height")
    r1_ok = fps in (24, 25, 30, 60) and isinstance(w, int) and isinstance(h, int)
    rep.check("R1", r1_ok,
              "时基 %dfps %sx%s" % (fps, w, h) if r1_ok
              else "fps 或画面尺寸不合规: %s / %sx%s" % (fps, w, h),
              "fps 取 24/25/30/60，尺寸写进 meta，组件内不硬编码")

    md_bad = []
    for i, s in zip(ids, scenes):
        t = str(s.get("voiceover_text", ""))
        if any(c in t for c in MD_CHARS):
            md_bad.append(i)
    rep.check("R2", not md_bad,
              "TTS 文本干净" if not md_bad
              else "voiceover_text 混入 markdown，TTS 会念出来: %s" % ",".join(md_bad),
              "强调词放进 emphasis_words，voiceover_text 只留纯文本")

    cps_bad = []
    for i, s, d in zip(ids, scenes, durs):
        sec = d / float(fps)
        cps = speak_len(s.get("voiceover_text")) / sec if sec else 0
        if not (CPS_MIN <= cps <= CPS_MAX):
            cps_bad.append("%s %.1f 字/秒" % (i, cps))
    rep.check("R3", not cps_bad,
              "语速全在 %.1f 到 %.1f 字/秒" % (CPS_MIN, CPS_MAX) if not cps_bad
              else "语速越界: " + "；".join(cps_bad),
              "改口播字数或改 durationInFrames，两者必调一个")

    sub_bad = []
    for i, s in zip(ids, scenes):
        lines = s.get("subtitle_lines")
        if not isinstance(lines, list) or not lines:
            sub_bad.append("%s 缺 subtitle_lines" % i)
            continue
        if len(lines) > SUB_LINES_MAX:
            sub_bad.append("%s 字幕 %d 行" % (i, len(lines)))
        for ln in lines:
            if speak_len(ln) > SUB_LINE_MAX:
                sub_bad.append("%s 某行 %d 字" % (i, speak_len(ln)))
    rep.check("R4", not sub_bad,
              "字幕在安全区内" if not sub_bad else "；".join(sub_bad[:3]),
              "每行不超过 16 字、最多 2 行，避开抖音上下遮挡区")

    total_speak = sum(speak_len(s.get("voiceover_text")) for s in scenes)
    est = total_speak / 5.8
    real = total_calc / float(fps)
    target = float(meta.get("target_seconds") or real)
    dev = abs(real - target) / target if target else 0
    rep.check("R5", dev <= ASSUME_TOL,
              "时长偏差 %.1f%%（口播 %d 字，实 %.1fs，目标 %.1fs）"
              % (dev * 100, total_speak, real, target) if dev <= ASSUME_TOL
              else "成片 %.1fs 与目标 %.1fs 差 %.0f%%，稿子念不完或会冷场（预估口播 %.1fs）"
                   % (real, target, dev * 100, est),
              "改总帧数或改字数，偏差控制在 15% 以内")

    if verbose:
        print_report(rep, doc)
    return rep


def print_report(rep, doc=None):
    titles = {"A": "A 可渲染性", "B": "B 视觉预算", "C": "C 故事与留存",
              "D": "D 去 AI 感", "R": "R 渲染契约"}
    print("")
    for g in ("A", "B", "C", "D", "R"):
        ok, n = rep.group_stat(g)
        mark = "PASS" if ok == n else "FAIL"
        print("[%s] %s  %d/%d" % (mark, titles[g], ok, n))
    fails = rep.fails()
    if fails:
        print("")
        print("未通过明细：")
        for f in fails:
            print("  [%s] %s" % (f["id"], f["msg"]))
            if f["fix"]:
                print("        改法：%s" % f["fix"])
    total = len(rep.findings)
    passed = total - len(fails)
    print("")
    print("结论：%s  %d/%d 项通过" % ("PASS" if not fails else "FAIL", passed, total))
    if not fails:
        print("可以进样片：python scripts/sample.py <script.json> --out-dir samples")


def selftest():
    good = os.path.join(FIXTURES, "good-script.json")
    bad = os.path.join(FIXTURES, "bad-script.json")
    problems = []
    if not os.path.isfile(good) or not os.path.isfile(bad):
        print("[FAIL] 缺 fixture：%s" % FIXTURES)
        return 2
    rg = validate(load(good), verbose=False)
    if rg.fails():
        problems.append("good-script.json 应全过，实有 %d 项未过：%s"
                        % (len(rg.fails()), ",".join(f["id"] for f in rg.fails())))
    rb = validate(load(bad), verbose=False)
    must = {"C3", "C2", "A2"}
    got = set(f["id"] for f in rb.fails())
    if len(got) < 5:
        problems.append("bad-script.json 只命中 %d 项，应至少 5 项" % len(got))
    miss = must - got
    if miss:
        problems.append("bad-script.json 未命中必报项：%s" % ",".join(sorted(miss)))
    print("")
    print("自检：good-script.json %s，bad-script.json 命中 %d 项（%s）"
          % ("全过" if not rg.fails() else "未全过", len(got), ",".join(sorted(got))))
    if problems:
        for p in problems:
            print("  [FAIL] " + p)
        return 1
    print("自检结论：PASS（2/2 用例）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="口播分镜稿确定性校验")
    ap.add_argument("script", nargs="?", help="script.json 路径")
    ap.add_argument("--json", dest="json_out", help="把结果写成 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出结论行")
    ap.add_argument("--selftest", action="store_true", help="跑内置正反例")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.script:
        ap.print_help()
        return 2
    if not os.path.isfile(args.script):
        sys.stderr.write("[FAIL] 文件不存在: %s\n" % args.script)
        return 2
    try:
        doc = load(args.script)
    except ValueError as exc:
        sys.stderr.write("[FAIL] JSON 解析失败: %s\n" % exc)
        return 2

    rep = validate(doc, verbose=not args.quiet)
    if args.quiet:
        print("%s %d/%d" % ("PASS" if not rep.fails() else "FAIL",
                            len(rep.findings) - len(rep.fails()), len(rep.findings)))
    if args.json_out:
        out = os.path.dirname(os.path.abspath(args.json_out))
        if out and not os.path.isdir(out):
            os.makedirs(out)
        with io.open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({
                "pass": not rep.fails(),
                "passed": len(rep.findings) - len(rep.fails()),
                "total": len(rep.findings),
                "findings": rep.findings,
            }, ensure_ascii=False, indent=2) + "\n")
    return 0 if not rep.fails() else 1


if __name__ == "__main__":
    sys.exit(main())
