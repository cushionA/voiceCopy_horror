# ralph-loop — base.md (HOW)

Ralph パターンの汎用ループロジック。frankbria/ralph-claude-code の dual-condition exit gate を参考。

## Ralph パターンとは

> Repeat a task until 2 independent signals say "done" or 1 fatal signal says "stop".

シンプルな "while-do" ループに、**dual-condition exit gate** を組み込んだもの。
1 シグナルだけでは false positive (一時的な OK で抜けてしまう) のリスク。
2 シグナル要求で確度を上げる。

## ループ構造

```
state = ralph_state()  # 初期化
state.reset()

while True:
    code = exit_gate.check(state)
    if code != 0:
        break  # 1=success-stop, 2=blocker

    do_one_iteration()  # consume-future-tasks 等

    state.signal("iteration")

cleanup()
```

## dual-condition exit gate

3 つの正規シグナル + 1 つの blocker シグナル:

### 正規シグナル (2 つ集まれば DONE)
1. **all-features-completed**: feature-db / pipeline-state で pending=0
2. **feature-completed-count >= threshold**: 連続 N feature 完了 (default 2)
3. **test-count delta >= threshold**: テスト数増加率 N% (default 30%)

### blocker シグナル (1 つで STOP)
- **consecutive-test-failures >= threshold** (default 3)
- **pipeline phase=blocked**

## state machine

| 遷移 | from | to | trigger |
|------|------|----|---------| 
| reset | * | initial | --reset 呼出 |
| iteration | * | * | --signal iteration |
| test pass | * | (counters++) | --signal test-passed |
| test fail | * | (consecutive++) | --signal test-failed |
| feature done | * | (completed++) | --signal feature-completed |

state は外部 JSON (`.claude/ralph-state.json` 等) に永続化、ループ間で共有。

## エラー処理

- state ファイル破損 → 警告して reset 扱い
- pipeline-state.json 不在 → blocker 扱い (前提条件不足)
- exit gate exit code 2 → blocker handoff (init-agent / 人間に戻す)

## 実装上の注意

- **副作用なし check**: `--check` は state を変更しない
- **冪等な signal**: 同じ signal を 2 回呼んでも整合性を保つ
- **timeout 保護**: ループに max_iterations を設けて無限ループ防止 (default 50)
- **interrupted recovery**: 中断後の再開時は state がそのまま使える

## 設計原則

- **dual condition でノイズ抑制**: 1 signal stop は false positive 多い
- **ステート永続化**: ループ間 / セッション間で継続
- **gate と本処理を分離**: gate は判定だけ、本処理は consume-future-tasks 等別 skill
- **exit code で意図を表現**: 0=continue, 1=stop, 2=blocker

## 関連

- `_two-layer-design.md` (本 base/overlay 設計の根拠)
- 上位 SKILL.md (project-specific overlay)
