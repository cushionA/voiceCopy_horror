# Two-layer Skill Definition — 設計メモ (Wave 2 Phase 10)

**作成日**: 2026-04-25
**Phase**: Wave 2 Phase 10 (`docs/WAVE_PLAN.md` L693-702 / P10-T1〜T6)
**目的**: Overstory の Two-layer agent definitions 方式（base.md = HOW / overlay = WHAT）を SisterGame の skill 体系に適用し、本プロジェクト固有の domain knowledge と再利用可能な手順論理を分離する。
**スコープ**: 試験的に `build-pipeline` と `create-feature` の 2 skill にのみ適用。残 22 skill への展開は P10-T5 の判定表で個別判定する。

---

## 1. 設計原則

### 1.1 base.md と overlay の境界線

| 層 | 役割 | 中身 | 移植性 |
|----|------|------|--------|
| **base.md** | HOW — 手順・アルゴリズム・状態機械の本体ロジック | 状態遷移表、TDD サイクル、git 操作の汎用手順、エラー時のリトライ戦略、I/O フォーマット | 他プロジェクトに**移植可能**なレベルの抽象度 |
| **SKILL.md (overlay)** | WHAT — SisterGame 固有のドメイン語彙・呼び先・規約参照 | 呼び出す skill 名（`/design-game` 等）、参照する rules ファイル、feature-db / pipeline-state.json 等の固有 artifact、Unity 固有のテスト配置、コミット規約 | **本プロジェクト専用** |

### 1.2 判定基準（base/overlay どちらに置くか）

ある記述を見たとき、以下のチェックを順に当てる:

1. **「このプロジェクトでなくても通用するか」**
   - YES → base.md（例: 「テストが Fail することを確認」「`pendingFeatures` の先頭から順に処理」「3 回失敗で skip 移動」）
   - NO → overlay（例: 「`/design-game` を呼ぶ」「`Tests/EditMode/{FeatureName}Tests.cs` に配置」）

2. **「ファイルパス・コマンド・skill 名がハードコードされているか」**
   - YES（パスや固有名詞を含む）→ overlay
   - NO（抽象的な手順のみ）→ base.md

3. **「Unity / SisterGame の rules ファイルを参照しているか」**
   - YES → overlay（rules ファイルそのものは SisterGame の document）
   - NO → base.md

### 1.3 構造規約

```
.claude/skills/<skill-name>/
├── SKILL.md   ← overlay。frontmatter（name / description / user-invocable）はここに残す
└── base.md    ← HOW。frontmatter なし。SKILL.md から `@base.md` で参照する
```

`SKILL.md` は冒頭に **base 参照ブロック**を置く:

```markdown
## Layer

このスキルは Two-layer 構成（[詳細](../_two-layer-design.md)）。

- **base.md** — 手順・状態遷移の本体（プロジェクト非依存）。実行時に併読する: `@base.md`
- **本ファイル (SKILL.md)** — SisterGame 固有の overlay。呼び先 skill / 参照 rules / artifact のバインディングを定義
```

---

## 2. `build-pipeline` の分離マッピング

現状 200 行の SKILL.md を以下の通り分離する。

### 2.1 base.md に置く内容（HOW）

| 元 SKILL.md セクション | 行範囲 | 抜粋理由 |
|-----------------------|--------|---------|
| 進行状態の管理（state schema 構造） | 26-43 | state machine schema は generic |
| 状態の読み書き手順（Python スニペット） | 50-71 | JSON I/O は generic |
| 書き込みタイミング表 | 73-83 | 状態遷移ルールは抽象論 |
| データ整合ルール（SoT/cache 区別） | 85-91 | 任意の state machine + DB 構成に通用 |
| "continue" 動作 | 165-169 | state 復元の generic 手順 |
| 各フェーズ間の遷移ルール（自動/承認待ち） | 171-177 | generic な state machine 遷移 |
| エラー時（3 回失敗 → skip） | 192-196 | 汎用的なリトライ戦略 |

### 2.2 overlay (SKILL.md) に残す内容（WHAT）

| 元 SKILL.md セクション | 行範囲 | 残す理由 |
|-----------------------|--------|---------|
| frontmatter | 1-6 | skill 自体のメタ情報 |
| パイプライン責任範囲（やる/やらない） | 14-24 | SisterGame 固有のスコープ宣言 |
| パイプライン全体フロー Phase 1-4 | 93-163 | `/design-game`、`/design-systems`、`/create-feature`、`/simplify` 等 SisterGame skill 名を含む |
| Git 運用（feature/pipeline-{コンセプト名}） | 179-190 | SisterGame ブランチ命名規約 |
| 出力リスト | 198-200 | designs/, GDD 等 SisterGame artifact |

### 2.3 期待行数

- base.md: 約 60-80 行（state machine ロジックに集中）
- SKILL.md (overlay): 約 100-120 行（呼び先と SisterGame 固有規約）

---

## 3. `create-feature` の分離マッピング

現状 157 行を以下の通り分離する。

### 3.1 base.md に置く内容（HOW）

