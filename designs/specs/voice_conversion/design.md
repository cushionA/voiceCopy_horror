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

    /// features [N, 1024] を append
    public void Append(Tensor<float> features);

    /// 既存プールから新規プールを作成 (α 混合用)
    public static MatchingSetPool MixWeighted(MatchingSetPool a, MatchingSetPool b, float alpha);

    /// プール全体を flat float[] (N * 1024) で取り出す
    public Tensor<float> ToTensor();

    /// 永続化 (npy フォーマット推奨、独自バイナリでも可)
    public void SaveTo(string filePath);
    public static MatchingSetPool LoadFrom(string filePath, string name);
}
```

**実装ポイント**:
- 内部表現: `List<float[]>` (各 entry が 1024-dim、append 効率)
- `ToTensor()` で連結し Sentis Tensor 化 (キャッシュ可)
- 永続化先: `Application.persistentDataPath/voice_horror/pools/{name}.bin`
- 5 分相当 = WavLM ~50fps × 300sec ≈ 15000 frames

### 3. `KnnVcConverter`

**責務**: query 特徴 + matching set → kNN 検索 → matched features

**配置**: `Scripts/KnnVc/KnnVcConverter.cs`

**Public API**:
```csharp
public class KnnVcConverter
{
    public int TopK { get; set; } = 4;       // kNN の k 値

    /// query [N1, 1024] と matching set [N2, 1024] から converted [N1, 1024]
    public Tensor<float> Convert(Tensor<float> query, Tensor<float> matchingSet);
}
```

**実装ポイント**:
- ピュア kNN (Sentis 不要、CPU/SIMD でも可)
- matcher.py:21 `fast_cosine_dist` を C# に移植
- topk=4 で平均、最終 [N1, 1024]
- 大規模 matching set (>5000 frames) の場合 GPU で torch.cdist 相当を使うか検討

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
public class SpeakerSimilarityJudge
{
    [SerializeField] float k_HighThreshold = 0.85f;  // BAD ED「奪われる」
    [SerializeField] float k_MidLow        = 0.40f;
    [SerializeField] float k_MidHigh       = 0.70f;  // 中域 = 「声変えて攻略」分岐

    public enum Verdict { BadCaptured, BadVoiceChange, Good }

    /// 2 プールの平均特徴のコサイン類似度を返す
    public float ComputeSimilarity(MatchingSetPool a, MatchingSetPool b);

    /// 類似度から ED 判定
    public Verdict Judge(float similarity);
}
```

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

    [Header("Pools")]
    public MatchingSetPool TargetPool { get; private set; }   // 少女声 (Phase 9 収録音)
    public MatchingSetPool PlayerPool { get; private set; }   // ゲーム中蓄積

    /// 起動時呼出: モデルロード + warmup + プール永続化ロード
    public void Initialize();

    /// プレイヤー録音を AudioClip 単位で蓄積 (B-2 MS-002)
    public void AccumulatePlayerVoice(AudioClip clip);

    /// 変換: source の発話内容を target 声色で再生
    /// alpha: 1.0 = 純 target 声 / 0.0 = 純 player 声 / 0.5 = 混合 (B-1 G-2)
    public AudioClip Convert(AudioClip source, float targetWeightAlpha = 1.0f);

    /// ED 判定 (B-3 SS-002)
    public SpeakerSimilarityJudge.Verdict JudgeEnding();

    /// 終了時: Worker / プール永続化
    public void Shutdown();
}
```

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

## Architect 整合性チェック

- **`.claude/rules/architecture.md` SoA / GameManager 規約**: VoiceConversionService は GameManager.Data.VoiceConversion で参照される想定 (Architect/01_Container.md に追記必要)
- **MonoBehaviour 単一責務 (`unity-conventions.md`)**: 各クラスは責務 1 文で説明可能 (上記)
- **AssetReference 規約 (`asset-workflow.md`)**: ONNX は Addressable に登録 (Phase 7 タスク)
- **テスト分離 (`test-driven.md`)**: コンバート/類似度/プールは EditMode で単体テスト可、Sentis Worker は PlayMode

## 関連

- `designs/specs/voice_conversion/spec.md`
- `designs/specs/voice_conversion/tasks.md`
- `docs/reports/spikes/2026-05-09_knn-vc-sentis-port.md`
- `Architect/` 既存設計と整合 (init-agent で精査)
