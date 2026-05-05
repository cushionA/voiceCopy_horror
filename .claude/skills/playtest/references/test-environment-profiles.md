# テスト環境プロファイル

テスト種別ごとに最適なシーン環境を定義する。
同一テストシーンを使い回す場合でも、テスト開始前に環境を適応させること。

## 原則

1. **テストが検証しない要素で干渉するものは無害化する** — 入力テスト中に敵に殺されてテスト不能になる事態を防ぐ
2. **テストが検証する要素は最適配置する** — AI検証時に攻撃範囲とヒットボックスが噛み合う距離に配置
3. **環境切替はテスト間で行う** — PlayModeセッション中でも `GameObject.SetActive` / `SetTransform` で動的切替可能
4. **プロファイルは参考であり、テスト内容から論理的に判断する** — ガードテストの入力検証なら敵は必要（攻撃してくる相手がいないとガードの検証にならない）。プロファイルを機械的に適用せず、「このテストには何が必要か」から環境を導出する

## 環境プロファイル定義

### PROFILE:SAFE_INPUT — 入力・移動テスト用

プレイヤーの入力→動作フローを検証する。外部干渉を排除。

```
敵キャラクター:     SetActive(false)  ← 攻撃してこないようにする
ボスキャラクター:   SetActive(false)
仲間キャラクター:   SetActive(false) or 遠方に退避 (x:-100)  ← 衝突干渉防止
ヒットボックス系:   親のSetActiveに従う
地形:              そのまま（移動テストに必要）
AutoInputTester:   有効
```

**適用テスト**: T2-AutoInput（移動系、攻撃モーション確認のみ）

### PROFILE:COMBAT_PVE — AI・ダメージ交換テスト用

敵AIの行動、ヒットボックス接触、ダメージ計算を検証する。

```
敵キャラクター:     SetActive(true)
                   攻撃範囲内に配置（ヒットボックスが実際に届く距離）
                   ※ k_DefaultAttackRange とヒットボックスサイズの整合性を事前確認
ボスキャラクター:   テスト対象なら有効、それ以外は無効
仲間キャラクター:   SetActive(true)、敵の近くに配置（被弾テスト）
AutoInputTester:   無効（Eval主導で検証するため）
```

**配置ルール（距離整合性）**:
- 敵の停止距離: `GameConstants.k_DefaultAttackRange` で確認
- ヒットボックス到達距離: `TestSceneBuilder` の hitboxOffset + hitboxSize/2 で計算
- **停止距離 > ヒットボックス到達距離 なら**: 敵を手動で近づけるか、攻撃範囲を調整
- 事前に `Eval` で実距離を検証してからテスト開始

**適用テスト**: T3-Snapshot（HP変動）、T7-Dynamic（攻撃範囲操作）

### PROFILE:COMPANION_AI — 仲間AI・連携テスト用

仲間の追従・攻撃・連携スキルを検証する。

```
敵キャラクター:     少数（1-2体）を有効、仲間の攻撃対象として配置
ボスキャラクター:   SetActive(false)
仲間キャラクター:   SetActive(true)、プレイヤー近傍に配置
プレイヤー:         定位置 or Eval で制御
AutoInputTester:   無効
```

**適用テスト**: T3-Snapshot（仲間HP/MP）、T7-Dynamic（追従距離操作）

### PROFILE:PROJECTILE — 飛翔体テスト用

飛翔体の生成・飛行・着弾を検証する。

```
敵キャラクター:     1体を有効、飛翔体の着弾先として配置
                   飛行経路上に障害物がない位置に調整
ボスキャラクター:   SetActive(false)
仲間キャラクター:   SetActive(false) — 飛翔体が仲間に当たる誤検出を防ぐ
AutoInputTester:   無効
```

**適用テスト**: T3-Snapshot（飛翔体存在確認）、T7-Dynamic（発射→着弾シーケンス）

### PROFILE:BOSS_ENCOUNTER — ボス戦テスト用

ボスAIのフェーズ遷移・特殊攻撃を検証する。

```
通常敵キャラクター: SetActive(false)
ボスキャラクター:   SetActive(true)
仲間キャラクター:   テスト内容に応じて有効/無効
プレイヤー:         ボスエリア内に配置
AutoInputTester:   無効
```

