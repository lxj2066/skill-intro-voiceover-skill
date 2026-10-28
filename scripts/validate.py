#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py — 引流视频 production.json 确定性校验（双时间线版）

用法：
    python validate.py production.json
    python validate.py production.json --json out/report.json
    python validate.py --selftest

判据九组，共 46 项：
    A 可渲染(6)  B 视觉预算(8)  C 故事留存(7)  D 事实(3)  E 去AI感(3)
    F 数字人(4)  G 口播纯净(4)  H 时间线对齐(6)  I 视觉一致(5)

F 组只在 meta.has_avatar = true 时计分，否则整组跳过（不计入分母）。

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
NUM_RE = re.compile(r"\d|倍|百分之|[一二三四五六七八九十百千万亿]{2,}")
ROLE_WORDS = ("主导", "负责", "参与", "牵头", "带队", "配合")
EXTREME = ("最好", "最强", "第一人", "唯一", "绝对", "百分百", "100%", "保证", "必定")
FORBIDDEN_CHARS = ["（", "）", "(", ")", "**", "＊", "[", "]", "`", "#", "<", ">"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
TURN_WORDS = ("但", "可是", "然而", "关键是", "更狠的是", "真正", "其实",
              "问题是", "反过来", "不算什么", "不止", "难得的是")
SAVE_WORDS = ("用得上", "用得着", "收藏", "留着", "存下", "存起来", "回头翻")
COOP_WORDS = ("我能提供", "我在找", "适合谁", "可以找我", "需要的人")

TYPES = ("statement", "bullets", "stat", "image", "title", "quote")
ENTERS = ("slide-from-bottom", "scale-up", "fade-up", "none")
SPRINGS = ("playful", "corporate", "bubble", "snappy", "smooth", "none")
BEATS = ("hook", "conflict", "progressive_breakdown", "midpoint_hook",
         "viewpoint", "persona", "cooperation", "cta")
DIRECTIONS = ("up", "down", "flat")
ROLES = ("evidence", "narrative")
LAYERS = ("subject", "decoration", "background")
ANCHORS = ("scene_enter", "on_emphasis", "before_scene_end",
           "relative_offset", "voiceover_gap")
EFFECTS = ("scale-up", "slide-in", "fade-up", "fade", "none", "push-in", "typewriter")
DECOR_OK = ("fade", "slide-in", "none")
AVATAR_MODES = ("full", "side_window", "hidden")
AVATAR_DIRS = ("direct", "presenting", "listening")

EFFECT_WEIGHT = {"scale-up": 3.0, "push-in": 2.5, "slide-in": 2.0,
                 "fade-up": 1.0, "typewriter": 1.0, "fade": 0.5, "none": 0.0}

CPS_MIN, CPS_MAX = 3.0, 5.0
CORE_LO, CORE_HI = 300, 600
HOOK_END = 90


def speak_len(text):
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

    def skip(self, group, why):
        self.findings.append({"id": group + "0", "group": group, "ok": True,
                              "msg": why, "fix": "", "skip": True})

    def group_stat(self, group):
        items = [f for f in self.findings if f["group"] == group and not f.get("skip")]
        return len([f for f in items if f["ok"]]), len(items)

    def fails(self):
        return [f for f in self.findings if not f["ok"]]


def load(path):
    with io.open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


# ------------------------------------------------------------ 取值助手

def scene_index(scenes):
    return {str(s.get("scene_id")): i for i, s in enumerate(scenes)}


def motions_of(motions, sid, layer=None):
    out = [m for m in motions if str((m.get("anchor") or {}).get("scene_id")) == sid]
    if layer:
        out = [m for m in out if m.get("layer") == layer]
    return out


def motion_frame(m, scenes, idx, fps):
    """估算动效落位帧（绝对帧）。锚点无法解析时返回 None。"""
    a = m.get("anchor") or {}
    sid = str(a.get("scene_id"))
    if sid not in idx:
        return None
    s = scenes[idx[sid]]
    st, dur = int(s.get("startFrame") or 0), int(s.get("durationInFrames") or 0)
    t = a.get("type")
    if t == "scene_enter":
        return st
    if t == "relative_offset":
        return st + int(a.get("offsetFrames") or 0)
    if t == "before_scene_end":
        return st + dur - int(a.get("beforeFrames") or 0)
    if t == "on_emphasis":
        words = [str(w) for w in (s.get("emphasis_words") or [])]
        pos = [int(p) for p in (s.get("emphasis_positions") or [])]
        w = str(a.get("emphasis_word") or "")
        if w in words and len(pos) == len(words):
            return st + pos[words.index(w)]
        return None
    if t == "voiceover_gap":
        return st + int(a.get("offsetFrames") or 0)
    return None


def scene_amplitude(motions, sid):
    tot = 0.0
    for m in motions_of(motions, sid):
        w = EFFECT_WEIGHT.get(str(m.get("effect")), 1.0)
        d = float((m.get("params") or {}).get("durationFrames") or 0)
        tot += w * d
    return tot


def platform_spec(platform):
    table = {
        "douyin": {"ratio": "9:16", "size": (1080, 1920),
                   "safe": {"top": 100, "bottom": 200, "left": 60, "right": 60}},
        "xiaohongshu": {"ratio": "3:4", "size": (1080, 1440),
                        "safe": {"top": 100, "bottom": 120, "left": 60, "right": 60}},
        "shipinhao": {"ratio": "9:16", "size": (1080, 1920),
                      "safe": {"top": 100, "bottom": 200, "left": 60, "right": 60}},
    }
    return table.get(platform, {})


# ------------------------------------------------------------ 主校验

def validate(doc, verbose=True):
    rep = Report()
    meta = doc.get("meta") or {}
    scenes = doc.get("scriptTimeline") or []
    motions = doc.get("motionTimeline") or []
    avatars = doc.get("avatarTimeline") or []
    trans = doc.get("transitions") or []

    for key in ("scriptTimeline", "motionTimeline", "avatarTimeline", "transitions"):
        if key not in doc:
            raise SystemExit("[FAIL] 缺时间线字段：%s（即使为空也要写空数组）" % key)
    if not scenes:
        raise SystemExit("[FAIL] scriptTimeline 为空，无法校验")

    fps = meta.get("fps")
    if not isinstance(fps, int) or fps <= 0:
        raise SystemExit("[FAIL] meta.fps 缺失或不是正整数")

    ids = [str(s.get("scene_id", "")) for s in scenes]
    durs = [int(s.get("durationInFrames") or 0) for s in scenes]
    starts = [int(s.get("startFrame") or 0) for s in scenes]
    idx = scene_index(scenes)
    tdur = {}
    dup = []
    for t in trans:
        a = str(t.get("afterScene", ""))
        if a in tdur:
            dup.append(a)
        tdur[a] = int(t.get("durationInFrames") or 0)
    total_decl = meta.get("totalCompositionFrames")
    total_calc = sum(durs) - sum(tdur.values())

    # ================== A 可渲染性 ==================
    a1 = []
    for t in trans:
        a = str(t.get("afterScene", ""))
        d = int(t.get("durationInFrames") or 0)
        if a not in ids:
            a1.append("afterScene 不存在: %s" % a)
            continue
        i = ids.index(a)
        if i == len(ids) - 1:
            a1.append("末场之后不能有转场: %s" % a)
        elif d < 2:
            a1.append("%s 转场只有 %d 帧" % (a, d))
        elif d > min(durs[i], durs[i + 1]) / 2.0:
            a1.append("%s 转场 %d 帧超过相邻场景一半（%d）"
                      % (a, d, int(min(durs[i], durs[i + 1]) / 2)))
    rep.check("A1", not a1,
              "转场 %d 条，均在相邻场景一半以内" % len(trans) if not a1 else "；".join(a1),
              "TransitionSeries 要求转场不超过相邻 sequence 的一半")

    rep.check("A2", total_decl == total_calc,
              "净时长 %d 帧" % total_calc if total_decl == total_calc
              else "净时长对不上：meta 写 %s，实算 %d（Σ场景 %d − Σ转场 %d）"
                   % (total_decl, total_calc, sum(durs), sum(tdur.values())),
              "meta.totalCompositionFrames = Σ scriptTimeline − Σ transitions")

    s0 = scenes[0]
    ok_a3 = (s0.get("enter") not in (None, "", "none")
             and int(s0.get("enterFrames") or 0) >= 12)
    rep.check("A3", ok_a3,
              "首场 enter=%s，%s 帧到位" % (s0.get("enter"), s0.get("enterFrames")) if ok_a3
              else "首场 enter 为 none 或 enterFrames 不足 12，第一页没有视觉张力",
              "钩子场景 enter 用 slide-from-bottom 或 scale-up，enterFrames ≥12")

    last = scenes[-1]
    ok_a4 = (int(last.get("durationInFrames") or 0) >= 60
             and last.get("spring") != "playful")
    rep.check("A4", ok_a4,
              "收口 %d 帧，spring=%s"
              % (int(last.get("durationInFrames") or 0), last.get("spring")) if ok_a4
              else "末场不足 60 帧，或收口仍用 playful spring（会抖）",
              "末场 ≥60 帧，spring 改 corporate 或 smooth")

    rep.check("A5", not dup,
              "转场无重复指向" if not dup
              else "同一场挂了多条转场: %s" % ",".join(sorted(set(dup))),
              "一场只挂一条，末场不挂")

    a6 = []
    cursor = 0
    for i, s in enumerate(scenes):
        got = int(s.get("startFrame") if s.get("startFrame") is not None else -1)
        if got != cursor:
            a6.append("%s 应为 %d 实为 %s" % (ids[i], cursor, got))
        cursor = (got if got >= 0 else cursor) + durs[i] - tdur.get(ids[i], 0)
    rep.check("A6", not a6,
              "起帧递推正确（末帧 %d）" % total_calc if not a6
              else "起帧未按转场重叠递推: " + "；".join(a6[:3]),
              "startFrame[i] = startFrame[i-1] + duration[i-1] − transition(i-1)")

    # ================== B 视觉预算 ==================
    heavy = sum(d for i, d in enumerate(durs) if len(motions_of(motions, ids[i])) >= 2)
    ratio = heavy / float(total_calc or 1)
    rep.check("B1", ratio <= 0.6,
              "主动运动场景占 %.0f%% 时长" % (ratio * 100) if ratio <= 0.6
              else "主动运动场景占 %.0f%% 时长，超过 60%%" % (ratio * 100),
              "合并中段动效，让高强度场景只占一半时长")

    b2 = [i for i in ids if len(motions_of(motions, i, "subject")) > 1]
    rep.check("B2", not b2,
              "每场至多一个主运动" if not b2 else "主运动超过一个: %s" % ",".join(b2),
              "一个场景只留一个 subject 动效，其余降级为 decoration")

    springs = [s.get("spring") for s in scenes]
    run, prev, longest = 0, None, 0
    for sp in springs:
        if sp == prev:
            run += 1
        else:
            run, prev = 1, sp
        longest = max(longest, run)
    rep.check("B3", longest <= 2,
              "spring 无连续三场重复" if longest <= 2
              else "连续 %d 场用同一种 spring，节奏发木" % longest,
              "相邻场景换 spring 或改 none")

    b4 = []
    for i, s, d in zip(ids, scenes, durs):
        sec = d / float(fps)
        cps = speak_len(s.get("voiceover_pure")) / sec if sec else 0
        if cps > CPS_MAX:
            b4.append("%s %.1f 字/秒" % (i, cps))
    rep.check("B4", not b4,
              "文字密度均 ≤ %.1f 字/秒" % CPS_MAX if not b4
              else "文字密度过高: " + "；".join(b4),
              "删字或加时长，别让字幕追不上眼睛")

    b5 = [str(m.get("motion_id")) for m in motions
          if m.get("layer") == "decoration" and m.get("effect") not in DECOR_OK]
    rep.check("B5", not b5,
              "装饰层只做淡入滑入" if not b5 else "装饰层出现强动效: %s" % ",".join(b5),
              "装饰层只允许 fade / slide-in / none")

    down_ids = [i for i, s in zip(ids, scenes)
                if (s.get("emotion") or {}).get("direction") == "down"]
    b6 = []
    for i in down_ids:
        if len(motions_of(motions, i)) > 1:
            b6.append("%s 有 %d 个动效" % (i, len(motions_of(motions, i))))
        if motions_of(motions, i, "background"):
            b6.append("%s 有背景运动" % i)
    rep.check("B6", not b6,
              "回落场景克制（%d 场）" % len(down_ids) if not b6 else "；".join(b6),
              "down 场景只留一个动效，不要背景运动")

    mid_idx = [i for i, s in enumerate(scenes) if s.get("narrative_beat") == "midpoint_hook"]
    b7 = []
    for i in mid_idx:
        nb = [scene_amplitude(motions, ids[j]) for j in (i - 1, i + 1)
              if 0 <= j < len(scenes)]
        if nb:
            limit = 0.5 * min(nb)
            amp = scene_amplitude(motions, ids[i])
            if amp > limit:
                b7.append("%s 幅度 %.1f 超过邻场一半 %.1f" % (ids[i], amp, limit))
    rep.check("B7", not b7,
              "微型钩子动效幅度克制" if not b7 else "；".join(b7),
              "钩子靠文案留人，动效幅度压到相邻功能场的一半以内")

    avg = total_calc / float(fps) / max(1, len(scenes))
    # 数字人出镜时人物本身就是画面主体，长镜成立；纯演示内容按 2 到 3 秒切
    cap = 6.5 if meta.get("content_type") == "personal_intro" else 4.5
    rep.check("B8", 1.5 <= avg <= cap,
              "镜头平均停留 %.1f 秒" % avg if 1.5 <= avg <= cap
              else "镜头平均停留 %.1f 秒，超出 1.5 到 %.1f 的合理带" % (avg, cap),
              "拆场景或合并场景，让单镜停留落在 2 到 3 秒附近")

    # ================== C 故事与留存 ==================
    vp = str(meta.get("viewpoint") or "").strip()
    hit = bool(norm(vp)) and any(norm(vp) in norm(s.get("voiceover_pure")) for s in scenes)
    rep.check("C1", hit,
              "观点句/人设句原句已出现" if hit
              else "观点句或人设句没有原句出现（或 meta.viewpoint 为空）",
              "在观点回扣或人设回扣段原句复述，一个字不改")

    bd = [s for s in scenes if s.get("narrative_beat") == "progressive_breakdown"]
    # 按 feature_index 分组：一个功能点可能跨多场，转折只需出现在新功能点的首场
    groups, seen = [], set()
    for s in bd:
        f = s.get("feature_index")
        key = ("f", f) if f is not None else ("s", s.get("scene_id"))
        if f is not None and f in seen:
            continue
        if f is not None:
            seen.add(f)
        groups.append(s)
    c2 = [str(s.get("scene_id")) for s in groups[1:]
          if not any(w in str(s.get("voiceover_pure")) for w in TURN_WORDS)]
    rep.check("C2", not c2,
              "功能点是递进（%d 个功能点 / %d 场拆解）" % (len(groups), len(bd)) if not c2
              else "这些功能点没有转折词，还在并列: %s" % ",".join(c2),
              "每个新功能点的首场插入但问题是/关键是/更狠的是/真正 这类转折")

    c3 = any(CORE_LO <= starts[i] <= CORE_HI for i in mid_idx)
    rep.check("C3", c3,
              "微型钩子落在 10 到 20 秒" if c3 else "300 到 600 帧内没有 midpoint_hook",
              "调整 startFrame，让钩子落在 %d 到 %d 帧" % (CORE_LO, CORE_HI))

    rep.check("C4", bool(down_ids),
              "情绪曲线有一次回落" if down_ids else "全片没有 direction=down，一路在喊",
              "在冲突或背景段末尾设一场 down")

    vp_scenes = [s for s in scenes if s.get("narrative_beat") in ("viewpoint", "persona")]
    c5 = any(any(w in str(s.get("voiceover_pure")) for w in SAVE_WORDS) for s in vp_scenes)
    if meta.get("content_type") == "personal_intro":
        coop = [s for s in scenes if s.get("narrative_beat") == "cooperation"]
        c5 = c5 and bool(coop) and any(
            sum(1 for w in COOP_WORDS if w in str(s.get("voiceover_pure"))) >= 2
            for s in coop)
    rep.check("C5", c5,
              "结尾有收藏理由与合作接口" if c5 else "回扣段缺收藏暗示，或合作接口不全",
              "补「这条你以后用得上」；个人介绍另加我能提供/我在找/适合谁")

    ok_first = (scenes[0].get("narrative_beat") == "hook" and starts[0] == 0
                and durs[0] <= HOOK_END)
    ok_last = (last.get("narrative_beat") == "cta"
               and int(last.get("durationInFrames") or 0) >= 60)
    parts = []
    if not ok_first:
        parts.append("首屏不是 3 秒内的 hook")
    if not c3:
        parts.append("核心停留段缺钩子")
    if not ok_last:
        parts.append("收口不是 cta 或不足 60 帧")
    rep.check("C6", not parts,
              "三段完播对齐" if not parts else "；".join(parts),
              "三段各自补设计，见 references/story-framework.md")

    persp = str(meta.get("perspective") or "")
    hook_you = "你" in str(scenes[0].get("voiceover_pure") or "")
    c7_ok = persp in ("first_person", "second_person", "third_person", "headhunter") and hook_you
    rep.check("C7", c7_ok,
              "视角 %s，首屏用了第二人称" % persp if c7_ok
              else "视角字段缺失，或首屏没有第二人称钩子",
              "meta.perspective 填第一/第二/第三人称或猎头，钩子句面向观众")

    # ================== D 事实 ==================
    d1 = []
    for i, s in zip(ids, scenes):
        txt = str(s.get("voiceover_pure") or "")
        claims = s.get("claims") or []
        ok = claims and all(str(c.get("source") or "").strip() for c in claims) \
            and all(str(c.get("text") or "").strip() for c in claims)
        if NUM_RE.search(txt) and not ok:
            d1.append(i)
    rep.check("D1", not d1,
              "数字均可溯源" if not d1
              else "这些场景有数字但没有 claims.source: %s" % ",".join(d1),
              "每个数字写进 claims[{text, source}]，source 填素材出处或用户确认")

    d2 = [i for i, s in zip(ids, scenes)
          if any(w in str(s.get("voiceover_pure") or "") for w in ROLE_WORDS)
          and not str(s.get("role_tag") or "").strip()]
    rep.check("D2", not d2,
              "项目归属已标注" if not d2
              else "提到主导/负责/参与但没标 role_tag: %s" % ",".join(d2),
              "role_tag 写实际角色，主导、负责、参与不混用")

    d3 = []
    for i, s in zip(ids, scenes):
        txt = str(s.get("voiceover_pure") or "")
        for w in EXTREME:
            if w in txt:
                d3.append("%s(%s)" % (i, w))
    rep.check("D3", not d3,
              "无极限词" if not d3 else "极限词: %s" % ",".join(d3[:3]),
              "改成具体描述，别用最好/唯一/保证")

    # ================== E 去 AI 感 ==================
    seq = [str((m.get("params") or {}).get("spring")) for m in motions]
    run2, prev2, longest2 = 0, None, 0
    for sp in seq:
        if sp == prev2:
            run2 += 1
        else:
            run2, prev2 = 1, sp
        longest2 = max(longest2, run2)
    rep.check("E1", longest2 <= 2,
              "动效 spring 无连续复读" if longest2 <= 2
              else "连续 %d 个动效用同一 spring" % longest2,
              "换缓动或改 none")

    tw = [i for i, s in zip(ids, scenes) if s.get("typewriter") is True]
    rep.check("E2", len(tw) <= 2,
              "打字机 %d 处" % len(tw) if len(tw) <= 2
              else "打字机 %d 处（上限 2）: %s" % (len(tw), ",".join(tw)),
              "只留关键句，其余整段入场")

    e3 = sorted({str(m.get("effect")) for m in motions if m.get("effect") not in EFFECTS})
    rep.check("E3", not e3,
              "effect 全在白名单" if not e3 else "effect 越界: %s" % ",".join(e3),
              "只能是 " + "/".join(EFFECTS))

    # ================== F 数字人 ==================
    if not meta.get("has_avatar"):
        rep.skip("F", "未启用数字人，F 组跳过")
    else:
        f1 = [str(a.get("avatar_id")) for a in avatars
              if a.get("mode") == "side_window" and a.get("position") == "center"]
        rep.check("F1", not f1,
                  "小窗均靠边" if not f1 else "小窗居中会压主画面: %s" % ",".join(f1),
                  "side_window 的 position 用 left 或 right")

        direct = len([a for a in avatars if a.get("direction") == "direct"])
        pct = direct * 100 / float(len(avatars) or 1)
        rep.check("F2", pct <= 70,
                  "direct 占 %.0f%%" % pct if pct <= 70
                  else "direct 占 %.0f%%，直视过多显得僵" % pct,
                  "presenting 与 direct 按 4:6 配")

        f3 = []
        for a in avatars:
            if a.get("mode") != "hidden":
                continue
            sid = str((a.get("anchor") or {}).get("scene_id"))
            if sid in idx and durs[idx[sid]] > 90:
                f3.append(sid)
        rep.check("F3", not f3,
                  "hidden 段均 ≤90 帧" if not f3 else "hidden 超过 90 帧: %s" % ",".join(f3),
                  "hidden 只用于证据揭示，单次不超过 3 秒")

        f4 = []
        for prev_a, cur_a in zip(avatars, avatars[1:]):
            if prev_a.get("mode") == cur_a.get("mode"):
                continue
            i1 = idx.get(str((prev_a.get("anchor") or {}).get("scene_id")))
            i2 = idx.get(str((cur_a.get("anchor") or {}).get("scene_id")))
            if i1 is not None and i2 is not None:
                if scenes[i1].get("narrative_beat") == scenes[i2].get("narrative_beat"):
                    f4.append(str(cur_a.get("avatar_id")))
        rep.check("F4", not f4,
                  "模式切换均对应 beat 变化" if not f4
                  else "这些切换没有对应叙事段变化: %s" % ",".join(f4),
                  "切镜头跟着故事段走，不要中途随便切")

    # ================== G 口播纯净 ==================
    g1 = []
    for i, s in zip(ids, scenes):
        txt = str(s.get("voiceover_pure") or "")
        bad = [c for c in FORBIDDEN_CHARS if c in txt]
        if bad or EMOJI.search(txt):
            g1.append(i)
    rep.check("G1", not g1,
              "口播全净（无括号/标记/emoji）" if not g1
              else "voiceover_pure 混入标记，TTS 会念出来: %s" % ",".join(g1),
              "括号、星号、emoji、舞台指示全部删掉，强调信息放 emphasis_words")

    g2 = [i for i, s in zip(ids, scenes)
          if len(s.get("emphasis_words") or []) != len(s.get("emphasis_positions") or [])]
    rep.check("G2", not g2,
              "重读词与帧偏移一一对应" if not g2
              else "emphasis_words 与 emphasis_positions 数量不等: %s" % ",".join(g2),
              "两个数组同长，positions 是相对场景起点的帧偏移")

    g3 = [i for i, s in zip(ids, scenes) if not str(s.get("voiceover_pure") or "").strip()]
    rep.check("G3", not g3,
              "每场都有纯口播文本" if not g3 else "缺 voiceover_pure: %s" % ",".join(g3),
              "TTS 只认这个字段，空场景等于静音")

    g4 = []
    for i, s in zip(ids, scenes):
        for sent in re.split(r"[。！？!?；;]", str(s.get("voiceover_pure") or "")):
            if speak_len(sent) > 25:
                g4.append("%s(%d 字)" % (i, speak_len(sent)))
                break
    rep.check("G4", not g4,
              "单句均 ≤25 字" if not g4 else "长句: %s" % ",".join(g4),
              "拆句，一口气念不完观众也读不完")

    # ================== H 时间线对齐 ==================
    h1 = []
    for m in motions:
        a = m.get("anchor") or {}
        if a.get("type") != "on_emphasis":
            continue
        sid = str(a.get("scene_id"))
        if sid not in idx:
            h1.append("%s 场景不存在" % m.get("motion_id"))
            continue
        words = [str(w) for w in (scenes[idx[sid]].get("emphasis_words") or [])]
        if str(a.get("emphasis_word")) not in words:
            h1.append("%s(%s)" % (m.get("motion_id"), a.get("emphasis_word")))
    rep.check("H1", not h1,
              "on_emphasis 锚点全部命中重读词" if not h1
              else "锚点词不在 emphasis_words: %s" % ",".join(h1[:3]),
              "锚点词必须逐字等于场景里的 emphasis_words 成员")

    h2 = []
    for layer in LAYERS:
        for sid in ids:
            frames = []
            for m in motions_of(motions, sid, layer):
                f = motion_frame(m, scenes, idx, fps)
                if f is not None:
                    frames.append((f, f + int((m.get("params") or {}).get("durationFrames") or 0),
                                   str(m.get("motion_id"))))
            frames.sort()
            for (f1_, e1, n1), (f2_, e2, n2) in zip(frames, frames[1:]):
                if f2_ < e1:
                    h2.append("%s/%s: %s 与 %s 重叠" % (sid, layer, n1, n2))
    rep.check("H2", not h2,
              "同场同层动效不重叠" if not h2 else "；".join(h2[:3]),
              "同层动效错开，锚点间距至少 15 帧")

    h3 = [str(m.get("motion_id")) for m in motions
          if m.get("span_scenes")
          and str((m.get("anchor") or {}).get("scene_id")) not in idx]
    rep.check("H3", not h3,
              "跨场动效锚点有效" if not h3
              else "span_scenes 锚点场景不存在: %s" % ",".join(h3),
              "跨场动效锚在真实场景上")

    h4 = [i for i in ids if not motions_of(motions, i, "subject")]
    rep.check("H4", not h4,
              "每场都有主运动" if not h4
              else "这些场景没有 subject 动效，画面会挂死: %s" % ",".join(h4),
              "每场至少一个 subject 层动效")

    decor = len([m for m in motions if m.get("layer") == "decoration"])
    h5_ok = decor <= len(scenes) * 1.5
    rep.check("H5", h5_ok,
              "装饰动效 %d 个（上限 %.0f）" % (decor, len(scenes) * 1.5) if h5_ok
              else "装饰动效 %d 个，超过场景数 1.5 倍" % decor,
              "删掉纯装饰，只留支撑叙事的")

    h6 = [str(m.get("motion_id")) for m in motions
          if (m.get("anchor") or {}).get("type") in ("on_emphasis", "voiceover_gap")
          and m.get("resolve_after_tts") is not True]
    rep.check("H6", not h6,
              "TTS 后需重算的锚点已标注" if not h6
              else "这些锚点依赖 TTS 时序却没标 resolve_after_tts: %s" % ",".join(h6[:3]),
              "on_emphasis 与 voiceover_gap 一律 resolve_after_tts: true")

    # ================== I 视觉一致性 ==================
    vis = meta.get("visual") or {}
    canvas = vis.get("canvas") or {}
    spec = platform_spec(meta.get("platform_primary"))
    i1 = ((canvas.get("width"), canvas.get("height")) == spec.get("size")
          and canvas.get("ratio") == spec.get("ratio"))
    rep.check("I1", i1,
              "画布 %sx%s %s" % (canvas.get("width"), canvas.get("height"),
                                 canvas.get("ratio")) if i1
              else "画布与平台不匹配：%sx%s / %s，应为 %s"
                   % (canvas.get("width"), canvas.get("height"),
                      canvas.get("ratio"), spec.get("size")),
              "抖音 1080x1920，小红书 3:4 用 1080x1440")

    safe = vis.get("safe_area") or {}
    i2 = all(safe.get(k) == v for k, v in (spec.get("safe") or {}).items())
    rep.check("I2", i2,
              "安全区 %s" % (spec.get("safe")) if i2
              else "安全区不符：%s，应为 %s" % (safe, spec.get("safe")),
              "抖音顶部 100 底部 200，小红书 3:4 底部 120")

    ts = vis.get("type_scale") or {}
    i3 = (ts.get("hook") or 0) >= 60 and (ts.get("body") or 0) >= 36
    rep.check("I3", i3,
              "字号 hook %s / body %s" % (ts.get("hook"), ts.get("body")) if i3
              else "字号不足：hook %s、body %s（下限 60 / 36）"
                   % (ts.get("hook"), ts.get("body")),
              "竖屏 1080 宽下 hook ≥60、body ≥36")

    bg = str(vis.get("background") or "").lower()
    i4 = bool(bg) and not any(w in bg for w in ("black", "dark", "near_black", "#0", "#1"))
    rep.check("I4", i4,
              "背景 %s" % bg if i4 else "背景偏暗或未声明：%s" % (bg or "<空>"),
              "两种风格都以明亮为底线，不用近黑背景与暗角")

    ml = meta.get("motion_language") or {}
    prm = ml.get("params") or {}
    dr = prm.get("durationFrames") or [0, 0]
    ov = prm.get("overshoot") or [0, 0]
    primary = str(ml.get("primary"))
    if primary == "playful":
        ok_i5 = 5 <= dr[0] and dr[1] <= 9 and ov[0] >= 0.10 and ov[1] <= 0.20
        want = "playful 5 到 9 帧、过冲 10% 到 20%"
    elif primary == "corporate":
        ok_i5 = 6 <= dr[0] and dr[1] <= 12 and ov[0] >= 0 and ov[1] <= 0.03
        want = "corporate 6 到 12 帧、过冲 0% 到 3%"
    else:
        ok_i5 = primary in ("bubble",) and dr[1] <= 12
        want = "bubble 短距位移，时长 ≤12 帧"
    rep.check("I5", ok_i5,
              "%s 参数 %s 帧 / 过冲 %s" % (primary, dr, ov) if ok_i5
              else "%s 的动效参数越界：%s 帧 / 过冲 %s" % (primary, dr, ov),
              want)

    if verbose:
        print_report(rep, doc)
    return rep


def print_report(rep, doc=None):
    titles = {"A": "A 可渲染性", "B": "B 视觉预算", "C": "C 故事与留存",
              "D": "D 事实", "E": "E 去 AI 感", "F": "F 数字人调度",
              "G": "G 口播纯净", "H": "H 时间线对齐", "I": "I 视觉一致性"}
    print("")
    for g in ("A", "B", "C", "D", "E", "F", "G", "H", "I"):
        ok, n = rep.group_stat(g)
        if n == 0:
            print("[SKIP] %s  未启用" % titles[g])
            continue
        print("[%s] %s  %d/%d" % ("PASS" if ok == n else "FAIL", titles[g], ok, n))
    fails = rep.fails()
    if fails:
        print("")
        print("未通过明细：")
        for f in fails:
            print("  [%s] %s" % (f["id"], f["msg"]))
            if f["fix"]:
                print("        改法：%s" % f["fix"])
    total = len([f for f in rep.findings if not f.get("skip")])
    print("")
    print("结论：%s  %d/%d 项通过" % ("PASS" if not fails else "FAIL",
                                    total - len(fails), total))
    if not fails:
        print("可以进样片：python scripts/sample.py <production.json> --out-dir samples")
        print("要人工剪辑：python scripts/export_edit_pack.py <production.json> --out-dir edit-pack")


def selftest():
    good = os.path.join(FIXTURES, "good-production.json")
    bad = os.path.join(FIXTURES, "bad-production.json")
    intro = os.path.join(FIXTURES, "good-intro.json")
    if not (os.path.isfile(good) and os.path.isfile(bad)):
        print("[FAIL] 缺 fixture：%s" % FIXTURES)
        return 2
    problems = []
    rg = validate(load(good), verbose=False)
    if rg.fails():
        problems.append("good-production.json 应全过，实有 %d 项未过：%s"
                        % (len(rg.fails()), ",".join(f["id"] for f in rg.fails())))
    n_cases = 2
    if os.path.isfile(intro):
        n_cases = 3
        ri = validate(load(intro), verbose=False)
        if ri.fails():
            problems.append("good-intro.json 应全过（含数字人 F 组），实有 %d 项未过：%s"
                            % (len(ri.fails()), ",".join(f["id"] for f in ri.fails())))
    rb = validate(load(bad), verbose=False)
    got = set(f["id"] for f in rb.fails())
    must = {"C3", "G1", "A2"}
    if len(got) < 6:
        problems.append("bad-production.json 只命中 %d 项，应至少 6 项" % len(got))
    miss = must - got
    if miss:
        problems.append("bad-production.json 未命中必报项：%s" % ",".join(sorted(miss)))
    print("")
    print("自检：good 全过=%s，bad 命中 %d 项（%s）"
          % (not rg.fails(), len(got), ",".join(sorted(got))))
    if problems:
        for p in problems:
            print("  [FAIL] " + p)
        return 1
    print("自检结论：PASS（%d/%d 用例）" % (n_cases, n_cases))
    return 0


def main():
    ap = argparse.ArgumentParser(description="引流视频 production.json 校验（双时间线）")
    ap.add_argument("script", nargs="?", help="production.json 路径")
    ap.add_argument("--json", dest="json_out", help="结果写成 JSON")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
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
    total = len([f for f in rep.findings if not f.get("skip")])
    if args.quiet:
        print("%s %d/%d" % ("PASS" if not rep.fails() else "FAIL",
                            total - len(rep.fails()), total))
    if args.json_out:
        d = os.path.dirname(os.path.abspath(args.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"pass": not rep.fails(), "total": total,
                                 "passed": total - len(rep.fails()),
                                 "findings": rep.findings},
                                ensure_ascii=False, indent=2) + "\n")
    return 0 if not rep.fails() else 1


if __name__ == "__main__":
    sys.exit(main())
