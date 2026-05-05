# Mutation Testing 規約 (Wave 5 Phase 14)

Stryker .NET を使った mutation testing の運用規約。
テストカバレッジ (line coverage) では検出できない「テストが意味のあるアサーションを書いているか」を
mutation score で評価する。

## 用語

| 用語 | 意味 |
|------|------|
| **mutation** | 元コードに対する小さな変更 (`+` → `-`、`>` → `>=` 等) |
| **mutant** | 1 個の mutation を適用したコード |
| **killed** | テストが失敗 = mutation を検出できた |
| **survived** | テストが成功 = mutation を検出できなかった (テスト不足のサイン) |
| **mutation score** | killed / total mutants の割合 |

## 閾値

| 範囲 | 判定 | 対応 |
|------|------|------|
| 80%+ | green   | OK、本番投入可 |
| 60-79% | yellow | 警告、レビューで見直し |
| < 60% | red    | テスト追加必須、PR ブロック対象 |

## SisterGame 適用範囲

### 適用する
- `Assets/MyAsset/Core/` 配下のロジッククラス (HpArmorLogic、HitReactionLogic、SituationalBonusLogic 等)
- 純粋計算系 (state 不要、副作用なし)
- 単独で Edit Mode テスト可能なクラス

### 適用しない
- MonoBehaviour 派生クラス (Unity 依存が強い)
- AnimatorController / VisualScripting 経由のロジック
- `[SerializeField]` を使う Inspector 設定主導クラス
- `System.IO` / `Resources.Load` を呼ぶクラス (mutation で副作用が破壊的)

## Unity プロジェクト適合性

Stryker .NET (公式: https://stryker-mutator.io/docs/stryker-net/) は標準的な csproj を前提とするが、
Unity プロジェクトは csproj が動的生成 (Editor 起動時) されるため以下の制約:

| 制約 | 対処方針 |
|------|----------|
| csproj が動的生成 | `tools/mutation-runner.sh` で Unity Editor 起動 → `-executeMethod CSProjectGen` で固定生成 → Stryker 起動 |
| `UnityEngine` 参照解決 | Stryker config で `<TargetFramework>` を Unity の Mono profile に合わせる |
| `EditMode` テスト実行 | NUnit3TestAdapter 経由で実行可能 (Unity Test Framework が NUnit ベース) |
| Source Generator (ODCGenerator) | `<EmitCompilerGeneratedFiles>true</EmitCompilerGeneratedFiles>` で展開後にテスト |

詳細は実環境検証時に `tools/mutation-runner.sh` を更新する (現状は MVP スケルトン)。

## 運用フロー

### 通常開発
1. `python tools/feature-db.py update <feature>` で全テスト Pass を確認
2. （オプション）`bash tools/mutation-runner.sh --feature <feature>` で mutation 計測
3. mutation score < 80% なら `tools/mutation-report.py` の **survived 一覧** からテスト追加

### create-feature SKILL での opt-in
Phase 23 の人間 gate (implement-gate) に追加で:

```bash
# 環境変数で ON にしたときのみ Stryker 実行
MUTATION_TESTING=1 python tools/feature-db.py update <feature>
```

`MUTATION_TESTING=1` が無ければ通常フローと同じ。`create-feature` SKILL は本変数を読み、
ON ならば mutation-runner.sh を呼ぶ (将来、本格運用時に SKILL.md を更新)。

### 月次 review
全 feature の mutation score を集計し `docs/reports/analysis/mutation-{YYYY-MM}.md` に記録。
60% 未満の feature は次月の優先テスト追加対象。

## 設定ファイル

`stryker-config.json` を repo ルートに配置:

```json
{
  "stryker-config": {
    "project": "Assets/MyAsset/...",
    "test-projects": ["Assets/Tests/EditMode/..."],
    "mutate": ["Assets/MyAsset/Core/Damage/*.cs"],
    "thresholds": {
      "high": 80,
      "low": 60,
      "break": 0
    },
    "reporters": ["json", "html", "progress"]
  }
}
```

詳細: `stryker-config.json` の本ファイル (本 Phase で導入)。

## 実環境検証 (将来タスク)

本 Phase は **MVP 構成**。実際の Stryker 起動は以下の理由で別 PR で検証:

- Unity Editor 起動 + csproj 生成の手順確立 (環境依存)
- Stryker .NET の Unity 対応事例が少ない (要試行錯誤)
- 1 機能で 5-10 分以上の処理時間 (CI 統合は時間予算と要相談)

`docs/FUTURE_TASKS.md` に「Stryker 実環境検証」エントリを追加 (本 PR で記録)。

## 関連

- WAVE_PLAN.md L862-871 (Phase 14 P14-T1〜T6)
- `tools/mutation-runner.sh` (起動 wrapper)
- `tools/mutation-report.py` (JSON → Markdown)
- `stryker-config.json` (設定)
- 外部: https://stryker-mutator.io/docs/stryker-net/
