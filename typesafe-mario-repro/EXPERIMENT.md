# 马里奥复现实验报告

> 这是简版。完整的逐帧取证、所有踩过的坑和错误更正记录在
> [REPORT.md](REPORT.md)，想看细节去看那边。

## 这个实验想说明什么

上游那个项目（typesafe-mario）做的事是：让 Jev 直接玩《超级马力欧兄弟》，
但**不给它看画面**——只给它一堆从游戏内存里读出来的数字（马力欧在哪、跑多快、
前面有什么怪、地形什么样）。核心想法是：**该算的代码算好，只让模型做判断。**

复现它，就是要把这个想法在真机上验一遍，顺便看看它到底行不行。

## 具体测了四个问题

| # | 问题 |
|---|---|
| A | 上游代码在真游戏上能原样跑通吗？ |
| B | 上游代码里有没有让模型"有力使不出"的毛病？ |
| C | 模型看到的"地形传感器"（碰撞网格）靠得住吗？ |
| D | 把事实准备得更好（学 JevHarness 的做法），模型能玩得更好吗？ |

## 实验怎么做的

真游戏（`gym-super-mario-bros` 自带的 ROM）、真 2KB 内存、上游代码一行没改，
只把"问模型"这一步换成本地替身（因为机器上没有 API Key）。

### A. 真机跑通 + 发现按键问题

`ruff` 和 10 个单元测试全过，真内存读出来的网格、地形数据都是对的。

但发现一个毛病：**`--display none`（无窗口模式）下，模型连按跳跃键跳不起来。**
原来超级马力欧的规则是"松开再按下 A 才算一次新跳跃"，可视化窗口模式处理了
这件事，无窗口模式忘了。结果模型对着墙连下 269 次"起跳"命令，
**一次都没跳起来**，活活卡死在墙前。同一个策略、同一副牌，把按键问题修掉之后，
从 x=594（水管前）一路打到 x=1124。

### B. 你发现的"网格里没有坑"

你在分享页面上注意到：模型看到的网格里没有坑，但它一直死在那。查下来发现
是个更严重的问题：

模型读地形的方式有个错位——游戏的地形数据是跟着镜头滚动的，而上游代码按
关卡绝对坐标去读。**镜头位置凑巧时读对，不凑巧时整整错开一页**（256 像素）。
错开的时候模型看到的网格是一片空白：没有坑、没有地面、什么都没有。

也就是说，模型大约一半的时间是"瞎的"。它每次走到那个坑边，看到的情报都是
"前方一路畅通"，然后径直掉下去——这就是"一直死在这里"的真正原因。

修法（在我们这层包一层，上游没动）：按镜头位置重新读一遍。修完之后，
死亡分布从"全部堆在一个坑"变成了 `[843×4, 1149, 1416]`——
有一局越过了从来没能通过的 1104 大坑。

### C. 决策节奏才是第一约束

实测出跳跃的完整数据：跑跳最高 68 像素、滞空 47 帧、水平跨度 82 像素。
World 1-1 第一根 4 格高的水管，**允许起跳的位置只有 28.6 像素宽**。
而上游默认 8 帧才做一次决定——一拍就跨过 21 像素，经常整拍错过窗口。

把决定频率调到 4 帧一次，同一个策略最好成绩从 1124 变成 **3156**（2.8 倍）。
**这是本次研究对上游最实用的一条建议。**

### D. 学 JevHarness 重写信息层（负结果）

按 JevHarness 的三板斧重写了一遍信息层：把"能不能跳过这个坑"提前算成
一句话结论、每个动作的说明里带上当场的具体数字、把前几次死亡蒸馏成教训
注入下一次决策。真机 A/B 的结果：**没打过原版**（900/1517 vs 1124/3156）。

为什么？本地替身是规则程序，它不读我们精心写的文字——六局的行为逐字节一样，
说明那些改进它一点没吸收。而原版的粗糙策略（3 格内就跳）在 4 帧粒度下
歪打正着，变成"高频连跳"，对连续水管段反而好用。

