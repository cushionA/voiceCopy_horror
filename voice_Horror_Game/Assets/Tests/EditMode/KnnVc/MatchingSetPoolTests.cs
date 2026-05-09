// MatchingSetPoolTests.cs — Phase 7 Group B (TDD Red)
// voice_horror Phase 7 (2026-05-09)
//
// Coverage:
//   B-1: 空プール初期化
//   B-2: append 動作 (累積、weight)
//   B-3: WeightedPoolBuilder (α 0.0/0.5/0.7/1.0 の重み確認)
//   B-4: npy 永続化 (save/load round-trip)
//   B-5: カバレッジ計算 + 段階目標 warning
//
// Note: ToTensor() / GetWeights() の Sentis Tensor 部分は EditMode でも動作確認可
//       (Sentis Worker は不要、Tensor の確保のみ)

using System.IO;
using NUnit.Framework;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.KnnVc;

namespace VoiceHorror.KnnVc.Tests.EditMode
{
    [TestFixture]
    public class MatchingSetPoolTests
    {
        // ── B-1: 空プール初期化 ───────────────────────────────────────

        [Test]
        public void B1_EmptyPool_HasZeroFrames()
        {
            var pool = new MatchingSetPool("test");

            Assert.AreEqual("test", pool.Name);
            Assert.AreEqual(0, pool.FrameCount);
            Assert.AreEqual(0f, pool.Coverage5MinRatio);

            using var tensor = pool.ToTensor();
            Assert.AreEqual(2, tensor.shape.rank);
            Assert.AreEqual(0, tensor.shape[0]);
            Assert.AreEqual(1024, tensor.shape[1]);

            Assert.AreEqual(0, pool.GetWeights().Length);
        }

        // ── B-2: append 動作 ──────────────────────────────────────────

        [Test]
        public void B2_Append_AccumulatesFrames()
        {
            var pool = new MatchingSetPool("test");

            // 50 frames を append
            using (var feats1 = MakeRandomFeatures(50, 1024, seed: 1))
                pool.Append(feats1);
            Assert.AreEqual(50, pool.FrameCount);

            // さらに 30 frames を append
            using (var feats2 = MakeRandomFeatures(30, 1024, seed: 2))
                pool.Append(feats2);
            Assert.AreEqual(80, pool.FrameCount);
        }

        [Test]
        public void B2b_Append_WithWeight_StoresWeightCorrectly()
        {
            var pool = new MatchingSetPool("test");

            using (var feats = MakeRandomFeatures(10, 1024, seed: 1))
                pool.Append(feats, weight: 0.7f);

            float[] weights = pool.GetWeights();
            Assert.AreEqual(10, weights.Length);
            for (int i = 0; i < 10; i++)
                Assert.AreEqual(0.7f, weights[i], 1e-6f, $"weight[{i}]");
        }

        [Test]
        public void B2c_Append_DefaultWeight_IsOne()
        {
            var pool = new MatchingSetPool("test");

            using (var feats = MakeRandomFeatures(5, 1024, seed: 1))
                pool.Append(feats);  // weight 省略 = 1.0

            float[] weights = pool.GetWeights();
            for (int i = 0; i < 5; i++)
                Assert.AreEqual(1.0f, weights[i], 1e-6f);
        }

        // ── B-3: WeightedPoolBuilder ──────────────────────────────────

        [Test]
        public void B3_WeightedPoolBuilder_AlphaHalf_EqualWeights()
        {
            var poolA = new MatchingSetPool("A");
            var poolB = new MatchingSetPool("B");
            using (var fa = MakeRandomFeatures(100, 1024, seed: 1)) poolA.Append(fa);
            using (var fb = MakeRandomFeatures(100, 1024, seed: 2)) poolB.Append(fb);

            var (features, weights) = WeightedPoolBuilder.Build(poolA, poolB, alpha: 0.5f);

            Assert.AreEqual(2, features.shape.rank);
            Assert.AreEqual(200, features.shape[0]);
            Assert.AreEqual(1024, features.shape[1]);
            Assert.AreEqual(200, weights.Length);

            // α=0.5 で全 weight = 0.5
            for (int i = 0; i < 200; i++)
                Assert.AreEqual(0.5f, weights[i], 1e-6f, $"weights[{i}]");

            features.Dispose();
        }

        [Test]
        public void B3b_WeightedPoolBuilder_AlphaSeven_AssignsWeights()
        {
            var poolA = new MatchingSetPool("A");
            var poolB = new MatchingSetPool("B");
            using (var fa = MakeRandomFeatures(100, 1024, seed: 1)) poolA.Append(fa);
            using (var fb = MakeRandomFeatures(100, 1024, seed: 2)) poolB.Append(fb);

            var (features, weights) = WeightedPoolBuilder.Build(poolA, poolB, alpha: 0.7f);

            // 前半 100 frames (A): weight 0.7、後半 100 (B): weight 0.3
            for (int i = 0; i < 100; i++)
                Assert.AreEqual(0.7f, weights[i], 1e-6f, $"A part weights[{i}]");
            for (int i = 100; i < 200; i++)
                Assert.AreEqual(0.3f, weights[i], 1e-6f, $"B part weights[{i}]");

            features.Dispose();
        }

