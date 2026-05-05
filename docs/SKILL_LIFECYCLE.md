# SKILL_LIFECYCLE — Claude Code skill 棚卸しルーチン

**目的**: SisterGame プロジェクトで運用している `.claude/skills/` 配下の skill を**四半期ごとに棚卸し**し、未使用 / 重複 / 陳腐化したものを archive または削除する運用ルールを定める。

**根拠**: Shrivu Shankar 氏の「20+ slash command はアンチパターン」指摘 ([blog](https://blog.sshh.io))。現状 SisterGame は 24+ skill を運用しているため、定期的な剪定が必須。

## 運用周期

- **四半期 (3 ヶ月) ごと**に棚卸し実施
- 次回予定: **2026-07-25** (本ファイル制定 2026-04-25 から 3 ヶ月後)

## 棚卸し手順

### Step 1: 使用頻度データ収集

```bash
python tools/skill-usage.py --since 90d
```

このスクリプトは以下を集計する:

- **直近 90 日**の git log から、skill 名 (例: `/build-pipeline`) を含むコミットメッセージ件数を抽出
- `.claude/skills/<name>/SKILL.md` の最終更新日 (mtime / git log) を記録
- session transcript（あれば）から skill invocation 件数を抽出 (将来拡張)

出力フォーマット (`docs/reports/analysis/YYYY-MM-DD_skill-usage.md`):

```markdown
| skill | コミット出現 | 最終更新 | 判定 |
|-------|-------------|---------|------|
| build-pipeline | 12 | 2026-04-25 | active |
| design-stage | 0 | 2026-02-01 | candidate-archive |
```

### Step 2: 判定基準

| 区分 | 判定基準 | アクション |
|------|---------|-----------|
| **active** | 直近 90 日でコミット出現 1 件以上 | 維持 |
| **stale** | コミット出現 0 件 + 最終更新 90-180 日 | 棚卸し対象、ユーザー判断 |
| **candidate-archive** | コミット出現 0 件 + 最終更新 180 日以上 | archive 推奨 |
| **deprecated** | description が「廃止」「非推奨」を含む | 削除推奨 |

### Step 3: ユーザー合議

棚卸しレポート (`docs/reports/analysis/YYYY-MM-DD_skill-usage.md`) を見ながら、以下を判断:

1. **stale / candidate-archive を archive するか、削除するか**
2. **active だが用途が重複している skill の統合**（例: 過去の `index-assets` → `generate-assets` への統合）
3. **新たに分割すべき肥大化 skill** （例: 200 行超で reference 切り出し検討）

判断基準:
- ユーザーが過去 90 日に**意識的に使った**記憶があるなら active 維持
- 完全に忘れていた skill は archive 候補
- 用途が他 skill と被るものは統合

### Step 4: archive / 削除実施

#### archive

```bash
# .claude/skills/<name>/ → .claude/skills/_archive/<name>/ に移動
git mv .claude/skills/<name> .claude/skills/_archive/<name>
```

`_archive/` 配下は将来再利用可能だが、`/<name>` で呼び出されない。

#### 削除

```bash
git rm -rf .claude/skills/<name>
```

完全に消す場合（再利用見込みなし）。

#### `.claude/skills/README.md` を更新

- 「Composition / Design / Implementation / ...」セクションから該当 skill を削除
- mermaid 依存グラフから該当ノード削除
- archive した場合は「## Archived」セクションに記録

### Step 5: PR 化

```bash
git checkout -b refactor/skill-lifecycle-YYYY-Q<N>
git add .claude/skills/ docs/reports/analysis/
git commit -m "refactor(skills): YYYY 第 N 四半期棚卸し（N skill archive、M skill 統合）"
gh pr create --title "skill 棚卸し YYYY 第 N 四半期" --body "..."
```

## 関連メタスキル

### `/writing-skills`

新規 skill 作成・既存 skill 改修を支援するメタスキル。
詳細: `.claude/skills/writing-skills/SKILL.md`

### Two-layer skill (Wave 2 Phase 10 で導入)

大型 skill は base.md (HOW) / SKILL.md (overlay) に分離する選択肢あり。
詳細: `.claude/skills/_two-layer-design.md`

## 棚卸し履歴

| 日付 | 担当 | active | stale → archive | 削除 | 統合 |
|------|------|--------|-----------------|------|------|
| 2026-04-25 | 制定 | 24 | 0 | 0 | 0 |

四半期ごとに本表に追記する。

## 関連

- `.claude/skills/README.md` — 現状の skill 一覧と依存グラフ
- `tools/skill-usage.py` — 使用頻度集計スクリプト (Phase 5 P5-T2)
- `.claude/skills/writing-skills/SKILL.md` — メタスキル (Phase 5 P5-T3)
- WAVE_PLAN.md L740-747 (Phase 5 タスク定義)
- 参考: [fsck.com Superpowers](https://blog.fsck.com/2025/10/09/superpowers/) — `/writing-skills` パターン
- 参考: [Shrivu Shankar blog](https://blog.sshh.io) — 「20+ slash command はアンチパターン」
