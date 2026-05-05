---
name: design-stage
description: Design a 2D side-scroller stage using the stage-layout-2d format. Takes a stage concept and generates complete stage data.
user-invocable: true
argument-hint: <stage concept or brief description>
---

# Design Stage: $ARGUMENTS

ステージコンセプトから `instruction-formats/stage-layout-2d.md` フォーマットに基づくステージデータを生成する。

## 前提
- `designs/game-design.md` が存在すること（ゲーム全体のコンテキスト把握のため）
- `instruction-formats/stage-layout-2d.md` フォーマットに従うこと

## 手順

1. **コンテキスト収集**:
   - `designs/game-design.md` からゲームジャンル、メカニクス、敵タイプ、アイテムタイプを確認
   - **`designs/asset-spec.json` を読み、タイルサイズ・チャンクサイズ・ジャンプ距離等の制約値を取得する**
   - 既存ステージがあれば `designs/stages/` を確認し、難易度の連続性を保つ
   - **`designs/stage-design-notes.md` を必ず読み、過去の調整ルールを適用する**
   - **`designs/gimmick-registry.json` を確認し、実績のあるギミックパターンを活用する**
   - ユーザーの入力からステージのテーマ、雰囲気、難易度意図を整理

2. **ステージ構造設計**:
   - チャンク数を決定（短いステージ: 4-6チャンク、中間: 8-12、長い: 15+）
   - 難易度カーブを設計: 序盤は安全、中盤で緊張、終盤にクライマックス
   - チェックポイント配置: 難所の直前に置く
   - 以下の原則に従う:
     - 新メカニクスは安全な場所で導入 → 次のチャンクでチャレンジに使用
     - ピット（落下穴）の前には必ず平坦な助走エリア
     - 初見殺しを避ける（危険の予兆を視覚的に示す）
     - プレイヤーの視認範囲内に次の足場が見えること

3. **タイルグリッド作成**:
   - 各チャンクのタイルグリッドを `stage-layout-2d.md` の文字セットで作成
   - グリッドサイズは全チャンク統一（推奨: 20列 x 12行）
   - 地形バリエーション: 平坦、階段状、洞窟、高低差

4. **敵配置**:
   - ステージ難易度に応じた敵の種類と密度
   - 初見プレイヤーが対処できる配置（背後からの奇襲は控えめに）
   - 敵グループは2-3体まで、それ以上は高難度ステージのみ

5. **アイテム・コレクティブル配置**:
   - 正規ルートにコイン/基本アイテムを配置
   - 探索報酬として隠しルートにパワーアップ/レアアイテム
   - 回復アイテムは難所の直前か直後

6. **レビュー用サマリー作成**:
   - ステージの全体マップ概要（チャンクごとの1行説明）
   - 難易度カーブの説明
   - 想定プレイ時間
   - 使用する新メカニクス/ギミックのリスト

7. **出力**: `designs/stages/[stage_id].md` にフォーマットに従ったステージデータを保存

8. **ギミック登録**: 新規ギミックパターンを使用した場合、`designs/gimmick-registry.json` に追加する
   ```json
   {
     "id": "gimmick_id",
     "name": "ギミック名",
     "description": "ギミックの説明",
     "tile_pattern": "タイルグリッドでの表現例（小さい抜粋）",
     "difficulty_range": [1, 10],
     "tags": ["platform", "timing", "combat", "puzzle", "secret"],
     "notes": "配置時の注意点",
     "first_used_in": "stage_id",
     "success_rating": null
   }
   ```

9. **ユーザー調整後の学習**: ステージ調整が行われた場合、以下を実行する
   - `designs/stage-design-notes.md` に調整内容を追記（日付、ステージID、変更前後、一般化ルール）
   - 該当ギミックの `gimmick-registry.json` エントリに `notes` を追記
   - 調整内容が一般ルール化できる場合、stage-design-notes.md の該当セクションにルールとして追加

## ルール
- `instruction-formats/stage-layout-2d.md` のタイル文字・フォーマットに厳密に従う
- ゲームに存在しない敵タイプ/アイテムタイプを勝手に追加しない（GDDに定義されたものを使う）
- 全チャンクのグリッドサイズ（行数・列数）を統一する
- `spawn` と `goal` は必須。checkpointは4チャンク以上のステージでは最低1つ配置
- 難易度値(1-10)はゲーム全体での相対値。ステージ1-1なら1-2、最終ステージなら8-10
- 水平方向のプラットフォーム間隔はプレイヤーのジャンプ距離以内に収める（`asset-spec.json` の `world.maxJumpWidth` 参照）
- チャンクサイズは `asset-spec.json` の `stage.chunkColumns` x `stage.chunkRows` に従う
- `asset-spec.json` が未設定の場合はエラーを出し、先に `/design-game` を実行するよう案内する

## 出力先
- `designs/stages/[stage_id].md`

## 次のステップ
ステージをUnityに構築する:
- **手動レビュー後**: stage-builder エージェントに渡す、または StageData ScriptableObject に変換
- **即座にビルド**: stage-builder エージェントに `designs/stages/[stage_id].md` を渡す
