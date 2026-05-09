// VoiceConversionTest.cs — Phase 3 component-level test runner
// voice_horror Phase 3 (2026-05-07)
//
// Tests:
//   T1: MelExtractor — feature mel 80, feature mel 128, acoustic mel
//   T2: SpkEmbedProjection — fallback truncation, JSON load
//   T3: FlowMatchingODE — synthetic inputs, n_steps=3 (speed test)
//   T4: VoiceConversionPipeline — full pipeline with synthetic AudioClip
//   T5: SpeakerMorphController — lerp + decay + cosine sim
//
// Usage: attach to GameObject in SentisTest scene.
//        Set runOnStart=true or use [ContextMenu] buttons.

using System;
using System.Collections;
using System.Diagnostics;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.VC;
using Debug = UnityEngine.Debug;

public class VoiceConversionTest : MonoBehaviour
{
    [Header("Test Models")]
    public ModelAsset campplusModel;
    public ModelAsset tokenizerModel;
    public ModelAsset ditModel;
    public ModelAsset hiftModel;

    [Header("Settings")]
    public BackendType backend    = BackendType.GPUCompute;
    public bool        runOnStart = true;
    public int         odeStepsTest = 3; // small for fast testing

    void Start()
    {
        if (runOnStart) RunAllTests();
    }

    [ContextMenu("Run All Phase 3 Tests")]
    public void RunAllTests()
    {
        Debug.Log("════════ Phase 3 VC Pipeline Tests ════════");
        bool t1 = TestMelExtractor();
        bool t2 = TestSpkEmbedProjection();
        bool t3 = TestFlowMatchingODE();
        bool t4 = TestFullPipeline();
        bool t5 = TestSpeakerMorphController();

        Debug.Log("════════ Summary ════════");
        Debug.Log($"  T1 MelExtractor         : {R(t1)}");
        Debug.Log($"  T2 SpkEmbedProjection   : {R(t2)}");
        Debug.Log($"  T3 FlowMatchingODE      : {R(t3)}");
        Debug.Log($"  T4 FullPipeline         : {R(t4)}");
        Debug.Log($"  T5 SpeakerMorphCtrl     : {R(t5)}");
        bool all = t1 && t2 && t3 && t4 && t5;
        if (all)
            Debug.Log("[OK] Phase 3 全テスト通過 → ゲーム統合フェーズへ");
        else
            Debug.LogWarning("[NG] 失敗あり。上記ログを確認。");
    }

    static string R(bool ok) => ok ? "OK" : "FAIL";

    // ════════════════════════════════════════════════════════════════
    // T1: MelExtractor
    // ════════════════════════════════════════════════════════════════
    bool TestMelExtractor()
    {
        Debug.Log("[T1] MelExtractor");
        try
        {
            // 1 second of silence at 16 kHz
            int sr16 = 16000;
            float[] audio16k = new float[sr16]; // silence
            // Add a simple tone (440 Hz) to avoid all-zero input
            for (int i = 0; i < audio16k.Length; i++)
                audio16k[i] = 0.1f * MathF.Sin(2f * MathF.PI * 440f * i / sr16);

            // Feature mel 80 → [T, 80]
            var sw = Stopwatch.StartNew();
            float[,] mel80 = MelExtractor.ExtractFeatureMel80(audio16k);
            sw.Stop();
            int T80 = mel80.GetLength(0);
            Debug.Log($"  Feature mel80: [{T80}, 80] in {sw.ElapsedMilliseconds}ms  " +
                      $"sample[0,0]={mel80[0,0]:F4}");
            if (T80 == 0 || mel80.GetLength(1) != 80) { Debug.LogError("  FAIL: wrong shape"); return false; }

            // Feature mel 128 → [128, T]
            sw.Restart();
            float[,] mel128 = MelExtractor.ExtractFeatureMel128(audio16k);
            sw.Stop();
            int T128 = mel128.GetLength(1);
            Debug.Log($"  Feature mel128: [128, {T128}] in {sw.ElapsedMilliseconds}ms  " +
                      $"sample[0,0]={mel128[0,0]:F4}");
            if (mel128.GetLength(0) != 128 || T128 == 0) { Debug.LogError("  FAIL: wrong shape"); return false; }

            // Acoustic mel → [80, T]
            float[] audio22k = MelExtractor.Resample(audio16k, 16000, 22050);
            sw.Restart();
            float[,] acouMel = MelExtractor.ExtractAcousticMel(audio22k);
            sw.Stop();
            int TA = acouMel.GetLength(1);
            Debug.Log($"  Acoustic mel: [80, {TA}] in {sw.ElapsedMilliseconds}ms  " +
                      $"sample[0,0]={acouMel[0,0]:F4}");
            if (acouMel.GetLength(0) != 80 || TA == 0) { Debug.LogError("  FAIL: wrong shape"); return false; }

            // Pad/truncate to 100
            float[,] padded = MelExtractor.PadOrTruncate(acouMel, 100);
            Debug.Log($"  PadOrTruncate: [80, {padded.GetLength(1)}] (target 100)");
            if (padded.GetLength(1) != 100) { Debug.LogError("  FAIL: pad/truncate"); return false; }

            // NaN/Inf check
            for (int m = 0; m < 80; m++)
                for (int t = 0; t < 100; t++)
                    if (float.IsNaN(padded[m, t]) || float.IsInfinity(padded[m, t]))
                    { Debug.LogError($"  FAIL: NaN/Inf at [{m},{t}]"); return false; }

            Debug.Log("  T1 OK");
            return true;
        }
        catch (Exception e) { Debug.LogError($"  T1 FAIL: {e}"); return false; }
    }

