# Test Scene Architecture — TestSceneBuilder 構成

## エリアレイアウト

```
x: -8        0         15          35         50
 |  Start   |  Combat  |  Mobility  |   Boss   |
 |  Area    |  Area    |  Area      |   Area   |
```

### 1. スタートエリア (x:-8 ~ 0)
- 安全地帯、仲間キャラクターと合流
- 地面: フラット
- 配置: Player(x:-5), Companion(x:-3)

### 2. 戦闘エリア (x:0 ~ 15)
- 敵x3 配置
- 攻撃・コンボ・ガード・回避をテスト
- 地面: フラット
- 配置: Enemy(x:5, x:8, x:11)

### 3. 機動テストエリア (x:15 ~ 35)
- 段差、ギャップ、高台
- ジャンプ・ダッシュ・空中攻撃をテスト
- 地面: 段差構成

### 4. ボスエリア (x:35 ~ 50)
- 強敵1体、壁で囲まれた擬似ボスルーム
- 配置: BossEnemy(x:42)

## キャラクター構成

### Player
- Components: PlayerCharacter, PlayerInputHandler, ActionExecutorController, DamageReceiver, CharacterAnimationController, CharacterCollisionController, BoxCollider2D, Rigidbody2D, SpriteRenderer
- Layer: 12 (CharaPassThrough)
- Tag: "Player"
- AttackInfos: PlayerCombo1, PlayerCombo2, PlayerCombo3, PlayerHeavy, PlayerSlash
- CharacterInfo: PlayerInfo.asset

### Enemy (通常)
- Components: EnemyCharacter, ActionExecutorController, DamageReceiver, DamageDealer(子), CharacterAnimationController, BoxCollider2D, Rigidbody2D, SpriteRenderer
- Layer: 12 (CharaPassThrough)
- Tag: "Enemy"
- AIInfo: PLACEHOLDER_BasicEnemyAI.asset
- AttackInfos: EnemyAttack
- HitBox(子): Layer 11 (EnemyHitbox)

### Enemy (Boss)
- 通常敵と同構成だがステータス強化
- AIInfo: PLACEHOLDER_BossAI.asset
- AttackInfos: EnemyAttack, BossSlam

### Companion
- Components: CompanionCharacter, ActionExecutorController, DamageReceiver, CharacterAnimationController, BoxCollider2D, Rigidbody2D, SpriteRenderer
- Layer: 12 (CharaPassThrough)
- Tag: "Companion"
- AIInfo: PLACEHOLDER_CompanionAI.asset
- AttackInfos: CompanionAttack
- CompanionMpSettings: 設定済み

## 物理レイヤー設定

TestSceneBuilder.SetupPhysicsLayers() が以下を設定:
1. `CollisionMatrixSetup.SetupCollisionMatrix()` を呼び出し（基本マトリクス）
2. 追加設定:
   - Layer 10(PlayerHitbox) ↔ Layer 6(Ground): 無視
   - Layer 11(EnemyHitbox) ↔ Layer 6(Ground): 無視
   - Layer 10 ↔ Layer 11: 無視（ヒットボックス同士は衝突しない）

## ScriptableObject アセット

| アセット | パス | 用途 |
|---------|------|------|
| PlayerInfo | Assets/MyAsset/Data/PlayerInfo.asset | プレイヤーステータス |
| BasicEnemyInfo | Assets/MyAsset/Data/BasicEnemyInfo.asset | 通常敵ステータス |
| CompanionInfo | Assets/MyAsset/Data/CompanionInfo.asset | 仲間ステータス |
| PLACEHOLDER_BasicEnemyAI | Assets/MyAsset/Data/ | 通常敵AI行動定義 |
| PLACEHOLDER_BossAI | Assets/MyAsset/Data/ | ボスAI行動定義 |
| PLACEHOLDER_CompanionAI | Assets/MyAsset/Data/ | 仲間AI行動定義 |
| PLACEHOLDER_PlayerCombo1-3 | Assets/MyAsset/Data/ | プレイヤーコンボ攻撃 |
| PLACEHOLDER_PlayerHeavy | Assets/MyAsset/Data/ | プレイヤー強攻撃 |
| PLACEHOLDER_EnemyAttack | Assets/MyAsset/Data/ | 敵攻撃 |
| PLACEHOLDER_BossSlam | Assets/MyAsset/Data/ | ボス叩きつけ攻撃 |
| PLACEHOLDER_CompanionAttack | Assets/MyAsset/Data/ | 仲間攻撃 |

## GameManager 構成

TestSceneBuilderがシーンに配置するGameManager:
- GameManager コンポーネント
- AutoInputTester コンポーネント（enableOnStart = true）
- DamagePopupController コンポーネント
- CameraController コンポーネント（MainCameraにアタッチ）

## CLIInternal メニュー項目

| メニューパス | 機能 |
|-------------|------|
| Tools/CLIInternal/Build Test Scene | ダイアログなしでテストシーン構築 |
| Tools/CLIInternal/Run Auto Input All | 全テスト有効でAutoInput設定 |
| Tools/CLIInternal/Run Auto Input Combat | 戦闘系のみ有効 |
| Tools/CLIInternal/Run Auto Input Movement | 移動系のみ有効 |
| Tools/CLIInternal/Run Auto Input Composite | 複合入力系のみ有効 |
