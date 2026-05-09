// KnnVcConverter.cs — Phase 7 Group C / Phase 8 完全 GPU 化
// voice_horror Phase 7-8 (2026-05-09)
//
// Responsibility:
//   query 特徴 [N1, 1024] と matching set [N2, 1024] (+ オプション weights [N2])
//   から topk kNN マッチした converted features [N1, 1024] を返す。
//
// Phase 8 完全 GPU 化:
//   旧 Phase 8 実装:
//     - cosine 距離行列 [N1, N2] を GPU で計算
//     - top-K インデックス選別を CPU 線形探索 (ms 全量 download → ~6MB GC 圧)
//     - top-K 行を CPU で平均
//   新 (本リファクタ):
//     - cosine 距離 → 重みつきスケール → Functional.TopK → IndexSelect → ReduceMean
//       までを 1 つの Sentis graph に詰める
//     - CPU readback は出力 [N1, dim]=7MB のみ (旧 dist 行列 [N1, N2]=10MB + ms [N2, dim]=6MB の二重 readback を解消)
//
// 数学:
//   q_norm   = q  / (|q| + eps)       (per row L2 正規化)
//   ms_norm  = ms / (|ms| + eps)
//   sim      = q_norm @ ms_norm.T            // [N1, N2]
//   dist     = 1 - sim                        // [N1, N2]
//   weighted = dist / w_safe                  // broadcast、w_safe[j]=max(w[j], 1e-30)
//                                            // ※ w=0 frame は w_safe=1e-30 → dist/w=∞ → TopK で除外
//   topk_idx = TopK(weighted, k, largest=false).indices   // [N1, k]
//   gathered = ms[topk_idx]                   // [N1, k, dim]
//   output   = mean(gathered, axis=1)         // [N1, dim]
//
// 関連 spec: VC-001 内部、MS-003 重みつき kNN
// 関連 design: design.md component 3
// 関連 tests: C-1 〜 C-6

using System;
using Unity.InferenceEngine;
using Unity.Profiling;

namespace VoiceHorror.KnnVc
{
    public class KnnVcConverter : IDisposable
    {
        static readonly ProfilerMarker s_MarkerTotal       = new ProfilerMarker("VC.kNN");
        static readonly ProfilerMarker s_MarkerWeightsPrep = new ProfilerMarker("VC.kNN.WeightsPrep");
        static readonly ProfilerMarker s_MarkerGpuExec     = new ProfilerMarker("VC.kNN.GpuExec");
        static readonly ProfilerMarker s_MarkerReadback    = new ProfilerMarker("VC.kNN.Readback");

        // weight=0 frame を TopK から実質除外するためのスケール。
        // dist は cosine 距離なので最大 2.0、それを 1e-30 で割れば 2e30 ≫ 他の dist/w_safe 値となり、
        // TopK(largest=false) で確実に押し出される。1e-38 まで余裕があるが、
        // 安全マージンを取って 1e-30 に。
        const float k_ZeroWeightEps = 1e-30f;

        public int TopK { get; set; } = 4;
        public BackendType Backend { get; set; } = BackendType.GPUCompute;

        // Sentis worker は (n1, n2, dim, k) shape でモデルが固定されるため、
        // shape が変わったら作り直す。最初の Convert() 呼出時に lazy 生成。
        Worker _worker;
        int _cachedN1 = -1;
        int _cachedN2 = -1;
        int _cachedDim = -1;
        int _cachedK = -1;
        bool _disposed;

        // GPU 側に投げる weights を (毎呼出 alloc 抑制のため) フィールドキャッシュ。
        // weights == null の場合は全 1.0、weights ありの場合は w[j]=max(weights[j], k_ZeroWeightEps) を入れる。
        float[] _weightsForGpuCache;

        /// <summary>
        /// query [N1, 1024] と matching set [N2, 1024] から kNN マッチして
        /// converted features [N1, 1024] を返す。
        ///
        /// weights が指定されていれば各 frame の cosine 距離を 1/weight でスケーリングする。
        /// (weight 大 → 距離短く見える → 選ばれやすい / weight=0 → 距離 ≈ +∞ で完全除外)
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

