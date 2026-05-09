// VcPerfRunner.cs — Phase 8 着手: PlayMode パフォーマンス計測ランナー
// voice_horror Phase 8 (2026-05-09)
//
// Goal:
//   PlayMode シーンで kNN-VC の変換負荷をホットキー駆動で観察する。
//   段階別の細かい内訳は Unity Profiler の ProfilerMarker (VC.Total /
//   VC.Extract / VC.kNN / VC.Vocode) で見る。本 Runner は IMGUI 上に
//   total elapsed の集計だけを出す。
//
// 操作:
//   起動 (Play) → 自動で Initialize + Warmup + TargetPool 構築
//   キー [Alpha1..Alpha4] : sources[i] を 1 回変換
//   キー [B]              : sources を順に N 回ループ変換 (バッチ)
//   キー [R]              : 統計リセット
//   キー [S]              : CSV 書き出し (VcTestOutput/perf_{timestamp}.csv)
//
// Profiler 使い方:
//   Window > Analysis > Profiler を開いて Editor 接続のまま Play。
//   Hierarchy ビューで "VC." prefix を絞り込めば各段階の time / GC alloc / count 集計が見える。

using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using Unity.Profiling;
using UnityEngine;
using UnityEngine.InputSystem;
using Debug = UnityEngine.Debug;

namespace VoiceHorror.KnnVc
{
    [DefaultExecutionOrder(100)] // VoiceConversionService の Awake より後
    public class VcPerfRunner : MonoBehaviour
    {
        [Header("Service")]
        [Tooltip("同シーン上の VoiceConversionService をアサイン")]
        [SerializeField] VoiceConversionService service;

        [Header("Audio Inputs")]
        [Tooltip("起動時に TargetPool に流し込む声 (少女声優想定)")]
        [SerializeField] AudioClip targetClip;
        [Tooltip("変換対象 source clip (キー 1..4 に対応、最大 4 個)")]
        [SerializeField] AudioClip[] sources = new AudioClip[4];

        [Header("Batch")]
        [Tooltip("キー [B] でバッチ実行する反復回数 (sources を順番に回す)")]
        [SerializeField] int batchIterations = 10;

        [Tooltip("変換 alpha (1.0 = target only)")]
        [Range(0f, 1f)]
        [SerializeField] float alpha = 1.0f;

        [Header("Output")]
        [Tooltip("変換結果を AudioSource で再生するか (耳で確認用)")]
        [SerializeField] bool playOutput;
        [SerializeField] AudioSource audioSource;

        [Header("Auto-run")]
        [Tooltip("Start 後すぐにバッチを 1 回流す (Profiler attach 観察用)")]
        [SerializeField] bool autoRunOnStart;

        // ── Stats (total only。段階別は Profiler 側で見る) ──────────────
        struct StageStats
        {
            public int count;
            public double sumMs;
            public double minMs;
            public double maxMs;
            public List<double> samples;

            public static StageStats New() => new StageStats
            {
                minMs = double.MaxValue,
                maxMs = double.MinValue,
                samples = new List<double>(64),
            };

            public void Record(double ms)
            {
                count++;
                sumMs += ms;
                if (ms < minMs) minMs = ms;
                if (ms > maxMs) maxMs = ms;
                samples.Add(ms);
            }

            public double MeanMs => count > 0 ? sumMs / count : 0;

            public double P95Ms
            {
                get
                {
                    if (count == 0) return 0;
                    var sorted = new List<double>(samples);
                    sorted.Sort();
                    int idx = Mathf.Min(sorted.Count - 1, (int)(sorted.Count * 0.95));
                    return sorted[idx];
                }
            }
        }

        StageStats _total = StageStats.New();

        bool _ready;
        bool _busy;
        string _statusLine = "(initializing)";

        // ── Lifecycle ───────────────────────────────────────────────────

        IEnumerator Start()
        {
            if (service == null)
            {
                _statusLine = "ERROR: service is not assigned";
                Debug.LogError("[VcPerfRunner] service field not assigned");
                yield break;
            }

            service.Initialize();
            yield return service.WarmupAsync();

            if (targetClip != null)
            {
                _statusLine = $"Building target pool from {targetClip.name}...";
                var sw = Stopwatch.StartNew();
                service.AccumulateTargetVoice(targetClip);
                sw.Stop();
                Debug.Log($"[VcPerfRunner] TargetPool built: {service.TargetPool.FrameCount} frames in {sw.ElapsedMilliseconds}ms");
            }
            else
            {
                Debug.LogWarning("[VcPerfRunner] targetClip not assigned, conversions will fail");
            }

            _ready = true;
            _statusLine = $"Ready. TargetPool={service.TargetPool.FrameCount}f. [1..4] convert  [B] batch  [R] reset  [S] save";

            if (autoRunOnStart)
                StartCoroutine(RunBatch());
        }

