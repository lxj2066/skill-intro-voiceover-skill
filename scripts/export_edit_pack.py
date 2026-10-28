#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_edit_pack.py — 把 production.json 导成剪辑工具能直接吃的东西

用法：
    python export_edit_pack.py production.json --out-dir edit-pack

产出：
    tts.txt               一句一行，直接丢给 TTS 或配音
    captions.srt          字幕，剪映 / Premiere / 达芬奇都能导入
    storyboard.csv        分镜表，Excel 打开不乱码，人工剪辑照着排
    remotion-props.json   Remotion 工程直接读的 props
    remotion-notes.md     渲染命令与时长设置
    edit-guide.md         三条落地路径与操作步骤

同一份稿，机器剪和人工剪共用一套数字，不靠人眼对时间轴。
"""

import argparse
import io
import json
import os
import re
import sys

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
SPLIT = re.compile(r"[。！？!?；;\n]+")


def load(path):
    with io.open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def speak_len(text):
    return len(CJK.findall(text or "")) + len(LATIN_WORD.findall(text or ""))


def sentences(text):
    return [s.strip() for s in SPLIT.split(text or "") if s.strip()]


def ts(frames, fps):
    ms = int(round(frames * 1000.0 / fps))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def main():
    ap = argparse.ArgumentParser(description="导出剪辑工具可用的素材包")
    ap.add_argument("script", help="production.json 路径")
    ap.add_argument("--out-dir", default="edit-pack")
    args = ap.parse_args()

    if not os.path.isfile(args.script):
        sys.stderr.write("[FAIL] 文件不存在: %s\n" % args.script)
        return 2
    doc = load(args.script)
    meta = doc.get("meta") or {}
    scenes = doc.get("scriptTimeline") or []
    if not scenes:
        sys.stderr.write("[FAIL] scriptTimeline 为空\n")
        return 2

    fps = int(meta.get("fps") or 30)
    total = int(meta.get("totalCompositionFrames") or 0)
    out_dir = os.path.abspath(args.out_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    # ---------- tts.txt
    tts_lines = []
    for s in scenes:
        tts_lines.extend(sentences(s.get("voiceover_pure")))
    with io.open(os.path.join(out_dir, "tts.txt"), "w", encoding="utf-8",
                 newline="\n") as fh:
        fh.write("\n".join(tts_lines) + "\n")

    # ---------- captions.srt（按字数比例分配场景内时间）
    blocks, n = [], 0
    for k, s in enumerate(scenes):
        st = int(s.get("startFrame") or 0)
        dur = int(s.get("durationInFrames") or 0)
        nxt = int(scenes[k + 1].get("startFrame") or 0) if k + 1 < len(scenes) else st + dur
        rows = sentences(s.get("voiceover_pure"))
        if not rows:
            continue
        lens = [max(1, speak_len(r)) for r in rows]
        total_len = float(sum(lens))
        cursor = st
        for row, ln in zip(rows, lens):
            seg = max(1, int(round(dur * ln / total_len)))
            end = cursor + seg
            if cursor + seg >= st + dur:          # 最后一条不越过下一场上行点
                end = max(cursor + 1, min(st + dur, nxt))
            n += 1
            blocks.append("%d\n%s --> %s\n%s\n" % (
                n, ts(cursor, fps), ts(end, fps), row))
            cursor = end
    with io.open(os.path.join(out_dir, "captions.srt"), "w", encoding="utf-8",
                 newline="\n") as fh:
        fh.write("\n".join(blocks))

    # ---------- storyboard.csv
    avatars = doc.get("avatarTimeline") or []
    av_by_scene = {}
    for a in avatars:
        sid = str((a.get("anchor") or {}).get("scene_id"))
        av_by_scene.setdefault(sid, []).append(str(a.get("mode")))
    motions = doc.get("motionTimeline") or []

    def q(v):
        return '"%s"' % str(v).replace('"', "'").replace("\n", " ")

    header = ["镜号", "起点秒", "时长秒", "叙事段", "画面类型", "视觉角色",
              "口播", "视觉素材", "动效数", "数字人"]
    rows = [",".join(header)]
    for i, s in enumerate(scenes, 1):
        sid = str(s.get("scene_id"))
        mc = len([m for m in motions
                  if str((m.get("anchor") or {}).get("scene_id")) == sid])
        rows.append(",".join([
            q("%02d" % i),
            q("%.1f" % (int(s.get("startFrame") or 0) / float(fps))),
            q("%.1f" % (int(s.get("durationInFrames") or 0) / float(fps))),
            q(s.get("narrative_beat")),
            q(s.get("type")),
            q(s.get("visual_role")),
            q(s.get("voiceover_pure")),
            q((s.get("visual_asset") or {}).get("type")),
            q(mc),
            q("/".join(av_by_scene.get(sid, [])) or "-"),
        ]))
    with io.open(os.path.join(out_dir, "storyboard.csv"), "w",
                 encoding="utf-8-sig", newline="\n") as fh:
        fh.write("\n".join(rows) + "\n")

    # ---------- remotion-props.json
    vis = meta.get("visual") or {}
    canvas = vis.get("canvas") or {}
    props = {"fps": fps, "durationInFrames": total,
             "width": canvas.get("width"), "height": canvas.get("height"),
             "props": doc}
    with io.open(os.path.join(out_dir, "remotion-props.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(props, ensure_ascii=False, indent=2) + "\n")

    # ---------- remotion-notes.md
    notes = """# Remotion 渲染参数

