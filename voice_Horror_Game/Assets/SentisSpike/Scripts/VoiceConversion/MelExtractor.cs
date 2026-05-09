// MelExtractor.cs — C# DSP for log-mel spectrogram extraction
// voice_horror Phase 3 (2026-05-07)  /  Phase 4 fix (2026-05-07)
//
// Two modes:
//   Feature mel (16 kHz): campplus input [1,T,80]  / tokenizer input [1,128,T]
//   Acoustic mel (24 kHz): DiT mu/cond [1,80,T]  / hift input [1,80,T]
//
// Acoustic mel parameters verified against cosyvoice3.yaml + matcha/utils/audio.py:
//   sample_rate=24000, n_fft=1920, hop=480, win=1920
//   fmin=0, fmax=null (→ sr/2 = 12000)
//   center=False → padding = (n_fft - hop)/2 = 720 samples each side (reflect)
//   spectrum: magnitude sqrt(re²+im²+1e-9)  — NOT power
//   filterbank: librosa Slaney normalization (norm=1, default)
//   log: log(clamp(x, 1e-5))
//
// FFT note:
//   n_fft=1920 is NOT a power-of-2. We zero-pad frames from 1920 to 2048 for
//   radix-2 FFT. The filterbank is built for n_fft=2048 (1025 bins at 11.72 Hz
//   vs 12.5 Hz ideal). This 6.7% resolution difference is small relative to
//   mel bin bandwidth and acceptable for VC quality.
//
// Resampler: linear interpolation

using System;
using UnityEngine;

namespace VoiceHorror.VC
{
    public static class MelExtractor
    {
        // ── Feature mel config (campplus / tokenizer, 16 kHz) ─────────────
        const int   k_FeatSR       = 16000;
        const int   k_FeatNFft     = 512;
        const int   k_FeatHop      = 160;
        const int   k_FeatWin      = 400;
        const float k_FeatLogClamp = 1e-9f;

        // ── Acoustic mel config (DiT mu / hift, 24 kHz) ───────────────────
        // Source: cosyvoice3.yaml feat_extractor + matcha/utils/audio.py
        const int   k_AcouSR       = 24000;
        const int   k_AcouNFft     = 1920;   // window / frame size (from yaml)
        const int   k_AcouFFTSize  = 2048;   // actual FFT size (next pow2 of 1920)
        const int   k_AcouHop      = 480;
        const int   k_AcouWin      = 1920;   // same as n_fft
        const float k_AcouLogClamp = 1e-5f;
        // fmax = null → sr/2 = 12000
        // center = False → padding = (n_fft - hop)/2 = 720 samples each side

        // ── Caches ────────────────────────────────────────────────────────
        static float[]   s_FeatWindow;
        static float[]   s_AcouWindow;
        static float[,]  s_FeatMel80;
        static float[,]  s_FeatMel128;
        static float[,]  s_AcouMel80;   // Slaney-normalized, built for k_AcouFFTSize

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
            float[,] mel = ExtractMelCore(audio16k,
                nMels: 80, fMax: k_FeatSR / 2,
                nFft: k_FeatNFft, fftSize: k_FeatNFft,
                hop: k_FeatHop, win: k_FeatWin,
                logClamp: k_FeatLogClamp,
                padMode: PadMode.HalfNFft,
                spectrum: SpecMode.Power,
                slaneyNorm: false,
                ref s_FeatWindow, ref s_FeatMel80,
                transposed: false);
            ApplyCmvn(mel);
            return mel; // [T, 80]
        }

        // tokenizer input: [1, 128, T] → return [128, T]
        public static float[,] ExtractFeatureMel128(float[] audio16k)
        {
            return ExtractMelCore(audio16k,
                nMels: 128, fMax: k_FeatSR / 2,
                nFft: k_FeatNFft, fftSize: k_FeatNFft,
                hop: k_FeatHop, win: k_FeatWin,
                logClamp: k_FeatLogClamp,
                padMode: PadMode.HalfNFft,
                spectrum: SpecMode.Power,
                slaneyNorm: false,
                ref s_FeatWindow, ref s_FeatMel128,
                transposed: true); // [128, T]
        }

        // ── Acoustic mel ─────────────────────────────────────────────────

