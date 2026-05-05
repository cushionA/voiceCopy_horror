# /test-game-ml — MLプレイテスト実行・分析

## 概要
ML-Agentsベースのプレイテストを実行し、結果を分析してステージ設計にフィードバックする。

## 引数
- `$ARGUMENTS` — ステージID（例: `stage_1_1`）。追加オプション: `episodes=100`, `steps=5000`

## 手順

### Step 1: ステージデータ確認
- `designs/stages/` から対象ステージデータを読み込む
- 対応する StageData ScriptableObject が存在するか確認

### Step 2: プレイテスト実行準備
- StageData を選択した状態で `GameMakePipeline/Run Playtest On Selection` メニューを実行
  （MCP経由: `execute_menu_item` ツール使用）
- パラメータ指定がある場合は PlaytestRunner.RunPlaytest() を直接呼び出し

### Step 3: トレーニング実行指示
ユーザーに以下を案内:
```
1. Unity Editor で Play Mode に入る
2. 別ターミナルで: mlagents-learn config/playtest.yaml --run-id=<stage_id>
3. 指定エピソード数の完了を待つ
```

### Step 4: レポート分析（Claude Agent SDK自動実行）
レポートJSONが生成されたら、Claude Agent SDKで自動分析を実行:
```bash
python tools/analyze-playtest.py Assets/PlaytestReports/<report>.json --stage-data designs/stages/<stage_id>.md
```

このスクリプトが自動的に以下を実行:
- レポートJSON読み込み・分析
- `designs/stage-design-notes.md` に分析結果を追記
- `designs/gimmick-registry.json` に成功パターンを追加

#### 分析観点
- **死亡ヒートマップ**: 死亡集中地点の特定、チャンク・タイル座標への逆変換
- **敵統計**: キル率 < 30% = 難しすぎ、> 90% = 簡単すぎ
- **難易度評価**: DesignedDifficulty との乖離検出
- **アイテム収集率**: < 20% = 見つけにくすぎ、100% = 隠しが甘い

### Step 5: 調整提案
分析結果に基づいて具体的な調整案をユーザーに提示:
- 難しすぎる場合: 穴を狭める、敵の配置間隔を広げる、チェックポイント追加
- 簡単すぎる場合: 障害物追加、敵のパトロール範囲拡大、アイテム配置変更
- ユーザーの承認を得てから `/adjust-stage` で実行

## 出力
- プレイテスト分析レポート（テキスト形式、自動生成）
- stage-design-notes.md への追記（自動）
- gimmick-registry.json への追加（自動）
- 調整提案リスト

## 依存
- `pip install claude-agent-sdk` (Python 3.10+)
- `ANTHROPIC_API_KEY` 環境変数
