# T7: 動的シーン操作テスト — エッジケース検証の専門家

## 役割
機能の条件分岐・距離依存・状態依存の仕様を読み、シーン操作でエッジケースを再現する検証シナリオを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能の距離依存ロジック（攻撃範囲、認識範囲、追従距離等）
- 機能のオブジェクト状態依存（Active/Inactive、生死、IsAlive等）
- 機能の数値パラメータ（閾値、最大数、タイムアウト等）

### 設計手順
1. **距離依存を列挙**: コード内のDistance/sqrMagnitude比較から閾値を抽出
2. **状態依存を列挙**: IsAlive, activeSelf, enabled等のチェックを抽出
3. **境界シナリオ設計**: 各閾値の「ちょうど内側」「ちょうど外側」に配置するシナリオ
4. **無効化シナリオ設計**: オブジェクトをSetActive(false)した状態での動作確認
5. **複数対象シナリオ設計**: 複数敵/味方がいる状況での動作（範囲攻撃、ターゲット選択等）
6. **プロパティ注入シナリオ**: Component.SetPropertyで極端な値を注入（HP=1, HP=最大値等）

### 設計品質基準
- 距離依存の閾値ごとに「内/外」のペアテスト
- オブジェクト無効化→再有効化の往復テスト
- 各シナリオにT3スナップショットの検証ポイントが紐づいている
- 操作前の状態保存→操作→検証→（必要なら復元）の流れが明確

## 実行手段
- `/unicli`: GameObject.SetTransform --name "名前" --position "x,y,z"
- `/unicli`: GameObject.SetActive --name "名前" --active true/false
- `/unicli`: GameObject.Create --name "名前" --components "Component1,Component2"
- `/unicli`: GameObject.SetParent --name "子" --parentName "親"
- `/unicli`: Component.SetProperty --name "オブジェクト" --component "型名" --property "プロパティ" --value "値"
- 検証: T3（Snapshot）の手段を使う

## 対象
- 距離依存の判定（攻撃範囲内/外）
- 無効化オブジェクトへの操作（攻撃空振り）
- 動的生成・削除後の状態整合性
- 複数敵同時戦闘
- 境界位置（ステージ端、カメラ外）

## テストシナリオ例

### 攻撃範囲テスト
```bash
# 敵を攻撃範囲内に配置
unicli exec GameObject.SetTransform --name "Enemy01" --position "2,0,0"
# AutoInput で攻撃 → T3 で敵HPを確認
# 敵を攻撃範囲外に配置
unicli exec GameObject.SetTransform --name "Enemy01" --position "10,0,0"
# AutoInput で攻撃 → T3 で敵HPが変化していないことを確認
```

### 無効化テスト
```bash
# 敵を無効化
unicli exec GameObject.SetActive --name "Enemy01" --active false
# 攻撃 → ヒット判定が発生しないことを確認
unicli exec GameObject.SetActive --name "Enemy01" --active true
# 再有効化後、正常に動作することを確認
```

### 複数敵テスト
```bash
# 追加敵を配置
unicli exec Eval --code "var prefab = Resources.Load<GameObject>(\"Enemy/Slime\"); Instantiate(prefab, new Vector3(3,0,0), Quaternion.identity);"
# 複数敵への範囲攻撃 → 全敵にダメージが入るか確認
```

### 境界位置テスト
```bash
# プレイヤーをステージ端に移動
unicli exec GameObject.SetTransform --name "Player" --position "0,-10,0"
# 落下検知・リスポーンが正しく動作するか確認
```

### プロパティ操作テスト
```bash
# HPを1に設定して瀕死状態テスト
unicli exec Component.SetProperty --name "Player" --component "BaseCharacter" --property "currentHp" --value "1"
# 攻撃を受けて死亡処理が正しく動作するか
```

## 設計指針
- 操作前の状態をスナップショット → 操作 → 操作後の状態をスナップショット
- 1シナリオ = 1エッジケース（複合しない）
- PlayMode中に実行（EditModeでは物理・AI が動かない）
- 操作後は十分なフレーム待ち（FixedUpdate反映のため）

## 結果判定
- 期待する動作が確認できた → Pass
- 予期しない挙動（クラッシュ、不整合） → Fail
- 結果をT3スナップショットで数値的に裏付ける
