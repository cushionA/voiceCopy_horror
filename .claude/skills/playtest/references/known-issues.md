# Known Issues — エディタ実行テストで発見された問題集

過去のプレイテストセッションで発見・修正した問題。再発防止と原因特定の高速化に使用。

## Issue 1: キャラクター同士がすり抜ける

**症状**: プレイヤーと敵が物理的にすり抜ける
**根本原因**: TestSceneBuilderがキャラクターをレイヤー7/8/9に配置していたが、CharacterCollisionControllerはレイヤー12/13/14を操作する
**修正**: 全キャラクターをレイヤー12 (`GameConstants.k_LayerCharaPassThrough`) に統一
**確認方法**: `unicli exec Eval --code "GameObject.Find(\"Player\").layer"` → 12であること

## Issue 2: 攻撃が当たらない

**症状**: プレイヤーの攻撃も敵の攻撃もヒットしない
**根本原因**: Issue 1と同根。CollisionMatrixSetupはレイヤー10(PlayerHitbox)↔12(CharaPassThrough)の衝突を有効化するが、キャラクターが12にいなかった。さらにTestSceneBuilder.SetupPhysicsLayers()が12↔ヒットボックスの衝突を明示的に無効化していた。
**修正**:
- キャラクターをレイヤー12に統一
- SetupPhysicsLayers()をCollisionMatrixSetup.SetupCollisionMatrix()に委譲
- ヒットボックス↔Ground(6)の衝突を無効化（地面にヒットしないように）
**確認方法**: Physics2D.GetIgnoreLayerCollision(10, 12) が false であること

## Issue 3: 強攻撃が二回発動する

**症状**: 強攻撃ボタンを押して離すと攻撃が2回出る
**根本原因**: PollAttackButtons()が押下時にもリリース時にも_attackBufferをセットしていた
**修正**: 強攻撃をリリース時確定方式に変更（押下時はホールド計測開始のみ、リリース時に秒数で通常/チャージを判定）
**設計**:
- 短押し（< _chargeThreshold）→ 通常強攻撃
- 長押し（>= _chargeThreshold）→ チャージ強攻撃
- 弱攻撃は従来通り押下時即発動（短押し=通常、長押しリリース=チャージ）
**ファイル**: `Assets/MyAsset/Runtime/Input/PlayerInputHandler.cs` PollAttackButtons()

## Issue 4: 死亡キャラクターに攻撃が当たる

**症状**: 倒した敵の死体に攻撃がヒットし続ける
**根本原因**: HitBox.OnTriggerEnter2D()にIsAliveチェックがなかった
**修正**: `if (!receiver.IsAlive) { return; }` を早期リターンとして追加
**ファイル**: `Assets/MyAsset/Runtime/Combat/HitBox.cs`

## Issue 5: 攻撃中に移動できる

**症状**: 攻撃モーション中もプレイヤーが移動できる
**根本原因**: PlayerCharacter.FixedUpdate()がIsActionExecutorBusy()を移動計算に反映していなかった
**修正**:
- `actionBusy`の場合`horizontalSpeed = 0f`に設定
- スプリントもactionBusy時は無効化
**ファイル**: `Assets/MyAsset/Runtime/Character/PlayerCharacter.cs`

## Issue 6: 同陣営への攻撃（Friendly Fire）

**症状**: レイヤー統一後、敵の攻撃が他の敵にもヒットする可能性
**根本原因**: 全キャラクターが同一レイヤーに移動したため、ヒットボックスが全員に到達する
**修正**: HitBox.OnTriggerEnter2D()で`CharacterBelong`（陣営）チェックを追加。同陣営なら早期リターン
**ファイル**: `Assets/MyAsset/Runtime/Combat/HitBox.cs`

## Issue 7: 静的候補リストのデータ競合

**症状**: 複数の敵が同フレームでFixedUpdateを実行すると候補リストが上書きされる
**根本原因**: EnemyCharacter/CompanionCharacterの`s_Candidates`がstaticだった
**修正**: インスタンスごとの`_candidates`フィールドに変更
**ファイル**: `Assets/MyAsset/Runtime/Character/EnemyCharacter.cs`, `CompanionCharacter.cs`

## 調査パターン（チェックリスト）

物理/衝突問題の場合:
1. キャラクターのレイヤー確認 → 12/13/14のいずれかか？
2. CollisionMatrixSetup.SetupCollisionMatrix()が呼ばれているか？
3. ヒットボックスのレイヤー → 10(Player系) or 11(Enemy系)か？
4. HitBox.Initialize()でownerHashが設定されているか？

攻撃が効かない場合:
1. ActionExecutorController.ExecuteAction()が呼ばれているか？
2. AttackInfoがnullでないか？
3. HitBox Collider2Dの isTrigger = true か？
4. AnimationBridgeがアニメーションイベントを受けているか？
5. DamageReceiver.IsAlive が true か？

AI が動かない場合:
1. AIInfoアセットが設定されているか？
2. GameManager.Dataが初期化済みか？
3. CharacterRegistryに登録されているか？
4. EnemyController/CompanionController が null でないか？
5. 候補リスト（candidates）が空でないか？
