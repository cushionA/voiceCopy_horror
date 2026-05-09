// KnnVcConverter.cs — Phase 7 Group C / Phase 8 GPU 化
// voice_horror Phase 7-8 (2026-05-09)
//
// Responsibility:
//   query 特徴 [N1, 1024] と matching set [N2, 1024] (+ オプション weights [N2])
//   から topk kNN マッチした converted features [N1, 1024] を返す。
//
// Phase 8 リファクタ: kNN 距離計算を Sentis MatMul (GPU) に載せる
//   - 旧実装 (Phase 7 純 C# loop): 1700×1500×1024 で ~12 秒 (~207 MFLOPS)
//   - 新実装 (Sentis MatMul): query / ms 正規化 + cosine sim を GPU で一発計算
//   - top-K 選別 + 平均だけ CPU で実施 (距離行列 [N1, N2] 程度のサイズ)
//
// 数学:
//   q_norm   = q  / |q|     (per row L2 正規化)
//   ms_norm  = ms / |ms|
//   sim      = q_norm @ ms_norm.T            // [N1, N2]
//   cos_dist = 1 - sim                        // [N1, N2]
//   weighted = cos_dist / weight (CPU 後処理、weight=0 は除外)
//   output[i] = mean(ms[topK_indices[i]])    // CPU
//
// 関連 spec: VC-001 内部、MS-003 重みつき kNN
// 関連 design: design.md component 3
// 関連 tests: C-1, C-1b (C2/C2b), C-3

using System;
using Unity.InferenceEngine;
using Unity.Profiling;
using UnityEngine;

namespace VoiceHorror.KnnVc
{
    public class KnnVcConverter : IDisposable
    {
        static readonly ProfilerMarker s_MarkerTotal   = new ProfilerMarker("VC.kNN");
        static readonly ProfilerMarker s_MarkerGpuDist = new ProfilerMarker("VC.kNN.GpuDist");
        static readonly ProfilerMarker s_MarkerTopK    = new ProfilerMarker("VC.kNN.TopK");
        static readonly ProfilerMarker s_MarkerAverage = new ProfilerMarker("VC.kNN.Average");

        public int TopK { get; set; } = 4;
        public BackendType Backend { get; set; } = BackendType.GPUCompute;

        // Sentis worker は (n1, n2, dim) shape でモデルが固定されるため、
        // shape が変わったら作り直す。最初の Convert() 呼出時に lazy 生成。
        Worker _worker;
        int _cachedN1 = -1;
        int _cachedN2 = -1;
        int _cachedDim = -1;
        bool _disposed;

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
            EnsureNotDisposed();
            if (query == null) throw new ArgumentNullException(nameof(query));
            if (matchingSet == null) throw new ArgumentNullException(nameof(matchingSet));
            if (query.shape.rank != 2)
                throw new ArgumentException($"query must be (N1, dim), got {query.shape}");
            if (matchingSet.shape.rank != 2)
                throw new ArgumentException($"matchingSet must be (N2, dim), got {matchingSet.shape}");
            if (query.shape[1] != matchingSet.shape[1])
                throw new ArgumentException(
                    $"dim mismatch: query={query.shape[1]}, ms={matchingSet.shape[1]}");

            using var _ = s_MarkerTotal.Auto();

            int n1 = query.shape[0];
            int n2 = matchingSet.shape[0];
            int dim = query.shape[1];
            int k = Math.Min(TopK, n2);

            if (weights != null && weights.Length != n2)
                throw new ArgumentException(
                    $"weights length {weights.Length} must match ms count {n2}");

            // Step 1: GPU で cosine 距離行列 [N1, N2] を計算
            float[] distFlat;
            using (s_MarkerGpuDist.Auto())
            {
                EnsureModel(n1, n2, dim);
                _worker.SetInput(0, query);
                _worker.SetInput(1, matchingSet);
                _worker.Schedule();
                using var distTensor = (_worker.PeekOutput() as Tensor<float>).ReadbackAndClone();
                distFlat = distTensor.DownloadToArray();
            }

