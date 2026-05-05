# 外部由来コンテンツの帰属表記 (License Attribution)

このファイルは SisterGame プロジェクト内に取り込まれた**外部 license のコンテンツ**の出典・著作権者・取り込み形態を一元管理する。

## Nice-Wolf-Studio/unity-claude-skills (MIT)

### Source

- **Repo**: https://github.com/Nice-Wolf-Studio/unity-claude-skills
- **License**: MIT License
- **Copyright**: Copyright (c) 2026 Nice-Wolf-Studio
- **取り込み Commit SHA**: `b954dccac894c53b5fea96c9a9e9150222791ec2` (2026-03-11)
- **取り込み日**: 2026-04-25
- **License 全文**: `.claude/refs/external/nice-wolf-studio/LICENSE`

### MIT License 要件への対応

MIT License は以下の 2 点を要求する:
1. ✅ **Copyright notice の保持**: 本ファイル（`_attribution.md`）と `.claude/refs/external/nice-wolf-studio/LICENSE` で copyright を明示
2. ✅ **License 全文の同梱**: `.claude/refs/external/nice-wolf-studio/LICENSE` に MIT License 全文を保存

それ以外（改変・統合・再配布）は無制限に許可される。

### 採用 16 skills の Tier 配分

| Tier | 配置先 | skills |
|---|---|---|
| **A** (rules 抽出) | `.claude/rules/*.md` の既存ファイルに追記 | unity-lifecycle, unity-physics-queries (規約部分), unity-async-patterns (規約部分), unity-performance (規約部分), unity-foundations, unity-scripting, unity-ui (anti-patterns), unity-testing, unity-data-driven, unity-scene-assets |
| **B** (静的 ref) | `.claude/refs/external/nice-wolf-studio/<skill>/` | unity-3d-math, unity-physics, unity-2d, unity-physics-queries (詳細), unity-performance (Profiler 操作) |
| **C** (skill auto-trigger) | `.claude/skills/external/nice-wolf-studio/<skill>/` | unity-input-correctness, unity-async-patterns (詳細) |
| **D** (リライト統合) | `Architect/` 配下の各文書 | unity-animation → `Architect/09_アニメーション規約.md`<br>unity-state-machines → `Architect/05_AIシステム.md § 11` |

### A 抽出が反映された rules ファイル

各ファイル末尾の `Sources: nice-wolf-studio/unity-claude-skills (MIT)` 行で出典を明示している:

| ファイル | 反映内容 |
|---|---|
| `.claude/rules/unity-conventions.md` | 「実行時バグ防止パターン」セクション全体（lifecycle / physics-queries / async-patterns / performance / foundations / scripting） |
| `.claude/rules/asset-workflow.md` | 「シーン遷移と Asset Lifecycle」セクション全体 |
| `.claude/rules/test-driven.md` | 「Unity Test Framework (UTF) API リファレンス」セクション全体 |
| `.claude/rules/architecture.md` | 「データ設計」セクション全体 |
| `.claude/rules/lint-patterns.json` | NonAlloc / fake-null / DestroyImmediate / async void / Instantiate-SetParent パターン追加 |
| `.claude/skills/create-ui/SKILL.md` | 「UI Toolkit Anti-Patterns」セクション全体 |

### B 配置（参照系）

`.claude/refs/external/nice-wolf-studio/` 以下に skill フォルダ単位でコピー:

```
unity-3d-math/                # 数学リファレンス
unity-physics/                # Rigidbody / raycasting / FixedUpdate
unity-2d/                     # Sprite / Tilemap / SortingLayer
unity-physics-queries/        # クエリ選択表 + NonAlloc 詳細
unity-performance/            # Profiler / Memory Profiler / Frame Debugger 操作
unity-lifecycle/              # A 抽出の元（参照可能）
unity-foundations/            # A 抽出の元（参照可能）
unity-scripting/              # A 抽出の元（参照可能）
unity-testing/                # A 抽出の元（参照可能）
unity-data-driven/            # A 抽出の元（参照可能）
unity-scene-assets/           # A 抽出の元（参照可能）
unity-ui/                     # A 抽出の元（参照可能）
LICENSE                       # MIT License 全文
README.md                     # 取り込み記録
```

