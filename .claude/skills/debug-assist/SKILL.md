---
name: debug-assist
description: Debug Unity issues via MCP - read console errors, inspect scene, take screenshots, and suggest fixes.
user-invocable: true
argument-hint: [error description or "check"]
---

# Debug Assist: $ARGUMENTS

MCP経由でUnityの問題を調査し、修正案を提示する。

## "check" モード（引数なし or "check"）

問題が不明な場合、まず全体を確認する:

### ステップ1: コンソールエラー確認
```python
read_console(action="get", types=["error", "exception"], count=30, format="detailed", include_stacktrace=True)
```

### ステップ2: 警告確認
```python
read_console(action="get", types=["warning"], count=20)
```

### ステップ3: シーン状態確認
```python
manage_scene(action="get_hierarchy", page_size=100)
```

### ステップ4: スクリーンショット
```python
manage_scene(action="screenshot", include_image=True, max_resolution=512)
```

### ステップ5: 問題のまとめと修正案提示

## エラー指定モード（具体的なエラー記述あり）

ユーザーが報告した問題に対して調査する。

### よくあるパターンと調査手順

| 問題 | 調査方法 |
|------|---------|
| プレイヤーが地面に立てない | TilemapCollider2D確認、Tile.colliderType確認、GroundLayer設定確認 |
| NullReferenceException | スタックトレースから該当コンポーネント特定→参照切れチェック |
| 操作が効かない | InputSystem設定確認、InputActionAsset確認 |
| カメラが動かない | MainCameraタグ確認、CameraFollow設定確認 |
| UIが表示されない | Canvas確認、EventSystem確認、UIDocument確認 |
| 壁をすり抜ける | Collider2D確認、Rigidbody2D設定確認、Layer設定確認 |

### 調査の流れ

1. **エラーの切り分け**: コンソールログから原因のカテゴリを特定
   - コンパイルエラー → スクリプト修正
   - ランタイムエラー → 参照・設定の問題
   - 無エラーだが動かない → Unity設定の暗黙知問題

2. **関連オブジェクト調査**: MCP経由で該当GameObjectを検索・確認
   ```python
   find_gameobjects(search_term="問題のオブジェクト", search_method="by_name")
   manage_components(action="get", target="instance_id")
   ```

3. **修正案提示**:
   - コードの修正が必要 → 具体的なコード変更を提案
   - Unity設定の修正が必要 → MCP経由で修正 or 手順を案内
   - 人間が対応すべき内容 → 手順を明確に説明

## 既知の暗黙知問題チェックリスト

パイプラインで過去に発生した問題:
- [ ] Tile.ColliderType が None になっている（Grid に設定が必要）
- [ ] LayerMask のデフォルト値が 0（地面判定不可）
- [ ] Camera.main が null（MainCamera タグ未設定）
- [ ] Input System の API ミスマッチ（旧API呼び出し）
- [ ] .meta ファイルの不整合
- [ ] asmdef の参照不足

## 出力

```
=== Debug Report ===

問題: [問題の要約]
原因: [根本原因]
カテゴリ: [コード/Unity設定/暗黙知/不明]

修正案:
1. [具体的な修正手順]
2. [必要であれば追加手順]

関連する過去の問題: [あれば参照]
```
