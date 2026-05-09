// VoiceConversionBenchEditor.cs — VoiceConversionBench のカスタム Inspector
// voice_horror Phase 4 (2026-05-07)

using UnityEditor;
using UnityEngine;
using VoiceHorror.VC;

namespace VoiceHorror.Editor
{
    [CustomEditor(typeof(VoiceConversionBench))]
    public class VoiceConversionBenchEditor : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            EditorGUILayout.Space(10);
            EditorGUILayout.LabelField("──────────────────────────────", EditorStyles.centeredGreyMiniLabel);

            VoiceConversionBench bench = (VoiceConversionBench)target;

            bool canRun = Application.isPlaying && bench.pipeline != null
                          && bench.sourceClip != null && bench.targetRefClip != null;

            if (!Application.isPlaying)
            {
                EditorGUILayout.HelpBox("Play モードで実行してください。", MessageType.Info);
            }
            else if (bench.pipeline == null)
            {
                EditorGUILayout.HelpBox("VoiceConversionPipeline コンポーネントを同じ GameObject にアタッチしてください。", MessageType.Warning);
            }
            else if (bench.sourceClip == null || bench.targetRefClip == null)
            {
                EditorGUILayout.HelpBox("Source Clip と Target Ref Clip を設定してください。", MessageType.Warning);
            }

            EditorGUILayout.Space(4);

            // ── 変換実行ボタン ──────────────────────────────────────────
            GUI.enabled = canRun;
            GUIStyle btnStyle = new GUIStyle(GUI.skin.button) { fontSize = 13, fontStyle = FontStyle.Bold };
            Color prev = GUI.backgroundColor;
            GUI.backgroundColor = canRun ? new Color(0.4f, 0.85f, 0.4f) : Color.grey;

            if (GUILayout.Button("▶  変換実行 (Source → Target)", btnStyle, GUILayout.Height(40)))
                bench.TriggerConvert();

            GUI.backgroundColor = prev;
            GUI.enabled = true;

            EditorGUILayout.Space(4);

            // ── Embedding だけ抽出ボタン ────────────────────────────────
            GUI.enabled = Application.isPlaying && bench.pipeline != null && bench.targetRefClip != null;
            if (GUILayout.Button("Extract Target Embedding のみキャッシュ", GUILayout.Height(28)))
                bench.TriggerExtractEmb();
            GUI.enabled = true;

            // ── 変換結果の再生ボタン ────────────────────────────────────
            EditorGUILayout.Space(4);
            bool hasResult = Application.isPlaying && bench.lastResult != null && bench.outputSource != null;
            GUI.enabled = hasResult;
            if (GUILayout.Button("▶  変換結果を再生", GUILayout.Height(28)))
                bench.outputSource.Play();
            GUI.enabled = true;

            // ── 直近結果サマリ ──────────────────────────────────────────
            if (bench.lastResult != null)
            {
                EditorGUILayout.Space(6);
                EditorGUILayout.HelpBox(
                    $"直近変換: {bench.lastConvertMs:F0}ms  →  {bench.lastResult.length:F2}s @ {bench.lastResult.frequency}Hz",
                    MessageType.None);
            }
        }
    }
}