```bash
# composition 一定要跟这三行对齐，否则首屏与结尾都会错位
fps              = {fps}
durationInFrames = {total}
width x height   = {w} x {h}
```

```bash
npx remotion render <composition-id> out.mp4 \\
  --codec=h264 --crf=18 --pixel-format=yuv420p \\
  --concurrency=4 --audio-codec=aac
```

- `remotion-props.json` 的 `props` 整块就是 `defaultProps`，不要再拆一层。
- 三条时间线都在里面：`scriptTimeline` 是主，`motionTimeline` 与 `avatarTimeline` 靠 `anchor` 挂上去。
- `resolve_after_tts: true` 的锚点，TTS 出声后要用 word timings 重算，别用这一次的时长写死。
- 字体放 `public/`，用 `delayRender()` 等加载完成，否则首帧是豆腐块。
""".format(fps=fps, total=total, w=canvas.get("width"), h=canvas.get("height"))
    with io.open(os.path.join(out_dir, "remotion-notes.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write(notes)

    # ---------- edit-guide.md
    sec = total / float(fps)
    chars = sum(speak_len(s.get("voiceover_pure")) for s in scenes)
    guide = """# 剪辑落地指南（本项目实际数字）

- 成片时长：**{sec:.1f} 秒**（{total} 帧 @ {fps}fps，已扣转场）
- 口播字数：**{chars} 字**，折合 {cps:.1f} 字/秒
- 镜头数：**{n} 个**，平均 {avg:.1f} 秒一个
- 平台：{platform}，画布 {w}x{h}

## 路径 A · Remotion（推荐，机器剪）

适合：要批量出、要改数据重渲、动效锚点要精确落帧。

1. `npm create video@latest` 建工程，`remotion.config.ts` 里把 fps 设成 {fps}
2. 根组件 `<Composition id="Main" durationInFrames={{{total}}} fps={{{fps}}} width={{{w}}} height={{{h}}} />`
3. 读 `remotion-props.json` 的 `props` 当 `defaultProps`
4. 用 `<TransitionSeries>` 铺 `scriptTimeline`，转场时长取 `transitions[].durationInFrames`
5. 动效按 `anchor.type` 换算成绝对帧：`scene_enter` 取 0，`relative_offset` 加偏移，`on_emphasis` 取 `emphasis_positions`
6. 渲命令看 `remotion-notes.md`

## 路径 B · 剪映专业版（最快，人工剪）

适合：一次性的、要现场改口播的、不想碰代码的。

1. 新建 9:16 项目，导入 `tts.txt` 生成的配音（或用剪映朗读，语速设 1.0 到 1.1 倍）
2. 导入 `captions.srt`，字幕样式选 40px 以上，位置避开底部 200px
3. 打开 `storyboard.csv`，按镜号一段段铺素材，时长按第三列卡
4. 转场时长照 `transitions` 填，全片统一 8 帧（约 0.27 秒），别用默认 1 秒
5. 导出：1080x1920、30fps、码率 8Mbps 以上、H.264

## 路径 C · 数字人平台（个人介绍用）

适合：`personal_intro`，`avatarTimeline` 不为空时。

1. 把 `tts.txt` 按场景分段喂给数字人平台（HeyGen / 腾讯智影 / 硅基智能）
2. 按 `avatarTimeline` 的 `mode` 出三段素材：`full` 半身居中、`side_window` 靠边小窗、`hidden` 空镜
3. 回剪辑软件按镜号拼，`hidden` 段不超过 90 帧
4. 人物素材留 5% 余量，便于小窗裁切

## 时长设置对照

| 目标 | 帧数 @30fps | 口播字数（4.2 字/秒） | 场景数 |
|---|---|---|---|
| 30 秒 | 900 | 110 到 125 | 9 到 11 |
| 38 秒 | 1140 | 145 到 160 | 11 到 13 |
| 45 秒 | 1350 | 175 到 190 | 13 到 15 |
| 60 秒 | 1800 | 235 到 250 | 14 到 18 |
| 90 秒 | 2700 | 355 到 375 | 20 到 26 |

帧数写死之前先看 `validate.py` 的 B4 与 B8 两项：字多了会挤，场景少了会拖。

## 发布前三件事

1. 第 0 帧截图当封面，检查有没有主体、有没有字被 UI 压住
2. 音画对齐：抽第 3 秒、第 15 秒、最后一秒各看一遍
3. 平台二次压缩后回看：1080p、H.264、yuv420p 才不会糊
"""
    with io.open(os.path.join(out_dir, "edit-guide.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write(guide.format(sec=sec, total=total, fps=fps, chars=chars,
                              cps=chars / sec if sec else 0, n=len(scenes),
                              avg=sec / max(1, len(scenes)),
                              platform=meta.get("platform_primary"),
                              w=canvas.get("width"), h=canvas.get("height")))

    print("[OK] 素材包已出：%s" % out_dir)
    print("     tts.txt            %d 句" % len(tts_lines))
    print("     captions.srt       %d 条字幕" % n)
    print("     storyboard.csv     %d 个镜号" % len(scenes))
    print("     remotion-props.json  fps=%d / durationInFrames=%d" % (fps, total))
    print("     remotion-notes.md  渲染命令")
    print("     edit-guide.md      三条落地路径 + 时长对照")
    print("")
    print("先读 edit-guide.md，它按这份稿的实际数字写了操作步骤。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
