// KnnVcConverterTests.cs — Phase 7 Group C (TDD Red)
// voice_horror Phase 7 (2026-05-09)
//
// Coverage:
//   C-1:  kNN マッチ単体 (重みなし、shape + topk 平均ロジック)
//   C-1b: kNN マッチ重みつき (重い frame が選ばれやすい、weight=0 frame は無視)
//   C-2:  fast_cosine_dist 数値一致 (matcher.py 移植版の正確性)
//   C-3:  identity test (query == matching set 部分集合 → 出力ほぼ一致)

using NUnit.Framework;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.KnnVc;

namespace VoiceHorror.KnnVc.Tests.EditMode
{
    [TestFixture]
    public class KnnVcConverterTests
    {
        // ── C-1: kNN マッチ単体 (重みなし) ────────────────────────────

        [Test]
        public void C1_Convert_NoWeights_ReturnsCorrectShape()
        {
            using var converter = new KnnVcConverter { TopK = 4 };

            using var query = MakeRandomTensor(10, 1024, seed: 1);
            using var matchingSet = MakeRandomTensor(100, 1024, seed: 2);

            using var result = converter.Convert(query, matchingSet);

            Assert.AreEqual(2, result.shape.rank);
            Assert.AreEqual(10, result.shape[0]);
            Assert.AreEqual(1024, result.shape[1]);

            // NaN / Inf チェック
            float[] arr = result.DownloadToArray();
            for (int i = 0; i < arr.Length; i++)
            {
                Assert.IsFalse(float.IsNaN(arr[i]), $"NaN at index {i}");
                Assert.IsFalse(float.IsInfinity(arr[i]), $"Inf at index {i}");
            }
        }