**这个负结果不是说"把事实准备好"没用，而是说：规则替身测不出这件事。**
要验证这条命题，必须上真 Jev（设个环境变量就行，代码零改动）。

## 结果说明

四个实验连起来是一个完整的故事：

**上游的思路是对的，但有两处实现 bug（按键、地形读取），让模型大约一半的
时间处于"下了命令没人执行 + 眼睛基本失明"的状态。** 在这种状态下谈任何
模型侧优化都没意义——先把这两处修好，模型的实际表现才有可能接近它的设计上限。

## 结论

1. 上游思路成立（真机全链路跑通），但有两处真实缺陷，都用 A/B 量化了影响；
2. 决策频率 8→4 帧是单点收益最大的优化（2.8 倍）；
3. 信息层重写的价值本地测不出来，是真 Jev 接入后的第一件事；
4. 建议把按键和地形读取两处修复反馈给上游作者。

---

## 附：这个实验里 Jev 的请求与回复结构

### Jev 的角色

每一拍（4-8 帧）回答**三个问题**（共享同一份 state，一次往返）：

1. `next_action`（choice，7 个手柄宏）——下一步按什么；
2. `jump_needed`（noul）——此刻前跳有没有用；
3. `danger`（score，0-2）——处境多危险，供页面可视化。

它**不执行任何动作**：选完由模拟器推进，下一步的事实重新解析再问。

### 请求长什么样（真实采样，见 artifacts/sample_request.json）

```json
{
  "state": {
    "objective": "Reach the flag in World 1-1 without dying.",
    "player": { "x": 172, "y": 79, "grounded": true, "jump_phase": "grounded", "horizontal_speed_px_per_frame": 0 },
    "trajectory": { "airborne_frames": 0, "crossing_known_gap": false },
    "hazard": { "enemy_ahead": true, "nearest_enemy_kind": "goomba", "nearest_enemy_distance_pixels": 42,
                "jump_must_start_this_decision": false, "takeoff_deadline_frames": null },
    "terrain": { "obstacle_distance_tiles": null, "gap_distance_tiles": 6, "observation_reliability": "high" },
    "reaction_timing": { "action_horizon_frames": 8, "last_inference_delay_frames": 0 },
    "recent_control": { "action": "right", "frames_observed": 1, "progress_gained_pixels": 0, "outcome": "not_enough_evidence" },
    "episode": { "lives": 2, "time_left": 387, "progress": 172, "stalled_frames": 0 }
  },
  "model": "jev-latest",
  "questions": {
    "next_action": { "type": "choice", "instructions": "Which controller macro should Mario commit to next? …（8 组策略）",
                     "criteria": { "noop": "Release the controls …", "right_run_jump": "Start a running jump when terrain or projected contact requires it …", "…": "共 7 个" } },
    "jump_needed": { "type": "noul", "instructions": "Do trusted terrain, projected hazard, trajectory … indicate that a forward jump should begin or remain held now?" },
    "danger": { "type": "score", "instructions": "How dangerous is Mario's immediate situation?",
                "criteria": ["Safe open movement", "Potential obstacle or enemy soon", "Immediate collision, fall, or enemy threat"] }
  }
}
```

v2 harness 在此之上加两个键：`takeoff_window`（起跳窗口判定，jump_now/wait/
too_late/regain_speed 四态）和 `prior_attempts`（跨局死亡蒸馏出的教训）。

### 回复结构（真实采样，见 artifacts/sample_response.json）

```json
{
  "model": "jev-latest",
  "usage": { "input_tokens": 1932, "output_tokens": 12 },
  "answers": {
    "next_action": { "type": "choice", "choice": "right_run", "confidence": 0.88,
                     "probabilities": { "noop": 0.02, "right": 0.02, "right_run": 0.88, "…": 0.14 } },
    "jump_needed": { "type": "noul", "noul": 0.05 },
    "danger": { "type": "score", "score": 0.0, "confidence": 0.85,
                "legend": { "0": "Safe open movement", "1": "Potential obstacle or enemy soon", "2": "Immediate collision …" },
                "probabilities": { "0": 0.9, "1": 0.08, "2": 0.02 } }
  }
}
```

