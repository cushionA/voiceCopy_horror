# Agent Separation 規約 (Wave 5 Phase 19)

Effective Harnesses 二相構造 (Phase 7) を agent レベルで実現するための責務境界規約。
init-agent と coding-agent の役割を明確化し、相互の context を分離する。

## 責務マトリクス

| 責務 | init-agent | coding-agent | 既存 tdd-* agents (subagent) |
|------|-----------|--------------|------------------------------|
| 要件整理 / GDD | ✅ | ❌ | - |
| Spec/Design/Tasks 文書 | ✅ | read only | - |
| verifiableRequirements 追加 | ✅ | ❌ | - |
| verifiableRequirements 状態更新 | ❌ | ✅ | - |
| ユーザー対話 | ✅ | 必要時のみ | - |
| Test 作成 (Red) | - | 経由 (tdd-test-writer) | ✅ tdd-test-writer |
| 実装 (Green) | - | 経由 (tdd-implementer) | ✅ tdd-implementer |
| リファクタ | - | 経由 (tdd-refactorer) | ✅ tdd-refactorer |
| feature-db 更新 | ❌ | ✅ | ❌ |
| git commit / push | ❌ | ✅ | ❌ |
| Architect/ 編集 | ❌ (read only) | ❌ (read only) | ❌ |

## tools 制約

| agent | tools | 禁止理由 |
|-------|-------|---------|
| init-agent | Read, Write, Edit, Glob, Grep | Bash 禁止 → git / Unity CLI / feature-db.py への副作用なし。spec を技術非依存に保つ |
| coding-agent | Read, Write, Edit, Glob, Grep, **Bash** | テスト実行 / git / feature-db のため Bash 必須 |
| tdd-test-writer | Read, Write, Edit, Glob, Grep, Bash | Red 確認のため tests 実行 |
| tdd-implementer | Read, Write, Edit, Glob, Grep, Bash | Green 確認のため tests 実行 |
| tdd-refactorer | Read, Write, Edit, Glob, Grep, Bash | リファクタ後 tests 実行 |

## モデル選択

| agent | model | 理由 |
|-------|-------|------|
| init-agent | opus | 要件整理は推論深度が必要 (Phase 15 Advisor Strategy: 設計=opus) |
| coding-agent | sonnet | 実装は構造化、コスパ重視 (Advisor Strategy: 実装=sonnet) |
| tdd-* | sonnet | 同上 |

## context 分離の正当化

Effective Harnesses の核心: **役割が違えば context も分ける**

| アンチパターン | 結果 |
|---------------|------|
| 1 agent で spec + 実装 | 実装視点で spec が歪む (FeatureBench 11%) |
| 1 agent で test + 実装 | テストが暗黙に実装 fit (循環論理) |
| coding-agent が spec を書き換え | "実装で spec を解釈" → 仕様の曖昧さ隠蔽 |

context 分離により:
- spec.md は技術非依存 (init-agent は Bash 持たないので runtime 試行錯誤できない)
- テストは spec から派生 (tdd-test-writer が implementation を見ない)
- 実装は test を pass させるためにある (tdd-implementer が spec を直接読まない)

## handoff フロー

```
ユーザー要求
    ↓
init-agent (opus, no Bash)
    │
    ├─ 対話的要件整理 + spec/design/tasks 出力
    ├─ verifiableRequirements 追加 (pipeline-state.json)
    ├─ 人間 review gate (spec-gate / design-gate / tasks-gate)
    │
    ↓ handoff (verifiableRequirements id 配列 + spec path)
coding-agent (sonnet, with Bash)
    │
    ├─ tdd-test-writer subagent → Red
    ├─ Test 実行 (UniCli/batch)
    ├─ tdd-implementer subagent → Green
    ├─ Test 実行
    ├─ tdd-refactorer subagent (任意)
    ├─ feature-db / pipeline-state 更新
    └─ commit + push
    │
    ↓ blocker on 3 連続失敗
init-agent (受け取り、spec 修正)
```

## blocker handoff 条件

coding-agent → init-agent の戻し:

1. **spec 曖昧**: テスト設計不能 → init-agent で spec 修正
2. **design 規約違反**: Architect/ と矛盾 → init-agent で design 修正
3. **3 連続 Green 失敗**: failedAttempts ≥ 3 → init-agent で原因分析

各ケースで `pipeline-state.json` に以下を記録:
- `phase: blocked`
- `failedAttempts[feature] += 1`
- `lastAction: "blocker handoff: <reason>"`

## 既存 SKILL との関係

build-pipeline / create-feature SKILL は Phase 19 完成時点で **間接的に** 二相 agent を呼ぶ形に再設計予定:

| SKILL | 現状 (Phase 18 まで) | 二相運用後 (Phase 19+) |
|-------|--------------------|------------------------|
| `/build-pipeline` | 直接 design-game / design-systems を呼ぶ | init-agent を呼ぶ → init-agent が design-game / design-systems を呼ぶ |
| `/create-feature` | 直接 tdd-* agents を呼ぶ | coding-agent を呼ぶ → coding-agent が tdd-* を呼ぶ |
| `/design-game` `/design-systems` | 既存挙動維持 | init-agent から呼ばれる subagent に格下げ (任意) |

**本 PR の scope**: agent 定義 + 規約のみ。SKILL の再設計は別 PR (動作影響大)。

## 関連

- `.claude/agents/init-agent/AGENT.md`
- `.claude/agents/coding-agent/AGENT.md`
- `.claude/agents/tdd-test-writer/AGENT.md` / `.claude/agents/tdd-implementer/AGENT.md` / `.claude/agents/tdd-refactorer/AGENT.md`
- `.claude/rules/effective-harnesses.md` (Phase 7 — 二相基盤)
- `.claude/rules/sdd-workflow.md` (Phase 23 — Spec/Design/Tasks)
- WAVE_PLAN.md L897-908 (Phase 19 P19-T1〜T8)
