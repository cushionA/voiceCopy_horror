// VoiceConversionPipeline.cs — 4-model VC pipeline (CosyVoice3)
// voice_horror Phase 3 (2026-05-07)
//
// Pipeline:
//   1. Resample source audio to 16 kHz (campplus) + 24000 Hz (acoustic mel / hift)
//   2. campplus    : mel80 [1,T,80]  → spk_emb [1,192] → project → spks [1,80]
//   3. tokenizer   : mel128 [1,128,T] → indices (unused in VC; kept for completeness)
//   4. DiT ODE     : x[noise] + mu[src_mel] + spks → mel_out [1,80,100]
//   5. hift        : mel_out [1,80,T] → audio [1,T_audio]
//   6. Create AudioClip at 24000 Hz (cosyvoice3.yaml: sample_rate=24000)
//
// NOTE: In full CosyVoice3, mu comes from an LLM token decoder.
//       Phase 3 approximation: mu = source acoustic mel (mel-to-mel VC).
//       Quality improves once the token decoder model is integrated.
//
// Usage:
//   Attach to a GameObject in the scene.
//   Assign the 4 ModelAssets in Inspector.
//   Call ConvertVoice(sourceClip, targetSpkEmb) → IEnumerator.

using System;
using System.Collections;
using System.Diagnostics;
using Unity.InferenceEngine;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace VoiceHorror.VC
{
    /// <summary>VC 中間結果のスナップショット (Phase 3.5 ノイズ調査用)。</summary>
    public class VcDebugCapture
    {
        public float[]   audio24k;          // resample 後の入力音声
        public float[,]  sourceMel80xT;     // [80, T_src]  acoustic mel (PadOrTruncate 前)
        public float[,]  mu80x100;          // [80, 100]    DiT mu 入力 (truncate 後)
        public float[]   ditOutMelFlat;     // [80*100]     DiT 出力 mel (row-major)
        public int       ditOutMelValidT;   // 有効 frame 数 (= min(T_src, 100))
        public float[]   hiftOutAudio;      // [T_audio]    hift 出力 (24kHz)
        public int       hiftSampleRate;
        public float[]   spks80;            // [80]         投影後 speaker embedding
    }

    public class VoiceConversionPipeline : MonoBehaviour
    {
        [Header("Models")]
        [Tooltip("campplus.onnx (Speaker Encoder, 28 MB)")]
        public ModelAsset campplusModel;

        [Tooltip("speech_tokenizer_v3.onnx (970 MB) — used for feature extraction")]
        public ModelAsset tokenizerModel;

        [Tooltip("flow.decoder.estimator.fp32.onnx (DiT, 1268 MB)")]
        public ModelAsset ditModel;

        [Tooltip("hift.fp32.onnx (CausalHiFTGenerator, 329 MB)")]
        public ModelAsset hiftModel;

        [Header("Settings")]
        public BackendType backend     = BackendType.GPUCompute;
        public int         odeSteps    = 10;
        public int         ditSeed     = 42;

        // Output sample rate for hift (must match model's training SR).
        // cosyvoice3.yaml: sample_rate: 24000
        const int k_HiftSR = 24000;

        // campplus mel フレーム数の上限。
        // Sentis の AveragePool ceil_mode=1 が floor として動作するバグ回避のため、
        // T を必ず 100 の倍数に揃える。内部で T が半分になるレイヤー (T/2 = 700) も
        // 100 の倍数になるよう 1400 を選ぶ。
        // 1400 フレーム × hop=160 / 16000Hz ≈ 14 秒。
        const int k_CampplusMaxFrames = 1400;

        // Workers (created lazily, reused across calls)
        Worker _campplusWorker;
        Worker _tokenizerWorker;
        Worker _ditWorker;
        Worker _hiftWorker;

        SpkEmbedProjection _projection;
        bool _initialized;

        // ── Debug capture (Phase 3.5 ノイズ調査用) ────────────────────────
        // captureDebug=true で ConvertVoice 実行時に直近の中間結果を保持する。
        // Bench がこれを読んで .npy / .wav に書き出す。
        [System.NonSerialized] public bool captureDebug;
        [System.NonSerialized] public VcDebugCapture lastCapture;

        // ── Lifecycle ─────────────────────────────────────────────────────

        void Awake()
        {
            _projection = SpkEmbedProjection.Load();
        }

        void OnDestroy()
        {
            _campplusWorker?.Dispose();
            _tokenizerWorker?.Dispose();
            _ditWorker?.Dispose();
            _hiftWorker?.Dispose();
        }

        // ── Public API ────────────────────────────────────────────────────

        // Extract speaker embedding from a reference AudioClip.
        // Returns float[192] or null on error.
        public float[] ExtractSpeakerEmbedding(AudioClip refClip)
        {
            if (refClip == null || campplusModel == null)
            {
                Debug.LogError("[VC] refClip or campplusModel is null");
                return null;
            }

            EnsureWorker(ref _campplusWorker, campplusModel, "campplus");

            float[] audio16k = GetAudio16k(refClip);
            float[,] mel     = MelExtractor.ExtractFeatureMel80(audio16k); // [T, 80]

            // Sentis AveragePool ceil_mode=1 バグ回避: T を 100 の倍数に揃えるため
            // k_CampplusMaxFrames (1400) でクリップ。超過分は先頭 14 秒で十分。
            int T = Math.Min(mel.GetLength(0), k_CampplusMaxFrames);
            if (mel.GetLength(0) > k_CampplusMaxFrames)
                Debug.LogWarning($"[VC] campplus: mel truncated {mel.GetLength(0)} → {T} frames (≈{T * 160 / 16000f:F1}s)");

            // Flatten to [1, T, 80] row-major
            float[] flat = new float[T * 80];
            for (int t = 0; t < T; t++)
                for (int f = 0; f < 80; f++)
                    flat[t * 80 + f] = mel[t, f];

            using var input = new Tensor<float>(new TensorShape(1, T, 80), flat);
            var sw = Stopwatch.StartNew();
            _campplusWorker.Schedule(input);
            using var outTensor = (_campplusWorker.PeekOutput() as Tensor<float>).ReadbackAndClone();
            sw.Stop();
            Debug.Log($"[VC] campplus forward {sw.ElapsedMilliseconds}ms → spk_emb shape={outTensor.shape}");

            return outTensor.DownloadToArray(); // [192]
        }

        // Convert source audio to target speaker's voice.
        // targetSpkEmb: float[192] from ExtractSpeakerEmbedding().
        // Returns converted AudioClip at k_HiftSR.
        public AudioClip ConvertVoice(AudioClip sourceClip, float[] targetSpkEmb)
        {
            if (sourceClip == null)   { Debug.LogError("[VC] sourceClip is null"); return null; }
            if (targetSpkEmb == null) { Debug.LogError("[VC] targetSpkEmb is null"); return null; }
            if (ditModel == null)     { Debug.LogError("[VC] ditModel is null"); return null; }
            if (hiftModel == null)    { Debug.LogError("[VC] hiftModel is null"); return null; }

            EnsureWorker(ref _ditWorker,  ditModel,  "DiT");
            EnsureWorker(ref _hiftWorker, hiftModel, "hift");

            var sw = Stopwatch.StartNew();

            // ── Step 1: Project speaker embedding 192 → 80 ─────────────
            float[] spks80 = _projection.Project(targetSpkEmb); // [80]

            // ── Step 2: Extract acoustic mel from source audio ──────────
            float[] audio24k   = GetAudio24k(sourceClip);
            float[,] acouMel   = MelExtractor.ExtractAcousticMel(audio24k); // [80, T_src]
            int melLength      = acouMel.GetLength(1);
            float[,] mu80x100  = MelExtractor.PadOrTruncate(acouMel, 100); // [80, 100]

            Debug.Log($"[VC] Mel: src_T={melLength}, clamped to 100. audio24k={audio24k.Length} samples");

            // ── Step 3: ODE flow matching ────────────────────────────────
            sw.Restart();
            float[] melFlat = FlowMatchingODE.Run(_ditWorker, mu80x100, spks80,
                melLength, odeSteps, ditSeed);
            sw.Stop();
            Debug.Log($"[VC] ODE ({odeSteps} steps) {sw.ElapsedMilliseconds}ms");

            // Reshape [80*100] → [80, T_valid] (only valid frames)
            int    validT    = Math.Min(melLength, 100);
            float[] melValid = ExtractValidFrames(melFlat, 80, 100, validT);

            // ── Step 4: Vocoder (hift) ───────────────────────────────────
            sw.Restart();
            float[] audioOut = RunHift(melValid, 80, validT);
            sw.Stop();
            Debug.Log($"[VC] hift {sw.ElapsedMilliseconds}ms → {audioOut.Length} samples at {k_HiftSR} Hz");

            // ── Step 5: Build AudioClip ──────────────────────────────────
            AudioClip clip = AudioClip.Create("vc_output", audioOut.Length, 1, k_HiftSR, false);
            clip.SetData(audioOut, 0);

            // ── Debug: 中間結果キャプチャ ────────────────────────────────
            if (captureDebug)
            {
                lastCapture = new VcDebugCapture
                {
                    audio24k          = audio24k,
                    sourceMel80xT     = acouMel,           // [80, T_src]
                    mu80x100          = mu80x100,          // [80, 100] (DiT 入力)
                    ditOutMelFlat     = melFlat,           // [80*100]
                    ditOutMelValidT   = validT,
                    hiftOutAudio      = audioOut,          // [T_audio]
                    hiftSampleRate    = k_HiftSR,
                    spks80            = spks80,
                };
            }

            return clip;
        }

        // ── Hift-only mode (Phase 3.5 検証用) ─────────────────────────────
        // DiT を完全にバイパスし、source acoustic mel をそのまま hift に通す。
        // 声質変換は行わないが、mel 抽出 + hift 単体の品質を聴感確認できる。
        // また、長さ問題 A (T=100 切断) の解決手段として「100-frame chunk loop」
        // の実装習作にもなる (🅱 token encoder ルートでも流用可能)。
        //
        // 実装: source mel [80, T_src] を 100 frame ごとに分割 → 各 chunk を hift で
        // vocode → 単純 concat。チャンク境界の連続性保証は行わない (初期検証目的)。
        public AudioClip RunHiftOnly(AudioClip sourceClip)
        {
            if (sourceClip == null) { Debug.LogError("[VC] sourceClip is null"); return null; }
            if (hiftModel == null)  { Debug.LogError("[VC] hiftModel is null"); return null; }

            EnsureWorker(ref _hiftWorker, hiftModel, "hift");

            var sw = Stopwatch.StartNew();

            // ── Step 1: 音声 → acoustic mel [80, T_src] ─────────────────
            float[] audio24k = GetAudio24k(sourceClip);
            float[,] acouMel = MelExtractor.ExtractAcousticMel(audio24k);
            int nMel   = acouMel.GetLength(0);
            int totalT = acouMel.GetLength(1);
            sw.Stop();
            Debug.Log($"[VC][HiftOnly] mel ({nMel},{totalT}) extracted in {sw.ElapsedMilliseconds}ms; audio24k={audio24k.Length} samples");

            // ── Step 2: 100-frame chunk に分割して hift へ ─────────────
            const int chunkT    = 100;
            int       numChunks = (totalT + chunkT - 1) / chunkT;
            var       chunks    = new System.Collections.Generic.List<float[]>(numChunks);

            sw.Restart();
            for (int i = 0; i < numChunks; i++)
            {
                int start = i * chunkT;
                int end   = Math.Min(start + chunkT, totalT);
                int thisT = end - start;

                // Flat [nMel * thisT], stride=thisT (RunHift が要求する形)
                float[] flat = new float[nMel * thisT];
                for (int m = 0; m < nMel; m++)
                    for (int t = 0; t < thisT; t++)
                        flat[m * thisT + t] = acouMel[m, start + t];

                float[] audioOut = RunHift(flat, nMel, thisT);
                chunks.Add(audioOut);
            }
            sw.Stop();
            Debug.Log($"[VC][HiftOnly] {numChunks} chunks vocoded in {sw.ElapsedMilliseconds}ms");

            // ── Step 3: concat ─────────────────────────────────────────
            int totalSamples = 0;
            foreach (var c in chunks) totalSamples += c.Length;
            float[] full   = new float[totalSamples];
            int     offset = 0;
            foreach (var c in chunks)
            {
                Array.Copy(c, 0, full, offset, c.Length);
                offset += c.Length;
            }

            AudioClip clip = AudioClip.Create("hift_only_output", full.Length, 1, k_HiftSR, false);
            clip.SetData(full, 0);

            // ── Debug capture (DiT 関連は null) ─────────────────────────
            if (captureDebug)
            {
                lastCapture = new VcDebugCapture
                {
                    audio24k        = audio24k,
                    sourceMel80xT   = acouMel,
                    mu80x100        = null,
                    ditOutMelFlat   = null,
                    ditOutMelValidT = 0,
                    hiftOutAudio    = full,
                    hiftSampleRate  = k_HiftSR,
                    spks80          = null,
                };
            }

            Debug.Log($"[VC][HiftOnly] output: {full.Length} samples ({full.Length / (float)k_HiftSR:F2}s @ {k_HiftSR}Hz)");
            return clip;
        }

        // Coroutine version for non-blocking game use.
        public IEnumerator ConvertVoiceAsync(AudioClip source, float[] targetSpkEmb,
            Action<AudioClip> onComplete)
        {
            // CPU work first frame
            float[] spks80   = _projection.Project(targetSpkEmb);
            float[] audio24k = GetAudio24k(source);
            float[,] acouMel = MelExtractor.ExtractAcousticMel(audio24k);
            int melLength    = acouMel.GetLength(1);
            float[,] mu      = MelExtractor.PadOrTruncate(acouMel, 100);
            yield return null; // yield before GPU work

            EnsureWorker(ref _ditWorker,  ditModel,  "DiT");
            EnsureWorker(ref _hiftWorker, hiftModel, "hift");

            // ODE loop (runs on main thread but schedules GPU work)
            float[] melFlat = FlowMatchingODE.Run(_ditWorker, mu, spks80,
                melLength, odeSteps, ditSeed);
            yield return null;

            int validT     = Math.Min(melLength, 100);
            float[] valid  = ExtractValidFrames(melFlat, 80, 100, validT);
            float[] audio  = RunHift(valid, 80, validT);

            AudioClip clip = AudioClip.Create("vc_output", audio.Length, 1, k_HiftSR, false);
            clip.SetData(audio, 0);
            onComplete?.Invoke(clip);
        }

        // ── Private helpers ───────────────────────────────────────────────

        // melFlat80xT: flat [nMel * nT] with stride nT (from ExtractValidFrames)
        float[] RunHift(float[] melFlat80xT, int nMel, int nT)
        {
            using var speechFeat = new Tensor<float>(new TensorShape(1, nMel, nT), melFlat80xT);
            _hiftWorker.Schedule(speechFeat);
            using var outTensor = (_hiftWorker.PeekOutput() as Tensor<float>).ReadbackAndClone();
            return outTensor.DownloadToArray(); // [T_audio]
        }

        // Extract first validT frames from flat [nMel, fullT] stored as [nMel*fullT].
        static float[] ExtractValidFrames(float[] flatMelFull, int nMel, int fullT, int validT)
        {
            float[] result = new float[nMel * validT];
            for (int m = 0; m < nMel; m++)
                for (int t = 0; t < validT; t++)
                    result[m * validT + t] = flatMelFull[m * fullT + t];
            return result;
        }

        float[] GetAudio16k(AudioClip clip)
        {
            float[] raw = new float[clip.samples * clip.channels];
            clip.GetData(raw, 0);
            float[] mono = ToMono(raw, clip.channels);
            return MelExtractor.Resample(mono, clip.frequency, 16000);
        }

        float[] GetAudio24k(AudioClip clip)
        {
            float[] raw  = new float[clip.samples * clip.channels];
            clip.GetData(raw, 0);
            float[] mono = ToMono(raw, clip.channels);
            return MelExtractor.Resample(mono, clip.frequency, 24000);
        }

        static float[] ToMono(float[] audio, int channels)
        {
            if (channels == 1) return audio;
            int n = audio.Length / channels;
            float[] mono = new float[n];
            for (int i = 0; i < n; i++)
            {
                float sum = 0f;
                for (int c = 0; c < channels; c++) sum += audio[i * channels + c];
                mono[i] = sum / channels;
            }
            return mono;
        }

        void EnsureWorker(ref Worker worker, ModelAsset asset, string name)
        {
            if (worker != null) return;
            var sw = Stopwatch.StartNew();
            var model = ModelLoader.Load(asset);
            worker = new Worker(model, backend);
            sw.Stop();
            Debug.Log($"[VC] {name} worker created in {sw.ElapsedMilliseconds}ms");
        }
    }
}