**適用テスト**: T3-Snapshot（ボスHP/フェーズ）、T7-Dynamic（フェーズ遷移トリガー）

### PROFILE:FULL_INTEGRATED — 全要素統合テスト用

全システムが連携して動作することを検証する。最終確認用。

```
全キャラクター:     SetActive(true)
全システム:         通常動作
AutoInputTester:   有効（フル入力シーケンス）
```

**注意**: プレイヤーが死亡する可能性がある。死亡した場合のリカバリ手段を事前に用意するか、HP回復を Eval で注入する。

**適用テスト**: T2-AutoInput（全カテゴリ）、T5-Performance

## 環境切替の実行方法

PlayMode中に `/unicli` で環境を切り替える:

```bash
# 敵を全て無効化
unicli exec Eval --code "foreach(var e in GameObject.FindGameObjectsWithTag(\"Enemy\")) e.SetActive(false);"

# 敵を全て有効化
unicli exec Eval --code "foreach(var e in GameObject.FindGameObjectsWithTag(\"Enemy\")) e.SetActive(true);"

# 仲間を退避
unicli exec GameObject.SetTransform --name "[PLACEHOLDER]CompanionCharacter" --position "-100,0,0"

# 仲間を復帰
unicli exec GameObject.SetTransform --name "[PLACEHOLDER]CompanionCharacter" --position "-3,2,0"

# 敵を攻撃範囲内に強制配置
unicli exec GameObject.SetTransform --name "Enemy_Melee_1" --position "1.5,2,0"

# プレイヤーHP回復（統合テスト中の死亡防止）
unicli exec Eval --code "var go=GameObject.FindWithTag(\"Player\"); var v=GameManager.Data.GetVitals(go.GetInstanceID()); /* HP回復ロジック */;"
```

## テスト種別→プロファイルマッピング

| テスト内容 | 推奨プロファイル | 理由 |
|-----------|----------------|------|
| プレイヤー移動・入力 | SAFE_INPUT | 外部干渉で死亡してテスト不能になるのを防止 |
| プレイヤー攻撃モーション | SAFE_INPUT | ヒットボックス発生は確認するが、被ダメは不要 |
| 敵AIの追跡・攻撃 | COMBAT_PVE | 敵が実際にターゲットに到達・攻撃する必要がある |
| ダメージ計算・HP変動 | COMBAT_PVE | ヒットボックスが当たる距離に配置が必要 |
| 仲間AI追従・攻撃 | COMPANION_AI | 仲間の行動対象となる敵が必要 |
| 飛翔体発射・着弾 | PROJECTILE | 飛行経路確保と着弾先の敵が必要 |
| ボスフェーズ遷移 | BOSS_ENCOUNTER | ボスのみアクティブにして他の干渉を排除 |
| 全体統合確認 | FULL_INTEGRATED | 最終検証、死亡リスクあり |

## 環境構築のタイミング

```
GRAPH:FULL_WORKFLOW での環境切替タイミング:

  [4c. ENTER_PLAY]
    │
    ├─ APPLY PROFILE:SAFE_INPUT
    │   └─ T2 AutoInput 実行
    │
    ├─ APPLY PROFILE:COMBAT_PVE
    │   └─ T3/T7 AI・ダメージ検証
    │
    ├─ APPLY PROFILE:COMPANION_AI
    │   └─ T3/T7 仲間AI検証
    │
    ├─ APPLY PROFILE:PROJECTILE
    │   └─ T3/T7 飛翔体検証
    │
    ├─ APPLY PROFILE:FULL_INTEGRATED
    │   └─ T5 パフォーマンス計測
    │
    └─ [4g. EXIT_PLAY]
```

## 事前検証チェックリスト

環境プロファイル適用後、テスト実行前に確認すべき項目:

- [ ] テスト対象のGameObjectが `SetActive(true)` であること
- [ ] テスト対象外の危険なGameObject（敵等）が `SetActive(false)` であること
- [ ] 攻撃テストの場合、ヒットボックスと被弾対象の距離が実際に届く範囲か
- [ ] SoAコンテナにテスト対象キャラクターが登録されているか（`GameManager.IsCharacterValid`）
- [ ] 被弾テストの場合、DamageReceiverコンポーネントが有効か
