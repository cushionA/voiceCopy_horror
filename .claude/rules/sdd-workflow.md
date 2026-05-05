# SDD (Spec-Driven Development) ワークフロー (Wave 5 Phase 23)

Pimzino/cc-sdd 等の SDD パターンを SisterGame の `design-game → design-systems → create-feature`
フローに統合するための規約。FeatureBench 11% 対策 (人間計画注入) を兼ねる。

## 基本方針: 既存フローを破壊しない

SisterGame には既に以下のフローが存在し、SDD 互換に近い:

```
design-game (GDD)
    ↓ section 単位で
design-systems (システム設計 + asmdef + feature 分解)
    ↓ feature 単位で
create-feature (TDD 実装)
```

Wave 5 Phase 23 では **既存 SKILL の挙動を変更せず**、以下を追加する:

1. **3 層対応関係を明示** — `instruction-formats/feature-spec.md` 冒頭で表化
2. **system 規模時の分離オプション** — `designs/specs/{system}/` ディレクトリ構造を許可
3. **人間レビュー gate を共通モジュール化** — `.claude/skills/_human-review-gate.md`
4. **verifiableRequirements への接続** — Spec の Behavior が `pipeline-state.json` の verifiableRequirements に対応

## 3 層への分離判定

| feature 数 / system | 分離する? | 推奨形式 |
|---------------------|-----------|----------|
| 1-4 feature | NO  | 1 feature = 1 feature-spec.md (既存) |
| 5-9 feature | OPT | `designs/specs/{system}/spec.md`、`design.md`、`tasks.md` の 3 ファイル |
| 10+ feature | YES | 上記 + `tasks.md` 内で feature 単位サブセクション化 |

判定は `design-systems` skill が feature 数を見て自動 (オプション)。
明示的に細分化したい場合のみ人間が指示する。

## ディレクトリ構造 (system 単位で分離する場合)

```
designs/
├── specs/
│   └── {system_slug}/         例: player_movement
│       ├── spec.md            Overview + Behavior + verifiableRequirements
│       ├── design.md          Components + Required Assets + Dependencies
│       └── tasks.md           Test Cases (1 task = 1 feature)
├── pipeline-state.json
└── claude-progress.txt
```

`spec.md` の Behavior 行 = `pipeline-state.json` の verifiableRequirements 1 件の対応関係を保つ。

## 人間レビュー gate

design 段階完了時に以下のいずれかで gate:

1. `pipeline-state.json` の `awaitingHumanReview: true` を立てる
2. ユーザーへ明示的に確認質問 (AskUserQuestion 推奨)
3. 承認後に `awaitingHumanReview: false` に戻し、`phase: implement` へ遷移

詳細手順は `.claude/skills/_human-review-gate.md` (共通モジュール)。

## verifiableRequirements への接続

Spec の Behavior 行を以下の規則で verifiableRequirements に変換:

```yaml
# spec.md
## Behavior
- 左右入力がある時 → キャラクターが入力方向に moveSpeed で移動する
```

↓

```json
// pipeline-state.json の verifiableRequirements
{
  "id": "PLM-001",
  "description": "左右入力時、キャラクターが入力方向に moveSpeed で移動する",
  "status": "pending",
  "feature": "PlayerMovement",
  "testFile": "Assets/Tests/PlayMode/PlayerMovementPlayTests.cs",
  "specSource": "designs/specs/player_movement/spec.md#behavior"
}
```

ID の prefix は system の頭文字 2-8 文字。連番は spec.md の Behavior 順。

## FeatureBench 11% 対策 (人間計画注入)

Anthropic の研究で feature-level 実装は精度が低い (11%)。
SDD で人間計画を注入することで以下を強制:

| gate | 何を確認するか |
|------|--------------|
| spec.md 完成時 | "本当にこの Behavior リストで仕様を網羅しているか" |
| design.md 完成時 | "Architect/ 既存設計と整合するか、SoA / GameManager / Ability 規約準拠か" |
| tasks.md 完成時 | "1 タスク 5 件以下のテストで完結するか" |

各 gate を通過しないと create-feature に進まない。

## 既存 SKILL との統合 (将来 Phase 19 で本格運用)

現状 (Phase 23 PR):
- `design-systems` SKILL の出力に `designs/specs/{system}/` オプションを追加するのは **将来タスク** (FUTURE_TASKS 登録)
- 当面は手動で `instruction-formats/feature-spec.md` 形式 + 大規模時のみ手動分離

Phase 19 (Harness 二相分離) で:
- init-agent が spec.md / design.md / tasks.md を出力
- coding-agent が tasks.md の 1 タスクを順次消化
- gate は `pipeline-state.json` の awaitingHumanReview で制御

## 関連

- WAVE_PLAN.md L910-919 (Phase 23 P23-T1〜T6)
- `.claude/rules/effective-harnesses.md` (Phase 7 verifiableRequirements との接続)
- `.claude/skills/_human-review-gate.md` (gate 共通モジュール)
- `instruction-formats/feature-spec.md` (1 ファイル形式の既存テンプレート)
- 外部参考: Pimzino/claude-code-spec-workflow、gotalab/cc-sdd
