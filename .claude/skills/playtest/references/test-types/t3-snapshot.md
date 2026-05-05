# T3: シーン状態スナップショットテスト — ランタイム状態検証の専門家

## 役割
機能の状態変化仕様を読み、PlayMode中に外部からEvalで取得すべき検証ポイントを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能が管理する状態変数（HP, MP, フラグ, カウンタ等）
- 状態変化のトリガー（ダメージ、回復、時間経過等）
- 不変条件（HP >= 0, スタミナ <= 最大値 等）

### 設計手順
1. **状態変数を列挙**: 実装コードから外部から読める状態（public/SerializeField）を抽出
2. **変化前→変化後のペアを設計**: 各トリガーに対して「取得→操作→再取得→比較」
3. **不変条件を列挙**: 「どんな操作をしてもこの条件は破れない」を検証項目化
4. **SoAアクセスパスを確認**: GameManager.Data 経由のアクセス方法を特定
5. **オブジェクト存在/消滅の検証**: 敵撃破、アイテム消費等で存在チェック

### 設計品質基準
- 全状態変数に最低1つの変化前後検証
- 不変条件（クランプ、範囲制限）の境界値検証
- SoAデータとMonoBehaviourの値が一致する検証（該当時）
- 検証タイミングが明示されている（「FixedUpdate N回後」等）

## 実行手段
- `/unicli`: Eval --code "C#式"
- `/unicli`: GameObject.Find --name "オブジェクト名"
- `/unicli`: GameObject.GetComponents --name "オブジェクト名"

## 検証パターン

### HP/リソース値の取得
```bash
unicli exec Eval --code "Debug.Log(GameManager.Data.GetVitals(hash).hp);"
```

### レイヤー確認
```bash
unicli exec Eval --code "Debug.Log(GameObject.Find(\"Player\").layer);"
```

### コンポーネント状態
```bash
unicli exec GameObject.GetComponents --name "Player"
```

### SoAデータ確認
```bash
unicli exec Eval --code "Debug.Log(GameManager.Data != null);"
unicli exec Eval --code "var go = GameObject.Find(\"Player\"); Debug.Log(GameManager.Data.GetVitals(go.GetInstanceID()).hp);"
```

### オブジェクト数
```bash
unicli exec Eval --code "Debug.Log(GameObject.FindGameObjectsWithTag(\"Enemy\").Length);"
```

## 設計指針
- 1スナップショット = 1つの検証項目（複雑なEvalは分割）
- 期待値と実測値を明示的に比較
- PlayMode中のタイミングに注意: FixedUpdate完了後に取得すること
- 複数フレーム待ちが必要な場合はAutoInput（T2）と組み合わせる

## 結果判定
- 期待値と一致 → Pass
- 不一致 → Fail（期待値・実測値をレポートに記載）
