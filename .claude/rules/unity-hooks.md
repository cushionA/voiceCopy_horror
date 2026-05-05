---
description: Unity 特化 hook の用途・有効化方法・注意点 (Wave 3 Phase 22)
---

# Unity-specific hooks (Wave 3 Phase 22)

PostToolUse / pre-build / post-build / pre-release の 4 種類の hook を Unity プロジェクト向けに整備した雛形と運用ガイド。
**本 PR では雛形のみ配置、settings.json への登録はユーザー判断**。

## 4 つの hook

| hook スクリプト | トリガー | 用途 |
|----------------|---------|------|
| `.claude/hooks/unity-console-check.sh` | PostToolUse(Write/Edit/MultiEdit) | unity-mcp `read_console` 連動でエラー検出 (P22-T1) |
| `.claude/hooks/pre-build-validate.sh` | ビルド前 | placeholder 数 / asmdef / Addressable 設定検証 (P22-T2) |
| `.claude/hooks/post-build-test.sh` | ビルド後 | Unity CLI で PlayMode テスト実行 (P22-T3) |
| `.claude/hooks/pre-release-size-check.sh` | リリース前 | APK / IPA / exe サイズ回帰検出 (P22-T4) |

## 現状 (2026-04-25)

すべて**雛形実装**として配置。**UniCli (`.claude/skills/unicli/`) を最優先 backend** として動作する。Editor 起動中なら Named Pipe IPC で最速・最軽量。Editor 未起動・UniCli 未インストール環境では skip / batch mode フォールバック。

### Backend 優先順序（UniCli 優先方針）

> **本プロジェクトでは UniCli を最優先で使う。**
> Named Pipe IPC で起動コストがほぼゼロ、Editor のロックも競合しない。
> MCP は将来 CLI が整備された時の補助、batch は CI 専用と位置づける。

| 優先度 | backend | 条件 | 特徴 |
|-------|---------|------|------|
| **🥇 第一選択** | **unicli** | Unity Editor 起動中 + UniCli インストール済み | **最速・最軽量** (Named Pipe IPC)、ロック競合なし |
| 🥈 第二（将来） | claude-mcp | MCP CLI 整備後（現状未確立） | unity-mcp サーバー経由 |
| 🥉 第三（CI） | batch | UNITY_PATH 指定 + Editor 未起動 | 低速（フルロード）、CI 専用 |
| ⏸ 退避 | skip | いずれも不可 | warning なしで exit（開発を止めない） |

各 hook で `UNITY_CLI_BACKEND=unicli\|mcp\|batch\|auto` (デフォルト `auto` = unicli 最優先) で明示制御可能。
**ローカル開発では `unicli check` で接続を確認しておく**ことを推奨（接続失敗時は warning なしで skip するため、hook が動いていない事に気付けない）。

### 各 hook の実装状況

| hook | unicli backend | batch backend | mcp backend |
|------|----------------|---------------|-------------|
| `unity-console-check.sh` | ✅ `Console.GetLog --json` で error 件数取得 | - | TODO |
| `pre-build-validate.sh` | TODO (`unicli exec` で asmdef 検証) | shell スタブ実装済 | - |
| `post-build-test.sh` | ✅ `TestRunner.RunPlayMode --json` | ✅ `Unity -batchmode -runTests` | - |
| `pre-release-size-check.sh` | - (ファイルシステムのみ) | - | - |

## 有効化方法 (将来)

### PostToolUse hook (unity-console-check)

`.claude/settings.json` の PostToolUse に追加:

```jsonc
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/post-edit-dispatch.sh" },
          { "type": "command", "command": "bash .claude/hooks/unity-console-check.sh" }
        ]
      }
    ]
  }
}
```

**注意**: 既存の `post-edit-dispatch.sh`（lint hook）と競合しないよう、配列で並列に登録するか、dispatcher 内に統合する。

### pre-build / post-build / pre-release

- ローカル: `Makefile` または `tools/build.sh` から呼び出し
- CI: GitHub Actions の build job の前後ステップで実行

## 環境変数

| 変数 | デフォルト | 用途 |
|------|-----------|------|
| `UNITY_HOOK_PHASE` | warn | unity-console-check の error 昇格制御 |
| `UNITY_PATH` | `C:/Program Files/Unity/Hub/Editor/6000.3.9f1/Editor/Unity.exe` | post-build-test の Unity 実行パス |
| `BUILD_OUTPUT_DIR` | `Builds/` | pre-release-size-check の対象ディレクトリ |
| `SIZE_REGRESSION_THRESHOLD_PCT` | 10 | pre-release-size-check の警告閾値 |

## 注意点

- **Unity CLI のロック競合**: `post-build-test.sh` は Unity Editor が起動中だとロックエラーになる。MCP 経由 `run_tests` を推奨
- **placeholder アセット**: `pre-build-validate.sh` はリリースビルド時のみ placeholder 残存をエラー扱い。dev ビルドでは許容
- **サイズ履歴**: `.claude/build-size-history.tsv` に追記される。`.gitignore` に追加推奨（リリースタグ単位で git にコミットする運用も可）

## P22-T5〜T7 (外部 skill 輸入) について

WAVE_PLAN.md L783-786 の以下は **`docs/FUTURE_TASKS.md` 登録済み**:

- **P22-T5**: Unity App UI Plugin 動作確認 + 導入判定
- **P22-T6**: TheOne Studio skills の C# 9 規約と Architect/ 整合性チェック
- **P22-T7**: 選定した外部 skill を `.claude/skills/` にインポート

ライセンス精査・Architect 整合性確認・ユーザー判断が必要なため、本 PR では含めず将来タスクとして残す。

## 関連

- WAVE_PLAN.md L778-786 (Phase 22 タスク定義)
- 関連 PR (Phase 11 lint hook 既存): #47
- 関連 PR (Phase 13 TDD agent): #54
- `.claude/hooks/post-edit-dispatch.sh` — 既存 dispatcher (PR #47)
- `tools/lint_check.py` — 既存 lint 検査 (PR #47)
