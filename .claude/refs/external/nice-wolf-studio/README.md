# Nice-Wolf-Studio/unity-claude-skills 取り込み記録

## ソース

- **Repo**: https://github.com/Nice-Wolf-Studio/unity-claude-skills
- **License**: MIT (Copyright (c) 2026 Nice-Wolf-Studio)
- **取り込み Commit SHA**: `b954dccac894c53b5fea96c9a9e9150222791ec2`
- **取り込み日**: 2026-04-25
- **元 skill 数**: 35 (Core 2 / Domain 18 / Correctness 5 / Architecture 5 / Domain Translation 5)
- **取り込み形態**: ABCD 4 Tier 配分（cherry-pick）

## 採用 16 skills の Tier 配分

| Tier | 形態 | 配置先 |
|---|---|---|
| **A** (rules 抽出) | 既存 `.claude/rules/` ファイルに追記 | コードに散在 |
| **B** (静的 ref) | このディレクトリ配下 | 明示 `@` import 時のみ |
| **C** (skill auto-trigger) | `.claude/skills/external/nice-wolf-studio/` | description マッチで auto-trigger |
| **D** (リライト統合) | `Architect/` の各文書 | 設計時にロード |

### B 配置済み (このディレクトリ): 5 skill (B 主) + 7 skill (A の元参照)

```
B 主配置（@ import で参照）:
  unity-3d-math/             # 数学リファレンス
  unity-physics/             # Rigidbody / raycasting / FixedUpdate
  unity-2d/                  # Sprite / Tilemap / SortingLayer
  unity-physics-queries/     # B (hybrid): query 選択表 + NonAlloc 規約
  unity-performance/         # B (hybrid): Profiler 操作手順

A 抽出の元（参照可能、A は既存 rules に統合済）:
  unity-lifecycle/           # → unity-conventions.md ライフサイクル罠
  unity-foundations/         # → 各 rules に分散吸収
  unity-scripting/           # → unity-conventions.md MonoBehaviour 制約
  unity-testing/             # → test-driven.md UTF API
  unity-data-driven/         # → architecture.md データ設計
  unity-scene-assets/        # → asset-workflow.md シーン遷移
  unity-ui/                  # → create-ui に anti-patterns 統合
```

### C 配置済み (`.claude/skills/external/nice-wolf-studio/`): 2 skills

- `unity-input-correctness` (narrow trigger: input action / rebinding)
- `unity-async-patterns` (narrow trigger: async / await / coroutine)

### A 抽出済み (各 rules ファイルに分散): 7 件 + 3 hybrid

詳細は `.claude/rules/_attribution.md` を参照。

### D リライト統合済み (Architect/ 配下): 2 件

- `Architect/02_animation.md` ← unity-animation を SisterGame 文脈（AnimationBridge 路線）でリライト
- `Architect/05_AI.md` ← unity-state-machines を SisterGame AI 設計（SoA + Ability 拡張）に統合

## 不採用 19 skills

### 衝突確定 (5)

| skill | 理由 |
|---|---|
| `unity-cinemachine` | SisterGame は ProCamera2D を採用 |
| `unity-save-system` | Easy Save 3 と直接衝突（自前 DTO + 手動マイグレーション前提）|
| `unity-game-architecture` | Service Locator vs DI 論調が SoA + GameManager + ODCGenerator と整合しない |
| `unity-platforms` | Android IL2CPP の深い落とし穴（リンカー/ストリッピング/Mono-IL2CPP 挙動差）が未カバー |
| `unity-editor-tools` | 既存 AnimatorBuilder/StageBuilder/EventSceneBuilder で自走可、価値薄い |

### Out-of-Scope (9)

`unity-multiplayer` / `unity-xr` / `unity-ecs-dots` / `unity-ai-navigation` / `unity-packages-services` / `unity-graphics` (URP/HDRP, SisterGame は Built-in) / `unity-lighting-vfx` / `unity-input` (correctness 採用済) / `unity-audio`

### Domain Translation 5 (継続監視枠)

`unity-game-loop` / `unity-npc-behavior` / `unity-ui-patterns` / `unity-level-design` / `unity-procedural-gen`
（設計レベルで `Architect/` + `design-systems` skill と重複領域、必要が出たら次回評価）

## 利用方法

### B (静的 ref) の参照

明示的に `@` import で取り込む:

```markdown
# 例: 物理系の作業をしているとき
詳細リファレンス: @.claude/refs/external/nice-wolf-studio/unity-physics/SKILL.md
```

`Assets/MyAsset/CLAUDE.md` に「該当領域を扱う作業時にロード」する案内が記載されている。

### C (auto-trigger skill) の参照

通常の skill と同様に、Claude Code が description マッチに応じて自動ロード。

例: ユーザーが「Awaitable で待ち合わせするとき同じインスタンスを 2 回使えるか」と質問
→ `unity-async-patterns` skill が auto-trigger

### A (rules 抽出) の参照

既存の `.claude/rules/*.md` ファイルに統合済みのため、`paths:` マッチで広範囲ロード時に自動的に Claude のコンテキストに乗る。
特別な操作不要。

### D (Architect/ 統合) の参照

`Architect/` 配下のファイルは SisterGame の設計時に常時参照される。
通常の `Architect/` ロードフローでカバーされる。

## 上流更新の sync ポリシー

- **A / D**: 一度抜いたら独立、上流更新の自動 sync 不要。**SisterGame 固有メモがリセットされるリスクを避けるため、上流の変更をそのまま反映しない**
- **B / C**: 上流更新があれば手動 sync を検討。ただし下記原則を守る:
  - SKILL.md の trigger description が変更された場合 (C のみ) → 既存挙動への影響を確認してから採用
  - reference 内容のみ更新 → 比較的安全に sync 可能
  - 新規 skill 追加 → 不採用 19 + Domain Translation 5 のいずれかに該当しないか再評価

## License

このディレクトリ配下のファイルは Nice-Wolf-Studio/unity-claude-skills（MIT License）由来。
LICENSE 全文は同ディレクトリの `LICENSE` を参照。
A 抽出 / D リライトを含むすべての利用に対しても、`.claude/rules/_attribution.md` で copyright notice を保持している。
