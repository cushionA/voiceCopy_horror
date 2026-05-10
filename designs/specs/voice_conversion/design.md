# design: voice_conversion (kNN-VC + WavLM)

**Phase**: 7 (init-agent draft)
**Source spec**: `designs/specs/voice_conversion/spec.md`
**Status**: draft (要 init-agent レビュー → 人間 design-gate 承認)

## Components (C# クラス分割)

### 1. `WavLMFeatureExtractor`

**責務**: 16kHz mono audio → WavLM Layer 6 特徴 [N, 1024]

**配置**: `voice_Horror_Game/Assets/SentisSpike/Scripts/KnnVc/WavLMFeatureExtractor.cs`
**namespace**: `VoiceHorror.KnnVc`

**Public API**:
```csharp
public class WavLMFeatureExtractor : IDisposable
{
    public WavLMFeatureExtractor(ModelAsset wavlmModel, BackendType backend = BackendType.GPUCompute);

    /// AudioClip → 16kHz mono → features [N, 1024]
    public Tensor<float> ExtractFeatures(AudioClip clip);

    /// raw 16kHz mono float[] → features
    public Tensor<float> ExtractFeatures(float[] audio16k);

    /// 起動直後に呼ぶ。dummy 5sec audio で warmup forward を 1 回実行
    public void Warmup();

    public void Dispose();
}
```

**実装ポイント**:
- Sentis Worker を内部に保持 (再利用)
- 入力 AudioClip が 16kHz でなければリサンプル
- 入力チャンネル数が 2 以上ならモノミックスダウン
- Sentis ceil_mode バグ回避のため、入力長が極端に短い (< 0.1秒) 時は zero-pad

### 2. `MatchingSetPool`

**責務**: WavLM 特徴の蓄積・永続化・α 比率混合

**配置**: `Scripts/KnnVc/MatchingSetPool.cs`

**Public API**:
```csharp
public class MatchingSetPool
{
    public string Name { get; }              // "target" / "player" 等
    public int FrameCount { get; }            // プール内の frame 数
    public float Coverage5MinRatio { get; }   // 5 分相当 (15000 frames) に対する割合

    public MatchingSetPool(string name);

    /// features [N, 1024] を append (weight=1.0 デフォルト)
    public void Append(Tensor<float> features, float weight = 1.0f);

    /// プール全体を flat float[] (N * 1024) で取り出す
    public Tensor<float> ToTensor();

    /// 各 frame の重み配列 [N] を取り出す (KnnVcConverter で使用)
    public float[] GetWeights();

    /// 永続化 (npy 形式、Python と互換、NpyWriter 流用)
    public void SaveTo(string filePath);
    public static MatchingSetPool LoadFrom(string filePath, string name);
}

/// 重みつき kNN マッチ用の合成プール (α 混合)
/// α=1.0 で純 a (target)、α=0.0 で純 b (player)、α=0.5 で均等
public static class WeightedPoolBuilder
{
    public static (Tensor<float> features, float[] weights) Build(
        MatchingSetPool a, MatchingSetPool b, float alpha);
}
```

**実装ポイント**:
- 内部表現: `List<(float[1024] feature, float weight)>` (append 効率)
- `ToTensor()` で連結し Sentis Tensor 化 (キャッシュ可)
- **永続化フォーマット: npy (NpyWriter / NpyReader 流用)**
  - `Application.persistentDataPath/voice_horror/pools/{name}.npy` (features)
  - `Application.persistentDataPath/voice_horror/pools/{name}_weights.npy` (weights)
  - Python サイドで簡単に読める (Phase 9 収録時の audio→npy バッチ変換)
- 5 分相当 = WavLM ~50fps × 300sec ≈ 15000 frames
- カバレッジ段階目標: スパイク 30秒 (1500 frames) / MVP 3分 (9000 frames) / 本番 10分 (30000 frames)
- weight は α 混合時に外部 (`WeightedPoolBuilder`) で設定、プール内部では 1.0 デフォルト

### 3. `KnnVcConverter`

**責務**: query 特徴 + matching set → kNN 検索 → matched features

**配置**: `Scripts/KnnVc/KnnVcConverter.cs`

