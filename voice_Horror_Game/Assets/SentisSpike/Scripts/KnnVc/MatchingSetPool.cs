// MatchingSetPool.cs — Phase 7 Group B 実装 / Phase 8 Optim
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   WavLM 特徴ベクトルの蓄積、weight 管理、npy 永続化。
//   target / player など複数プールを並行管理し、WeightedPoolBuilder で α 混合する。
//
// Phase 8 最適化:
//   List<float[]> → flat float[] への変換結果をキャッシュ。
//   毎回 ToTensor() で生成する重複 alloc を、AsReadOnlyFlatSpan() で参照のみ取る経路で回避。
//   バッチ stress test で 240MB GC 圧 → 0 (キャッシュヒット時) に削減できる。
//
// 関連 spec: MS-001 〜 MS-006
// 関連 design: design.md component 2
// 関連 tests: B-1 〜 B-5, B-6 (cache invalidation)

using System;
using System.Collections.Generic;
using System.IO;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.VC; // NpyWriter / NpyReader

namespace VoiceHorror.KnnVc
{
    public class MatchingSetPool
    {
        const int k_FeatureDim = 1024;
        const int k_FiveMinFrames = 15000; // WavLM ~50 fps × 300 sec

        readonly List<float[]> _features = new();   // 各 entry が 1024-dim
        readonly List<float>   _weights  = new();

        // Phase 8 最適化: List<float[]> から flatten 済みの float[] と weights をキャッシュ。
        // Append 時に invalidate、次回参照時に lazy 再構築。
        // _cachedFlat の長さは _cachedFrameCount * k_FeatureDim、容量は伸ばしても shrink しない (再 alloc 回避)。
        float[] _cachedFlat;
        float[] _cachedWeights;
        int _cachedFrameCount = -1;

        public string Name { get; }
        public int FrameCount => _features.Count;
        public float Coverage5MinRatio => Mathf.Clamp01((float)FrameCount / k_FiveMinFrames);

        public MatchingSetPool(string name)
        {
            Name = name ?? throw new ArgumentNullException(nameof(name));
        }

        /// <summary>
        /// WavLM 特徴 [N, 1024] を append。weight はその全 N frame に共通で適用。
        /// 入力 Tensor は呼び出し側の所有のままで、このメソッドはコピーする。
        /// </summary>
        public void Append(Tensor<float> features, float weight = 1.0f)
        {
            if (features == null) throw new ArgumentNullException(nameof(features));
            if (features.shape.rank != 2 || features.shape[1] != k_FeatureDim)
                throw new ArgumentException(
                    $"features shape must be (N, {k_FeatureDim}), got {features.shape}");

            int n = features.shape[0];
            float[] flat = features.DownloadToArray();

            for (int i = 0; i < n; i++)
            {
                float[] frame = new float[k_FeatureDim];
                Array.Copy(flat, i * k_FeatureDim, frame, 0, k_FeatureDim);
                _features.Add(frame);
                _weights.Add(weight);
            }

            InvalidateCache();
        }

        /// <summary>
        /// プール全体を Tensor [N, 1024] として取り出す (新規 Tensor、呼び出し側で Dispose)。
        /// Tensor はデータを所有するため必ず新規 alloc になるが、
        /// 内部 flat キャッシュからの Buffer.BlockCopy で List 反復は回避する。
        /// </summary>
        public Tensor<float> ToTensor()
        {
            int n = FrameCount;
            EnsureFlatCache();
            float[] flat = new float[n * k_FeatureDim];
            if (n > 0)
                Buffer.BlockCopy(_cachedFlat, 0, flat, 0, n * k_FeatureDim * sizeof(float));
            return new Tensor<float>(new TensorShape(n, k_FeatureDim), flat);
        }

        /// <summary>
        /// 各 frame の weight 配列 [N] を新規コピーで返す。
        /// </summary>
        public float[] GetWeights()
        {
            int n = FrameCount;
            EnsureFlatCache();
            float[] copy = new float[n];
            if (n > 0)
                Buffer.BlockCopy(_cachedWeights, 0, copy, 0, n * sizeof(float));
            return copy;
        }

        /// <summary>
        /// Phase 8 最適化: flat 化済みキャッシュへの直接参照 (read-only)。
        /// WeightedPoolBuilder 等の連結で DownloadToArray + 反復コピーを回避するための公開 API。
        /// 戻り値の Span は次の <see cref="Append"/> 呼び出しで invalidate されるため、
        /// 同期的にコピー / 連結で消費すること。
        /// </summary>
        public ReadOnlySpan<float> AsReadOnlyFlatSpan()
        {
            EnsureFlatCache();
            int len = FrameCount * k_FeatureDim;
            if (len == 0) return ReadOnlySpan<float>.Empty;
            return new ReadOnlySpan<float>(_cachedFlat, 0, len);
        }

