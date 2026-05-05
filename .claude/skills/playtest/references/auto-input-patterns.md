# Auto Input Patterns — テストパターン設計ガイド

## AutoInputTester 概要

`Assets/MyAsset/Runtime/Debug/AutoInputTester.cs` は PlayMode で自動入力シーケンスを送信してメカニクスを検証する。
`PlayerInputHandler.SetOverrideInput(MovementInfo)` を使い、スクリプト化された入力を送る。

## 現在のテストカテゴリ（12種）

| カテゴリ | フラグ | 検証内容 |
|---------|--------|---------|
| Move | _testMove | 左右移動、移動速度、停止 |
| Jump | _testJump | ジャンプ、接地判定、空中状態 |
| LightAttack | _testLightAttack | 弱攻撃発動、ダメージ発生 |
| HeavyAttack | _testHeavyAttack | 強攻撃発動（リリース確定方式） |
| Skill | _testSkill | スキル入力 |
| Dodge | _testDodge | 回避（スプリントボタン短押し） |
| Sprint | _testSprint | スプリント（スプリントボタン長押し） |
| Guard | _testGuard | ガード状態、被ダメージ軽減 |
| Buttons | _testButtons | その他ボタン（インタラクト、メニュー等） |
| Stamina | _testStamina | スタミナ消費・回復 |
| AerialAttack | _testAerialAttack | 空中攻撃、空中浮遊 |
| Composite | _testComposite | 複合入力（移動+攻撃、ジャンプ+攻撃等） |

## テストステップの構成

```csharp
struct TestStep
{
    string name;           // テスト名
    float duration;        // 実行時間（秒）
    MovementInfo input;    // 送信する入力
    Action validation;     // 検証コールバック
}
```

## MovementInfo フィールド一覧

```csharp
struct MovementInfo
{
    Vector2 moveDirection;       // 移動方向 (-1~1, -1~1)
    bool jumpPressed;            // ジャンプ（一発入力）
    bool jumpHeld;               // ジャンプ長押し
    bool dodgePressed;           // 回避（一発入力）
    bool sprintHeld;             // スプリント
    AttackInputType? attackInput; // 攻撃入力タイプ
    bool guardHeld;              // ガード
    bool interactPressed;        // インタラクト
    bool cooperationPressed;     // 連携
    bool weaponSwitchPressed;    // 武器切替
    bool gripSwitchPressed;      // グリップ切替
    bool menuPressed;            // メニュー
    bool mapPressed;             // マップ
    float chargeMultiplier;      // チャージ倍率
}
```

## AttackInputType 定義

```csharp
enum AttackInputType : byte
{
    LightGround,     // 地上弱攻撃
    HeavyGround,     // 地上強攻撃
    SkillGround,     // 地上スキル
    LightAerial,     // 空中弱攻撃
    HeavyAerial,     // 空中強攻撃
    SkillAerial,     // 空中スキル
}
```

## テスト設計パターン

### パターン1: 単純動作検証
```
[移動開始] → 0.5s → [位置が変化したか確認] → [停止] → 0.3s → [速度が0か確認]
```

### パターン2: 攻撃→ヒット検証
```
[右移動] → 0.5s（敵に接近）→ [攻撃入力] → 0.3s → [敵HP減少確認]
```

### パターン3: タイミング依存検証
```
[ジャンプ] → 0.1s → [空中攻撃] → 0.3s → [空中攻撃状態確認] → 0.5s → [着地確認]
```

### パターン4: 状態遷移検証
```
[ガード開始] → 0.2s → [ガード状態確認] → [ガード解除] → 0.2s → [通常状態確認]
```

### パターン5: リソース消費検証
```
[スタミナ記録] → [回避] → 0.3s → [スタミナ減少確認] → 1.0s → [スタミナ回復確認]
```

### パターン6: チャージ攻撃検証（リリース方式）
AutoInputTesterからはSetOverrideInputを使うため、チャージはattackInputとchargeMultiplierで直接指定する:
```
[attackInput = HeavyGround, chargeMultiplier = 1.0] → 0.3s → [通常強攻撃確認]
[attackInput = HeavyGround, chargeMultiplier = 2.5] → 0.3s → [チャージ強攻撃確認]
```

注意: PlayerInputHandler.SetOverrideInput()はPollAttackButtons()をバイパスする。
チャージのホールド→リリースのタイミングテストはPlayModeの実入力テストが必要。

## CLIInternal による設定変更

```bash
# 全テスト有効
unicli exec Menu.Execute --menuPath "Tools/CLIInternal/Run Auto Input All"

# 戦闘系のみ
unicli exec Menu.Execute --menuPath "Tools/CLIInternal/Run Auto Input Combat"

# 移動系のみ
unicli exec Menu.Execute --menuPath "Tools/CLIInternal/Run Auto Input Movement"
```

これらのメニュー項目は AutoInputTester の各フラグを設定してから PlayMode に入る。

## テスト追加時の注意事項

1. **テスト間の独立性**: 各テストステップは前のステップの状態に依存しないようにする
2. **タイミングマージン**: 物理演算のフレーム遅延を考慮し、検証前に十分な待機時間を設ける
3. **スナップショット活用**: 検証前にHP/スタミナ/位置をスナップショットし、差分で判定する
4. **ログ出力**: 各テストの開始・終了・結果をログに記録する
5. **周回テスト**: _loopCount で同じテストを複数回実行し、再現性を確認する
