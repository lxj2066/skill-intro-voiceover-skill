#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scaffold.py — 出合规帧骨架

用法：
    python scaffold.py --seconds 38 --anchor efficiency \
        --viewpoint "你花时间做的事，本来就不该你来做" --out script.json

做的事：
    1. 按五段骨架分配帧，微型钩子固定 1.4 秒不参与缩放
    2. 按转场重叠递推算 startFrame，算总帧数
    3. 填占位口播与情绪标注，保证开箱即可通过 validate.py

占位口播是骨架，不是成品。改字不重算帧号；改字数后必须重跑 validate.py。
"""

import argparse
import io
import json
import os
import sys

BASE_SECONDS = [2.4, 8.0, 8.6, 1.4, 7.6, 6.0, 4.0]
MID_IDX = 3

ANCHORS = {
    "efficiency": {
        "zh": "效率反差",
        "c1": "但问题是", "c2": "更狠的是", "c3": "关键是第二步",
        "pain": "还得替机器干一遍搬运的活，七步，一步都不能少",
        "pb2": "它不只改格式，连命名和归档一起做了，你只需要点头",
    },
    "capability": {
        "zh": "能力越级",
        "c1": "但关键在于", "c2": "真正变的是", "c3": "真正变的是第二步",
        "pain": "还得先学会它，才能开始做那件本来就会做的事",
        "pb2": "它不只给结果，连中间那几步的判断一起给了，你只负责挑",
    },
    "quality": {
        "zh": "质量碾压",
        "c1": "但这不算本事", "c2": "难得的是", "c3": "难得的是第二步",
        "pain": "还得自己逐条核对，错一个字就得整段返工",
        "pb2": "它不只不出错，连你没注意的那几处也一起改了，你只管发",
    },
    "process": {
        "zh": "流程消失",
        "c1": "但这不算什么", "c2": "真正让我", "c3": "真正让我决定做这条视频的是",
        "pain": "还得在四个软件之间来回倒，倒一次错一次",
        "pb2": "它不只省了第一步，中间那几步也吃了，你只剩拍板",
    },
}

SEGMENTS = [
    # beat, type, emotion, motion, spring, enter, enterFrames, typewriter, visual
    ("hook", "statement", (5, "flat"), 3, "bouncy", "scale-up", 14, True,
     {"asset": "result_first_frame", "highlight_region": "center"}),
    ("conflict", "statement", (4, "down"), 1, "smooth", "fade-up", 12, False,
     {"asset": "pain_split", "highlight_region": "left_side"}),
    ("progressive_breakdown", "bullets", (3, "up"), 2, "snappy", "slide-from-bottom", 12, False,
     {"asset": "before_after_split", "highlight_region": "after_side"}),
    ("midpoint_hook", "title", (4, "up"), 1, "snappy", "scale-up", 10, False,
     {"asset": "solid_black", "highlight_region": "center"}),
    ("progressive_breakdown", "bullets", (5, "up"), 2, "smooth", "slide-from-bottom", 12, False,
     {"asset": "pipeline_steps", "highlight_region": "middle_steps"}),
    ("viewpoint", "quote", (5, "flat"), 1, "bouncy", "scale-up", 16, False,
     {"asset": "solid_black", "highlight_region": "center"}),
    ("cta", "title", (3, "flat"), 1, "smooth", "fade-up", 12, False,
     {"asset": "group_entry", "highlight_region": "bottom"}),
]

SUBTITLES = [
    ["改一份格式", "你花了四十分钟"],
    ["这不是手慢", "是你替机器搬运"],
    ["快只是表面", "那一步整个拿掉了"],
    ["真正离谱的是下一个"],
    ["关键是第二步", "连归档一起做了"],
    ["你花时间做的事", "本来就不该你来做"],
    ["完整用法在主页粉丝群"],
]


def build(seconds, anchor_key, viewpoint, fps, size):
    a = ANCHORS[anchor_key]
    vp = viewpoint.strip().rstrip("。.！!？?")
    factor = (seconds - BASE_SECONDS[MID_IDX]) / (sum(BASE_SECONDS) - BASE_SECONDS[MID_IDX])
    secs = [b if i == MID_IDX else b * factor for i, b in enumerate(BASE_SECONDS)]
    durs = [max(30, int(round(s * fps))) for s in secs]

    voice = [
        "改一份格式，你花了四十分钟。",
        "这不是手慢。是你把判断做完之后，" + a["pain"] + "。",
        "你以为是快，%s，快只是表面。%s，它把改格式那一步整个拿掉了。" % (a["c1"], a["c2"]),
        "真正离谱的是下一个。",
        "%s。%s。" % (a["c3"], a["pb2"]),
        "所以%s。这条，你以后会用得上。" % vp,
        "完整用法在主页粉丝群，拿走去用。",
    ]
    emphasis = [
        ["四十分钟"],
        ["不是手慢", "一步都不能少"],
        [a["c1"], a["c2"], "整个拿掉了"],
        ["真正离谱"],
        [a["c3"], "点头"],
        ["不该你来做", "用得上"],
        ["主页粉丝群"],
    ]

    trans = []
    for i in range(len(durs) - 1):
        t = max(2, min(8, int(min(durs[i], durs[i + 1]) / 2)))
        trans.append({"after_scene": "s%d" % (i + 1), "durationInFrames": t, "kind": "fade"})
    tdur = {t["after_scene"]: t["durationInFrames"] for t in trans}

    scenes, cursor = [], 0
    for i, (beat, typ, emo, motion, spring, enter, ef, tw, visual) in enumerate(SEGMENTS):
        sid = "s%d" % (i + 1)
        scenes.append({
            "scene_id": sid,
            "narrative_beat": beat,
            "startFrame": cursor,
            "durationInFrames": durs[i],
            "type": typ,
            "voiceover_text": voice[i],
            "subtitle_lines": SUBTITLES[i],
            "emphasis_words": emphasis[i],
            "emotion": {"level": emo[0], "direction": emo[1]},
            "motion_budget": motion,
            "first_frame_visible": i == 0,
            "typewriter": tw,
            "animation": {"enter": enter, "spring": spring, "enterFrames": ef},
            "visual": visual,
        })
        cursor = cursor + durs[i] - tdur.get(sid, 0)

    return {
        "meta": {
            "platform": "douyin",
            "fps": fps,
            "width": size[0],
            "height": size[1],
            "safe_area": {"top": 200, "bottom": 400, "left": 60, "right": 200},
            "target_seconds": seconds,
            "anchor_type": anchor_key,
            "anchor_zh": a["zh"],
            "viewpoint": vp,
            "note": "占位口播，必须整段替换为素材真实内容；替换后重跑 validate.py",
        },
        "scenes": scenes,
        "transitions": trans,
        "totalCompositionFrames": cursor,
    }


def main():
    ap = argparse.ArgumentParser(description="出合规帧骨架")
    ap.add_argument("--seconds", type=float, default=38.0, help="目标时长，30 到 50")
    ap.add_argument("--anchor", default="efficiency", choices=sorted(ANCHORS),
                    help="价值锚点类型")
    ap.add_argument("--viewpoint", required=True, help="观点句，一句判断，20 字内")
    ap.add_argument("--fps", type=int, default=30, choices=[24, 25, 30, 60])
    ap.add_argument("--size", default="1080x1920", help="画面尺寸，宽x高")
    ap.add_argument("--out", default="script.json", help="输出路径")
    args = ap.parse_args()

    if not (30 <= args.seconds <= 50):
        sys.stderr.write("[FAIL] --seconds 只支持 30 到 50，超长请另做结构\n")
        return 2
    try:
        w, h = [int(x) for x in args.size.lower().split("x")]
    except ValueError:
        sys.stderr.write("[FAIL] --size 写成 宽x高，例如 1080x1920\n")
        return 2

    doc = build(args.seconds, args.anchor, args.viewpoint, args.fps, (w, h))
    out = os.path.abspath(args.out)
    parent = os.path.dirname(out)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    total = doc["totalCompositionFrames"]
    print("[OK] 骨架已出：%s" % out)
    print("     锚点 %s（%s），%d 场，%d 帧，%.1f 秒 @%dfps"
          % (args.anchor, doc["meta"]["anchor_zh"], len(doc["scenes"]), total,
             total / float(args.fps), args.fps))
    print("     转场 %d 条，合计 %d 帧"
          % (len(doc["transitions"]), sum(t["durationInFrames"] for t in doc["transitions"])))
    print("     观点句：%s" % doc["meta"]["viewpoint"])
    print("")
    print("下一步：")
    print("  1. 逐场替换 voiceover_text，保持大致字数，帧号不用动")
    print("  2. python scripts/validate.py %s" % os.path.basename(out))
    print("  3. python scripts/sample.py %s --out-dir samples" % os.path.basename(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
