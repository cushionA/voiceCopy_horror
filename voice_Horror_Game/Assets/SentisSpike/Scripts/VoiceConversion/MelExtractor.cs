// MelExtractor.cs — C# DSP for log-mel spectrogram extraction
// voice_horror Phase 3 (2026-05-07)
//
// Two modes:
//   Feature mel (16 kHz): campplus input [1,T,80]  / tokenizer input [1,128,T]
//   Acoustic mel (22050 Hz): DiT mu/cond [1,80,T]  / hift input [1,80,T]
//
// FFT: Cooley-Tukey radix-2 (in-place, power-of-2 sizes only)
// Resampler: linear interpolation

using System;
using UnityEngine;

namespace VoiceHorror.VC
{
    public static class MelExtractor
    {
        // ── Feature mel config (campplus / tokenizer) ─────────────────────
        const int   k_FeatSR      = 16000;
        const int   k_FeatNFft    = 512;
        const int   k_FeatHop     = 160;
        const int   k_FeatWin     = 400;
        const float k_FeatLogClamp = 1e-9f;

        // ── Acoustic mel config (DiT mu / hift) ───────────────────────────
        const int   k_AcouSR      = 22050;
        const int   k_AcouNFft    = 1024;
        const int   k_AcouHop     = 256;
        const int   k_AcouWin     = 1024;
        const float k_AcouLogClamp = 1e-5f;

        // ── Caches ────────────────────────────────────────────────────────
        static float[]   s_FeatWindow;
        static float[]   s_AcouWindow;
        static float[,]  s_FeatMel80;
        static float[,]  s_FeatMel128;
        static float[,]  s_AcouMel80;

        // ════════════════════════════════════════════════════════════════
        // Public API
        // ════════════════════════════════════════════════════════════════

        // Resample float[] to a new sample rate (linear interpolation).
        public static float[] Resample(float[] audio, int srcRate, int dstRate)
        {
            if (srcRate == dstRate) return audio;
            double ratio  = (double)dstRate / srcRate;
            int    outLen = (int)(audio.Length * ratio);
            float[] result = new float[outLen];
            for (int i = 0; i < outLen; i++)
            {
                double srcIdx = i / ratio;
                int lo = (int)srcIdx;
                int hi = Math.Min(lo + 1, audio.Length - 1);
                float t = (float)(srcIdx - lo);
                result[i] = audio[lo] * (1f - t) + audio[hi] * t;
            }
            return result;
        }

        // ── Feature mel ─────────────────────────────────────────────────

        // campplus input: [1, T, 80] → we return [T, 80] (caller adds batch dim)
        // Apply utterance-level CMVN for campplus.
        public static float[,] ExtractFeatureMel80(float[] audio16k)
        {
            float[,] mel = ExtractMel(audio16k,
                nMels: 80, fMax: k_FeatSR / 2,
                nFft: k_FeatNFft, hop: k_FeatHop, win: k_FeatWin,
                logClamp: k_FeatLogClamp, ref s_FeatWindow, ref s_FeatMel80,
                transposed: false);
            ApplyCmvn(mel);   // utterance-level CMVN
            return mel;       // shape [T, 80]
        }

        // tokenizer input: [1, 128, T] → return [128, T]
        public static float[,] ExtractFeatureMel128(float[] audio16k)
        {
            float[,] mel = ExtractMel(audio16k,
                nMels: 128, fMax: k_FeatSR / 2,
                nFft: k_FeatNFft, hop: k_FeatHop, win: k_FeatWin,
                logClamp: k_FeatLogClamp, ref s_FeatWindow, ref s_FeatMel128,
                transposed: true);   // returns [128, T]
            return mel;
        }

        // ── Acoustic mel ─────────────────────────────────────────────────

        // DiT mu/cond and hift input: [1, 80, T] → return [80, T]
        // Caller pads to T=100 for DiT or passes full T to hift.
        public static float[,] ExtractAcousticMel(float[] audio22050k)
        {
            float[,] mel = ExtractMel(audio22050k,
                nMels: 80, fMax: k_AcouSR / 2,
                nFft: k_AcouNFft, hop: k_AcouHop, win: k_AcouWin,
                logClamp: k_AcouLogClamp, ref s_AcouWindow, ref s_AcouMel80,
                transposed: true);   // returns [80, T]
            return mel;
        }

