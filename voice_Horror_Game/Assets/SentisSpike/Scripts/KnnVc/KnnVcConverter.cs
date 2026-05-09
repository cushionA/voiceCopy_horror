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

        // 自前 alloc する配列のうち、内部使用のみのものはフィールドキャッシュで GC 圧を回避。
        // - topkIndices: 内部使用のみ → キャッシュ可
        // - outFlat: 戻り値 Tensor が所有 → 次回呼出で破壊されるため毎回 alloc 必須
        // - distFlat / ms: Sentis DownloadToArray() の戻り値 (destination 受取オーバーロード無し)
        //                  のため毎回 alloc 不可避
        int[] _topkIndicesCache;

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
                _worker.SetInput("q",  query);
                _worker.SetInput("ms", matchingSet);
                _worker.Schedule();

                // Worker の output tensor から直接 DownloadToArray (内部で同期 readback)。
                // 旧実装は ReadbackAndClone (Tensor 確保 ~10MB) → DownloadToArray (float[] ~10MB)
                // で二重 alloc していたが、distFlat だけあれば良いため Tensor 確保を省略。
                var output = _worker.PeekOutput() as Tensor<float>;
                output.CompleteAllPendingOperations();
                distFlat = output.DownloadToArray();
            }

            // ms は CPU 側で平均計算に必要なので 1 回だけ download
            float[] ms = matchingSet.DownloadToArray();

            // Step 2 (Pass 1): top-K インデックス算出 (重みつき除外もここで)
            // Profiler マーカーが互いにネストしないよう、TopK と Average を 2 パスに分離。
            int topkLen = n1 * k;
            if (_topkIndicesCache == null || _topkIndicesCache.Length < topkLen)
                _topkIndicesCache = new int[topkLen];
            int[] topkIndicesAll = _topkIndicesCache;
            using (s_MarkerTopK.Auto())
            {
                int[] topkIdx = new int[k];
                float[] topkDist = new float[k];

                for (int i = 0; i < n1; i++)
                {
                    for (int t = 0; t < k; t++)
                    {
                        topkIdx[t] = -1;
                        topkDist[t] = float.PositiveInfinity;
                    }

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

                    int outBase = i * k;
                    for (int t = 0; t < k; t++) topkIndicesAll[outBase + t] = topkIdx[t];
                }
            }

            // Step 3 (Pass 2): top-K インデックスから ms 行を平均。
            // 戻り値の Tensor が outFlat を所有するため、毎回 alloc 必須
            // (フィールドキャッシュにすると次回呼出で前回戻り値が破壊される)
            float[] outFlat = new float[n1 * dim];
            using (s_MarkerAverage.Auto())
            {
                for (int i = 0; i < n1; i++)
                {
                    int outBase = i * dim;
                    int idxBase = i * k;
                    int validCount = 0;
                    for (int d = 0; d < dim; d++) outFlat[outBase + d] = 0f;

                    for (int t = 0; t < k; t++)
                    {
                        int j = topkIndicesAll[idxBase + t];
                        if (j < 0) continue;
                        validCount++;
                        int msBase = j * dim;
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

            // L2 正規化 (per row)。0 ベクトル (無音入力) で NaN にならないよう
            // ノルムに極小の eps を加算してから割る (旧 C# 実装の Math.Max(norm, 1e-12f) 相当)
            var eps = Functional.Constant(1e-12f);
            var qL2 = Functional.Add(Functional.ReduceL2(qIn, dim: 1, keepdim: true), eps);  // [N1, 1]
            var qN  = Functional.Div(qIn, qL2);                                              // [N1, dim]
            var msL2 = Functional.Add(Functional.ReduceL2(msIn, dim: 1, keepdim: true), eps);
            var msN  = Functional.Div(msIn, msL2);

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
