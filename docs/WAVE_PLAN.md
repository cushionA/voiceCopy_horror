# SisterGame Claude Code パイプライン改善プラン（v2 — 2026-04-24 再構築）

## セッション再開手順（別セッションで本 plan を開いた場合）

1. **過去の学びを把握**
   - `docs/compound/` の最新 3 エントリを Read（年月日降順でファイル名ソート）
   - `docs/compound/README.md` の運用ルールも確認
2. **完了済み PR を確認**
   - `gh pr list --state merged --search "refactor/pipeline OR feature/wave"` で関連 PR をスキャン
   - 下記「完了済み」セクションと突合し、進捗を更新
3. **進行中の Wave を特定**
   - `git branch -a | grep -i wave` で Wave ブランチの有無を確認
   - `git log --oneline -10` 最近のコミットから現在の作業を把握
4. **前提知識の確認**
   - `.claude/rules/wave0-audit.md` — rules 精読成果（各 Phase で引用）
   - `.claude/rules/lint-patterns.json` — Phase 11 用 40 パターン（前倒し済）
   - `.claude/rules/security-patterns.json` — Phase 21 用 prompt injection / CVE（前倒し済）
   - `.claude/skills/README.md` — 現在のスキル依存グラフ
5. **次の作業を選ぶ**
   - 本 plan file の「実装順序と依存関係」→ Wave 単位で作業を選択
   - 各 Phase の「Session 0 読み物リスト」で事前必要情報を確認

---

## Context

Unity 2D アクションゲーム「SisterGame」開発プロジェクトにおける、Claude Code + 40+ スキルの独自パイプラインの段階的改善計画。

