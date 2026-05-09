// WavLMFeatureExtractor.cs — Phase 7 Group A 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   16kHz mono audio (float[] or AudioClip) → WavLM Layer 6 features [1, T_frame, 1024]
//
// 設計:
//   - Sentis Worker を内部に保持・再利用
//   - AudioClip は内部で 16kHz mono に変換 (再サンプル + ダウンミックス)
//   - Warmup() で cold start (~510ms) を loading 画面に隠せる
//   - IDisposable で GPU リソース確実解放
//
// 関連 spec: VC-001, VC-003, VC-005, VC-006, SR-002, SR-003, SR-004
// 関連 design: design.md component 1
// 関連 tests: A-1 ~ A-4

using System;
using Unity.InferenceEngine;
using Unity.Profiling;
using UnityEngine;

namespace VoiceHorror.KnnVc
{
    /// <summary>
    /// Sentis 経由で WavLM Large の Layer 6 特徴を抽出する。
    /// Worker は内部保持し、複数回 forward を再利用する。
    /// 使用後は必ず Dispose() を呼ぶ (using 推奨)。
    /// </summary>
    public class WavLMFeatureExtractor : IDisposable
    {
        const int k_SampleRate16k = 16000;
        const int k_WarmupAudioSamples = 80000; // 5秒 @ 16kHz
        // WavLM の receptive field を満たすための最小入力長 (0.1 秒 = 1600 samples)
        // これ未満は zero-pad して安全に forward させる (spec.md SR-* / 設計の堅牢化)
        const int k_MinAudioSamples = 1600;

        // Sentis GPU compute dispatch limit 対策のチャンクサイズ。
        // WavLM 第 1 conv (stride=5) の出力長が 65,535 を超えると thread group 上限を超え
        // 特徴量が破損する (Pool / CopyOps の "Exceeded safe compute dispatch group count limit" 警告)。
        // 安全マージンを取って 10 秒 = 160,000 samples → 第1 conv 出力 32,000 を上限とする。
        // PyTorch では発生しないが Sentis の compute shader では必須の制限。
        const int k_MaxChunkSamples = 160000; // 10 秒 @ 16kHz
        // WavLM の出力 frame rate (16kHz / 320 stride = 50 fps)
        const int k_StridePerFrame = 320;

        static readonly ProfilerMarker s_Marker = new ProfilerMarker("VC.Extract");

        readonly Worker _worker;
        readonly BackendType _backend;
        bool _disposed;

        public WavLMFeatureExtractor(ModelAsset wavlmModel, BackendType backend = BackendType.GPUCompute)
        {
            if (wavlmModel == null)
                throw new ArgumentNullException(nameof(wavlmModel), "WavLM ModelAsset is required");

            _backend = backend;
            var model = ModelLoader.Load(wavlmModel);
            _worker = new Worker(model, backend);
        }

        /// <summary>
        /// 16kHz mono float[] の audio を WavLM forward して特徴 [1, T_frame, 1024] を返す。
        /// 戻り値の Tensor は呼び出し側で Dispose する責任。
        /// </summary>
        public Tensor<float> ExtractFeatures(float[] audio16kMono)
        {
            EnsureNotDisposed();
            if (audio16kMono == null || audio16kMono.Length == 0)
                throw new ArgumentException("audio is null or empty", nameof(audio16kMono));

            using (s_Marker.Auto())
            {
                // WavLM receptive field 確保のため、短すぎる入力は zero-pad
                if (audio16kMono.Length < k_MinAudioSamples)
                {
                    var padded = new float[k_MinAudioSamples];
                    Array.Copy(audio16kMono, 0, padded, 0, audio16kMono.Length);
                    return ForwardSingle(padded);
                }

                if (audio16kMono.Length <= k_MaxChunkSamples)
                    return ForwardSingle(audio16kMono);

                return ForwardChunked(audio16kMono);
            }
        }

        /// <summary>
        /// 単一チャンクを forward。output 所有権は呼び出し側。
        /// </summary>
        Tensor<float> ForwardSingle(float[] audio)
        {
            using var input = new Tensor<float>(new TensorShape(1, audio.Length), audio);
            _worker.Schedule(input);
            return (_worker.PeekOutput() as Tensor<float>).ReadbackAndClone();
        }

