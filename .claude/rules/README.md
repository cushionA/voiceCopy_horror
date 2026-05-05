# `.claude/rules/` — モジュラールール運用ガイド

このディレクトリは **CLAUDE.md を分割して管理**するためのモジュラールール置き場。
各ファイルは特定の作業コンテキストで Claude が参照すべき規約を記載する。

## ロードの仕組み（2 系統併用）

### 1. `paths:` frontmatter（SisterGame 独自）
ファイル冒頭の frontmatter に `paths:` を書くと、該当ディレクトリでの作業時に自動参照対象になる。
（`/design-systems` スキルが `architecture.md` を更新する際にこの仕組みに依存）

```yaml
---
description: ...
paths:
  - "Assets/MyAsset/**/*.cs"
  - "Assets/Tests/**/*.cs"
---
```

### 2. path-scoped CLAUDE.md（Claude Code 公式機能）
ディレクトリ直下に `CLAUDE.md` を置くと、そのディレクトリで作業時に自動ロードされる。
`@../../.claude/rules/xxx.md` で rules ファイルを明示的にインポートする。

```
Assets/MyAsset/CLAUDE.md   → architecture.md + unity-conventions.md + asset-workflow.md
Assets/Tests/CLAUDE.md     → test-driven.md + unity-conventions.md + architecture.md
Assets/Scenes/CLAUDE.md    → asset-workflow.md + git-workflow.md（.meta セット / シーン保存）
```

### アセット配置時の CLAUDE.md 判断表

| 配置先 | CLAUDE.md 配置 | 根拠 rules |
|-------|---------------|-----------|
| `Assets/MyAsset/` | 配置済み | architecture / unity-conventions / asset-workflow |
| `Assets/Tests/` | 配置済み | test-driven / unity-conventions / architecture |
| `Assets/Scenes/` | 配置済み | asset-workflow / git-workflow |
| `Assets/Sprites/`, `Assets/Audio/`, `Assets/Models/`, `Assets/Prefabs/` 等を新設する場合 | **新規配置推奨** | asset-workflow（命名規則、Addressable グループ） |
| `Assets/Resources/` | 配置非推奨（そもそも新規利用を避ける） | asset-workflow — Addressable 推奨 |
| `Assets/Plugins/`, `Assets/ThirdParty/`, `Assets/AnyPortrait/` 等の外部ライブラリ | **配置しない**（触らない領域） | - |
| `Assets/Settings/`, `Assets/Gizmos/`, `Assets/Editor Default Resources/` | 配置不要（Unity 標準、編集機会少） | - |

**両方を併用**する理由: `paths:` frontmatter の公式動作保証が不明なため、公式機能（path-scoped CLAUDE.md + `@` インポート）で補完する二重保険方式。

## ファイル一覧

| ファイル | 用途 | `paths:` 設定 | インポート元 |
|---------|------|--------------|-------------|
| `architecture.md` | SoA / GameManager / Ability 等の設計原則 | `Assets/MyAsset/**/*.cs`, `Assets/Tests/**/*.cs` | Assets/MyAsset/CLAUDE.md, Assets/Tests/CLAUDE.md |
| `unity-conventions.md` | 命名規則 / パフォーマンス規約 / マジックナンバー禁止等 | 未設定 | Assets/MyAsset/CLAUDE.md, Assets/Tests/CLAUDE.md |
| `asset-workflow.md` | プレースホルダー / Addressable グループ / ラベル | 未設定 | Assets/MyAsset/CLAUDE.md |
| `test-driven.md` | TDD ワークフロー / 結合テスト 3 観点 | 未設定 | Assets/Tests/CLAUDE.md |
| `git-workflow.md` | ブランチ戦略 / コミット規約 / PR レビュー観点 | 未設定（全体に適用） | CLAUDE.md（ルート）から参照 |
| `template-usage.md` | テンプレートレジストリ確認手順 | 未設定 | CLAUDE.md（ルート）から参照 |
| `lint.md` | lint hook 運用ガイド (検査内容 / 誤検知抑止 / phase 切替条件) | 未設定（全体に適用） | CLAUDE.md（ルート）から参照（Wave 2 Phase 11 P11-T7） |
| `lint-patterns.json` | lint パターン source of truth (40 パターン) | - | `tools/lint_check.py` が読み込む |
| `lint-patterns.schema.json` | lint-patterns.json の JSON Schema (draft-07) | - | スキーマ検証 |
| `lint-observation-log.md` | lint hook 誤検知 / 真検知の観察ログ (Phase 11 P11-T6) | - | 観察期間中の手動更新 |
| `wave0-audit.md` | Wave 0 精読成果 (40 lint パターン対応表 / TDD 3 分離 / PR レビュー 4 観点) | - | Phase 11/13/25 で参照 |
| `security-known.md` / `security-patterns.json` | セキュリティ既知リスクと検出パターン | - | `tools/pr-validate.py` が読み込む |
| `ralph-overnight.md` | Wave 5 Phase 18 — Ralph 夜間バッチ運用ルール (起動前チェック / 推奨タスク / Sandbox 前提 / ロールバック) | 未設定（全体に適用） | CLAUDE.md（ルート）から参照（Wave 5 Phase 18） |
| `README.md` | 本ファイル | - | - |

