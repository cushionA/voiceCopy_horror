// HiFiGANVocoder.cs — Phase 7 Group D 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   converted features [1, T_frame, 1024] (channel-last) → audio waveform [T_audio]
//
// HiFiGAN 入力の罠:
//   knn-vc/hifigan/models.py:103 docstring:
//     "x as (bs, seq_len, dim), regular hifi assumes input of shape (bs, n_mels, seq_len)"
//   → HiFiGAN は channel-last (B, T_frame, dim) を期待。
//      channel-first (B, dim, T_frame) で投入すると Linear shape mismatch でクラッシュ。
//
// Sentis 出力 shape: (1, 1, T_audio)。flatten して float[T_audio] で返す。
//
// 関連 spec: VC-001, VC-003, VC-004 (peak 正規化)
// 関連 design: design.md component 4
// 関連 tests: D-1, D-2, D-3

using System;
using Unity.InferenceEngine;

namespace VoiceHorror.KnnVc
{
    public class HiFiGANVocoder : IDisposable
    {
        const int k_FeatureDim = 1024;
        const float k_PeakNormalizeTarget = 0.95f;
        const int k_WarmupFrames = 250; // 5秒分

        readonly Worker _worker;
        bool _disposed;

        public HiFiGANVocoder(ModelAsset hifiganModel, BackendType backend = BackendType.GPUCompute)
        {
            if (hifiganModel == null)
                throw new ArgumentNullException(nameof(hifiganModel));

            var model = ModelLoader.Load(hifiganModel);
            _worker = new Worker(model, backend);
        }

        /// <summary>
        /// features (1, T_frame, 1024) → audio float[T_audio]
        /// peak 正規化なし、生 HiFiGAN 出力。
        /// </summary>
        public float[] Vocode(Tensor<float> features)
        {
            EnsureNotDisposed();
            if (features == null) throw new ArgumentNullException(nameof(features));
            if (features.shape.rank != 3)
                throw new ArgumentException(
                    $"features must be (B, T_frame, dim), got rank {features.shape.rank}");
            if (features.shape[2] != k_FeatureDim)
                throw new ArgumentException(
                    $"features last dim must be {k_FeatureDim} (channel-last), " +
                    $"got shape {features.shape}. " +
                    $"(HiFiGAN expects (B, T_frame, dim), not (B, dim, T_frame))");

            _worker.Schedule(features);
            using var output = (_worker.PeekOutput() as Tensor<float>).ReadbackAndClone();

            // output shape (1, 1, T_audio) または (1, T_audio) → flatten
            float[] audio = output.DownloadToArray();
            return audio;
        }

        /// <summary>
        /// peak が 1.0 を超えていたら 0.95 にスケール、超えていなければ raw のまま返す。
        /// 16bit PCM 保存時のクリッピング防止。
        /// </summary>
        public float[] VocodeNormalized(Tensor<float> features)
        {
            float[] audio = Vocode(features);
            float peak = 0;
            for (int i = 0; i < audio.Length; i++)
            {
                float v = audio[i] >= 0 ? audio[i] : -audio[i];
                if (v > peak) peak = v;
            }
            if (peak > 1.0f)
            {
                float scale = k_PeakNormalizeTarget / peak;
                for (int i = 0; i < audio.Length; i++)
                    audio[i] *= scale;
            }
            return audio;
        }

        /// <summary>
        /// Cold start 解消用 warmup。dummy features で 1 回 forward。
        /// </summary>
        public void Warmup()
        {
            EnsureNotDisposed();
            float[] dummy = new float[k_WarmupFrames * k_FeatureDim];
            using var feats = new Tensor<float>(
                new TensorShape(1, k_WarmupFrames, k_FeatureDim), dummy);
            float[] _ = Vocode(feats);
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _worker?.Dispose();
        }

        void EnsureNotDisposed()
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(HiFiGANVocoder));
        }
    }
}
