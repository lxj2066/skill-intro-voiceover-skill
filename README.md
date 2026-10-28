# skill-intro-voiceover-skill

把 Agent、Skill 或个人履历写成 30 到 90 秒引流视频的 `production.json`，并导出剪辑软件能直接用的素材包。
安装：把本目录复制到 `~/.workbuddy/skills/`，或上传 SkillHub。
许可证：PolyForm Noncommercial 1.0.0，个人与内部使用免费，禁止商业用途与转售。

## 它和普通分镜模板的差别

帧号、转场、视觉预算解决的是“拍得出来”。它不解决“观众为什么要看到第 15 秒”。

这个包做三件事：

1. **故事层**按抖音三段考核设计：前 3 秒停不停、10 到 20 秒走不走、结尾记不记得。
2. **工程层**拆三条时间线：口播、动效、数字人各自独立，靠锚点对齐，改一处不碰坏另一处。
3. **交付层**出确定性校验与剪辑素材包，机器剪和人工剪共用一套数字。

## 四条命令

```bash
# 1. 出骨架：三条时间线、帧分配、转场核算一次算好
python scripts/scaffold.py --type agent_skill \
  --viewpoint "你花时间做的事，本来就不该你来做" --seconds 38 --out production.json

# 2. 校验九组 46 项
python scripts/validate.py production.json

# 3. 切双样片：8 秒首屏 + 中段钩子前后
python scripts/sample.py production.json --out-dir samples

# 4. 导出剪辑素材包：SRT、分镜表、渲染参数、落地指南
python scripts/export_edit_pack.py production.json --out-dir edit-pack
```

个人介绍把 `--type` 换成 `personal_intro`，`--seconds 60`。

## 判据九组

| 组 | 项数 | 管什么 |
|---|---|---|
| A 可渲染 | 6 | 转场、净时长、起帧递推、首帧可见、收口停留 |
| B 视觉预算 | 8 | 运动占比、主运动数、spring 分布、文字密度、镜长 |
| C 故事与留存 | 7 | 观点句复述、递进转折、中段钩子、情绪回落、收藏与接口、三段对齐 |
| D 事实 | 3 | 数字溯源、角色标注、极限词 |
| E 去 AI 感 | 3 | spring 复读、打字机限量、effect 白名单 |
| F 数字人 | 4 | 小窗位置、直视比例、隐藏时长、切换时机 |
| G 口播纯净 | 4 | 标记、重读词对齐、空场景、长句 |
| H 时间线对齐 | 6 | 锚点可解析、不重叠、跨场有效、每场有主运动 |
| I 视觉一致 | 5 | 画布、安全区、字号、背景、动效参数 |

`validate.py` 退出码 0 才算过。`--selftest` 跑三份正反例（38 秒工具稿、60 秒个人稿、反例）。

## 剪辑落地

`references/editing-toolchain.md` 给三条路径：

| 路径 | 工具 | 什么时候用 |
|---|---|---|
| A 代码渲染 | Remotion | 批量出、改数据重渲、动效精确落帧 |
| B 人工剪辑 | 剪映专业版 / Premiere / 达芬奇 | 一次性、现场改口播 |
| C 数字人 | HeyGen / 腾讯智影 / 硅基智能 | 个人介绍要真人出镜 |

时长、帧数、字数、场景数四者必须同时成立，对照表在那一章。

## 目录

```
SKILL.md                     三条时间线、工作流、输出契约、红线
references/
  story-framework.md         两类内容的五段骨架、递进句式、记忆点三件套
  editing-toolchain.md       剪辑与生成工具选型、时长设置、导出参数
  remotion-pitfalls.md       渲染驱动的 26 个坑与对应契约
  platform-rules.md          完播三段口径、安全区、小红书差异、合规
  methodology.md             设计理由与反模式表
  examples.md                38 秒完整示例与校验输出
scripts/                     validate / scaffold / sample / export_edit_pack
assets/                      production.schema.json 与 38 秒模板
tests/                       三份正反例与回归用例
```

## 不适用

90 秒以上长视频、直播带货话术、纯图文文案、无画面需求的配音稿。

## 作者

李献杰 Lyon｜12 年高端猎头，人力百强集团猎头合伙人｜擅长中高管招聘说服、框架梳理、流程 AI 自动化、Agent 编写、降本增效｜浙江杭州｜欢迎沟通交流

## 版本

当前版本 2.0.0，许可证 PolyForm Noncommercial 1.0.0。
