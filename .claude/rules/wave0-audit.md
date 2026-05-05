# Wave 0: `.claude/rules/` 精読抽出レポート

**実施日**: 2026-04-24
**対象**: `.claude/rules/` 配下 6 ファイル（合計 887 行）
**目的**: Phase 4/11/13/21/25 実装で利用する具体条項を抽出・永続化

---

## セクション A: path-scoped CLAUDE.md 配置判定

### A-1. `Assets/MyAsset/**/*.cs` 向け（コード実装時にロード）
- **architecture.md** — SoA/GameManager/ハッシュアクセス/Ability拡張/レイヤー構成/Section 1〜4 固有ルール（フロントマターで既に `paths: Assets/MyAsset/**/*.cs` 指定済）
- **unity-conventions.md** — 命名、マジックナンバー禁止、ライフサイクル順序、パフォーマンス規約（Update内アロケーション、GetComponent キャッシュ、CompareTag、sqrMagnitude）
- **asset-workflow.md（一部）** — `AssetReference` 使用、`AssetDatabase` ランタイム使用禁止、解放原則、条件コンパイルガード

### A-2. `Assets/Tests/**/*.cs` 向け
- **test-driven.md** — TDD ワークフロー、命名規則、Edit/Play Mode 判定、結合テスト 3 観点、テスト設計チェックリスト
- **architecture.md**（既存ロジック呼び出し検証のため） — 既存ユーティリティ（HpArmorLogic、ActionExecutor 等）の存在把握
- **unity-conventions.md（命名のみ）** — テストクラス名・メソッド名の PascalCase / camelCase

### A-3. アセット編集（Sprites/Models/Audio 配下）時
- **asset-workflow.md** — 配置先命名規則、Addressable グループ/ラベル/アドレス命名、`[PLACEHOLDER]` プレフィックス、ビルド除外
- **git-workflow.md の `.meta` 管理条項** — アセットと .meta のセットコミット
- **template-usage.md** — template-registry.json 確認手順（GameObject/Prefab 作成時）

### A-4. CLAUDE.md トップに残すべき普遍条項（短く）
- Unity パス / プロジェクトパス（環境情報）
- アーキテクチャ文書の参照先（`Architect/` ディレクトリ）
- 将来タスク管理の存在（docs/FUTURE_TASKS.md）
- ログ規約（`AILogger.Log` vs `Debug.Log`）
- Git コミット規約の **核**（日本語タイトル、Co-Authored-By、.meta セット）
- パイプラインフロー（/build-pipeline 等主要スキル名）
- 用語定義（セクション/スプリント/機能/システム）
- path-scoped CLAUDE.md が別に存在することの告知

---

## セクション B: lint-patterns（40 パターン）

**実装済み**: パターン定義は `.claude/rules/lint-patterns.json` に永続化済（Phase 11 前倒し）。
本セクションは**元の抽出データ**（regex・severity・source の対応表）を保持する。

