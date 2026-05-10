// VcQuantizeCompareRunner.cs — Phase 8 FP16 量子化比較ランナー
// voice_horror Phase 8 (2026-05-10)
//
// Goal:
//   FP32 / FP16 ONNX (WavLM + HiFiGAN) を 2 つの VoiceConversionService に
//   それぞれアサインし、同一 (source, target) ペアで両方変換 → 出力波形と
//   レイテンシの差分を測る。
//
// シーケンス (Play 押下時に自動進行):
//   1. Initialize + WarmupAsync を 2 service 並行
//   2. testClips の各要素を target / source として全組合せ (対角除外) ループ
//   3. 各 (src, tgt) で:
//        a. 両 service の TargetPool を tgt で再構築
//        b. FP32 service.Convert(src, alpha=1) → audioFp32 + timingsFp32
//        c. FP16 service.Convert(src, alpha=1) → audioFp16 + timingsFp16
//        d. メトリクス計算 (time-domain RMSE, max abs diff, length match)
//        e. WAV 書き出し (fp32, fp16, diff)
//   4. CSV に集計
//
// 出力:
//   VcTestOutput/quantize_{timestamp}/
//     fp32/{src}_to_{tgt}.wav
//     fp16/{src}_to_{tgt}.wav
//     diff/{src}_to_{tgt}_diff.wav   ← (fp32 - fp16) / 2 を audio として保存
//     quantize_compare.csv
//
// 注:
//   - VcPerfRunner と同じシーンに置かないこと (両方 Start で走るため衝突)。
//   - alpha は 1.0 固定 (FP16 vs FP32 を素朴比較するため、混合比は出さない)。
//   - testClips の長さは可能な限り揃えること (極端に違うと target pool の frame 数差が
//     比較解釈を難しくする)。

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Unity.InferenceEngine;
using UnityEngine;
using VoiceHorror.VC; // WavWriter

namespace VoiceHorror.KnnVc
{
    [DefaultExecutionOrder(100)] // VoiceConversionService の Awake より後
    public class VcQuantizeCompareRunner : MonoBehaviour
    {
        [Header("Services (FP32 / FP16 ONNX をそれぞれアサインした 2 service を並行使用)")]
        [Tooltip("FP32 ONNX をアサインした VoiceConversionService")]
        [SerializeField] VoiceConversionService serviceFp32;
        [Tooltip("FP16 ONNX をアサインした VoiceConversionService")]
        [SerializeField] VoiceConversionService serviceFp16;

        [Header("Test clips (source / target を全組合せで使い回す。対角は除外)")]
        [Tooltip("5 件想定: my_sampleVoice, 107, 10, 86, raizyo")]
        [SerializeField] AudioClip[] testClips = new AudioClip[5];

        [Header("Settings")]
        [Tooltip("変換 alpha (1.0 = target only。FP16/FP32 比較では 1.0 固定が解釈しやすい)")]
        [Range(0f, 1f)]
        [SerializeField] float alpha = 1.0f;

        [Tooltip("CSV / WAV を書き出さず計測のみ行う (計測ループのデバッグ用)")]
        [SerializeField] bool dryRunNoOutput = false;

        // ── State ──────────────────────────────────────────────────────

        struct PairResult
        {
            public string srcName;
            public string tgtName;
            public int audioLenFp32;
            public int audioLenFp16;
            public double timeRmse;       // sqrt(mean((fp32-fp16)^2))
            public double timeMaxAbsDiff; // max(|fp32-fp16|)
            public double peakFp32;
            public double peakFp16;
            public VoiceConversionService.ConversionTimings timingsFp32;
            public VoiceConversionService.ConversionTimings timingsFp16;
        }

        readonly List<PairResult> _results = new();
        string _statusLine = "(initializing)";
        string _runTimestamp;

        // ── Lifecycle ───────────────────────────────────────────────────

        IEnumerator Start()
        {
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;

            if (serviceFp32 == null || serviceFp16 == null)
            {
                _statusLine = "ERROR: serviceFp32 / serviceFp16 のいずれかが未アサイン";
                Debug.LogError("[VcQuantize] " + _statusLine);
                yield break;
            }

            _statusLine = "Initialize + Warmup (FP32)...";
            yield return null;
            serviceFp32.Initialize();
            yield return serviceFp32.WarmupAsync();

            _statusLine = "Initialize + Warmup (FP16)...";
            yield return null;
            serviceFp16.Initialize();
            yield return serviceFp16.WarmupAsync();

            int validClips = 0;
            for (int i = 0; i < testClips.Length; i++) if (testClips[i] != null) validClips++;
            if (validClips < 2)
            {
                _statusLine = $"ERROR: testClips に non-null が {validClips} 件しかない (≥2 必要)";
                Debug.LogError("[VcQuantize] " + _statusLine);
                yield break;
            }

            yield return RunPairs();

            if (!dryRunNoOutput)
            {
                string csv = SaveCsv();
                _statusLine = $"DONE. {_results.Count} pairs. CSV: {csv}";
            }
            else
            {
                _statusLine = $"DONE (dryRun, no output). {_results.Count} pairs measured.";
            }
            Debug.Log("[VcQuantize] " + _statusLine);
        }