## 運用ルール

### 更新時の影響範囲
- **architecture.md を更新**: Assets/MyAsset 配下全コード + テストコードに即時影響
- **unity-conventions.md を更新**: ランタイムコード全体（新規/既存問わず）に影響
- **asset-workflow.md を更新**: Addressable 設定 + アセット配置に影響
- **test-driven.md を更新**: テスト追加時の命名・結合テスト観点に影響
- **git-workflow.md を更新**: 以降のコミット / PR レビュー規約に即時影響
- **lint.md / lint-patterns.json を更新**: PostToolUse hook の動作に即時影響（誤検知調整・phase 昇格時に編集）

### 新規 rules ファイル追加時
1. frontmatter に `description:` を必ず書く（目的説明）
2. 適用範囲を `paths:` で限定できるなら明記
3. 対応する path-scoped CLAUDE.md を追加 or 既存のものに `@` インポート行追加
4. 本 README.md の「ファイル一覧」表を更新
5. CLAUDE.md トップからの参照（`詳細: .claude/rules/xxx.md`）を追加

### 重複の回避
複数の rules ファイルで同じルールを繰り返すのは禁止。
- **例**: GetComponent キャッシュは `unity-conventions.md` に集約、`architecture.md` からは「パフォーマンスは unity-conventions 参照」と書く
- **例**: `.meta` セット管理は `git-workflow.md` に集約、CLAUDE.md 本体からは削除

### rules と CLAUDE.md 本体の役割分担
| 内容 | 置き場所 |
|------|---------|
| 環境情報（Unity パス等） | CLAUDE.md 本体（短く） |
| パイプライン主要フロー | CLAUDE.md 本体 |
| 用語定義 | CLAUDE.md 本体 |
| アーキテクチャ原則 | `rules/architecture.md` |
| コード規約（詳細） | `rules/unity-conventions.md` |
| TDD 手順（詳細） | `rules/test-driven.md` |
| Git 運用（詳細） | `rules/git-workflow.md` |
| アセット管理（詳細） | `rules/asset-workflow.md` |

CLAUDE.md 本体は **2.5k トークン（≈100-200 行）以下**を目標とする（[Boris Cherny 基準](https://www.humanlayer.dev/blog/writing-a-good-claude-md) 参照）。

## 今後の拡張予定

- `rules/lint-patterns.json` — 静的分析 hook 用パターン定義（Phase 11 で追加予定）
- `rules/lint.md` — 静的分析の運用説明（Phase 11 で追加予定）
- `rules/security-known.md` — 既知 CVE と対策（Phase 21 で追加予定）
- `rules/anti-patterns.md` — 失敗パターン辞書（Phase 25 で追加予定）
- `rules/sandbox.md` — Sandbox 運用ルール（Phase 20 で追加予定）