| # | pattern (regex) | severity | message | source |
|---|---|---|---|---|
| 1 | `\bvar\s+\w+\s*=` | error | `var` は使用しない（型を明示） | unity-conventions L84 |
| 2 | `private\s+\w+\s+[A-Z]\w*\s*;` | warning | private フィールドは `_camelCase`（先頭アンダースコア + camelCase） | unity-conventions L25 |
| 3 | `private\s+\w+\s+[a-z]\w*\s*(?!=)` (no underscore) | warning | private フィールドは `_` プレフィックス必須 | unity-conventions L25 |
| 4 | `(public\|private)\s+const\s+\w+\s+(?!k_)[A-Z]` | warning | const は `k_PascalCase` を使用 | unity-conventions L26 |
| 5 | `public\s+[^(){}]+;$` (フィールド直書き) | warning | public フィールドではなく `[SerializeField] private` を使用 | unity-conventions L43 |
| 6 | `\.tag\s*==\s*"` | warning | `CompareTag()` を使用（文字列比較は遅い） | unity-conventions L117 |
| 7 | `Vector[23]\.Distance\s*\(` | warning | `sqrMagnitude` 比較を検討（sqrt 回避） | unity-conventions L113 |
| 8 | `void\s+Update\s*\(\)[^}]*\bnew\s+[A-Z]` (multiline) | error | Update 内でのアロケーション禁止。フィールドで事前確保 | unity-conventions L88-102 |
| 9 | `void\s+Update\s*\(\)[^}]*"\s*\+\s*` (multiline) | warning | Update 内での文字列連結禁止。StringBuilder 使用 | unity-conventions L104-106 |
| 10 | `GetComponent<[^>]+>\s*\(\)` (non-Awake/Start context) | warning | GetComponent は Awake/Start でキャッシュ | unity-conventions L108, architecture L25 |
| 11 | `FindObjectOfType\s*<` | error | `FindObjectOfType` 使用禁止（GameManager 経由） | architecture L25 |
| 12 | `transform\.position` (複数フレーム呼出) | info | `transform` プロパティもキャッシュ推奨 | unity-conventions L110 |
| 13 | `[0-9]+\.[0-9]+f\s*\*` in loop body | warning | マジックナンバー疑い。`const k_` を検討 | unity-conventions L62-70 |
| 14 | `using\s+System\.IO` in Assets/MyAsset/Runtime | warning | ランタイムコードでのファイル IO は Addressable/SaveSystem 経由 | asset-workflow L48-52 |
| 15 | `AssetDatabase\.` in non-Editor folder | error | ランタイムで `AssetDatabase` 使用禁止 | asset-workflow L219 |
| 16 | `Resources\.Load` | error | Addressable を使用（Resources フォルダ禁止） | asset-workflow L48 |
| 17 | `Addressables\.LoadAssetAsync[^;]+;` without `.Release` (per class) | warning | ロードしたアセットは必ず解放 | asset-workflow L180 |
| 18 | `Addressables\.InstantiateAsync[^;]+;` without `.ReleaseInstance` | warning | `InstantiateAsync` は `ReleaseInstance` で破棄 | asset-workflow L183 |
| 19 | `Debug\.Log\s*\(` in Assets/MyAsset/Core/ | warning | Core では `AILogger.Log` を使用 | CLAUDE.md ログ規約 |
| 20 | `\[SerializeField\]\s+public` | error | SerializeField + public は矛盾。private を使用 | unity-conventions L43 |
| 21 | `MonoBehaviour` class without `namespace` | warning | 名前空間を必ず指定（PascalCase） | unity-conventions L30 |
| 22 | `public\s+class\s+I[A-Z]` | error | I プレフィックスはインターフェース専用 | unity-conventions L20 |
| 23 | `interface\s+(?!I[A-Z])` | error | インターフェースは `I + PascalCase` | unity-conventions L20 |
| 24 | `(bool\|Boolean)\s+[a-z]\w*\s*;` without `is\|has\|can\|should` | info | bool は `is/has/can` で始める | unity-conventions L34 |
| 25 | `if\s*\([^)]+\)\s*[^{]` (1行if中括弧なし) | warning | 1行でも中括弧を付ける (`csharp_prefer_braces`) | unity-conventions L83 |
| 26 | `^\t` (タブインデント) | error | スペース 4 つ（タブ不使用） | unity-conventions L81 |
| 27 | `{\s*$` on same line as `if/for/while` | warning | Allman スタイル（中括弧は新しい行） | unity-conventions L82 |
| 28 | `Debug\.Log\s*\(` without `#if UNITY_EDITOR\|Conditional` in release-path | info | `[Conditional("UNITY_EDITOR")]` で除去可能化を検討 | unity-conventions L129 |
| 29 | `Update\s*\(\)[^}]*new\s+List<` | error | Update 内で List new 禁止。Clear して再利用 | unity-conventions L90-101 |
| 30 | `enum\s+\w+s\s+{` (複数形 without `[Flags]`) | warning | 複数形 enum には `[Flags]` を付与 | unity-conventions L29 |
| 31 | `\[Flags\][^}]*enum\s+\w+(?<!s)\s+` | warning | `[Flags]` enum は複数形 | unity-conventions L29 |
| 32 | `enum\s+\w+\s*{` without `:\s*byte` (small enum) | info | 値が少ない enum は `byte` 指定でメモリ節約 | unity-conventions L121 |
| 33 | `public\s+\w+\s+On[A-Z]\w*\s*\(` event handler without event | info | "On" で始まるメソッドはイベント発生メソッド規約 | unity-conventions L38 |
| 34 | `class\s+\w+\s*:\s*MonoBehaviour[^{]*{[^}]*public\s+\w+\s+\w+\s*;` | warning | public フィールド直書き禁止。SerializeField private を使用 | unity-conventions L43 |
| 35 | `Awake\s*\(\)[^}]*event\s*\+=` | warning | イベント登録は `OnEnable` で行う | unity-conventions L74 |
| 36 | `OnDestroy[^}]*(?<!\-=)` where `OnEnable[^}]*\+=` exists | error | OnEnable で購読したイベントは OnDisable で解除 | unity-conventions L77, test-driven L44 |
| 37 | `new\s+(Vector[23]\|Quaternion)\(` in Update | info | Update 内の構造体 new は軽量だがホットパスなら定数化 | unity-conventions L88 |
| 38 | `LoadAssetAsync<[^>]+>\("` with hard-coded uppercase path | error | Addressable アドレスは小文字・ハイフン区切り | asset-workflow L138-141 |
| 39 | `\[SerializeField\]\s+private\s+\w+\s+_[a-z]` | error | SerializeField は `camelCase`（`_` プレフィックス不要） | unity-conventions L27 |
| 40 | `Coroutine` / `StartCoroutine` in Core logic layer | warning | ロジック層は MonoBehaviour 非依存（ピュアロジック） | architecture L134 |

