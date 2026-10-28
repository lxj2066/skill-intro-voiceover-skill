#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sample.py — 切双样片

用法：
    python sample.py script.json --out-dir samples

产出两份自包含 JSON：
    samples/head-sample.json      0 到 240 帧，回答「首屏留得住吗」
    samples/midpoint-sample.json  微型钩子前后各一场，回答「观众会在这里划走吗」

两份都能直接喂给渲染器，帧号已重基到 0。
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
    """按原始场景下标切一份自包含稿，帧号重基到 0。"""
    scenes_all = doc["scenes"]
    ids = [str(s["scene_id"]) for s in scenes_all]
    keep = set(idxs)
    offset = int(scenes_all[idxs[0]].get("startFrame") or 0)
    trs = []
    for t in doc.get("transitions") or []:
        a = str(t.get("after_scene"))
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
    total = sum(int(s["durationInFrames"]) for s in scenes) - \
        sum(int(t["durationInFrames"]) for t in trs)
    if clamp_total and total > clamp_total:
        over = total - clamp_total
        scenes[-1]["durationInFrames"] = max(30, int(scenes[-1]["durationInFrames"]) - over)
        total = sum(int(s["durationInFrames"]) for s in scenes) - \
            sum(int(t["durationInFrames"]) for t in trs)
    out = {
        "meta": dict(doc.get("meta") or {}),
        "sample": label,
        "sample_source": os.path.basename(doc.get("_src", "script.json")),
        "scenes": scenes,
        "transitions": trs,
        "totalCompositionFrames": total,
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="切双样片")
    ap.add_argument("script", help="script.json 路径")
    ap.add_argument("--out-dir", default="samples", help="输出目录")
    args = ap.parse_args()

    if not os.path.isfile(args.script):
        sys.stderr.write("[FAIL] 文件不存在: %s\n" % args.script)
        return 2
    doc = load(args.script)
    doc["_src"] = os.path.basename(args.script)
    scenes = doc.get("scenes") or []
    if not scenes:
        sys.stderr.write("[FAIL] scenes 为空\n")
        return 2

    fps = int((doc.get("meta") or {}).get("fps") or 30)
    head_frames = int(HEAD_SECONDS * fps)

    head_idx = [i for i, s in enumerate(scenes)
                if int(s.get("startFrame") or 0) < head_frames]
    if not head_idx:
        sys.stderr.write("[FAIL] 首屏没有可切场景\n")
        return 2
    head_idx = head_idx[:4]

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

    paths = []
    for name, data in (("head-sample.json", head), ("midpoint-sample.json", mid)):
        p = os.path.join(out_dir, name)
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        paths.append((p, data))

    print("[OK] 样片已出：%s" % out_dir)
    for p, d in paths:
        print("     %s  %d 场  %d 帧  %.1f 秒"
              % (os.path.basename(p), len(d["scenes"]),
                 d["totalCompositionFrames"], d["totalCompositionFrames"] / float(fps)))
    print("")
    print("看片只问一句：")
    print("  1. head-sample：这 %d 秒，陌生人会不会滑走？首帧有主体吗？" % int(HEAD_SECONDS))
    print("  2. midpoint-sample：这 %.1f 秒，已经听懂的人在等什么？"
          % (mid["totalCompositionFrames"] / float(fps)))
    print("")
    print("两段都过，才铺全片。中段不过，先改口播，不要加动效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
