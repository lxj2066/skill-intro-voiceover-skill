# 完整示例：38 秒工具介绍

素材：一个把杂乱合同批量改格式、自动命名、按项目归档的 Skill。
类型：`agent_skill`。锚点：效率反差。观点句：你花时间做的事，本来就不该你来做。

## 一、素材拆解

- 输入类型：只有提示词，无录屏、无输出截图。
- 两个功能点：批量改格式、自动命名并归档。
- **最可能划走的位置**：第 19 秒（第 552 帧）。第一个功能点刚讲完“快”，
  第二个还没露底牌，观众觉得“差不多懂了”。

这个预判决定微型钩子必须落在 552 帧。晚 2 秒就掉一半人。

## 二、观点句

> 你花时间做的事，本来就不该你来做。

判据：读完想反驳（有些事只能我做），能单独截图，不含“支持/可以/一键”。

## 三、五段落地（节选）

| 帧 | `narrative_beat` | 情绪 | 口播（`voiceover_pure`） |
|---|---|---|---|
| 0 到 72 | `hook` | 5 flat | 格式改到深夜，你该睡了。 |
| 64 到 184 | `conflict` | 4 up | 这不是手慢。判断你早做完了。 |
| 176 到 296 | `conflict` | 4 down | 剩下那七步，全靠手动搬运。 |
| 288 到 408 | `progressive_breakdown` | 3 up | 你以为是快。但问题是，快只是表面。 |
| 400 到 520 | `progressive_breakdown` | 4 up | 更狠的是，它把改格式那一步整个拿走了。 |
| 512 到 554 | `midpoint_hook` | 4 up | 离谱的在后面。 |
| 546 到 660 | `progressive_breakdown` | 4 up | 关键是第二步。它不只改格式。 |
| 652 到 766 | `progressive_breakdown` | 5 up | 连命名和归档一起做了，你只点头。 |
| 758 到 878 | `viewpoint` | 5 flat | 所以你花时间做的事，本来就不该你来做。 |
| 870 到 960 | `viewpoint` | 4 flat | 这条，你以后会用得上。 |
| 952 到 1060 | `cta` | 3 flat | 完整用法在主页粉丝群。 |

注意 64 而不是 72：转场重叠 8 帧，起帧靠递推，不靠手填。

## 四、场景片段（A 线）

```json
{
  "scene_id": "s06",
  "startFrame": 512,
  "durationInFrames": 42,
  "type": "title",
  "narrative_beat": "midpoint_hook",
  "emotion": { "level": 4, "direction": "up" },
  "visual_role": "narrative",
  "voiceover_pure": "离谱的在后面。",
  "emphasis_words": ["离谱"],
  "emphasis_positions": [21],
  "visual_asset": { "type": "blank_stage", "highlight_region": "center" },
  "claims": [],
  "role_tag": "",
  "spring": "smooth",
  "enter": "scale-up",
  "enterFrames": 10,
  "typewriter": false
}
```

## 五、动效片段（B 线）

```json
{
  "motion_id": "m_006",
  "layer": "subject",
  "anchor": { "type": "scene_enter", "scene_id": "s06" },
  "effect": "fade",
  "params": { "durationFrames": 5, "spring": "smooth", "overshoot": 0.0 },
  "target": "primary_subject",
  "span_scenes": false,
  "resolve_after_tts": false
}
```

钩子只有 42 帧、一个 fade、无背景运动。它靠 7 个字留人，不靠动效。
`validate.py` 的 B7 会算幅度：本场 2.5，邻场 16 与 24，上限 8，通过。

## 六、校验输出（原样贴）

```
[PASS] A 可渲染性  6/6
[PASS] B 视觉预算  8/8
[PASS] C 故事与留存  7/7
[PASS] D 事实  3/3
[PASS] E 去 AI 感  3/3
[SKIP] F 数字人调度  未启用
[PASS] G 口播纯净  4/4
[PASS] H 时间线对齐  6/6
[PASS] I 视觉一致性  5/5

结论：PASS  42/42 项通过
```

## 七、双样片

- `head-8s.json`：240 帧整 8 秒，3 场 3 个动效。看首帧有没有主体，第一句是不是结果。
- `midpoint.json`：约 8.7 秒，钩子前后各一场。看完问：已经听懂的人，此刻还有理由留下吗。

两段都过再铺全片。中段不过，改口播，不加动效。

## 八、剪辑素材包

`export_edit_pack.py` 出六个文件：

| 文件 | 用途 |
|---|---|
| `tts.txt` | 14 句，一句一行，直接喂 TTS |
| `captions.srt` | 14 条字幕，末条不越过下一场起点 |
| `storyboard.csv` | 11 个镜号，含时长与动效数，Excel 打开不乱码 |
| `remotion-props.json` | `fps=30`、`durationInFrames=1060`，整块当 `defaultProps` |
| `remotion-notes.md` | 渲染命令与字体注意项 |
| `edit-guide.md` | 三条落地路径，按这份稿的实际数字写 |

人工剪的话，`captions.srt` 与 `storyboard.csv` 两张表就够排完一条片。

## 九、小红书分支

- 封面 3:4、1080×1440，结果截图加观点句，视觉锤出现。
- 标题 20 字内：改一份合同的格式，不该花四十分钟。
- 正文第一段重复观点句，第二段写两个功能，用“但问题是/更狠的是”承接，300 到 500 字。
- 正文末尾给收藏理由：这套流程存下来，下次改合同直接用。
- 粉丝群话术放评论区首评，正文不写群。
- 不输出 `scriptTimeline`，只出封面、标题、正文、首评。