**Public API**:
```csharp
public class KnnVcConverter
{
    public int TopK { get; set; } = 4;       // kNN の k 値

    /// query [N1, 1024] と matching set [N2, 1024] から converted [N1, 1024]
    /// weights [N2] はオプション。null の場合は全て 1.0 として扱う (均等 kNN)
    /// weights 指定時は cosine distance に weight を反映 (α 混合の核心)
    public Tensor<float> Convert(
        Tensor<float> query,
        Tensor<float> matchingSet,
        float[] weights = null);
}
```

**実装ポイント**:
- ピュア kNN (Sentis 不要、CPU/SIMD でも可)
- matcher.py:21 `fast_cosine_dist` を C# に移植
- topk=4 で平均、最終 [N1, 1024]
- **重みつき kNN**: distance を `cos_dist / weight` でスケーリング
  (weight 大の frame は近く見える → kNN で選ばれやすい)
  - α 混合の場合: a プールの全 frame に weight=`α`、b プールの全 frame に weight=`1-α`
  - α=1.0 → b プール完全無視 (distance ÷ 0 = inf)、α=0.0 → a プール完全無視
- 大規模 matching set (>15000 frames) の場合 GPU で torch.cdist 相当を使うか検討

### 4. `HiFiGANVocoder`

**責務**: kNN マッチ後の features [1, T_frame, 1024] → audio [T_audio]

**配置**: `Scripts/KnnVc/HiFiGANVocoder.cs`

**Public API**:
```csharp
public class HiFiGANVocoder : IDisposable
{
    public HiFiGANVocoder(ModelAsset hifiganModel, BackendType backend = BackendType.GPUCompute);

    /// features (1, T_frame, 1024) → audio (T_audio,)
    public float[] Vocode(Tensor<float> features);

    /// 出力 peak が 1.0 超えていれば 0.95 に正規化
    public float[] VocodeNormalized(Tensor<float> features);

    public void Warmup();
    public void Dispose();
}
```

**実装ポイント**:
- HiFiGAN 入力は `(B=1, T_frame, dim=1024)` (channel-last) — spec/spike で実証済
- Sentis output (1, 1, T_audio) を float[T_audio] に flatten

### 5. `SpeakerSimilarityJudge`

**責務**: 2 プールの話者類似度判定 (BAD/GOOD ED 分岐用)

**配置**: `Scripts/KnnVc/SpeakerSimilarityJudge.cs`

**Public API**:
```csharp
[CreateAssetMenu(fileName = "EdThresholds", menuName = "VoiceHorror/ED Thresholds")]
public class EdThresholdsAsset : ScriptableObject
{
    public float HighThreshold = 0.85f;  // > 0.85 → BAD ED「奪われる」(仮、Phase 8 で実測)
    public float MidLow        = 0.40f;  // < 0.40 → GOOD ED「脱出」
    public float MidHigh       = 0.70f;  // 0.40-0.70 → BAD「声変えて電話切れ」
}

public class SpeakerSimilarityJudge
{
    public EdThresholdsAsset Thresholds { get; set; }

    public enum Verdict { BadCaptured, BadVoiceChange, Good }

    /// 2 プールの平均特徴のコサイン類似度を返す
    /// 戻り値域: [0, 1] (生 cosine sim を max(0, cos) でクランプ)
    public float ComputeSimilarity(MatchingSetPool a, MatchingSetPool b);

    /// 類似度から ED 判定 (Thresholds に従う)
    public Verdict Judge(float similarity);
}
```

**実装ポイント**:
- cosine sim = `dot(a, b) / (|a| * |b|)` の生値は [-1, 1]
- voice_horror では `max(0, cos)` でクランプして [0, 1] に統一
  (反対方向のベクトル =「逆の声」概念は不要、無関係扱いで十分)
- Thresholds は ScriptableObject 経由で hot-fix 可能
  (本番リリース後にテレメトリで再調整する場合の保険)

### 6. `VoiceConversionService` (ファサード)

**責務**: 上記すべての統合エントリポイント

**配置**: `Scripts/KnnVc/VoiceConversionService.cs`

