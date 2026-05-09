// WeightedPoolBuilder.cs — Phase 7 Group B 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   2 つの MatchingSetPool (a, b) を α 比率で重みつき混合した
//   合成 features [N_total, 1024] と weights [N_total] を構築する。
//   KnnVcConverter に渡して narrative の「混ざっていく」演出を実現する。
//
// 重みつき kNN の意味:
//   - α=1.0 で a 部分 weight=1.0、b 部分 weight=0.0 → b 完全無視
//   - α=0.0 で a 部分 weight=0.0、b 部分 weight=1.0 → a 完全無視
//   - α=0.5 で全 frame weight=0.5 (均等)
//   - 任意 α で a 部分=α、b 部分=1-α
//
// 関連 spec: MS-003
// 関連 design: design.md component 2
// 関連 tests: B-3 (B-3, B-3b, B-3c, B-3d)

using System;
using Unity.InferenceEngine;

namespace VoiceHorror.KnnVc
{
    public static class WeightedPoolBuilder
    {
        /// <summary>
        /// 2 プールを連結して合成 features と weights を返す。
        /// features: a の全 frames + b の全 frames を順に並べた [N_total, 1024] Tensor
        /// weights: 前半 N_a frame は α、後半 N_b frame は 1-α
        ///
        /// 戻り値の features Tensor は呼び出し側で Dispose する責任。
        /// </summary>
        public static (Tensor<float> features, float[] weights) Build(
            MatchingSetPool a, MatchingSetPool b, float alpha)
        {
            if (a == null) throw new ArgumentNullException(nameof(a));
            if (b == null) throw new ArgumentNullException(nameof(b));
            if (alpha < 0f || alpha > 1f)
                throw new ArgumentOutOfRangeException(
                    nameof(alpha), $"alpha must be in [0, 1], got {alpha}");

            int nA = a.FrameCount;
            int nB = b.FrameCount;
            int nTotal = nA + nB;

            // features 連結
            using var ta = a.ToTensor();
            using var tb = b.ToTensor();
            float[] aFlat = ta.DownloadToArray();
            float[] bFlat = tb.DownloadToArray();
            int dim = ta.shape[1]; // 1024 想定

            float[] mergedFlat = new float[nTotal * dim];
            Array.Copy(aFlat, 0, mergedFlat, 0, aFlat.Length);
            Array.Copy(bFlat, 0, mergedFlat, aFlat.Length, bFlat.Length);
            var mergedTensor = new Tensor<float>(new TensorShape(nTotal, dim), mergedFlat);

            // weights 構築
            float[] weights = new float[nTotal];
            for (int i = 0; i < nA; i++) weights[i] = alpha;
            for (int i = 0; i < nB; i++) weights[nA + i] = 1f - alpha;

            return (mergedTensor, weights);
        }
    }
}
