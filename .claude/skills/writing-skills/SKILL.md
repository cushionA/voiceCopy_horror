---
name: writing-skills
description: Meta-skill for creating, refining, and reviewing Claude Code skills. Use when adding a new skill, restructuring an existing one, or running the quarterly skill lifecycle review (per docs/SKILL_LIFECYCLE.md).
user-invocable: true
argument-hint: <new-skill-name | review-existing | quarterly-audit>
---

# Writing Skills: $ARGUMENTS

Claude Code skill の作成・改修・棚卸しを支援するメタスキル。
**Wave 3 Phase 5 P5-T3 で新設**。obra/Superpowers の `/writing-skills` パターンを SisterGame に最適化。

## 何をする skill か

| サブコマンド (引数) | 動作 |
|--------------------|------|
| 新規 skill 名 | `.claude/skills/<name>/SKILL.md` を生成。frontmatter / 構造ガイド / 既存 skill との重複検出 |
| `review-existing <name>` | 既存 skill の品質チェック（description 改善 / 構造冗長性 / Two-layer 化検討） |
| `quarterly-audit` | `tools/skill-usage.py` を起動し棚卸しレポートを生成、判定結果から archive / 削除候補を提案 |

## サブコマンド詳細

### 1. 新規 skill 作成 (`/writing-skills <new-skill-name>`)

#### ステップ 1: 重複チェック

```bash
ls .claude/skills/
```

既存 skill 一覧と引数の skill 名を照合する。類似名 (`bind-assets` vs `bind-asset`、`run-tests` vs `test-runner`) があればユーザーに統合 / 拡張を提案。

`.claude/skills/README.md` の依存グラフで「他 skill の責務との重複」も確認。

#### ステップ 2: SKILL.md 雛形生成

```yaml
---
name: <new-skill-name>
description: <一文で何をする skill か。トリガー条件も含める>
user-invocable: true
argument-hint: <引数のヒント>
---

# <Title>: $ARGUMENTS

<目的と適用条件>

## 動作

### ステップ 1: <名前>
<内容>

### ステップ 2: <名前>
<内容>

## ルール

- <禁止事項>
- <注意点>

## 関連

- <他の skill との関係>
- <参照する rules ファイル>
```

#### ステップ 3: skill 分類への登録

`.claude/skills/README.md` の該当カテゴリ表に新 skill 行を追加:

- Composition (オーケストレータ) — 他 skill を呼ぶ
- Design / Implementation / Verification / Assets / Stage-Content / Auxiliary

依存があれば mermaid グラフにも追加。

#### ステップ 4: Two-layer 化判定

`.claude/skills/_two-layer-design.md` § 1.2 の判定基準に照らし、**HOW (汎用) と WHAT (SisterGame 固有) を分離する価値**があるか検討:

- 規模が 100 行超見込み + 再利用可能性あり → base.md / overlay 分離を推奨
- 短い primitive skill → 単一 SKILL.md で十分

### 2. 既存 skill レビュー (`/writing-skills review-existing <name>`)

#### チェック項目

- [ ] **description 品質**: 1 文で「何をするか + いつ呼ぶか」が明示されている
- [ ] **トリガー語**: description の冒頭に「Use when ...」または「〜時に呼ぶ」表現がある
- [ ] **責務範囲**: 1 skill 1 責務原則。複数役割が混在していないか
- [ ] **冗長性**: 200 行超なら reference 切り出しまたは Two-layer 化検討
- [ ] **依存**: 他 skill を呼んでいるなら README の Composition 表に登録されているか
- [ ] **ルール参照**: `.claude/rules/` のどれを参照すべきか冒頭で明示
- [ ] **誤検知 / 副作用**: destructive 操作 (rm / push / delete) のガード明記

#### 出力

レビュー結果を `docs/reports/reviews/YYYY-MM-DD_skill-<name>.md` に保存（任意）。
チェックリスト各項目に ✅ / ⚠️ / ❌ を付け、改善提案を併記。

### 3. 四半期棚卸し (`/writing-skills quarterly-audit`)

#### ステップ 1: 使用頻度集計

```bash
python tools/skill-usage.py --since 90d --output docs/reports/analysis/$(date +%Y-%m-%d)_skill-usage.md
```

#### ステップ 2: 判定結果の提示

`docs/SKILL_LIFECYCLE.md` § Step 2 の判定基準に従い、各 skill を `active` / `stale` / `candidate-archive` / `deprecated` に分類。

#### ステップ 3: ユーザー合議

棚卸しレポートを表示し、以下を質問:

- stale を維持するか archive するか
- candidate-archive は archive で問題ないか
- deprecated を完全削除してよいか

#### ステップ 4: 反映

ユーザー判断に従って archive (`git mv .claude/skills/<name> .claude/skills/_archive/<name>`) または削除 (`git rm -rf`)。
`.claude/skills/README.md` を更新。

#### ステップ 5: PR

```bash
git checkout -b refactor/skill-lifecycle-YYYY-Q<N>
git add ...
git commit -m "refactor(skills): YYYY 第 N 四半期棚卸し"
gh pr create
```

`docs/SKILL_LIFECYCLE.md` § 棚卸し履歴 表に行を追加。

## ルール

- **新規 skill 作成時は必ず重複チェック**を行う（同じ責務を複数 skill が持つのを避ける）
- **destructive 操作 (削除 / archive) はユーザー確認必須**
- **Two-layer 化は試験段階**: 全 skill に適用する必要はない。`_two-layer-design.md` の判定表を参照
- メタスキル自体（本 skill）の改修は半年に 1 度の頻度に留める（過剰最適化を避ける）

## 関連

- `docs/SKILL_LIFECYCLE.md` — 棚卸しルーチン定義
- `tools/skill-usage.py` — 使用頻度集計スクリプト
- `.claude/skills/README.md` — 現状の skill 一覧
- `.claude/skills/_two-layer-design.md` — base/overlay 分離の判定基準
- 参考: [obra/Superpowers の writing-skills](https://blog.fsck.com/2025/10/09/superpowers/)
- 参考: [Shrivu Shankar blog](https://blog.sshh.io) — skill 過多のアンチパターン