**Public API**:
```csharp
public class VoiceConversionService : MonoBehaviour, IDisposable
{
    [Header("Models")]
    [SerializeField] ModelAsset wavlmModel;
    [SerializeField] ModelAsset hifiganModel;

    [Header("ED 判定")]
    [SerializeField] EdThresholdsAsset edThresholds;

    [Header("Pools")]
    public MatchingSetPool TargetPool { get; private set; }   // 少女声 (Phase 9 収録音)
    public MatchingSetPool PlayerPool { get; private set; }   // ゲーム中蓄積

    /// 起動時呼出: モデルロード (warmup は別途 WarmupAsync 推奨)
    /// Initialize は ONNX ロード + プール永続化ロードまで (重い処理は WarmupAsync で分離)
    public void Initialize();

    /// タイトル → ゲーム開始遷移時に呼ぶ (SR-002)
    /// dummy 5sec audio で WavLM + HiFiGAN forward を 1 回実行
    /// シーン遷移 loading で隠す想定
    public IEnumerator WarmupAsync();

    /// プレイヤー録音を AudioClip 単位で蓄積 (B-2 MS-002)
    public void AccumulatePlayerVoice(AudioClip clip);

    /// 変換: source の発話内容を target 声色で再生
    /// alpha: 1.0 = 純 target 声 / 0.0 = 純 player 声 / 0.5 = 混合 (G-2)
    /// 内部で WeightedPoolBuilder.Build(TargetPool, PlayerPool, alpha) を使用
    public AudioClip Convert(AudioClip source, float targetWeightAlpha = 1.0f);

    /// 変換 + per-stage timings 内訳取得 (extract / knn / vocode / total)。
    /// 量子化比較ランナーや perf 計測の細粒度分析用。
    public AudioClip Convert(AudioClip source, float targetWeightAlpha, out ConversionTimings timings);

    /// 事前トークン化用: source AudioClip を WavLM forward して
    /// query features [N, 1024] を返す (戻り値は呼出側 Dispose 責務)。
    /// 配布時に固定の少女セリフ等を起動時/Addressable ロード時にここで一括 tokenize し、
    /// 演出時の Convert は下の Tensor 入力 overload に切り替える設計。
    public Tensor<float> ExtractQueryFeatures(AudioClip source);

    /// 事前トークン化された query features を入力に取り、WavLM forward を skip して変換。
    /// timings.extractMs は 0 で返る。
    /// 効果実測: batch mean -34% (615ms → 405ms)、p95 -47%
    /// (Phase 8 PR #8 計測、VcTestOutput/perf_20260510_135417/perf.csv)
    public AudioClip Convert(Tensor<float> queryFeatures, float targetWeightAlpha, out ConversionTimings timings);

    /// ED 判定 (B-3 SS-002)
    public SpeakerSimilarityJudge.Verdict JudgeEnding();

    /// IDisposable 実装
    /// MonoBehaviour の OnDestroy() からも自動的に呼ばれる
    public void Dispose();

    /// MonoBehaviour lifecycle
    void OnDestroy() { Dispose(); }
}
```

**実装ポイント** (lifecycle):
- MonoBehaviour + IDisposable のハイブリッド構成
- `OnDestroy()` で `Dispose()` を呼ぶ (Unity が自動解放を保証)
- 明示破棄 (Editor / テスト) も可能
- Worker は `Dispose()` で確実に解放、プールは永続化保存
- DontDestroyOnLoad の GameObject にアタッチ (singleton 風、シーン遷移で再初期化なし)

## Sentis Worker 管理

- **Worker は GameObject ライフサイクルではなく Service の Initialize/Shutdown で管理**
  → シーン遷移で再初期化しなくて済む (warmup コスト回避)
- DontDestroyOnLoad の GameObject に Service をアタッチ (singleton 風)
- メモリ予算: WavLM ~600MB + HiFiGAN ~50MB + features pool ~100MB = **~750MB**

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| ModelAsset 未アサイン | `Initialize()` で `LogError` + `Disposed` 状態で待機 |
| GPU 利用不可 | BackendType.CPU にフォールバック (低速だが動作) |
| ONNX ロード失敗 (op 不対応等) | 例外を投げる + ログ出力。ゲームは起動継続 (VC は OFF 状態) |
| 入力 AudioClip が空 / 短すぎる | 0.1 秒未満は zero-pad、空の場合は無音 AudioClip 返す |
| matching set が空 | `Convert` を呼ぶ前に target プールロードを必須化 (assert) |
| WavLM forward で NaN/Inf 検出 | warning ログ + 次フレームから再 warmup |

## パフォーマンス予算 (RTX 2070S 想定)

