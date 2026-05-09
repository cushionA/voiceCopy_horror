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
// 関連 tests: C-1 〜 C-7

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

        BackendType _backend = BackendType.GPUCompute;

        /// <summary>
        /// 推論 backend。値変更時は次回 Convert() 呼出で worker を作り直す。
        /// </summary>
        public BackendType Backend
        {
            get => _backend;
            set
            {
                if (_backend == value) return;
                _backend = value;
                // backend が変わったら graph 再 compile が必要なため worker を破棄。
                // EnsureModel() の cache 比較は shape のみなので、ここで明示破棄しないと古い worker が残る。
                _worker?.Dispose();
                _worker = null;
                _cachedN1 = _cachedN2 = _cachedDim = _cachedK = -1;
            }
        }

        // Sentis worker は (n1, n2, dim, k) shape でモデルが固定されるため、
        // shape が変わったら作り直す。最初の Convert() 呼出時に lazy 生成。
        Worker _worker;
        int _cachedN1 = -1;
        int _cachedN2 = -1;
        int _cachedDim = -1;
        int _cachedK = -1;
        bool _disposed;

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

            using ProfilerMarker.AutoScope _ = s_MarkerTotal.Auto();

            int n1 = query.shape[0];
            int n2 = matchingSet.shape[0];
            int dim = query.shape[1];
            int k = Math.Min(TopK, n2);

            if (weights != null && weights.Length != n2)
                throw new ArgumentException(
                    $"weights length {weights.Length} must match ms count {n2}");

            // Step 1: GPU に渡す weights を準備 (weight=0 → eps、null → 全 1.0)
            // Tensor<float> はバッキング配列の所有権を奪うため、毎呼出で new float[n2] が必要 (alloc 不可避)。
            float[] tensorBacking = new float[n2];
            using (ProfilerMarker.AutoScope __ = s_MarkerWeightsPrep.Auto())
            {
                if (weights == null)
                {
                    for (int i = 0; i < n2; i++) tensorBacking[i] = 1.0f;
                }
                else
                {
                    for (int i = 0; i < n2; i++)
                    {
                        float w = weights[i];
                        tensorBacking[i] = (w > 0f) ? w : k_ZeroWeightEps;
                    }
                }
            }

            // Step 2: GPU graph を準備 (shape 変化時のみ再構築)
            EnsureModel(n1, n2, dim, k);

            // Step 3: 推論実行 + readback
            // weightsTensor は SetInput 後すぐ不要だが、Schedule() の例外時に native handle が漏れるのを
            // 避けるため using で囲む。
            float[] outFlat;
            using (Tensor<float> weightsTensor = new Tensor<float>(new TensorShape(n2), tensorBacking))
            {
                using (ProfilerMarker.AutoScope __ = s_MarkerGpuExec.Auto())
                {
                    _worker.SetInput("q", query);
                    _worker.SetInput("ms", matchingSet);
                    _worker.SetInput("w", weightsTensor);
                    _worker.Schedule();
                }

                // 出力 readback。出力 shape は [N1, dim]、これだけ CPU に持ってくる。
                using (ProfilerMarker.AutoScope __ = s_MarkerReadback.Auto())
                {
                    Tensor<float> output = _worker.PeekOutput() as Tensor<float>;
                    output.CompleteAllPendingOperations();
                    outFlat = output.DownloadToArray();
                }
            }

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

            FunctionalGraph graph = new FunctionalGraph();
            FunctionalTensor qIn  = graph.AddInput<float>(new TensorShape(n1, dim), "q");
            FunctionalTensor msIn = graph.AddInput<float>(new TensorShape(n2, dim), "ms");
            FunctionalTensor wIn  = graph.AddInput<float>(new TensorShape(n2), "w");

            // L2 正規化 (per row)。0 ベクトル (無音入力) で NaN にならないよう
            // ノルムに極小の eps を加算してから割る (旧 C# 実装の Math.Max(norm, 1e-12f) 相当)
            FunctionalTensor eps  = Functional.Constant(1e-12f);
            FunctionalTensor qL2  = Functional.Add(Functional.ReduceL2(qIn, dim: 1, keepdim: true), eps);
            FunctionalTensor qN   = Functional.Div(qIn, qL2);
            FunctionalTensor msL2 = Functional.Add(Functional.ReduceL2(msIn, dim: 1, keepdim: true), eps);
            FunctionalTensor msN  = Functional.Div(msIn, msL2);

            // sim = qN @ msN.T   → [N1, N2]
            FunctionalTensor msNT = Functional.Transpose(msN, 0, 1);
            FunctionalTensor sim  = Functional.MatMul(qN, msNT);

            // dist = 1 - sim
            FunctionalTensor one  = Functional.Constant(1.0f);
            FunctionalTensor dist = Functional.Sub(one, sim);

            // weighted = dist / w (broadcast: [N1, N2] / [1, N2])
            // w_safe は CPU 側で w<=0 → eps にすり替え済 → ここでは単純除算でよい
            FunctionalTensor w2D      = wIn.Reshape(new[] { 1, n2 });
            FunctionalTensor weighted = Functional.Div(dist, w2D);

            // TopK smallest k → indices [N1, k]
            // FunctionalTensor[] = [values, indices]
            FunctionalTensor[] topkOut    = Functional.TopK(weighted, k, dim: 1, largest: false, sorted: false);
            FunctionalTensor   topkIndices = topkOut[1]; // [N1, k] int

            // IndexSelect: 1D indices [N1*k] で ms axis=0 から gather → [N1*k, dim]
            FunctionalTensor flatIdx  = topkIndices.Reshape(new[] { n1 * k });
            FunctionalTensor gathered = msIn.IndexSelect(0, flatIdx);

            // [N1, k, dim] に reshape して axis=1 で平均 → [N1, dim]
            FunctionalTensor gathered3D = gathered.Reshape(new[] { n1, k, dim });
            FunctionalTensor meanOut    = Functional.ReduceMean(gathered3D, dim: 1, keepdim: false);

            Model model = graph.Compile(meanOut);
            _worker = new Worker(model, _backend);

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
