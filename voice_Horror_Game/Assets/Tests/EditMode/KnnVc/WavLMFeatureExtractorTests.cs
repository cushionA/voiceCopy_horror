// WavLMFeatureExtractorTests.cs — Phase 7 Group A (EditMode)
// voice_horror Phase 7 (2026-05-09)
//
// EditMode で動作確認 (Sentis Worker は EditMode でも動く、Phase 6 KnnVcSentisLoadTest 実証済)。
//
// Coverage:
//   A-1: 16kHz mono float[] からの特徴抽出 (output shape, NaN/Inf)
//   A-2: AudioClip リサンプル経由抽出 (44.1kHz stereo → 16kHz mono)
//   A-3: warmup の効果計測 (cold start vs warmed)
//   A-4: Dispose の正常動作 (ObjectDisposedException, GPU 解放)

using System;
using NUnit.Framework;
using Unity.InferenceEngine;
using UnityEditor;
using UnityEngine;
using VoiceHorror.KnnVc;

namespace VoiceHorror.KnnVc.Tests.EditMode
{
    [TestFixture]
    public class WavLMFeatureExtractorTests
    {
        const string k_WavlmModelPath = "Assets/SentisSpike/Models/KnnVc/wavlm_large_layer6.onnx";
        const int k_SampleRate16k = 16000;

        ModelAsset _wavlmModel;

        [OneTimeSetUp]
        public void OneTimeSetUp()
        {
            _wavlmModel = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_WavlmModelPath);
            if (_wavlmModel == null)
            {
                Assert.Inconclusive(
                    $"WavLM model not found at {k_WavlmModelPath}. " +
                    "Run sandbox export script to generate ONNX (~340MB, gitignored).");
            }
        }

        // ── A-1: 16kHz mono float[] からの特徴抽出 ────────────────────

        [Test]
        public void A1_ExtractFeatures_FromFloatArray_ReturnsValidShape()
        {
            using var extractor = new WavLMFeatureExtractor(_wavlmModel);

            // 5秒の sin wave (440Hz, 16kHz mono)
            float[] audio = GenerateSinWave(durationSec: 5.0f, freqHz: 440f, sampleRate: k_SampleRate16k);

            using var features = extractor.ExtractFeatures(audio);

            Assert.IsNotNull(features, "features tensor should not be null");
            Assert.AreEqual(3, features.shape.rank, "features should be (1, T_frame, 1024)");
            Assert.AreEqual(1, features.shape[0], "batch dim should be 1");
            // T_frame = ceil(audio_samples / 320) approx (WavLM hop)
            // 5sec * 16000 / 320 ≈ 250 frames (実測 249)
            Assert.That(features.shape[1], Is.InRange(240, 260),
                $"T_frame should be ~250 for 5sec audio (got {features.shape[1]})");
            Assert.AreEqual(1024, features.shape[2], "feature dim should be 1024");

            // NaN / Inf チェック
            float[] arr = features.DownloadToArray();
            int nanCount = 0, infCount = 0;
            for (int i = 0; i < arr.Length; i++)
            {
                if (float.IsNaN(arr[i])) nanCount++;
                else if (float.IsInfinity(arr[i])) infCount++;
            }
            Assert.AreEqual(0, nanCount, $"output has {nanCount} NaN values");
            Assert.AreEqual(0, infCount, $"output has {infCount} Inf values");
        }

        // ── A-2: AudioClip リサンプル経由抽出 ───────────────────────

        [Test]
        public void A2_ExtractFeatures_FromAudioClip_ResamplesAndMixesDown()
        {
            using var extractor = new WavLMFeatureExtractor(_wavlmModel);

            // 44.1kHz stereo の AudioClip を作成 (3秒)
            int sr = 44100;
            int channels = 2;
            float duration = 3.0f;
            int samples = (int)(sr * duration);
            var clip = AudioClip.Create("test_stereo_44k", samples, channels, sr, stream: false);
            float[] data = new float[samples * channels];
            for (int i = 0; i < samples; i++)
            {
                float v = Mathf.Sin(2 * Mathf.PI * 440f * i / sr) * 0.5f;
                data[i * channels + 0] = v;
                data[i * channels + 1] = v;
            }
            clip.SetData(data, 0);

            using var features = extractor.ExtractFeatures(clip);

            Assert.IsNotNull(features);
            Assert.AreEqual(3, features.shape.rank);
            Assert.AreEqual(1, features.shape[0]);
            // 3sec @ 16kHz = 48000 samples / 320 hop ≈ 150 frames
            Assert.That(features.shape[1], Is.InRange(140, 160),
                $"T_frame should be ~150 for 3sec audio (got {features.shape[1]})");
            Assert.AreEqual(1024, features.shape[2]);
        }

