---
name: create-feature
description: Create a new game feature using TDD workflow (test first, then implement, then record)
user-invocable: true
argument-hint: <FeatureName> [description]
model: sonnet
---

<!-- Wave 4 Phase 15 P15-T7 (Advisor Strategy): create-feature は Sonnet 固定。理由: TDD サイクル / Unity 規約適用 / feature-db 操作はパターンマッチ性が高い実行型タスク。Opus は overkill -->


# Create Feature: $ARGUMENTS

TDD ワークフローで新しいゲーム機能を作成する。

## Layer

このスキルは Two-layer 構成（[詳細](../_two-layer-design.md)）で運用している。

- **base.md** — TDD サイクル・git workflow・自己レビュー観点の汎用ロジック（プロジェクト非依存）。実行時に併読する: `@base.md`
- **本ファイル (SKILL.md, overlay)** — SisterGame / Unity 固有のテスト配置・規約参照・feature-db / FUTURE_TASKS.md 連携・コミット規約のバインディング

base 層が要求する I/O コントラクトに対し、overlay は次のように具体値を供給する:

| base が要求する項目 | SisterGame での実体 |
|--------------------|----------------------|
| 仕様フォーマット | `instruction-formats/feature-spec.md` |
| 設計書（あれば） | `designs/systems/` 配下 |
| テストファイル配置 | `Tests/EditMode/{Name}Tests.cs` / `Tests/PlayMode/{Name}PlayTests.cs` |
| 結合テスト配置 | `Tests/EditMode/Integration_{Name}Tests.cs` |
| テスト実行 | MCP `run_tests`（推奨）/ Unity CLI `-runTests -batchmode` |
| コード規約 | `.claude/rules/unity-conventions.md` |
| アーキテクチャ規約 | `.claude/rules/architecture.md` |
| アセット規約 | `.claude/rules/asset-workflow.md` |
| 結合テスト規約 | `.claude/rules/test-driven.md` の「結合テスト」節 |
| 機能 DB 操作 | `python tools/feature-db.py add/update` |
| ブランチ命名 | `feature/<機能名>` |
| コミット書式 | `feat(scope): 機能名を実装` + `Co-Authored-By: Claude Opus 4.7 (1M context)` |
| 将来タスク | `docs/FUTURE_TASKS.md` |
| アセット要求登録 | `python tools/feature-db.py add-asset` |

---

## ステップ 0: ブランチ作成 + 事前チェック

base.md「ブランチ作成」に従う。SisterGame 固有のブランチ命名は `feature/<機能名>`（日本語 OK）。

### 将来タスクからの開始

引数が `docs/FUTURE_TASKS.md` の項目を指している場合:

1. `docs/FUTURE_TASKS.md` を読み、該当タスクの詳細（説明・対象ファイル・依存関係）を取得
2. タスクの情報を仕様整理（base.md ステップ 1）のインプットとして活用
3. 実装完了後、ステップ 7 でタスクにチェックを入れる

### 重複検出

実装を始める前に既存機能との重複を確認する。

```bash
python tools/feature-db.py list
```

チェック項目:
- **同名・類似機能が存在するか**: 存在する場合はユーザーに報告
  - 「この機能は既存の XXX と重複しています。拡張で対応しますか？」
- **拡張で済むか**: 既存機能のテスト・実装ファイルを確認し、変更範囲を見積もる
- **新規作成が妥当か**: 完全に新しい場合のみ新規作成に進む

重複が見つかった場合:
- **拡張**: 既存テストにケース追加 → 既存実装を拡張 → feature-db は `update`
- **新規**: 通常の TDD フローへ進む

---

## ステップ 1: 仕様確認

base.md ステップ 1 に従い、`instruction-formats/feature-spec.md` フォーマットで機能仕様を整理する。

設計書がある場合（`designs/systems/` 配下）:
- 該当システムの設計書から機能仕様を読み取る
- コンポーネント構成、インタフェース、データフローを確認

---

## ステップ 2: テスト作成（Red）

base.md ステップ 2 に従う。`.claude/rules/test-driven.md` の追加規約も併読する。

- `Tests/EditMode/{FeatureName}Tests.cs`（必須）
- `Tests/PlayMode/{FeatureName}PlayTests.cs`（ゲームプレイ機能の場合）

テスト命名: `[機能名]_[条件]_[期待結果]`

---

## ステップ 3: Red 確認

base.md ステップ 3 に従う。

テスト実行手段（優先順位）:
1. **MCP 経由**: `run_tests` ツール（Unity エディタが起動中の場合）
2. **CLI**: Unity `-runTests -batchmode`（エディタが閉じている場合）

---

## ステップ 4: 実装（Green）

base.md ステップ 4 に従う。SisterGame 固有の追加観点:

- コード規約: `.claude/rules/unity-conventions.md`
- アーキテクチャ準拠: `.claude/rules/architecture.md`（SoA、GameManager 中央ハブ、Ability 拡張）
- テンプレート確認: `template-registry.json`
- 必要アセットは `[PLACEHOLDER]` で仮配置（`.claude/rules/asset-workflow.md` 参照）

