// VcPerfRunner.cs — Phase 8 着手: PlayMode パフォーマンス計測ランナー
// voice_horror Phase 8 (2026-05-09)
//
// Goal:
//   PlayMode シーンで kNN-VC の変換負荷を自動シーケンスで観察する。
//   段階別の細かい内訳は Unity Profiler の ProfilerMarker (VC.Total /
//   VC.Extract / VC.kNN / VC.Vocode) で見る。本 Runner は IMGUI 上に
//   2 段階 (warmup / steady) の集計を出し、終了時に CSV を自動書き出す。
//
// シーケンス (Play 押下時に自動進行):
//   1. Initialize + WarmupAsync (extractor / vocoder のカーネル JIT)
//   2. TargetPool 構築 (target AudioClip → WavLM forward → pool)
//   3. Warmup 変換: sources[0] を 1 回 (kNN 経路の cold start 解消、stats には記録しない)
//   4. Single pass: 各 source × 1 回 (stats=single)
//   5. Batch: batchIterations × sources (stats=batch)
//   6. CSV 自動保存
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
        [Tooltip("変換対象 source clip (順に処理。null は skip)")]
        [SerializeField] AudioClip[] sources = new AudioClip[4];

        [Header("Run")]
        [Tooltip("バッチ反復回数 (sources を順に何セット回すか)")]
        [SerializeField] int batchIterations = 10;

        [Tooltip("変換 alpha (1.0 = target only)")]
        [Range(0f, 1f)]
        [SerializeField] float alpha = 1.0f;

        // ── Stats ───────────────────────────────────────────────────────
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

        StageStats _single = StageStats.New();
        StageStats _batch  = StageStats.New();

        string _statusLine = "(initializing)";

        // ── Lifecycle ───────────────────────────────────────────────────

        IEnumerator Start()
        {
            // Profiler を見やすくするため 60fps 固定
            // (vSync を切らないと targetFrameRate が無視される環境がある)
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;

            if (service == null)
            {
                _statusLine = "ERROR: service is not assigned";
                Debug.LogError("[VcPerfRunner] service field not assigned");
                yield break;
            }

            _statusLine = "Initialize + Warmup...";
            yield return null;
            service.Initialize();
            yield return service.WarmupAsync();

            if (targetClip == null)
            {
                _statusLine = "ERROR: targetClip is not assigned";
                Debug.LogError("[VcPerfRunner] targetClip not assigned");
                yield break;
            }

            _statusLine = $"Building target pool from {targetClip.name}...";
            yield return null;
            var swPool = Stopwatch.StartNew();
            service.AccumulateTargetVoice(targetClip);
            swPool.Stop();
            Debug.Log($"[VcPerfRunner] TargetPool built: {service.TargetPool.FrameCount} frames in {swPool.ElapsedMilliseconds}ms");

            yield return RunFullSequence();
        }

        IEnumerator RunFullSequence()
        {
            // (a) Warmup conversion: kNN/vocode 経路の cold start を吸収。stats には記録しない。
            AudioClip firstSource = FindFirstNonNull();
            if (firstSource == null)
            {
                _statusLine = "ERROR: no non-null sources";
                yield break;
            }
            _statusLine = $"Warmup convert (discarded): {firstSource.name}";
            yield return null;
            ConvertClip(firstSource, recordTo: null);
            yield return null;

            // (b) Single pass: 各 source × 1
            int singleCount = 0;
            for (int i = 0; i < sources.Length; i++)
            {
                if (sources[i] == null) continue;
                _statusLine = $"Single pass [{singleCount + 1}/{NonNullSourceCount()}]: {sources[i].name}";
                yield return null;
                ConvertClip(sources[i], recordTo: SingleRef);
                singleCount++;
                yield return null;
            }

            // (c) Batch: batchIterations × sources
            int total = batchIterations * NonNullSourceCount();
            int run = 0;
            for (int iter = 0; iter < batchIterations; iter++)
            {
                for (int i = 0; i < sources.Length; i++)
                {
                    if (sources[i] == null) continue;
                    run++;
                    _statusLine = $"Batch [{run}/{total}]: {sources[i].name} (iter {iter + 1}/{batchIterations})";
                    ConvertClip(sources[i], recordTo: BatchRef);
                    yield return null;
                }
            }

            // (d) CSV 自動保存
            string csv = SaveCsv();

            _statusLine =
                $"DONE. single n={_single.count} mean={_single.MeanMs:F0}ms p95={_single.P95Ms:F0}ms / " +
                $"batch n={_batch.count} mean={_batch.MeanMs:F0}ms p95={_batch.P95Ms:F0}ms";
            Debug.Log($"[VcPerfRunner] {_statusLine}\n[VcPerfRunner] CSV: {csv}");
        }

        // ── Helpers ─────────────────────────────────────────────────────

        // recordTo は ref への delegate 代わりに「どっちに記録するか」を選ぶフラグ
        // (struct は ref で渡せないので、明示的に代入する小さなコールバック)
        delegate void StatsRef(double ms);
        void SingleRef(double ms) => _single.Record(ms);
        void BatchRef(double ms)  => _batch.Record(ms);

        AudioClip FindFirstNonNull()
        {
            for (int i = 0; i < sources.Length; i++)
                if (sources[i] != null) return sources[i];
            return null;
        }

        int NonNullSourceCount()
        {
            int c = 0;
            for (int i = 0; i < sources.Length; i++) if (sources[i] != null) c++;
            return c;
        }

        void ConvertClip(AudioClip clip, StatsRef recordTo)
        {
            var sw = Stopwatch.StartNew();
            try
            {
                service.Convert(clip, alpha);
            }
            catch (System.Exception ex)
            {
                Debug.LogError($"[VcPerfRunner] Convert FAILED: {ex.GetType().Name}: {ex.Message}");
                return;
            }
            sw.Stop();
            recordTo?.Invoke(sw.Elapsed.TotalMilliseconds);
        }

        string SaveCsv()
        {
            string repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
            string outDir = Path.Combine(repoRoot, "VcTestOutput");
            Directory.CreateDirectory(outDir);
            string ts = System.DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string path = Path.Combine(outDir, $"perf_{ts}.csv");

            var sb = new StringBuilder();
            sb.AppendLine("# kNN-VC Perf Runner — total elapsed only (per-stage breakdown via Profiler ProfilerMarker)");
            sb.AppendLine("stage,count,mean_ms,min_ms,max_ms,p95_ms");
            sb.AppendLine($"single,{_single.count},{_single.MeanMs:F2},{_single.minMs:F2},{_single.maxMs:F2},{_single.P95Ms:F2}");
            sb.AppendLine($"batch,{_batch.count},{_batch.MeanMs:F2},{_batch.minMs:F2},{_batch.maxMs:F2},{_batch.P95Ms:F2}");
            sb.AppendLine();
            sb.AppendLine("stage,idx,sample_ms");
            for (int i = 0; i < _single.samples.Count; i++) sb.AppendLine($"single,{i},{_single.samples[i]:F2}");
            for (int i = 0; i < _batch.samples.Count; i++)  sb.AppendLine($"batch,{i},{_batch.samples[i]:F2}");

            File.WriteAllText(path, sb.ToString());
            return path;
        }

        // ── IMGUI 表示 ───────────────────────────────────────────────────

        static GUIStyle s_labelStyle;
        static GUIStyle s_titleStyle;

        static void EnsureStyles()
        {
            if (s_labelStyle == null)
            {
                s_labelStyle = new GUIStyle(GUI.skin.label) { fontSize = 18 };
                s_titleStyle = new GUIStyle(GUI.skin.box)
                {
                    fontSize = 20,
                    alignment = TextAnchor.UpperLeft,
                    fontStyle = FontStyle.Bold,
                };
            }
        }

        void OnGUI()
        {
            EnsureStyles();
            const int w = 880, h = 240;
            const int pad = 18;
            GUI.Box(new Rect(10, 10, w, h), "kNN-VC Perf Runner — Profiler の 'VC.*' マーカーで段階別を見る", s_titleStyle);

            int y = 56;
            GUI.Label(new Rect(pad + 10, y, w - pad * 2, 28), _statusLine, s_labelStyle); y += 36;

            DrawHeader(y); y += 30;
            DrawRow(y, "single", _single); y += 28;
            DrawRow(y, "batch",  _batch);
        }

        static void DrawHeader(int y)
        {
            const int x0 = 28;
            GUI.Label(new Rect(x0,        y, 110, 26), "stage", s_labelStyle);
            GUI.Label(new Rect(x0 + 130,  y, 100, 26), "count", s_labelStyle);
            GUI.Label(new Rect(x0 + 240,  y, 130, 26), "mean",  s_labelStyle);
            GUI.Label(new Rect(x0 + 380,  y, 130, 26), "min",   s_labelStyle);
            GUI.Label(new Rect(x0 + 520,  y, 130, 26), "max",   s_labelStyle);
            GUI.Label(new Rect(x0 + 660,  y, 130, 26), "p95",   s_labelStyle);
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