        // Pad or truncate acoustic mel [80, T_src] → [80, T_target]
        public static float[,] PadOrTruncate(float[,] mel80xT, int targetT)
        {
            int srcT = mel80xT.GetLength(1);
            if (srcT == targetT) return mel80xT;

            float[,] result = new float[80, targetT];
            int copyT = Math.Min(srcT, targetT);
            for (int m = 0; m < 80; m++)
                for (int t = 0; t < copyT; t++)
                    result[m, t] = mel80xT[m, t];
            // remaining frames stay zero (padding)
            return result;
        }

        // Return number of acoustic mel frames for a given audio length at 22050 Hz.
        // With center-padding n_fft//2 on each side: nFrames = (audio.Length + n_fft - n_fft) / hop + 1
        public static int AcousticMelFrames(float[] audio22050)
            => audio22050.Length / k_AcouHop + 1;

        // ════════════════════════════════════════════════════════════════
        // Core: log-mel spectrogram
        // ════════════════════════════════════════════════════════════════

        // Returns [T, nMels] when transposed=false, [nMels, T] when transposed=true.
        static float[,] ExtractMel(float[] audio,
            int nMels, int fMax,
            int nFft, int hop, int win, float logClamp,
            ref float[] windowCache, ref float[,] fbCache,
            bool transposed)
        {
            float[] window = GetHannWindow(win, ref windowCache);
            float[,] fb    = GetFilterbank(nMels, nFft, fMax, ref fbCache);

            // Center padding (reflect)
            int     pad    = nFft / 2;
            float[] padded = new float[audio.Length + pad * 2];
            Array.Copy(audio, 0, padded, pad, audio.Length);
            for (int i = 0; i < pad && i < audio.Length; i++)
            {
                padded[pad - 1 - i]                    = audio[i];
                padded[padded.Length - pad + i]        = audio[audio.Length - 1 - i];
            }

            int nFreqs  = nFft / 2 + 1;
            int nFrames = (padded.Length - nFft) / hop + 1;

            float[,] logMelTF = new float[nFrames, nMels];
            float[]  frame    = new float[nFft];
            float[]  real     = new float[nFft];
            float[]  imag     = new float[nFft];
            float[]  power    = new float[nFreqs];

            for (int fr = 0; fr < nFrames; fr++)
            {
                int start   = fr * hop;
                int leftPad = (nFft - win) / 2;

                Array.Clear(frame, 0, nFft);
                int copyLen = Math.Min(win, padded.Length - start);
                for (int i = 0; i < copyLen; i++)
                    frame[leftPad + i] = padded[start + i] * window[i];

                Fft(frame, real, imag, nFft);

                for (int k = 0; k < nFreqs; k++)
                    power[k] = real[k] * real[k] + imag[k] * imag[k];

                for (int m = 0; m < nMels; m++)
                {
                    float sum = 0f;
                    for (int k = 0; k < nFreqs; k++)
                        sum += fb[m, k] * power[k];
                    logMelTF[fr, m] = MathF.Log(MathF.Max(sum, logClamp));
                }
            }

            if (!transposed) return logMelTF; // [T, nMels]

            // Transpose to [nMels, T]
            float[,] logMelFT = new float[nMels, nFrames];
            for (int m = 0; m < nMels; m++)
                for (int t = 0; t < nFrames; t++)
                    logMelFT[m, t] = logMelTF[t, m];
            return logMelFT; // [nMels, T]
        }

        // ════════════════════════════════════════════════════════════════
        // Helpers
        // ════════════════════════════════════════════════════════════════

        // Utterance-level CMVN on [T, F] mel (in-place).
        static void ApplyCmvn(float[,] mel)
        {
            int T = mel.GetLength(0), F = mel.GetLength(1);
            for (int f = 0; f < F; f++)
            {
                double mean = 0, var = 0;
                for (int t = 0; t < T; t++) mean += mel[t, f];
                mean /= T;
                for (int t = 0; t < T; t++) var += (mel[t, f] - mean) * (mel[t, f] - mean);
                float std = (float)Math.Sqrt(var / T + 1e-9);
                for (int t = 0; t < T; t++) mel[t, f] = (float)((mel[t, f] - mean) / std);
            }
        }

