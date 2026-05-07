#!/usr/bin/env python3
"""
extract_spk_projection.py — CosyVoice3 speaker projection weight extractor
voice_horror Phase 3 (2026-05-07)

Extracts spk_embed_affine_layer (Linear 192→80) from CosyVoice3-0.5B-RL
and saves as JSON for use by SpkEmbedProjection.cs in Unity.

Usage:
    cd voiceCoppy_test
    python extract_spk_projection.py [--model-dir <path>] [--out <output.json>]

Output JSON format:
    {
        "weight": [float...],   # flat [80 * 192] row-major (weight[out, in])
        "bias":   [float...]    # [80]
    }

Place output in:
    voice_Horror_Game/Assets/StreamingAssets/spk_projection.json
"""

import argparse
import json
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Extract CosyVoice3 spk_embed_affine_layer weights")
    parser.add_argument("--model-dir", default="CosyVoice3-0.5B-RL",
                        help="Path to CosyVoice3 model directory")
    parser.add_argument("--out", default="spk_projection.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    # Add CosyVoice3 to path if running from voiceCoppy_test/
    cosyvoice_root = Path(__file__).parent / "CosyVoice3"
    if cosyvoice_root.exists():
        sys.path.insert(0, str(cosyvoice_root))

    try:
        import torch
    except ImportError:
        print("[ERROR] torch not installed. Run in the CosyVoice3 conda env.")
        sys.exit(1)

    try:
        from cosyvoice.cli.cosyvoice import CosyVoice3
        print(f"[INFO] Loading CosyVoice3 from {args.model_dir} ...")
        cosyvoice = CosyVoice3(
            args.model_dir,
            load_jit=False,
            load_trt=False,
            fp16=False,
        )
        model = cosyvoice.model
    except ImportError as e:
        print(f"[ERROR] Cannot import CosyVoice3: {e}")
        print("        Make sure you're in the CosyVoice3 conda environment.")
        sys.exit(1)

    # Locate spk_embed_affine_layer in the flow model
    flow = model.flow  # CausalConditionalCFM or similar

    affine = None
    # Try common attribute paths
    for attr_path in [
        "spk_embed_affine_layer",
        "decoder.spk_embed_affine_layer",
        "decoder.estimator.spk_embed_affine_layer",
    ]:
        obj = flow
        try:
            for part in attr_path.split("."):
                obj = getattr(obj, part)
            if hasattr(obj, "weight"):
                affine = obj
                print(f"[INFO] Found affine layer at flow.{attr_path}")
                break
        except AttributeError:
            continue

    if affine is None:
        print("[ERROR] spk_embed_affine_layer not found. Dumping module structure:")
        for name, module in flow.named_modules():
            if "affine" in name.lower() or "spk" in name.lower():
                print(f"  {name}: {type(module)}")
        print("\nSet attr_path manually in this script and re-run.")
        sys.exit(1)

    weight = affine.weight.data.detach().float().cpu().numpy()  # [80, 192]
    bias   = affine.bias.data.detach().float().cpu().numpy()    # [80]

    print(f"[INFO] weight shape: {weight.shape}, bias shape: {bias.shape}")

    out_data = {
        "weight": weight.flatten().tolist(),  # row-major [80*192]
        "bias":   bias.tolist(),
    }

    out_path = Path(args.out)
    with open(out_path, "w") as f:
        json.dump(out_data, f)
    print(f"[OK] Saved to {out_path}")
    print(f"     → Copy to: voice_Horror_Game/Assets/StreamingAssets/spk_projection.json")
    print(f"       (or Resources/spk_projection.json for baked builds)")


if __name__ == "__main__":
    main()
