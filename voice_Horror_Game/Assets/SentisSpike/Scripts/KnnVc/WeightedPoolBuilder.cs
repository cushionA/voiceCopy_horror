// WeightedPoolBuilder.cs — Phase 7 Group B 実装 / Phase 8 Optim
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
// Phase 8 最適化:
//   旧: a.ToTensor() + b.ToTensor() でそれぞれ Tensor 確保 + DownloadToArray
//   新: AsReadOnlyFlatSpan() で float[] 参照を直接取得 → 連結用 float[] に Buffer.BlockCopy
//   alloc は連結後の new float[] と new Tensor<float> の 2 つだけになる。
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
        const int k_FeatureDim = 1024;

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

            // 早期 return: α=1.0 なら b 完全無視、α=0.0 なら a 完全無視
            // → メモリ + 後続 kNN コストを削減 (narrative 序盤 α=1.0 が頻出)
            // 元の実装でも weight=0 frame は KnnVcConverter で除外されるため結果は同等
            if (alpha >= 1f)
            {
                var weightsA = new float[nA];
                for (int i = 0; i < nA; i++) weightsA[i] = 1f;
                return (a.ToTensor(), weightsA);
            }
            if (alpha <= 0f)
            {
                var weightsB = new float[nB];
                for (int i = 0; i < nB; i++) weightsB[i] = 1f;
                return (b.ToTensor(), weightsB);
            }

            int nTotal = nA + nB;

            // Phase 8 最適化: ToTensor + DownloadToArray の二重 alloc を避けるため、
            // pool 内部の flatten 済みキャッシュへの ReadOnlySpan を直接使って連結。
            ReadOnlySpan<float> aFlat = a.AsReadOnlyFlatSpan();
            ReadOnlySpan<float> bFlat = b.AsReadOnlyFlatSpan();

            float[] mergedFlat = new float[nTotal * k_FeatureDim];
            var mergedSpan = new Span<float>(mergedFlat);
            aFlat.CopyTo(mergedSpan);
            bFlat.CopyTo(mergedSpan.Slice(aFlat.Length));
            var mergedTensor = new Tensor<float>(new TensorShape(nTotal, k_FeatureDim), mergedFlat);

            // weights 構築
            float[] weights = new float[nTotal];
            for (int i = 0; i < nA; i++) weights[i] = alpha;
            for (int i = 0; i < nB; i++) weights[nA + i] = 1f - alpha;

            return (mergedTensor, weights);
        }
    }
}
