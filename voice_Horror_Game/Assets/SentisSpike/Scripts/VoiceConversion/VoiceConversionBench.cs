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

using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
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

        [Header("Hift Only Mode (Phase 3.5 検証)")]
        [Tooltip("DiT をバイパスし source acoustic mel をそのまま hift に通す。声質変換無しだが mel 抽出 + hift 単体の品質を聴感確認できる。Target Ref Clip は不要。")]
        public bool hiftOnlyMode;

        [Header("Debug Output")]
        [Tooltip("出力 WAV と中間 mel を保存するルートディレクトリ (project root 相対 or 絶対)。空欄=保存しない")]
        public string saveDirectory = "VcDebugOut";

        [Tooltip("source_mel.npy / mu.npy / dit_out_mel.npy も保存する (Python 比較用)")]
        public bool dumpIntermediates = true;

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
            if (hiftOnlyMode)
                StartCoroutine(HiftOnlyCoroutine());
            else
                StartCoroutine(ConvertCoroutine());
        }

        /// <summary>hift 単体実行 — DiT バイパス。Target Ref Clip 不要。</summary>
        [ContextMenu("hift 単体実行 (DiT バイパス)")]
        public void TriggerHiftOnly()
        {
            if (!Application.isPlaying)
            {
                Debug.LogWarning("[Bench] Play モードで実行してください。");
                return;
            }
            StartCoroutine(HiftOnlyCoroutine());
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
            // Note: dumpIntermediates 有効時は ConvertVoice (同期版) を使う。
            //       ConvertVoiceAsync は中間キャプチャに対応していないため。
            Debug.Log($"[Bench] 変換開始: source={sourceClip.name} ({sourceClip.length:F2}s) → target={targetRefClip.name}");

            AudioClip result = null;
            Stopwatch sw = Stopwatch.StartNew();

            bool wantDump = !string.IsNullOrEmpty(saveDirectory);
            pipeline.captureDebug = wantDump;

            if (wantDump)
            {
                // 同期版で中間結果をキャプチャ
                result = pipeline.ConvertVoice(sourceClip, _cachedTargetEmb);
                yield return null;
            }
            else
            {
                yield return StartCoroutine(
                    pipeline.ConvertVoiceAsync(sourceClip, _cachedTargetEmb, clip => result = clip));
            }

            sw.Stop();
            lastConvertMs = sw.ElapsedMilliseconds;
            lastResult    = result;

            if (result == null)
            {
                Debug.LogError("[Bench] 変換結果が null です。Console のエラーを確認してください。");
                yield break;
            }

            Debug.Log($"[Bench] 変換完了: {lastConvertMs}ms → {result.length:F2}s @ {result.frequency}Hz");

            // Step 3: 結果をディスクに保存 (WAV + 中間 mel)
            if (wantDump)
                SaveDebugDump(result);

            // Step 4: 再生
            if (playOnConvert && outputSource != null)
            {
                outputSource.clip = result;
                outputSource.Play();
            }
        }

        // ── Debug dump ────────────────────────────────────────────────────

        void SaveDebugDump(AudioClip result)
        {
            try
            {
                string root = Path.IsPathRooted(saveDirectory)
                    ? saveDirectory
                    : Path.Combine(Application.dataPath, "..", saveDirectory);
                string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                string outDir = Path.Combine(root, stamp);
                Directory.CreateDirectory(outDir);

                // 1. 出力 WAV
                string outWav = Path.Combine(outDir, "output.wav");
                WavWriter.Save(outWav, result);
                Debug.Log($"[Bench] 出力 WAV: {outWav}  ({result.length:F2}s, {result.frequency}Hz)");

                if (dumpIntermediates && pipeline.lastCapture != null)
                {
                    var c = pipeline.lastCapture;

                    // 入力 24kHz audio
                    if (c.audio24k != null)
                    {
                        WavWriter.Save(Path.Combine(outDir, "input_24k.wav"), c.audio24k, 24000);
                        NpyWriter.Save(Path.Combine(outDir, "input_24k.npy"), c.audio24k);
                    }

                    // source acoustic mel [80, T_src] — Python 側 matcha mel と要素比較する対象
                    if (c.sourceMel80xT != null)
                        NpyWriter.Save(Path.Combine(outDir, "source_mel.npy"), c.sourceMel80xT);

                    // PadOrTruncate 後の mu (DiT 入力) [80, 100]
                    if (c.mu80x100 != null)
                        NpyWriter.Save(Path.Combine(outDir, "mu.npy"), c.mu80x100);

                    // DiT 出力 mel (生 [80*100] flat)
                    if (c.ditOutMelFlat != null)
                        NpyWriter.Save(Path.Combine(outDir, "dit_out_mel.npy"),
                                       c.ditOutMelFlat, new[] { 80, 100 });

                    // hift 出力 audio (raw float)
                    if (c.hiftOutAudio != null)
                        NpyWriter.Save(Path.Combine(outDir, "hift_out.npy"), c.hiftOutAudio);

                    // speaker projection (80)
                    if (c.spks80 != null)
                        NpyWriter.Save(Path.Combine(outDir, "spks80.npy"), c.spks80);

                    // メタ情報
                    string meta =
                        $"source_clip      = {sourceClip?.name} ({sourceClip?.length:F2}s @ {sourceClip?.frequency}Hz)\n" +
                        $"target_ref_clip  = {targetRefClip?.name} ({targetRefClip?.length:F2}s @ {targetRefClip?.frequency}Hz)\n" +
                        $"input_24k_len    = {c.audio24k?.Length}\n" +
                        $"source_mel_T     = {c.sourceMel80xT?.GetLength(1)}\n" +
                        $"mu_shape         = (80, 100)\n" +
                        $"dit_out_validT   = {c.ditOutMelValidT}\n" +
                        $"hift_out_samples = {c.hiftOutAudio?.Length} ({(c.hiftOutAudio?.Length ?? 0) / (float)c.hiftSampleRate:F2}s @ {c.hiftSampleRate}Hz)\n" +
                        $"ode_steps        = {pipeline.odeSteps}\n" +
                        $"dit_seed         = {pipeline.ditSeed}\n";
                    File.WriteAllText(Path.Combine(outDir, "meta.txt"), meta);

                    Debug.Log($"[Bench] 中間 dump: {outDir}\n{meta}");
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[Bench] dump 失敗: {ex.Message}\n{ex.StackTrace}");
            }
            finally
            {
                pipeline.captureDebug = false;
                pipeline.lastCapture  = null; // GC を促す
            }
        }

        IEnumerator HiftOnlyCoroutine()
        {
            if (pipeline == null)
            {
                Debug.LogError("[Bench] VoiceConversionPipeline が見つかりません。");
                yield break;
            }
            if (sourceClip == null)
            {
                Debug.LogError("[Bench] Source Clip が設定されていません。");
                yield break;
            }
            if (pipeline.hiftModel == null)
            {
                Debug.LogError("[Bench] VoiceConversionPipeline.hiftModel が未設定です。");
                yield break;
            }

            Debug.Log($"[Bench][HiftOnly] 実行: source={sourceClip.name} ({sourceClip.length:F2}s)  DiT バイパス");

            bool wantDump = !string.IsNullOrEmpty(saveDirectory);
            pipeline.captureDebug = wantDump;

            AudioClip result = null;
            Stopwatch sw = Stopwatch.StartNew();
            try
            {
                result = pipeline.RunHiftOnly(sourceClip);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[Bench][HiftOnly] 実行失敗: {ex.Message}\n{ex.StackTrace}");
            }
            sw.Stop();
            yield return null;

            lastConvertMs = sw.ElapsedMilliseconds;
            lastResult    = result;

            if (result == null)
            {
                Debug.LogError("[Bench][HiftOnly] 結果が null です。Console を確認してください。");
                pipeline.captureDebug = false;
                pipeline.lastCapture  = null;
                yield break;
            }

            Debug.Log($"[Bench][HiftOnly] 完了: {lastConvertMs}ms → {result.length:F2}s @ {result.frequency}Hz");

            if (wantDump)
                SaveDebugDump(result);

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