        [Test]
        public void B3c_WeightedPoolBuilder_AlphaOne_BPartWeightZero()
        {
            var poolA = new MatchingSetPool("A");
            var poolB = new MatchingSetPool("B");
            using (var fa = MakeRandomFeatures(50, 1024, seed: 1)) poolA.Append(fa);
            using (var fb = MakeRandomFeatures(50, 1024, seed: 2)) poolB.Append(fb);

            var (features, weights) = WeightedPoolBuilder.Build(poolA, poolB, alpha: 1.0f);

            // α=1.0: A 部分は weight=1.0、B 部分は weight=0.0 (B 完全無視)
            for (int i = 0; i < 50; i++)
                Assert.AreEqual(1.0f, weights[i], 1e-6f);
            for (int i = 50; i < 100; i++)
                Assert.AreEqual(0.0f, weights[i], 1e-6f);

            features.Dispose();
        }

        [Test]
        public void B3d_WeightedPoolBuilder_AlphaZero_APartWeightZero()
        {
            var poolA = new MatchingSetPool("A");
            var poolB = new MatchingSetPool("B");
            using (var fa = MakeRandomFeatures(50, 1024, seed: 1)) poolA.Append(fa);
            using (var fb = MakeRandomFeatures(50, 1024, seed: 2)) poolB.Append(fb);

            var (features, weights) = WeightedPoolBuilder.Build(poolA, poolB, alpha: 0.0f);

            for (int i = 0; i < 50; i++)
                Assert.AreEqual(0.0f, weights[i], 1e-6f);
            for (int i = 50; i < 100; i++)
                Assert.AreEqual(1.0f, weights[i], 1e-6f);

            features.Dispose();
        }

        // ── B-4: npy 永続化 ───────────────────────────────────────────

        [Test]
        public void B4_SaveLoad_RoundTrip_PreservesData()
        {
            var pool = new MatchingSetPool("test");
            using (var feats = MakeRandomFeatures(123, 1024, seed: 42))
                pool.Append(feats, weight: 0.7f);

            string tmpDir = Path.Combine(Application.temporaryCachePath, "knnvc_test_pool");
            Directory.CreateDirectory(tmpDir);
            string path = Path.Combine(tmpDir, "pool.npy");
            try
            {
                pool.SaveTo(path);
                Assert.IsTrue(File.Exists(path), "features npy file should exist");
                Assert.IsTrue(File.Exists(Path.Combine(tmpDir, "pool_weights.npy")),
                    "weights npy file should exist");

                var restored = MatchingSetPool.LoadFrom(path, "restored");
                Assert.AreEqual(123, restored.FrameCount);
                Assert.AreEqual("restored", restored.Name);

                // Features 数値一致
                using var origTensor = pool.ToTensor();
                using var restTensor = restored.ToTensor();
                float[] origArr = origTensor.DownloadToArray();
                float[] restArr = restTensor.DownloadToArray();
                Assert.AreEqual(origArr.Length, restArr.Length);
                for (int i = 0; i < origArr.Length; i++)
                    Assert.AreEqual(origArr[i], restArr[i], 1e-6f, $"features[{i}]");

                // Weights 数値一致
                float[] origW = pool.GetWeights();
                float[] restW = restored.GetWeights();
                Assert.AreEqual(origW.Length, restW.Length);
                for (int i = 0; i < origW.Length; i++)
                    Assert.AreEqual(origW[i], restW[i], 1e-6f, $"weights[{i}]");
            }
            finally
            {
                if (Directory.Exists(tmpDir))
                    Directory.Delete(tmpDir, recursive: true);
            }
        }

        // ── B-5: カバレッジ計算 ───────────────────────────────────────

        [Test]
        public void B5_Coverage5MinRatio_FullPool()
        {
            var pool = new MatchingSetPool("test");
            using (var feats = MakeRandomFeatures(15000, 1024, seed: 1))
                pool.Append(feats);

            Assert.AreEqual(1.0f, pool.Coverage5MinRatio, 1e-3f,
                "15000 frames = 5 分相当で Coverage = 1.0");
        }

        [Test]
        public void B5b_Coverage5MinRatio_PartialPool()
        {
            var pool = new MatchingSetPool("test");
            using (var feats = MakeRandomFeatures(4500, 1024, seed: 1))
                pool.Append(feats);

            Assert.AreEqual(0.3f, pool.Coverage5MinRatio, 1e-3f,
                "4500 frames = 1.5 分で Coverage = 0.3");
        }

        // ── Helpers ───────────────────────────────────────────────────

        static Tensor<float> MakeRandomFeatures(int n, int dim, int seed)
        {
            var rng = new System.Random(seed);
            float[] data = new float[n * dim];
            for (int i = 0; i < data.Length; i++)
                data[i] = (float)(rng.NextDouble() * 2.0 - 1.0);
            return new Tensor<float>(new TensorShape(n, dim), data);
        }
    }
}
