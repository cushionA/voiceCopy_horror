// SentisLoadTest.cs
// voice_horror — CosyVoice VC コンポーネントを Unity Inference Engine (旧 Sentis) 2.5 で動作検証
//
// 配置: Assets/SentisSpike/Scripts/SentisLoadTest.cs
//
// Phase 1 (2026-05-06): campplus + speech_tokenizer_v3  → 両モデル OK
// Phase 2 (2026-05-07): flow.decoder.estimator (DiT) + hift の Sentis ロード確認
//
// 使い方:
//   1. Inspector で各 ModelAsset をドラッグアサイン
//   2. Play モードで自動実行 (runOnStart=true)
//   3. Console 出力を確認
//
// 期待結果: 4 モデル全て op エラーなし・NaN なし

using System;
using System.Diagnostics;
using Unity.InferenceEngine;
using UnityEngine;
using Debug = UnityEngine.Debug;

public class SentisLoadTest : MonoBehaviour
{
    [Header("Phase 1 Models")]
    [Tooltip("campplus.onnx (Speaker Encoder, 28MB)")]
    public ModelAsset campplusModel;

    [Tooltip("speech_tokenizer_v3.onnx (970MB)")]
    public ModelAsset tokenizerModel;

    [Header("Phase 2 Models")]
    [Tooltip("flow.decoder.estimator.fp32.onnx (DiT, 2.8MB graph + 1265MB data)")]
    public ModelAsset ditModel;

    [Tooltip("hift.fp32.onnx (CausalHiFTGenerator, 328MB)")]
    public ModelAsset hiftModel;

    [Header("Settings")]
    [Tooltip("推論バックエンド。GPUCompute / CPU / GPUPixel")]
    public BackendType backend = BackendType.GPUCompute;

    [Tooltip("テスト用入力の時間長 (campplus mel フレーム数)")]
    public int campplusFrames = 100;

    [Tooltip("テスト用入力の時間長 (tokenizer mel フレーム数)")]
    public int tokenizerFrames = 200;

    [Tooltip("テスト用入力の時間長 (hift mel フレーム数)")]
    public int hiftFrames = 50;

    [Tooltip("Phase 1 テストを実行するか")]
    public bool runPhase1 = true;

    [Tooltip("Phase 2 テストを実行するか")]
    public bool runPhase2 = true;

    [Tooltip("Play モード開始時に自動実行するか")]
    public bool runOnStart = true;

    void Start()
    {
        if (runOnStart) RunFullTest();
    }

    [ContextMenu("Run Full Test")]
    public void RunFullTest()
    {
        Debug.Log("=== Inference Engine (Sentis 2.5) Load Test ===");
        Debug.Log($"Backend: {backend}");
        Debug.Log("");

        bool campplusOK = true;
        bool tokenizerOK = true;
        bool ditOK = true;
        bool hiftOK = true;

        // ── Phase 1 ──
        if (runPhase1)
        {
            Debug.Log("[Phase 1] campplus.onnx");
            campplusOK = (campplusModel != null) ? TestCampplus() : Skip("campplusModel");
            Debug.Log("");

            Debug.Log("[Phase 1] speech_tokenizer_v3.onnx");
            tokenizerOK = (tokenizerModel != null) ? TestTokenizer() : Skip("tokenizerModel");
            Debug.Log("");
        }

        // ── Phase 2 ──
        if (runPhase2)
        {
            Debug.Log("[Phase 2] flow.decoder.estimator.fp32.onnx (DiT)");
            ditOK = (ditModel != null) ? TestDit() : Skip("ditModel");
            Debug.Log("");

            Debug.Log("[Phase 2] hift.fp32.onnx (CausalHiFTGenerator)");
            hiftOK = (hiftModel != null) ? TestHift() : Skip("hiftModel");
            Debug.Log("");
        }

        // ── Summary ──
        Debug.Log("=== Summary ===");
        if (runPhase1)
        {
            Debug.Log($"  campplus.onnx            : {(campplusOK  ? "OK" : "FAIL")}");
            Debug.Log($"  speech_tokenizer_v3      : {(tokenizerOK ? "OK" : "FAIL")}");
        }
        if (runPhase2)
        {
            Debug.Log($"  flow.decoder.estimator   : {(ditOK  ? "OK" : "FAIL")}");
            Debug.Log($"  hift                     : {(hiftOK ? "OK" : "FAIL")}");
        }

        bool allOK = campplusOK && tokenizerOK && ditOK && hiftOK;
        if (allOK)
            Debug.Log("[OK] 全モデルロード成功 → Phase 3 (C# パイプライン実装) へ進行可");
        else
            Debug.LogWarning("[NG] 失敗あり。'Unsupported operator' → Sentis op カバレッジ問題。上記 op を確認して ONNX 修正またはフォールバック検討。");
    }

