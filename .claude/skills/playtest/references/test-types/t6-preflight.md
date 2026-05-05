# T6: コンポーネント整合性テスト（プリフライト） — 実行前整合性チェックの専門家

## 役割
テスト対象機能の依存コンポーネント・レイヤー・シーン構成を読み、テスト実行前に必要な整合性チェック項目を設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能が依存するコンポーネント（RequireComponent、GetComponent呼び出し）
- 機能が前提とするレイヤー設定（Physics2D衝突マトリクス）
- 機能が前提とするシーン構成（GameManager、特定タグのオブジェクト等）

### 設計手順
1. **必須コンポーネント列挙**: 実装の[RequireComponent]属性とGetComponent呼び出しから抽出
2. **レイヤー依存列挙**: Physics2D.OverlapXxx、OnTriggerEnter2D等からレイヤー要件を特定
3. **シングルトン依存列挙**: GameManager.Instance等の参照を特定
4. **ScriptableObject依存列挙**: SerializeFieldで参照されるSO（AIInfo, AttackInfo等）
5. **チェック項目化**: 各依存を「存在するか」「値が正しいか」のEval文に変換

### 設計品質基準
- 機能のGetComponent/FindがNullReferenceを起こさない保証
- 物理衝突が期待通りに動くレイヤー設定の保証
- テストシーンに必要な全オブジェクトが存在する保証

## 実行手段
- `/unicli`: GameObject.Find --tag / --name / --requiredComponents
- `/unicli`: GameObject.GetComponents
- `/unicli`: Eval
- `/unicli`: Prefab.GetStatus

## 実行タイミング
- **FULL_WORKFLOW の Step 0d**（シーンビルド直後、テスト実行前）
- **batch-test のグループ実行前**（全機能共通で1回）

## チェック項目

### 1. キャラクターレイヤー
```bash
# Player = Layer 12
unicli exec Eval --code "Debug.Log(GameObject.FindWithTag(\"Player\").layer);"
# → 12 であること

# Enemy = Layer 13 or 14
unicli exec Eval --code "foreach(var e in GameObject.FindGameObjectsWithTag(\"Enemy\")) Debug.Log(e.name + \":\" + e.layer);"
# → 全て 13 or 14 であること
```

### 2. HitBox レイヤー
```bash
# PlayerHitbox = Layer 10, EnemyHitbox = Layer 11
unicli exec Eval --code "var hbs = GameObject.FindObjectsByType<HitBox>(FindObjectsSortMode.None); foreach(var h in hbs) Debug.Log(h.name + \":\" + h.gameObject.layer);"
```

### 3. 必須コンポーネント存在
```bash
# プレイヤー必須コンポーネント
unicli exec GameObject.GetComponents --name "Player"
# → BaseCharacter, PlayerInputHandler, ActionExecutorController が含まれること

# 敵必須コンポーネント
unicli exec GameObject.GetComponents --tag "Enemy"
# → BaseCharacter, AIBrain が含まれること
```

### 4. GameManager初期化
```bash
unicli exec Eval --code "Debug.Log(GameManager.Instance != null);"
unicli exec Eval --code "Debug.Log(GameManager.Data != null);"
```

### 5. プレハブ整合性
```bash
unicli exec Prefab.GetStatus --name "Player"
# → overrides が意図したものか確認
```

### 6. AutoInputTester設定（T2実行前のみ）
```bash
unicli exec GameObject.Find --requiredComponents "AutoInputTester"
# → 存在すること、enabledであること
```

## 設計指針
- 全チェックをまとめて実行し、全結果を一括報告
- 1つでもFailなら他テストを**中断**（修正コストの無駄を防ぐ）
- Fix提案: どのオブジェクトの何が間違っているかを具体的に報告
- PlayMode進入前にEditModeで実行できるチェックを優先

## 結果判定
- 全チェックPass → 他テストに進む
- 1つでもFail → REPORT_PREFLIGHT_FAILURE → END（他テスト実行しない）
