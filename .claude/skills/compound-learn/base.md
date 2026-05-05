# compound-learn — base.md (HOW)

Compound Engineering における「学びの抽出 → 確認 → 昇格 → archive」の汎用ワークフロー。
プロジェクト非依存の手順を記述する。SisterGame 固有のパス・規約は overlay (SKILL.md) を参照。

## ワークフロー全体

```
[1. 抽出]  Stop hook or 手動 → tools/compound-extract.py → drafts/
   ↓
[2. 確認]  人間が draft を読み、再利用可能な学びを Pattern セクションに昇格
   ↓
[3. 昇格]  draft → 正式エントリに書き直し、別ファイルとして save、draft 削除
   ↓
[4. 評価]  既存エントリと比較、3 件以上同パターン → rules/Architect 化候補
   ↓
[5. archive]  6 ヶ月超 / archived: true → _archived/ へ移動
```

## ステップ 1: 抽出 (auto / manual)

### auto (Stop hook)
- 閾値超え session で `tools/compound-extract.py` が起動
- detect する 3 パターン:
  - failure-correction (tool error → recovery)
  - user-correction (user メッセージの修正指示)
  - success-pattern (success signal: 完了 / OK / 完璧 等)
- 出力: `_drafts/{date}_{slug}.md`

### manual
- 人間が直接 `_drafts/` または最終置き場に書く
- 大きな学びを得た直後 (PR マージ後 / blocker 解消時) が推奨タイミング

## ステップ 2: draft 確認

draft の構造:
```markdown
---
topic: (auto-extracted) ...
date: YYYY-MM-DD
outcome: (要レビュー)
tags: [auto-extract]
---

## Context
...

## Pattern
(レビューで埋める)

## Examples (raw extract)
- user_corrections / failure_corrections / success_signals の生抽出

## Anti-patterns
(レビューで埋める)
```

確認チェックリスト:
- [ ] raw extract に同じ学びを示す素材が複数あるか
- [ ] その学びは将来別 session で再利用できるか
- [ ] 既存エントリで同 pattern を扱っていないか

## ステップ 3: 昇格

draft を **書き直して** 正式エントリにする (コピーではなく rewrite):

1. `topic` を 1 行で本質を表現
2. `outcome` をパターン名 (動詞化推奨: 「〇〇は△△で書く」)
3. `tags` から `auto-extract` を削除し、再利用キーワードを追加
4. `Pattern` セクションを箇条書きで書く (3-5 項目程度)
5. `Examples` を最小限のコード片 / コマンド片に圧縮
6. `Anti-patterns` を必ず書く (失敗時の挙動)
7. `Related` に関連 compound エントリ / plan file / rules ファイルへのリンク

書き終えたら:
- 正式置き場に `{date}_{slug}.md` として save
- draft を削除 (履歴は git log で追える)

## ステップ 4: 昇格判定 (rules / Architect / future-task)

3 件以上同 pattern が出たら、より上位の文書への昇格を検討:

| 経路 | 判定基準 |
|------|----------|
| rules 化 | コード規約・ワークフローに関する。3 ファイル以上の修正で再利用される |
| Architect 化 | データ構造・状態機械・アーキテクチャに関する |
| future-task 化 | 実装タスクの示唆。Wave 計画外で別途拾う |

判定後の compound エントリ自体は **削除しない**:
- 出典として残す
- frontmatter に `archived: true` を追加 (次回 archive 対象)
- Pattern セクションの末尾に「→ 昇格先: `<path>`」を追記

## ステップ 5: archive

`tools/consolidate-memory-extension.py` で定期的に整理:

- `--apply` で `archived: true` のエントリを `_archived/{YYYY}/` に移動
- 6 ヶ月超で promotion 無し → archive 候補として警告 (移動はしない、人間判断)
- 重複 outcome を検出 (同一表現は統合 or 古い方を archive)

## エラー処理

- draft が壊れている (frontmatter parse 失敗) → skip + warning
- 既存エントリと完全一致 → 重複として扱い draft を削除
- archive 移動失敗 (権限 / disk) → エラー出力、移動せず継続

## 設計原則

- **副作用最小**: archive 移動と新ファイル作成のみ。既存エントリは触らない (frontmatter 追記を除く)
- **人間レビュー必須**: auto-extract は draft 止まり。`docs/compound/` 直書きはしない
- **冪等性**: 同 draft を 2 回処理しても 2 件にならない (重複検出)
- **追跡可能性**: 昇格時に出典を記録 (Pattern → rules への移動を blame 可能に)

## 関連

- `_two-layer-design.md` (本 base/overlay 設計の根拠)
- 上位 SKILL.md (project-specific overlay)
