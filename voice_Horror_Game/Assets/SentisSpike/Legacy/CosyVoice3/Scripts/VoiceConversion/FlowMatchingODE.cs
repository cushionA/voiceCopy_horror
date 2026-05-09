// FlowMatchingODE.cs — Euler ODE integration for CosyVoice3 flow matching
// voice_horror Phase 3 (2026-05-07)
//
// CosyVoice3 uses Conditional Flow Matching (CFM / Rectified Flow):
//   t=0 → noise (Gaussian), t=1 → data (mel)
//   Euler: x(t+dt) = x(t) + dt * v_theta(x(t), t)
//   We integrate from t=0 to t=1 in n_steps.
//
// DiT input/output (static T=100):
//   x     [1, 80, 100]  current noisy mel
//   mask  [1,  1, 100]  validity mask (1=valid frame)
//   mu    [1, 80, 100]  conditioning mean (source mel)
//   t     [1]           current timestep scalar
//   spks  [1, 80]       speaker embedding (projected from campplus 192→80)
//   cond  [1, 80, 100]  extra conditioning (=mu in VC mode)
//   out   velocity [1, 80, 100]

using System;
using Unity.InferenceEngine;
using UnityEngine;

namespace VoiceHorror.VC
{
    public static class FlowMatchingODE
    {
        const int k_Mel = 80;
        const int k_T   = 100;  // DiT static sequence length

        // Integrate from pure noise to mel over n_steps.
        // Returns flat float[80*T] (row-major [mel, T]) of the generated mel.
        //
        // Parameters:
        //   ditWorker  — pre-created Worker for flow.decoder.estimator ONNX
        //   mu80xT     — conditioning mel [80, T] (source acoustic mel, padded to T=100)
        //   spks80     — projected speaker embedding [80]
        //   melLength  — actual mel frames (< T for padded audio)
        //   nSteps     — ODE steps (default 10; reduce for speed, increase for quality)
        //   seed       — random seed for reproducibility (-1 = random)
        public static float[] Run(
            Worker ditWorker,
            float[,] mu80xT,
            float[]  spks80,
            int      melLength,
            int      nSteps = 10,
            int      seed   = -1)
        {
            if (mu80xT.GetLength(0) != k_Mel || mu80xT.GetLength(1) != k_T)
                throw new ArgumentException($"mu80xT must be [{k_Mel},{k_T}]");
            if (spks80.Length != k_Mel)
                throw new ArgumentException($"spks80 must have {k_Mel} elements");

            // Build mask: 1 for valid frames, 0 for padding
            float[] maskFlat = new float[k_T];
            int clampedLen = Math.Min(melLength, k_T);
            for (int i = 0; i < clampedLen; i++) maskFlat[i] = 1f;

            // Build mu flat [80*T] from mu80xT [80,T]
            float[] muFlat = Flatten2D(mu80xT, k_Mel, k_T);

            // Initialize x from Gaussian noise
            float[] x = SampleGaussian(k_Mel * k_T, seed);

            float dt = 1f / nSteps;

            for (int step = 0; step < nSteps; step++)
            {
                float tVal = step * dt; // goes from 0 to 1-dt

                // Schedule DiT forward pass
                using var xTensor    = new Tensor<float>(new TensorShape(1, k_Mel, k_T), x);
                using var maskTensor = new Tensor<float>(new TensorShape(1, 1, k_T), maskFlat);
                using var muTensor   = new Tensor<float>(new TensorShape(1, k_Mel, k_T), muFlat);
                using var tTensor    = new Tensor<float>(new TensorShape(1), new float[] { tVal });
                using var spksTensor = new Tensor<float>(new TensorShape(1, k_Mel), spks80);
                using var condTensor = new Tensor<float>(new TensorShape(1, k_Mel, k_T), muFlat); // cond = mu

                ditWorker.SetInput("x",    xTensor);
                ditWorker.SetInput("mask", maskTensor);
                ditWorker.SetInput("mu",   muTensor);
                ditWorker.SetInput("t",    tTensor);
                ditWorker.SetInput("spks", spksTensor);
                ditWorker.SetInput("cond", condTensor);
                ditWorker.Schedule();

                // Readback velocity and update x
                using var velOut = (ditWorker.PeekOutput("velocity") as Tensor<float>)
                    .ReadbackAndClone();
                float[] vel = velOut.DownloadToArray();

                // Euler step: x += dt * velocity
                for (int i = 0; i < x.Length; i++)
                    x[i] += dt * vel[i];
            }

            return x; // [80*T] row-major, valid for first melLength frames
        }

        // Run returns mel as flat float[]. Reshape to [80, T] for downstream use.
        public static float[,] Unflatten(float[] flat, int nMel, int nT)
        {
            float[,] result = new float[nMel, nT];
            for (int m = 0; m < nMel; m++)
                for (int t = 0; t < nT; t++)
                    result[m, t] = flat[m * nT + t];
            return result;
        }

        // ── Helpers ───────────────────────────────────────────────────────

        static float[] Flatten2D(float[,] arr, int rows, int cols)
        {
            float[] flat = new float[rows * cols];
            for (int r = 0; r < rows; r++)
                for (int c = 0; c < cols; c++)
                    flat[r * cols + c] = arr[r, c];
            return flat;
        }

        static float[] SampleGaussian(int n, int seed)
        {
            var rng = (seed < 0) ? new System.Random() : new System.Random(seed);
            float[] data = new float[n];
            // Box-Muller transform
            for (int i = 0; i < n - 1; i += 2)
            {
                double u1 = 1.0 - rng.NextDouble();
                double u2 = 1.0 - rng.NextDouble();
                double mag = Math.Sqrt(-2.0 * Math.Log(u1));
                data[i]     = (float)(mag * Math.Cos(2 * Math.PI * u2));
                data[i + 1] = (float)(mag * Math.Sin(2 * Math.PI * u2));
            }
            if (n % 2 == 1)
            {
                double u1 = 1.0 - rng.NextDouble();
                double u2 = 1.0 - rng.NextDouble();
                data[n - 1] = (float)(Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2 * Math.PI * u2));
            }
            return data;
        }
    }
}
