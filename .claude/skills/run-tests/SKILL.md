---
name: run-tests
description: Run Unity tests and report results
user-invocable: true
argument-hint: [EditMode|PlayMode|All] [--feature FeatureName] [--watch]
---

# Run Tests: $ARGUMENTS

Unity Test Frameworkでテストを実行し、結果をレポートする。

## このスキルの使い所

- **単純な Unity Test Runner 実行のみ**を担当する。テスト設計やオーケストレーションはしない
- 典型例: 機能実装後の Pass 確認、CI 的な回帰チェック、feature-db 更新
- シーン構築・複数機能の一括検証・バグ修正ループが必要なら `/playtest` を使う
  （`/playtest` は内部的に本スキルを呼ばず、直接 Unity CLI/MCP を叩く）

## テスト実行方法（優先順位）

### 方法1: MCP経由（Unityエディタが起動中の場合 — 推奨）

```python
# テスト実行（非同期）
result = run_tests(mode="EditMode")  # or "PlayMode"
job_id = result["job_id"]

# 完了待ち
result = get_test_job(job_id=job_id, wait_timeout=120, include_failed_tests=True)
```

MCP経由のメリット:
- エディタ起動済みなら高速（バッチモード起動の待ち時間なし）
- 失敗テストの詳細を直接取得可能
- コンソールエラーも同時に確認可能

### 方法2: CLI（エディタが閉じている場合）

```bash
"C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe" \
  -quit -batchmode \
  -projectPath "C:\Users\tatuk\Desktop\GameDev\SisterGame" \
  -runTests -testPlatform EditMode \
  -testResults TestResults.xml
```

## テスト実行後の追加チェック

### コンソールエラー確認（MCP経由）

テスト自体はPassしていても、ランタイムエラーが出ている場合がある。

```python
read_console(
    action="get",
    types=["error", "warning"],
    count=20,
    format="detailed"
)
```

**重要**: 以下のパターンに注意:
- テストPassだがコンソールにNullReferenceException → 実行時に問題あり
- `MissingComponentException` → コンポーネント未アタッチ
- `LayerMask` / `Tag` 関連のwarning → Unity設定の問題

### シーン検証（MCP経由・オプション）

`--watch` オプション指定時、テスト後にシーンの健全性も確認する:

```python
# シーン階層を取得
manage_scene(action="get_hierarchy", page_size=100)

# スクリーンショットで視覚確認
manage_scene(action="screenshot", include_image=True, max_resolution=512)
```

## 結果解析

### TestResults.xml 解析（CLI使用時）
TestResults.xml を読み込んで要約する。

### レポート出力

```
=== Test Results ===
Platform: [EditMode|PlayMode]
Total: N | Passed: N | Failed: N | Skipped: N
Console Errors: N（テスト外のエラー）

[失敗テストがある場合]
FAILED:
- TestName: エラーメッセージ

[コンソールエラーがある場合]
CONSOLE ERRORS:
- エラーメッセージ（テスト外で発生）
```

## feature-db 更新

```bash
python tools/feature-db.py update "機能名" --test-passed N --test-failed N
```

`--feature FeatureName` 指定時は、そのfeatureのテストファイルのみを実行対象とする。

## 特定機能のテスト実行

`--feature` オプションでfeature-dbから対象テストファイルを特定し、そのテストのみ実行する。

```bash
# feature-dbからテストファイルを取得
python tools/feature-db.py get "FeatureName"
# → tests: ["Assets/Tests/EditMode/FeatureTests.cs"]

# MCP経由で特定テストを実行
run_tests(mode="EditMode", test_names=["FeatureTests.TestMethod1", "FeatureTests.TestMethod2"])
```
