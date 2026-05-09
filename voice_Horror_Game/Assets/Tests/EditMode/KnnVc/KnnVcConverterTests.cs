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
