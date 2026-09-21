# Jev Playground

给 TypeSafe 的判定模型 [Jev](https://docs.typesafe.ai) 搭的游乐场：三个确定性牌/棋类环境
+ 一份真机复现研究。全部遵循 [NanoJev](https://github.com/TianyuCodings/NanoJev) 的
`snake_game.py` 模式——确定性引擎、完整可验证的 JSON 状态、`render_request` 渲染问题、
程序化 gold 标签，渲染时严格省略隐藏信息。

| 项目 | 说明 | 依赖 |
|---|---|---|
| [doudizhu/](doudizhu/) | 斗地主：三座位自动对局，CSS 扑克实时观战，💥 炸弹震屏 | 零（纯标准库） |
| [blackjack/](blackjack/) | 21 点：基本策略 gold、鞋组成与爆牌概率预计算、资金曲线 | 零（纯标准库） |
| [sudoku/](sudoku/) | 数独解题评测：MRV 选格 + naked/hidden single 裁判，难度旋钮 | 零（纯标准库） |
| [typesafe-mario-repro/](typesafe-mario-repro/) | [typesafe-mario](https://github.com/fhshaik/typesafe-mario) 真机复现研究：上游两处缺陷的实锤 + JevHarness 式 harness 对照 + 浏览器观战 | Python 3.13 + 上游 venv |

每个项目文件夹内有独立的 README 与快速开始命令。本地裁判（规则替身）让所有项目
**无 API Key 即可跑通**；设 `TYPESAFE_API_KEY` 后同一套问题走真 Jev，代码零改动。

## 一分钟体验

```bash
cd doudizhu && python3 serve_doudizhu.py        # 斗地主观战
cd blackjack && python3 serve_blackjack.py      # 21 点观战
cd sudoku && python3 jev_sudoku.py --episodes 5 # 数独评测
```

## 许可

各环境代码 CC0-1.0（对齐 NanoJev 约定）；斗地主/21点/数独不含任何第三方游戏资产；
Mario 复现使用的 ROM 来自 `gym-super-mario-bros` 包自带文件，上游仓库未改动一行。
