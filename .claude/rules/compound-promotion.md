# Compound エントリ昇格判定基準 (Wave 5 Phase 24)

`docs/compound/` に蓄積したエントリのうち、再現性の高いパターンを
`.claude/rules/` / `Architect/` / `docs/FUTURE_TASKS.md` に昇格する判定基準。

## 昇格の 3 経路

### 経路 1: rules 化 (`.claude/rules/<新ファイル>.md`)
**判定基準**:
- 同じ抽象パターンが **3 件以上** の compound エントリで出現
- パターンが **コード規約・命名・ワークフロー** に関する (実装規約として書ける)
- 既存 rules ファイル (architecture / unity-conventions / test-driven 等) のいずれにも該当しない

**例**:
- compound エントリ「PostToolUse hook で Python heredoc が bash 引用と衝突」が 3 件出現
  → `.claude/rules/shell-python-heredoc.md` に昇格 (引用エスケープ規約)

### 経路 2: Architect 化 (`Architect/<番号>_<トピック>.md`)
**判定基準**:
- パターンが **アーキテクチャ・データ構造・状態機械** に関する
- 既存 Architect 文書の章で扱える内容ではない (新章相当)
- `docs/compound/` で言及される実装ファイル数が **3 ファイル以上**

**例**:
- compound エントリ「ハッシュベース O(1) アクセスの GameManager 経由が必須」が 3 件出現
  → `Architect/01_Container.md` に追記 (新章ではなく既存章の拡充で済むケース)

### 経路 3: future-task 化 (`docs/FUTURE_TASKS.md`)
**判定基準**:
- パターンが **未着手の実装タスク** を示唆 (規約や設計ではなく実装課題)
- 当該タスクが **Wave 計画外** (現 Wave 終了後に拾うべき)

**例**:
- compound エントリ「Stryker テスト時間が 30 分超でローカル開発を阻害」
  → FUTURE_TASKS に「Stryker incremental mode 検討」エントリ追加

## 月次 review 手順

毎月 25 日 (Wave 進捗 review と同期) に以下:

1. `ls docs/compound/*.md | wc -l` で蓄積数確認
2. `tags` field でタグ別集計 (例: `grep -l "tags:.*hook" docs/compound/*.md`)
3. 同タグ 3 件以上のクラスタを確認
4. 経路 1/2/3 の判定基準で各クラスタを評価
5. 昇格候補があれば PR を出す (1 昇格 = 1 PR)
6. 昇格済 compound エントリは `archived: true` を frontmatter に追加 (削除はしない、出典として残す)

## archive 基準

`tools/consolidate-memory-extension.py` が以下を自動 archive:

- frontmatter の `archived: true`
- 最終更新から **6 ヶ月以上経過** かつ昇格に至らなかったもの
- 同 outcome の重複エントリ (より新しいエントリを残す)

archive 先: `docs/compound/_archived/{YYYY}/{原ファイル名}` (gitignore 対象外、出典保持のため)

## auto-extract draft の取扱い

`tools/compound-extract.py` が出力する `docs/compound/_drafts/` のファイル:

- **本ディレクトリは gitignore 対象** (人間レビュー前のノイズを commit しない)
- `/compound-learn` で確認後、人間が `docs/compound/{date}_{slug}.md` に昇格させる
- 1 ヶ月放置 された draft は警告対象 (consolidate-memory-extension が検出)

## 関連

- WAVE_PLAN.md L921-930 (Phase 24 P24-T1〜T6)
- `docs/compound/_template.md` (frontmatter 規約)
- `docs/compound/README.md` (運用説明)
- `.claude/skills/compound-learn/SKILL.md` (手動レビュー skill)