        /// <summary>
        /// 長尺 audio を k_MaxChunkSamples 単位で分割して forward し、
        /// 出力 [1, T_frame, dim] を T_frame 軸で連結する。
        ///
        /// 注: WavLM transformer はチャンク内で global attention するため
        /// チャンク境界の数 frame は連続 forward と微妙に異なる。
        /// kNN-VC は per-frame マッチングなので品質影響は軽微。
        /// </summary>
        Tensor<float> ForwardChunked(float[] audio)
        {
            int totalSamples = audio.Length;
            var chunkOutputs = new System.Collections.Generic.List<float[]>();
            int dim = -1;
            int totalFrames = 0;

            int pos = 0;
            while (pos < totalSamples)
            {
                int remaining = totalSamples - pos;
                int chunkLen = Math.Min(k_MaxChunkSamples, remaining);

                // 末尾の極端に短いチャンク (< k_MinAudioSamples) は pad しつつ
                // 出力 frame 数を「実 audio 長から期待される frame 数」に切り詰める。
                bool padded = chunkLen < k_MinAudioSamples;
                float[] chunkAudio = new float[padded ? k_MinAudioSamples : chunkLen];
                Array.Copy(audio, pos, chunkAudio, 0, chunkLen);

                using var chunkOut = ForwardSingle(chunkAudio);
                if (dim < 0) dim = chunkOut.shape[2];
                int chunkFrames = chunkOut.shape[1];

                int validFrames = padded
                    ? Math.Min(chunkFrames, Math.Max(1, chunkLen / k_StridePerFrame))
                    : chunkFrames;

                float[] flat = chunkOut.DownloadToArray();
                if (validFrames == chunkFrames)
                {
                    chunkOutputs.Add(flat);
                }
                else
                {
                    var trimmed = new float[validFrames * dim];
                    Array.Copy(flat, 0, trimmed, 0, trimmed.Length);
                    chunkOutputs.Add(trimmed);
                }
                totalFrames += validFrames;
                pos += chunkLen;
            }

            // T 軸で連結
            float[] merged = new float[totalFrames * dim];
            int writeOffset = 0;
            foreach (var c in chunkOutputs)
            {
                Array.Copy(c, 0, merged, writeOffset, c.Length);
                writeOffset += c.Length;
            }

            return new Tensor<float>(new TensorShape(1, totalFrames, dim), merged);
        }

        /// <summary>
        /// AudioClip を内部で 16kHz mono に変換してから特徴抽出。
        /// </summary>
        public Tensor<float> ExtractFeatures(AudioClip clip)
        {
            EnsureNotDisposed();
            if (clip == null)
                throw new ArgumentNullException(nameof(clip));

            float[] audio16k = ClipTo16kMono(clip);
            return ExtractFeatures(audio16k);
        }

        /// <summary>
        /// Cold start (~510ms) を解消するため、ゲーム起動 / シーン遷移時に
        /// dummy 5sec audio で 1 回 forward を実行する。
        /// </summary>
        public void Warmup()
        {
            EnsureNotDisposed();
            float[] dummyAudio = new float[k_WarmupAudioSamples];
            // 全ゼロ audio で OK (warmup は CUDA カーネル JIT が目的)
            using var output = ExtractFeatures(dummyAudio);
            // output の中身は使わず、Warmup の副作用 (kernel コンパイル) のみが目的
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _worker?.Dispose();
        }

        // ── Private helpers ───────────────────────────────────────────

        void EnsureNotDisposed()
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(WavLMFeatureExtractor));
        }

        /// <summary>
        /// AudioClip → 16kHz mono float[] に変換。
        /// stereo → mono は単純平均、リサンプリングは linear interpolation。
        /// </summary>
        static float[] ClipTo16kMono(AudioClip clip)
        {
            float[] raw = new float[clip.samples * clip.channels];
            clip.GetData(raw, 0);

            // Mono 変換 (stereo → 平均)
            float[] mono = ToMono(raw, clip.channels);

            // 16kHz リサンプリング
            if (clip.frequency == k_SampleRate16k)
                return mono;

            return Resample(mono, clip.frequency, k_SampleRate16k);
        }

        static float[] ToMono(float[] interleaved, int channels)
        {
            if (channels == 1) return interleaved;
            int n = interleaved.Length / channels;
            float[] mono = new float[n];
            for (int i = 0; i < n; i++)
            {
                float sum = 0f;
                for (int c = 0; c < channels; c++)
                    sum += interleaved[i * channels + c];
                mono[i] = sum / channels;
            }
            return mono;
        }

        /// <summary>
        /// Linear interpolation resampler. WavLM は 16kHz mono を期待。
        /// 高品質再サンプリング (Lanczos 等) は将来必要なら検討。
        /// </summary>
        static float[] Resample(float[] src, int srcSr, int dstSr)
        {
            if (srcSr == dstSr) return src;
            double ratio = (double)dstSr / srcSr;
            int dstLen = (int)(src.Length * ratio);
            float[] dst = new float[dstLen];
            for (int i = 0; i < dstLen; i++)
            {
                double srcIdx = i / ratio;
                int idx0 = (int)srcIdx;
                int idx1 = Math.Min(idx0 + 1, src.Length - 1);
                float frac = (float)(srcIdx - idx0);
                dst[i] = src[idx0] * (1f - frac) + src[idx1] * frac;
            }
            return dst;
        }
    }
}