（样例由本地替身按同一 schema 生成；真 API 的字段结构一致。）
三种原语在这里同时出现，各司其职：choice 驱动动作，noul 上页面「前跳是否有
利」条，score 上「即时危险度」条。

### 一次推理的运行路径

```
① 模拟器推进 frames_per_decision 帧
② _unwrap_ram() 从层层包装里取出 2KB RAM
③ MarioStateParser 解析：敌人槽位、nametable 地形、位置/速度、上一回合结果
   （parser_fix.py 在复现层修正相机页错位，见 REPORT §11）
④ （v2）feasibility_features 算起跳窗口；AttemptMemory 蒸馏跨局教训
⑤ policy.choose() 构造 Choice/Noul/Score 三个问题对象
⑥ TypeSafeClient.system_one(state, questions) → POST /v1/systemone
⑦ SDK 用 Pydantic wire model 校验；_answer() 从 choices/nouls/scores 取回
⑧ Decision(action, confidence, probabilities, latency_ms, jump_needed, danger)
⑨ runner 把 action 映射到 SIMPLE_MOVEMENT 索引；dashboard 路径按需插入
   JUMP_RELEASE_ACTION 释放帧，然后 env.step() 推进
```

代码位置：上游 `typesafe_mario/policy.py`（choose/_answer）、
`typesafe_mario/runner.py`（循环与释放帧）；复现层 `repro_run.py`
（替身与客户端补丁）、`mario_harness_v2.py`（v2 harness）。


---

## 附：Jev 扮演什么角色、花多少钱、要等多久

### Jev 在这个实验里干什么

每一拍（4-8 帧游戏画面）回答**三个问题**：下一步按哪个手柄宏（7 选 1）、
此刻前跳有没有用（是/否）、处境危不危险（0-2 打分）。我们负责把 2KB 游戏内存
解析成结构化事实（位置、速度、敌人投影、地形几何、实测推理延迟），它只做选择，
**不执行任何动作**——动作由模拟器按它选的手柄宏推进。

### 每次推理的请求规模与费用（实测）

| 版本 | 请求体积 | 折合输入 token | 单次成本 |
|---|---:|---:|---:|
| v1（上游原版） | 4653 字节 | 约 1163 | 约 $0.000049 |
| v2（JevHarness 式） | 5698 字节 | 约 1424 | 约 $0.000060 |

v2 大 22%：多出「起跳窗口判定」和「跨局死亡记忆」两块事实。定价同前
（官方文档，2026-09）：输入 $0.042 / 100 万 token，输出免费。

### 响应时间

- 本地替身实测：0.02ms
- 真 Jev 参考：JevHarness 公开数据 median 259-269ms
- 按 260ms/次估算

### 玩一局的耗时与总成本

| 场景 | 决策次数 | API 耗时 | 输入 token（v1） | 费用（v1） |
|---|---:|---:|---:|---:|
| 早死局（撞第一根水管） | 68 | 约 18 秒 | 7.9 万 | 约 $0.0033 |
| 中局（过第一根水管） | 317 | 约 82 秒 | 36.9 万 | 约 $0.0155 |
| 通关局（预估） | 400-600 | 1.7-2.6 分钟 | 47-70 万 | 约 $0.020-0.029 |
| 本实验累计（约 100 局） | 约 1.5 万 | 约 1 小时 | 约 1750 万 | 约 $0.73 |

四个实验里最贵的一个：一局动辄 300 拍（因为 4 帧一拍），而且请求带着
完整地形与敌人投影。省钱的办法是调大 `--frames-per-decision`（拍数变少、
但错过起跳窗口的概率上升，见实验 C）。

> 以上均为估算：token 按 4 字符约 1 token 折算，延迟取公开参考值 260ms。
> 真跑 `--judge` 接真 Jev 后，`usage` 与 `latency` 都有实测字段可替换。
