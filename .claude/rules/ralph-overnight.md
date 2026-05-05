# Ralph 夜間バッチ運用ルール (Wave 5 Phase 18)

`/ralph-loop` を夜間バッチで動かす際の安全規約。Phase 20 Sandbox + Docker --network none と組み合わせて
人間監視なしで一晩 3-5 タスクを消化することを目標とする。

## 起動前チェックリスト

夜間バッチ起動前に必ず確認:

- [ ] **作業ブランチがクリーン**: `git status` で M / ?? が無い、または stash 済
- [ ] **pipeline-state.json の phase=idle** (`bash scripts/init.sh --short` で確認)
- [ ] **対象タスクが🟢タグ** (実装容易・low risk)
- [ ] **🔴タグタスクは含めない** (人間判断必須なため夜間バッチ向けでない)
- [ ] **lint hook = warn** (error 段階だと連続失敗が増える)
- [ ] **TDD-Guard が無効化されている** (Phase 6 不採用なら Wave 5 時点で問題なし)
- [ ] **Sandbox 環境で起動**: `--dangerously-skip-permissions` を使う場合は必ず Docker 内 (Issue #17544)

## 推奨環境変数

```bash
export RALPH_MAX_TEST_LOOPS=3       # 連続失敗 3 回で blocker
export RALPH_DONE_SIGNALS=2          # 2 feature 完了で DONE 候補 1 つ
export RALPH_TEST_PCT=30             # テスト 30% 増で DONE 候補 2 つ
export RALPH_OVERNIGHT=1             # 夜間モード: より conservative

# Phase 16 連動 (将来): keepalive ping を有効化
export KEEPALIVE_PING=1
export CACHE_TTL_HINT=1h
```

## 夜間モードの追加ガード

`RALPH_OVERNIGHT=1` 時の追加判定 (将来 ralph-exit-gate.py で実装):

| 追加条件 | 値 |
|---------|-----|
| 1 iteration 最長時間 | 30 分 (超で blocker) |
| トータル時間上限 | 8 時間 (超で stop) |
| トータルコスト上限 | $20 (cost-aggregate.py 連携、超で stop) |
| Bash command 数上限 | 200/iteration |

これらは現状 manual 監視。実装は将来タスク。

## 推奨タスク種類

| 種類 | 例 | 理由 |
|------|-----|------|
| 🟢 typo 修正 / コメント追加 | `fix(docs): 誤字修正 X 箇所` | リスク低、テスト不要 |
| 🟢 lint 修正 | warn 段階で残った lint 違反の機械修正 | パターンマッチのみ |
| 🟢 import 整理 | unused import 削除 | コンパイル通れば OK |
| 🟢 コメント翻訳 | 英語コメント → 日本語 | 動作変わらず |
| 🟢 テスト追加 (既存実装に対する境界値テスト) | unit test の augment | 実装は変えない |

## 非推奨タスク

| 種類 | 理由 |
|------|------|
| 🔴 アーキテクチャ変更 | 人間判断必須、Architect/ への影響大 |
| 🔴 新機能実装 (init-agent 経由 spec が必要) | 仕様確定無しに実装させると FeatureBench 11% 問題 |
| 🔴 Public API 変更 | 既存テスト全 pass 確認後の人間判断必要 |
| 🔴 Settings.json 編集 | hook 設定の連鎖変更リスク |
| 🟡 ステージ設計 / アセット生成 | 美的判断必須 |

## Sandbox 環境前提

夜間バッチは **Phase 20 Sandbox** (Wave 4 完了) の Docker --network none 環境で起動する:

```bash
# 起動例 (Phase 20 完成後の想定)
docker run --rm \
  --network none \
  -v "$PWD":/workspace \
  -e RALPH_OVERNIGHT=1 \
  claude-code-sandbox \
  /loop /ralph-loop
```

## 監視 / 介入

夜間バッチ中に以下を確認できる仕組みを用意:

| 監視項目 | 確認方法 |
|---------|---------|
| iteration 進捗 | `cat .claude/ralph-state.json` |
| pipeline 状態 | `bash scripts/init.sh --short` |
| コスト状態 | `python tools/cost-report.py --period 1d` (Phase 15 連動) |
| commit 履歴 | `git log --oneline main..HEAD` |
| blocker | exit code 2 で停止、人間 review 待ち |

## 終了後の片付け

ralph-loop が exit (stop または blocker) したら:

1. `bash scripts/init.sh` で全状態確認
2. `git log --oneline main..HEAD` で commit 履歴 review (不適切な commit が無いか)
3. 不適切な commit があれば `git revert` (force-push は禁止)
4. `python tools/compound-extract.py` (Phase 24 連動) で session の学びを抽出
5. `/handoff-note` でセッション締め

## 失敗時のロールバック

ralph-loop が予期せぬ commit を量産した場合:

```bash
# 直近の Ralph commit (タグ "wave5-checkpoint-*" で識別)
git tag --list "wave5-checkpoint-*" | tail -10

# 安全なロールバック (revert で履歴を残す)
git revert <commit-hash>

# main / リモート履歴は変更しない (force-push 禁止)
```

破壊的ロールバック (`git reset --hard`) は **ローカルのみ** で可、push 済 commit には適用しない。

## 関連

- WAVE_PLAN.md L885-895 (Phase 18 P18-T5 夜間バッチ運用ルール)
- `.claude/skills/ralph-loop/SKILL.md`
- `tools/ralph-exit-gate.py`
- Phase 20 (Wave 4) Sandbox + Docker --network none
- Phase 24 (本 Wave) compound-extract.py で session 学び抽出
- Phase 16 (5/2 以降) keepalive-ping.sh で長時間バッチの cache 維持
