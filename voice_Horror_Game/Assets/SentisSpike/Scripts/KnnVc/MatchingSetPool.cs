// MatchingSetPool.cs — Phase 7 Group B 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   WavLM 特徴ベクトルの蓄積、weight 管理、npy 永続化。
//   target / player など複数プールを並行管理し、WeightedPoolBuilder で α 混合する。
//
// 関連 spec: MS-001 〜 MS-006
// 関連 design: design.md component 2
// 関連 tests: B-1 〜 B-5

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
        }

        /// <summary>
        /// プール全体を Tensor [N, 1024] として取り出す (新規 Tensor、呼び出し側で Dispose)。
        /// </summary>
        public Tensor<float> ToTensor()
        {
            int n = FrameCount;
            float[] flat = new float[n * k_FeatureDim];
            for (int i = 0; i < n; i++)
                Array.Copy(_features[i], 0, flat, i * k_FeatureDim, k_FeatureDim);
            return new Tensor<float>(new TensorShape(n, k_FeatureDim), flat);
        }

        /// <summary>
        /// 各 frame の weight 配列 [N] を新規コピーで返す。
        /// </summary>
        public float[] GetWeights()
        {
            return _weights.ToArray();
        }

        /// <summary>
        /// npy 形式で永続化。features → path、weights → path に "_weights" suffix。
        /// </summary>
        public void SaveTo(string path)
        {
            if (string.IsNullOrEmpty(path)) throw new ArgumentException(nameof(path));

            int n = FrameCount;
            float[] featuresFlat = new float[n * k_FeatureDim];
            for (int i = 0; i < n; i++)
                Array.Copy(_features[i], 0, featuresFlat, i * k_FeatureDim, k_FeatureDim);
            NpyWriter.Save(path, featuresFlat, new[] { n, k_FeatureDim });

            string weightsPath = WeightsPathFor(path);
            NpyWriter.Save(weightsPath, _weights.ToArray());
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
            return pool;
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