| 元 SKILL.md セクション | 行範囲 | 抜粋理由 |
|-----------------------|--------|---------|
| ステップ0 ブランチ作成（git checkout 手順） | 13-22 | git workflow は generic |
| TDD ステップ概要（Red → Green の流れ） | 61-88 | TDD サイクルは標準パターン |
| Red/Green 判定の generic ルール | 70-72, 86-88 | 「テストが Fail / Pass する」検証の汎用記述 |
| 自己チェックリスト（イベント対称性、リソース解放） | 113-114 | 言語非依存の generic checks |
| エラー時のリトライ戦略 | （なし、build-pipeline 側に内包） | - |

### 3.2 overlay (SKILL.md) に残す内容（WHAT）

| 元 SKILL.md セクション | 行範囲 | 残す理由 |
|-----------------------|--------|---------|
| frontmatter | 1-6 | skill メタ情報 |
| 将来タスク（FUTURE_TASKS.md 参照） | 28-34 | SisterGame 固有 |
| 重複検出（`tools/feature-db.py list`） | 36-51 | feature-db は SisterGame 固有 |
| ステップ1 仕様確認（`feature-spec.md` フォーマット） | 53-59 | SisterGame fmt |
| テスト配置パス (`Tests/EditMode/{Name}Tests.cs`) | 65-66 | Unity 固有 |
| MCP `run_tests` / Unity CLI | 74-77 | Unity 固有 |
| ステップ4 実装の規約参照 (`unity-conventions.md`、`asset-workflow.md`) | 80-84 | SisterGame rules |
| ステップ5.5 結合テスト (`Tests/EditMode/Integration_{Name}Tests.cs`) | 93-102 | Unity 固有 |
| ステップ6 自己チェックの Unity 規約系 (`ScriptableObject`、`Addressable`) | 107-114 (一部) | Unity 固有 |
| ステップ7 feature-db 記録 | 116-127 | SisterGame 固有 |
| ステップ7.5 FUTURE_TASKS.md 更新 | 129-133 | SisterGame 固有 |
| ステップ8 git コミット規約（Co-Authored-By, scope） | 135-143 | SisterGame 規約 |
| ステップ9 アセット要求 (`asset-request.md`) | 145-151 | SisterGame 固有 |

### 3.3 期待行数

- base.md: 約 50-70 行（TDD サイクル + git/branch generic 手順）
- SKILL.md (overlay): 約 80-100 行（Unity 配置・rules 参照・SisterGame artifact）

---

## 4. 既存実装との対比 — `playtest-orchestrator/agent.md` 方式

agent 側 (`.claude/agents/playtest-orchestrator/agent.md`) では既に **reference ディレクトリ**方式を採用している（test-types/ 以下に分割）。
これは「**長文の知識ベースを別ファイルに切り出す**」アプローチで、Two-layer の **base/overlay 分離**とは目的が異なる。

| 方式 | 目的 | 適用例 |
|------|------|-------|
| reference ディレクトリ | 長文知識を分割して読み込み量を制御 | `playtest-orchestrator/test-types/t*.md` |
| **Two-layer (本 Phase 10)** | **HOW (汎用) と WHAT (固有) を分離して移植性向上** | build-pipeline / create-feature |

両者は併用可能。例えば base.md が肥大化したら、base 配下に reference サブディレクトリを切ることもできる。Phase 10 ではまず Two-layer に絞り、reference 化の判断は P10-T5 で個別検討する。

---

## 5. 検証方法（P10-T2/T3 の動作確認）

各試験対象 skill について以下を確認:

1. **Read 検証**: SKILL.md の `@base.md` 参照ブロックが正しいパスを指している（タイポ無し）
2. **手動 dry-run**: ユーザーに `/build-pipeline` または `/create-feature` を一度実行してもらい、両層が併読されることを Claude 側のレスポンスから確認（base.md の TDD ステップ概念と SKILL.md の Unity 固有手順が両方反映されているか）
3. **行数測定**: 分離前後で `wc -l SKILL.md base.md` を記録し、READMEに対比表として残す

実行時に skill が両層を確実に併読する保証は Claude Code の現仕様には**ない**ため、`@base.md` の信頼性は低い。これを補うため、SKILL.md の冒頭で base.md の主要観点を 1-2 行で要約しておく（Claude が SKILL.md だけ読んでも最低限の HOW を把握できるように）。

---

## 6. P10-T5 — 残 22 skill への適用判定表

P10-T2/T3 の試験実装後、残 22 skill（`build-pipeline` / `create-feature` 以外）に対し、規模・HOW/WHAT 比・再利用見込みの 3 軸で適用判定を行った結果を以下に示す。

### 判定軸

| 軸 | 内容 | 重み |
|----|------|------|
| **規模** | SKILL.md が 100 行以上か（短い skill は分離コスト > 利益） | 強 |
| **HOW/WHAT 比** | 手順論理（HOW）と SisterGame 固有要素（WHAT）の混在度 | 強 |
| **再利用見込み** | 別プロジェクト（将来の他ゲーム/別 LLM プロジェクト）に流用したいか | 中 |