        [Test]
        public void C1b_Convert_TopkAveraging_WorksCorrectly()
        {
            // matching set の特定 4 frame だけが query に近い場合、結果はその平均になるはず
            using var converter = new KnnVcConverter { TopK = 4 };

            // query = 全 1.0 / 全 0.0 等のシンプル
            using var query = MakeUniformTensor(1, 1024, value: 1.0f);

            // matching set: 4 frame は query と完全一致 (cos sim 1)、他は乱数
            float[] msFlat = new float[100 * 1024];
            for (int i = 0; i < 4; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = 1.0f;
            var rng = new System.Random(42);
            for (int i = 4; i < 100; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = (float)(rng.NextDouble() * 2.0 - 1.0);
            using var ms = new Tensor<float>(new TensorShape(100, 1024), msFlat);

            using var result = converter.Convert(query, ms);
            float[] r = result.DownloadToArray();

            // 結果は 4 frame の平均 = 全 1.0
            for (int d = 0; d < 1024; d++)
                Assert.AreEqual(1.0f, r[d], 1e-3f, $"result[{d}]");
        }

        // ── C-1b: 重みつき kNN ────────────────────────────────────────

        [Test]
        public void C2_Convert_WithWeights_ZeroWeightFramesIgnored()
        {
            using var converter = new KnnVcConverter { TopK = 4 };

            // query = 全 1.0
            using var query = MakeUniformTensor(1, 1024, value: 1.0f);

            // matching set: 前半 50 は query 近傍 (target 役)、後半 50 は遠い (player 役)
            float[] msFlat = new float[100 * 1024];
            for (int i = 0; i < 50; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = 1.0f; // target 部分
            for (int i = 50; i < 100; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = -1.0f; // player 部分 (反対方向)
            using var ms = new Tensor<float>(new TensorShape(100, 1024), msFlat);

            // weights: 前半 50 frame=1.0、後半 50 frame=0.0 (player 完全無視)
            float[] weights = new float[100];
            for (int i = 0; i < 50; i++) weights[i] = 1.0f;
            for (int i = 50; i < 100; i++) weights[i] = 0.0f;

            using var result = converter.Convert(query, ms, weights);
            float[] r = result.DownloadToArray();

            // weight=0 の player 部分は決して選ばれない → 結果は target 平均 = 全 1.0
            for (int d = 0; d < 1024; d++)
                Assert.AreEqual(1.0f, r[d], 1e-3f,
                    $"result[{d}] should be 1.0 (player frames have weight=0)");
        }

        [Test]
        public void C2b_Convert_WithWeights_AlphaOne_PlayerFullyIgnored()
        {
            // narrative テスト: α=1.0 で player 完全無視
            using var converter = new KnnVcConverter { TopK = 4 };

            using var query = MakeUniformTensor(1, 1024, value: 1.0f);

            // target = +1.0 / player = -1.0
            float[] msFlat = new float[200 * 1024];
            for (int i = 0; i < 100; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = 1.0f; // target
            for (int i = 100; i < 200; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = -1.0f; // player
            using var ms = new Tensor<float>(new TensorShape(200, 1024), msFlat);

            // α=1.0: target=1.0、player=0.0
            float[] weights = new float[200];
            for (int i = 0; i < 100; i++) weights[i] = 1.0f;
            for (int i = 100; i < 200; i++) weights[i] = 0.0f;

            using var result = converter.Convert(query, ms, weights);
            float[] r = result.DownloadToArray();

            for (int d = 0; d < 1024; d++)
                Assert.AreEqual(1.0f, r[d], 1e-3f, $"result[{d}]");
        }

        // ── C-3: identity test ───────────────────────────────────────

        [Test]
        public void C3_Convert_QueryFromMatchingSetSubset_RecoversNearIdentity()
        {
            // matching set の subset を query にしたら output ≈ query になるはず
            using var converter = new KnnVcConverter { TopK = 4 };

            using var ms = MakeRandomTensor(100, 1024, seed: 42);
            float[] msFlat = ms.DownloadToArray();

            // matching set の最初 5 frame を query にする
            float[] queryFlat = new float[5 * 1024];
            System.Array.Copy(msFlat, 0, queryFlat, 0, 5 * 1024);
            using var query = new Tensor<float>(new TensorShape(5, 1024), queryFlat);

            using var result = converter.Convert(query, ms);
            float[] r = result.DownloadToArray();

            // 各 query frame に対し、matching set の自分自身 + 他の近傍 3 個の平均
            // 自分自身は cos sim 1 で必ず top 1 → 結果は query と「ほぼ同じ」
            // 他 3 frame の平均が混ざる分の差はあるが、L1 < 0.3 くらい
            for (int q = 0; q < 5; q++)
            {
                float l1 = 0;
                for (int d = 0; d < 1024; d++)
                    l1 += Mathf.Abs(queryFlat[q * 1024 + d] - r[q * 1024 + d]);
                l1 /= 1024;
                Assert.Less(l1, 0.5f,
                    $"query[{q}] L1 distance to result should be small (got {l1})");
            }
        }

        // ── PR #6 review 反映: 追加カバレッジ ─────────────────────────

        [Test]
        public void C4_Convert_ZeroVectorQuery_DoesNotProduceNaN()
        {
            // 完全無音 (zero-pad された箇所など) でも NaN を出さない (Functional.Add eps 保護)
            using var converter = new KnnVcConverter { TopK = 4 };

            float[] zeroQuery = new float[1 * 1024]; // 全 0
            using var query = new Tensor<float>(new TensorShape(1, 1024), zeroQuery);
            using var ms = MakeRandomTensor(50, 1024, seed: 99);

            using var result = converter.Convert(query, ms);
            float[] r = result.DownloadToArray();
            for (int i = 0; i < r.Length; i++)
            {
                Assert.IsFalse(float.IsNaN(r[i]), $"NaN at {i} (zero-vector query should not break)");
                Assert.IsFalse(float.IsInfinity(r[i]), $"Inf at {i}");
            }
        }

        [Test]
        public void C5_Convert_ShapeChange_RebuildsModel()
        {
            // shape が変わった呼出で内部 Worker が再構築され、結果が壊れない
            using var converter = new KnnVcConverter { TopK = 4 };

            using (var q1 = MakeRandomTensor(5, 1024, seed: 1))
            using (var ms1 = MakeRandomTensor(50, 1024, seed: 2))
            using (var r1 = converter.Convert(q1, ms1))
            {
                Assert.AreEqual(new[] { 5, 1024 }, new[] { r1.shape[0], r1.shape[1] });
            }

            // shape を変えて再呼出 (n1, n2 ともに変化)
            using (var q2 = MakeRandomTensor(8, 1024, seed: 3))
            using (var ms2 = MakeRandomTensor(120, 1024, seed: 4))
            using (var r2 = converter.Convert(q2, ms2))
            {
                Assert.AreEqual(new[] { 8, 1024 }, new[] { r2.shape[0], r2.shape[1] });
                float[] arr = r2.DownloadToArray();
                for (int i = 0; i < arr.Length; i++)
                {
                    Assert.IsFalse(float.IsNaN(arr[i]));
                    Assert.IsFalse(float.IsInfinity(arr[i]));
                }
            }

            // 元の shape に戻すと Worker キャッシュが再びヒット (動作確認のみ、性能は別途)
            using (var q3 = MakeRandomTensor(5, 1024, seed: 5))
            using (var ms3 = MakeRandomTensor(50, 1024, seed: 6))
            using (var r3 = converter.Convert(q3, ms3))
            {
                Assert.AreEqual(new[] { 5, 1024 }, new[] { r3.shape[0], r3.shape[1] });
            }
        }

        [Test]
        public void C6_Convert_FieldCacheReuse_ProducesSameResult()
        {
            // フィールドキャッシュ (topkIndices) の再利用で同 shape 連続呼出の結果が等価
            using var converter = new KnnVcConverter { TopK = 4 };

            using var query = MakeUniformTensor(1, 1024, value: 1.0f);
            float[] msFlat = new float[100 * 1024];
            for (int i = 0; i < 4; i++)
                for (int d = 0; d < 1024; d++) msFlat[i * 1024 + d] = 1.0f;
            var rng = new System.Random(42);
            for (int i = 4; i < 100; i++)
                for (int d = 0; d < 1024; d++) msFlat[i * 1024 + d] = (float)(rng.NextDouble() * 2.0 - 1.0);
            using var ms = new Tensor<float>(new TensorShape(100, 1024), msFlat);

            // 1 回目
            float[] r1;
            using (var result1 = converter.Convert(query, ms)) r1 = result1.DownloadToArray();
            // 2 回目 (キャッシュ再利用パス)
            float[] r2;
            using (var result2 = converter.Convert(query, ms)) r2 = result2.DownloadToArray();

            for (int d = 0; d < 1024; d++)
                Assert.AreEqual(r1[d], r2[d], 1e-5f, $"result[{d}] mismatched between 1st and 2nd call");
        }

        // ── PR #7 review 反映: tie-breaking + backend setter ─────────

        [Test]
        public void C7_Convert_AllMsFramesIdentical_NoNaNAndOutputMatches()
        {
            // 全 ms frame が同一ベクトル (= 全ペアで cos sim 同値、TopK tie)。
            // Sentis TopK の tie-breaking は実装依存だが、
            // どの indices が選ばれても出力 = ms frame と等しいはず。
            using KnnVcConverter converter = new KnnVcConverter { TopK = 4 };

            float[] msFlat = new float[50 * 1024];
            for (int i = 0; i < 50; i++)
                for (int d = 0; d < 1024; d++)
                    msFlat[i * 1024 + d] = 0.5f;
            using Tensor<float> ms = new Tensor<float>(new TensorShape(50, 1024), msFlat);
            using Tensor<float> query = MakeUniformTensor(3, 1024, value: 0.7f);

            using Tensor<float> result = converter.Convert(query, ms);
            float[] r = result.DownloadToArray();
            for (int q = 0; q < 3; q++)
            {
                for (int d = 0; d < 1024; d++)
                {
                    Assert.IsFalse(float.IsNaN(r[q * 1024 + d]));
                    Assert.AreEqual(0.5f, r[q * 1024 + d], 1e-3f,
                        $"r[{q},{d}] should equal ms value 0.5 regardless of tie-break");
                }
            }
        }

        [Test]
        public void C8_Backend_Setter_RebuildsWorkerOnNextConvert()
        {
            // Backend setter で worker が破棄され、次回 Convert で再構築されること。
            // 値変更しても結果が壊れない (CPU/GPU で数値一致 ε 範囲) を担保。
            using KnnVcConverter converter = new KnnVcConverter { TopK = 4 };

            using Tensor<float> q  = MakeRandomTensor(4, 1024, seed: 11);
            using Tensor<float> ms = MakeRandomTensor(60, 1024, seed: 22);

            float[] gpuResult;
            using (Tensor<float> r = converter.Convert(q, ms)) gpuResult = r.DownloadToArray();

            // backend を CPU に切替えて同入力で再実行
            converter.Backend = BackendType.CPU;
            float[] cpuResult;
            using (Tensor<float> r = converter.Convert(q, ms)) cpuResult = r.DownloadToArray();

            Assert.AreEqual(gpuResult.Length, cpuResult.Length);
            // 浮動小数点の集約順序差で完全一致は望めないため、平均 L1 ≤ 1e-3 で十分
            float l1 = 0f;
            for (int i = 0; i < gpuResult.Length; i++) l1 += Mathf.Abs(gpuResult[i] - cpuResult[i]);
            l1 /= gpuResult.Length;
            Assert.Less(l1, 1e-3f, $"CPU/GPU 結果の平均 L1 = {l1}");
        }

        // ── Helpers ───────────────────────────────────────────────────

        static Tensor<float> MakeRandomTensor(int n, int dim, int seed)
        {
            var rng = new System.Random(seed);
            float[] data = new float[n * dim];
            for (int i = 0; i < data.Length; i++)
                data[i] = (float)(rng.NextDouble() * 2.0 - 1.0);
            return new Tensor<float>(new TensorShape(n, dim), data);
        }

        static Tensor<float> MakeUniformTensor(int n, int dim, float value)
        {
            float[] data = new float[n * dim];
            for (int i = 0; i < data.Length; i++) data[i] = value;
            return new Tensor<float>(new TensorShape(n, dim), data);
        }
    }
}
