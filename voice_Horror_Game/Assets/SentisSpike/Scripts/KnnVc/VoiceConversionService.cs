// VoiceConversionService.cs — Phase 7 Group F 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   ファサード。WavLM + kNN + HiFiGAN + プール管理 + 類似度判定を統合する。
//   MonoBehaviour として DontDestroyOnLoad の GameObject にアタッチする想定。
//
// Lifecycle:
//   1. Initialize() — Awake or 起動時。モデルロード + プール永続化ロード
//   2. WarmupAsync() — タイトル → ゲーム開始遷移時。cold start 解消
//   3. AccumulatePlayerVoice() — プレイ中、録音ごと
//   4. Convert() — 演出時 (BAD ED 等)
//   5. JudgeEnding() — エンディング直前
//   6. OnDestroy() → Dispose() — ゲーム終了
//
// 関連 spec: VC-001 ~ VC-006, MS-001 ~ MS-006, SS-001 ~ SS-004, SR-001 ~ SR-004
// 関連 design: design.md component 6
// 関連 tests: F-1 〜 F-4 (PlayMode 必要、ユーザー手動実行)

using System;
using System.Collections;
using System.IO;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.VC; // WavWriter / NpyWriter

namespace VoiceHorror.KnnVc
{
    public class VoiceConversionService : MonoBehaviour, IDisposable
    {
        const int k_HiftSampleRate = 16000;

        [Header("Models")]
        [Tooltip("WavLM Large Layer 6 ONNX")]
        [SerializeField] ModelAsset wavlmModel;
        [Tooltip("HiFiGAN for WavLM features")]
        [SerializeField] ModelAsset hifiganModel;

        [Header("ED 判定")]
        [Tooltip("ScriptableObject で hot-fix 可能な ED 閾値")]
        [SerializeField] EdThresholdsAsset edThresholds;

        [Header("Settings")]
        [SerializeField] BackendType backend = BackendType.GPUCompute;
        [SerializeField] int topK = 4;

        [Header("Pool 永続化先 (Application.persistentDataPath からの相対)")]
        [SerializeField] string targetPoolFile = "voice_horror/pools/girl_ghost.npy";
        [SerializeField] string playerPoolFile = "voice_horror/pools/player.npy";

        public MatchingSetPool TargetPool { get; private set; }
        public MatchingSetPool PlayerPool { get; private set; }

        WavLMFeatureExtractor _extractor;
        KnnVcConverter _converter;
        HiFiGANVocoder _vocoder;
        SpeakerSimilarityJudge _judge;
        bool _initialized;
        bool _disposed;

        // ── Public API ─────────────────────────────────────────────────

        /// <summary>
        /// 起動時呼出: ONNX ロード + プール永続化ロード。
        /// 重い処理は WarmupAsync() で分離する。
        /// </summary>
        public void Initialize()
        {
            EnsureNotDisposed();
            if (_initialized) return;
            if (wavlmModel == null) throw new InvalidOperationException("wavlmModel not assigned");
            if (hifiganModel == null) throw new InvalidOperationException("hifiganModel not assigned");

            _extractor = new WavLMFeatureExtractor(wavlmModel, backend);
            _vocoder   = new HiFiGANVocoder(hifiganModel, backend);
            _converter = new KnnVcConverter { TopK = topK };
            _judge     = new SpeakerSimilarityJudge(edThresholds);

            // プール永続化ロード (無ければ空プール)
            TargetPool = LoadOrCreatePool(targetPoolFile, "target");
            PlayerPool = LoadOrCreatePool(playerPoolFile, "player");

            _initialized = true;
        }

        /// <summary>
        /// タイトル → ゲーム開始遷移時に呼ぶ。cold start (~510ms) を loading に隠す。
        /// 1 回完走後はこのコルーチンを再呼び出しする必要なし。
        /// </summary>
        public IEnumerator WarmupAsync()
        {
            EnsureInitialized();
            _extractor.Warmup();
            yield return null;
            _vocoder.Warmup();
            yield return null;
        }

        /// <summary>
        /// プレイヤー録音を WavLM forward して PlayerPool に append する。
        /// 録音 3 秒 で ~0.1-0.3 秒程度 (Phase 6 計測ベース)。
        /// </summary>
        public void AccumulatePlayerVoice(AudioClip clip)
        {
            EnsureInitialized();
            if (clip == null) throw new ArgumentNullException(nameof(clip));

            using var feats = _extractor.ExtractFeatures(clip);
            // WavLM 出力 (1, T_frame, 1024) を (T_frame, 1024) に reshape して append
            float[] flat = feats.DownloadToArray();
            int tFrame = feats.shape[1];
            int dim = feats.shape[2];
            using var reshaped = new Tensor<float>(new TensorShape(tFrame, dim), flat);
            PlayerPool.Append(reshaped);
        }

