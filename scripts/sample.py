#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sample.py — 从 production.json 切双样片

用法：
    python sample.py production.json --out-dir samples

产出两份自包含 JSON（三条时间线一起裁剪，帧号重基到 0）：
    samples/head-8s.json     0 到 240 帧，回答「首屏留得住吗」
    samples/midpoint.json    微型钩子前后各一场，回答「观众会在这里划走吗」
"""

import argparse
import io
import json
import os
import sys

HEAD_SECONDS = 8.0


def load(path):
    with io.open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def subset(doc, idxs, label, clamp_total=None):
    scenes_all = doc["scriptTimeline"]
    ids = [str(s["scene_id"]) for s in scenes_all]
    keep = set(idxs)
    offset = int(scenes_all[idxs[0]].get("startFrame") or 0)

    trs = []
    for t in doc.get("transitions") or []:
        a = str(t.get("afterScene"))
        if a not in ids:
            continue
        i = ids.index(a)
        if i in keep and (i + 1) in keep and a != ids[-1]:
            trs.append(dict(t))

    scenes = []
    for i in idxs:
        s = json.loads(json.dumps(scenes_all[i], ensure_ascii=False))
        s["startFrame"] = int(s.get("startFrame") or 0) - offset
        scenes.append(s)

    keep_ids = set(str(s["scene_id"]) for s in scenes)

    def keep_anchor(item):
        return str((item.get("anchor") or {}).get("scene_id")) in keep_ids

    motions = [json.loads(json.dumps(m, ensure_ascii=False))
               for m in doc.get("motionTimeline") or [] if keep_anchor(m)]
    avatars = [json.loads(json.dumps(a, ensure_ascii=False))
               for a in doc.get("avatarTimeline") or [] if keep_anchor(a)]

    total = sum(int(s["durationInFrames"]) for s in scenes) - \
        sum(int(t["durationInFrames"]) for t in trs)
    if clamp_total and total > clamp_total:
        scenes[-1]["durationInFrames"] = max(
            30, int(scenes[-1]["durationInFrames"]) - (total - clamp_total))
        total = sum(int(s["durationInFrames"]) for s in scenes) - \
            sum(int(t["durationInFrames"]) for t in trs)

    out = {
        "meta": dict(doc.get("meta") or {}),
        "sample": label,
        "sample_source": doc.get("_src", "production.json"),
        "scriptTimeline": scenes,
        "motionTimeline": motions,
        "avatarTimeline": avatars,
        "transitions": trs,
        "checks": {},
    }
    out["meta"]["totalCompositionFrames"] = total
    return out


def main():
    ap = argparse.ArgumentParser(description="切双样片")
    ap.add_argument("script", help="production.json 路径")
    ap.add_argument("--out-dir", default="samples")
    args = ap.parse_args()

    if not os.path.isfile(args.script):
        sys.stderr.write("[FAIL] 文件不存在: %s\n" % args.script)
        return 2
    doc = load(args.script)
    doc["_src"] = os.path.basename(args.script)
    scenes = doc.get("scriptTimeline") or []
    if not scenes:
        sys.stderr.write("[FAIL] scriptTimeline 为空\n")
        return 2

    fps = int((doc.get("meta") or {}).get("fps") or 30)
    head_frames = int(HEAD_SECONDS * fps)

    head_idx = [i for i, s in enumerate(scenes)
                if int(s.get("startFrame") or 0) < head_frames][:4]
    mid_idx = [i for i, s in enumerate(scenes)
               if s.get("narrative_beat") == "midpoint_hook"]
    if not mid_idx:
        sys.stderr.write("[FAIL] 没有 midpoint_hook 场景，无法切中段样片。\n"
                         "       先改稿，把微型钩子落在 10 到 20 秒。\n")
        return 1
    m = mid_idx[0]
    mid_scope = [i for i in (m - 1, m, m + 1) if 0 <= i < len(scenes)]

    out_dir = os.path.abspath(args.out_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    head = subset(doc, head_idx, "head_8s", clamp_total=head_frames)
    mid = subset(doc, mid_scope, "midpoint")

    for name, data in (("head-8s.json", head), ("midpoint.json", mid)):
        p = os.path.join(out_dir, name)
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    print("[OK] 样片已出：%s" % out_dir)
    for name, d in (("head-8s.json", head), ("midpoint.json", mid)):
        print("     %s  %d 场 / %d 动效 / %d 数字人 / %d 帧 / %.1f 秒"
              % (name, len(d["scriptTimeline"]), len(d["motionTimeline"]),
                 len(d["avatarTimeline"]), d["meta"]["totalCompositionFrames"],
                 d["meta"]["totalCompositionFrames"] / float(fps)))
    print("")
    print("看片只问两句：")
    print("  1. 这 8 秒，陌生人会不会滑走？第 0 帧有主体吗？")
    print("  2. 这 %.1f 秒，已经听懂的人在等什么？动效有没有抢戏？"
          % (mid["meta"]["totalCompositionFrames"] / float(fps)))
    print("")
    print("两段都过，才铺全片。中段不过，先改口播，不要加动效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
