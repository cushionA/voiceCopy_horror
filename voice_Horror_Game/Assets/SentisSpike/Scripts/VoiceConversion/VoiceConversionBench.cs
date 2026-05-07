// VoiceConversionBench.cs — オフライン VC テスト用インスペクタ UI
// voice_horror Phase 4 (2026-05-07)
//
// 使い方:
//   1. GameObject に本コンポーネントをアタッチ
//   2. VoiceConversionPipeline コンポーネントも同じ GameObject にアタッチ
//      (または Pipeline フィールドに参照をドラッグ)
//   3. Source Clip  → 変換したい元音声 (話し方を変えたい音声)
//   4. Target Ref Clip → 変換先スピーカーの参照音声 (この声質に変換する)
//   5. Play モードで Inspector の「変換実行」ボタンを押す
//   6. Console でタイムログを確認、Output Source から変換済み音声が再生される

using System.Collections;
using System.Diagnostics;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace VoiceHorror.VC
{
    [RequireComponent(typeof(AudioSource))]
    public class VoiceConversionBench : MonoBehaviour
    {
        // ── Inspector ─────────────────────────────────────────────────────

        [Header("Pipeline")]
        [Tooltip("同 GameObject の VoiceConversionPipeline。省略時は GetComponent で取得。")]
        public VoiceConversionPipeline pipeline;

        [Header("Input")]
        [Tooltip("変換元音声 (この話し方を Target の声質で喋り直す)")]
        public AudioClip sourceClip;

        [Tooltip("変換先スピーカーの参照音声 (この人の声質にする)")]
        public AudioClip targetRefClip;

        [Header("Output")]
        [Tooltip("変換済み音声を再生する AudioSource。省略時は GetComponent。")]
        public AudioSource outputSource;

        [Tooltip("変換完了後に自動再生する")]
        public bool playOnConvert = true;

        [Header("Settings")]
        [Tooltip("Start() で自動変換を走らせる (Scene 起動直後にテストしたい場合)")]
        public bool convertOnStart;

        [Header("Debug (read-only)")]
        [Tooltip("直近の変換時間 (ms)")]
        public float lastConvertMs;

        [Tooltip("直近の変換結果 AudioClip")]
        public AudioClip lastResult;

        // キャッシュ: targetRefClip が変わったときだけ embedding を再抽出する
        float[]   _cachedTargetEmb;
        AudioClip _cachedTargetRef;

        // ── Lifecycle ─────────────────────────────────────────────────────

        void Awake()
        {
            if (pipeline == null)
                pipeline = GetComponent<VoiceConversionPipeline>();

            if (outputSource == null)
                outputSource = GetComponent<AudioSource>();
        }

        void Start()
        {
            if (convertOnStart)
                StartCoroutine(ConvertCoroutine());
        }

        // ── Public API (Inspector ボタン / ContextMenu から呼ぶ) ───────────

        /// <summary>変換実行 — Play モードで Inspector ボタン or ContextMenu から。</summary>
        [ContextMenu("変換実行")]
        public void TriggerConvert()
        {
            if (!Application.isPlaying)
            {
                Debug.LogWarning("[Bench] Play モードで実行してください。");
                return;
            }
            StartCoroutine(ConvertCoroutine());
        }

        /// <summary>Target Embedding だけ先に抽出してキャッシュする。</summary>
        [ContextMenu("Target Embedding を抽出・キャッシュ")]
        public void TriggerExtractEmb()
        {
            if (!Application.isPlaying)
            {
                Debug.LogWarning("[Bench] Play モードで実行してください。");
                return;
            }
            StartCoroutine(ExtractEmbCoroutine());
        }

        // ── Coroutines ────────────────────────────────────────────────────

        IEnumerator ConvertCoroutine()
        {
            if (!ValidateInputs()) yield break;

            // Step 1: target embedding が古い (または未取得) なら再抽出
            if (_cachedTargetEmb == null || _cachedTargetRef != targetRefClip)
                yield return StartCoroutine(ExtractEmbCoroutine());

            if (_cachedTargetEmb == null)
            {
                Debug.LogError("[Bench] Target embedding 抽出に失敗しました。");
                yield break;
            }

            // Step 2: VC 変換 (GPU forward × ODE steps)
            Debug.Log($"[Bench] 変換開始: source={sourceClip.name} ({sourceClip.length:F2}s) → target={targetRefClip.name}");

            AudioClip result = null;
            Stopwatch sw = Stopwatch.StartNew();

            yield return StartCoroutine(
                pipeline.ConvertVoiceAsync(sourceClip, _cachedTargetEmb, clip => result = clip));

            sw.Stop();
            lastConvertMs = sw.ElapsedMilliseconds;
            lastResult    = result;

            if (result == null)
            {
                Debug.LogError("[Bench] 変換結果が null です。Console のエラーを確認してください。");
                yield break;
            }

            Debug.Log($"[Bench] 変換完了: {lastConvertMs}ms → {result.length:F2}s @ {result.frequency}Hz");

            // Step 3: 再生
            if (playOnConvert && outputSource != null)
            {
                outputSource.clip = result;
                outputSource.Play();
            }
        }

        IEnumerator ExtractEmbCoroutine()
        {
            if (targetRefClip == null)
            {
                Debug.LogError("[Bench] Target Ref Clip が設定されていません。");
                yield break;
            }
            if (pipeline.campplusModel == null)
            {
                Debug.LogError("[Bench] VoiceConversionPipeline.campplusModel が未設定です。");
                yield break;
            }

            Debug.Log($"[Bench] Target embedding 抽出中: {targetRefClip.name} ({targetRefClip.length:F2}s)");

            Stopwatch sw = Stopwatch.StartNew();
            _cachedTargetEmb = pipeline.ExtractSpeakerEmbedding(targetRefClip);
            _cachedTargetRef = targetRefClip;
            sw.Stop();

            Debug.Log($"[Bench] Embedding 抽出完了: {sw.ElapsedMilliseconds}ms → float[{_cachedTargetEmb?.Length}]");
            yield return null;
        }

        // ── Validation ────────────────────────────────────────────────────

        bool ValidateInputs()
        {
            if (pipeline == null)
            {
                Debug.LogError("[Bench] VoiceConversionPipeline が見つかりません。");
                return false;
            }
            if (sourceClip == null)
            {
                Debug.LogError("[Bench] Source Clip が設定されていません。");
                return false;
            }
            if (targetRefClip == null)
            {
                Debug.LogError("[Bench] Target Ref Clip が設定されていません。");
                return false;
            }
            if (pipeline.ditModel == null || pipeline.hiftModel == null)
            {
                Debug.LogError("[Bench] VoiceConversionPipeline の ditModel / hiftModel が未設定です。");
                return false;
            }
            return true;
        }
    }
}