        IEnumerator RunPairs()
        {
            int totalPairs = 0;
            for (int s = 0; s < testClips.Length; s++)
                for (int t = 0; t < testClips.Length; t++)
                    if (testClips[s] != null && testClips[t] != null && s != t) totalPairs++;

            int pairIdx = 0;
            for (int t = 0; t < testClips.Length; t++)
            {
                if (testClips[t] == null) continue;

                // target pool を **共通 features** で再構築。
                // 旧実装は両 service で個別に WavLM forward を走らせていたため、
                // FP32/FP16 で target encode の数値差が混入していた。
                // 比較したいのは「convert 時の query encode + vocode 差分」なので、
                // FP32 service で 1 回 forward して両 service の TargetPool に
                // 同じ features を append することで target 側の差分を排除する。
                _statusLine = $"Building target pool (shared features): {testClips[t].name}";
                yield return null;
                serviceFp32.ClearPools();
                serviceFp16.ClearPools();
                using (Tensor<float> targetFeats2D = serviceFp32.ExtractQueryFeatures(testClips[t]))
                {
                    // ExtractQueryFeatures は (T, 1024)。MatchingSetPool.Append は
                    // (N, 1024) を期待 (rank 2、最終 dim 1024) なのでそのまま渡せる。
                    serviceFp32.TargetPool.Append(targetFeats2D);
                    serviceFp16.TargetPool.Append(targetFeats2D);
                }

                for (int s = 0; s < testClips.Length; s++)
                {
                    if (testClips[s] == null || s == t) continue;
                    pairIdx++;
                    AudioClip src = testClips[s];
                    AudioClip tgt = testClips[t];
                    _statusLine = $"[{pairIdx}/{totalPairs}] {src.name} -> {tgt.name}";
                    yield return null;

                    PairResult? r = ConvertAndCompare(src, tgt);
                    if (r.HasValue) _results.Add(r.Value);
                    yield return null;
                }
            }
        }

        // ── Convert + 比較 ──────────────────────────────────────────────

        PairResult? ConvertAndCompare(AudioClip src, AudioClip tgt)
        {
            float[] audioFp32 = null;
            float[] audioFp16 = null;
            VoiceConversionService.ConversionTimings tFp32 = default;
            VoiceConversionService.ConversionTimings tFp16 = default;

            // FP32
            try
            {
                AudioClip outFp32 = serviceFp32.Convert(src, alpha, out tFp32);
                audioFp32 = ClipToFloatArray(outFp32);
                UnityEngine.Object.Destroy(outFp32);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VcQuantize] FP32 Convert FAILED for {src.name}->{tgt.name}: {ex.GetType().Name}: {ex.Message}");
                return null;
            }

            // FP16
            try
            {
                AudioClip outFp16 = serviceFp16.Convert(src, alpha, out tFp16);
                audioFp16 = ClipToFloatArray(outFp16);
                UnityEngine.Object.Destroy(outFp16);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VcQuantize] FP16 Convert FAILED for {src.name}->{tgt.name}: {ex.GetType().Name}: {ex.Message}");
                return null;
            }

            // メトリクス計算 (純関数、テスト容易性のため static helper に分離)
            WaveformMetrics m = ComputeWaveformMetrics(audioFp32, audioFp16);

            // WAV 出力
            if (!dryRunNoOutput)
            {
                SaveOutputs(src.name, tgt.name, audioFp32, audioFp16, m.compareLen);
            }