        // DiT mu/cond and hift input: [1, 80, T] → return [80, T]
        // Matches matcha/utils/audio.py mel_spectrogram() parameters.
        public static float[,] ExtractAcousticMel(float[] audio24k)
        {
            return ExtractMelCore(audio24k,
                nMels: 80, fMax: k_AcouSR / 2,       // fmax=null → 12000
                nFft: k_AcouNFft, fftSize: k_AcouFFTSize,  // window=1920, FFT=2048
                hop: k_AcouHop, win: k_AcouWin,
                logClamp: k_AcouLogClamp,
                padMode: PadMode.HalfNFftMinusHop,   // (n_fft - hop)/2 = 720
                spectrum: SpecMode.Magnitude,          // sqrt(re²+im²+1e-9)
                slaneyNorm: true,                      // librosa default
                ref s_AcouWindow, ref s_AcouMel80,
                transposed: true); // [80, T]
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
            return result;
        }

        // Acoustic mel frame count at 24000 Hz with (n_fft-hop)/2 padding.
        // nFrames = floor(audio.Length / hop)
        public static int AcousticMelFrames(float[] audio24k)
            => audio24k.Length / k_AcouHop;

        // ── Spectral / padding modes ─────────────────────────────────────

        enum PadMode
        {
            HalfNFft,           // nFft/2 each side (feature mel, center=True-like)
            HalfNFftMinusHop,   // (nFft-hop)/2 each side (acoustic mel, matcha style)
        }

        enum SpecMode
        {
            Power,       // re²+im² (for feature mel)
            Magnitude,   // sqrt(re²+im²+1e-9) (for acoustic mel, matches matcha/audio.py)
        }

        // ════════════════════════════════════════════════════════════════
        // Core mel extraction
        // ════════════════════════════════════════════════════════════════

