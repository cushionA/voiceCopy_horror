// KnnVcConverter.cs — Phase 7 Group C 実装
// voice_horror Phase 7 (2026-05-09)
//
// Responsibility:
//   query 特徴 [N1, 1024] と matching set [N2, 1024] (+ オプション weights [N2])
//   から topk kNN マッチした converted features [N1, 1024] を返す。
//
// kNN 計算:
//   - cosine 距離 = 1 - cos(query, ms_i)
//   - 重みつき: distance / weight (weight 大 → 距離が短く見える → 選ばれやすい)
//   - weight = 0 の frame は distance = +∞ にして候補から除外
//   - top-K の特徴ベクトルを単純平均
//
// 関連 spec: VC-001 内部、MS-003 重みつき kNN
// 関連 design: design.md component 3
// 関連 tests: C-1, C-1b (C2/C2b), C-3
//
// 注: matcher.py:21 fast_cosine_dist の C# 移植 (簡易版)。
//     バッチ最適化は将来必要なら検討 (現状は素朴 O(N1 × N2 × dim))。

using System;
using Unity.InferenceEngine;

namespace VoiceHorror.KnnVc
{
    public class KnnVcConverter
    {
        public int TopK { get; set; } = 4;

        /// <summary>
        /// query [N1, 1024] と matching set [N2, 1024] から kNN マッチして
        /// converted features [N1, 1024] を返す。
        ///
        /// weights が指定されていれば各 frame の cosine 距離を 1/weight でスケーリングする。
        /// (weight 大 → 距離短く見える → 選ばれやすい / weight=0 → 候補から完全除外)
        ///
        /// 戻り値の Tensor は呼び出し側で Dispose する責任。
        /// </summary>
        public Tensor<float> Convert(
            Tensor<float> query,
            Tensor<float> matchingSet,
            float[] weights = null)
        {
            if (query == null) throw new ArgumentNullException(nameof(query));
            if (matchingSet == null) throw new ArgumentNullException(nameof(matchingSet));
            if (query.shape.rank != 2)
                throw new ArgumentException($"query must be (N1, dim), got {query.shape}");
            if (matchingSet.shape.rank != 2)
                throw new ArgumentException($"matchingSet must be (N2, dim), got {matchingSet.shape}");
            if (query.shape[1] != matchingSet.shape[1])
                throw new ArgumentException(
                    $"dim mismatch: query={query.shape[1]}, ms={matchingSet.shape[1]}");

            int n1 = query.shape[0];
            int n2 = matchingSet.shape[0];
            int dim = query.shape[1];
            int k = Math.Min(TopK, n2);

            if (weights != null && weights.Length != n2)
                throw new ArgumentException(
                    $"weights length {weights.Length} must match ms count {n2}");

            float[] q = query.DownloadToArray();
            float[] m = matchingSet.DownloadToArray();

            // matching set の各 frame の L2 ノルムを事前計算
            float[] msNorms = new float[n2];
            for (int j = 0; j < n2; j++)
            {
                float ss = 0;
                for (int d = 0; d < dim; d++)
                {
                    float v = m[j * dim + d];
                    ss += v * v;
                }
                msNorms[j] = (float)Math.Sqrt(ss);
            }

            // 結果配列
            float[] outFlat = new float[n1 * dim];

            // 各 query frame について kNN
            int[] topkIdx = new int[k];
            float[] topkDist = new float[k];
            for (int i = 0; i < n1; i++)
            {
                // query[i] のノルム
                float qNorm = 0;
                for (int d = 0; d < dim; d++)
                {
                    float v = q[i * dim + d];
                    qNorm += v * v;
                }
                qNorm = (float)Math.Sqrt(qNorm);
                if (qNorm < 1e-12f) qNorm = 1e-12f;

                // 全 matching set frame との distance を計算 → topk 選別
                for (int t = 0; t < k; t++)
                {
                    topkIdx[t]  = -1;
                    topkDist[t] = float.PositiveInfinity;
                }
                for (int j = 0; j < n2; j++)
                {
                    // weight=0 → 候補から除外
                    float w = (weights != null) ? weights[j] : 1.0f;
                    if (w <= 0f) continue;

                    float dot = 0;
                    for (int d = 0; d < dim; d++)
                        dot += q[i * dim + d] * m[j * dim + d];
                    float cos = dot / (qNorm * Math.Max(msNorms[j], 1e-12f));
                    float dist = 1f - cos;
                    // 重みつき距離: 1/weight でスケール (大きい weight ほど短く見える)
                    dist /= w;

                    // topk insertion
                    int worstIdx = 0;
                    for (int t = 1; t < k; t++)
                        if (topkDist[t] > topkDist[worstIdx]) worstIdx = t;
                    if (dist < topkDist[worstIdx])
                    {
                        topkDist[worstIdx] = dist;
                        topkIdx[worstIdx]  = j;
                    }
                }

                // topk の特徴ベクトルを平均して output に書く
                int validCount = 0;
                for (int d = 0; d < dim; d++) outFlat[i * dim + d] = 0f;
                for (int t = 0; t < k; t++)
                {
                    if (topkIdx[t] < 0) continue;
                    validCount++;
                    int j = topkIdx[t];
                    for (int d = 0; d < dim; d++)
                        outFlat[i * dim + d] += m[j * dim + d];
                }
                if (validCount > 0)
                    for (int d = 0; d < dim; d++)
                        outFlat[i * dim + d] /= validCount;
            }

            return new Tensor<float>(new TensorShape(n1, dim), outFlat);
        }
    }
}
