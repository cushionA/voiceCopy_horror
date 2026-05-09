// Eval body for unicli Eval — VcPerfTest シーンを自動構築
// 実行: unicli exec Eval --code "@tools/build_vc_perf_scene.cs" 等の方法で渡す。
// (本ファイルは Assets/ 外なので Unity コンパイル対象外)

ModelAsset FindModel(string n)
{
    var guids = UnityEditor.AssetDatabase.FindAssets(n + " t:ModelAsset");
    foreach (var g in guids)
    {
        var p = UnityEditor.AssetDatabase.GUIDToAssetPath(g);
        if (System.IO.Path.GetFileNameWithoutExtension(p) == n)
            return UnityEditor.AssetDatabase.LoadAssetAtPath<ModelAsset>(p);
    }
    return guids.Length > 0 ? UnityEditor.AssetDatabase.LoadAssetAtPath<ModelAsset>(UnityEditor.AssetDatabase.GUIDToAssetPath(guids[0])) : null;
}

AudioClip FindClip(string n)
{
    var guids = UnityEditor.AssetDatabase.FindAssets(n + " t:AudioClip");
    foreach (var g in guids)
    {
        var p = UnityEditor.AssetDatabase.GUIDToAssetPath(g);
        if (System.IO.Path.GetFileNameWithoutExtension(p) == n)
            return UnityEditor.AssetDatabase.LoadAssetAtPath<AudioClip>(p);
    }
    return guids.Length > 0 ? UnityEditor.AssetDatabase.LoadAssetAtPath<AudioClip>(UnityEditor.AssetDatabase.GUIDToAssetPath(guids[0])) : null;
}

const string scenePath = "Assets/SentisSpike/VcPerfTest.unity";
var newScene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects, UnityEditor.SceneManagement.NewSceneMode.Single);

var wavlm = FindModel("wavlm_large_layer6");
var hifigan = FindModel("hifigan_wavlm_layer6");
var target = FindClip("my_sampleVoice");
var s1 = FindClip("107");
var s2 = FindClip("10");
var s3 = FindClip("2");
var s4 = FindClip("86");

var svcGo = new GameObject("VoiceConversionService");
var svc = svcGo.AddComponent<VoiceHorror.KnnVc.VoiceConversionService>();
var so = new UnityEditor.SerializedObject(svc);
so.FindProperty("wavlmModel").objectReferenceValue = wavlm;
so.FindProperty("hifiganModel").objectReferenceValue = hifigan;
so.ApplyModifiedPropertiesWithoutUndo();

var runnerGo = new GameObject("VcPerfRunner");
var runner = runnerGo.AddComponent<VoiceHorror.KnnVc.VcPerfRunner>();
var rso = new UnityEditor.SerializedObject(runner);
rso.FindProperty("service").objectReferenceValue = svc;
rso.FindProperty("targetClip").objectReferenceValue = target;
var srcs = rso.FindProperty("sources");
srcs.arraySize = 4;
srcs.GetArrayElementAtIndex(0).objectReferenceValue = s1;
srcs.GetArrayElementAtIndex(1).objectReferenceValue = s2;
srcs.GetArrayElementAtIndex(2).objectReferenceValue = s3;
srcs.GetArrayElementAtIndex(3).objectReferenceValue = s4;
rso.FindProperty("batchIterations").intValue = 10;
rso.FindProperty("alpha").floatValue = 1.0f;
rso.ApplyModifiedPropertiesWithoutUndo();

UnityEditor.SceneManagement.EditorSceneManager.SaveScene(newScene, scenePath);

return $"saved={scenePath} wavlm={(wavlm!=null)} hifigan={(hifigan!=null)} target={(target!=null)} s1={(s1!=null)} s2={(s2!=null)} s3={(s3!=null)} s4={(s4!=null)}";