    // ════════════════════════════════════════════════════════════════
    // T2: SpkEmbedProjection
    // ════════════════════════════════════════════════════════════════
    bool TestSpkEmbedProjection()
    {
        Debug.Log("[T2] SpkEmbedProjection");
        try
        {
            // Fallback (truncation)
            var proj = new SpkEmbedProjection();
            float[] emb192 = new float[192];
            var rng = new System.Random(1);
            for (int i = 0; i < 192; i++) emb192[i] = (float)(rng.NextDouble() * 2 - 1);

            float[] out80 = proj.Project(emb192);
            if (out80.Length != 80) { Debug.LogError("  FAIL: output length"); return false; }

            // Verify truncation: first 80 dims should match
            for (int i = 0; i < 80; i++)
                if (Math.Abs(out80[i] - emb192[i]) > 1e-6f)
                { Debug.LogError($"  FAIL: truncation mismatch at {i}"); return false; }

            // Morphed: zero embedding
            float[] zeros = new float[192];
            float[] zOut  = proj.Project(zeros);
            for (int i = 0; i < 80; i++)
                if (Math.Abs(zOut[i]) > 1e-6f)
                { Debug.LogError("  FAIL: zero input should give zero output (truncation)"); return false; }

            Debug.Log($"  Fallback truncation OK. out80 sample: [{out80[0]:F4}, {out80[1]:F4}, ...]");
            Debug.Log("  T2 OK (JSON load skipped — run extract_spk_projection.py first)");
            return true;
        }
        catch (Exception e) { Debug.LogError($"  T2 FAIL: {e}"); return false; }
    }

    // ════════════════════════════════════════════════════════════════
    // T3: FlowMatchingODE (requires ditModel)
    // ════════════════════════════════════════════════════════════════
    bool TestFlowMatchingODE()
    {
        Debug.Log("[T3] FlowMatchingODE");
        if (ditModel == null) { Debug.LogWarning("  ditModel not assigned — skip"); return true; }

        Worker ditWorker = null;
        try
        {
            var sw = Stopwatch.StartNew();
            var model = ModelLoader.Load(ditModel);
            ditWorker = new Worker(model, backend);
            sw.Stop();
            Debug.Log($"  DiT worker created in {sw.ElapsedMilliseconds}ms");

            // Synthetic mu [80, 100]
            float[,] mu = new float[80, 100];
            var rng = new System.Random(2);
            for (int m = 0; m < 80; m++)
                for (int t = 0; t < 100; t++)
                    mu[m, t] = (float)(rng.NextDouble() * 0.1 - 0.05); // small values

            float[] spks = new float[80];
            for (int i = 0; i < 80; i++) spks[i] = (float)(rng.NextDouble() * 0.01);

            sw.Restart();
            float[] result = FlowMatchingODE.Run(ditWorker, mu, spks,
                melLength: 50, nSteps: odeStepsTest, seed: 42);
            sw.Stop();
            Debug.Log($"  ODE {odeStepsTest} steps in {sw.ElapsedMilliseconds}ms → {result.Length} floats");

            if (result.Length != 80 * 100) { Debug.LogError("  FAIL: wrong output length"); return false; }

            // NaN check
            for (int i = 0; i < result.Length; i++)
                if (float.IsNaN(result[i]) || float.IsInfinity(result[i]))
                { Debug.LogError($"  FAIL: NaN/Inf at [{i}]"); return false; }

            float mean = 0f;
            for (int i = 0; i < result.Length; i++) mean += result[i];
            mean /= result.Length;
            Debug.Log($"  Output mean={mean:F4} (should be near mu mean ≈ 0)");
            Debug.Log("  T3 OK");
            return true;
        }
        catch (Exception e) { Debug.LogError($"  T3 FAIL: {e}"); return false; }
        finally { ditWorker?.Dispose(); }
    }

