// Eval body for unicli Eval — VcPerfTest シーンを自動構築
//
// 用途:
//   `voice_Horror_Game/Assets/SentisSpike/VcPerfTest.unity` を再構築する際に
//   unicli Eval 経由で実行するスニペット。シーンを誤削除した / 別環境でセットアップ
//   し直したい場合などに使う。通常運用では既存の .unity ファイルを使えば良い。
//
// 実行方法 (cwd = voice_Horror_Game):
//   unicli exec Eval --code "$(cat ../tools/build_vc_perf_scene.cs)" \
//     --declarations "using Unity.InferenceEngine; using VoiceHorror.KnnVc;"
//
// 動作:
//   1. 新規シーン生成 (Camera + Directional Light)
//   2. wavlm_large_layer6 / hifigan_wavlm_layer6 を auto-find
//   3. my_sampleVoice (target) と 107 / 10 / 2 / 86 (sources) を auto-find
//   4. VoiceConversionService GameObject に ModelAsset 2 個をバインド
//   5. VcPerfRunner GameObject に service / target / sources / batchIterations をバインド
//   6. Assets/SentisSpike/VcPerfTest.unity に保存
//
// 本ファイルは Assets/ 外なので Unity コンパイル対象外 (.cs だが .csproj に含まれない)

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
