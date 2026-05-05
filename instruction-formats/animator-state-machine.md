# Animator State Machine 指示フォーマット

このフォーマットを使用して、AnimatorControllerの構成をAIに齟齬なく伝える。

## フォーマット

```
# AnimatorController: [名前]

## States
- [ステート名] (default, motion: [アニメーション名])
- [ステート名] (motion: [アニメーション名])
- [ステート名] (motion: [アニメーション名], speed: [倍率])

## Parameters
- [パラメータ名]: Float (default: 0)
- [パラメータ名]: Bool (default: false)
- [パラメータ名]: Int (default: 0)
- [パラメータ名]: Trigger

## Transitions
- [開始ステート] → [終了ステート]: [条件1], [条件2]
- Any → [ステート名]: [条件] (※ AnyStateからの遷移)
- [ステート名] → Exit: [条件] (※ 終了遷移)

## Transition Options (省略時はデフォルト)
- exit time: [0.0-1.0] (遷移開始タイミング)
- transition duration: [秒] (ブレンド時間)
- has exit time: true/false

## Layers
- [レイヤー名]: weight [0.0-1.0], [override|additive]

## Sub-State Machines (必要な場合)
- [サブステートマシン名]:
  - [ステート名] (motion: [アニメーション名])
  - ...
```

## 使用例

```
# AnimatorController: PlayerAnimator

## States
- Idle (default, motion: player_idle)
- Walk (motion: player_walk)
- Run (motion: player_run, speed: 1.5)
- Jump (motion: player_jump)
- Fall (motion: player_fall)
- Land (motion: player_land)

## Parameters
- Speed: Float (default: 0)
- IsGrounded: Bool (default: true)
- JumpTrigger: Trigger
- VerticalVelocity: Float (default: 0)

## Transitions
- Idle → Walk: Speed > 0.1, IsGrounded == true
- Walk → Idle: Speed < 0.1
- Walk → Run: Speed > 5.0
- Run → Walk: Speed < 5.0, Speed > 0.1
- Any → Jump: JumpTrigger, IsGrounded == true
- Jump → Fall: VerticalVelocity < 0 (has exit time: false)
- Fall → Land: IsGrounded == true (transition duration: 0.1)
- Land → Idle: (exit time: 0.8)

## Layers
- Base Layer: weight 1.0, override
- Upper Body: weight 0.5, additive
```

## 注意事項
- `default` マーカーは1つのステートにのみ付与（Entry遷移先）
- `Any →` は AnyState からの遷移を示す
- 条件なしの遷移は exit time のみで遷移する
- 複数条件はカンマ区切りでAND条件