### 再構築の経緯
- **v1**: 現場課題（スキル過多、FUTURE_TASKS 肥大化、pipeline-state 未実装）から Phase 1-11 を策定し、Phase 1-3 + dream-skill 導入を実装（PR #44）
- **v2（本版）**: ユーザー研究資料 `C:\Users\tatuk\Desktop\GameDev\AI研究\reserch\` の 2 文書（claude_baseKnowledge.md 553 行 + claude_knowledge.md 610 行）を 2 エージェント並列で精読、最新知見（2026/04 時点）で全面更新

### 設計原則（v2 で確定）
1. **Harness 設計 >> モデル性能**（Anthropic 公式 2 本の宣言）
2. **検証可能な外在化**: pipeline-state.json、handoff-note、registry.md の三位一体で context rot を回避
3. **二相エージェント構造**: 初期化エージェント + コーディングエージェントを分離
4. **Cross-model consensus**: 単モデルレビューを信用しない、Adversarial Review を標準化
5. **TDD を hook で物理強制**: プロンプト指示では mechanical adherence しか得られない
6. **Compound Engineering 50/50**: 新機能 50% / institutional knowledge 50%
7. **外部スキルはライフサイクル短め前提**: Anthropic が 2 段階吸収するため

---

## 完了済み（PR #44 + dream-skill 導入）

### Phase 1: スキル統廃合 ✅
- `plan-sprint` → `design-systems` 統合
- `index-assets` → `generate-assets index` 内包
- `list-assets` → 廃止（feature-db.py assets 代替）
- `playtest` / `run-tests` 役割明示化

### Phase 2: FUTURE_TASKS 管理改善 ✅
- タグ体系（🔴🟡🟢 + ✓⚠🔶）とエントリテンプレート
- `docs/ARCHIVED_TASKS.md` 新設
- `consume-future-tasks` SKILL を新タグ体系に対応

### Phase 3: pipeline-state 復活 ✅
- `designs/pipeline-state.json` 作成（初期 `phase: "idle"`）
- `build-pipeline` SKILL に状態操作手順と書き込みタイミング表を明記

### 追加実装
- `.claude/skills/README.md` でスキル依存グラフを人間向けに明示化
- **dream-skill 導入**: `~/.claude/skills/dream/` + Stop hook で 24h 自動メモリ統合
- CLAUDE.md に dream 連携節追加

---

## 次フェーズ計画

既存 Phase 4-11 を**リサーチ由来の新知見で全面更新**し、Phase 12-25 を新規追加する。

### 優先度の凡例
- 🥇 **即実装推奨**: 2026-04-25 以降の次セッションで着手可
- 🥈 **中期（1-4 週間）**: 素材と前提が揃ったら実装
- 🥉 **中長期（1-3 ヶ月）**: 先行フェーズの成果を見てから着手
- ⏸ **監視・再評価**: 外部依存・成熟度を見ながら判断

---

## Phase 4（改訂）: CLAUDE.md 剪定 + path-scoped 化 🥇

**v1 → v2 更新ポイント**:
- ~~40-60 行目標~~ → **100-200 行 / 2.5k トークン以下**（Boris Cherny 基準、[HumanLayer 分析](https://www.humanlayer.dev/blog/writing-a-good-claude-md) で命令数上限 100-150）
- **`@` インポート多用禁止**、「必要なら読め」方式（anvodev 47k→9k 削減事例 [DEV](https://dev.to/anvodev/how-i-organized-my-claudemd-in-a-monorepo-with-too-many-contexts-37k7)）
- **Architecture 指定を最優先**（[arXiv 2511.09268](https://arxiv.org/html/2511.09268v1) の 328 プロジェクト分析）
- **session 中の CLAUDE.md 編集 = dynamic zone キャッシュ全無効化**を踏まえて、編集禁止時間帯を設ける
- Unity 特化 4 行ヘッダーを冒頭に配置（Unity Version / RP / Input System / Scripting Backend）

### 対象ファイル
- `CLAUDE.md`（現状 ~180 行、トークン計測後に再編成）
- `Architect/`, `Assets/` 直下に path-scoped CLAUDE.md を配置

---

## Phase 5（改訂）: スキル棚卸しの運用化 🥈

**v1 → v2 更新ポイント**:
- 「20+ slash command はアンチパターン」([Shrivu Shankar](https://blog.sshh.io)) を明記
- 四半期棚卸しで「直近 2 ヶ月未使用」スキルを `/archive` 化
- **メタスキル `/writing-skills` 導入**（obra/Superpowers 準拠、[fsck.com blog](https://blog.fsck.com/2025/10/09/superpowers/)）
- Skill description 改善は**三者ループ**（Skill 作者 × 使い手 × 人間専門家）で反復
- **[SkillsBench](https://arxiv.org/pdf/2602.12670) 平均 +16.2pp** を根拠に配置精度を数値管理

### 新設ファイル
- `docs/SKILL_LIFECYCLE.md` — 棚卸しルーチン定義

---

## Phase 6（改訂）: Hook 駆動 quality gate 🥇

**v1 → v2 更新ポイント**:
- **`nizos/tdd-guard`** を PostToolUse ではなく **PreToolUse hook** で傍受し、Write/Edit/MultiEdit/TodoWrite をブロック対象に
- **hook 間でファイル永続化検証コンテキスト**（IPC 不要）
- **[aitmpl 39+ Hooks](https://www.aitmpl.com/hooks/)** を素材集として参照
- **Lasso Prompt Injection Defender**（tool output を別モデルで判定）を PostToolUse で検討
- `TaskCompleted` / `TeammateIdle` による quality gate は継続（v1 踏襲）

### 補足
- 公式の `allowManagedHooksOnly` で Enterprise 強制も可能（個人プロジェクトでは不要）

---

## Phase 7（改訂）: pipeline-state + phase-boundary commit 連動 🥈

**v1 → v2 更新ポイント**:
- Anthropic **[Effective Harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)** の**二相構造**を準拠
  - **初期化エージェント**: `init.sh` + `claude-progress.txt` + 検証可能要件 JSON リスト + 初期 git commit を生成
  - **コーディングエージェント**: 以降同一ハーネスで increment のみ
- `pipeline-state.json` を検証可能要件リスト化（phase 完了条件を機械判定可能に）
- PostToolUse hook で phase 完了時に自動 commit → `/rewind` + "Rewind code only" でロールバック可能な checkpoint に

---

## Phase 8（改訂）: Compound Engineering 自動トリガー 🥇

**v1 → v2 更新ポイント**:
- 単に `consolidate-memory` を回すのではなく、**[Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin) 4 ステップループ** (Plan → Work → Review → **Compound**) に昇格
- 「**50% 新機能 / 50% institutional knowledge**」の時間配分を明示
- **コンテキストが新鮮なうちに compound**（`/compact` や終了直前では遅い）
- consolidate-memory に**削除・統合ロジック**を追加（[arXiv 2509.25250](https://arxiv.org/pdf/2509.25250) の experience following property: 欠陥メモリがエージェントを劣化させる）

### 成果物
- `docs/compound/YYYY-MM-DD-<topic>.md` — YAML frontmatter 付き learning artifact
- Stop hook で session 終了時に自動生成

---

## Phase 9（改訂）: 外部スキル組み込み ⏸

**v1 → v2 更新ポイント**:
- Anthropic **2 段階吸収サイクル**（Ralph→`/loop`、Community swarm→TeammateTool、Beads→Tasks）を認識し、**ライフサイクル短めを前提に設計**
- 候補リポジトリ明示化:
  - **[wshobson/agents](https://github.com/wshobson/agents)**: 184 agents + 150 skills + 98 commands
  - **[rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)**: 135 agents + 35 skills
  - **[anthropics/skills](https://github.com/anthropics/skills)**: 37.5k★
  - **[ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)**: 外部 API 系
- **Unity 特化**:
  - [Unity App UI 公式 plugin](https://docs.unity3d.com/Packages/com.unity.dt.app-ui@2.2/manual/claude-plugin.html) — 保留（UI 戦略見直し時に再評価）
  - [The1Studio/theone-training-skills](https://github.com/The1Studio/theone-training-skills) — 見送り（VContainer/SignalBus 強制で SoA + GameManager と衝突）
  - [Dev-GOM/claude-code-marketplace の unity-dev-toolkit](https://github.com/Dev-GOM/claude-code-marketplace/blob/main/plugins/unity-dev-toolkit/README.md) — **14 items**（7 skills + 4 agents + 3 commands、Apache-2.0）。WAVE_PLAN 当初記述の「66 skills」は誤情報。SisterGame 既存資産と 11 項目重複・「実験段階・動作保証なし」のため見送り
  - **[Nice-Wolf-Studio/unity-claude-skills](https://github.com/Nice-Wolf-Studio/unity-claude-skills)** — 35 skills, MIT, Unity 6.3 LTS。**16 skills を採用**（A:rules 抽出 / B:静的 ref / C:auto-trigger skill / D:Architect リライト統合）。詳細: `.claude/rules/_attribution.md` および `docs/reports/research/2026-04-25_external-skills-evaluation.md`
- 導入前に Architect/ の設計文書と整合性チェック

---

## Phase 10（改訂）: スキル依存グラフ 🥈

**v1 → v2 更新ポイント**:
- v1 で `.claude/skills/README.md` に初版を作成済み
- **Overstory の Two-layer agent definitions**（base.md = HOW / overlay = WHAT）方式を採用検討
- primitive / composition 分離原則を継続
- `.claude/agents/<name>.md` の frontmatter（`tools:`、`memory:`、`isolation: worktree`）を活用

---

## Phase 11: 静的分析 hook（キーワードベース） 🥇

**v1 の設計メモを引き継ぐ**（詳細は過去版参照）:
- `.claude/rules/lint-patterns.json` に NG パターン定義（25 個目安）
- `.claude/hooks/lint-check.sh` が Edit/Write 直後に diff を grep
- 重大度別分岐: warning → stdout のみ / error → `asyncRewake` で Claude に差し戻し
- 初期パターン: Update 内アロケーション、`var` 禁止、絵文字、`CompareTag` 推奨、Core 配下 `Debug.Log` → `AILogger.Log`、TODO/FIXME/XXX、`GameObject.Find`、`Vector3.Distance`、magic number、async void、Addressable 未使用 等

**v2 追加**: **ClaudeWatch 風 self-healer** — Write/Edit 後に Unity console・テスト・visual を unity-mcp 経由で検証し、失敗時は fix 試行してフィードバック

---

## Phase 12: Adversarial Review gate 🥈

**新規** — Anthropic 内部レビュー substantive 率 16%→54% 実績の移植。

### 方式
- **[ng-adversarial-review](https://github.com/...)** プラグイン相当: **Optimizer（Sonnet）+ Skeptic（Opus）並列**
- **Cross-model consensus**: 両モデル合意のみ auto-fix、不一致は author に dispute 提示
- スコア閾値:
  - ≤ 0: report なし
  - 1-4: Sonnet-only
  - ≥ 5: dual-model
- **公式 `plugins/code-review` の 4 並列パターン**: 2 Sonnet（compliance）+ 2 Opus（logic/security）+ 独立検証 subagent
- false positive を別 subagent で独立検証（HIGH SIGNAL のみ出力）

### 新設スキル
- `/adversarial-review` — PR 後の並列合議

---

## Phase 13: TDD 3 サブエージェント分離 + TDD-Guard 🥇

**新規** — `alexop.dev` の循環論法防止パターン。

### 方式
- `.claude/agents/` に **`tdd-test-writer` / `tdd-implementer` / `tdd-refactorer`** を別コンテキストで定義
- **同一コンテキストだとテストが無意識に実装に fit される循環論法を物理的に防ぐ**
- `create-feature` スキルを 3 分割ワークフローに改修
- Unity Edit Mode テストに適合させる

### Hook 連動
- **TDD-Guard**（[nizos/tdd-guard](https://github.com/nizos/tdd-guard)）の PreToolUse hook で:
  - ① 失敗テストなしの実装をブロック
  - ② テスト要件超過実装をブロック
  - ③ 複数テスト同時追加をブロック
- 作者認識の引用: 「**ブロッキングだけでは mechanical adherence。REFACTOR 段階を LLM はスキップしがち**」→ 3 エージェント分離で対処

### 新設スキル
- `/tdd-guard-setup` — hook 導入を案内

---

## Phase 14: Mutation Testing 統合 🥉

**新規** — swingerman/atdd の第 6 フェーズ相当。

- **Stryker .NET** を Unity プロジェクトに導入（AST mutator）
- **Property-based + Stryker mutation 80% 閾値**で弱テスト特定
- Meta 社 "Just-in-Time Catching Test Generation"（回帰検出 4 倍）を参照
- `create-feature` 完了時のオプション検証ステップとして統合

---

## Phase 15: コスト可視化 + Advisor 経済性 🥈

**新規** — $1,600/hour 事故対策。

### コスト可視化
- Stop hook で `/cost` 出力を `.claude/cost-log.jsonl` に追記
- 月次集計スクリプト `tools/cost-report.py` を新設
- `ccusage` OSS 連携（JSONL セッション集計）

### Advisor Strategy（[Anthropic 内部実測 11% 削減](https://www.anthropic.com/...)）
- **Opus = 非実行アドバイザー**（計画/アーキテクチャ/レビュー、**コードに触れない**）
- **Sonnet/Haiku = 実装者**
- `/design-systems` 系は Opus 固定、`/create-feature` 系は Sonnet or Haiku 固定
- `/model opusplan` をデフォルト化で Plan↔Impl 自動切替（40% 削減）

### 環境変数設定
```json
{
  "env": {
    "DISABLE_NON_ESSENTIAL_MODEL_CALLS": "1",
    "MAX_THINKING_TOKENS": "8000"
  }
}
```

### 新設スキル
- `/cost-report` — 集計と閾値アラート

---

## Phase 16: 5 分 Cache TTL 対策 🥈

**新規** — 2026 初頭の Prompt Cache TTL 変更（60 分 → 5 分）対応。

### 課題
- バースト型の節約率 **84%→52%** に悪化
- 長時間の `/build-pipeline continue` や夜間バッチで特に影響

### 対策
- **4 分インターバル keepalive ping**（軽量プロンプト送信）
- **1 時間 TTL 明示指定**（書き込み 2 倍コストと引換え）
- **Static / Dynamic ゾーン分離**: CLAUDE.md 編集を session 中に避ける
- [Issue #19436](https://github.com/anthropics/claude-code/issues/19436) の multi-tier caching を watch

---

## Phase 17: Registry-based handoff + Handoff Note 自動化 🥈

**新規** — Ilyas Ibrahim の 26 エージェント失敗事例からの逆算。

### 方式
- **`.claude/reports/_registry.md`** を中心にカテゴリ別 report フォルダ:
  - `analysis/` / `arch/` / `bugs/` / `commits/` / `design/` / `exec/` / `handoff/` / `impl/` / `review/` / `tests/` / `archive/`
- build-pipeline 入口で `_registry.md` 参照を強制（SessionStart hook）
- Stop hook で自動 handoff note 生成: `docs/handoff-notes/YYYYMMDD-HHMM.md`
- 次セッション冒頭に `/resume-handoff` Skill でロード
- 効果: effective context を**20 分 → 2 時間**に延長（Ilyas 実測）

### 新設スキル
- `/handoff-note` — 手動生成
- `/resume-handoff` — 前回状態のロード
- `/registry-check` — SessionStart 強制

---

## Phase 18: Ralph / Compound ループによる長時間バッチ 🥉

**新規** — Geoffrey Huntley の `while true` パターン + Every 社 Compound。

### 方式
- `/consume-future-tasks` を **Ralph パターン化** — bash ループが `FUTURE_TASKS.md` を read-continue する stateless agent
- **コンテキストを毎回 malloc 再割当て** → compaction/context rot を根絶
- **Dual-condition exit gate**（[frankbria/ralph-claude-code](https://github.com/frankbria/ralph-claude-code)）:
  - completion indicator **AND** EXIT_SIGNAL 両方で誤完了防止
  - `MAX_CONSECUTIVE_TEST_LOOPS=3` / `MAX_CONSECUTIVE_DONE_SIGNALS=2` / `TEST_PERCENTAGE_THRESHOLD=30`
- 夜間バッチで未完タスクを自動消化（auto mode + sandbox 三重防御前提）

### Anthropic の吸収警告
- Ralph Wiggum plugin → 公式 `/loop` 抽象化に吸収済み
- **`/loop`** が使える場合は公式優先

---

## Phase 19: Harness 二相分離 🥉

**新規** — Phase 7 の深化版として独立フェーズ化。

### 方式
- `build-pipeline` を**初期化エージェント専用**に
  - `init.sh` + 要件 JSON リストを生成
  - `create-feature` 以降のコーディングには関与しない
- **コーディングエージェント**は `.claude/agents/coding-agent.md` として別定義
  - `tools:` を Read/Edit/Write/Bash に限定
  - `memory: project` で memory 階層制限

### 効果
- 初期設計と実装の context 汚染を分離
- increment のみの軽量ループで long-running に強くなる

---

## Phase 20: Sandbox + Docker --network none 強化 🥈

**新規** — `--dangerously-skip-permissions` と `--permission-mode plan` の**silent override bug（[Issue #17544](https://github.com/anthropics/claude-code/issues/17544)）対策**。

### 方式
- `--dangerously-skip-permissions` を**必ず Docker `--network none` + 非 root** で隔離
- 60 秒毎に GitHub auto-commit（損失ゼロ保証）
- セッション終了でコンテナ破棄
- `--permission-mode plan` との**組合せは避ける**
- sandbox で権限プロンプト **84% 削減**（公式実測）

---

## Phase 21: Comment and Control 攻撃防御 🥇

**新規** — 2026 初頭の新種脆弱性（[SecurityWeek](https://www.securityweek.com/claude-code-gemini-cli-github-copilot-agents-vulnerable-to-prompt-injection-via-comments/)）。

### 課題
- Claude Code Security Review / Gemini CLI Action / Copilot Agent が **GitHub コメント経由で hijack** される
- "Ignore all previous instructions" パターン等

### 対策
- PR レビュースキルに:
  - **Zod/JSON schema バリデーション**
  - **"Ignore all previous instructions" パターン検出**
  - **fail-closed デフォルト**
- **untrusted GitHub 入力と secrets を同一ランタイムで扱わない**
- 既知 CVE をチェックリスト化:
  - CVE-2025-54794（経路制約バイパス、≤ v0.2.111）
  - CVE-2025-54795（コマンド実行、≤ v1.0.20）
  - CVE-2025-55284（DNS exfil）
  - Adversa 50 no-op subcommand bypass（v2.1.90 修正）

---

## Phase 22: Unity 特化 hook と skill 輸入 🥈

**新規**:

### Unity-specific hooks
- `PostToolUse(Edit|Write).cs`: unity-mcp の `read_console` で compile error 自動検査
- `pre-build` hook: `validate:project`
- `post-build` hook: `test:playmode`
- `pre-release` hook: `check:size`（APK/IPA サイズ回帰検出）

### Unity skill 輸入
- Unity App UI 公式プラグイン（navigation/theming/state management skill 同梱）
- Unity MCP (CoplayDev) — scene/profiler/physics/animation/ProBuilder（既導入）
- TheOne Studio の C# 9 / VContainer DI / SignalBus スキルを Architect/ と整合性チェック後に取り込み

---

## Phase 23: Spec-Driven Development (SDD) 統合 🥉

**新規** — SisterGame の `/design-game` → `/design-systems` → `/create-feature` 三段構成を SDD 準拠にリフォーマット。

- Requirements → Design → Tasks → Implementation の 4 フェーズを subagent 並列化
- 参考: [Pimzino/claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow)、[gotalab/cc-sdd](https://github.com/gotalab/cc-sdd)（Kiro 由来）
- **FeatureBench 11% / SWE-bench 74.4% 落差**を踏まえ、**人間の計画注入を create-feature の前提とする**

---

## Phase 24: Compound 恒常化（learning artifact 蓄積） 🥈

**新規** — Phase 8 の成果物運用の独立化。

- `docs/compound/` を正式リポジトリとして定義
- YAML frontmatter 必須項目: `topic`, `date`, `outcome`, `related_pr`, `files_affected`
- PR レビュー完了後に自動抽出
- 月次で CLAUDE.md / `Architect/` / FUTURE_TASKS.md に昇格させる review 会を設ける

### 新設スキル
- `/compound-learn` — 抽出ワークフロー

---

## Phase 25: 失敗パターン辞書化 🥉

**新規** — `.claude/rules/anti-patterns.md` として成文化。

| パターン名 | 症状 | 対策 |
|-----------|------|------|
| Kitchen sink session | 無関係タスク混在 | `/clear` で区切る |
| Correction loop | 2 回修正しても直らない | `/clear` + 学びを反映した新プロンプト |
| Agent dumb zone | context 60-70% 超で基本ルール無視 | `/compact` with preserve instruction |
| Bad compact | 劣化後 compact は劣化を内包 | Dream 4-phase / compound で事前処置 |
| Confident hallucination | 存在しない関数引用 | Writer/Reviewer Fresh Context 原則 |
| Infinite loop on failed approach | 同じ失敗 5 回 | 「知ってること全部使って、elegant solution に書き直せ」で打ち切り |
| Running-but-wrong code | コンパイル通過を正解と混同 | 「新規参入が保守しやすいか」追加チェック |
| Long custom slash command list | 20+ で希釈化 | 四半期棚卸し（Phase 5） |

---

## 矛盾・更新情報まとめ（v1 → v2）

### 定量基準の更新
| 項目 | v1 | v2 | 採用理由 |
|------|-----|-----|---------|
| CLAUDE.md 長さ | 40-60 行 | **2.5k トークン以下（100-200 行）** | Boris Cherny 基準、HumanLayer 分析 |
| worktree 並列 | 5 本 | **3-4 本（Windows+Unity 実務）** | Boris のローカル 5 は Anthropic 内部環境前提 |
| Skill メタデータ予算 | ~42 skills | **20+ はアンチパターン** | Shrivu Shankar（区間整合） |

### 2026 初頭の重要変更
1. **Prompt Cache TTL 60 分 → 5 分**（バースト節約率 84%→52%） → Phase 16 必須
2. **"Comment and Control 攻撃"** — GitHub コメント経由 hijack → Phase 21 必須
3. **`--dangerously-skip-permissions` + `--permission-mode plan` silent override bug** → Phase 20 必須
4. **FeatureBench 11%（feature-level 実装は壊滅的）** → Phase 23 の人間計画注入必須
5. **5 層 compaction パイプライン**（Budget reduction/Snip/Microcompact/Context collapse/Auto-compact）が [arXiv 2604.14228](https://arxiv.org/html/2604.14228) で公式実装から抽出済み

### マルチエージェント採用判断
- **+90.2% 性能向上**（Anthropic multi-agent research）
- **トークン 15 倍消費** — tightly interdependent タスクには不向き
- SisterGame の Unity + ECS は interdependent 高い → **並列化は設計・リサーチ系に限定**
- Agent Teams は実験機能、Boris 本人も慎重 → **Ralph パターンのほうが実践的**（Phase 18）

---

## 実装順序と依存関係

### スプリント 1（即実装、2-3 日）
1. **Phase 4** — CLAUDE.md 剪定（トークン測定 → 2.5k 以下に）
2. **Phase 6** — TDD-Guard PreToolUse hook 導入
3. **Phase 8** — Compound ループの手動版運用開始
4. **Phase 11** — 静的分析 hook（キーワード辞書 + lint-check.sh）
5. **Phase 21** — Comment and Control 防御（Zod validation 導入）

### スプリント 2（1-2 週間）
6. **Phase 5** — スキル棚卸しルーチン文書化
7. **Phase 10** — スキル依存グラフの Two-layer 化
8. **Phase 12** — Adversarial Review gate
9. **Phase 13** — TDD 3 サブエージェント分離
10. **Phase 15** — コスト可視化 + Advisor Strategy
11. **Phase 17** — Registry-based handoff
12. **Phase 20** — Sandbox 強化
13. **Phase 22** — Unity 特化 hook

### スプリント 3（中長期、1-3 ヶ月）
14. **Phase 7** — Harness 二相の pipeline-state 連動
15. **Phase 14** — Mutation Testing
16. **Phase 16** — Cache TTL 対策
17. **Phase 18** — Ralph ループ
18. **Phase 19** — Harness 二相分離
19. **Phase 23** — SDD 統合
20. **Phase 24** — Compound 恒常化
21. **Phase 25** — anti-patterns.md

### 監視（⏸）
- **Phase 9** — 外部スキル Anthropic 吸収動向をチェック

---

## 新設予定スキル・hook 一覧

### Skills
- `/writing-skills` — メタスキル（Phase 5）
- `/cost-report` — 月次コスト集計（Phase 15）
- `/adversarial-review` — クロスモデル合議（Phase 12）
- `/tdd-guard-setup` — TDD-Guard 導入案内（Phase 13）
- `/handoff-note` — 手動 handoff（Phase 17）
- `/resume-handoff` — 前回状態ロード（Phase 17）
- `/registry-check` — SessionStart 強制（Phase 17）
- `/compound-learn` — learning artifact 抽出（Phase 24）
- `/review-parallel` — 公式 4 並列パターン（Phase 12）

### Hooks（`.claude/settings.json`）
- `PreToolUse(Edit|Write|MultiEdit)` — TDD-Guard（Phase 13）
- `PostToolUse(Edit|Write).cs` — lint-check + Unity compile 検査（Phase 11/22）
- `PostToolUse(Edit)` — self-healer（Phase 11）
- `PreToolUse(Bash)` — `rm -rf`, `curl`, dangerous flag ブロック（Phase 20）
- `PreToolUse(Write)` — CLAUDE.md / settings.json 保護（Phase 4）
- `Stop` — handoff note + cost 記録 + compound 抽出（Phase 15/17/24）
- `SessionStart` — registry 参照強制 + dream-pending チェック（Phase 17）
- `TaskCompleted` — quality gate（Phase 6）

---

## 検証方法（全体）

- **スプリント完了条件**: 各 Phase に記載の具体目標を満たす
- **定期再評価**: 月次で本 plan file を見直し、Anthropic の吸収・非推奨を反映
- **効果測定**:
  - コスト削減率（Phase 15 で月次計測）
  - effective context 時間（Phase 17 で 20 分 → 2 時間を確認）
  - レビュー substantive 率（Phase 12 で 16%→54% に近づくか）
  - テストカバレッジ + mutation score（Phase 14）

---

## 参考資料

### Anthropic 公式
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Harness Design for Long-Running Apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [plugins/code-review](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)

### コミュニティ・ベストプラクティス
- [HumanLayer: Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [alexop.dev: Spec-driven development](https://alexop.dev/posts/spec-driven-development-claude-code-in-action/)
- [fsck.com: Superpowers](https://blog.fsck.com/2025/10/09/superpowers/)
- [aitmpl Hooks](https://www.aitmpl.com/hooks/)
- [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)
- [nizos/tdd-guard](https://github.com/nizos/tdd-guard)
- [wshobson/agents](https://github.com/wshobson/agents)
- [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)

### 論文（2025-2026）
- [arXiv 2604.14228: Dive into Claude Code](https://arxiv.org/html/2604.14228)
- [arXiv 2509.25250: experience following property](https://arxiv.org/pdf/2509.25250)
- [arXiv 2602.10975: FeatureBench](https://arxiv.org/abs/2602.10975)
- [arXiv 2601.11077: ABC-Bench](https://arxiv.org/pdf/2601.11077)
- [arXiv 2511.05459: SWE-Compass](https://arxiv.org/html/2511.05459v1)
- [arXiv 2511.09268: CLAUDE.md analysis](https://arxiv.org/html/2511.09268v1)
- [arXiv 2602.12670: SkillsBench](https://arxiv.org/pdf/2602.12670)
- [arXiv 2509.16941: SWE-Bench Pro]
- [arXiv 2507.13334: Context Engineering Survey]
- [arXiv 2508.11126: AI Agentic Programming Survey]

### セキュリティ
- [SecurityWeek: Comment and Control 攻撃](https://www.securityweek.com/claude-code-gemini-cli-github-copilot-agents-vulnerable-to-prompt-injection-via-comments/)
- CVE-2025-54794 / 54795 / 55284
- [Issue #17544: silent override bug](https://github.com/anthropics/claude-code/issues/17544)

### 研究資料（ユーザー提供）
- `C:\Users\tatuk\Desktop\GameDev\AI研究\reserch\claude_baseKnowledge.md`（553 行、ベストプラクティス総説）
- `C:\Users\tatuk\Desktop\GameDev\AI研究\reserch\claude_knowledge.md`（610 行、発展的手法調査）
- 中間レポート: `humming-dancing-conway-agent-a383b60c19f3717e0.md` / `humming-dancing-conway-agent-aa34619d19ec44a2a.md`（2 エージェントの精読結果）

---

## 未決課題メモ（2026-04-24 時点）

### `.claude/rules/` モジュラー運用が未整備

現状:
- 6 ファイル（architecture / asset-workflow / git-workflow / template-usage / test-driven / unity-conventions、計 887 行）に分割済み
- CLAUDE.md からは「詳細: `.claude/rules/xxx.md`」のテキスト参照のみ

課題:
- `@` インポート / path-scoped CLAUDE.md / Skill references のいずれも未整備で、**受動的な Read に依存**している
- 本 plan v2 の各 Phase も rules 本文を精読せずに策定したため、具体条項（`k_` 定数命名、`_camelCase` private、`CompareTag` 推奨、Pack Together / Pack Separately 使い分け 等）が Phase 11 の lint-patterns などに反映できていない

次セッションでの対応候補:
1. 1 エージェントで 6 ファイル精読 → plan v3 化（各 Phase に具体条項を織り込む）
2. path-scoped CLAUDE.md の配置
   - `Assets/MyAsset/` → `@.claude/rules/unity-conventions.md` + `@.claude/rules/architecture.md`
   - `Assets/Tests/` → `@.claude/rules/test-driven.md`
   - `Assets/Addressables/` or アセット編集作業 → `@.claude/rules/asset-workflow.md`
3. `.claude/rules/README.md` を新設し、モジュラー運用のガイドラインを成文化
4. Hook / Skill で `.claude/rules/xxx.md` を source of truth として参照（Phase 11 の lint-patterns.json のパターン由来を明示リンク）

---

## 実装計画（WBS — Work Breakdown Structure）

### Wave 構成と全体見積

| Wave | 期間目安 | Phase | 総タスク | 総見積 |
|------|---------|-------|---------|--------|
| **Wave 0**（前処理） | 1 セッション | rules 精読 → plan v3 化 | 6 | 3-4 h |
| **Wave 1**（基盤） | 1-2 セッション | 4(前半), 8(手動版), 21 | 16 | 6-9 h |
| **Wave 2**（主要 hook 群） | 1-2 週間 | 4(後半), 10, 11, 17 | 26 | 15-22 h |
| **Wave 3**（品質強化） | 1-2 週間 | 5, 6, 13, 22 | 24 | 18-26 h |
| **Wave 4**（レビュー・経済性） | 2-3 週間 | 12, 15, 20, 25 | 22 | 14-20 h |
| **Wave 5**（高度パターン） | 1-2 ヶ月 | 7, 14, 16, 18, 19, 23, 24 | 34 | 28-42 h |
| **Wave 監視** | 継続 | 8(自動化), 9 | 7 | 継続観察 |
| **合計** | **3-4 ヶ月** | Phase 4-25（22 Phase） | **135 タスク** | **84-123 h** |

### 依存グラフ（クリティカルパス）

```
Wave 0 (rules 精読) ─┬─→ Phase 4 後半 ─→ Phase 11 ─→ Phase 13
                     ├─→ Phase 11 パターン定義
                     └─→ Phase 6, Phase 25

