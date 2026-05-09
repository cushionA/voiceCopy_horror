// SpeakerSimilarityJudge.cs — Phase 7 Group E 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   2 つの MatchingSetPool 間の話者類似度 (cosine sim) 計算と ED 分岐判定。
//   WavLM 特徴を流用、追加モデル不要 (1 モデル 2 役)。
//
// Cosine 類似度の値域:
//   - 生 cos は [-1, 1] だが、voice_horror では max(0, cos) で [0, 1] にクランプ
//   - 「類似してない」=0 で直感的、反対方向ベクトル = 無関係扱い
//
// 関連 spec: SS-001 〜 SS-004
// 関連 design: design.md component 5
// 関連 tests: E-1, E-2, E-3

using System;
using Unity.InferenceEngine;

namespace VoiceHorror.KnnVc
{
    public class SpeakerSimilarityJudge
    {
        public enum Verdict { BadCaptured, BadVoiceChange, Good }

        public EdThresholdsAsset Thresholds { get; set; }

        public SpeakerSimilarityJudge(EdThresholdsAsset thresholds = null)
        {
            Thresholds = thresholds;
        }

        /// <summary>
        /// 2 プールの平均特徴ベクトル間のコサイン類似度を [0, 1] で返す。
        /// (max(0, cos) でクランプ、反対方向は無関係扱い)
        /// </summary>
        public float ComputeSimilarity(MatchingSetPool a, MatchingSetPool b)
        {
            if (a == null) throw new ArgumentNullException(nameof(a));
            if (b == null) throw new ArgumentNullException(nameof(b));
            if (a.FrameCount == 0)
                throw new InvalidOperationException("pool a is empty");
            if (b.FrameCount == 0)
                throw new InvalidOperationException("pool b is empty");

            float[] meanA = ComputeMeanFeature(a);
            float[] meanB = ComputeMeanFeature(b);

            float dot = 0, normA = 0, normB = 0;
            for (int d = 0; d < meanA.Length; d++)
            {
                dot   += meanA[d] * meanB[d];
                normA += meanA[d] * meanA[d];
                normB += meanB[d] * meanB[d];
            }
            normA = (float)Math.Sqrt(normA);
            normB = (float)Math.Sqrt(normB);
            if (normA < 1e-12f || normB < 1e-12f) return 0f;

            float cos = dot / (normA * normB);
            // [0, 1] クランプ (反対方向 = 無関係扱い)
            return cos < 0f ? 0f : cos;
        }

        /// <summary>
        /// 類似度から ED 判定 (spec.md SS-002 の 3 段階)。
        ///
        /// sim > HighThreshold      → BadCaptured (カラダを奪われる)
        /// MidLow < sim ≤ MidHigh  → BadVoiceChange (声色変えて電話切れ)
        /// sim ≤ MidLow             → Good (脱出)
        ///
        /// (MidHigh, HighThreshold] の中間域は **未定義**: HighThreshold > MidHigh の
        /// 設定では存在しうる。挙動として BadCaptured 寄りに倒す (高類似側に保守的)。
        ///
        /// 推奨設定: MidLow < MidHigh ≤ HighThreshold (Phase 8 キャリブレーション後)
        /// </summary>
        public Verdict Judge(float similarity)
        {
            if (Thresholds == null)
                throw new InvalidOperationException(
                    "Thresholds is null. Inject EdThresholdsAsset before calling Judge().");

            if (similarity > Thresholds.HighThreshold) return Verdict.BadCaptured;
            if (similarity > Thresholds.MidHigh)
                return Verdict.BadCaptured; // MidHigh < sim ≤ High の中間も「奪われ寄り」(保守側)
            if (similarity > Thresholds.MidLow)        return Verdict.BadVoiceChange;
            return Verdict.Good;
        }

        // ── private helpers ───────────────────────────────────────────

        static float[] ComputeMeanFeature(MatchingSetPool pool)
        {
            using var t = pool.ToTensor();
            int n = t.shape[0];
            int dim = t.shape[1];
            float[] flat = t.DownloadToArray();
            float[] mean = new float[dim];
            for (int i = 0; i < n; i++)
                for (int d = 0; d < dim; d++)
                    mean[d] += flat[i * dim + d];
            for (int d = 0; d < dim; d++) mean[d] /= n;
            return mean;
        }
    }
}
