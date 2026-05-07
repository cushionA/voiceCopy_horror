// SentisSpikeSetupPhase3.cs — Editor helper for Phase 3 test scene setup
// voice_horror Phase 3 (2026-05-07)
//
// Adds "Tools/Sentis Spike/Setup VC Test Scene (Phase 3)" menu item.
// Creates a scene with VoiceConversionPipeline + VoiceConversionTest components.

using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using Unity.InferenceEngine;
using VoiceHorror.VC;

public static class SentisSpikeSetupPhase3
{
    const string k_ScenePath    = "Assets/SentisSpike/SentisTest.unity";
    const string k_CampplusPath = "Assets/SentisSpike/Models/campplus.onnx";
    const string k_TokenizerPath= "Assets/SentisSpike/Models/speech_tokenizer_v3.onnx";
    const string k_DitPath      = "Assets/SentisSpike/Models/flow.decoder.estimator.fp32.onnx";
    const string k_HiftPath     = "Assets/SentisSpike/Models/hift.fp32.onnx";

    [MenuItem("Tools/Sentis Spike/Setup VC Test Scene (Phase 3)")]
    public static void SetupPhase3()
    {
        var campplus  = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_CampplusPath);
        var tokenizer = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_TokenizerPath);
        var dit       = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_DitPath);
        var hift      = AssetDatabase.LoadAssetAtPath<ModelAsset>(k_HiftPath);

        Debug.Log($"[Phase3Setup] Models found: campplus={campplus != null}, " +
                  $"tokenizer={tokenizer != null}, dit={dit != null}, hift={hift != null}");

        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        // ── VoiceConversionPipeline ──
        var pipelineGO = new GameObject("VCPipeline");
        var pipeline   = pipelineGO.AddComponent<VoiceConversionPipeline>();
        pipeline.campplusModel  = campplus;
        pipeline.tokenizerModel = tokenizer;
        pipeline.ditModel       = dit;
        pipeline.hiftModel      = hift;
        pipeline.odeSteps       = 10;
        pipeline.backend        = BackendType.GPUCompute;
        EditorUtility.SetDirty(pipeline);

        // ── SpeakerMorphController ──
        var morphGO = new GameObject("SpeakerMorph");
        var morph   = morphGO.AddComponent<SpeakerMorphController>();
        morph.morphSpeedPerVoice = 0.05f;
        morph.decayHalfLife      = 30f;
        EditorUtility.SetDirty(morph);

        // ── VoiceConversionTest ──
        var testGO   = new GameObject("VCTestRunner");
        var testComp = testGO.AddComponent<VoiceConversionTest>();
        testComp.campplusModel  = campplus;
        testComp.tokenizerModel = tokenizer;
        testComp.ditModel       = dit;
        testComp.hiftModel      = hift;
        testComp.backend        = BackendType.GPUCompute;
        testComp.runOnStart     = true;
        testComp.odeStepsTest   = 3; // fast test (3 steps)
        EditorUtility.SetDirty(testComp);

        EditorSceneManager.MarkSceneDirty(scene);
        bool saved = EditorSceneManager.SaveScene(scene, k_ScenePath);
        Debug.Log($"[Phase3Setup] Scene saved: {saved} at {k_ScenePath}");
        Debug.Log("[Phase3Setup] Press Play to run T1-T5 tests automatically.");
    }

    [MenuItem("Tools/Sentis Spike/Enter Play Mode (VC Test)")]
    public static void EnterPlayMode()
    {
        var scene = EditorSceneManager.GetActiveScene();
        if (scene.path != k_ScenePath)
            EditorSceneManager.OpenScene(k_ScenePath, OpenSceneMode.Single);
        EditorApplication.EnterPlaymode();
    }
}
