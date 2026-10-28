#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scaffold.py — 出 production.json 骨架（双时间线）

用法：
    python scaffold.py --type agent_skill --viewpoint "你花时间做的事，本来就不该你来做" \
        --seconds 38 --out production.json
    python scaffold.py --type personal_intro --viewpoint "我不是把方案写完就走的人" \
        --seconds 60 --out production.json

做的事：
    1. 按内容类型分支出场景骨架，帧号由转场重叠递推，不手填
    2. 每个场景自动挂一个 subject 动效，锚点全部可解析
    3. personal_intro 自动出数字人时间线（full / side_window / hidden）
    4. 默认时长（38 / 60 秒）开箱即过；改时长按输出提示拆场景或删字

占位口播是骨架，不是成品。改字不重算帧号；改字数后必须重跑 validate.py。
"""

import argparse
import io
import json
import os
import sys

MID_SECONDS = 1.4

# beat, share, type, level, direction, visual_role, text, subs, emphasis
AGENT_SKILL = [
    ("hook", 2.4, "statement", 5, "flat", "evidence",
     "格式改到深夜，你该睡了。",
     ["格式改到深夜", "你该睡了"], ["深夜"], None),
    ("conflict", 4.0, "statement", 4, "up", "narrative",
     "这不是手慢。判断你早做完了。",
     ["这不是手慢", "判断你早做完了"], ["不是手慢"], None),
    ("conflict", 4.0, "statement", 4, "down", "narrative",
     "剩下那七步，全靠手动搬运。",
     ["剩下那七步", "全靠手动搬运"], ["七步"], None),
    ("progressive_breakdown", 4.0, "bullets", 3, "up", "evidence",
     "你以为是快。但问题是，快只是表面。",
     ["快只是表面", "但问题在后面"], ["但问题是"], 1),
    ("progressive_breakdown", 4.0, "bullets", 4, "up", "evidence",
     "更狠的是，它把改格式那一步整个拿走了。",
     ["更狠的是", "那一步整个拿走了"], ["更狠的是", "整个拿走了"], 1),
    ("midpoint_hook", MID_SECONDS, "title", 4, "up", "narrative",
     "离谱的在后面。",
     ["离谱的在后面"], ["离谱"], None),
    ("progressive_breakdown", 3.8, "bullets", 4, "up", "evidence",
     "关键是第二步。它不只改格式。",
     ["关键是第二步", "它不只改格式"], ["关键是第二步"], 2),
    ("progressive_breakdown", 3.8, "bullets", 5, "up", "evidence",
     "连命名和归档一起做了，你只点头。",
     ["连命名归档一起做", "你只点头"], ["一起做了"], 2),
    ("viewpoint", 4.0, "quote", 5, "flat", "narrative",
     "所以你花时间做的事，本来就不该你来做。",
     ["你花时间做的事", "本来就不该你来做"], ["不该你来做"], None),
    ("viewpoint", 3.0, "statement", 4, "flat", "narrative",
     "这条，你以后会用得上。",
     ["这条", "你以后会用得上"], ["用得上"], None),
    ("cta", 3.6, "title", 3, "flat", "narrative",
     "完整用法在主页粉丝群。",
     ["完整用法", "在主页粉丝群"], ["主页粉丝群"], None),
]

PERSONAL_INTRO = [
    ("hook", 3.0, "statement", 5, "flat", "evidence",
     "如果你在找重做招聘流程的人。",
     ["如果你在找", "重做招聘流程的人"], ["重做"], None),
    ("conflict", 3.5, "statement", 4, "up", "narrative",
     "我入行的时候，先学会的是把流程跑顺。",
     ["入行的时候", "先学会把流程跑顺"], ["流程跑顺"], None),
    ("conflict", 3.5, "statement", 4, "down", "narrative",
     "但跑顺之后我发现，人还是留不住。",
     ["跑顺之后", "人还是留不住"], ["留不住"], None),
    ("progressive_breakdown", 4.0, "bullets", 3, "up", "evidence",
     "我先动了筛选。但问题是，筛得准也没用。",
     ["我先动了筛选", "但问题是"], ["但问题是"], 1),
    ("midpoint_hook", MID_SECONDS, "title", 4, "up", "narrative",
     "我用了很久。",
     ["我用了很久"], ["很久"], None),
    ("progressive_breakdown", 8.0, "bullets", 4, "up", "evidence",
     "更狠的是，决定成败的不是面试，是人进来以后的头几个月。",
     ["更狠的是", "进来以后的几个月"], ["更狠的是"], 2),
    ("progressive_breakdown", 8.0, "bullets", 5, "up", "evidence",
     "关键是第三步。我把交付标准写进合同，谁都能查。",
     ["关键是第三步", "标准写进合同"], ["关键是第三步"], 3),
    ("persona", 8.0, "quote", 5, "flat", "narrative",
     "我不是把方案写完就走的人，我是把方案落到数据上的人。",
     ["不是写完就走", "是把方案落到数据上"], ["落到数据上"], None),
    ("persona", 8.0, "statement", 4, "flat", "narrative",
     "落到数据上不是口号，是我看项目的标准，这条你用得上。",
     ["不是口号", "是我看项目的标准"], ["不是口号", "用得上"], None),
    ("cooperation", 8.0, "bullets", 4, "up", "narrative",
     "我能提供的是招聘体系梳理。我在找愿意重做流程的团队。",
     ["我能提供招聘体系梳理", "我在找重做流程的团队"], ["我能提供", "我在找"], None),
    ("cta", 4.6, "title", 3, "flat", "narrative",
     "具体聊，主页私信我。",
     ["具体聊", "主页私信我"], ["私信我"], None),
]

EFFECT_CYCLE = ["scale-up", "slide-in", "fade-up", "push-in", "fade"]
SPRING_CYCLE = ["playful", "corporate", "snappy", "smooth"]


def build(kind, viewpoint, seconds, fps, platform):
    table = AGENT_SKILL if kind == "agent_skill" else PERSONAL_INTRO
    mid_i = [i for i, row in enumerate(table) if row[0] == "midpoint_hook"][0]
    # 微型钩子之前定长：保证钩子始终落在 10 到 20 秒，不被总时长拉走
    prefix = sum(row[1] for row in table[:mid_i])
    suffix = sum(row[1] for row in table[mid_i + 1:])
    factor = max(0.5, (seconds - prefix - MID_SECONDS) / suffix) if suffix else 1.0

    durs = []
    for i, row in enumerate(table):
        if i == mid_i:
            sec = MID_SECONDS
        elif i < mid_i:
            sec = row[1]
        else:
            sec = row[1] * factor
        durs.append(max(30, int(round(sec * fps))))

    trans = []
    for i in range(len(durs) - 1):
        t = max(2, min(8, int(min(durs[i], durs[i + 1]) / 2)))
        trans.append({"afterScene": "s%02d" % (i + 1), "presentation": "slide"
                      if i == 0 else "fade",
                      "direction": "from-bottom" if i == 0 else "none",
                      "durationInFrames": t})
    tdur = {t["afterScene"]: t["durationInFrames"] for t in trans}


    scenes, motions, cursor = [], [], 0
    vp = viewpoint.strip().rstrip("。.！!？?")
    vp_done = False
    for i, row in enumerate(table):
        beat, _share, typ, level, direction, role, text, subs, emph, feat = row
        if beat in ("viewpoint", "persona") and not vp_done:
            text = ("所以%s。" % vp) if kind == "agent_skill" else ("%s。" % vp)
            vp_done = True
        sid = "s%02d" % (i + 1)
        emo = {"level": level, "direction": direction}
        enter = "scale-up" if i == 0 else ("fade-up" if i % 2 else "slide-from-bottom")
        ef = 14 if i == 0 else 10
        spring = SPRING_CYCLE[i % len(SPRING_CYCLE)]
        if beat == "midpoint_hook":
            spring = "smooth"
        if beat == "cta":
            spring = "smooth"

        scene = {
            "scene_id": sid,
            "startFrame": cursor,
            "durationInFrames": durs[i],
            "type": typ,
            "narrative_beat": beat,
            "emotion": emo,
            "visual_role": role,
            "voiceover_pure": text,
            "emphasis_words": emph,
            "emphasis_positions": [int(durs[i] * (k + 1) / (len(emph) + 1))
                                   for k in range(len(emph))],
            "visual_asset": {"type": "screen_record" if role == "evidence" else "blank_stage",
                             "highlight_region": "center"},
            "claims": [],
            "role_tag": "",
            "spring": spring,
            "enter": enter,
            "enterFrames": ef,
            "typewriter": i == 0,
        }
        if feat is not None:
            scene["feature_index"] = feat
        scenes.append(scene)

        # 主运动：微型钩子用 fade，幅度小
        eff = "fade" if beat == "midpoint_hook" else EFFECT_CYCLE[i % len(EFFECT_CYCLE)]
        mdur = 5 if beat == "midpoint_hook" else (9 if level == 5 else 6 + (i % 3))
        motions.append({
            "motion_id": "m_%03d" % (len(motions) + 1),
            "layer": "subject",
            "anchor": {"type": "on_emphasis" if i in (0, 8) else "scene_enter",
                       "scene_id": sid,
                       "emphasis_word": emph[0] if emph and i in (0, 8) else None,
                       "offsetFrames": 0},
            "effect": eff,
            "params": {"durationFrames": mdur, "spring": spring,
                       "overshoot": 0.12 if spring == "playful" else 0.0},
            "target": "primary_subject",
            "span_scenes": False,
            "resolve_after_tts": i in (0, 8),
        })
        for m in motions:
            if m["anchor"].get("emphasis_word") is None:
                m["anchor"].pop("emphasis_word", None)

        # 装饰：只给两个中段场景，且不在回落与钩子场景
        if i in (4, 7) and direction != "down" and beat != "midpoint_hook":
            motions.append({
                "motion_id": "m_%03d" % (len(motions) + 1),
                "layer": "decoration",
                "anchor": {"type": "relative_offset", "scene_id": sid,
                           "offsetFrames": max(2, durs[i] // 2)},
                "effect": "slide-in",
                "params": {"durationFrames": 5, "spring": "none", "overshoot": 0.0},
                "target": "label_chip",
                "span_scenes": False,
                "resolve_after_tts": False,
            })

        cursor = cursor + durs[i] - tdur.get(sid, 0)

    # 保证微型钩子邻场是强动效，避免幅度倒挂
    if mid_i > 0:
        for j in (mid_i - 1, mid_i + 1):
            if 0 <= j < len(scenes):
                for m in motions:
                    if m["layer"] == "subject" and \
                            m["anchor"]["scene_id"] == scenes[j]["scene_id"]:
                        m["effect"] = "slide-in"
                        m["params"]["durationFrames"] = max(
                            8, int(m["params"]["durationFrames"]))

    avatar = []
    if kind == "personal_intro":
        plan = [(0, "full", "direct", "center", "65%"),
                (3, "side_window", "presenting", "right", "25%"),
                (4, "hidden", "listening", "center", "0%"),
                (7, "full", "direct", "center", "65%")]
        for k, (i, mode, direc, pos, size) in enumerate(plan):
            if i >= len(scenes):
                continue
            avatar.append({
                "avatar_id": "av_%03d" % (k + 1),
                "anchor": {"type": "scene_enter", "scene_id": scenes[i]["scene_id"],
                           "offsetFrames": 0},
                "mode": mode,
                "direction": direc,
                "position": pos,
                "size": size,
                "enter_effect": "fade-up",
                "resolve_after_tts": False,
            })

    palette = "bright_playful" if kind == "agent_skill" else "bright_corporate"
    primary = "playful" if kind == "agent_skill" else "corporate"
    params = ({"durationFrames": [5, 9], "easing": "ease-out-back",
               "overshoot": [0.10, 0.20], "maxSimultaneousElements": 3}
              if primary == "playful" else
              {"durationFrames": [6, 12], "easing": "cubic-bezier(0.2,0,0,1)",
               "overshoot": [0.0, 0.03], "maxSimultaneousElements": 1})
    canvas = {"douyin": (1080, 1920, "9:16"), "xiaohongshu": (1080, 1440, "3:4"),
              "shipinhao": (1080, 1920, "9:16")}[platform]
    safe = {"top": 100, "bottom": 120 if platform == "xiaohongshu" else 200,
            "left": 60, "right": 60}

    return {
        "meta": {
            "content_type": kind,
            "platform_primary": platform,
            "fps": fps,
            "totalCompositionFrames": cursor,
            "target_seconds": seconds,
            "perspective": "first_person",
            "viewpoint": viewpoint,
            "language_nail": "落到数据上" if kind == "personal_intro" else "",
            "visual_hammer": "结果画面第一屏" if kind == "agent_skill" else "项目结果看板",
            "has_avatar": kind == "personal_intro",
            "visual": {
                "canvas": {"width": canvas[0], "height": canvas[1], "ratio": canvas[2]},
                "safe_area": safe,
                "type_scale": {"hook": 72, "h1": 56, "body": 40, "caption": 32},
                "palette": palette,
                "background": "warm_off_white" if kind == "agent_skill" else "cool_off_white",
                "accent_colors": ["coral", "teal"] if kind == "agent_skill" else ["slate_blue"],
                "text_color": "charcoal" if kind == "agent_skill" else "deep_slate",
            },
            "motion_language": {"primary": primary, "params": params},
            "note": "占位口播，必须整段替换为素材真实内容；有数字的场景要填 claims.source",
        },
        "scriptTimeline": scenes,
        "motionTimeline": motions,
        "avatarTimeline": avatar,
        "transitions": trans,
        "checks": {},
    }


def main():
    ap = argparse.ArgumentParser(description="出 production.json 骨架（双时间线）")
    ap.add_argument("--type", dest="kind", default="agent_skill",
                    choices=["agent_skill", "personal_intro"])
    ap.add_argument("--viewpoint", required=True, help="观点句或人设句")
    ap.add_argument("--seconds", type=float, default=0, help="目标时长，默认 38 / 60")
    ap.add_argument("--fps", type=int, default=30, choices=[24, 25, 30, 60])
    ap.add_argument("--platform", default="douyin",
                    choices=["douyin", "xiaohongshu", "shipinhao"])
    ap.add_argument("--out", default="production.json")
    args = ap.parse_args()

    default = 38.0 if args.kind == "agent_skill" else 60.0
    seconds = args.seconds or default
    if not (30 <= seconds <= 90):
        sys.stderr.write("[FAIL] --seconds 只支持 30 到 90\n")
        return 2

    doc = build(args.kind, args.viewpoint.strip(), seconds, args.fps, args.platform)
    out = os.path.abspath(args.out)
    parent = os.path.dirname(out)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    fps = args.fps
    total = doc["meta"]["totalCompositionFrames"]
    print("[OK] 骨架已出：%s" % out)
    print("     类型 %s / 平台 %s / %d 场 / %d 帧 / %.1f 秒 @%dfps"
          % (args.kind, args.platform, len(doc["scriptTimeline"]), total,
             total / float(fps), fps))
    print("     动效 %d 条（subject %d / decoration %d），数字人 %d 条"
          % (len(doc["motionTimeline"]),
             len([m for m in doc["motionTimeline"] if m["layer"] == "subject"]),
             len([m for m in doc["motionTimeline"] if m["layer"] == "decoration"]),
             len(doc["avatarTimeline"])))
    print("     观点句/人设句：%s" % doc["meta"]["viewpoint"])
    base = 38.0 if args.kind == "agent_skill" else 60.0
    if seconds < base - 1:
        print("")
        print("[WARN] 时长压到 %.0f 秒，骨架字数不变，B4 会报文字密度过高。" % seconds)
        print("       按 4.2 字/秒删字，或把 --seconds 调回 %.0f。" % base)
    if seconds > base + 1:
        need = int(round(len(doc["scriptTimeline"]) * seconds / base))
        print("")
        print("[WARN] 时长拉到 %.0f 秒，骨架只有 %d 场，B8 会报镜长超限。"
              % (seconds, len(doc["scriptTimeline"])))
        print("       拆场景到 %d 场左右，或把 --seconds 调回 %.0f。" % (need, base))
    print("")
    print("下一步：")
    print("  1. 逐场替换 voiceover_pure，字数按 4.2 字/秒估，帧号不用动")
    print("  2. python scripts/validate.py %s" % os.path.basename(out))
    print("  3. python scripts/sample.py %s --out-dir samples" % os.path.basename(out))
    print("  4. python scripts/export_edit_pack.py %s --out-dir edit-pack" % os.path.basename(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