        /// <summary>
        /// 変換: source の発話内容を target 声色で再生する (alpha=1.0)、
        /// あるいは α 比率で target / player を混合する。
        /// 戻り値の AudioClip は呼び出し側で再生・破棄。
        /// </summary>
        public AudioClip Convert(AudioClip source, float targetWeightAlpha = 1.0f)
        {
            EnsureInitialized();
            if (source == null) throw new ArgumentNullException(nameof(source));

            // Step 1: query 特徴抽出
            using var query2D = ExtractQuery2D(source);

            // Step 2: 重みつき合成プール構築
            var (mergedFeats, mergedWeights) = WeightedPoolBuilder.Build(
                TargetPool, PlayerPool, targetWeightAlpha);

            // Step 3: kNN 変換
            using var converted2D = _converter.Convert(query2D, mergedFeats, mergedWeights);
            mergedFeats.Dispose();

            // Step 4: HiFiGAN vocode (channel-last (1, T_frame, 1024) に reshape)
            int tFrame = converted2D.shape[0];
            int dim = converted2D.shape[1];
            float[] flat = converted2D.DownloadToArray();
            using var feats3D = new Tensor<float>(new TensorShape(1, tFrame, dim), flat);
            float[] audio = _vocoder.VocodeNormalized(feats3D);

            // Step 5: AudioClip 化
            var clip = AudioClip.Create("knn_vc_output", audio.Length, 1, k_HiftSampleRate, stream: false);
            clip.SetData(audio, 0);
            return clip;
        }

        /// <summary>
        /// PlayerPool と TargetPool の話者類似度から ED 判定。
        /// </summary>
        public SpeakerSimilarityJudge.Verdict JudgeEnding()
        {
            EnsureInitialized();
            float sim = _judge.ComputeSimilarity(PlayerPool, TargetPool);
            return _judge.Judge(sim);
        }

        /// <summary>
        /// プール永続化を保存する (シーン遷移 / 終了時に呼ぶ想定)。
        /// </summary>
        public void SavePools()
        {
            EnsureInitialized();
            string targetPath = ResolvePersistentPath(targetPoolFile);
            string playerPath = ResolvePersistentPath(playerPoolFile);
            EnsureDir(targetPath);
            EnsureDir(playerPath);
            TargetPool.SaveTo(targetPath);
            PlayerPool.SaveTo(playerPath);
        }

        // ── IDisposable / lifecycle ────────────────────────────────────

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _extractor?.Dispose();
            _vocoder?.Dispose();
            _extractor = null;
            _vocoder = null;
        }

        void OnDestroy()
        {
            Dispose();
        }

        // ── private helpers ────────────────────────────────────────────

        Tensor<float> ExtractQuery2D(AudioClip source)
        {
            using var feats3D = _extractor.ExtractFeatures(source); // (1, T, 1024)
            int tFrame = feats3D.shape[1];
            int dim = feats3D.shape[2];
            float[] flat = feats3D.DownloadToArray();
            return new Tensor<float>(new TensorShape(tFrame, dim), flat);
        }

        MatchingSetPool LoadOrCreatePool(string relPath, string fallbackName)
        {
            string path = ResolvePersistentPath(relPath);
            if (File.Exists(path))
            {
                try
                {
                    return MatchingSetPool.LoadFrom(path, fallbackName);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[VC] pool load failed ({path}): {ex.Message}. " +
                                   $"Creating empty pool instead.");
                }
            }
            return new MatchingSetPool(fallbackName);
        }

        static string ResolvePersistentPath(string relPath)
        {
            return Path.Combine(Application.persistentDataPath, relPath);
        }

        static void EnsureDir(string filePath)
        {
            string dir = Path.GetDirectoryName(filePath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);
        }

        void EnsureInitialized()
        {
            EnsureNotDisposed();
            if (!_initialized) throw new InvalidOperationException(
                "Initialize() must be called first");
        }

        void EnsureNotDisposed()
        {
            if (_disposed) throw new ObjectDisposedException(nameof(VoiceConversionService));
        }
    }
}