Phase 4 前半 (path-scoped) ─→ 全 Phase のコンテキスト基盤
Phase 8 手動版 ─→ Phase 24 恒常化 ─→ Phase 8 自動化
Phase 17 (Registry) ─→ Phase 19 (Harness 二相)
Phase 15 (コスト) ─→ 全 Phase の経済性前提
Phase 21 (セキュリティ) ─→ 独立、早期実装
```

**クリティカルパス**: Wave 0 → Phase 4 → Phase 11 → Phase 13 → Phase 24

---

### Wave 0: rules 精読 → plan v3 化（前処理）

**目的**: `.claude/rules/` 配下 6 ファイルの本文を反映し、後続 Phase の具体条項を plan に織り込む。

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| W0-T1 | `.claude/rules/` 6 ファイル精読 | なし | 読了 + 抜粋メモ | 45 分 |
| W0-T2 | Phase 4 の「Architecture 最優先」を architecture.md 根拠で肉付け | W0-T1 | plan 更新 | 20 分 |
| W0-T3 | Phase 11 lint-patterns に具体条項追加（25→40 パターンへ拡張） | W0-T1 | plan 更新 | 60 分 |
| W0-T4 | Phase 13 の TDD 3 サブエージェント分離を test-driven.md に整合 | W0-T1 | plan 更新 | 20 分 |
| W0-T5 | Phase 21 の PR レビューを git-workflow.md の「Code Reuse/Quality/Efficiency」観点と接続 | W0-T1 | plan 更新 | 20 分 |
| W0-T6 | Phase 25（anti-patterns）に rules の禁止事項を移植 | W0-T1 | plan 更新 | 30 分 |

**Wave 0 成果**: plan v3 化完了、rules 具体条項がプランに織り込まれる。

---

### Wave 1: 基盤（即着手可）

#### Phase 4 前半: path-scoped CLAUDE.md + トークン測定

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P4-T1 | 現 CLAUDE.md のトークン測定（`tiktoken` or `wc -c`/4） | なし | 現状値記録 | 10 分 |
| P4-T2 | Unity 特化 4 行ヘッダー追加（Version/RP/InputSystem/Backend） | P4-T1 | CLAUDE.md 冒頭更新 | 10 分 |
| P4-T3 | `Assets/MyAsset/CLAUDE.md` 新設（`@.claude/rules/unity-conventions.md` + `architecture.md`） | W0 | 新規ファイル | 20 分 |
| P4-T4 | `Assets/Tests/CLAUDE.md` 新設（`@.claude/rules/test-driven.md`） | W0 | 新規ファイル | 15 分 |
| P4-T5 | アセット編集作業用 path-scoped CLAUDE.md 配置先決定（Assets/Plugins 等は除外） | W0 | 配置計画 | 15 分 |
| P4-T6 | `.claude/rules/README.md` 新設（モジュラー運用ルール成文化） | W0 | 新規ファイル | 30 分 |
| P4-T7 | 動作確認（path-scoped CLAUDE.md が該当ディレクトリ作業時にロードされるか） | P4-T3-6 | 確認ログ | 30 分 |
| P4-T8 | コミット + push + PR | 上記全 | PR 作成 | 15 分 |

#### Phase 8 手動版: Compound ディレクトリ雛形

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P8m-T1 | `docs/compound/` ディレクトリ作成 + .gitkeep | なし | ディレクトリ | 5 分 |
| P8m-T2 | YAML frontmatter テンプレート定義（topic/date/outcome/related_pr/files_affected） | なし | `docs/compound/_template.md` | 20 分 |
| P8m-T3 | PR #44 からの learning を最初のエントリとして手動記入 | P8m-T2 | 最初のエントリ | 30 分 |
| P8m-T4 | CLAUDE.md に Compound 運用節追加（手動運用明記） | P8m-T2 | CLAUDE.md 更新 | 15 分 |
| P8m-T5 | コミット + push（自動化は Phase 24 で） | 上記 | コミット | 10 分 |

#### Phase 21: Comment and Control 防御

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P21-T1 | 既知 CVE リスト化（CVE-2025-54794/54795/55284/Adversa）を `.claude/rules/security-known.md` に記録 | W0 | 新規ファイル | 30 分 |
| P21-T2 | PR レビュー時の "Ignore all previous instructions" / "Disregard" 等検出パターン定義 | P21-T1 | regex 集 | 20 分 |
| P21-T3 | `/security-review` スキルに fail-closed デフォルト + prompt injection 検出を組込み | P21-T2 | SKILL.md 更新 | 45 分 |
| P21-T4 | Zod / JSON schema 形式での PR body validator スクリプト（Python） | P21-T3 | `tools/pr-validate.py` | 45 分 |
| P21-T5 | 検証（検出パターン自作 PR で動作確認） | P21-T4 | テスト結果 | 20 分 |
| P21-T6 | コミット + push + PR | 上記 | PR 作成 | 15 分 |

**Wave 1 合計**: 16 タスク / 6-9 時間 / 2-3 PR

---

### Wave 2: 主要 hook 群

#### Phase 4 後半: CLAUDE.md 剪定

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P4b-T1 | 冒頭 60 行の必須ルール抽出・整理 | Wave 1 完了 | 剪定案 | 60 分 |
| P4b-T2 | 残りの記述を `.claude/rules/` に移動 or 削除判定 | P4b-T1 | 移動マップ | 45 分 |
| P4b-T3 | CLAUDE.md 剪定実施（2.5k トークン以下目標） | P4b-T2 | 新 CLAUDE.md | 90 分 |
| P4b-T4 | トークン再測定 + 対比報告 | P4b-T3 | 削減量記録 | 15 分 |
| P4b-T5 | 実運用で 1 日テスト（ハルシネーション頻度、Read 発生回数） | P4b-T4 | 観察メモ | 1 日（実時間） |
| P4b-T6 | 微調整 + PR | P4b-T5 | PR 作成 | 30 分 |

#### Phase 10: スキル依存グラフ深化（Two-layer agent definitions）

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P10-T1 | Overstory の base.md / overlay.md 方式を調査・設計 | なし | 設計メモ | 30 分 |
| P10-T2 | `build-pipeline` を base / overlay に分離試験 | P10-T1 | 試験版 | 60 分 |
| P10-T3 | `create-feature` を base / overlay に分離試験 | P10-T2 | 試験版 | 60 分 |
| P10-T4 | `.claude/skills/README.md` 更新（two-layer 追記） | P10-T3 | README 更新 | 20 分 |
| P10-T5 | 他 Skill への適用判定（全 skill でやる必要なし） | P10-T4 | 適用リスト | 30 分 |
| P10-T6 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 11: 静的分析 hook

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P11-T1 | `.claude/rules/lint-patterns.json` 初期定義（40 パターン、W0-T3 ベース） | W0-T3 | 新規ファイル | 90 分 |
| P11-T2 | `.claude/rules/lint-patterns.schema.json` スキーマ定義 | P11-T1 | スキーマ | 30 分 |
| P11-T3 | `.claude/hooks/lint-check.sh` 実装（jq + rg 依存） | P11-T1 | スクリプト | 90 分 |
| P11-T4 | 手動テスト（違反コードに対して期待通り警告が出るか） | P11-T3 | テストログ | 45 分 |
| P11-T5 | `.claude/settings.json` に PostToolUse hook 追加 | P11-T4 | settings 更新 | 15 分 |
| P11-T6 | 誤検知調整期間（1 週間、規約準拠コードで警告が出ないか） | P11-T5 | 調整ログ | 1 週間（実時間） |
| P11-T7 | `.claude/rules/lint.md` 成文化（何が検査されるか、誤検知時の抑止方法） | P11-T6 | 新規ファイル | 30 分 |
| P11-T8 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 17: Registry-based handoff + Handoff Note 自動化

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P17-T1 | `docs/reports/` ディレクトリ構造設計（analysis/arch/bugs/...） | なし | ディレクトリ案 | 30 分 |
| P17-T2 | `docs/reports/_registry.md` テンプレート | P17-T1 | 新規ファイル | 20 分 |
| P17-T3 | `docs/reports/<category>/` 各ディレクトリ作成 + README | P17-T2 | 11 ディレクトリ | 30 分 |
| P17-T4 | `/handoff-note` スキル新設（手動生成） | P17-T2 | SKILL.md | 45 分 |
| P17-T5 | `/resume-handoff` スキル新設（前回状態ロード） | P17-T4 | SKILL.md | 45 分 |
| P17-T6 | `/registry-check` スキル新設（SessionStart で参照強制） | P17-T2 | SKILL.md | 30 分 |
| P17-T7 | Stop hook に handoff note 自動生成追加 | P17-T4 | settings 更新 | 30 分 |
| P17-T8 | SessionStart hook に `/registry-check` 起動追加 | P17-T6 | settings 更新 | 20 分 |
| P17-T9 | 1 週間運用試験 + effective context 時間計測 | 上記 | 計測ログ | 1 週間 |
| P17-T10 | PR | 上記 | PR 作成 | 15 分 |

**Wave 2 合計**: 26 タスク / 15-22 時間 / 4 PR

---

### Wave 3: 品質強化

#### Phase 5: スキル棚卸し運用化

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P5-T1 | `docs/SKILL_LIFECYCLE.md` 新設（四半期棚卸しルーチン） | なし | 新規ファイル | 45 分 |
| P5-T2 | 現状スキル 24 個の使用頻度調査スクリプト（git log + session transcript grep） | P5-T1 | `tools/skill-usage.py` | 60 分 |
| P5-T3 | `/writing-skills` メタスキル新設（obra/Superpowers 参考） | なし | SKILL.md | 60 分 |
| P5-T4 | 初回棚卸し実施（使用頻度低スキルの archive 判定） | P5-T2 | 棚卸しレポート | 60 分 |
| P5-T5 | 棚卸し結果の反映（archive or 削除） | P5-T4 | コミット | 30 分 |
| P5-T6 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 6: TDD-Guard（Hook 駆動 quality gate）

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P6-T1 | `nizos/tdd-guard` clone + ローカル動作確認 | なし | 動作ログ | 30 分 |
| P6-T2 | PreToolUse hook 登録（Write/Edit/MultiEdit/TodoWrite 傍受） | P6-T1 | settings 更新 | 30 分 |
| P6-T3 | 検証セッション設計（RED → GREEN → REFACTOR の判定ロジック） | P6-T2 | 設計メモ | 60 分 |
| P6-T4 | aitmpl 39+ Hooks から useful なものを選定（3-5 個） | なし | 選定リスト | 45 分 |
| P6-T5 | Lasso Prompt Injection Defender 導入検討 | なし | 評価メモ | 30 分 |
| P6-T6 | SisterGame での 1 週間試用（false positive 観察） | P6-T2 | 観察ログ | 1 週間 |
| P6-T7 | 誤検知調整 + 除外設定 | P6-T6 | 設定更新 | 60 分 |
| P6-T8 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 13: TDD 3 サブエージェント分離

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P13-T1 | `.claude/agents/tdd-test-writer.md` 定義（tools/memory/isolation frontmatter） | W0-T4 | 新規ファイル | 45 分 |
| P13-T2 | `.claude/agents/tdd-implementer.md` 定義 | P13-T1 | 新規ファイル | 45 分 |
| P13-T3 | `.claude/agents/tdd-refactorer.md` 定義 | P13-T2 | 新規ファイル | 45 分 |
| P13-T4 | `create-feature` SKILL.md 改修（3 段分割ワークフロー） | P13-T3 | SKILL.md 更新 | 90 分 |
| P13-T5 | `/tdd-guard-setup` スキル新設 | Phase 6 | SKILL.md | 30 分 |
| P13-T6 | Unity Edit Mode test 適合性確認 | P13-T4 | テスト実行 | 60 分 |
| P13-T7 | 1 機能を 3 分割版で実装試験 | P13-T6 | 試験結果 | 2-3 時間 |
| P13-T8 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 22: Unity 特化 hook と skill 輸入

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P22-T1 | `PostToolUse(Edit|Write).cs` で unity-mcp `read_console` 連動 hook | Phase 11 | hook スクリプト | 60 分 |
| P22-T2 | `pre-build` hook: `validate:project` | P22-T1 | hook スクリプト | 45 分 |
| P22-T3 | `post-build` hook: `test:playmode` | P22-T2 | hook スクリプト | 45 分 |
| P22-T4 | `pre-release` hook: `check:size`（APK/IPA 回帰検出） | P22-T3 | hook スクリプト | 45 分 |
| P22-T5 | Unity App UI Plugin 動作確認 + 導入判定 | なし | 評価メモ | 60 分 |
| P22-T6 | TheOne Studio skills の C# 9 規約と `Architect/` 整合性チェック | なし | 整合チェック | 60 分 |
| P22-T7 | 選定した外部 skill を `.claude/skills/` にインポート | P22-T5-6 | skill 配置 | 60 分 |
| P22-T8 | PR | 上記 | PR 作成 | 15 分 |

**Wave 3 合計**: 24 タスク / 18-26 時間 / 4 PR

---

### Wave 4: レビュー・経済性

#### Phase 12: Adversarial Review gate

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P12-T1 | `ng-adversarial-review` の設計調査 | なし | 設計メモ | 30 分 |
| P12-T2 | `.claude/agents/reviewer-optimizer.md`（Sonnet） 定義 | Phase 10 | 新規ファイル | 30 分 |
| P12-T3 | `.claude/agents/reviewer-skeptic.md`（Opus）定義 | P12-T2 | 新規ファイル | 30 分 |
| P12-T4 | `/adversarial-review` スキル新設（2 並列合議ロジック） | P12-T3 | SKILL.md | 90 分 |
| P12-T5 | スコア閾値実装（≤0 report なし / 1-4 Sonnet only / ≥5 dual） | P12-T4 | スクリプト | 60 分 |
| P12-T6 | Anthropic 公式 `plugins/code-review` 4 並列パターン移植 | P12-T5 | 追加 agent 2 本 | 90 分 |
| P12-T7 | SisterGame 既存 PR 3 本でリトロスペクト試験 | P12-T6 | 試験結果 | 2 時間 |
| P12-T8 | `/review-parallel` スキル新設（4 並列版） | P12-T6 | SKILL.md | 45 分 |
| P12-T9 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 15: コスト可視化 + Advisor 経済性

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P15-T1 | `tools/cost-report.py` 実装（JSONL 集計） | なし | 新規ファイル | 90 分 |
| P15-T2 | Stop hook で `/cost` 出力を `.claude/cost-log.jsonl` 追記 | P15-T1 | settings 更新 | 30 分 |
| P15-T3 | `/cost-report` スキル新設（月次レポート + 閾値アラート） | P15-T1 | SKILL.md | 45 分 |
| P15-T4 | `ccusage` 導入検討（実運用で置換できるか） | P15-T1 | 評価メモ | 45 分 |
| P15-T5 | `/model opusplan` デフォルト化 | なし | settings 更新 | 15 分 |
| P15-T6 | `DISABLE_NON_ESSENTIAL_MODEL_CALLS=1` / `MAX_THINKING_TOKENS=8000` 設定 | なし | settings 更新 | 15 分 |
| P15-T7 | Advisor Strategy: `/design-systems` を Opus 固定、`/create-feature` を Sonnet 固定 | P15-T5 | SKILL frontmatter 更新 | 30 分 |
| P15-T8 | 1 週間コスト計測 + 削減率測定 | P15-T2 | 測定レポート | 1 週間 |
| P15-T9 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 20: Sandbox + Docker 強化

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P20-T1 | Docker 環境要件調査（Windows + WSL2 対応） | なし | 調査メモ | 45 分 |
| P20-T2 | `--network none` コンテナ定義（`Dockerfile.sandbox`） | P20-T1 | 新規ファイル | 60 分 |
| P20-T3 | 60 秒 auto-commit スクリプト | P20-T2 | `tools/sandbox-autocommit.sh` | 45 分 |
| P20-T4 | `--dangerously-skip-permissions` 運用ルール明文化（`.claude/rules/sandbox.md`） | P20-T3 | 新規ファイル | 30 分 |
| P20-T5 | Issue #17544 回避: plan mode との組合せ禁止チェック | P20-T4 | 検出スクリプト | 30 分 |
| P20-T6 | SisterGame での動作試験（1 機能を sandbox で実装） | 上記 | 試験結果 | 2 時間 |
| P20-T7 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 25: anti-patterns.md 辞書化

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P25-T1 | `.claude/rules/anti-patterns.md` 新設（8 パターンの症状/対策/実例） | W0-T6 | 新規ファイル | 90 分 |
| P25-T2 | 各パターンの検出ヒント追加（keyword / 頻度 / context%） | P25-T1 | 更新 | 45 分 |
| P25-T3 | Stop hook で該当パターン検出時の警告スクリプト | P25-T2 | hook スクリプト | 45 分 |
| P25-T4 | Phase 11 lint-patterns との重複を整理 | Phase 11 | 重複排除 | 30 分 |
| P25-T5 | PR | 上記 | PR 作成 | 15 分 |

**Wave 4 合計**: 22 タスク / 14-20 時間 / 4 PR

---

### Wave 5: 高度パターン

#### Phase 7: pipeline-state + phase-boundary commit 連動（Effective Harnesses 準拠）

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P7-T1 | Effective Harnesses 二相構造の設計再読 | なし | 設計メモ | 45 分 |
| P7-T2 | `scripts/init.sh` 実装（セッション初期化） | P7-T1 | 新規ファイル | 60 分 |
| P7-T3 | `designs/claude-progress.txt` フォーマット定義 | P7-T2 | テンプレート | 30 分 |
| P7-T4 | 検証可能要件 JSON リスト仕様（`designs/pipeline-state.json` 拡張） | P7-T3 | 仕様書 | 60 分 |
| P7-T5 | PostToolUse hook で phase 完了時に自動 commit + tag 付与 | P7-T4 | hook スクリプト | 60 分 |
| P7-T6 | `/rewind` "code only" 動作確認 + checkpoint 戦略文書化 | P7-T5 | 確認メモ | 45 分 |
| P7-T7 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 14: Mutation Testing 統合

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P14-T1 | Stryker .NET 導入調査（Unity プロジェクト適合性） | なし | 調査メモ | 60 分 |
| P14-T2 | Unity プロジェクトへの組込み手順 | P14-T1 | 手順書 | 90 分 |
| P14-T3 | 最初の 1 機能で mutation テスト実行 + 閾値確認 | P14-T2 | テスト結果 | 2 時間 |
| P14-T4 | 80% mutation score 閾値運用ルール | P14-T3 | `.claude/rules/mutation.md` | 45 分 |
| P14-T5 | `create-feature` のオプション検証ステップとして統合 | P14-T4 | SKILL 更新 | 45 分 |
| P14-T6 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 16: Cache TTL 5 分対策

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P16-T1 | 現状の cache hit 率計測（ccusage 等） | Phase 15 | 計測値 | 45 分 |
| P16-T2 | keepalive ping 設計（4 分インターバル、軽量プロンプト） | P16-T1 | 設計メモ | 30 分 |
| P16-T3 | 1h TTL 明示指定の運用ルール（どの Skill で指定するか） | P16-T2 | ルール文書 | 30 分 |
| P16-T4 | static/dynamic ゾーン分離（session 中の CLAUDE.md 編集禁止時間帯） | P16-T3 | 運用メモ | 30 分 |
| P16-T5 | 長時間バッチ（`/consume-future-tasks` 等）向け keepalive 実装 | P16-T2 | スクリプト | 60 分 |
| P16-T6 | 効果測定（1 週間、cache hit 率比較） | P16-T5 | 測定レポート | 1 週間 |
| P16-T7 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 18: Ralph ループ

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P18-T1 | `/loop` 公式機能の動作確認 | なし | 確認ログ | 30 分 |
| P18-T2 | `frankbria/ralph-claude-code` 参考設計（Dual-condition exit gate） | P18-T1 | 設計メモ | 60 分 |
| P18-T3 | `/consume-future-tasks` に Ralph パターン統合（オプション） | P18-T2 | SKILL 更新 | 90 分 |
| P18-T4 | exit 条件閾値（MAX_TEST_LOOPS=3, DONE_SIGNALS=2, TEST_%=30）実装 | P18-T3 | スクリプト | 60 分 |
| P18-T5 | 夜間バッチ運用ルール（sandbox + auto-commit 前提） | P18-T4, Phase 20 | 運用文書 | 30 分 |
| P18-T6 | 試験バッチ実行（3-5 タスク、一晩） | P18-T5 | 試験結果 | 1 日 |
| P18-T7 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 19: Harness 二相分離

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P19-T1 | init-agent / coding-agent 責務分離設計 | Phase 7 | 設計書 | 60 分 |
| P19-T2 | `.claude/agents/init-agent.md` 定義 | P19-T1 | 新規ファイル | 45 分 |
| P19-T3 | `.claude/agents/coding-agent.md` 定義（tools/memory/isolation） | P19-T2 | 新規ファイル | 45 分 |
| P19-T4 | `build-pipeline` を init-agent 専用化 | P19-T3 | SKILL 更新 | 60 分 |
| P19-T5 | `create-feature` を coding-agent 経由化 | P19-T4 | SKILL 更新 | 60 分 |
| P19-T6 | 検証可能要件 JSON リスト運用（Phase 7 拡張との統合） | Phase 7 | 統合 | 60 分 |
| P19-T7 | 1 セクション分を二相化フローで実装試験 | 上記 | 試験結果 | 3 時間 |
| P19-T8 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 23: SDD 統合

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P23-T1 | `Pimzino/claude-code-spec-workflow` / `gotalab/cc-sdd` 調査 | なし | 調査メモ | 60 分 |
| P23-T2 | SisterGame 既存の `design-game → design-systems → create-feature` と SDD の対応表 | P23-T1 | マッピング表 | 45 分 |
| P23-T3 | Requirements → Design → Tasks → Impl の subagent 並列化試験 | P23-T2 | 試験結果 | 2 時間 |
| P23-T4 | `create-feature` への人間計画注入点明示化 | P23-T3 | SKILL 更新 | 60 分 |
| P23-T5 | FeatureBench 11% 対策として人間レビュー gate 設置 | P23-T4 | 運用ルール | 30 分 |
| P23-T6 | PR | 上記 | PR 作成 | 15 分 |

#### Phase 24: Compound 恒常化

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P24-T1 | Phase 8 手動版の運用データ蓄積確認（最低 5 エントリ） | Phase 8 手動 | 確認 | 15 分 |
| P24-T2 | Stop hook で自動 compound-learn 抽出スクリプト | P24-T1 | hook スクリプト | 90 分 |
| P24-T3 | `/compound-learn` スキル新設 | P24-T2 | SKILL.md | 60 分 |
| P24-T4 | 月次 review 会の運用ルール（CLAUDE.md / Architect/ / FUTURE_TASKS.md への昇格判定） | P24-T3 | 運用文書 | 45 分 |
| P24-T5 | consolidate-memory に削除・統合ロジック追加（experience following property 対策） | P24-T2 | スキル更新 | 60 分 |
| P24-T6 | PR | 上記 | PR 作成 | 15 分 |

**Wave 5 合計**: 34 タスク / 28-42 時間 / 7 PR

---

### Wave 監視（継続観察）

#### Phase 8 自動化（Wave 5 の Phase 24 で実装済みになる見込み）

#### Phase 9: 外部スキル組み込み（⏸）

| ID | タスク | 前提 | 成果物 | 見積 |
|----|--------|------|--------|------|
| P9-T1 | Anthropic 公式リリースノート監視（月次） | なし | 継続 | 月 30 分 |
| P9-T2 | 候補スキル棚卸し（wshobson/rohitg00 等）の差分確認 | P9-T1 | 差分メモ | 月 30 分 |
| P9-T3 | 採用可否判定基準の文書化（ライフサイクル・依存・Unity 適合性） | なし | `.claude/rules/external-skill-eval.md` | 60 分 |
| P9-T4 | 年次で評価レビュー会 | 上記 | 評価レポート | 年 2 時間 |

---

### 全体クリティカルパス図

```
Wave 0 (3-4h)
  └─> Wave 1 (6-9h)
        ├─> Wave 2 Phase 11 (lint-patterns 具体化)
        ├─> Wave 2 Phase 4 後半 (CLAUDE.md 剪定)
        └─> Wave 2 Phase 10, 17 (独立)
              └─> Wave 3 Phase 5, 6, 13, 22
                    └─> Wave 4 Phase 12, 15, 20, 25
                          └─> Wave 5 Phase 7, 14, 16, 18, 19, 23, 24
                                └─> Wave 監視 (継続)
