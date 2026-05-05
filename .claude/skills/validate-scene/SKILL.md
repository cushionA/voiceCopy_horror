---
name: validate-scene
description: Validate Unity scene integrity via MCP (missing references, remaining placeholders, component issues, visual check)
user-invocable: true
argument-hint: [SceneName]
---

# Validate Scene: $ARGUMENTS

指定シーンの整合性をMCP経由で検証する。

## チェック項目

### 1. シーン階層確認（MCP）

```python
# シーンの全GameObjectを取得
manage_scene(action="get_hierarchy", page_size=100)
```

確認する内容:
- **Missing Scripts**: 削除されたスクリプトへの参照が残っていないか
- **Placeholder残存**: `[PLACEHOLDER]` プレフィックス付きGameObjectの一覧
- **Duplicate Names**: 同名GameObjectの検出
- **Empty GameObjects**: コンポーネントがTransformのみのGameObject

### 2. キーオブジェクト存在確認（MCP）

```python
# 必須オブジェクトの存在チェック
find_gameobjects(search_term="Player", search_method="by_name")
find_gameobjects(search_term="MainCamera", search_method="by_tag")
find_gameobjects(search_term="StageInitializer", search_method="by_component")
```

ゲームシーンの場合、以下が存在するか確認:
- Player オブジェクト
- MainCamera タグ付きカメラ
- 初期化コンポーネント（StageInitializer等）
- HUD / Canvas

### 3. コンソールエラー確認（MCP）

```python
read_console(action="get", types=["error"], count=20, format="detailed")
```

### 4. 視覚的検証（MCP・スクリーンショット）

```python
# 通常ビュー
manage_scene(action="screenshot", include_image=True, max_resolution=512)

# 6方向確認（3Dの場合）
manage_scene(action="screenshot", batch="surround", max_resolution=256)

# 特定オブジェクト周辺
manage_scene(action="screenshot", look_at="Player", max_resolution=512)
```

目視チェック:
- プレイヤーのスポーン位置は適切か（壁の中、空中でないか）
- 地面が正しくレンダリングされているか
- UIが画面内に収まっているか
- 明らかな配置ミスがないか

### 5. コンポーネント検証（MCP）

キーオブジェクトの重要プロパティを確認:

```python
# プレイヤーのコンポーネント状態
manage_components(action="get", target="Player")

# TilemapCollider2Dの存在確認（地面が踏めるか）
find_gameobjects(search_term="TilemapCollider2D", search_method="by_component")
```

## 出力フォーマット

```
=== Scene Validation: [SceneName] ===

ERRORS (must fix):
- [E001] Missing reference: [GO名].[コンポーネント].[プロパティ]
- [E002] Missing script: [GO名]
- [E003] Player spawn inside wall/void

WARNINGS (review):
- [W001] Placeholder: [PLACEHOLDER]GOName
- [W002] Duplicate name: "Enemy" (3 instances)
- [W003] Console warning: メッセージ

INFO:
- Total GameObjects: N
- Total Components: N
- Placeholders: N
- Screenshot: [確認結果のサマリー]
```

## 手順
1. MCP経由でシーン階層を取得
2. キーオブジェクトの存在確認
3. コンソールエラー確認
4. スクリーンショットで視覚的検証
5. コンポーネントの重要プロパティ確認
6. 結果をフォーマットに従ってレポート