        // Returns [T, nMels] when transposed=false, [nMels, T] when transposed=true.
        static float[,] ExtractMelCore(float[] audio,
            int nMels, int fMax,
            int nFft, int fftSize,   // nFft=window size, fftSize=FFT buffer (may differ)
            int hop, int win, float logClamp,
            PadMode padMode, SpecMode spectrum, bool slaneyNorm,
            ref float[] windowCache, ref float[,] fbCache,
            bool transposed)
        {
            float[] window = GetHannWindow(win, ref windowCache);

            // Filterbank is built for fftSize (accounts for zero-padding of frame)
            float[,] fb = slaneyNorm
                ? GetSlaneyFilterbank(nMels, fftSize, fMax, ref fbCache)
                : GetHTKFilterbank(nMels, fftSize, fMax, ref fbCache);

            // Padding amount
            int pad = (padMode == PadMode.HalfNFft)
                ? nFft / 2
                : (nFft - hop) / 2;  // = 720 for n_fft=1920, hop=480

            // Build padded signal (reflect mode)
            int paddedLen = audio.Length + pad * 2;
            float[] padded = new float[paddedLen];
            Array.Copy(audio, 0, padded, pad, audio.Length);

            if (padMode == PadMode.HalfNFft)
            {
                // Symmetric reflect (original feature mel behavior)
                for (int i = 0; i < pad && i < audio.Length; i++)
                {
                    padded[pad - 1 - i]            = audio[i];
                    padded[pad + audio.Length + i] = audio[audio.Length - 1 - i];
                }
            }
            else
            {
                // Exclusive reflect matching PyTorch F.pad mode='reflect'
                // left: padded[pad-1-i] = audio[i+1]  (i=0..pad-1)
                // right: padded[pad+len+i] = audio[len-2-i]  (i=0..pad-1)
                for (int i = 0; i < pad && i + 1 < audio.Length; i++)
                {
                    padded[pad - 1 - i]            = audio[i + 1];
                    padded[pad + audio.Length + i] = audio[audio.Length - 2 - i];
                }
            }

            int nFreqs  = fftSize / 2 + 1;
            int nFrames = (paddedLen - nFft) / hop + 1;

            // FFT buffers (fftSize may be larger than nFft for zero-padding)
            float[] frame = new float[fftSize];
            float[] real  = new float[fftSize];
            float[] imag  = new float[fftSize];

            float[,] logMelTF = new float[nFrames, nMels];

            for (int fr = 0; fr < nFrames; fr++)
            {
                int start   = fr * hop;
                int leftPad = (nFft - win) / 2;  // = 0 for n_fft=win=1920

                // Fill frame: apply Hann window to 'win' samples, rest stays 0
                Array.Clear(frame, 0, fftSize);
                int copyLen = Math.Min(win, paddedLen - (start + leftPad));
                for (int i = 0; i < copyLen; i++)
                    frame[leftPad + i] = padded[start + i] * window[i];
                // Zero-padding from nFft to fftSize is implicit (Array.Clear)

                Fft(frame, real, imag, fftSize);

                for (int m = 0; m < nMels; m++)
                {
                    float sum = 0f;

                    if (spectrum == SpecMode.Power)
                    {
                        for (int k = 0; k < nFreqs; k++)
                            sum += fb[m, k] * (real[k] * real[k] + imag[k] * imag[k]);
                    }
                    else // Magnitude: matches matcha audio.py sqrt(spec.pow(2).sum(-1) + 1e-9)
                    {
                        for (int k = 0; k < nFreqs; k++)
                        {
                            float mag = MathF.Sqrt(real[k] * real[k] + imag[k] * imag[k] + 1e-9f);
                            sum += fb[m, k] * mag;
                        }
                    }

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

        // ── Filterbank builders ──────────────────────────────────────────

        static float[,] GetSlaneyFilterbank(int nMels, int fftSize, int fMax, ref float[,] cache)
        {
            int nFreqs = fftSize / 2 + 1;
            if (cache != null && cache.GetLength(0) == nMels && cache.GetLength(1) == nFreqs)
                return cache;
            cache = BuildSlaneyFilterbank(nMels, fftSize, fMax);
            return cache;
        }

        static float[,] GetHTKFilterbank(int nMels, int fftSize, int fMax, ref float[,] cache)
        {
            int nFreqs = fftSize / 2 + 1;
            if (cache != null && cache.GetLength(0) == nMels && cache.GetLength(1) == nFreqs)
                return cache;
            cache = BuildHTKFilterbank(nMels, fftSize, fMax);
            return cache;
        }

        // Slaney-normalized mel filterbank matching librosa.filters.mel(norm=1).
        // enorm[m] = 2.0 / (hz[m+2] - hz[m])  (area normalization in linear Hz).
        static float[,] BuildSlaneyFilterbank(int nMels, int fftSize, int fMax)
        {
            int sr     = fMax * 2;
            int nFreqs = fftSize / 2 + 1;

            Func<float, float> hz2mel = hz => 2595f * MathF.Log10(1f + hz / 700f);
            Func<float, float> mel2hz = mel => 700f * (MathF.Pow(10f, mel / 2595f) - 1f);

            float melMin = hz2mel(0f);
            float melMax = hz2mel(fMax);

            // nMels+2 equally spaced mel-scale points
            float[] melPts = new float[nMels + 2];
            for (int i = 0; i < nMels + 2; i++)
                melPts[i] = melMin + (melMax - melMin) * i / (nMels + 1);

            // Convert mel points to Hz
            float[] hzPts = new float[nMels + 2];
            for (int i = 0; i < nMels + 2; i++)
                hzPts[i] = mel2hz(melPts[i]);

            // FFT bin center frequencies
            float[] fftFreqsHz = new float[nFreqs];
            for (int k = 0; k < nFreqs; k++)
                fftFreqsHz[k] = (float)k * sr / fftSize;

            float[,] fb = new float[nMels, nFreqs];

            for (int m = 0; m < nMels; m++)
            {
                float lower  = hzPts[m];
                float center = hzPts[m + 1];
                float upper  = hzPts[m + 2];

                for (int k = 0; k < nFreqs; k++)
                {
                    float f = fftFreqsHz[k];
                    float w = 0f;
                    if (f >= lower && f <= center && center > lower)
                        w = (f - lower) / (center - lower);
                    else if (f > center && f <= upper && upper > center)
                        w = (upper - f) / (upper - center);
                    fb[m, k] = w;
                }

                // Slaney normalization: 2 / (upper_hz - lower_hz)
                float enorm = 2.0f / (upper - lower);
                for (int k = 0; k < nFreqs; k++)
                    fb[m, k] *= enorm;
            }

            return fb;
        }

        // Unnormalized HTK-style triangular filterbank (for feature mel / campplus).
        static float[,] BuildHTKFilterbank(int nMels, int fftSize, int fMax)
        {
            int sr     = fMax * 2;
            int nFreqs = fftSize / 2 + 1;

            Func<float, float> hz2mel = hz => 2595f * MathF.Log10(1f + hz / 700f);
            Func<float, float> mel2hz = mel => 700f * (MathF.Pow(10f, mel / 2595f) - 1f);

            float melMin = hz2mel(0f);
            float melMax = hz2mel(fMax);

            float[] melPts = new float[nMels + 2];
            for (int i = 0; i < nMels + 2; i++)
                melPts[i] = melMin + (melMax - melMin) * i / (nMels + 1);

            float[] binPts = new float[nMels + 2];
            for (int i = 0; i < nMels + 2; i++)
                binPts[i] = (float)Math.Floor(mel2hz(melPts[i]) / sr * fftSize + 0.5f);

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

        // ── Cooley-Tukey radix-2 FFT (in-place, n must be power-of-2) ────

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
