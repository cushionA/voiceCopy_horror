---
name: build-pipeline
description: Orchestrate the full game creation pipeline from concept to implementation. Chains design, planning, and implementation skills automatically.
user-invocable: true
argument-hint: <game concept or "continue">
---

# Build Pipeline: $ARGUMENTS

ゲームコンセプトから設計→計画→実装まで進行する。
**人間との対話を重視**し、各フェーズでユーザー確認を挟む。
"continue" が渡された場合は現在の進行状態から再開する。

## Layer

このスキルは Two-layer 構成（[詳細](../_two-layer-design.md)）で運用している。

- **base.md** — 状態機械・I/O・エラー処理の汎用ロジック（プロジェクト非依存）。実行時に併読する: `@base.md`
- **本ファイル (SKILL.md, overlay)** — SisterGame 固有の呼び先 skill / 参照 rules / artifact / Git 規約のバインディング

base 層が要求する I/O コントラクトに対し、overlay は次のように具体値を供給する:

| base が要求する項目 | SisterGame での実体 |
|--------------------|----------------------|
| state JSON のパス | `designs/pipeline-state.json` |
| 機能 DB 操作 | `python tools/feature-db.py list/update/summary` |
| 設計 phase で呼ぶ skill | `/design-game`, `/design-systems` |
| 実装 phase で呼ぶ skill | `/create-feature` |
| レビュー phase で呼ぶ skill | `/simplify` + MCP `run_tests` / `read_console` |
| branch 命名 | `feature/pipeline-{コンセプト短縮名}` |
| コミット規約 | `[種類](範囲): 日本語タイトル` + `Co-Authored-By: Claude Opus 4.7` |
| アーティファクト出力先 | `designs/` 配下（GDD, systems, sprints, asset-spec.json） |

## パイプラインの責任範囲

1. **設計補助** — 対話型要件整理、ジャンル調査、ワールド設定、共通設計、asmdef 設計
2. **機能単位の実装と管理** — TDD 実装、feature-db 管理、重複検出
3. **テストの設計と実行** — 単体/結合テスト、MCP 経由テスト、コンソール監視
4. **その他制作補助** — HTML マップ案、パラメータ設計、図表、デバッグ支援等

### パイプラインが**やらない**こと
- タイル配置によるステージ自動生成（人間が主導）
- Unity シーンの自動構築（MCP 経由の検証・補助のみ）
- ユーザー確認なしの自律進行

## パイプライン全体フロー

base.md の状態機械に対して、各 phase で**何の skill を呼ぶか**を以下に定義する。

### Phase 1: 設計 (`phase = "design"`)

1. `/design-game` を実行
   - 対話型要件整理（コンセプト→GDD）
   - ワールド設定（`designs/asset-spec.json`）
   - ジャンル調査→不足機能提案
2. ユーザーに GDD を提示し確認 → **承認待ち**
3. `/design-systems section-1` を実行
   - 既存機能との照合
   - 共通設計の抽出
   - asmdef 設計
   - システム設計書作成（`designs/systems/`）
4. ユーザーにシステム設計を提示し確認 → **承認待ち**
5. state を更新: `phase: "planning"`

### Phase 2: 計画 (`phase = "planning"`)

旧 `/plan-sprint` は `/design-systems` に統合済み（2026-04-24）。
Phase 1 step 3 の `/design-systems` 実行内で以下が完了している:

- 既存機能との重複チェック
- 機能のカテゴリ分類（system / content）
- 依存解決・実装順序決定
- feature-db 登録
- スプリント計画出力（`designs/sprints/[セクション名].md`）

ユーザー承認後、state を更新: `phase: "implementation"`

### Phase 3: 実装 (`phase = "implementation"`)

`pendingFeatures` の先頭から順に:

1. `/create-feature {featureName}` を実行
2. テスト通過を確認
3. `completedFeatures` に移動（base.md の「機能完了」遷移）
4. state を更新
5. Git コミット + プッシュ
6. 次の機能へ → `pendingFeatures` が空になるまで繰り返す

全機能完了後:
- `python tools/feature-db.py summary` で進捗サマリー出力
- ユーザーに動作確認を案内

### Phase 4: レビュー (`phase = "review"`)

セクション実装完了後、2 段階のレビューを実施する。

#### Phase 4a: コードレビュー（自動）

`/simplify` を実行し、セクション内の全変更コードをレビュー・修正する。
修正後はテスト全体を再実行してリグレッションがないことを確認する。

#### Phase 4b: 検証と報告

1. テスト全体を実行（MCP 経由 `run_tests` または CLI）
2. コンソールエラーを確認（MCP 経由 `read_console`）
3. 結果をユーザーに報告
4. 人間作業のリストアップ:
   - 未配置アセット: `python tools/feature-db.py assets --status pending`
   - アニメーション設定
   - ビジュアル調整
   - ゲームフィール調整（ScriptableObject の値）

### セクション完了 → 次セクションへ

1. `currentSection` をインクリメント
2. `currentSection <= totalSections` なら:
   - `/design-systems section-{currentSection}` に戻る (Phase 1 step 3)
3. 全セクション完了なら: パイプライン完了（base.md の遷移ルールに従う）

## "continue" で呼ばれた場合

base.md の "continue" モード手順に従う。SisterGame では具体的に:

1. `designs/pipeline-state.json` を読み込む
2. `phase` と `pendingFeatures` から現在地を特定
3. 中断したところから再開

## ユーザー確認ポイント（base.md 「各フェーズ間の遷移ルール」の具体化）

- **設計 → 計画**: GDD と システム設計書をユーザーに提示
- **計画 → 実装**: スプリント計画（`designs/sprints/*.md`）をユーザーに提示
- **レビュー → 次セクション設計**: テスト結果と人間作業リストをユーザーに提示

## Git 運用（SisterGame 規約）

### パイプライン開始時
- main ブランチが最新か確認
- 新しい feature ブランチを作成: `feature/pipeline-{コンセプト短縮名}`

### 各フェーズでのコミット
- **設計完了時**: `docs(設計): GDD作成` / `docs(設計): セクションNのシステム設計・機能分解完了`
- **機能実装時**: `/create-feature` が各機能ごとにコミット+プッシュ

### コミット後の文脈クリーン
コミット実行後は `/compact` で文脈を圧縮してから次の作業に進む。

## 出力アーティファクト

- `designs/pipeline-state.json`（進行状態。base.md が読み書き対象とする）
- `designs/game-design.md`（GDD）
- `designs/asset-spec.json`（ワールド/タイル/PPU 設定）
- `designs/systems/*.md`（セクション別システム設計）
- `designs/sprints/*.md`（スプリント計画）
- 各 skill の通常出力（テスト、コード等）
