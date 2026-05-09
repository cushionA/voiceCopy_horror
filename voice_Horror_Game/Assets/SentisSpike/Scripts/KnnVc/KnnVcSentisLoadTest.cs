// KnnVcSentisLoadTest.cs — Phase 6 T6-3: Sentis 2.5 で kNN-VC 用 ONNX をロード成功するか
// voice_horror Phase 6 (2026-05-09)
//
// Goal:
//   - WavLM Large (338MB) と HiFiGAN (63MB) が Sentis 2.5 でロード成功する
//   - Worker 起動が成功する
//   - dummy input で forward が成功する (NaN/Inf 出ない、shape 正しい)
//
// Usage:
//   1. Editor MenuItem "Tools/kNN-VC Spike/Sentis Load Test" or
//      UniCli `Eval` から KnnVcSentisLoadTest.RunAll()
//   2. Console で各ステージのログを確認

using System;
using System.Diagnostics;
using Unity.InferenceEngine;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace VoiceHorror.KnnVc
{
    public class KnnVcSentisLoadTest : MonoBehaviour
    {
        [Header("ONNX Models")]
        [Tooltip("WavLM Large Layer 6 (338MB)")]
        public ModelAsset wavlmModel;

        [Tooltip("HiFiGAN for WavLM features (63MB)")]
        public ModelAsset hifiganModel;

        [Header("Settings")]
        public BackendType backend = BackendType.GPUCompute;

        // 計測サマリ
        public float wavlmLoadMs;
        public float wavlmForwardMs;
        public float hifiganLoadMs;
        public float hifiganForwardMs;

        // ── ContextMenu / MenuItem entry ──────────────────────────

        [ContextMenu("Run All Tests")]
        public void RunAll()
        {
            Debug.Log("=== kNN-VC Sentis Load Test (Phase 6 T6-3) ===");
            Debug.Log($"Backend: {backend}");

            bool wavlmOK = TestWavLM();
            bool hifiganOK = TestHiFiGAN();

            Debug.Log("=== Summary ===");
            Debug.Log($"WavLM    load={wavlmLoadMs:F0}ms forward={wavlmForwardMs:F0}ms : {(wavlmOK ? "OK" : "FAILED")}");
            Debug.Log($"HiFiGAN  load={hifiganLoadMs:F0}ms forward={hifiganForwardMs:F0}ms : {(hifiganOK ? "OK" : "FAILED")}");
            Debug.Log($"Phase 6 T6-3 (Sentis 互換性検証): {(wavlmOK && hifiganOK ? "PASSED" : "BLOCKED")}");
        }

        // ── WavLM 単体テスト ──────────────────────────────────────

        public bool TestWavLM()
        {
            if (wavlmModel == null)
            {
                Debug.LogError("[WavLM] wavlmModel が未アサインです。Inspector で設定してください。");
                return false;
            }

            Debug.Log($"[WavLM] Loading {wavlmModel.name}...");
            var sw = Stopwatch.StartNew();
            Worker worker = null;
            try
            {
                var model = ModelLoader.Load(wavlmModel);
                worker = new Worker(model, backend);
                wavlmLoadMs = sw.ElapsedMilliseconds;
                Debug.Log($"[WavLM] Loaded in {wavlmLoadMs:F0}ms");

                // dummy input: 5 秒の 16kHz audio = (1, 80000)
                int audioSamples = 80000;
                float[] dummyAudio = new float[audioSamples];
                System.Random rng = new System.Random(42);
                for (int i = 0; i < audioSamples; i++)
                    dummyAudio[i] = (float)(rng.NextDouble() * 2.0 - 1.0); // [-1, 1]

                using var audioTensor = new Tensor<float>(new TensorShape(1, audioSamples), dummyAudio);

                sw.Restart();
                worker.Schedule(audioTensor);
                using var output = (worker.PeekOutput() as Tensor<float>).ReadbackAndClone();
                sw.Stop();
                wavlmForwardMs = sw.ElapsedMilliseconds;

                Debug.Log($"[WavLM] Forward {wavlmForwardMs:F0}ms");
                Debug.Log($"[WavLM] Output shape: {output.shape}");

                // 値域確認 (NaN / Inf チェック)
                float[] outArr = output.DownloadToArray();
                int nanCount = 0, infCount = 0;
                float minV = float.MaxValue, maxV = float.MinValue;
                for (int i = 0; i < outArr.Length; i++)
                {
                    float v = outArr[i];
                    if (float.IsNaN(v)) nanCount++;
                    else if (float.IsInfinity(v)) infCount++;
                    else
                    {
                        if (v < minV) minV = v;
                        if (v > maxV) maxV = v;
                    }
                }

                if (nanCount > 0 || infCount > 0)
                {
                    Debug.LogError($"[WavLM] Output has {nanCount} NaN / {infCount} Inf!");
                    return false;
                }

                Debug.Log($"[WavLM] Output stats: min={minV:F4}, max={maxV:F4}, len={outArr.Length}");
                Debug.Log("[WavLM] ✅ Forward successful, no NaN/Inf");
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[WavLM] FAILED: {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");
                return false;
            }
            finally
            {
                worker?.Dispose();
            }
        }

        // ── HiFiGAN 単体テスト ────────────────────────────────────

        public bool TestHiFiGAN()
        {
            if (hifiganModel == null)
            {
                Debug.LogError("[HiFiGAN] hifiganModel が未アサインです。Inspector で設定してください。");
                return false;
            }

            Debug.Log($"[HiFiGAN] Loading {hifiganModel.name}...");
            var sw = Stopwatch.StartNew();
            Worker worker = null;
            try
            {
                var model = ModelLoader.Load(hifiganModel);
                worker = new Worker(model, backend);
                hifiganLoadMs = sw.ElapsedMilliseconds;
                Debug.Log($"[HiFiGAN] Loaded in {hifiganLoadMs:F0}ms");

                // dummy input: WavLM Layer 6 features = (1, T_frame=250, 1024)
                int tFrame = 250;
                int dim = 1024;
                int totalSize = tFrame * dim;
                float[] dummyFeats = new float[totalSize];
                System.Random rng = new System.Random(42);
                for (int i = 0; i < totalSize; i++)
                    dummyFeats[i] = (float)(rng.NextDouble() * 2.0 - 1.0);

                using var featTensor = new Tensor<float>(new TensorShape(1, tFrame, dim), dummyFeats);

                sw.Restart();
                worker.Schedule(featTensor);
                using var output = (worker.PeekOutput() as Tensor<float>).ReadbackAndClone();
                sw.Stop();
                hifiganForwardMs = sw.ElapsedMilliseconds;

                Debug.Log($"[HiFiGAN] Forward {hifiganForwardMs:F0}ms");
                Debug.Log($"[HiFiGAN] Output shape: {output.shape}");

                float[] outArr = output.DownloadToArray();
                int nanCount = 0, infCount = 0;
                float minV = float.MaxValue, maxV = float.MinValue;
                for (int i = 0; i < outArr.Length; i++)
                {
                    float v = outArr[i];
                    if (float.IsNaN(v)) nanCount++;
                    else if (float.IsInfinity(v)) infCount++;
                    else
                    {
                        if (v < minV) minV = v;
                        if (v > maxV) maxV = v;
                    }
                }

                if (nanCount > 0 || infCount > 0)
                {
                    Debug.LogError($"[HiFiGAN] Output has {nanCount} NaN / {infCount} Inf!");
                    return false;
                }

                Debug.Log($"[HiFiGAN] Output stats: min={minV:F4}, max={maxV:F4}, len={outArr.Length}");
                Debug.Log("[HiFiGAN] ✅ Forward successful, no NaN/Inf");
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[HiFiGAN] FAILED: {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");
                return false;
            }
            finally
            {
                worker?.Dispose();
            }
        }
    }
}