            // Step 1: GPU に渡す weights を準備 (weight=0 → eps、null → 全 1.0)
            Tensor<float> weightsTensor;
            using (s_MarkerWeightsPrep.Auto())
            {
                if (_weightsForGpuCache == null || _weightsForGpuCache.Length < n2)
                    _weightsForGpuCache = new float[n2];
                if (weights == null)
                {
                    for (int i = 0; i < n2; i++) _weightsForGpuCache[i] = 1.0f;
                }
                else
                {
                    for (int i = 0; i < n2; i++)
                    {
                        float w = weights[i];
                        _weightsForGpuCache[i] = (w > 0f) ? w : k_ZeroWeightEps;
                    }
                }
                // Tensor<float> にラップ。Worker への入力後 dispose する。
                // 初回 alloc 後は同 shape でなければ再 alloc が必要。
                // n2 が変わると graph も再構築するので tensor も毎回新規で問題ない。
                float[] tensorBacking = new float[n2];
                Buffer.BlockCopy(_weightsForGpuCache, 0, tensorBacking, 0, n2 * sizeof(float));
                weightsTensor = new Tensor<float>(new TensorShape(n2), tensorBacking);
            }

            // Step 2: GPU graph を準備 (shape 変化時のみ再構築)
            EnsureModel(n1, n2, dim, k);

            // Step 3: 推論実行
            float[] outFlat;
            using (s_MarkerGpuExec.Auto())
            {
                _worker.SetInput("q", query);
                _worker.SetInput("ms", matchingSet);
                _worker.SetInput("w", weightsTensor);
                _worker.Schedule();
            }

            // Step 4: 出力 readback
            // 出力 shape は [N1, dim]、これだけ CPU に持ってくる。
            // Worker の output tensor から直接 DownloadToArray (内部で同期 readback)。
            using (s_MarkerReadback.Auto())
            {
                var output = _worker.PeekOutput() as Tensor<float>;
                output.CompleteAllPendingOperations();
                outFlat = output.DownloadToArray();
            }

            weightsTensor.Dispose();

            return new Tensor<float>(new TensorShape(n1, dim), outFlat);
        }

        /// <summary>
        /// shape (n1, n2, dim, k) 用の Sentis Functional モデル
        /// (cosine 距離 + 重みつきスケール + TopK + Gather + Mean) を必要なら作り直す。
        /// 同 shape の連続呼出ならキャッシュ再利用。
        /// </summary>
        void EnsureModel(int n1, int n2, int dim, int k)
        {
            if (_worker != null
                && _cachedN1 == n1 && _cachedN2 == n2 && _cachedDim == dim && _cachedK == k)
                return;

            _worker?.Dispose();
            _worker = null;

            var graph = new FunctionalGraph();
            var qIn  = graph.AddInput<float>(new TensorShape(n1, dim), "q");
            var msIn = graph.AddInput<float>(new TensorShape(n2, dim), "ms");
            var wIn  = graph.AddInput<float>(new TensorShape(n2), "w");

            // L2 正規化 (per row)。0 ベクトル (無音入力) で NaN にならないよう
            // ノルムに極小の eps を加算してから割る (旧 C# 実装の Math.Max(norm, 1e-12f) 相当)
            var eps = Functional.Constant(1e-12f);
            var qL2  = Functional.Add(Functional.ReduceL2(qIn, dim: 1, keepdim: true), eps);
            var qN   = Functional.Div(qIn, qL2);
            var msL2 = Functional.Add(Functional.ReduceL2(msIn, dim: 1, keepdim: true), eps);
            var msN  = Functional.Div(msIn, msL2);

            // sim = qN @ msN.T   → [N1, N2]
            var msNT = Functional.Transpose(msN, 0, 1);
            var sim  = Functional.MatMul(qN, msNT);

            // dist = 1 - sim
            var one  = Functional.Constant(1.0f);
            var dist = Functional.Sub(one, sim);

            // weighted = dist / w (broadcast: [N1, N2] / [1, N2])
            // w_safe は CPU 側で w<=0 → eps にすり替え済 → ここでは単純除算でよい
            var w2D = wIn.Reshape(new[] { 1, n2 });
            var weighted = Functional.Div(dist, w2D);

            // TopK smallest k → indices [N1, k]
            // FunctionalTensor[] = [values, indices]
            var topkOut = Functional.TopK(weighted, k, dim: 1, largest: false, sorted: false);
            var topkIndices = topkOut[1]; // [N1, k] int

            // IndexSelect: 1D indices [N1*k] で ms axis=0 から gather → [N1*k, dim]
            var flatIdx  = topkIndices.Reshape(new[] { n1 * k });
            var gathered = msIn.IndexSelect(0, flatIdx);

            // [N1, k, dim] に reshape して axis=1 で平均 → [N1, dim]
            var gathered3D = gathered.Reshape(new[] { n1, k, dim });
            var meanOut    = Functional.ReduceMean(gathered3D, dim: 1, keepdim: false);

            var model = graph.Compile(meanOut);
            _worker = new Worker(model, Backend);

            _cachedN1 = n1;
            _cachedN2 = n2;
            _cachedDim = dim;
            _cachedK = k;
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
