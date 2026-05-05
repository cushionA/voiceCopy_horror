# build-pipeline base — HOW (プロジェクト非依存の手順論理)

> このファイルは `.claude/skills/_two-layer-design.md` で定義された Two-layer 構成の **base 層**。
> SisterGame 固有の呼び先・ファイルパス・規約は overlay (`SKILL.md`) を参照する。
> 本ファイルは状態機械・I/O・エラー処理など「他プロジェクトに移植可能な手順」のみを記述する。

---

## 進行状態の管理

パイプラインは外部 JSON ファイルに**進行状態を外在化**して追跡する。
SisterGame では `designs/pipeline-state.json` がそれに該当する（ファイル位置は overlay で指定）。

### State Schema

```json
{
  "phase": "idle|design|planning|implementation|code-review|review",
  "currentSection": 1,
  "totalSections": null,
  "currentBranch": "feature/xxx",
  "completedFeatures": [],
  "pendingFeatures": [],
  "skippedFeatures": [],
  "failedAttempts": {},
  "lastAction": "説明",
  "lastUpdated": "2026-03-15T12:00:00Z"
}
```

- `phase: "idle"` がパイプライン待機中（初期値）。開始指示で `"design"` に遷移する
- `phase: "planning"` は実装フェーズと接続する**中間状態**として使用する（設計と実装の橋渡し）

### State の読み書き手順（Python）

**読み込み**（パイプライン開始時・`continue` 時）:
```bash
python - <<'PY'
import json, pathlib
p = pathlib.Path("<state-file-path>")
state = json.loads(p.read_text(encoding="utf-8"))
print(state["phase"], state.get("currentSection"))
PY
```

**更新**（各フェーズ遷移時）:
```bash
python - <<'PY'
import json, pathlib, datetime
p = pathlib.Path("<state-file-path>")
state = json.loads(p.read_text(encoding="utf-8"))
state["phase"] = "implementation"
state["lastAction"] = "section-1 の機能分解完了"
state["lastUpdated"] = datetime.datetime.utcnow().isoformat() + "Z"
p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
PY
```

`<state-file-path>` は overlay で具体パスを指定する。

### 書き込みタイミング（必須）

| タイミング | 更新するフィールド |
|-----------|------------------|
| パイプライン開始 | `phase`, `currentBranch`, `lastAction`, `lastUpdated` |
| GDD/全体設計 確定 | `totalSections`, `phase` 維持 |
| セクション設計完了 | `phase` → `"implementation"`, `pendingFeatures` を機能 DB から取得 |
| 機能完了 | `completedFeatures` に追記、`pendingFeatures` から削除、`lastAction`, `lastUpdated` |
| 機能失敗 3 回 | `skippedFeatures` に移動、`failedAttempts[name]` = 3 |
| セクション完了 | `currentSection` インクリメント、`phase` → 次セクションの `"design"` |
| パイプライン完了 | `phase` → `"idle"`, `currentBranch` → null |

---

## データ整合ルール

- **機能 DB が Source of Truth**: 機能の状態は機能 DB（SisterGame では feature-db）が正
- **state JSON はキャッシュ**: 進行位置を追跡するためのもの
- **整合チェック**: 各フェーズ遷移時に機能 DB と state を照合する
  - 機能 DB の `complete` 状態リストと state の `completedFeatures` を突合
  - 乖離があれば**機能 DB を正として state を補正**し、警告を表示する

---

## "continue" モード（再開時の動作）

`continue` 引数で起動された場合:

1. state JSON を読み込む
2. `phase` と `pendingFeatures` から現在地を特定
3. 中断したところから再開する
4. もし state 不整合があれば「データ整合ルール」に従って機能 DB を正として補正

---

## 各フェーズ間の遷移ルール（汎用）

| 遷移 | トリガー |
|------|---------|
| 設計 → 計画 | ユーザー確認後 |
| 計画 → 実装 | ユーザー確認後 |
| 実装中の各機能間 | 自動遷移（テスト Pass 後に次へ） |
| 実装 → レビュー | 自動遷移 |
| レビュー → 次セクション設計 | ユーザー確認後 |

ユーザー確認が必要なポイントは overlay (SKILL.md) で具体化する。

---

## エラー時の処理

| 状況 | アクション |
|------|----------|
| テスト失敗 | 修正を試みる（最大 3 回） / `failedAttempts` に記録 |
| 3 回失敗 | ユーザーに報告して次の機能に進む（`skippedFeatures` に移動） |
| スキル実行失敗 | エラー内容をユーザーに報告して停止 |

---

## I/O コントラクト（base 層が要求する overlay 提供物）

overlay 側で必ず指定すべき項目:

1. **state JSON のパス** — 例: `designs/pipeline-state.json`
2. **機能 DB の操作コマンド** — 例: `python tools/feature-db.py list --status complete`
3. **各 `phase` で呼ぶ skill 名と引数** — 例: design phase で `/design-game`、implementation phase で `/create-feature`
4. **branch 命名規則** — 例: `feature/pipeline-{コンセプト名}`
5. **コミットメッセージ規約** — 例: `docs(設計): GDD 作成`
6. **アーティファクト出力先** — 例: `designs/`、テストファイル配置場所

これら全て揃わないと base のロジックは動かない。overlay でこれらを束ねる責務を持つ。
