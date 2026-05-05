# 人間レビュー gate — 共通モジュール (Wave 5 Phase 23)

design phase / spec phase / implement phase の境界で人間判断を挟むための共通手順。
個別 skill (design-systems / create-feature / build-pipeline) から参照される。

## いつ gate を発火するか

| gate 名 | 発火タイミング | 確認内容 |
|---------|--------------|----------|
| `spec-gate` | spec.md 完成時 | Behavior リストが仕様を網羅しているか |
| `design-gate` | design.md 完成時 | Architect/ 既存設計との整合 (SoA / GameManager / Ability) |
| `tasks-gate` | tasks.md 完成時 | 1 task = 1 feature、5 件以下のテストで完結するか |
| `implement-gate` | feature 実装完了時 | 全テスト Pass + コード規約準拠 (Phase 7 verifiableRequirements の status=passed) |

## 動作 (汎用フロー)

### ステップ 1: gate 発火を pipeline-state.json に記録

```python
import json
state_file = "designs/pipeline-state.json"
state = json.load(open(state_file, encoding="utf-8"))
state["awaitingHumanReview"] = True
state["lastAction"] = "spec-gate fired: review designs/specs/player_movement/spec.md"
state["lastUpdated"] = datetime.now(timezone.utc).isoformat()
json.dump(state, open(state_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
```

### ステップ 2: ユーザーへ確認質問

`AskUserQuestion` ツールで以下の選択肢を提示:

- **承認** → 次 phase へ
- **修正** → 該当ファイルへ指摘内容を追記、現 phase に留まる
- **保留** → `phase: blocked` に遷移、blocker 内容を `claude-progress.txt` に記録

質問例:
> "spec.md の Behavior リスト (10 項目) を確認しました。すべて承認して design phase に進みますか?"

### ステップ 3: 結果に応じて state を更新

```python
# 承認時
state["awaitingHumanReview"] = False
state["phase"] = "design"  # 次 phase へ
# 修正時
state["awaitingHumanReview"] = True  # 維持、Behavior 追加
# 保留時
state["awaitingHumanReview"] = True
state["phase"] = "blocked"
```

### ステップ 4: state 更新を commit (任意)

phase 遷移を git history に残す場合:

```bash
git add designs/pipeline-state.json
git commit -m "chore(state): {gate-name} {approved|modified|blocked}"
```

phase-boundary-commit hook (Wave 5 Phase 7) が自動 tag を打つかは
gate のタイプによる (spec-gate / design-gate は不要、implement-gate は推奨)。

## エラー処理

- `pipeline-state.json` が存在しない → gate 中断、人間に手動状態確認を求める
- `AskUserQuestion` が利用不可 (autonomous mode 等) → state を `awaitingHumanReview: true`
  にしたまま処理を停止 (次セッションで人間が `/resume-handoff` から判断)
- gate を通過したが Behavior 数 ≠ verifiableRequirements 数 → 警告 (整合違反)

## 設計原則

- **冪等**: 同 gate を 2 回呼んでも問題なし (state を見て判断)
- **副作用最小**: state 更新と AskUserQuestion のみ (ファイル直接編集はしない)
- **追跡可能**: 全 gate 通過の記録を `claude-progress.txt` に append

## 関連

- `.claude/rules/sdd-workflow.md` (本 gate がどこで発火するかの全体像)
- `.claude/rules/effective-harnesses.md` (Phase 7 — pipeline-state.json の awaitingHumanReview)
- WAVE_PLAN.md L910-919 (Phase 23 P23-T5: FeatureBench 11% 対策)