明示 `@` import 時のみ参照される。

### C 配置（auto-trigger skill）

`.claude/skills/external/nice-wolf-studio/` 以下:

| skill | trigger 範囲 |
|---|---|
| `unity-input-correctness` | New Input System の action 読取 / rebinding 永続化 |
| `unity-async-patterns` | async / await / coroutine / Awaitable |

両者とも narrow trigger description で、既存 SisterGame skill との競合リスクを最小化している。

### D リライト（SisterGame 文脈統合）

| 元 skill | 統合先 | 統合内容 |
|---|---|---|
| `unity-animation` | `Architect/09_アニメーション規約.md`（新規） | AnimationBridge + CrossFade 駆動を**正典**として記述。Mecanim Transitions / Parameters 駆動は不採用と明記。CrossFade API / BlendTree / IK / Root Motion は採用部分として記載 |
| `unity-state-machines` | `Architect/05_AIシステム.md § 11` | SisterGame は MonoBehaviour ベースのルール駆動 AI（既存）を採用。FSM/HFSM/BT は**サブシステム / コンボ管理 / UI 遷移など局所的に**使う場面のみ。「plain C# classes, NOT MonoBehaviours」原則を SoA + Ability 拡張と整合させて再構成 |

### 不採用 19 skills（参考、配置していない）

| 理由 | skills |
|---|---|
| 衝突確定 (5) | unity-cinemachine (ProCamera2D 採用), unity-save-system (Easy Save 3 採用), unity-game-architecture (SoA + GameManager と論調ずれ), unity-platforms (Android IL2CPP 深部未カバー), unity-editor-tools (既存 Builder 群で十分) |
| Out-of-Scope (9) | unity-multiplayer, unity-xr, unity-ecs-dots, unity-ai-navigation, unity-packages-services, unity-graphics (URP/HDRP, SisterGame は Built-in), unity-lighting-vfx, unity-input (correctness 採用済), unity-audio |
| Domain Translation 5 (継続監視枠) | unity-game-loop, unity-npc-behavior, unity-ui-patterns, unity-level-design, unity-procedural-gen |

詳細評価: `docs/reports/research/2026-04-25_external-skills-evaluation.md`

### 上流更新の sync ポリシー

- **A / D**: 一度抽出/リライトしたら独立。上流変更を自動 sync しない（SisterGame 固有調整を保護）
- **B / C**: 上流更新があれば手動 sync 検討:
  - SKILL.md frontmatter の `description` 変更 → 既存 trigger 動作への影響を要評価
  - reference 内容のみの更新 → 比較的安全に sync 可能
  - 新規 skill 追加 → 不採用 19 + Domain Translation 5 のいずれかに該当しないか再評価

---

## 帰属付与の追加方針

### 各 A 抽出セクション

各 rules ファイルの該当セクション冒頭に以下を記載済み:

```markdown
> Sources: nice-wolf-studio/unity-claude-skills (MIT) — <skill 名>
```

### 各 B / C 配置 SKILL.md

オリジナルの frontmatter / 内容を**改変せずそのまま**置いている。LICENSE は同ディレクトリで保持。

### D リライト ファイル

`Architect/09_アニメーション規約.md` および `Architect/05_AIシステム.md § 11` の該当箇所冒頭に以下を記載:

```markdown
> Sources: nice-wolf-studio/unity-claude-skills (MIT) — <skill 名> を SisterGame の <文脈> に合わせて再構成
```

---

## 履歴

| 日付 | 内容 |
|---|---|
| 2026-04-25 | 初版（Nice-Wolf-Studio から 16 skills を ABCD 配分で取り込み）|
