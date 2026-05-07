// SentisSpikeSetupPhase4.cs — Editor helper for Phase 4 offline VC bench setup
// voice_horror Phase 4 (2026-05-07)
//
// Adds "Tools/Sentis Spike/Setup VC Bench Scene (Phase 4)" menu item.
// Creates a scene with VoiceConversionPipeline + VoiceConversionBench components.
// Inspector で Source / Target AudioClip をアタッチして「変換実行」ボタンで変換できる。

using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using Unity.InferenceEngine;
using VoiceHorror.VC;

public static class SentisSpikeSetupPhase4
{
    const string k_ScenePath     = "Assets/SentisSpike/SentisVCBench.unity";
    const string k_CampplusPath  = "Assets/SentisSpike/Models/campplus.onnx";
    const string k_TokenizerPath = "Assets/SentisSpike/Models/speech_tokenizer_v3.onnx";
    const string k_DitPath       = "Assets/SentisSpike/Models/flow.decoder.estimator.merged.fp32.onnx";
    const string k_HiftPath      = "Assets/SentisSpike/Models/hift.fixed.fp32.onnx";

    [MenuItem("Tools/Sentis Spike/Setup VC Bench Scene (Phase 4)")]
    public static void SetupPhase4()
    {
        ModelAsset campplus  = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_CampplusPath);
        ModelAsset tokenizer = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_TokenizerPath);
        ModelAsset dit       = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_DitPath);
        ModelAsset hift      = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_HiftPath);

        Debug.Log($"[Phase4Setup] Models: campplus={campplus != null}, " +
                  $"tokenizer={tokenizer != null}, dit={dit != null}, hift={hift != null}");

        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        // ── VCPipeline + Bench を同じ GameObject に載せる ──
        var benchGO  = new GameObject("VCBench");

        var pipeline = benchGO.AddComponent<VoiceConversionPipeline>();
        pipeline.campplusModel  = campplus;
        pipeline.tokenizerModel = tokenizer;
        pipeline.ditModel       = dit;
        pipeline.hiftModel      = hift;
        pipeline.odeSteps       = 10;
        pipeline.backend        = BackendType.GPUCompute;
        EditorUtility.SetDirty(pipeline);

        // AudioSource (RequireComponent で自動追加されるが明示的に設定)
        AudioSource audioSrc = benchGO.AddComponent<AudioSource>();
        audioSrc.playOnAwake = false;
        EditorUtility.SetDirty(audioSrc);

        VoiceConversionBench bench = benchGO.AddComponent<VoiceConversionBench>();
        bench.pipeline      = pipeline;
        bench.outputSource  = audioSrc;
        bench.playOnConvert = true;
        bench.convertOnStart = false;
        // sourceClip / targetRefClip は Inspector で手動アタッチ
        EditorUtility.SetDirty(bench);

        EditorSceneManager.MarkSceneDirty(scene);
        bool saved = EditorSceneManager.SaveScene(scene, k_ScenePath);
        Debug.Log($"[Phase4Setup] Scene saved: {saved} at {k_ScenePath}");
        Debug.Log("[Phase4Setup] 手順: Inspector で Source Clip と Target Ref Clip を設定 → Play → 「変換実行」ボタン");
    }

    [MenuItem("Tools/Sentis Spike/Open VC Bench Scene (Phase 4)")]
    public static void OpenBenchScene()
    {
        EditorSceneManager.OpenScene(k_ScenePath, OpenSceneMode.Single);
    }
}
