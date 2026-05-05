---
name: adjust-stage
description: Adjust a stage based on feedback. Records learnings to stage-design-notes.md and gimmick-registry.json for future stages.
user-invocable: true
argument-hint: <stage_id> <feedback or adjustment description>
---

# Adjust Stage: $ARGUMENTS

ステージのフィードバックに基づく調整を行い、学習内容を記録する。

## 手順

1. **対象ステージ読み込み**:
   - `designs/stages/[stage_id].md` を読み込む
   - ユーザーのフィードバック内容を整理する

2. **調整実行**:
   - フィードバックに基づきステージデータを修正する
   - 修正箇所をメモする（変更前 → 変更後）

3. **学習記録**（重要）:
   `designs/stage-design-notes.md` に以下のフォーマットで追記する:
   ```markdown
   ### [今日の日付] [stage_id] — [調整の要約]
   - 変更前: [具体的な値/配置]
   - 変更後: [具体的な値/配置]
   - 理由: [ユーザーのフィードバック]
   - 一般化ルール: [今後のステージ全般に適用すべきルール]
   ```

   記録内容の分類先:
   - 穴幅・プラットフォーム間隔 → 「プラットフォーム・穴のルール」セクション
   - 敵の配置・数 → 「敵配置のルール」セクション
   - ギミックの配置・調整 → 「ギミック配置のルール」セクション
   - 全体的な難易度 → 「難易度カーブのルール」セクション

4. **ギミックレジストリ更新**:
   調整がギミックに関するものの場合、`designs/gimmick-registry.json` の該当エントリを更新:
   - `notes` に注意事項を追記
   - `success_rating` を更新（ユーザーが満足なら "good"、調整が必要だったなら "needs_tuning"）

5. **一般化の判断**:
   同じ種類の調整が2回以上発生している場合:
   - stage-design-notes.md にルールとして明確に記載
   - `/design-stage` スキルの手順2「ステージ構造設計」の原則に追加を検討
   - ユーザーに「このルールを今後のデフォルトにしますか？」と確認

6. **出力**: 修正済みステージデータを `designs/stages/[stage_id].md` に上書き保存

## ルール
- 調整前のステージデータは必ずバックアップとして記録に残す（stage-design-notes.md内に変更前の値を含める）
- 学習記録は省略しない。小さな調整でも「一般化ルール」を考える
- 数値の調整は具体的に記録する（「穴を狭くした」ではなく「穴を6タイル→4タイルに縮小」）