    // ==========================================================
    // Phase 1: campplus (Speaker Encoder)
    // 入力: [1, T, 80]  float32
    // 出力: [1, 192]    float32
    // ==========================================================
    bool TestCampplus()
    {
        Worker worker = null;
        Tensor<float> input = null;
        try
        {
            var sw = Stopwatch.StartNew();
            var runtime = ModelLoader.Load(campplusModel);
            sw.Stop();
            Debug.Log($"  Load... OK ({sw.ElapsedMilliseconds}ms)");
            DescribeModel(runtime);

            sw.Restart();
            worker = new Worker(runtime, backend);
            sw.Stop();
            Debug.Log($"  Worker... OK ({sw.ElapsedMilliseconds}ms)");

            int B = 1, T = campplusFrames, F = 80;
            input = MakeRandFloat(new TensorShape(B, T, F), 42);
            Debug.Log($"  Input: [{B},{T},{F}]");

            sw.Restart();
            worker.Schedule(input);
            var cloned = (worker.PeekOutput() as Tensor<float>).ReadbackAndClone();
            sw.Stop();
            Debug.Log($"  Forward... OK ({sw.ElapsedMilliseconds}ms)  output={ShapeToString(cloned.shape)}");
            Debug.Log($"  Sample: [{string.Join(", ", PreviewFloat(cloned, 5))}]");

            if (HasNaNOrInf(cloned)) { Debug.LogError("  NaN/Inf detected"); cloned.Dispose(); return false; }
            cloned.Dispose();
            return true;
        }
        catch (Exception e) { LogFail("campplus", e); return false; }
        finally { input?.Dispose(); worker?.Dispose(); }
    }

    // ==========================================================
    // Phase 1: speech_tokenizer_v3 (Conformer + VQ)
    // 入力1: feats [1, 128, T]  float32
    // 入力2: feats_length [1]   int32
    // 出力: indices [?, ?]      int32
    // ==========================================================
    bool TestTokenizer()
    {
        Worker worker = null;
        Tensor<float> feats = null;
        Tensor<int> featsLen = null;
        try
        {
            var sw = Stopwatch.StartNew();
            var runtime = ModelLoader.Load(tokenizerModel);
            sw.Stop();
            Debug.Log($"  Load... OK ({sw.ElapsedMilliseconds}ms)");
            DescribeModel(runtime);

            sw.Restart();
            worker = new Worker(runtime, backend);
            sw.Stop();
            Debug.Log($"  Worker... OK ({sw.ElapsedMilliseconds}ms)");

            int B = 1, F = 128, T = tokenizerFrames;
            feats    = MakeRandFloat(new TensorShape(B, F, T), 43);
            featsLen = new Tensor<int>(new TensorShape(1), new int[] { T });
            Debug.Log($"  Inputs: feats=[{B},{F},{T}], feats_length=[{T}]");

            sw.Restart();
            worker.SetInput("feats", feats);
            worker.SetInput("feats_length", featsLen);
            worker.Schedule();
            var cloned = (worker.PeekOutput("indices") as Tensor<int>).ReadbackAndClone();
            sw.Stop();
            Debug.Log($"  Forward... OK ({sw.ElapsedMilliseconds}ms)  output={ShapeToString(cloned.shape)}");
            Debug.Log($"  Sample: [{string.Join(", ", PreviewInt(cloned, 10))}]");
            cloned.Dispose();
            return true;
        }
        catch (Exception e) { LogFail("speech_tokenizer", e); return false; }
        finally { feats?.Dispose(); featsLen?.Dispose(); worker?.Dispose(); }
    }

