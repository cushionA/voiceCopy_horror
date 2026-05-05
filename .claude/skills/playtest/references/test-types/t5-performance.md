# T5: パフォーマンス回帰テスト — パフォーマンス計測の専門家

## 役割
機能の実装を読み、パフォーマンス問題を起こしうるホットパスを特定し、計測シナリオを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能のUpdate/FixedUpdate内処理
- アロケーション可能性のあるコード（new, LINQ, string連結等）
- 処理頻度（毎フレーム、イベント駆動、一回きり等）

### 設計手順
1. **ホットパス特定**: Update/FixedUpdate内で毎フレーム実行されるコードを抽出
2. **アロケーション箇所特定**: new, List生成, string連結, LINQ, ボクシングを列挙
3. **負荷シナリオ設計**: 機能が最も負荷をかける状況を特定
   - 例: 複数敵同時戦闘、範囲攻撃ヒット、大量ポップアップ生成
4. **ベースライン定義**: 比較基準となる通常状態のシナリオ
5. **閾値設定**: デフォルト閾値を使うか、機能固有の閾値が必要か判断

### 設計品質基準
- 毎フレーム実行のコードパスが計測対象に含まれている
- 通常シナリオ + 高負荷シナリオの両方がある
- GCアロケーション箇所が特定されている

## 実行手段
- `/unicli`: Profiler.StartRecording
- `/unicli`: Profiler.StopRecording
- `/unicli`: Profiler.AnalyzeFrames
- `/unicli`: Profiler.FindSpikes --frameTimeThresholdMs <閾値>

## 実行フロー

### 1. 録画開始（PlayMode Enter 後）
```bash
unicli exec Profiler.StartRecording
```

### 2. テスト実行
- AutoInput（T2）やDynamic（T7）と並行して計測
- 設計した負荷シナリオを実行

### 3. 録画停止
```bash
unicli exec Profiler.StopRecording
```

### 4. 分析
```bash
# フレーム統計
unicli exec Profiler.AnalyzeFrames
# → avgFrameTime, minFrameTime, maxFrameTime, totalFrames

# スパイク検出（30fps = 33.3ms 閾値）
unicli exec Profiler.FindSpikes --frameTimeThresholdMs 33
# → spikeCount, spikeFrames[], topSamples[]
```

## 閾値設定

| 指標 | 許容値 | 警告値 | 異常値 |
|------|--------|--------|--------|
| 平均フレームタイム | < 16.6ms (60fps) | 16.6-33ms | > 33ms |
| スパイクフレーム率 | < 1% | 1-5% | > 5% |
| GC Alloc/フレーム | < 1KB | 1-10KB | > 10KB |

## 対象シナリオ

| シナリオ | 負荷ポイント |
|---------|-------------|
| 通常プレイ | ベースライン計測 |
| 複数敵戦闘 | ActionExecutor, HitBox判定 |
| エフェクト大量 | パーティクル, マテリアル |
| レベル切替 | アセットロード, シーン遷移 |
| UI大量更新 | HUD, ダメージポップアップ |

## 設計指針
- ベースライン（何もしない状態）を最初に計測
- 同一シナリオを複数回実行して分散を確認
- 回帰テスト: 前回の計測値と比較（手動記録）
- Update内のアロケーション検出が最優先

## 結果判定
- 全指標が許容値内 → Pass
- 警告値超過 → Warning（レポートに記載、feature-dbは変更しない）
- 異常値超過 → Fail（レポートに記載、対応策を提案）

## レポート出力例
```
### Performance (T5)
- Avg frame time: 12.3 ms (60fps OK)
- Spikes: 2 frames > 33ms (0.3%, 許容範囲内)
- Top allocators:
  1. ActionExecutor.Execute: 0.8ms avg
  2. HitBoxChecker.CheckCollisions: 0.3ms avg
- GC: 0.5KB/frame avg
```