---

## セクション C: TDD 3 サブエージェント分離の具体ルール

### C-1. test-writer 担当ルール
- **命名規則**: `[機能名]_[条件]_[期待結果]`（test-driven L14-17）
- **配置**: Edit Mode = `Tests/EditMode/[機能名]Tests.cs` / Play Mode = `Tests/PlayMode/[機能名]PlayTests.cs` / 結合 = `Tests/EditMode/Integration_{テスト名}Tests.cs`
- **モード選択**: ロジック/計算 → Edit Mode、MonoBehaviour連携/物理/コルーチン → Play Mode
- **結合テスト 3 観点必須**:
  1. 既存ロジック呼び出し検証（呼び先の**効果**まで検証、例: HP クランプ・アーマーブレイクボーナス）
  2. 状態シーケンス検証（A→B→A 実行後の OnCompleted 1 回発火等）
  3. 境界値・不変条件（HP < 0 にならない、subscribe/unsubscribe 対称性）
- **テスト設計チェックリスト 4 項目**（L47-51）: 他システム呼出、イベント購読、状態保持、リソース確保 — 該当すれば専用テストを追加

### C-2. implementer 担当ルール
- **順序**: Red → Green。test-writer が書いた全テストが Fail する状態から開始
- **命名**: unity-conventions 全般（PascalCase/camelCase/`_camelCase`/`k_`）
- **アーキテクチャ準拠**: GameManager 経由アクセス、SoA コンテナ、Ability 拡張、1コンポーネント1責務
- **パフォーマンス**: Update 内アロケーション禁止、GetComponent キャッシュ、CompareTag、sqrMagnitude
- **マジックナンバー禁止**: `const k_` 必須
- **実装完了条件**: 全テスト Pass + コンソールエラーなし

### C-3. refactorer 担当ルール
- **DRY/KISS/YAGNI**: 重複排除、最小実装、不要機能作らない（unity-conventions L8-10）
- **コンポーネント粒度**: 責務を 1 文で説明できること（「〜と〜」は分割シグナル／architecture L59）
- **クラス構成順序**: Fields → Properties → Events → MonoBehaviour → Public → Private
- **リファクタ後**: 全テスト Pass を再確認してから `feature-db.py update`
- **コード規約違反修正**: lint-patterns に引っかかった箇所の機械的修正

---

## セクション D: PR レビュー 4 観点整理

### D-1. Code Reuse（重複検出）
- 重複パターン、既存ユーティリティ未使用（git-workflow L140）
- 既存 `HpArmorLogic`、`HitReactionLogic`、`SituationalBonusLogic` 等 static class の経由漏れ
- template-registry.json 未確認での GameObject 新規作成（template-usage L7-9）

### D-2. Code Quality（バグ・命名・リソース）
- バグ、命名規約違反、イベントリーク、リソースリーク（git-workflow L140）
- `_camelCase` / `k_` / PascalCase 違反
- OnEnable/OnDisable の subscribe/unsubscribe 非対称
- Addressable の `Release` 漏れ
- シーン保存漏れ、コンソールエラー残存（git-workflow L107-110）

### D-3. Efficiency（ホットパス）
- ホットパスアロケーション、キャッシュ漏れ、不要な sqrt（git-workflow L141）
- Update 内 `new`、`Vector3.Distance`、`obj.tag == ""`、`GetComponent` 繰り返し
- `string +` 連結

### D-4. TDD/Process
- 全テスト Pass 確認（git-workflow L134）
- テスト追加なしで実装のみのコミット → 警告
- .meta セットコミット確認
- 日本語タイトル（70 文字以内）+ Co-Authored-By 付与
- Summary + Test plan の記載

### 禁止事項
- `--no-verify` / `--no-gpg-sign`（明示指示時のみ）
- `push --force`（`--force-with-lease` のみ、rebase 後に限る／git-workflow L96）
- `reset --hard` / `branch -D` はユーザー確認必須（L128）
- アセットストア由来/第三者ライセンス/APIキーのステージ（L113-115）

---

## セクション E: anti-patterns 辞書化元ネタ（10 個）

