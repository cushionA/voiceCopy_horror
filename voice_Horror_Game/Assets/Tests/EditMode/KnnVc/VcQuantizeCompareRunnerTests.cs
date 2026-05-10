// VcQuantizeCompareRunnerTests.cs — Phase 8 PR #8 review S-2
// voice_horror Phase 8 (2026-05-10)
//
// Coverage: VcQuantizeCompareRunner.ComputeWaveformMetrics の純関数部分
//   - 既知 delta で RMSE / maxAbsDiff / peak が公式通り
//   - 長さ違い (短い方 → RMSE、両 peak → 全長集計) の挙動
//   - null / 空配列のガード
// 比較メトリクスは production loop 内で 1 ペアあたり 1 回回るので、
// バグると CSV 全列が腐る。EditMode で純関数として落とし込む。

using NUnit.Framework;
using VoiceHorror.KnnVc;

namespace VoiceHorror.KnnVc.Tests.EditMode
{
    [TestFixture]
    public class VcQuantizeCompareRunnerTests
    {
        const double k_FloatTol = 1e-6;

        // ── 基本動作: 同一入力 ─────────────────────────────────────────

        [Test]
        public void Metrics_IdenticalArrays_ZeroDiff()
        {
            float[] a = { 0.1f, -0.5f, 0.9f, -0.3f };
            float[] b = { 0.1f, -0.5f, 0.9f, -0.3f };

            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(a, b);

            Assert.AreEqual(4, m.compareLen);
            Assert.AreEqual(0.0, m.rmse, k_FloatTol);
            Assert.AreEqual(0.0, m.maxAbsDiff, k_FloatTol);
            Assert.AreEqual(0.9, m.peakA, k_FloatTol);
            Assert.AreEqual(0.9, m.peakB, k_FloatTol);
        }

        // ── RMSE 公式検証 ──────────────────────────────────────────────

        [Test]
        public void Metrics_KnownDelta_RmseEqualsExpected()
        {
            // a - b = [0.5, 0.5, 0.5] → sumSq = 0.75 → RMSE = sqrt(0.25) = 0.5
            float[] a = { 0.5f, 0.5f, 0.5f };
            float[] b = { 0.0f, 0.0f, 0.0f };

            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(a, b);

            Assert.AreEqual(3, m.compareLen);
            Assert.AreEqual(0.5, m.rmse, k_FloatTol);
            Assert.AreEqual(0.5, m.maxAbsDiff, k_FloatTol);
            Assert.AreEqual(0.5, m.peakA, k_FloatTol);
            Assert.AreEqual(0.0, m.peakB, k_FloatTol);
        }

        [Test]
        public void Metrics_MixedDelta_RmseEqualsExpected()
        {
            // a - b = [0.2, -0.4, 0.6, -0.8] → sumSq = 0.04+0.16+0.36+0.64 = 1.20
            // RMSE = sqrt(1.20 / 4) = sqrt(0.3) ≈ 0.547722557...
            float[] a = { 0.2f, -0.4f, 0.6f, -0.8f };
            float[] b = { 0.0f, 0.0f, 0.0f, 0.0f };

            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(a, b);

            Assert.AreEqual(System.Math.Sqrt(0.3), m.rmse, k_FloatTol);
            Assert.AreEqual(0.8, m.maxAbsDiff, k_FloatTol);
            Assert.AreEqual(0.8, m.peakA, k_FloatTol, "|−0.8| が peak");
        }

        // ── maxAbsDiff: 符号反転を吸収 ────────────────────────────────────

        [Test]
        public void Metrics_NegativeDelta_MaxAbsDiffIsAbsoluteValue()
        {
            // a - b = [−0.7, 0.1, −0.9, 0.3] → maxAbsDiff = 0.9
            float[] a = { 0.0f, 0.1f, 0.0f, 0.3f };
            float[] b = { 0.7f, 0.0f, 0.9f, 0.0f };

            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(a, b);

            Assert.AreEqual(0.9, m.maxAbsDiff, k_FloatTol);
        }

        // ── 長さ違い: 短い方で RMSE、両 peak は全長 ─────────────────────────

        [Test]
        public void Metrics_DifferentLength_UsesShorterForRmseButFullForPeak()
        {
            // a (len=2) と b (len=5)。 a の最後尾 +0.99 は peak だけに反映、RMSE には含まれない。
            float[] a = { 0.1f, 0.2f };
            float[] b = { 0.1f, 0.2f, 0.99f, -0.5f, 0.3f };

            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(a, b);

            Assert.AreEqual(2, m.compareLen, "短い方の長さで比較");
            Assert.AreEqual(0.0, m.rmse, k_FloatTol, "比較範囲の delta は 0");
            Assert.AreEqual(0.0, m.maxAbsDiff, k_FloatTol);
            Assert.AreEqual(0.2, m.peakA, k_FloatTol, "a の全長 (2) から");
            Assert.AreEqual(0.99, m.peakB, k_FloatTol, "b の全長 (5) から、長さ超過部分も反映");
        }

        [Test]
        public void Metrics_DifferentLength_PeakAFromTrailingPart()
        {
            // a が長い場合は、a 末尾 (b 範囲外) の peak が peakA に反映されるはず
            float[] a = { 0.1f, 0.2f, 0.95f, -0.85f };
            float[] b = { 0.1f, 0.2f };

            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(a, b);

            Assert.AreEqual(2, m.compareLen);
            Assert.AreEqual(0.95, m.peakA, k_FloatTol, "a の長さ超過部分の peak");
            Assert.AreEqual(0.2, m.peakB, k_FloatTol);
        }

        // ── ガード: null / 空 ────────────────────────────────────────────

        [Test]
        public void Metrics_NullA_ReturnsDefault()
        {
            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(null, new float[] { 0.5f });

            Assert.AreEqual(0, m.compareLen);
            Assert.AreEqual(0.0, m.rmse);
            Assert.AreEqual(0.0, m.maxAbsDiff);
            Assert.AreEqual(0.0, m.peakA);
            Assert.AreEqual(0.0, m.peakB);
        }

        [Test]
        public void Metrics_NullB_ReturnsDefault()
        {
            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(new float[] { 0.5f }, null);

            Assert.AreEqual(0, m.compareLen);
        }

        [Test]
        public void Metrics_EmptyArrays_AllZero()
        {
            VcQuantizeCompareRunner.WaveformMetrics m =
                VcQuantizeCompareRunner.ComputeWaveformMetrics(new float[0], new float[0]);

            Assert.AreEqual(0, m.compareLen);
            Assert.AreEqual(0.0, m.rmse, "n=0 のとき RMSE は 0 (NaN を返さない)");
            Assert.AreEqual(0.0, m.peakA);
            Assert.AreEqual(0.0, m.peakB);
        }
    }
}
