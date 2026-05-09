// SpeakerSimilarityJudgeTests.cs — Phase 7 Group E (TDD Red)
// voice_horror Phase 7 (2026-05-09)
//
// Coverage:
//   E-1: cosine 類似度の境界値 + [0, 1] クランプ (逆方向)
//   E-2: ED 判定 3 分岐 (BadCaptured / BadVoiceChange / Good)
//   E-3: ScriptableObject 注入 + hot-fix 確認

using System;
using NUnit.Framework;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.KnnVc;

namespace VoiceHorror.KnnVc.Tests.EditMode
{
    [TestFixture]
    public class SpeakerSimilarityJudgeTests
    {
        // ── E-1: cosine 類似度 + [0, 1] クランプ ──────────────────

        [Test]
        public void E1_ComputeSimilarity_SamePool_ReturnsOne()
        {
            var pool = new MatchingSetPool("a");
            using (var f = MakeUniformTensor(50, 1024, value: 1.0f))
                pool.Append(f);

            var judge = new SpeakerSimilarityJudge();
            float sim = judge.ComputeSimilarity(pool, pool);
            Assert.AreEqual(1.0f, sim, 1e-3f);
        }

        [Test]
        public void E1b_ComputeSimilarity_OrthogonalPools_ReturnsZero()
        {
            // dim=4 で簡略化: A=[1,0,0,0]、B=[0,1,0,0] が直交
            // ただし MatchingSetPool は dim=1024 固定なので、padding でテスト
            var poolA = new MatchingSetPool("A");
            var poolB = new MatchingSetPool("B");

            float[] aFlat = new float[10 * 1024];
            float[] bFlat = new float[10 * 1024];
            for (int i = 0; i < 10; i++)
            {
                aFlat[i * 1024 + 0] = 1.0f; // A は dim 0 だけ
                bFlat[i * 1024 + 1] = 1.0f; // B は dim 1 だけ
            }
            using (var ta = new Tensor<float>(new TensorShape(10, 1024), aFlat)) poolA.Append(ta);
            using (var tb = new Tensor<float>(new TensorShape(10, 1024), bFlat)) poolB.Append(tb);

            var judge = new SpeakerSimilarityJudge();
            float sim = judge.ComputeSimilarity(poolA, poolB);
            Assert.AreEqual(0.0f, sim, 1e-3f, "orthogonal pools should give sim=0");
        }

        [Test]
        public void E1c_ComputeSimilarity_OppositePools_Clamped_ReturnsZero()
        {
            // A=[1,1,...,1] / B=[-1,-1,...,-1] の cos = -1 → clamp で 0
            var poolA = new MatchingSetPool("A");
            var poolB = new MatchingSetPool("B");
            using (var f = MakeUniformTensor(10, 1024, value: 1.0f)) poolA.Append(f);
            using (var f = MakeUniformTensor(10, 1024, value: -1.0f)) poolB.Append(f);

            var judge = new SpeakerSimilarityJudge();
            float sim = judge.ComputeSimilarity(poolA, poolB);
            Assert.AreEqual(0.0f, sim, 1e-3f,
                "opposite pools (cos=-1) should be clamped to 0");
        }

        [Test]
        public void E1d_ComputeSimilarity_EmptyPool_Throws()
        {
            var emptyPool = new MatchingSetPool("empty");
            var nonEmpty = new MatchingSetPool("ok");
            using (var f = MakeUniformTensor(5, 1024, 1.0f)) nonEmpty.Append(f);

            var judge = new SpeakerSimilarityJudge();
            Assert.Throws<InvalidOperationException>(
                () => judge.ComputeSimilarity(emptyPool, nonEmpty));
            Assert.Throws<InvalidOperationException>(
                () => judge.ComputeSimilarity(nonEmpty, emptyPool));
        }

        // ── E-2: 3 分岐判定 ──────────────────────────────────────────

        [Test]
        public void E2_Judge_HighSimilarity_BadCaptured()
        {
            var so = ScriptableObject.CreateInstance<EdThresholdsAsset>();
            so.HighThreshold = 0.85f;
            so.MidHigh = 0.70f;
            so.MidLow = 0.40f;

            var judge = new SpeakerSimilarityJudge(so);
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.BadCaptured, judge.Judge(0.9f));
        }

        [Test]
        public void E2b_Judge_MidSimilarity_BadVoiceChange()
        {
            var so = ScriptableObject.CreateInstance<EdThresholdsAsset>();
            so.HighThreshold = 0.85f;
            so.MidHigh = 0.70f;
            so.MidLow = 0.40f;

            var judge = new SpeakerSimilarityJudge(so);
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.BadVoiceChange, judge.Judge(0.5f));
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.BadVoiceChange, judge.Judge(0.7f));
        }

        [Test]
        public void E2c_Judge_LowSimilarity_Good()
        {
            var so = ScriptableObject.CreateInstance<EdThresholdsAsset>();
            so.HighThreshold = 0.85f;
            so.MidHigh = 0.70f;
            so.MidLow = 0.40f;

            var judge = new SpeakerSimilarityJudge(so);
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.Good, judge.Judge(0.2f));
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.Good, judge.Judge(0.4f));
        }

        // ── E-3: SO による hot-fix ────────────────────────────────────

        [Test]
        public void E3_Judge_ThresholdSwap_ChangesVerdict()
        {
            var so = ScriptableObject.CreateInstance<EdThresholdsAsset>();
            so.HighThreshold = 0.85f;
            so.MidHigh = 0.70f;
            so.MidLow = 0.40f;

            var judge = new SpeakerSimilarityJudge(so);
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.BadVoiceChange, judge.Judge(0.5f));

            // Threshold を hot-fix
            so.HighThreshold = 0.4f;
            Assert.AreEqual(SpeakerSimilarityJudge.Verdict.BadCaptured, judge.Judge(0.5f),
                "after threshold change, same sim should give different verdict");
        }

        [Test]
        public void E3b_Judge_NullThresholds_Throws()
        {
            var judge = new SpeakerSimilarityJudge(null);
            Assert.Throws<InvalidOperationException>(() => judge.Judge(0.5f));
        }

        // ── helpers ───────────────────────────────────────────────────

        static Tensor<float> MakeUniformTensor(int n, int dim, float value)
        {
            float[] data = new float[n * dim];
            for (int i = 0; i < data.Length; i++) data[i] = value;
            return new Tensor<float>(new TensorShape(n, dim), data);
        }
    }
}