---

## ステップ 5: Green 確認

base.md ステップ 5 に従う。MCP 経由でテスト実行した場合は `read_console` でコンソールエラーも確認する。

---

## ステップ 5.5: 結合テスト作成

`.claude/rules/test-driven.md` の「結合テスト（Cross-System Testing）」セクションに従う。

**テスト設計チェックリスト**を確認し、該当する項目があれば結合テストを作成:

- 配置: `Tests/EditMode/Integration_{機能名}Tests.cs`
- 必須 3 観点: 既存ロジック呼び出し検証 / 状態シーケンス検証 / 境界値・不変条件検証

結合テストが不要なケース（純粋なデータ構造体、他システムへの依存がない独立ロジック）はスキップ可。

---

## ステップ 6: コードレビュー（自己チェック）

base.md ステップ 6 の汎用観点に加え、Unity 固有の観点を追加:

- [ ] Unity 規約に準拠しているか（命名、フォーマット、パフォーマンス）
- [ ] `[SerializeField] private` で publicフィールドを避けているか
- [ ] ScriptableObject で設定値を外出ししているか
- [ ] マジックナンバーは `const k_` で定数化しているか
- [ ] `GetComponent` を Awake/Start でキャッシュしているか
- [ ] `obj.tag == "..."` ではなく `CompareTag()` を使っているか
- [ ] `Vector3.Distance` を `sqrMagnitude` で代替できないか
- [ ] OnEnable/OnDisable でイベント subscribe/unsubscribe が対称か
- [ ] Addressable ハンドルは `Release` / `ReleaseInstance` で解放しているか

---

## ステップ 7: 記録

feature-db に完了記録を追加する。

```bash
# 新規作成の場合
python tools/feature-db.py add "$0" --tests テストファイルパス --impl 実装ファイルパス
python tools/feature-db.py update "$0" --status complete --test-passed N --test-failed 0

# 拡張の場合
python tools/feature-db.py update "既存機能名" --status complete --test-passed N --test-failed 0
```

### FUTURE_TASKS.md 更新

将来タスクから開始した場合:
- `docs/FUTURE_TASKS.md` の該当タスクに `[x]` チェックを入れる
- 完了メモ（✅ で始まる 1 行）を追記する

---

## ステップ 8: Git コミット

base.md ステップ 8 に従う。SisterGame 規約:

- ブランチ確認: ステップ 0 で作成した `feature/<機能名>` にいること
- ステージング: テストファイルと実装ファイルを `git add`
- コミットメッセージ書式: `feat(scope): 機能名を実装`（日本語タイトル）
- プッシュ: `git push origin <branch>`
- Co-Authored-By 行: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## ステップ 9: アセット要求

必要アセットがある場合は `instruction-formats/asset-request.md` フォーマットでリストアップし、feature-db にも登録する。

```bash
python tools/feature-db.py add-asset <id> "$0" <type> "<description>" --priority <high|medium|low>
```

---

## ルール参照（再掲）

- テスト規約: `.claude/rules/test-driven.md`
- コード規約: `.claude/rules/unity-conventions.md`
- アーキテクチャ規約: `.claude/rules/architecture.md`
- アセット管理: `.claude/rules/asset-workflow.md`
- **既存機能の重複作成は絶対に避ける**。拡張で済む場合は拡張する
- 実装が大きくなりすぎた場合は分割を提案する

## 3 段分割モード（Wave 3 Phase 13 で導入、オプション）

機能複雑度が高く「テストが無意識に実装に fit される循環論法」を避けたい場合、**3 つの subagent を別コンテキストで順次起動**するモードに切り替える。

```
[1] /agent tdd-test-writer <FeatureName>
    ↓ Red phase: 失敗テストを書く（実装には触れない）
[2] /agent tdd-implementer <FeatureName>
    ↓ Green phase: テスト読み込み + 最小実装でパス
[3] /agent tdd-refactorer <FeatureName>
    ↓ Refactor phase: DRY/KISS/YAGNI、テスト維持、commit + feature-db 記録
```

各 agent は別の context で起動するため、test-writer の意図が implementer に漏れず、refactorer は「Green になっただけで満足」を防止する。

### 使い分け

- **通常**: 本 SKILL.md ステップ 0〜9 の単一エージェントモード（小機能、テスト 5 個以内）
- **3 段分割**: 中〜大機能、Integration テストが必要、または TDD 規律を強化したい時
- **TDD-Guard 連動**: `.claude/skills/tdd-guard-setup/SKILL.md` で Phase 6 の hook を有効化すると、3 段分割を物理強制できる（Phase 6 はユーザー承認後に別 PR で導入）

### 詳細

各 agent の責務と禁止事項は `.claude/agents/{tdd-test-writer,tdd-implementer,tdd-refactorer}/AGENT.md` を参照。
