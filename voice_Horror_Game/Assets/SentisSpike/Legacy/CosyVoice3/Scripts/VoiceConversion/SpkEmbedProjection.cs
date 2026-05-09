// SpkEmbedProjection.cs — Linear 192→80 speaker embedding projection
// voice_horror Phase 3 (2026-05-07)
//
// campplus outputs [1, 192]. DiT expects spks [1, 80].
// The projection (CausalConditionalCFM.spk_embed_affine_layer) is outside the DiT ONNX.
//
// Weight loading:
//   1. Run voiceCoppy_test/extract_spk_projection.py to export JSON.
//   2. Place spk_projection.json in Assets/StreamingAssets/ (or Resources/).
//   3. Call LoadFromJson(path). If not found, falls back to truncation.
//
// API:
//   Project(float[192]) → float[80]

using System;
using System.IO;
using UnityEngine;

namespace VoiceHorror.VC
{
    public class SpkEmbedProjection
    {
        const int k_InDim  = 192;
        const int k_OutDim = 80;

        // weight[out, in], bias[out]
        readonly float[,] _weight;
        readonly float[]  _bias;
        readonly bool     _hasWeights;

        // ── Constructors ─────────────────────────────────────────────────

        // Truncation fallback (first 80 dims of 192-dim embedding).
        public SpkEmbedProjection()
        {
            _weight    = null;
            _bias      = null;
            _hasWeights = false;
            Debug.LogWarning("[SpkEmbed] No weights loaded. Using truncation fallback (quality degraded).");
        }

        // Load from extracted JSON (run extract_spk_projection.py first).
        public SpkEmbedProjection(string jsonPath)
        {
            try
            {
                string json = File.ReadAllText(jsonPath);
                var data    = JsonUtility.FromJson<WeightData>(json);

                if (data.weight == null || data.bias == null)
                    throw new Exception("JSON missing weight or bias field.");

                // data.weight is flat [out*in] row-major
                if (data.weight.Length != k_OutDim * k_InDim)
                    throw new Exception($"Weight length mismatch: got {data.weight.Length}, expected {k_OutDim * k_InDim}");

                _weight = new float[k_OutDim, k_InDim];
                for (int o = 0; o < k_OutDim; o++)
                    for (int i = 0; i < k_InDim; i++)
                        _weight[o, i] = data.weight[o * k_InDim + i];

                _bias       = data.bias;
                _hasWeights = true;
                Debug.Log($"[SpkEmbed] Loaded projection weights from {jsonPath}");
            }
            catch (Exception e)
            {
                _weight    = null;
                _bias      = null;
                _hasWeights = false;
                Debug.LogWarning($"[SpkEmbed] Failed to load {jsonPath}: {e.Message}. Using truncation fallback.");
            }
        }

        // ── Factory helper ────────────────────────────────────────────────

        // Try StreamingAssets first, then Resources.
        public static SpkEmbedProjection Load()
        {
            string sa = Path.Combine(Application.streamingAssetsPath, "spk_projection.json");
            if (File.Exists(sa)) return new SpkEmbedProjection(sa);

            // Try Resources (requires TextAsset wrapper and is baked into build)
            var ta = Resources.Load<TextAsset>("spk_projection");
            if (ta != null)
            {
                string tmpPath = Path.Combine(Application.temporaryCachePath, "spk_projection.json");
                File.WriteAllText(tmpPath, ta.text);
                return new SpkEmbedProjection(tmpPath);
            }

            Debug.LogWarning("[SpkEmbed] spk_projection.json not found. Run extract_spk_projection.py.");
            return new SpkEmbedProjection(); // truncation fallback
        }

        // ── Project 192 → 80 ─────────────────────────────────────────────

        // Input:  spkEmb192[192]
        // Output: spkEmb80[80]  (DiT spks input after unsqueeze → [1, 80])
        public float[] Project(float[] spkEmb192)
        {
            if (spkEmb192 == null || spkEmb192.Length != k_InDim)
                throw new ArgumentException($"spkEmb192 must have {k_InDim} elements, got {spkEmb192?.Length}");

            float[] out80 = new float[k_OutDim];

            if (!_hasWeights)
            {
                // Truncation fallback: first 80 dims
                Array.Copy(spkEmb192, out80, k_OutDim);
                return out80;
            }

            // Linear: out = weight @ in + bias
            for (int o = 0; o < k_OutDim; o++)
            {
                float sum = _bias[o];
                for (int i = 0; i < k_InDim; i++)
                    sum += _weight[o, i] * spkEmb192[i];
                out80[o] = sum;
            }
            return out80;
        }

        // ── JSON schema ───────────────────────────────────────────────────

        [Serializable]
        class WeightData
        {
            public float[] weight;  // flat [k_OutDim * k_InDim] row-major
            public float[] bias;    // [k_OutDim]
        }
    }
}