            // ms は CPU 側で平均計算に必要なので 1 回だけ download
            float[] ms = matchingSet.DownloadToArray();

            // Step 2: 各 query row について top-K (CPU、重みつき除外もここで)
            float[] outFlat = new float[n1 * dim];
            int[] topkIdx = new int[k];
            float[] topkDist = new float[k];

            using (s_MarkerTopK.Auto())
            {
                using (s_MarkerAverage.Auto())
                {
                    for (int i = 0; i < n1; i++)
                    {
                        // top-K 初期化
                        for (int t = 0; t < k; t++)
                        {
                            topkIdx[t] = -1;
                            topkDist[t] = float.PositiveInfinity;
                        }

                        // dist[i, j] を線形スキャン
                        int rowBase = i * n2;
                        for (int j = 0; j < n2; j++)
                        {
                            float w = (weights != null) ? weights[j] : 1.0f;
                            if (w <= 0f) continue; // weight=0 は完全除外

                            float dist = distFlat[rowBase + j];
                            if (weights != null) dist /= w;

                            // 最悪要素を見つけて入替 (k=4 想定なので線形 OK)
                            int worstIdx = 0;
                            for (int t = 1; t < k; t++)
                                if (topkDist[t] > topkDist[worstIdx]) worstIdx = t;
                            if (dist < topkDist[worstIdx])
                            {
                                topkDist[worstIdx] = dist;
                                topkIdx[worstIdx] = j;
                            }
                        }

                        // top-K 平均
                        int validCount = 0;
                        int outBase = i * dim;
                        for (int d = 0; d < dim; d++) outFlat[outBase + d] = 0f;
                        for (int t = 0; t < k; t++)
                        {
                            if (topkIdx[t] < 0) continue;
                            validCount++;
                            int msBase = topkIdx[t] * dim;
                            for (int d = 0; d < dim; d++)
                                outFlat[outBase + d] += ms[msBase + d];
                        }
                        if (validCount > 0)
                        {
                            float inv = 1f / validCount;
                            for (int d = 0; d < dim; d++)
                                outFlat[outBase + d] *= inv;
                        }
                    }
                }
            }

            return new Tensor<float>(new TensorShape(n1, dim), outFlat);
        }

        /// <summary>
        /// shape (n1, n2, dim) 用の Sentis Functional モデル (cosine 距離行列)
        /// を必要なら作り直す。同 shape の連続呼出ならキャッシュ再利用。
        /// </summary>
        void EnsureModel(int n1, int n2, int dim)
        {
            if (_worker != null && _cachedN1 == n1 && _cachedN2 == n2 && _cachedDim == dim)
                return;

            _worker?.Dispose();
            _worker = null;

            var graph = new FunctionalGraph();
            var qIn = graph.AddInput<float>(new TensorShape(n1, dim), "q");
            var msIn = graph.AddInput<float>(new TensorShape(n2, dim), "ms");

            // L2 正規化 (per row)
            var qL2 = Functional.ReduceL2(qIn, dim: 1, keepdim: true);   // [N1, 1]
            var qN = Functional.Div(qIn, qL2);                            // [N1, dim]
            var msL2 = Functional.ReduceL2(msIn, dim: 1, keepdim: true);
            var msN = Functional.Div(msIn, msL2);

            // sim = qN @ msN.T   → [N1, N2]
            var msNT = Functional.Transpose(msN, 0, 1);                   // [dim, N2]
            var sim = Functional.MatMul(qN, msNT);                        // [N1, N2]

            // dist = 1 - sim
            var one = Functional.Constant(1.0f);
            var dist = Functional.Sub(one, sim);

            var model = graph.Compile(dist);
            _worker = new Worker(model, Backend);

            _cachedN1 = n1;
            _cachedN2 = n2;
            _cachedDim = dim;
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _worker?.Dispose();
            _worker = null;
        }

        void EnsureNotDisposed()
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(KnnVcConverter));
        }
    }
}
