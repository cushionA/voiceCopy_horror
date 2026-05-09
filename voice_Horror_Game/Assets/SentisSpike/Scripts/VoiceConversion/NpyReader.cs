// NpyReader.cs — Numpy .npy file reader (float32 little-endian only)
// voice_horror Phase 7 (2026-05-09)
//
// NpyWriter と対称、MatchingSetPool 永続化で使う。
// Format spec: https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html

using System;
using System.IO;
using System.Text;

namespace VoiceHorror.VC
{
    public static class NpyReader
    {
        /// <summary>
        /// .npy ファイルを読み、flat float[] と shape を返す。
        /// </summary>
        public static (float[] data, int[] shape) Load(string path)
        {
            using var fs = File.OpenRead(path);
            using var br = new BinaryReader(fs);

            // Magic check
            byte magic = br.ReadByte();
            if (magic != 0x93)
                throw new InvalidDataException($"Not a npy file: {path} (magic byte mismatch)");
            string numpyTag = Encoding.ASCII.GetString(br.ReadBytes(5));
            if (numpyTag != "NUMPY")
                throw new InvalidDataException($"Not a npy file: {path} (tag={numpyTag})");

            // Version
            byte verMajor = br.ReadByte();
            byte verMinor = br.ReadByte();
            int headerLen;
            if (verMajor == 1)
                headerLen = br.ReadUInt16(); // uint16 LE
            else if (verMajor == 2)
                headerLen = (int)br.ReadUInt32();
            else
                throw new InvalidDataException($"Unsupported npy version: {verMajor}.{verMinor}");

            string headerDict = Encoding.ASCII.GetString(br.ReadBytes(headerLen));

            // Parse header dict (very simple, supports float32 / fortran_order:False / shape only)
            if (!headerDict.Contains("'<f4'") && !headerDict.Contains("'|f4'"))
                throw new InvalidDataException(
                    $"Only float32 little-endian supported, header={headerDict.Trim()}");
            if (headerDict.Contains("'fortran_order': True"))
                throw new InvalidDataException("Fortran order not supported");

            int[] shape = ParseShape(headerDict);

            int total = 1;
            for (int i = 0; i < shape.Length; i++) total *= shape[i];

            float[] data = new float[total];
            for (int i = 0; i < total; i++)
                data[i] = br.ReadSingle(); // BinaryReader is LE on all .NET platforms

            return (data, shape);
        }

        static int[] ParseShape(string headerDict)
        {
            // Find "'shape': (" and extract until ")"
            int idx = headerDict.IndexOf("'shape':");
            if (idx < 0) throw new InvalidDataException("shape key not found in header");
            int open = headerDict.IndexOf('(', idx);
            int close = headerDict.IndexOf(')', open);
            string inside = headerDict.Substring(open + 1, close - open - 1);

            // Split by comma, strip whitespace, parse int. Trailing comma OK.
            string[] tokens = inside.Split(',');
            var dims = new System.Collections.Generic.List<int>();
            foreach (var t in tokens)
            {
                string s = t.Trim();
                if (string.IsNullOrEmpty(s)) continue;
                dims.Add(int.Parse(s));
            }
            return dims.ToArray();
        }
    }
}