    // ==========================================================
    // Phase 2: flow.decoder.estimator (DiT)
    // 入力: x[1,80,100], mask[1,1,100], mu[1,80,100], t[1], spks[1,80], cond[1,80,100]
    // 出力: velocity[1,80,100]  float32
    //
    // 静的 T=100 export (RotaryEmbedding が T を特殊化)。
    // 実推論では C# 側でゼロパディングして T=100 に揃える。
    //
    // op リスト (31): Add, Cast, Concat, Conv, Cos, Equal, Expand, Gather, Gemm,
    //   IsNaN, LayerNormalization, MatMul, Mish, Mul, Neg, Not, Or, Pow, ReduceSum,
    //   Reshape, Sigmoid, Sin, Slice, Softmax, Split, Squeeze, Tanh, Tile,
    //   Transpose, Unsqueeze, Where
    // ==========================================================
    bool TestDit()
    {
        Worker worker = null;
        Tensor<float> x = null, mask = null, mu = null, t = null, spks = null, cond = null;
        try
        {
            var sw = Stopwatch.StartNew();
            var runtime = ModelLoader.Load(ditModel);
            sw.Stop();
            Debug.Log($"  Load... OK ({sw.ElapsedMilliseconds}ms)");
            DescribeModel(runtime);

            sw.Restart();
            worker = new Worker(runtime, backend);
            sw.Stop();
            Debug.Log($"  Worker... OK ({sw.ElapsedMilliseconds}ms)");

            int B = 1, Mel = 80, T = 100;
            x    = MakeRandFloat(new TensorShape(B, Mel, T), 44);
            mask = MakeOnesFloat(new TensorShape(B, 1, T));
            mu   = MakeRandFloat(new TensorShape(B, Mel, T), 45);
            t    = MakeZerosFloat(new TensorShape(B));
            spks = MakeRandFloat(new TensorShape(B, 80), 46);
            cond = MakeRandFloat(new TensorShape(B, Mel, T), 47);
            Debug.Log($"  Inputs: x[{B},{Mel},{T}], mask[{B},1,{T}], mu[{B},{Mel},{T}], t[{B}], spks[{B},80], cond[{B},{Mel},{T}]");

            sw.Restart();
            worker.SetInput("x",    x);
            worker.SetInput("mask", mask);
            worker.SetInput("mu",   mu);
            worker.SetInput("t",    t);
            worker.SetInput("spks", spks);
            worker.SetInput("cond", cond);
            worker.Schedule();
            var cloned = (worker.PeekOutput("velocity") as Tensor<float>).ReadbackAndClone();
            sw.Stop();
            Debug.Log($"  Forward... OK ({sw.ElapsedMilliseconds}ms)  output={ShapeToString(cloned.shape)}");
            Debug.Log($"  Sample: [{string.Join(", ", PreviewFloat(cloned, 5))}]");

            if (HasNaNOrInf(cloned)) { Debug.LogError("  NaN/Inf detected"); cloned.Dispose(); return false; }
            cloned.Dispose();
            return true;
        }
        catch (Exception e) { LogFail("DiT", e); return false; }
        finally
        {
            x?.Dispose(); mask?.Dispose(); mu?.Dispose();
            t?.Dispose(); spks?.Dispose(); cond?.Dispose();
            worker?.Dispose();
        }
    }

