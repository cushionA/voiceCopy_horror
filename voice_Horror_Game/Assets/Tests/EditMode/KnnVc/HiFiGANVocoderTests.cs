// HiFiGANVocoderTests.cs — Phase 7 Group D (EditMode)
// voice_horror Phase 7 (2026-05-09)
//
// EditMode で動作 (Sentis Worker は EditMode 可、UniCli 経由実行を優先するため)。
//
// Coverage:
//   D-1: dummy 特徴 [1, 250, 1024] → audio [80000]、NaN/Inf なし
//   D-2: peak > 1.0 で VocodeNormalized が peak 0.95 にスケール
//   D-3: 入力 shape の罠 (channel-last 必須)

using System;
using NUnit.Framework;
using Unity.InferenceEngine;
using UnityEditor;
using UnityEngine;
using VoiceHorror.KnnVc;

namespace VoiceHorror.KnnVc.Tests.EditMode
{
    [TestFixture]
    public class HiFiGANVocoderTests
    {
        const string k_HifiganPath = "Assets/SentisSpike/Models/KnnVc/hifigan_wavlm_layer6.onnx";

        ModelAsset _hifiganModel;

        [OneTimeSetUp]
        public void OneTimeSetUp()
        {
            _hifiganModel = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_HifiganPath);
            if (_hifiganModel == null)
                Assert.Inconclusive($"HiFiGAN model not found at {k_HifiganPath}");
        }

        // ── D-1: dummy 特徴 → audio ──────────────────────────────────

        [Test]
        public void D1_Vocode_DummyFeatures_ReturnsValidAudio()
        {
            using var vocoder = new HiFiGANVocoder(_hifiganModel);

            using var feats = MakeRandomFeatures(1, 250, 1024, seed: 42);
            float[] audio = vocoder.Vocode(feats);

            Assert.IsNotNull(audio);
            // 250 frames × hop 320 = 80000 samples (16kHz audio)
            Assert.That(audio.Length, Is.InRange(75000, 85000),
                $"audio length should be ~80000 (got {audio.Length})");

            int nan = 0, inf = 0;
            for (int i = 0; i < audio.Length; i++)
            {
                if (float.IsNaN(audio[i])) nan++;
                else if (float.IsInfinity(audio[i])) inf++;
            }
            Assert.AreEqual(0, nan);
            Assert.AreEqual(0, inf);
        }

        // ── D-2: peak 正規化 ────────────────────────────────────────

        [Test]
        public void D2_VocodeNormalized_PeakGreaterThanOne_ScalesTo095()
        {
            using var vocoder = new HiFiGANVocoder(_hifiganModel);
            using var feats = MakeRandomFeatures(1, 250, 1024, seed: 42);

            float[] raw = vocoder.Vocode(feats);
            float rawPeak = 0;
            for (int i = 0; i < raw.Length; i++)
            {
                float v = Mathf.Abs(raw[i]);
                if (v > rawPeak) rawPeak = v;
            }

            float[] normalized = vocoder.VocodeNormalized(feats);
            float normPeak = 0;
            for (int i = 0; i < normalized.Length; i++)
            {
                float v = Mathf.Abs(normalized[i]);
                if (v > normPeak) normPeak = v;
            }

            if (rawPeak > 1.0f)
            {
                Assert.AreEqual(0.95f, normPeak, 0.01f,
                    $"normalized peak should be 0.95 (rawPeak was {rawPeak})");
            }
            else
            {
                // raw が既に範囲内なら同じ
                Assert.AreEqual(rawPeak, normPeak, 1e-3f);
            }
        }

        // ── D-3: 入力 shape の罠 ────────────────────────────────────

        [Test]
        public void D3_Vocode_WrongShape_ThrowsArgumentException()
        {
            using var vocoder = new HiFiGANVocoder(_hifiganModel);

            // (1, dim=1024, T_frame=250) は HiFiGAN にとって誤った channel-first
            // (HiFiGAN は (B, T_frame, dim) channel-last 期待)
            using var wrongFeats = MakeRandomFeatures(1, 1024, 250, seed: 42);

            // ArgumentException か RuntimeException (Sentis 由来) のどちらかが出るべき
            Assert.Catch<Exception>(
                () => vocoder.Vocode(wrongFeats),
                "wrong shape (channel-first) should throw");
        }

        [Test]
        public void D3b_Vocode_CorrectShape_DoesNotThrow()
        {
            using var vocoder = new HiFiGANVocoder(_hifiganModel);
            using var correctFeats = MakeRandomFeatures(1, 250, 1024, seed: 42);
            Assert.DoesNotThrow(() =>
            {
                float[] _ = vocoder.Vocode(correctFeats);
            });
        }

        // ── Helpers ───────────────────────────────────────────────────

        static Tensor<float> MakeRandomFeatures(int b, int dim1, int dim2, int seed)
        {
            var rng = new System.Random(seed);
            int total = b * dim1 * dim2;
            float[] data = new float[total];
            for (int i = 0; i < total; i++)
                data[i] = (float)(rng.NextDouble() * 2.0 - 1.0);
            return new Tensor<float>(new TensorShape(b, dim1, dim2), data);
        }
    }
}