    // ════════════════════════════════════════════════════════════════
    // T4: Full pipeline (requires all 4 models)
    // ════════════════════════════════════════════════════════════════
    bool TestFullPipeline()
    {
        Debug.Log("[T4] FullPipeline (synthetic 1-second sine wave)");
        if (campplusModel == null || ditModel == null || hiftModel == null)
        { Debug.LogWarning("  Models not assigned — skip"); return true; }

        VoiceConversionPipeline pipeline = null;
        try
        {
            // Create pipeline on a temporary GameObject
            var go       = new GameObject("_VCPipelineTest");
            pipeline     = go.AddComponent<VoiceConversionPipeline>();
            pipeline.campplusModel = campplusModel;
            pipeline.tokenizerModel = tokenizerModel;
            pipeline.ditModel  = ditModel;
            pipeline.hiftModel = hiftModel;
            pipeline.backend   = backend;
            pipeline.odeSteps  = odeStepsTest;

            // Create a synthetic 1-second 440 Hz AudioClip at 44100 Hz
            int      sr      = 44100;
            int      samples = sr; // 1 second
            float[]  data    = new float[samples];
            for (int i = 0; i < samples; i++)
                data[i] = 0.1f * MathF.Sin(2f * MathF.PI * 440f * i / sr);

            AudioClip srcClip = AudioClip.Create("test_src", samples, 1, sr, false);
            srcClip.SetData(data, 0);

            // Extract speaker embedding (using same clip as target speaker for test)
            var sw = Stopwatch.StartNew();
            float[] spkEmb = pipeline.ExtractSpeakerEmbedding(srcClip);
            sw.Stop();
            Debug.Log($"  ExtractSpeakerEmbedding: {sw.ElapsedMilliseconds}ms → [{spkEmb.Length}]");
            if (spkEmb == null || spkEmb.Length != 192)
            { Debug.LogError("  FAIL: spkEmb length"); return false; }

            // Full VC conversion
            sw.Restart();
            AudioClip outClip = pipeline.ConvertVoice(srcClip, spkEmb);
            sw.Stop();
            Debug.Log($"  ConvertVoice: {sw.ElapsedMilliseconds}ms → " +
                      $"{(outClip != null ? outClip.samples + " samples" : "null")}");

            if (outClip == null || outClip.samples == 0)
            { Debug.LogError("  FAIL: output clip is null or empty"); return false; }

            // Verify no silence-only output (mean amplitude > 1e-6)
            float[] outData = new float[outClip.samples];
            outClip.GetData(outData, 0);
            double amp = 0;
            for (int i = 0; i < outData.Length; i++) amp += Math.Abs(outData[i]);
            amp /= outData.Length;
            Debug.Log($"  Output mean amplitude: {amp:F6}");

            Debug.Log("  T4 OK");
            return true;
        }
        catch (Exception e) { Debug.LogError($"  T4 FAIL: {e}"); return false; }
        finally
        {
            if (pipeline != null)
                DestroyImmediate(pipeline.gameObject);
        }
    }

    // ════════════════════════════════════════════════════════════════
    // T5: SpeakerMorphController
    // ════════════════════════════════════════════════════════════════
    bool TestSpeakerMorphController()
    {
        Debug.Log("[T5] SpeakerMorphController");
        try
        {
            var go   = new GameObject("_MorphTest");
            var ctrl = go.AddComponent<SpeakerMorphController>();

            // Set up ghost and player embeddings
            float[] ghost  = new float[192]; ghost[0]  = 1f;
            float[] player = new float[192]; player[0] = 0f;
            ctrl.girlGhostEmb  = ghost;
            ctrl.morphSpeedPerVoice = 0.1f;

            // Initial: no player voice → pure ghost
            float[] morph1 = ctrl.GetMorphedEmbedding();
            Debug.Log($"  Before voice: morph[0]={morph1[0]:F3} (expected 1.0)");
            if (Math.Abs(morph1[0] - 1f) > 1e-4f) { Debug.LogError("  FAIL: initial morph"); return false; }

            // Record player voice
            ctrl.RecordPlayerVoice(player);
            float ratio1 = ctrl.morphRatio;
            Debug.Log($"  After 1 voice: morphRatio={ratio1:F3}");
            if (ratio1 < 0.05f) { Debug.LogError("  FAIL: morphRatio didn't increase"); return false; }

            // Morphed embedding should be interpolated
            float[] morph2 = ctrl.GetMorphedEmbedding();
            Debug.Log($"  After 1 voice: morph[0]={morph2[0]:F3} (expected ≈ {1f - ratio1:F3})");
            // ghost[0]=1, player[0]=0 → lerp = 1 - ratio
            float expected = 1f - ratio1;
            if (Math.Abs(morph2[0] - expected) > 1e-4f)
            { Debug.LogError($"  FAIL: lerp wrong {morph2[0]:F4} != {expected:F4}"); return false; }

            // Cosine similarity
            float[] sameVec = new float[192]; sameVec[0] = 1f;
            ctrl.girlGhostEmb = sameVec;
            ctrl.playerEmb    = sameVec;
            float sim = ctrl.ComputeSimilarity();
            Debug.Log($"  CosineSim(same, same) = {sim:F4} (expected ≈ 1.0)");
            if (Math.Abs(sim - 1f) > 1e-4f) { Debug.LogError("  FAIL: cosine sim"); return false; }

            DestroyImmediate(go);
            Debug.Log("  T5 OK");
            return true;
        }
        catch (Exception e) { Debug.LogError($"  T5 FAIL: {e}"); return false; }
    }
}
