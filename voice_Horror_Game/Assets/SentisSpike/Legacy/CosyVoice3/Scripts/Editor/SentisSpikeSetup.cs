// SentisSpikeSetup.cs - Editor 専用セットアップツール
// MenuItem または UniCli の Eval から呼出可能。
// シーンを作成、SentisTestRunner GameObject を配置、ModelAsset をアサインする。

using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using Unity.InferenceEngine;

public static class SentisSpikeSetup
{
    const string CampplusPath   = "Assets/SentisSpike/Models/campplus.onnx";
    const string TokenizerPath  = "Assets/SentisSpike/Models/speech_tokenizer_v3.onnx";
    const string DitPath        = "Assets/SentisSpike/Models/flow.decoder.estimator.fp32.onnx";
    const string HiftPath       = "Assets/SentisSpike/Models/hift.fp32.onnx";
    const string ScenePath      = "Assets/SentisSpike/SentisTest.unity";

    [MenuItem("Tools/Sentis Spike/Setup Test Scene (Phase 2)")]
    public static void SetupTestScene()
    {
        var campplus  = AssetDatabase.LoadAssetAtPath<ModelAsset>(CampplusPath);
        var tokenizer = AssetDatabase.LoadAssetAtPath<ModelAsset>(TokenizerPath);
        var dit       = AssetDatabase.LoadAssetAtPath<ModelAsset>(DitPath);
        var hift      = AssetDatabase.LoadAssetAtPath<ModelAsset>(HiftPath);

        Debug.Log($"[SentisSpikeSetup] campplus={campplus != null}  tokenizer={tokenizer != null}  dit={dit != null}  hift={hift != null}");

        // 新規シーン作成 (DefaultGameObjects = カメラ + ライト)
        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        var go   = new GameObject("SentisTestRunner");
        var comp = go.AddComponent<SentisLoadTest>();

        comp.campplusModel  = campplus;
        comp.tokenizerModel = tokenizer;
        comp.ditModel       = dit;
        comp.hiftModel      = hift;

        // Phase 1 モデルが未インポートの場合は Phase 2 のみ実行
        comp.runPhase1 = (campplus != null && tokenizer != null);
        comp.runPhase2 = true;

        EditorUtility.SetDirty(comp);
        EditorUtility.SetDirty(go);
        EditorSceneManager.MarkSceneDirty(scene);

        var saved = EditorSceneManager.SaveScene(scene, ScenePath);
        Debug.Log($"[SentisSpikeSetup] Scene saved: {saved} at {ScenePath}");
    }

    // Phase 1 専用 (後方互換)
    [MenuItem("Tools/Sentis Spike/Setup Test Scene")]
    public static void SetupTestSceneLegacy()
    {
        SetupTestScene();
    }

    [MenuItem("Tools/Sentis Spike/Run Play Mode Test")]
    public static void RunPlayModeTest()
    {
        if (EditorApplication.isPlaying)
        {
            Debug.LogWarning("[SentisSpikeSetup] Already in Play mode");
            return;
        }
        var current = EditorSceneManager.GetActiveScene();
        if (current.path != ScenePath)
        {
            Debug.Log($"[SentisSpikeSetup] Opening test scene: {ScenePath}");
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        }
        EditorApplication.EnterPlaymode();
    }
}