        void Update()
        {
            if (!_ready || _busy) return;

            var kb = Keyboard.current;
            if (kb == null) return; // headless 等で keyboard 無し

            if (kb.digit1Key.wasPressedThisFrame) ConvertOne(0);
            if (kb.digit2Key.wasPressedThisFrame) ConvertOne(1);
            if (kb.digit3Key.wasPressedThisFrame) ConvertOne(2);
            if (kb.digit4Key.wasPressedThisFrame) ConvertOne(3);
            if (kb.bKey.wasPressedThisFrame)      StartCoroutine(RunBatch());
            if (kb.rKey.wasPressedThisFrame)      ResetStats();
            if (kb.sKey.wasPressedThisFrame)      SaveCsv();
        }

        // ── Operations ──────────────────────────────────────────────────

        void ConvertOne(int sourceIndex)
        {
            if (sourceIndex < 0 || sourceIndex >= sources.Length || sources[sourceIndex] == null)
            {
                _statusLine = $"sources[{sourceIndex}] is null";
                return;
            }
            ConvertClipMeasured(sources[sourceIndex]);
        }

        IEnumerator RunBatch()
        {
            if (sources == null || sources.Length == 0)
            {
                _statusLine = "no sources to batch";
                yield break;
            }

            _busy = true;
            _statusLine = $"Batch x{batchIterations}...";
            int totalRun = 0;
            for (int iter = 0; iter < batchIterations; iter++)
            {
                for (int i = 0; i < sources.Length; i++)
                {
                    if (sources[i] == null) continue;
                    ConvertClipMeasured(sources[i]);
                    totalRun++;
                    yield return null; // 1 frame 譲ってフリーズ感を抑える
                }
            }
            _busy = false;
            _statusLine = $"Batch done: {totalRun} runs. mean={_total.MeanMs:F0}ms p95={_total.P95Ms:F0}ms";
        }

        /// <summary>
        /// 1 回の変換を計測。total elapsed のみ記録。段階内訳は Profiler で見る。
        /// </summary>
        void ConvertClipMeasured(AudioClip clip)
        {
            var sw = Stopwatch.StartNew();
            AudioClip outClip = null;
            try
            {
                outClip = service.Convert(clip, alpha);
            }
            catch (System.Exception ex)
            {
                Debug.LogError($"[VcPerfRunner] Convert FAILED: {ex.GetType().Name}: {ex.Message}");
                return;
            }
            sw.Stop();
            _total.Record(sw.Elapsed.TotalMilliseconds);

            if (playOutput && audioSource != null && outClip != null)
                audioSource.PlayOneShot(outClip);
            // outClip は Unity の GC + AudioClip の lifecycle に任せる
        }

        // ── Reset / Save ─────────────────────────────────────────────────

        void ResetStats()
        {
            _total = StageStats.New();
            _statusLine = "stats reset";
        }

        void SaveCsv()
        {
            string repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
            string outDir = Path.Combine(repoRoot, "VcTestOutput");
            Directory.CreateDirectory(outDir);
            string ts = System.DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string path = Path.Combine(outDir, $"perf_{ts}.csv");

            var sb = new StringBuilder();
            sb.AppendLine("# kNN-VC Perf Runner — total elapsed only (per-stage breakdown via Profiler ProfilerMarker)");
            sb.AppendLine("stage,count,mean_ms,min_ms,max_ms,p95_ms");
            sb.AppendLine($"total,{_total.count},{_total.MeanMs:F2},{_total.minMs:F2},{_total.maxMs:F2},{_total.P95Ms:F2}");
            // 個別サンプル (regression 解析しやすいよう全件出す)
            sb.AppendLine();
            sb.AppendLine("idx,sample_ms");
            for (int i = 0; i < _total.samples.Count; i++)
                sb.AppendLine($"{i},{_total.samples[i]:F2}");

            File.WriteAllText(path, sb.ToString());
            _statusLine = $"saved {path}";
            Debug.Log($"[VcPerfRunner] CSV: {path}");
        }