        // Triangular mel filterbank [nMels, nFft/2+1].
        static float[,] GetFilterbank(int nMels, int nFft, int fMax, ref float[,] cache)
        {
            if (cache != null && cache.GetLength(0) == nMels) return cache;

            int nFreqs = nFft / 2 + 1;
            // Use sample rate derived from nFft and nFreqs to convert freq bins to Hz.
            // We store the cache per (nMels, nFft) pair implicitly via ref.
            cache = BuildFilterbank(nMels, nFreqs, nFft, fMax);
            return cache;
        }

        // Build filterbank given nFft and fMax (SR = 2*fMax).
        static float[,] BuildFilterbank(int nMels, int nFreqs, int nFft, int fMax)
        {
            int sr = fMax * 2;

            Func<float, float> hz2mel = hz => 2595f * MathF.Log10(1f + hz / 700f);
            Func<float, float> mel2hz = mel => 700f * (MathF.Pow(10f, mel / 2595f) - 1f);

            float melMin = hz2mel(0f);
            float melMax = hz2mel(fMax);

            float[] melPts = new float[nMels + 2];
            for (int i = 0; i < nMels + 2; i++)
                melPts[i] = melMin + (melMax - melMin) * i / (nMels + 1);

            float[] binPts = new float[nMels + 2];
            for (int i = 0; i < nMels + 2; i++)
                binPts[i] = (float)Math.Floor(mel2hz(melPts[i]) / sr * nFft + 0.5f);

            float[,] fb = new float[nMels, nFreqs];
            for (int m = 0; m < nMels; m++)
            {
                float lo = binPts[m], center = binPts[m + 1], hi = binPts[m + 2];
                for (int k = (int)lo; k < (int)center && k < nFreqs; k++)
                    if (k >= 0 && center > lo)
                        fb[m, k] = (k - lo) / (center - lo);
                for (int k = (int)center; k < (int)hi && k < nFreqs; k++)
                    if (k >= 0 && hi > center)
                        fb[m, k] = (hi - k) / (hi - center);
            }
            return fb;
        }

        static float[] GetHannWindow(int size, ref float[] cache)
        {
            if (cache != null && cache.Length == size) return cache;
            cache = new float[size];
            for (int i = 0; i < size; i++)
                cache[i] = 0.5f * (1f - MathF.Cos(2f * MathF.PI * i / (size - 1)));
            return cache;
        }

        // ── Cooley-Tukey radix-2 FFT (in-place) ─────────────────────────

        static void Fft(float[] data, float[] real, float[] imag, int n)
        {
            for (int i = 0; i < n; i++) { real[i] = data[i]; imag[i] = 0f; }

            int bits = BitLen(n);
            for (int i = 1; i < n; i++)
            {
                int j = BitReverse(i, bits);
                if (j > i) { Swap(ref real[i], ref real[j]); Swap(ref imag[i], ref imag[j]); }
            }

            for (int len = 2; len <= n; len <<= 1)
            {
                float ang = -2f * MathF.PI / len;
                float wRe = MathF.Cos(ang), wIm = MathF.Sin(ang);
                for (int i = 0; i < n; i += len)
                {
                    float curRe = 1f, curIm = 0f;
                    for (int j = 0; j < len >> 1; j++)
                    {
                        int a = i + j, b = i + j + (len >> 1);
                        float vRe = real[b] * curRe - imag[b] * curIm;
                        float vIm = real[b] * curIm + imag[b] * curRe;
                        real[b] = real[a] - vRe; imag[b] = imag[a] - vIm;
                        real[a] += vRe;           imag[a] += vIm;
                        float nr = curRe * wRe - curIm * wIm;
                        curIm = curRe * wIm + curIm * wRe;
                        curRe = nr;
                    }
                }
            }
        }

        static int BitLen(int n) { int b = 0; while ((1 << b) < n) b++; return b; }

        static int BitReverse(int x, int bits)
        {
            int r = 0;
            for (int i = 0; i < bits; i++) { r = (r << 1) | (x & 1); x >>= 1; }
            return r;
        }

        static void Swap(ref float a, ref float b) { float t = a; a = b; b = t; }
    }
}
