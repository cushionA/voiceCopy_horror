// VcEndToEndTesterWindow.cs — Phase 8 着手: 実 WAV → 実 WAV のエンドツーエンド変換テスト
// voice_horror Phase 8 (2026-05-09)
//
// Goal:
//   Editor 上で target / source AudioClip を切り替えながら kNN-VC の変換結果を
//   即座に試聴できるようにする。Tools > kNN-VC > End-to-End Tester から開く。
//
// Flow:
//   1. target AudioClip → WavLM.ExtractFeatures → MatchingSetPool.Append
//   2. source AudioClip → WavLM.ExtractFeatures → query
//   3. KnnVcConverter.Convert(query, targetPool, weights=1.0)
//   4. HiFiGANVocoder.VocodeNormalized
//   5. WavWriter.Save → VcTestOutput/{file}.wav (リポジトリ直下) を Reveal
//
// 関連: VoiceConversionService (ランタイム想定のファサード)、本 window はその dev tool 版。

using System;
using System.Diagnostics;
using System.IO;
using Unity.InferenceEngine;
using UnityEditor;
using UnityEngine;
using VoiceHorror.KnnVc;
using VoiceHorror.VC;
using Debug = UnityEngine.Debug;

namespace VoiceHorror.KnnVc.EditorTools
{
    /// <summary>
    /// kNN-VC End-to-End Tester EditorWindow。
    /// target / source の AudioClip を入れ替えながら変換結果を WAV 出力する。
    /// </summary>
    public class VcEndToEndTesterWindow : EditorWindow
    {
        const int k_HiftSampleRate = 16000;
        const string k_OutputDirRelative = "VcTestOutput"; // リポジトリ直下

        // 既定アセット名 (auto-find に使う)
        const string k_DefaultWavLM = "wavlm_large_layer6";
        const string k_DefaultHiFiGAN = "hifigan_wavlm_layer6";
        const string k_DefaultTarget = "my_sampleVoice";
        const string k_DefaultSource = "107";

        ModelAsset _wavlm;
        ModelAsset _hifigan;
        AudioClip _targetClip;
        AudioClip _sourceClip;
        BackendType _backend = BackendType.GPUCompute;
        int _topK = 4;
        string _outputFile = "knn_vc_output.wav";

        // 直近の実行結果
        string _lastOutputPath;
        string _lastSummary;
        bool _isRunning;

        // ── Menu ─────────────────────────────────────────────────────────

        [MenuItem("Tools/kNN-VC/End-to-End Tester")]
        public static void Open()
        {
            var w = GetWindow<VcEndToEndTesterWindow>("kNN-VC E2E Tester");
            w.minSize = new Vector2(380, 320);
        }

        void OnEnable() => TryAutoFind();

        // ── GUI ──────────────────────────────────────────────────────────

        void OnGUI()
        {
            EditorGUILayout.HelpBox(
                "target=声色を移したい先 (e.g. 少女声優) / source=喋らせる内容 (e.g. プレイヤー声)。\n" +
                "α=1.0 (target only) で変換し、結果を VcTestOutput/ に WAV 出力します。",
                MessageType.Info);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Models", EditorStyles.boldLabel);
            _wavlm = (ModelAsset)EditorGUILayout.ObjectField("WavLM", _wavlm, typeof(ModelAsset), false);
            _hifigan = (ModelAsset)EditorGUILayout.ObjectField("HiFiGAN", _hifigan, typeof(ModelAsset), false);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Audio (差し替え可)", EditorStyles.boldLabel);
            _targetClip = (AudioClip)EditorGUILayout.ObjectField("Target (matching set)", _targetClip, typeof(AudioClip), false);
            _sourceClip = (AudioClip)EditorGUILayout.ObjectField("Source (query)",        _sourceClip, typeof(AudioClip), false);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Settings", EditorStyles.boldLabel);
            _backend = (BackendType)EditorGUILayout.EnumPopup("Backend", _backend);
            _topK = EditorGUILayout.IntSlider("TopK", _topK, 1, 16);
            _outputFile = EditorGUILayout.TextField("Output Filename", _outputFile);

            EditorGUILayout.Space();
            using (new EditorGUI.DisabledScope(_isRunning))
            {
                if (GUILayout.Button(_isRunning ? "Running..." : "Run Conversion", GUILayout.Height(32)))
                {
                    RunConversion();
                }
                if (GUILayout.Button("Re-Auto-Find Defaults"))
                {
                    _wavlm = null; _hifigan = null; _targetClip = null; _sourceClip = null;
                    TryAutoFind();
                }
            }

            if (!string.IsNullOrEmpty(_lastSummary))
            {
                EditorGUILayout.Space();
                EditorGUILayout.LabelField("Last Result", EditorStyles.boldLabel);
                EditorGUILayout.HelpBox(_lastSummary, MessageType.None);
                if (!string.IsNullOrEmpty(_lastOutputPath) && File.Exists(_lastOutputPath))
                {
                    if (GUILayout.Button("Reveal Output WAV"))
                        EditorUtility.RevealInFinder(_lastOutputPath);
                }
            }
        }