```

### PR 作成見込み

Wave 0: plan 更新のみ（PR なし、plan file はプロジェクト外）
Wave 1: 3 PR（P4 前半、P8 手動、P21）
Wave 2: 4 PR（P4 後半、P10、P11、P17）
Wave 3: 4 PR（P5、P6、P13、P22）
Wave 4: 4 PR（P12、P15、P20、P25）
Wave 5: 7 PR（P7、P14、P16、P18、P19、P23、P24）
**合計: 22 PR**（Phase 数に一致、1 Phase 1 PR 原則）

### 運用ルール

1. **1 Wave = 1 スプリント**で区切る。Wave 完了までユーザー確認を挟み次 Wave へ
2. **各 Phase 完了後 1 週間は効果観察**（観察期間中は次 Phase の準備は可）
3. **hook は必ず warning 段階 → error 段階の順で導入**（Phase 11, 6 は特に重要）
4. **Anthropic 吸収をウォッチ**（特に Phase 8/9/18、`/loop` / `consolidate-memory` / Ralph は公式化が進行中）
5. **失敗時は Phase 単位で revert**（`git revert <PR hash>` で即戻す）
6. **plan file は各 Wave 完了時に更新**（学び / 調整 / 次 Wave の優先順位）

---

## Wave 0 実施記録（2026-04-24）

### 実施内容
- `.claude/rules/` 配下 6 ファイル（計 887 行）をエージェント 1 名で精読

### 主要発見

1. **`architecture.md` に `paths:` frontmatter が既に設定済み**
   ```yaml
   paths:
     - "Assets/MyAsset/**/*.cs"
     - "Assets/Tests/**/*.cs"
   ```
   - SisterGame 独自の path-scope 仕組み
   - Claude Code 公式の path-scoped CLAUDE.md（ディレクトリ配置）とは別仕様
   - 他 rules ファイルには未設定（asset-workflow.md 等は `paths:` なし）

2. **Co-Authored-By のバージョン古い**: Claude Opus 4.6 → 4.7 更新必要（CLAUDE.md・git-workflow.md の 2 箇所）

3. **lint パターン 40 個抽出済み**（regex + severity + source 付き、Phase 11 で利用）

4. **rules 間の重複**（CLAUDE.md 剪定時に整理対象）:
   - GetComponent キャッシュ: architecture と unity-conventions
   - `.meta` セット管理: CLAUDE.md と git-workflow
   - Addressable: asset-workflow と CLAUDE.md
   - コミットメッセージ規約: CLAUDE.md と git-workflow

5. **SerializeField の命名は `camelCase`（アンダースコアなし）が正**: unity-conventions L27（private フィールドの `_camelCase` と区別）

### Wave 1 への反映

- Phase 4 前半: **path-scoped CLAUDE.md を併設**（`paths:` frontmatter と公式機能の二重保険）
- Phase 4 後半: 重複除去を剪定で実施
- Phase 11: 40 lint パターンを初期登録（W0-T3 根拠）
- Phase 21: CVE リスト + git-workflow.md の `--no-verify`/`--force` 禁止事項を source of truth に

### 精読成果の永続版

詳細は以下のプロジェクト内ファイルに永続化済み（別セッションでそのまま参照可）:
- `.claude/rules/wave0-audit.md` — セクション A-F の完全版（path-scoped 配置判定、40 lint パターン対応表、TDD 3 分離ルール、PR レビュー 4 観点、anti-patterns 辞書元ネタ、rules 間重複）
- `.claude/rules/lint-patterns.json` — Phase 11 の source of truth（40 パターン初期版、regex + severity + source 付き）
- `.claude/rules/security-patterns.json` — Phase 21 の source of truth（prompt injection 12 + CC 3 + CVE 5）
- `.claude/rules/security-known.md` — Phase 21 の人間向け運用ドキュメント

---

## Session 0 読み物リスト（各 Phase 実装時の参照先）

別セッションで各 Phase を実装する前に、以下の「必須」資料を読む。**外部 URL は Anthropic 吸収や URL 変更のリスクがあるので、可能な限りプロジェクト内の永続ファイルを優先**。

### Phase 4（CLAUDE.md 剪定 + path-scoped 化）
- **必須**: `.claude/rules/wave0-audit.md` § A（path-scoped 配置判定）, § F（重複・矛盾）
- **必須**: `.claude/rules/README.md`（運用ルール、既設）
- **必須**: `Assets/MyAsset/CLAUDE.md`, `Assets/Tests/CLAUDE.md`（既設、拡張時の参考）
- 参考: [HumanLayer: Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md) — 2.5k トークン基準の根拠
- 参考: [anvodev: 47k→9k 削減事例](https://dev.to/anvodev/how-i-organized-my-claudemd-in-a-monorepo-with-too-many-contexts-37k7)
- 参考: [arXiv 2511.09268](https://arxiv.org/html/2511.09268v1) — 328 プロジェクト分析で「Architecture 指定が最重要」

### Phase 5（スキル棚卸し）
- **必須**: `.claude/skills/README.md`（現状の依存グラフ、現在 24 スキル）
- **必須**: `CLAUDE.md`「スキル分類」節（主要 vs 補助）
- 参考: [fsck.com: Superpowers](https://blog.fsck.com/2025/10/09/superpowers/) — `/writing-skills` メタスキルのパターン
- 参考: [Shrivu Shankar blog](https://blog.sshh.io) — 「20+ slash command はアンチパターン」の論拠

### Phase 6（TDD-Guard Hook）
- **必須**: `.claude/rules/test-driven.md`（TDD ワークフロー、結合テスト 3 観点）
- **必須**: `.claude/rules/wave0-audit.md` § C（TDD 3 サブエージェント分離詳細）
- **必須**: [nizos/tdd-guard](https://github.com/nizos/tdd-guard) の README — PreToolUse hook 設定例、ブロック対象（Write/Edit/MultiEdit/TodoWrite）
- 参考: [aitmpl 39+ Hooks](https://www.aitmpl.com/hooks/) — レシピ集
- 参考: Lasso Prompt Injection Defender — tool output 別モデル判定パターン

### Phase 7（Effective Harnesses 準拠）
- **必須**: [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — init-agent + coding-agent の責務定義
- **必須**: [Anthropic: Harness Design for Long-Running Apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- **必須**: 現状の `designs/pipeline-state.json`（拡張元）
- 参考: [arXiv 2604.14228: Dive into Claude Code](https://arxiv.org/html/2604.14228) — 5 層 compaction パイプライン + 7 高レベルコンポーネント

### Phase 8（Compound 自動トリガー）
- **必須**: `docs/compound/README.md`（既設、手動運用ルール）
- **必須**: `docs/compound/_template.md`（フォーマット）
- **必須**: `docs/compound/2026-04-24-pr44-pipeline-refactor.md`（初回エントリの書き方参考）
- **必須**: [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) — 4 ステップループの実装
- **必須**: [arXiv 2509.25250](https://arxiv.org/pdf/2509.25250) — experience following property（consolidate に削除ロジック必須の論拠）

### Phase 9（外部スキル組み込み）
- **必須**: Anthropic リリースノート（月次、外部スキルの公式吸収動向）
- 参考: [wshobson/agents](https://github.com/wshobson/agents)（184 agents + 150 skills）
- 参考: [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)
- 参考: [anthropics/skills](https://github.com/anthropics/skills)（37.5k★、公式）

### Phase 10（スキル依存グラフ深化 / Two-layer）
- **必須**: `.claude/skills/README.md`（現状 primitive/composition 分離、mermaid グラフ）
- **必須**: Overstory の Two-layer agent definitions（base.md = HOW / overlay.md = WHAT）— ※出典は claude_knowledge.md §3.5、`humming-dancing-conway-agent-aa34619d19ec44a2a.md` 参照
- 参考: [Claude Code Issue #27113](https://github.com/anthropics/claude-code/issues/27113)（declarative skill dependency 公式検討）

### Phase 11（静的分析 hook）
- **必須**: `.claude/rules/lint-patterns.json`（40 パターン、source of truth、既設）
- **必須**: `.claude/rules/wave0-audit.md` § B（regex + source 対応表）
- **必須**: `.claude/rules/unity-conventions.md`, `architecture.md`, `asset-workflow.md`（各パターンの根拠）
- 参考: `tools/pr-validate.py` — hook スクリプト設計の参考（jq + regex + severity 分岐）
- 参考: ClaudeWatch 風 self-healer（出典: claude_knowledge.md §3.7）

### Phase 12（Adversarial Review gate）
- **必須**: [anthropics/claude-code `plugins/code-review`](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md) — 4 並列パターン
- **必須**: `.claude/rules/wave0-audit.md` § D（PR レビュー 4 観点: Code Reuse / Quality / Efficiency / TDD）
- **必須**: `.claude/rules/git-workflow.md`（既存 PR レビュー条項）
- 参考: ng-adversarial-review プラグイン（Sonnet + Opus 並列、スコア閾値実装パターン）

### Phase 13（TDD 3 サブエージェント分離）
- **必須**: `.claude/rules/wave0-audit.md` § C（test-writer / implementer / refactorer の役割分担詳細）
- **必須**: `.claude/rules/test-driven.md`（結合テスト 3 観点必須）
- **必須**: `Assets/Tests/CLAUDE.md`（既設、path-scoped ルール）
- 参考: [alexop.dev: Custom TDD Workflow](https://alexop.dev/posts/custom-tdd-workflow-claude-code-vue/) — Vue 事例だが 3 分離の原理は同じ

### Phase 14（Mutation Testing）
- 参考: [Stryker .NET](https://stryker-mutator.io/docs/stryker-net/introduction/) — .NET 用 mutation testing tool
- 参考: Meta "Just-in-Time Catching Test Generation"（回帰検出 4 倍）

### Phase 15（コスト可視化 + Advisor 経済性）
- **必須**: [ccusage GitHub](https://github.com/...)（ログ集計 OSS、導入検討）
- **必須**: `/cost` コマンド出力例（Claude Code 標準）
- **必須**: Advisor Strategy — Opus = 非実行アドバイザー（出典: claude_knowledge.md §3.11、11% 削減実測）
- 参考: [Issue #19436](https://github.com/anthropics/claude-code/issues/19436) — multi-tier caching 提案

### Phase 16（Cache TTL 5 分対策）
- **必須**: claude_knowledge.md §3.11（5 分 TTL 変更の背景、keepalive 設計）
- 参考: Batch API + Prompt Caching 重ね掛けパターン

### Phase 17（Registry-based handoff）
- **必須**: Ilyas Ibrahim の 26 エージェント失敗事例 → `.claude/reports/_registry.md` 中心のカテゴリ別フォルダ（出典: claude_knowledge.md §3.8）
- 参考: AnandChowdhary リレー設計プロンプト例
- 参考: `designs/pipeline-state.json`（同じく外在化方針）

### Phase 18（Ralph ループ）
- **必須**: [Geoffrey Huntley: while true ループ設計](https://www.ghuntley.com/...)
- **必須**: [frankbria/ralph-claude-code](https://github.com/frankbria/ralph-claude-code) — Dual-condition exit gate 実装
- **必須**: Claude Code `/loop` 公式機能のドキュメント確認（Anthropic 吸収済みの可能性）

### Phase 19（Harness 二相分離）
- Phase 7 の読み物リスト + Overstory の Two-layer（Phase 10）参照
- `.claude/agents/<name>.md` frontmatter 仕様（tools / memory / isolation）

### Phase 20（Sandbox + Docker 強化）
- **必須**: `.claude/rules/security-known.md`（既設、Issue #17544 silent override bug）
- **必須**: `.claude/rules/security-patterns.json` の `known_cves`
- 参考: Docker --network none コンテナ実装例
- 参考: [Issue #17544](https://github.com/anthropics/claude-code/issues/17544)

### Phase 21（Comment and Control 防御）
- **必須**: `.claude/rules/security-known.md`（既設、全内容）
- **必須**: `.claude/rules/security-patterns.json`（既設、12 + 3 + 5 パターン）
- **必須**: `tools/pr-validate.py`（既設、実装参考）
- 参考: [SecurityWeek: Comment and Control 攻撃](https://www.securityweek.com/claude-code-gemini-cli-github-copilot-agents-vulnerable-to-prompt-injection-via-comments/)

### Phase 22（Unity 特化 hook と skill 輸入）
- **必須**: `.claude/rules/lint-patterns.json`（Unity C# 特化パターン、既設）
- **必須**: unity-mcp の `read_console` / `manage_scene` API ドキュメント
- 参考: [Unity App UI Plugin](https://docs.unity3d.com/Packages/com.unity.dt.app-ui@2.2/manual/claude-plugin.html)
- 参考: [The1Studio/theone-training-skills](https://github.com/The1Studio/theone-training-skills)

### Phase 23（SDD 統合）
- **必須**: [Pimzino/claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow)
- **必須**: [gotalab/cc-sdd](https://github.com/gotalab/cc-sdd)（Kiro 由来 harness）
- 参考: [arXiv 2602.10975: FeatureBench](https://arxiv.org/abs/2602.10975) — feature-level 11% の論拠（人間計画注入必須）

### Phase 24（Compound 恒常化）
- Phase 8 読み物リスト + 運用実績（docs/compound/ 配下 5 エントリ以上）

### Phase 25（anti-patterns 辞書）
- **必須**: `.claude/rules/wave0-audit.md` § E（10 パターンの元ネタ）
- **必須**: claude_baseKnowledge.md §3.12（Kitchen sink / Correction loop / Agent dumb zone 等の失敗パターン名）

---

## 中間レポートファイル

Wave 0 で生成した中間成果物（エージェント精読結果の詳細版、plan file と同ディレクトリ配置）:
- `~/.claude/plans/humming-dancing-conway-agent-a383b60c19f3717e0.md` — claude_baseKnowledge.md の精読レポート（新規観点 25 項目、SisterGame 適用案）
- `~/.claude/plans/humming-dancing-conway-agent-aa34619d19ec44a2a.md` — claude_knowledge.md の精読レポート（新規観点 12 項目、Compound/TDD/Overstory 等の具体 pattern）

**用途**: 本 plan file で要約された知見の詳細を確認したい時、または各 Phase の元データ（Overstory の Two-layer 詳細、Ralph ループの exit gate 閾値等）が必要な時。

---

## 動線補強の更新履歴

| 日付 | 内容 |
|------|------|
| 2026-04-24 | Wave 0 の agentId 参照を削除、`.claude/rules/wave0-audit.md` / `lint-patterns.json` に永続化。Session 0 読み物リストを各 Phase 別に追加 |