    // ==========================================================
    // Phase 2: hift (CausalHiFTGenerator)
    // 入力: speech_feat [1, 80, T_mel]  float32
    // 出力: audio [1, T_audio]          float32
    //
    // op リスト (38): Abs, Add, Cast, Clip, Concat, ConstantOfShape, Conv, Cos,
    //   CumSum, DFT, Div, Elu, Exp, Expand, Floor, Gather, GatherND, Greater,
    //   LeakyRelu, MatMul, Mul, Pad, Pow, Range, ReduceL2, Reshape, Resize,
    //   STFT, ScatterElements, ScatterND, Shape, Sin, Slice, Squeeze, Sub,
    //   Tanh, Transpose, Unsqueeze
    // ==========================================================
    bool TestHift()
    {
        Worker worker = null;
        Tensor<float> speechFeat = null;
        try
        {
            var sw = Stopwatch.StartNew();
            var runtime = ModelLoader.Load(hiftModel);
            sw.Stop();
            Debug.Log($"  Load... OK ({sw.ElapsedMilliseconds}ms)");
            DescribeModel(runtime);

            sw.Restart();
            worker = new Worker(runtime, backend);
            sw.Stop();
            Debug.Log($"  Worker... OK ({sw.ElapsedMilliseconds}ms)");

            int B = 1, Mel = 80, T = hiftFrames;
            speechFeat = MakeRandFloat(new TensorShape(B, Mel, T), 48);
            Debug.Log($"  Input: speech_feat[{B},{Mel},{T}]");

            sw.Restart();
            worker.SetInput("speech_feat", speechFeat);
            worker.Schedule();
            var cloned = (worker.PeekOutput() as Tensor<float>).ReadbackAndClone();
            sw.Stop();
            Debug.Log($"  Forward... OK ({sw.ElapsedMilliseconds}ms)  output={ShapeToString(cloned.shape)}");
            Debug.Log($"  Sample: [{string.Join(", ", PreviewFloat(cloned, 5))}]");

            if (HasNaNOrInf(cloned)) { Debug.LogError("  NaN/Inf detected"); cloned.Dispose(); return false; }
            cloned.Dispose();
            return true;
        }
        catch (Exception e) { LogFail("hift", e); return false; }
        finally { speechFeat?.Dispose(); worker?.Dispose(); }
    }

    // ==========================================================
    // Helpers
    // ==========================================================
    static bool Skip(string fieldName)
    {
        Debug.LogWarning($"  {fieldName} が未アサイン → スキップ");
        return true;
    }

    static void LogFail(string name, Exception e)
    {
        Debug.LogError($"  {name} FAILED: {e.GetType().Name}: {e.Message}");
        Debug.LogError(e.StackTrace);
    }

    static void DescribeModel(Model model)
    {
        foreach (var inp in model.inputs)
            Debug.Log($"  Input:  {inp.name}  shape={inp.shape}  dtype={inp.dataType}");
        foreach (var outp in model.outputs)
            Debug.Log($"  Output: {outp.name}");
    }

    static Tensor<float> MakeRandFloat(TensorShape shape, int seed)
    {
        int n = shape.length;
        float[] data = new float[n];
        var rng = new System.Random(seed);
        for (int i = 0; i < n; i++) data[i] = (float)(rng.NextDouble() * 2 - 1);
        return new Tensor<float>(shape, data);
    }

    static Tensor<float> MakeOnesFloat(TensorShape shape)
    {
        int n = shape.length;
        float[] data = new float[n];
        for (int i = 0; i < n; i++) data[i] = 1f;
        return new Tensor<float>(shape, data);
    }

    static Tensor<float> MakeZerosFloat(TensorShape shape)
    {
        return new Tensor<float>(shape, new float[shape.length]);
    }

    static string ShapeToString(TensorShape s)
    {
        var dims = new string[s.rank];
        for (int i = 0; i < s.rank; i++) dims[i] = s[i].ToString();
        return "[" + string.Join(", ", dims) + "]";
    }

    static string[] PreviewFloat(Tensor<float> t, int n)
    {
        float[] data = t.DownloadToArray();
        int len = Math.Min(n, data.Length);
        string[] preview = new string[len];
        for (int i = 0; i < len; i++) preview[i] = data[i].ToString("F4");
        return preview;
    }

    static string[] PreviewInt(Tensor<int> t, int n)
    {
        int[] data = t.DownloadToArray();
        int len = Math.Min(n, data.Length);
        string[] preview = new string[len];
        for (int i = 0; i < len; i++) preview[i] = data[i].ToString();
        return preview;
    }

    static bool HasNaNOrInf(Tensor<float> t)
    {
        float[] data = t.DownloadToArray();
        int checkLen = Math.Min(data.Length, 1000);
        for (int i = 0; i < checkLen; i++)
            if (float.IsNaN(data[i]) || float.IsInfinity(data[i])) return true;
        return false;
    }
}