        // ── A-3: warmup の効果計測 ──────────────────────────────────

        [Test]
        public void A3_Warmup_ReducesSubsequentForwardTime()
        {
            using var extractor = new WavLMFeatureExtractor(_wavlmModel);

            float[] audio = GenerateSinWave(5.0f, 440f, k_SampleRate16k);

            // Cold start measure
            var sw = System.Diagnostics.Stopwatch.StartNew();
            using (var feat1 = extractor.ExtractFeatures(audio)) { }
            sw.Stop();
            long coldMs = sw.ElapsedMilliseconds;

            // Warmed measures (2-3 回平均)
            sw.Restart();
            using (var feat2 = extractor.ExtractFeatures(audio)) { }
            sw.Stop();
            long warmMs1 = sw.ElapsedMilliseconds;

            sw.Restart();
            using (var feat3 = extractor.ExtractFeatures(audio)) { }
            sw.Stop();
            long warmMs2 = sw.ElapsedMilliseconds;

            UnityEngine.Debug.Log($"[A3] Cold={coldMs}ms, Warm1={warmMs1}ms, Warm2={warmMs2}ms");

            Assert.Less(warmMs2, coldMs,
                $"warmed forward ({warmMs2}ms) should be faster than cold ({coldMs}ms)");
            Assert.Less(warmMs2, 200,
                $"warmed forward ({warmMs2}ms) should be < 200ms for 5sec audio (RTX 2070S)");
        }

        [Test]
        public void A3b_WarmupMethod_CompletesWithoutException()
        {
            using var extractor = new WavLMFeatureExtractor(_wavlmModel);

            // Warmup() メソッドが例外なく完走すること
            Assert.DoesNotThrow(() => extractor.Warmup(),
                "Warmup() should complete without throwing");

            // Warmup 後の forward が速い
            float[] audio = GenerateSinWave(5.0f, 440f, k_SampleRate16k);
            var sw = System.Diagnostics.Stopwatch.StartNew();
            using (var feat = extractor.ExtractFeatures(audio)) { }
            sw.Stop();
            Assert.Less(sw.ElapsedMilliseconds, 200,
                $"after Warmup(), forward should be < 200ms (got {sw.ElapsedMilliseconds}ms)");
        }

        // ── A-4: Dispose の正常動作 ──────────────────────────────────

        [Test]
        public void A4_Dispose_ThenExtractFeatures_ThrowsObjectDisposedException()
        {
            var extractor = new WavLMFeatureExtractor(_wavlmModel);
            extractor.Dispose();

            float[] audio = GenerateSinWave(1.0f, 440f, k_SampleRate16k);
            Assert.Throws<ObjectDisposedException>(
                () => extractor.ExtractFeatures(audio),
                "ExtractFeatures after Dispose should throw ObjectDisposedException");
        }

        [Test]
        public void A4b_DoubleDispose_DoesNotThrow()
        {
            var extractor = new WavLMFeatureExtractor(_wavlmModel);
            extractor.Dispose();
            Assert.DoesNotThrow(() => extractor.Dispose(),
                "Double Dispose should be safe (idempotent)");
        }

        // ── Helpers ───────────────────────────────────────────────────

        static float[] GenerateSinWave(float durationSec, float freqHz, int sampleRate)
        {
            int samples = (int)(durationSec * sampleRate);
            float[] audio = new float[samples];
            for (int i = 0; i < samples; i++)
                audio[i] = Mathf.Sin(2 * Mathf.PI * freqHz * i / sampleRate) * 0.5f;
            return audio;
        }
    }
}
