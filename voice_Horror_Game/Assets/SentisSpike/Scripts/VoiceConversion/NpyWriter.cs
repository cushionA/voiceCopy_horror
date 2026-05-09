// NpyWriter.cs — Numpy .npy file writer (float32 little-endian only)
// voice_horror Phase 3.5 (2026-05-08)
//
// Format spec: https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html
//   Magic: \x93NUMPY
//   Version: 1.0
//   Header dict (ASCII), padded with spaces to 64-byte alignment, trailing \n
//   Data: row-major float32 little-endian
//
// Python load:
//   import numpy as np
//   mel = np.load("mu.npy")  # shape (80, 100), dtype float32

using System.IO;
using System.Text;

namespace VoiceHorror.VC
{
    public static class NpyWriter
    {
        // 1D float[] → .npy (shape = (length,))
        public static void Save(string path, float[] data)
        {
            Save(path, data, new[] { data.Length });
        }

        // 2D float[,] → .npy (shape = (rows, cols), C-order)
        public static void Save(string path, float[,] data)
        {
            int rows = data.GetLength(0);
            int cols = data.GetLength(1);
            float[] flat = new float[rows * cols];
            for (int r = 0; r < rows; r++)
                for (int c = 0; c < cols; c++)
                    flat[r * cols + c] = data[r, c];
            Save(path, flat, new[] { rows, cols });
        }

        // Generic flat float[] with explicit shape
        public static void Save(string path, float[] flat, int[] shape)
        {
            string dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            string shapeStr;
            if (shape.Length == 1)
                shapeStr = $"({shape[0]},)";
            else
                shapeStr = "(" + string.Join(", ", shape) + ")";

            string headerDict = $"{{'descr': '<f4', 'fortran_order': False, 'shape': {shapeStr}, }}";

            // Magic(6) + ver(2) + headerLen(2) = 10 bytes prefix
            // Total preamble must be a multiple of 64 (NPY format requirement).
            int prefixLen   = 10;
            int currentLen  = prefixLen + headerDict.Length + 1; // +1 for trailing \n
            int padding     = (64 - currentLen % 64) % 64;
            headerDict      = headerDict + new string(' ', padding) + "\n";

            using var fs = File.Create(path);
            using var bw = new BinaryWriter(fs);

            // Magic
            bw.Write((byte)0x93);
            bw.Write(Encoding.ASCII.GetBytes("NUMPY"));
            // Version 1.0
            bw.Write((byte)1);
            bw.Write((byte)0);
            // Header length (uint16 LE)
            bw.Write((ushort)headerDict.Length);
            // Header dict (ASCII)
            bw.Write(Encoding.ASCII.GetBytes(headerDict));

            // Data (float32 LE — BinaryWriter is LE on all .NET platforms)
            for (int i = 0; i < flat.Length; i++)
                bw.Write(flat[i]);
        }
    }
}