| 操作 | warmup 後の時間 |
|------|----------------|
| AudioClip → 16kHz リサンプル | < 5ms (CPU) |
| WavLM forward (1 秒 audio) | ~8ms |
| kNN match (query 50 frames × pool 15000 frames) | ~5-15ms |
| HiFiGAN vocode (1 秒分) | ~12ms |
| 16kHz audio → AudioClip | < 5ms |
| **合計 (1 秒変換)** | **~35-45ms** (RTF 0.04) |

ストリーミング不要、非ストリーミング (録音→全変換→再生) で十分。

## 事前トークン化パス (Phase 8 PR #8 で導入)

### 動機

ナラティブ演出 (BAD ED で「混ざっていく」) で使う source 音声 (少女セリフ) は
配布時点で **固定**。プレイヤー録音は逆に実時間 forward 必要だが、source 側は
事前に WavLM Layer 6 features を計算して `.npy` として同梱できる。

### パイプライン分岐

```
[player 録音 → Pool 蓄積]
   AudioClip → WavLM(forward) → 1024-dim features → MatchingSetPool.Append
                ↑ 実時間で必須

[ナラティブ演出: 固定 source 変換]
   AudioClip ─┬─ WavLM(forward) ─┐
              │   ↑ 既存パス     ├─→ Convert (kNN + HiFiGAN)
   .npy ──────┴─ NpyReader ──────┘
                ↑ 事前トークン化パス (本 PR で追加)
```

### 配布物

- 少女セリフ N 本 → 各 `~6 MB / 30 秒` の `.npy` (FP32 features)
- FP16 で保存すれば半分 (~3 MB / 30 秒)
- Addressable group: `Audio_PretokenizedFeatures` (label: `pretokenize`, `event-*`)

### 計測実績 (PR #8、`VcPerfRunner.usePretokenizedSource=true`)

| 計測 | baseline (live forward) | pretokenized | delta |
|------|------------------------|--------------|-------|
| batch mean (n=40) | 615.1 ms | **404.5 ms** | **−34.2%** |
| batch p95 | 693.8 ms | 461.4 ms | −33.5% |
| single p95 | 845.4 ms | 445.0 ms | **−47.4%** |

→ 演出時のセリフ変換が「ボタン押下から 0.4 秒以内」に収まる体感に変わる。
   FP16 量子化が Sentis では失敗 (+5%) した一方、こちらは大成功。

### 制約

- 事前トークン化できるのは **source 側のみ**。プレイヤー録音は実時間 forward 必須
- → WavLM ONNX (340 MB) は引き続きランタイムロード必要
- → 純粋なファイルサイズ削減効果はなし、**速度改善のみ**

### Phase 9 統合タスク (本 PR scope 外)

- Python スクリプト `voiceCoppy_test/pretokenize/pretokenize_source.py` で
  少女セリフ wav 群を `.npy` 化 (onnxruntime + WavLM ONNX で forward)
- `Assets/Audio/PretokenizedFeatures/*.npy` を Addressable 登録
- 演出側 (BAD ED 等) の API: `service.Convert(loadedFeatures, alpha, out _)`
- `MatchingSetPool.LoadFrom` の NpyReader を query features 用にも reuse

## Architect 整合性チェック

- **新規追加**: **`Architect/10_音声変換システム.md`** を Phase 7 内 (実装着手前) に作成し、
  本 design 全体を「voice_horror アーキテクチャの公式 1 章」として位置付ける
  (Architect/ で他システム (敵 AI、UI 等) と並列に管理)
- **`.claude/rules/architecture.md` SoA / GameManager 規約**: VoiceConversionService は
  `GameManager.Data.VoiceConversion` で参照される想定。`Architect/01_Container.md` に追記
- **MonoBehaviour 単一責務 (`unity-conventions.md`)**: 各クラスは責務 1 文で説明可能 (上記)
- **AssetReference 規約 (`asset-workflow.md`)**: ONNX は Addressable に登録 (Phase 7 後半タスク)
- **テスト分離 (`test-driven.md`)**: コンバート/類似度/プールは EditMode で単体テスト可、
  Sentis Worker / 統合は PlayMode

## 関連

- `designs/specs/voice_conversion/spec.md`
- `designs/specs/voice_conversion/tasks.md`
- `docs/reports/spikes/2026-05-09_knn-vc-sentis-port.md`
- `Architect/` 既存設計と整合 (init-agent で精査)
