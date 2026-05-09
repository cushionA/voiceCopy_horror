// SpeakerMorphController.cs — Speaker embedding interpolation for ghost voice morphing
// voice_horror Phase 3 (2026-05-07)
//
// ゲームの核心メカニクス:
//   少女幽霊の声 (girlGhostEmb) とプレイヤーの声 (playerEmb) の間を補間する。
//   プレイヤーが声を出すほど少女の声に近づき、エンドロール直前に類似度判定。
//
// Usage:
//   Attach to a persistent GameObject (e.g., GameManager child).
//   Call RecordPlayerVoice() when capturing mic input.
//   Call GetMorphedEmbedding() to get the interpolated spk_emb for DiT.

using System;
using UnityEngine;

namespace VoiceHorror.VC
{
    [DisallowMultipleComponent]
    public class SpeakerMorphController : MonoBehaviour
    {
        [Header("Embeddings")]
        [Tooltip("少女幽霊の speaker embedding [192]. ExtractSpeakerEmbedding で事前計算。")]
        public float[] girlGhostEmb;

        [Tooltip("プレイヤーの最新 speaker embedding [192]. RecordPlayerVoice で更新。")]
        [HideInInspector] public float[] playerEmb;

        [Header("Morph Settings")]
        [Range(0f, 1f)]
        [Tooltip("0 = all girl ghost, 1 = all player voice")]
        public float morphRatio = 0f;

        [Tooltip("プレイヤーが声を出すたびに少女の声に近づく速度")]
        public float morphSpeedPerVoice = 0.05f;

        [Tooltip("時間経過でモーフが減少する速度 (半分/秒) — 時間経過で増加分の半分まで減少するゲームメカニクス")]
        public float decayHalfLife = 30f;  // seconds

        // 声を出した累積モーフ分 (増加量のみ追跡して減衰計算に使う)
        float _accumulatedMorph;
        float _lastVoiceTime;

        // ── Lifecycle ─────────────────────────────────────────────────────

        void Update()
        {
            ApplyDecay();
        }

        // ── Public API ────────────────────────────────────────────────────

        // プレイヤーが声を出したときに呼ぶ。
        // newPlayerEmb: VoiceConversionPipeline.ExtractSpeakerEmbedding の出力 [192]
        public void RecordPlayerVoice(float[] newPlayerEmb)
        {
            playerEmb = newPlayerEmb;

            _accumulatedMorph  = Mathf.Min(_accumulatedMorph + morphSpeedPerVoice, 1f);
            _lastVoiceTime     = Time.time;
            morphRatio         = Mathf.Clamp01(morphRatio + morphSpeedPerVoice);

            Debug.Log($"[Morph] PlayerVoice recorded. morphRatio={morphRatio:F3}");
        }

        // DiT の spks に渡す前に SpkEmbedProjection.Project() に通す。
        // Returns float[192] — interpolated embedding.
        public float[] GetMorphedEmbedding()
        {
            if (girlGhostEmb == null || girlGhostEmb.Length != 192)
            {
                Debug.LogWarning("[Morph] girlGhostEmb not set. Returning zero embedding.");
                return new float[192];
            }

            if (playerEmb == null || playerEmb.Length != 192)
                return girlGhostEmb; // no player voice yet → pure girl ghost

            float t = Mathf.Clamp01(morphRatio);
            float[] result = new float[192];
            for (int i = 0; i < 192; i++)
                result[i] = Lerp(girlGhostEmb[i], playerEmb[i], t);
            return result;
        }

        // 声類似度スコア (cosine similarity) — エンドロール直前の分岐判定に使う。
        // > 0.85 → BAD END (カラダを奪われる)、< 0.85 → GOOD END
        public float ComputeSimilarity()
        {
            if (girlGhostEmb == null || playerEmb == null) return 0f;
            return CosineSimilarity(girlGhostEmb, playerEmb);
        }

        // ── Decay (ゲームメカニクス: 時間経過で増加分の半分まで減少) ─────────

        void ApplyDecay()
        {
            if (_accumulatedMorph <= 0f) return;

            float elapsed = Time.time - _lastVoiceTime;
            if (elapsed < 0.5f) return; // grace period after voice

            // Decay: accumulated → accumulated/2 over decayHalfLife seconds
            float decayRate = Mathf.Log(2f) / decayHalfLife;
            float decayed   = _accumulatedMorph * Mathf.Exp(-decayRate * Time.deltaTime);
            float delta     = _accumulatedMorph - decayed;
            _accumulatedMorph  = decayed;
            morphRatio         = Mathf.Max(0f, morphRatio - delta);
        }

        // ── Static helpers ────────────────────────────────────────────────

        static float Lerp(float a, float b, float t) => a + (b - a) * t;

        static float CosineSimilarity(float[] a, float[] b)
        {
            double dot = 0, normA = 0, normB = 0;
            for (int i = 0; i < a.Length; i++)
            {
                dot   += a[i] * b[i];
                normA += a[i] * a[i];
                normB += b[i] * b[i];
            }
            double denom = Math.Sqrt(normA) * Math.Sqrt(normB);
            return (float)(denom < 1e-9 ? 0 : dot / denom);
        }
    }
}
