# Effective Harnesses 二相運用ルール (Wave 5 Phase 7)

Anthropic / 業界の "Effective Harnesses" パターンを SisterGame に適用するための運用規約。
Phase 7 (本フェーズ) で基盤を整え、Phase 19 (Harness 二相分離) で本格運用に入る。

## 二相 (Two-Phase) アーキテクチャ

```
┌─────────────────┐  Spec / Design / Tasks   ┌──────────────────┐
│  init phase     │ ──────────────────────►  │  coding phase    │
│                 │                           │                  │
│  対話・要件整理 │                           │  Red→Green→Refactor│
│  - design-game  │                           │  - create-feature│
│  - design-systems                           │  - 実装 + テスト │
│  - human review │                           │  - feature-db 更新│
└─────────────────┘                           └──────────────────┘
        │                                              │
        ▼                                              ▼
   pipeline-state.json (Source of Truth for state machine)
   claude-progress.txt (作業文脈スナップショット)
```

## 構成ファイル

| ファイル | 役割 |
|---------|------|
| `designs/pipeline-state.json` | 機械可読 state (phase / verifiableRequirements / features) |
| `designs/pipeline-state.schema.json` | 上記の JSON Schema (draft-07) |
| `designs/claude-progress.txt` | 人間とエージェント双方が読む作業ノート |
| `scripts/init.sh` | セッション初期化 (state + progress + handoff + feature-db を 1 画面集約) |
| `.claude/hooks/phase-boundary-commit.sh` | feature 完了検出時に checkpoint tag |
| `.claude/rules/effective-harnesses.md` | 本ファイル (運用規約) |

## verifiableRequirements の使い方

`pipeline-state.json` の `verifiableRequirements` フィールドは Phase 7 拡張。
init phase で書き出し、coding phase で実装と検証に使う。

### スキーマ (1 要件)

```json
{
  "id": "PLM-001",
  "description": "ジャンプ中に空中ダッシュ入力が来た場合、追加速度ベクトルが進行方向に加算される",
  "status": "pending",
  "feature": "PlayerAirDash",
  "testFile": "Assets/Tests/EditMode/PlayerAirDashTests.cs",
  "specSource": "designs/specs/player/spec.md#air-dash",
  "lastVerifiedAt": null
}
```

### ID 命名規則

- 接頭辞 (大文字 2-8 文字): システム略称 (PLM=PlayerMovement, CMB=Combat, AI=AI 等)
- 連番 (1-4 桁): システム内通番
- 正規表現: `^[A-Z]{2,8}-[0-9]{1,4}$`

### status 遷移

```
pending ──► in_progress ──► passed
                        ──► failed     (テスト Red 後の Green 失敗)
   └────────────────────► skipped     (人間判断でスコープ外)
```

`failed` から `pending` に戻すのは init phase の責務 (Spec 修正)。

## phase 遷移ルール

| from   | to          | 起動条件 |
|--------|-------------|----------|
| idle   | design      | `/build-pipeline <concept>` または `/design-game` |
| design | spec        | GDD 完成 + ユーザー確認済 |
| spec   | implement   | `verifiableRequirements` が 1 件以上 status=pending |
| implement | test     | feature-db でテスト実行中 |
| test   | review      | 全テスト Pass + Phase 12 Adversarial Review 起動可 |
| review | implement   | レビュー指摘で再実装が必要 |
| review | idle        | PR マージ → Wave 完了 |
| any    | blocked     | `failedAttempts[feature] >= 3` |
| blocked | design     | 人間が原因分析 + Spec 修正 |

phase は機械的に必ずどちらかが書き換える:
- `design / spec` 段階 → init-agent (Phase 19)
- `implement / test / review` 段階 → coding-agent (Phase 19)

Phase 19 完成までは build-pipeline / create-feature が両方を担当。

## hook の自動連動

| イベント | 動作 |
|---------|------|
| Write/Edit on `pipeline-state.json` | `phase-boundary-commit.sh` が新規 completed feature を検出 → 軽量 tag |
| Stop (セッション末) | `stop-handoff-reminder.sh` が `/handoff-note` を促す |
| SessionStart | `session-start-registry.sh` が直近 handoff を表示 |
| 任意 (人間起動) | `bash scripts/init.sh` で全状態を 1 画面集約 |

## /rewind "code only" 運用

Effective Harnesses では code-only rewind が前提。
`pipeline-state.json` と `claude-progress.txt` は **コード扱い** で commit されており、
rewind 後も状態継続できる。逆に conversation rewind ではこれらは戻らない。

実運用:
1. 失敗実装を rewind したい場合 `/rewind` で code only 復元
2. `bash scripts/init.sh` で現状確認
3. `claude-progress.txt` の「次にやること」を参照して再開

## checkpoint tag

`phase-boundary-commit.sh` が打つ tag:
```
wave5-checkpoint-{YYYYMMDDTHHMMSSZ}-{feature-slug}
```

- annotated tag (`-a`)、HEAD に対して付与
- commit はしない (副作用最小)
- 既存 tag があれば skip
- `PHASE_HOOK_DRYRUN=1` で実行抑制

## 観察期間 (Phase 7 〜 Phase 19 着手まで)

Phase 7 で基盤導入、Phase 19 で完全二相化。その間は以下を観察:

- `verifiableRequirements` が手動でも書き続けられるか
- `claude-progress.txt` の更新頻度 (低すぎると死蔵、高すぎると noise)
- `phase-boundary-commit.sh` の tag が後で役立つか (revert / blame シグナルとして)

観察ログは `docs/compound/` に Wave 5 lessons として記録。

## 関連

- WAVE_PLAN.md L850-860 (Phase 7 タスク表)
- WAVE_PLAN.md L897-908 (Phase 19 二相分離、本基盤を本格運用)
- WAVE_PLAN.md L910-919 (Phase 23 SDD 統合、verifiableRequirements を Spec/Tasks に拡張)
- `.claude/rules/wave0-audit.md` § C (TDD 3 サブエージェント分離との整合)
- `~/.claude/plans/wave5-logical-tome.md` (Wave 5 全体ロードマップ)
