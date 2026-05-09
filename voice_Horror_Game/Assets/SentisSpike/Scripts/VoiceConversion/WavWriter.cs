// WavWriter.cs — 16-bit PCM mono WAV writer for VC debug output
// voice_horror Phase 3.5 (2026-05-08)

using System.IO;
using System.Text;
using UnityEngine;

namespace VoiceHorror.VC
{
    public static class WavWriter
    {
        /// <summary>16-bit PCM mono WAV を path に書き出す。samples は -1..+1 想定。</summary>
        public static void Save(string path, float[] samples, int sampleRate)
        {
            string dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            int byteCount = samples.Length * 2;
            using var fs = File.Create(path);
            using var bw = new BinaryWriter(fs);

            // RIFF header
            bw.Write(Encoding.ASCII.GetBytes("RIFF"));
            bw.Write(36 + byteCount);
            bw.Write(Encoding.ASCII.GetBytes("WAVE"));

            // fmt chunk
            bw.Write(Encoding.ASCII.GetBytes("fmt "));
            bw.Write(16);                  // PCM chunk size
            bw.Write((short)1);            // PCM
            bw.Write((short)1);            // mono
            bw.Write(sampleRate);
            bw.Write(sampleRate * 2);      // byte rate
            bw.Write((short)2);            // block align
            bw.Write((short)16);           // bits per sample

            // data chunk
            bw.Write(Encoding.ASCII.GetBytes("data"));
            bw.Write(byteCount);
            for (int i = 0; i < samples.Length; i++)
            {
                float c = Mathf.Clamp(samples[i], -1f, 1f);
                bw.Write((short)(c * 32767f));
            }
        }

        /// <summary>AudioClip を WAV 保存。</summary>
        public static void Save(string path, AudioClip clip)
        {
            float[] data = new float[clip.samples * clip.channels];
            clip.GetData(data, 0);
            // mono 化 (stereo の場合は平均)
            if (clip.channels > 1)
            {
                float[] mono = new float[clip.samples];
                for (int i = 0; i < clip.samples; i++)
                {
                    float sum = 0f;
                    for (int c = 0; c < clip.channels; c++) sum += data[i * clip.channels + c];
                    mono[i] = sum / clip.channels;
                }
                data = mono;
            }
            Save(path, data, clip.frequency);
        }
    }
}