        // ── IMGUI 表示 ───────────────────────────────────────────────────

        // 大きめフォント (高解像度ディスプレイ対策)
        static GUIStyle s_labelStyle;
        static GUIStyle s_titleStyle;
        static GUIStyle s_buttonStyle;

        static void EnsureStyles()
        {
            if (s_labelStyle == null)
            {
                s_labelStyle = new GUIStyle(GUI.skin.label) { fontSize = 18 };
                s_titleStyle = new GUIStyle(GUI.skin.box) { fontSize = 20, alignment = TextAnchor.UpperLeft, fontStyle = FontStyle.Bold };
                s_buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = 18 };
            }
        }

        void OnGUI()
        {
            EnsureStyles();
            const int w = 880, h = 320;
            const int pad = 18;
            GUI.Box(new Rect(10, 10, w, h), "kNN-VC Perf Runner — per-stage breakdown: Profiler 'VC.*' markers", s_titleStyle);

            int y = 56;
            GUI.Label(new Rect(pad + 10, y, w - pad * 2, 28), _statusLine, s_labelStyle); y += 32;
            GUI.Label(new Rect(pad + 10, y, w - pad * 2, 28), "[1..4] convert   [B] batch   [R] reset   [S] save CSV", s_labelStyle); y += 36;

            // ボタン
            int bx = pad + 10;
            int bw = 60;
            int bh = 32;
            if (GUI.Button(new Rect(bx, y, bw, bh), "1", s_buttonStyle)) ConvertOne(0); bx += bw + 6;
            if (GUI.Button(new Rect(bx, y, bw, bh), "2", s_buttonStyle)) ConvertOne(1); bx += bw + 6;
            if (GUI.Button(new Rect(bx, y, bw, bh), "3", s_buttonStyle)) ConvertOne(2); bx += bw + 6;
            if (GUI.Button(new Rect(bx, y, bw, bh), "4", s_buttonStyle)) ConvertOne(3); bx += bw + 16;
            if (GUI.Button(new Rect(bx, y, 110, bh), "Batch", s_buttonStyle) && !_busy) StartCoroutine(RunBatch()); bx += 116;
            if (GUI.Button(new Rect(bx, y, 90,  bh), "Reset", s_buttonStyle)) ResetStats(); bx += 96;
            if (GUI.Button(new Rect(bx, y, 130, bh), "Save CSV", s_buttonStyle)) SaveCsv();
            y += bh + 14;

            DrawHeader(y); y += 30;
            DrawRow(y, "total", _total);
        }

        static void DrawHeader(int y)
        {
            const int x0 = 28;
            GUI.Label(new Rect(x0,        y, 110, 26), "stage", s_labelStyle);
            GUI.Label(new Rect(x0 + 130,  y, 100, 26), "count", s_labelStyle);
            GUI.Label(new Rect(x0 + 240,  y, 130, 26), "mean", s_labelStyle);
            GUI.Label(new Rect(x0 + 380,  y, 130, 26), "min", s_labelStyle);
            GUI.Label(new Rect(x0 + 520,  y, 130, 26), "max", s_labelStyle);
            GUI.Label(new Rect(x0 + 660,  y, 130, 26), "p95", s_labelStyle);
        }

        static void DrawRow(int y, string label, StageStats s)
        {
            const int x0 = 28;
            GUI.Label(new Rect(x0,        y, 110, 26), label, s_labelStyle);
            GUI.Label(new Rect(x0 + 130,  y, 100, 26), s.count.ToString(), s_labelStyle);
            GUI.Label(new Rect(x0 + 240,  y, 130, 26), $"{s.MeanMs:F0}ms", s_labelStyle);
            GUI.Label(new Rect(x0 + 380,  y, 130, 26), s.count > 0 ? $"{s.minMs:F0}ms" : "-", s_labelStyle);
            GUI.Label(new Rect(x0 + 520,  y, 130, 26), s.count > 0 ? $"{s.maxMs:F0}ms" : "-", s_labelStyle);
            GUI.Label(new Rect(x0 + 660,  y, 130, 26), s.count > 0 ? $"{s.P95Ms:F0}ms" : "-", s_labelStyle);
        }
    }
}