        // ── Auto-find ────────────────────────────────────────────────────

        void TryAutoFind()
        {
            if (_wavlm == null)      _wavlm      = FindAssetByName<ModelAsset>(k_DefaultWavLM);
            if (_hifigan == null)    _hifigan    = FindAssetByName<ModelAsset>(k_DefaultHiFiGAN);
            if (_targetClip == null) _targetClip = FindAssetByName<AudioClip>(k_DefaultTarget);
            if (_sourceClip == null) _sourceClip = FindAssetByName<AudioClip>(k_DefaultSource);
        }

        static T FindAssetByName<T>(string nameWithoutExt) where T : UnityEngine.Object
        {
            string filter = $"{nameWithoutExt} t:{typeof(T).Name}";
            string[] guids = AssetDatabase.FindAssets(filter);
            // 完全一致を優先
            foreach (string g in guids)
            {
                string path = AssetDatabase.GUIDToAssetPath(g);
                if (Path.GetFileNameWithoutExtension(path) == nameWithoutExt)
                {
                    var a = AssetDatabase.LoadAssetAtPath<T>(path);
                    if (a != null) return a;
                }
            }
            // フォールバック: 1 件目
            if (guids.Length > 0)
                return AssetDatabase.LoadAssetAtPath<T>(AssetDatabase.GUIDToAssetPath(guids[0]));
            return null;
        }

        // ── Conversion ───────────────────────────────────────────────────