| # | 症状 | 対策 | 実例（引用） |
|---|---|---|---|
| 1 | Update 内で `new List<>()` 毎フレーム生成 | フィールドに `_reusableList = new List()` 事前確保し `Clear()` で再利用 | unity-conventions L88-102 |
| 2 | `obj.tag == "Player"` で文字列比較 | `obj.CompareTag("Player")` 使用 | unity-conventions L117 |
| 3 | `Vector3.Distance` で sqrt 発生 | `sqrMagnitude` 比較、範囲値も 2 乗でキャッシュ | unity-conventions L113 |
| 4 | `FindObjectOfType` / 毎フレーム `GetComponent` | Awake/Start でキャッシュ、もしくは GameManager.Data ハッシュアクセス | architecture L22-25 |
| 5 | ランタイムで `AssetDatabase.LoadAssetAtPath` | `AssetReference` / `Addressables.LoadAssetAsync` を使用 | asset-workflow L48-52, L219 |
| 6 | `Addressables.LoadAssetAsync` して `Release` 呼ばず | OnDestroy/OnDisable で `Release` / `ReleaseInstance` | asset-workflow L179-183 |
| 7 | OnEnable で `+=` 登録したのに OnDisable で `-=` 解除しない | 対称性を守る（イベントリーク＝購読数増加） | test-driven L44, unity-conventions L74-77 |
| 8 | `transform.position += Vector3.up * 9.81f * Time.deltaTime` | `const float k_Gravity = 9.81f` で定数化 | unity-conventions L62-70 |
| 9 | public フィールド直書き | `[SerializeField] private` + `[Header]` グループ化 | unity-conventions L43-45 |
| 10 | `var` の多用で型が追えない | 型を明示（プロジェクト方針） | unity-conventions L84 |

---

## セクション F: rules 間の重複・矛盾

### F-1. 重複記述（削除候補・集約先）
- **GetComponent キャッシュ**: architecture L24-25 と unity-conventions L46, L108 で重複 → **unity-conventions に集約、architecture は「GetComponent 排除」の原則のみ残す**
- **Addressable 使用**: asset-workflow L48-52 と CLAUDE.md 本体（アセット管理セクション）で一部重複
- **`.meta` セット管理**: CLAUDE.md（`.meta` ファイルはアセットと必ずセットでコミット）と git-workflow L100-103 で重複 → **git-workflow が正**
- **コミットメッセージ規約**: CLAUDE.md（Git 運用）と git-workflow で重複 → **git-workflow が正、CLAUDE.md は短縮**

### F-2. 矛盾・古くなっている記述
- **Co-Authored-By のバージョン**: CLAUDE.md と git-workflow L49, L125 は "Claude Opus 4.6" と記載されているが、現在は **4.7 (1M context)**。**要更新**
- **template-registry.json のパス**: template-usage L7 で `unity-bridge/Templates/template-registry.json` を指示しているが、CLAUDE.md テンプレートセクションでは単に `template-registry.json` と記載。**実在パスの再確認必要**
- **SerializeField 命名**: unity-conventions L27 で `camelCase`（アンダースコアなし: `moveSpeed`）、L25 で private は `_camelCase`。**`[SerializeField] private` は `camelCase`（アンダースコアなし）が正**（L27 が優先ルール）

### F-3. path-scoped `@` インポート時の判断

**path-scoped CLAUDE.md に `@` インポートして本体から削除可能**:
- architecture.md（既に `paths: Assets/MyAsset/**/*.cs, Assets/Tests/**/*.cs` フロントマター指定済 → path-scoped 化して CLAUDE.md 本体のアーキテクチャ参照セクションは短縮可）
- asset-workflow.md の Addressable ランタイムコード部分 → `Assets/MyAsset/**/*.cs` 配下 CLAUDE.md へ
- unity-conventions.md → `Assets/MyAsset/**/*.cs` 配下 CLAUDE.md へ

**CLAUDE.md 本体に残すべき**:
- 環境情報（Unity パス、プロジェクトパス、feature-db コマンド）
- パイプラインフロー（対話型セクション単位、主要スキル一覧）
- 用語定義（セクション/スプリント/機能/システム）
- 将来タスク管理の運用ルール
- ログ規約（`AILogger` vs `Debug`）
- Git コミット規約の **核**（日本語タイトル、Co-Authored-By）— 全ファイル共通で効くため

**削除しにくい（どこでも効くため）**:
- test-driven.md の結合テスト 3 観点 — `Assets/Tests/**` に path-scope して本体から削除可
- git-workflow.md — ルート CLAUDE.md（`.` スコープ）に残す

---

## 精読対象ファイル（絶対パス）

- `.claude/rules/architecture.md`（271 行、`paths:` frontmatter 済）
- `.claude/rules/asset-workflow.md`（230 行）
- `.claude/rules/git-workflow.md`（148 行）
- `.claude/rules/template-usage.md`（24 行）
- `.claude/rules/test-driven.md`（74 行）
- `.claude/rules/unity-conventions.md`（140 行）

合計 887 行。本 audit はこの全内容を精読したうえで後続 Phase の実装計画に直接利用できる形で抽出している。

---

## 本 audit の更新履歴

| 日付 | 更新者 | 内容 |
|------|--------|------|
| 2026-04-24 | Wave 0 (Claude agent) | 初版作成 |
