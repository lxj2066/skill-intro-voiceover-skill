# skill-intro-voiceover-skill

把工具或技能的功能素材写成 30 到 50 秒抖音口播分镜稿，交付 Remotion 可直接渲染的帧表。
安装：把本目录复制到 `~/.workbuddy/skills/`，或上传 SkillHub。
许可证：PolyForm Noncommercial 1.0.0，个人与内部使用免费，禁止商业用途与转售。

## 为什么不是又一份“帧表模板”

帧号、转场核算、视觉预算解决的是“拍得出来”。它不解决“观众为什么要看到第 15 秒”。

这个包把抖音完播拆成三段来做：前 3 秒停不停、10 到 20 秒走不走、结尾记不记得。
每一条都落成可执行检查，不是写在提示词里的形容词。

## 三条命令

```bash
# 出骨架
python scripts/scaffold.py --seconds 38 --anchor efficiency \
  --viewpoint "你花时间做的事，本来就不该你来做" --out script.json

# 校验 29 项
python scripts/validate.py script.json

# 切双样片
python scripts/sample.py script.json --out-dir samples
```

## 判据分五组

| 组 | 项数 | 管什么 |
|---|---|---|
| A 可渲染性 | 5 | 转场合法、净时长、起帧递推、首帧可见、收口停留 |
| B 视觉预算 | 9 | 类型白名单、spring 分布、回落留白、钩子克制、运动占比 |
| C 故事与留存 | 7 | 观点句复述、递进转折、中段钩子落位、情绪回落、收藏理由、三段对齐 |
| D 去 AI 感 | 3 | spring 不复读、打字机限量、无装饰动画 |
| R 渲染契约 | 5 | fps、TTS 文本纯净、语速区间、字幕安全区、时长偏差 |

`validate.py` 退出码 0 才算过。`--selftest` 跑内置正反例。

## 目录

```
SKILL.md                     五段结构、工作流、输出契约、红线
references/
  story-framework.md         五段骨架、递进句式库、钩子库、观点句生成法
  remotion-pitfalls.md       渲染驱动的 21 个坑与对应契约
  platform-rules.md          完播三段口径、安全区、小红书差异、合规
  methodology.md             设计理由与反模式表
  examples.md                38 秒完整示例与校验输出
scripts/                     validate / scaffold / sample
assets/                      script.schema.json 与 38 秒模板
tests/                       正反例与回归用例
```

## 不适用

90 秒以上长视频、直播带货话术、纯图文文案、无画面需求的配音稿。

## 作者

李献杰 Lyon｜12 年高端猎头，人力百强集团猎头合伙人｜擅长中高管招聘说服、框架梳理、流程 AI 自动化、Agent 编写、降本增效｜浙江杭州｜欢迎沟通交流

## 版本

当前版本 1.0.0，许可证 PolyForm Noncommercial 1.0.0。