        void RunConversion()
        {
            if (!ValidateInputs(out string error))
            {
                EditorUtility.DisplayDialog("kNN-VC E2E Tester", error, "OK");
                return;
            }

            _isRunning = true;
            try
            {
                Stopwatch swTotal = Stopwatch.StartNew();
                Stopwatch swStep = new Stopwatch();

                using var extractor = new WavLMFeatureExtractor(_wavlm, _backend);
                using var vocoder = new HiFiGANVocoder(_hifigan, _backend);
                var converter = new KnnVcConverter { TopK = _topK };

                // Step 1: target → MatchingSetPool
                Debug.Log($"[VcE2E] target='{_targetClip.name}' ({_targetClip.length:F1}s @ {_targetClip.frequency}Hz, {_targetClip.channels}ch)");
                swStep.Restart();
                using var targetFeats3D = extractor.ExtractFeatures(_targetClip);
                long targetExtractMs = swStep.ElapsedMilliseconds;
                int tFramesT = targetFeats3D.shape[1];
                int dim = targetFeats3D.shape[2];
                float[] targetFlat = targetFeats3D.DownloadToArray();
                using var targetFeats2D = new Tensor<float>(new TensorShape(tFramesT, dim), targetFlat);
                var targetPool = new MatchingSetPool("target");
                targetPool.Append(targetFeats2D);
                Debug.Log($"[VcE2E] Target pool: {targetPool.FrameCount} frames (extract={targetExtractMs}ms)");

                // Step 2: source → query
                Debug.Log($"[VcE2E] source='{_sourceClip.name}' ({_sourceClip.length:F1}s @ {_sourceClip.frequency}Hz, {_sourceClip.channels}ch)");
                swStep.Restart();
                using var srcFeats3D = extractor.ExtractFeatures(_sourceClip);
                long srcExtractMs = swStep.ElapsedMilliseconds;
                int tFramesS = srcFeats3D.shape[1];
                float[] srcFlat = srcFeats3D.DownloadToArray();
                using var query2D = new Tensor<float>(new TensorShape(tFramesS, dim), srcFlat);
                Debug.Log($"[VcE2E] Source query: {tFramesS} frames (extract={srcExtractMs}ms)");

                // Step 3: kNN convert (alpha=1.0 → target only)
                using var pool2D = targetPool.ToTensor();
                float[] weights = new float[targetPool.FrameCount];
                for (int i = 0; i < weights.Length; i++) weights[i] = 1f;

                swStep.Restart();
                using var converted2D = converter.Convert(query2D, pool2D, weights);
                long knnMs = swStep.ElapsedMilliseconds;
                Debug.Log($"[VcE2E] kNN match top-{_topK}: {knnMs}ms ({tFramesS} query × {targetPool.FrameCount} ms frames)");

                // Step 4: vocode
                int tF = converted2D.shape[0], dimC = converted2D.shape[1];
                float[] convFlat = converted2D.DownloadToArray();
                using var feats3D = new Tensor<float>(new TensorShape(1, tF, dimC), convFlat);
                swStep.Restart();
                float[] audio = vocoder.VocodeNormalized(feats3D);
                long vocodeMs = swStep.ElapsedMilliseconds;
                Debug.Log($"[VcE2E] Vocode: {vocodeMs}ms → {audio.Length} samples");

                // NaN/Inf 健全性チェック
                int nanCount = 0;
                for (int i = 0; i < audio.Length; i++)
                {
                    if (float.IsNaN(audio[i]) || float.IsInfinity(audio[i])) nanCount++;
                }

                // Step 5: WAV 出力
                string repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
                string outDir = Path.Combine(repoRoot, k_OutputDirRelative);
                Directory.CreateDirectory(outDir);
                string outPath = Path.Combine(outDir, _outputFile);
                WavWriter.Save(outPath, audio, k_HiftSampleRate);

                swTotal.Stop();
                float duration = audio.Length / (float)k_HiftSampleRate;
                _lastOutputPath = outPath;
                _lastSummary =
                    $"OK: {outPath}\n" +
                    $"duration={duration:F2}s, nan/inf={nanCount}\n" +
                    $"target_extract={targetExtractMs}ms, src_extract={srcExtractMs}ms, " +
                    $"knn={knnMs}ms, vocode={vocodeMs}ms\n" +
                    $"total={swTotal.ElapsedMilliseconds}ms";
                Debug.Log($"[VcE2E] {_lastSummary}");

                if (nanCount > 0)
                    Debug.LogWarning($"[VcE2E] Output contains {nanCount} NaN/Inf samples");

                EditorUtility.RevealInFinder(outPath);
            }
            catch (Exception ex)
            {
                _lastSummary = $"FAILED: {ex.GetType().Name}: {ex.Message}";
                Debug.LogError($"[VcE2E] {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");
            }
            finally
            {
                _isRunning = false;
                Repaint();
            }
        }

        bool ValidateInputs(out string error)
        {
            if (_wavlm == null)      { error = "WavLM ModelAsset が未指定です。"; return false; }
            if (_hifigan == null)    { error = "HiFiGAN ModelAsset が未指定です。"; return false; }
            if (_targetClip == null) { error = "Target AudioClip が未指定です。"; return false; }
            if (_sourceClip == null) { error = "Source AudioClip が未指定です。"; return false; }
            if (string.IsNullOrWhiteSpace(_outputFile))
            {
                error = "Output Filename が空です。"; return false;
            }
            error = null;
            return true;
        }
    }
}
