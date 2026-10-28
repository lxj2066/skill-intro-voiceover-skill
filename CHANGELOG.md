# CHANGELOG

## 2.0.0

技术层重写为双时间线，并新增个人介绍分支与剪辑落地。判据由 29 项扩到 46 项，属主版本升级。

**结构：一份 JSON，三条时间线**
- `scriptTimeline[]` 只放会被念出来的字，`voiceover_pure` 是唯一 TTS 字段，强调信息移到 `emphasis_words` 与 `emphasis_positions`。
- `motionTimeline[]` 用五种锚点挂到口播上（`scene_enter` / `on_emphasis` / `before_scene_end` / `relative_offset` / `voiceover_gap`），不再写绝对帧。
- `avatarTimeline[]` 独立调度数字人，`full` / `side_window` / `hidden` 三档，切换必须对应叙事段变化。
- 依赖 TTS 时序的锚点强制 `resolve_after_tts: true`，走两阶段解析。

**内容：两类分支**
- `agent_skill`：观点句、功能递进、中段钩子、收藏暗示、粉丝群。
- `personal_intro`：人设句、记忆点三件套（视觉锤 / 语言钉 / 可用反差）、合作接口三项、数字人调度。
- 新增 D 组事实判据：数字必须进 `claims.source`，提到主导/负责/参与必须标 `role_tag`，极限词拦截。

**判据：九组 46 项**
A 可渲染 6、B 视觉预算 8、C 故事留存 7、D 事实 3、E 去 AI 感 3、F 数字人 4、G 口播纯净 4、H 时间线对齐 6、I 视觉一致 5。
F 组未启用数字人时整组跳过，不虚增分母。

**交付：从稿到能发**
- 新增 `export_edit_pack.py`：出 `tts.txt`、`captions.srt`、`storyboard.csv`、`remotion-props.json`、`remotion-notes.md`、`edit-guide.md`。
- 新增 `references/editing-toolchain.md`：Remotion / 剪映 / 数字人三条路径的选型、时长设置、导出参数、四个翻车点。
- `scaffold.py` 支持两类内容与平台切换，微型钩子前定长，保证钩子永远落在 10 到 20 秒。
- 安全区口径改为抖音上 100 下 200、小红书 3:4 下 120。

**校验**
- `validate.py --selftest` 三份用例：38 秒工具稿 42/42、60 秒个人稿 46/46、反例命中 11 项。
- 渲染坑位从 21 条补到 26 条，新增锚点写绝对帧、on_emphasis 估算值、跨场动效、数字人图层、SRT 与帧表不一致。

**已知未覆盖**
- 不评估画面美感，只保证不越界、不超预算。
- 不预测播放量；平台权重为行业口径，需按自己账号复核。
- 数字人素材需外部平台生成，本包只出调度表。

## 1.0.0

首版。把一份“渲染规格书”级的口播提示词升级成带确定性判据的技能包。

**故事层**
- 观点句作叙事终点，C1 校验原句复述。
- 功能点并列改递进，C2 校验转折词。
- 10 到 20 秒新增微型钩子，C3/C7 校验落位与字数。
- 情绪曲线 level 与 direction，C4 校验必须有一次回落。
- 结尾三段式：观点回扣加收藏理由加粉丝群，C5 校验。

**渲染层**
- fps 改变量，帧号由秒派生。
- 起帧递推契约，手填必错。
- 转场上限改为相邻场景一半。
- 首帧必须可见，`first_frame_visible` 必填。
- TTS 文本与强调词分离，禁 markdown。
- 语速预算 3.2 到 8.0 字每秒，字幕每行 16 字。

**交付层**
- validate.py 29 项，scaffold.py 四种锚点骨架，sample.py 双样片。
- script.schema.json 字段契约，voiceover-template.json 38 秒模板。
- remotion-pitfalls.md 21 个渲染坑。