            return new PairResult
            {
                srcName = src.name,
                tgtName = tgt.name,
                audioLenFp32 = audioFp32.Length,
                audioLenFp16 = audioFp16.Length,
                timeRmse = m.rmse,
                timeMaxAbsDiff = m.maxAbsDiff,
                peakFp32 = m.peakA,
                peakFp16 = m.peakB,
                timingsFp32 = tFp32,
                timingsFp16 = tFp16,
            };
        }

        /// <summary>
        /// 2 つの mono PCM 波形の比較メトリクス。純関数 (static + 副作用なし) で EditMode テスト容易。
        /// 長さが違う場合は **短い方の長さで RMSE / maxAbsDiff を計算**、peak は両方の全長から集計。
        /// </summary>
        public struct WaveformMetrics
        {
            public int compareLen;     // RMSE / maxAbsDiff 計算に使った長さ = min(a.Length, b.Length)
            public double rmse;        // sqrt(mean((a[i] - b[i])^2)) over compareLen
            public double maxAbsDiff;  // max(|a[i] - b[i]|) over compareLen
            public double peakA;       // max(|a[i]|) over a.Length 全体
            public double peakB;       // max(|b[i]|) over b.Length 全体
        }

        /// <summary>
        /// FP32 vs FP16 等の波形比較で使う metrics を計算する。
        /// null / 空配列でも例外を投げず compareLen=0、rmse=0、peak=0 を返す。
        /// </summary>
        public static WaveformMetrics ComputeWaveformMetrics(float[] a, float[] b)
        {
            WaveformMetrics m = default;
            if (a == null || b == null) return m;

            int n = Math.Min(a.Length, b.Length);
            m.compareLen = n;

            double sumSq = 0;
            double maxAbs = 0;
            double peakA = 0;
            double peakB = 0;
            for (int i = 0; i < n; i++)
            {
                double d = (double)a[i] - b[i];
                sumSq += d * d;
                double ad = d >= 0 ? d : -d;
                if (ad > maxAbs) maxAbs = ad;
                double pa = a[i] >= 0 ? a[i] : -a[i];
                double pb = b[i] >= 0 ? b[i] : -b[i];
                if (pa > peakA) peakA = pa;
                if (pb > peakB) peakB = pb;
            }
            // 長さが違う部分は peak 集計のみ更新
            for (int i = n; i < a.Length; i++)
            {
                double pa = a[i] >= 0 ? a[i] : -a[i];
                if (pa > peakA) peakA = pa;
            }
            for (int i = n; i < b.Length; i++)
            {
                double pb = b[i] >= 0 ? b[i] : -b[i];
                if (pb > peakB) peakB = pb;
            }

            m.rmse = n > 0 ? Math.Sqrt(sumSq / n) : 0;
            m.maxAbsDiff = maxAbs;
            m.peakA = peakA;
            m.peakB = peakB;
            return m;
        }

        const int k_OutputSampleRate = 16000;

        void SaveOutputs(string srcName, string tgtName, float[] fp32, float[] fp16, int compareLen)
        {
            string dir = OutputDir();
            string baseName = $"{srcName}_to_{tgtName}";

            string p32 = Path.Combine(dir, "fp32", baseName + ".wav");
            string p16 = Path.Combine(dir, "fp16", baseName + ".wav");
            string pDiff = Path.Combine(dir, "diff", baseName + "_diff.wav");

            try
            {
                WavWriter.Save(p32, fp32, k_OutputSampleRate);
                WavWriter.Save(p16, fp16, k_OutputSampleRate);

                // diff: (fp32 - fp16) / 2 で振幅クリッピングを避けつつ違いを聴感確認できる形にする
                float[] diff = new float[compareLen];
                for (int i = 0; i < compareLen; i++)
                {
                    float d = (fp32[i] - fp16[i]) * 0.5f;
                    if (d > 1f) d = 1f;
                    else if (d < -1f) d = -1f;
                    diff[i] = d;
                }
                WavWriter.Save(pDiff, diff, k_OutputSampleRate);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VcQuantize] WAV save FAILED ({baseName}): {ex.Message}");
            }
        }

        // ── Helpers ─────────────────────────────────────────────────────

        static float[] ClipToFloatArray(AudioClip clip)
        {
            float[] data = new float[clip.samples * clip.channels];
            clip.GetData(data, 0);
            // mono 想定 (kHiftSampleRate=16k, channels=1)。stereo の場合のみ ToMono。
            if (clip.channels == 1) return data;
            int n = clip.samples;
            float[] mono = new float[n];
            for (int i = 0; i < n; i++)
            {
                float sum = 0;
                for (int c = 0; c < clip.channels; c++) sum += data[i * clip.channels + c];
                mono[i] = sum / clip.channels;
            }
            return mono;
        }

        string OutputDir()
        {
            if (_runTimestamp == null)
                _runTimestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
            string dir = Path.Combine(repoRoot, "VcTestOutput", $"quantize_{_runTimestamp}");
            Directory.CreateDirectory(Path.Combine(dir, "fp32"));
            Directory.CreateDirectory(Path.Combine(dir, "fp16"));
            Directory.CreateDirectory(Path.Combine(dir, "diff"));
            return dir;
        }

        string SaveCsv()
        {
            string dir = OutputDir();
            string path = Path.Combine(dir, "quantize_compare.csv");

            var sb = new StringBuilder();
            sb.AppendLine("# kNN-VC FP16 quantize compare. timing は Stopwatch ベース (extract/knn/vocode/total)。波形は 16kHz mono。");
            sb.AppendLine("src,tgt,len_fp32,len_fp16," +
                          "extract_fp32_ms,knn_fp32_ms,vocode_fp32_ms,total_fp32_ms," +
                          "extract_fp16_ms,knn_fp16_ms,vocode_fp16_ms,total_fp16_ms," +
                          "time_rmse,time_max_abs_diff,peak_fp32,peak_fp16");
            foreach (PairResult r in _results)
            {
                sb.AppendLine(string.Join(",",
                    r.srcName, r.tgtName,
                    r.audioLenFp32, r.audioLenFp16,
                    r.timingsFp32.extractMs.ToString("F2"),
                    r.timingsFp32.knnMs.ToString("F2"),
                    r.timingsFp32.vocodeMs.ToString("F2"),
                    r.timingsFp32.totalMs.ToString("F2"),
                    r.timingsFp16.extractMs.ToString("F2"),
                    r.timingsFp16.knnMs.ToString("F2"),
                    r.timingsFp16.vocodeMs.ToString("F2"),
                    r.timingsFp16.totalMs.ToString("F2"),
                    r.timeRmse.ToString("E3"),
                    r.timeMaxAbsDiff.ToString("E3"),
                    r.peakFp32.ToString("F3"),
                    r.peakFp16.ToString("F3")));
            }

            // 集計行 (mean)
            if (_results.Count > 0)
            {
                double mE32 = 0, mK32 = 0, mV32 = 0, mT32 = 0;
                double mE16 = 0, mK16 = 0, mV16 = 0, mT16 = 0;
                double mRmse = 0, mMaxAbs = 0;
                foreach (PairResult r in _results)
                {
                    mE32 += r.timingsFp32.extractMs;
                    mK32 += r.timingsFp32.knnMs;
                    mV32 += r.timingsFp32.vocodeMs;
                    mT32 += r.timingsFp32.totalMs;
                    mE16 += r.timingsFp16.extractMs;
                    mK16 += r.timingsFp16.knnMs;
                    mV16 += r.timingsFp16.vocodeMs;
                    mT16 += r.timingsFp16.totalMs;
                    mRmse += r.timeRmse;
                    mMaxAbs += r.timeMaxAbsDiff;
                }
                int n = _results.Count;
                sb.AppendLine();
                sb.AppendLine("# mean across pairs");
                sb.AppendLine("stage,fp32_ms,fp16_ms,delta_ms,delta_pct");
                AppendStageMean(sb, "extract", mE32 / n, mE16 / n);
                AppendStageMean(sb, "knn",     mK32 / n, mK16 / n);
                AppendStageMean(sb, "vocode",  mV32 / n, mV16 / n);
                AppendStageMean(sb, "total",   mT32 / n, mT16 / n);
                sb.AppendLine();
                sb.AppendLine($"# mean time_rmse: {mRmse / n:E3}");
                sb.AppendLine($"# mean time_max_abs_diff: {mMaxAbs / n:E3}");
            }

            File.WriteAllText(path, sb.ToString());
            return path;
        }

        static void AppendStageMean(StringBuilder sb, string label, double fp32Ms, double fp16Ms)
        {
            double delta = fp16Ms - fp32Ms;
            double pct = fp32Ms > 0 ? delta / fp32Ms * 100.0 : 0;
            sb.AppendLine($"{label},{fp32Ms:F2},{fp16Ms:F2},{delta:F2},{pct:F1}");
        }

        // ── IMGUI 表示 ───────────────────────────────────────────────────

        static GUIStyle s_labelStyle;
        static GUIStyle s_titleStyle;

        static void EnsureStyles()
        {
            if (s_labelStyle == null)
            {
                s_labelStyle = new GUIStyle(GUI.skin.label) { fontSize = 16 };
                s_titleStyle = new GUIStyle(GUI.skin.box)
                {
                    fontSize = 18,
                    alignment = TextAnchor.UpperLeft,
                    fontStyle = FontStyle.Bold,
                };
            }
        }

        void OnGUI()
        {
            EnsureStyles();
            const int w = 880, h = 100;
            GUI.Box(new Rect(10, 10, w, h), "kNN-VC Quantize Compare (FP32 vs FP16)", s_titleStyle);
            GUI.Label(new Rect(28, 50, w - 36, 26), _statusLine, s_labelStyle);
            GUI.Label(new Rect(28, 78, w - 36, 26), $"results: {_results.Count}", s_labelStyle);
        }
    }
}