判定区分:
- **🟢 適用推奨** — 大規模 + HOW/WHAT バランス + 再利用価値あり。次セッション以降で順次 Two-layer 化
- **🟡 適用候補（要観察）** — 中規模で価値あり。試験 2 skill の運用効果を見て判定
- **🔴 適用しない** — 短い primitive、または SisterGame 固有度が極端に高くて分離価値が出ない

### 判定結果

| skill | 行数 | 区分 | 理由 |
|-------|------|------|------|
| `consume-future-tasks` | 364 | 🟢 | 大規模。並列 worktree 実装 + テスト + PR の orchestration ロジックは generic、tag 体系・FUTURE_TASKS.md 連携は WAT |
| `design-systems` | 268 | 🟢 | 大規模。feature DB 操作 + 設計テンプレート読み出しの workflow 部分は HOW、機能カテゴリ・asmdef 設計は WHAT |
| `playtest` | 451 | 🟢 | 最大規模。既に reference ディレクトリ採用済（test-types/）。Two-layer + reference 併用パターンの先行事例として有望 |
| `generate-char-designs` | 291 | 🟡 | 大規模だが Flanime + ComfyUI + Kaggle の固有度が高い。HOW（生成パイプライン）/ WHAT（モデル設定）分離は可能だが価値要観察 |
| `create-ui` | 208 | 🟡 | UI Toolkit（UXML/USS）固有。HOW（コンポーネント生成手順）と WHAT（Unity 配置）は分離可能だが Unity 依存度高い |
| `unicli` | 164 | 🟡 | Unity CLI 操作。HOW（コマンド呼び出し汎化）/ WHAT（オプション一覧）の分離余地はあるが overlay 比重大きい |
| `design-game` | 159 | 🟡 | 対話型 GDD 作成。HOW（ヒアリング → 文書化）と WHAT（SisterGame 用テンプレート）の比は要観察 |
| `manage-flags` | 144 | 🟡 | フラグ管理。HOW（CRUD・バリデーション）と WHAT（SisterGame ストーリー / マップローカル定義）の分離は可能 |
| `generate-assets` | 120 | 🔴 | Kaggle FLUX.2 + 音声マッチングの固有度が高い。分離価値が小さい |
| `run-tests` | 120 | 🔴 | Unity test runner の primitive。短く Unity 固有度が極大 |
| `security-review-local` | 118 | 🔴 | tools/pr-validate.py 連携が中心、外部依存固有度が極大 |
| `drawio` | 111 | 🔴 | draw.io 図生成、用途特化で再利用見込み低い |
| `validate-scene` | 107 | 🔴 | Unity scene 検証 primitive。Unity MCP 依存固有度が極大 |
| `debug-assist` | 95 | 🔴 | 100 行未満、Unity MCP debug 連携固有度が高い |
| `design-stage` | 95 | 🔴 | 100 行未満、stage-layout-2d format 固有度が高い |
| `create-balance-sheet` | 68 | 🔴 | 短い、ゲーム固有 |
| `create-event` | 55 | 🔴 | 短い、Timeline + Dialog UI 固有 |
| `create-map-reference` | 51 | 🔴 | 短い、HTML map 固有 |
| `adjust-stage` | 54 | 🔴 | 短い、stage 学習ノート固有 |
| `bind-assets` | 37 | 🔴 | 短い primitive |
| `build-game` | 41 | 🔴 | 短い、Unity build 設定固有 |
| `test-game-ml` | 59 | 🔴 | 短い、ML-Agents 固有 |

### サマリ

- **🟢 推奨 (3 skill)**: `consume-future-tasks` / `design-systems` / `playtest`
- **🟡 要観察 (5 skill)**: `generate-char-designs` / `create-ui` / `unicli` / `design-game` / `manage-flags`
- **🔴 適用しない (14 skill)**: 残り全て

### 次アクション

1. **`build-pipeline` / `create-feature` の試験運用**を 1-2 週間継続し、Two-layer 化の効果（HOW 部分の他プロジェクト流用、SKILL.md 読み込み量、Claude が両層を併読しているかの観察）を `docs/compound/` に記録
2. 効果が確認できたら **🟢 3 skill** から順次 Two-layer 化 PR を出す
3. **🟡 5 skill** は半年後の reflection で再評価（特に `playtest` と reference 方式の併用パターンを学んだ後）

`drawio` / `validate-scene` / `security-review-local` の 3 skill は 100 行超だが、いずれも特定外部ツール依存が極端に強く、HOW を抜き出しても再利用価値が出ないため 🔴 判定とした。

---

## 7. 参考資料

- `docs/WAVE_PLAN.md` L693-702（Phase 10 タスク定義）、L1076-1080（Session 0 読み物リスト）
- `~/.claude/plans/humming-dancing-conway-agent-aa34619d19ec44a2a.md` §3.5（あれば Overstory two-layer 詳細）
- [Claude Code Issue #27113](https://github.com/anthropics/claude-code/issues/27113) — declarative skill dependency 公式議論
- `.claude/skills/README.md` 117 行目の reference ディレクトリ言及（既存のドキュメント切り出し方針）