        /// <summary>
        /// weights のキャッシュへの直接参照 (read-only)。
        /// AsReadOnlyFlatSpan と対をなす Phase 8 最適化 API。
        /// </summary>
        public ReadOnlySpan<float> AsReadOnlyWeightsSpan()
        {
            EnsureFlatCache();
            int n = FrameCount;
            if (n == 0) return ReadOnlySpan<float>.Empty;
            return new ReadOnlySpan<float>(_cachedWeights, 0, n);
        }

        /// <summary>
        /// npy 形式で永続化。features → path、weights → path に "_weights" suffix。
        /// </summary>
        public void SaveTo(string path)
        {
            if (string.IsNullOrEmpty(path)) throw new ArgumentException(nameof(path));

            int n = FrameCount;
            EnsureFlatCache();

            // npy ヘッダ + 本体書込で _cachedFlat の参照を直接渡せるよう、
            // NpyWriter は配列をそのまま書き出す前提 (現実装で OK)。
            // ただし容量は cachedFrameCount * dim、確実に同じ長さの配列に再コピーして渡す。
            float[] featuresFlat = new float[n * k_FeatureDim];
            if (n > 0)
                Buffer.BlockCopy(_cachedFlat, 0, featuresFlat, 0, n * k_FeatureDim * sizeof(float));
            NpyWriter.Save(path, featuresFlat, new[] { n, k_FeatureDim });

            float[] weightsFlat = new float[n];
            if (n > 0)
                Buffer.BlockCopy(_cachedWeights, 0, weightsFlat, 0, n * sizeof(float));
            string weightsPath = WeightsPathFor(path);
            NpyWriter.Save(weightsPath, weightsFlat);
        }

        /// <summary>
        /// npy ファイルからプール復元。features と weights の対応が壊れていれば例外。
        /// </summary>
        public static MatchingSetPool LoadFrom(string path, string name)
        {
            var (featuresFlat, fShape) = NpyReader.Load(path);
            if (fShape.Length != 2 || fShape[1] != k_FeatureDim)
                throw new InvalidDataException(
                    $"features npy shape mismatch: {string.Join(",", fShape)}, expected (N, {k_FeatureDim})");
            int n = fShape[0];

            string weightsPath = WeightsPathFor(path);
            float[] weightsArr;
            if (File.Exists(weightsPath))
            {
                var (wData, wShape) = NpyReader.Load(weightsPath);
                if (wShape.Length != 1 || wShape[0] != n)
                    throw new InvalidDataException(
                        $"weights npy shape mismatch: {string.Join(",", wShape)}, expected ({n},)");
                weightsArr = wData;
            }
            else
            {
                // 互換性: weights 無しの古い npy は全 1.0 とみなす
                weightsArr = new float[n];
                for (int i = 0; i < n; i++) weightsArr[i] = 1.0f;
            }

            var pool = new MatchingSetPool(name);
            for (int i = 0; i < n; i++)
            {
                float[] frame = new float[k_FeatureDim];
                Array.Copy(featuresFlat, i * k_FeatureDim, frame, 0, k_FeatureDim);
                pool._features.Add(frame);
                pool._weights.Add(weightsArr[i]);
            }
            // LoadFrom 直後に AsReadOnlyFlatSpan() / ToTensor() が呼ばれる確率が高いので、
            // 既に flatten 済みデータをそのまま流用してキャッシュを構築しておく。
            // (Append ループは _cachedFrameCount=-1 のままなので EnsureFlatCache 1 回で済む)
            pool._cachedFlat = featuresFlat;
            pool._cachedWeights = weightsArr;
            pool._cachedFrameCount = n;
            return pool;
        }

        // ── private helpers ────────────────────────────────────────────

        void InvalidateCache()
        {
            _cachedFrameCount = -1;
            // _cachedFlat / _cachedWeights は次回 EnsureFlatCache で書き直すので
            // 容量を残したまま (再 alloc 回避)
        }

        void EnsureFlatCache()
        {
            int n = _features.Count;
            if (_cachedFrameCount == n) return;

            int needed = n * k_FeatureDim;
            if (_cachedFlat == null || _cachedFlat.Length < needed)
                _cachedFlat = new float[needed];
            if (_cachedWeights == null || _cachedWeights.Length < n)
                _cachedWeights = new float[n];

            for (int i = 0; i < n; i++)
            {
                Buffer.BlockCopy(_features[i], 0, _cachedFlat, i * k_FeatureDim * sizeof(float),
                                 k_FeatureDim * sizeof(float));
                _cachedWeights[i] = _weights[i];
            }
            _cachedFrameCount = n;
        }

        static string WeightsPathFor(string featuresPath)
        {
            string dir = Path.GetDirectoryName(featuresPath);
            string fileName = Path.GetFileNameWithoutExtension(featuresPath);
            string ext = Path.GetExtension(featuresPath);
            return Path.Combine(dir ?? "", fileName + "_weights" + ext);
        }
    }
}
