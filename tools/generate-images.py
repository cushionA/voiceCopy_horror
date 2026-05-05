#!/usr/bin/env python3
"""
Kaggle Image Asset Generator (Python API v2.0.0)
feature-dbのpendingアセットからSprite/Texture系を抽出し、
KaggleでSD 1.5バッチ生成→結果取り込みを行う。

Usage:
  python tools/generate-images.py prepare [--asset-ids A001 A002]  # 生成リクエスト作成
  python tools/generate-images.py submit                           # Kaggleノートブック生成+プッシュ
  python tools/generate-images.py fetch                            # 結果取り込み
  python tools/generate-images.py status                           # Kaggle kernel状態確認
  python tools/generate-images.py monitor                          # 完了まで監視
  python tools/generate-images.py run [--asset-ids A001 A002]      # prepare+submit+monitor+fetch 一括
"""
import builtins
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- Windows cp932 encoding fix ---
# Kaggle API v2.0.0 uses open(file, ...) without encoding parameter.
# On Windows this defaults to cp932, which crashes on Unicode characters.
# Patch builtins.open BEFORE importing kaggle to force UTF-8.
_original_open = builtins.open


def _utf8_open(file, mode="r", *args, **kwargs):
    if isinstance(mode, str) and "b" not in mode and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
    return _original_open(file, mode, *args, **kwargs)


if sys.platform == "win32":
    builtins.open = _utf8_open

# --- Auth setup ---
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Kaggle Python API v2.0.0 expects KAGGLE_API_TOKEN for access token auth
# Our .env has KAGGLE_API_TOKEN already (KGAT_ prefix)
# Also support legacy KAGGLE_KEY fallback
if os.getenv("KAGGLE_API_TOKEN"):
    pass  # Already set, access token auth will work
elif os.getenv("KAGGLE_KEY"):
    os.environ["KAGGLE_API_TOKEN"] = os.getenv("KAGGLE_KEY")

from kaggle.api.kaggle_api_extended import KaggleApi

# --- Paths ---
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "asset-gen.json"
REQUEST_PATH = PROJECT_ROOT / "designs" / "asset-gen-request.json"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks" / "asset_gen"
DB_PATH = PROJECT_ROOT / "feature-log.db"
ASSET_SPEC_PATH = PROJECT_ROOT / "designs" / "asset-spec.json"

IMAGE_ASSET_TYPES = {"Sprite", "Texture", "sprite", "texture", "Image", "image"}


def _get_api() -> KaggleApi:
    """認証済みKaggle APIインスタンスを取得"""
    api = KaggleApi()
    api.authenticate()
    return api


def find_existing_assets(unity_project):
    """Unityプロジェクト内の既存画像アセットをスキャンして返す。"""
    image_extensions = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".psd"}
    assets_dir = PROJECT_ROOT / unity_project / "Assets"
    existing = {}  # filename_without_ext -> full_path

    if not assets_dir.exists():
        return existing

    for dirpath, _dirnames, filenames in os.walk(assets_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in image_extensions:
                name_no_ext = os.path.splitext(fname)[0].lower()
                rel = os.path.relpath(os.path.join(dirpath, fname), PROJECT_ROOT / unity_project)
                existing[name_no_ext] = rel.replace("\\", "/")

    return existing


def load_config():
    if not CONFIG_PATH.exists():
        print("Error: config/asset-gen.json not found", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_asset_spec():
    if ASSET_SPEC_PATH.exists():
        with open(ASSET_SPEC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_pending_image_assets(asset_ids=None):
    """feature-dbからpending状態の画像系アセットを取得。"""
    if not DB_PATH.exists():
        print("Error: feature-log.db not found. Run 'python tools/feature-db.py init' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT pa.*, f.name as feature_name
        FROM pending_assets pa
        JOIN features f ON pa.feature_id = f.id
        WHERE pa.status = 'pending'
    """
    params = []

    if asset_ids:
        placeholders = ",".join("?" for _ in asset_ids)
        query += f" AND pa.asset_id IN ({placeholders})"
        params.extend(asset_ids)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    # 画像系のみフィルタ
    image_assets = [dict(r) for r in rows if r["asset_type"] in IMAGE_ASSET_TYPES]
    return image_assets


def check_reusable_assets(assets, unity_project):
    """配置済みアセットの中から再利用可能なものを検出する。"""
    existing = find_existing_assets(unity_project)
    reusable = []
    need_generation = []

    placed_by_desc = {}
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT asset_id, description, expected_path FROM pending_assets
            WHERE status = 'placed' AND expected_path IS NOT NULL
        """).fetchall()
        conn.close()
        for row in rows:
            desc_key = row["description"].strip().lower()
            placed_by_desc[desc_key] = {
                "asset_id": row["asset_id"],
                "expected_path": row["expected_path"],
            }

    for asset in assets:
        expected = asset["expected_path"] or f"Assets/Sprites/{asset['asset_id']}.png"
        expected_name = os.path.splitext(os.path.basename(expected))[0].lower()

        full_path = PROJECT_ROOT / unity_project / expected
        if full_path.exists():
            reusable.append((asset, expected, "file_exists"))
            continue

        desc_key = asset["description"].strip().lower()
        if desc_key in placed_by_desc:
            placed = placed_by_desc[desc_key]
            placed_full = PROJECT_ROOT / unity_project / placed["expected_path"]
            if placed_full.exists():
                reusable.append((asset, placed["expected_path"], "same_description"))
                continue

        if expected_name in existing:
            reusable.append((asset, existing[expected_name], "name_match"))
            continue

        need_generation.append(asset)

    return reusable, need_generation


def prepare(asset_ids=None):
    """生成リクエストJSONを作成。再利用可能なアセットは除外する。"""
    config = load_config()
    asset_spec = load_asset_spec()
    unity_project = config.get("unity_project", ".")
    assets = get_pending_image_assets(asset_ids)

    if not assets:
        print("No pending image assets found.")
        return

    reusable, need_generation = check_reusable_assets(assets, unity_project)
    reuse_list = []

    if reusable:
        print(f"=== Reusable assets ({len(reusable)}) ===")
        for asset, existing_path, reason in reusable:
            reason_text = {
                "file_exists": "配置先に既存ファイルあり",
                "same_description": "同じ説明のアセットが配置済み",
                "name_match": "同名ファイルが既に存在",
            }.get(reason, reason)
            print(f"  {asset['asset_id']}: {reason_text} -> {existing_path}")
            reuse_list.append({
                "asset_id": asset["asset_id"],
                "reason": reason,
                "existing_path": existing_path,
                "description": asset["description"],
            })

    if not need_generation:
        print("\nAll assets can be reused. No generation needed.")
        if reusable:
            reuse_data = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "reusable": reuse_list,
                "assets": [],
                "total": 0,
            }
            REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(REQUEST_PATH, "w", encoding="utf-8") as f:
                json.dump(reuse_data, f, indent=2, ensure_ascii=False)
        return

    kaggle_config = config.get("image_generation", {}).get("kaggle", {})
    default_size = kaggle_config.get("default_size", [512, 512])
    style_prefix = kaggle_config.get("style_prompt_prefix", "")

    requests = []
    for asset in need_generation:
        width, height = default_size
        prompt = asset["description"]
        if style_prefix:
            prompt = f"{style_prefix}, {prompt}"

        requests.append({
            "asset_id": asset["asset_id"],
            "feature": asset["feature_name"],
            "description": asset["description"],
            "prompt": prompt,
            "width": width,
            "height": height,
            "expected_path": asset["expected_path"] or f"Assets/Sprites/{asset['asset_id']}.png",
            "format": asset.get("format") or "png",
            "transparent_bg": True,
        })

    request_data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": kaggle_config.get("model", "sd-1.5"),
        "lora": kaggle_config.get("lora"),
        "reusable": reuse_list,
        "total": len(requests),
        "assets": requests,
    }

    REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REQUEST_PATH, "w", encoding="utf-8") as f:
        json.dump(request_data, f, indent=2, ensure_ascii=False)

    print(f"\nPrepared {len(requests)} image generation requests (skipped {len(reusable)} reusable)")
    print(f"Saved to: {REQUEST_PATH}")
    for req in requests:
        print(f"  {req['asset_id']}: {req['description'][:50]}")


def generate_notebook():
    """Kaggle用ノートブック(train.ipynb)を生成。"""
    if not REQUEST_PATH.exists():
        print("Error: No request file. Run 'prepare' first.", file=sys.stderr)
        sys.exit(1)

    with open(REQUEST_PATH, "r", encoding="utf-8") as f:
        request_data = json.load(f)

    config = load_config()
    kaggle_config = config.get("image_generation", {}).get("kaggle", {})

    cells = []

    # Cell 1: セットアップ (FLUX.2 [klein] 4B — latest, Apache 2.0)
    cells.append({
        "cell_type": "code",
        "metadata": {},
        "source": [
            "!pip install -q 'Pillow>=10.0,<11.0' git+https://github.com/huggingface/diffusers.git transformers accelerate safetensors sentencepiece protobuf\n",
        ],
        "outputs": [],
        "execution_count": None,
    })

    # Cell 2: モデルロード (FLUX.2 [klein] 4B — 13GB VRAM, no auth needed)
    cells.append({
        "cell_type": "code",
        "metadata": {},
        "source": [
            "import torch\n",
            "from diffusers import Flux2KleinPipeline\n",
            "from PIL import Image\n",
            "import json\n",
            "import os\n",
            "import gc\n",
            "\n",
            'pipe = Flux2KleinPipeline.from_pretrained(\n',
            '    "black-forest-labs/FLUX.2-klein-4B",\n',
            '    torch_dtype=torch.bfloat16,\n',
            ')\n',
            'pipe.enable_model_cpu_offload()\n',
        ],
        "outputs": [],
        "execution_count": None,
    })

    # Cell 3: リクエストデータ埋め込み + 生成ループ
    request_json = json.dumps(request_data, ensure_ascii=False)
    cells.append({
        "cell_type": "code",
        "metadata": {},
        "source": [
            f"request_data = json.loads('''{request_json}''')\n",
            "\n",
            "os.makedirs('/kaggle/working/output', exist_ok=True)\n",
            "\n",
            "for asset in request_data['assets']:\n",
            "    print(f\"Generating: {asset['asset_id']} - {asset['description'][:40]}\")\n",
            "    image = pipe(\n",
            "        prompt=asset['prompt'],\n",
            "        width=asset['width'],\n",
            "        height=asset['height'],\n",
            "        num_inference_steps=4,\n",
            "        guidance_scale=1.0,\n",
            "    ).images[0]\n",
            "\n",
            "    target_w, target_h = asset['width'], asset['height']\n",
            "    if image.size != (target_w, target_h):\n",
            "        image = image.resize((target_w, target_h), Image.LANCZOS)\n",
            "\n",
            "    out_path = f\"/kaggle/working/output/{asset['asset_id']}.png\"\n",
            "    image.save(out_path)\n",
            "    print(f\"  Saved: {out_path}\")\n",
            "\n",
            "    # Free VRAM between generations\n",
            "    del image\n",
            "    gc.collect()\n",
            "    torch.cuda.empty_cache()\n",
            "\n",
            "print('Done!')\n",
        ],
        "outputs": [],
        "execution_count": None,
    })

    # Cell 4: ZIP出力
    cells.append({
        "cell_type": "code",
        "metadata": {},
        "source": [
            "import zipfile\n",
            "\n",
            "with zipfile.ZipFile('/kaggle/working/generated_assets.zip', 'w') as zf:\n",
            "    for fname in os.listdir('/kaggle/working/output'):\n",
            "        zf.write(f'/kaggle/working/output/{fname}', fname)\n",
            "\n",
            "print('Zipped to /kaggle/working/generated_assets.zip')\n",
        ],
        "outputs": [],
        "execution_count": None,
    })

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 4,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0"
            }
        },
        "cells": cells,
    }

    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    notebook_path = NOTEBOOK_DIR / "train.ipynb"
    with open(notebook_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    # kernel-metadata.json
    kernel_meta = {
        "id": kaggle_config.get("kernel_id", "your-username/game-asset-generator"),
        "title": "Game Asset Generator",
        "code_file": "train.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "accelerator": "nvidiaTeslaT4x2",
        "enable_internet": True,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
    }
    dataset_id = kaggle_config.get("dataset_id")
    if dataset_id:
        kernel_meta["dataset_sources"].append(dataset_id)

    with open(NOTEBOOK_DIR / "kernel-metadata.json", "w", encoding="utf-8") as f:
        json.dump(kernel_meta, f, indent=2)

    print(f"Notebook generated: {notebook_path}")
    return notebook_path


def submit():
    """ノートブックを生成してKaggle Python APIでプッシュ。"""
    generate_notebook()

    print("Pushing to Kaggle via Python API...")
    try:
        api = _get_api()
        response = api.kernels_push(str(NOTEBOOK_DIR))

        kernel_ref = getattr(response, "ref", None)
        url = getattr(response, "url", None) or f"https://www.kaggle.com/code/{kernel_ref}"

        print(f"Submitted successfully!")
        print(f"  Kernel: {kernel_ref}")
        print(f"  URL: {url}")
        return kernel_ref
    except Exception as e:
        error_msg = str(e)
        if "409" in error_msg or "Conflict" in error_msg:
            print(f"Error: Kernel already has a running/queued version. "
                  f"Wait for it to complete first.", file=sys.stderr)
        else:
            print(f"Error pushing to Kaggle: {e}", file=sys.stderr)
        sys.exit(1)


def status() -> Optional[str]:
    """Kaggle kernelの実行状態を確認（Python API）。"""
    config = load_config()
    kaggle_config = config.get("image_generation", {}).get("kaggle", {})
    kernel_id = kaggle_config.get("kernel_id")

    if not kernel_id:
        print("Error: kernel_id not set in config/asset-gen.json", file=sys.stderr)
        sys.exit(1)

    try:
        api = _get_api()
        response = api.kernels_status(kernel_id)

        status_val = response.status
        failure_msg = response.failure_message or None

        # Convert enum to string
        status_str = str(status_val).split(".")[-1].lower() if status_val else "unknown"

        print(f"Kernel {kernel_id}: {status_str}")
        if failure_msg:
            print(f"  Failure: {failure_msg[:200]}")

        return status_str
    except Exception as e:
        print(f"Error checking status: {e}", file=sys.stderr)
        return None


def monitor(check_interval: int = 60, max_hours: float = 2.0, initial_wait: int = 90) -> bool:
    """Kaggle kernelの完了を監視（Python API）。"""
    config = load_config()
    kaggle_config = config.get("image_generation", {}).get("kaggle", {})
    kernel_id = kaggle_config.get("kernel_id")

    if not kernel_id:
        print("Error: kernel_id not set in config/asset-gen.json", file=sys.stderr)
        return False

    print(f"Monitoring: {kernel_id}")
    print(f"Interval: {check_interval}s, Max: {max_hours}h")

    if initial_wait > 0:
        print(f"Waiting {initial_wait}s for Kaggle to queue...")
        time.sleep(initial_wait)

    start = datetime.now()
    max_seconds = max_hours * 3600
    check_count = 0

    while True:
        check_count += 1
        elapsed = (datetime.now() - start).total_seconds()
        print(f"[{datetime.now():%H:%M:%S}] Check #{check_count} ({elapsed/60:.0f}m)")

        try:
            api = _get_api()
            response = api.kernels_status(kernel_id)
            status_val = response.status
            status_str = str(status_val).split(".")[-1].lower() if status_val else "unknown"
            failure_msg = response.failure_message or ""
        except Exception as e:
            print(f"  [WARN] Status check failed: {e}")
            time.sleep(check_interval)
            continue

        if status_str == "complete":
            print(f"  [OK] Training COMPLETE!")
            return True
        elif status_str == "error":
            print(f"  [FAIL] Training ERROR!")
            if failure_msg:
                print(f"  {failure_msg[:300]}")
            return False
        elif status_str in ("cancelled", "cancel_acknowledged", "cancel_requested"):
            print(f"  [FAIL] Training CANCELLED")
            return False
        else:
            print(f"  ... {status_str}")

        if elapsed > max_seconds:
            print(f"\n  [TIMEOUT] {max_hours}h exceeded")
            return False

        time.sleep(check_interval)


def fetch():
    """Kaggle出力をPython APIでダウンロードしてAssets/に配置。"""
    config = load_config()
    kaggle_config = config.get("image_generation", {}).get("kaggle", {})
    kernel_id = kaggle_config.get("kernel_id")
    unity_project = config.get("unity_project", ".")

    if not kernel_id:
        print("Error: kernel_id not set in config/asset-gen.json", file=sys.stderr)
        sys.exit(1)

    output_dir = NOTEBOOK_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching output from {kernel_id} via Python API...")
    try:
        api = _get_api()
        files, token = api.kernels_output(kernel_id, str(output_dir), quiet=True)
        print(f"Downloaded {len(files)} files to {output_dir}")
    except Exception as e:
        print(f"Error fetching output: {e}", file=sys.stderr)
        sys.exit(1)

    # ZIP展開（generated_assets.zipがある場合）
    zip_path = output_dir / "generated_assets.zip"
    if zip_path.exists():
        import zipfile
        extract_dir = output_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        print(f"Extracted ZIP to {extract_dir}")

    # リクエストファイルを読んで配置先を決定
    if not REQUEST_PATH.exists():
        print("Error: No request file found. Cannot determine asset placement.", file=sys.stderr)
        sys.exit(1)

    with open(REQUEST_PATH, "r", encoding="utf-8") as f:
        request_data = json.load(f)

    placed = 0
    for asset in request_data["assets"]:
        asset_id = asset["asset_id"]
        # 複数の候補パスを順に探す
        candidates = [
            output_dir / f"{asset_id}.png",
            output_dir / "output" / f"{asset_id}.png",
            output_dir / "extracted" / f"{asset_id}.png",
        ]
        src = None
        for c in candidates:
            if c.exists():
                src = c
                break

        if src is None:
            print(f"  Warning: {asset_id}.png not found in output")
            continue

        dest = PROJECT_ROOT / unity_project / asset["expected_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  Placed: {asset_id} -> {asset['expected_path']}")

        # feature-dbでbind
        import subprocess
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "feature-db.py"), "bind", asset_id],
            capture_output=True, text=True
        )
        placed += 1

    print(f"\nPlaced {placed}/{len(request_data['assets'])} assets")


def run(asset_ids=None):
    """prepare → submit → monitor → fetch を一括実行。"""
    print("=" * 60)
    print("=== Phase 1: Prepare ===")
    print("=" * 60)
    prepare(asset_ids)

    if not REQUEST_PATH.exists():
        print("No request file generated. Nothing to submit.")
        return

    with open(REQUEST_PATH, "r", encoding="utf-8") as f:
        request_data = json.load(f)

    if request_data.get("total", 0) == 0:
        print("No assets need generation. Done.")
        return

    print("\n" + "=" * 60)
    print("=== Phase 2: Submit ===")
    print("=" * 60)
    submit()

    print("\n" + "=" * 60)
    print("=== Phase 3: Monitor ===")
    print("=" * 60)
    ok = monitor()

    if not ok:
        print("\nTraining failed or timed out. Use 'status' to check.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("=== Phase 4: Fetch ===")
    print("=" * 60)
    fetch()

    print("\n" + "=" * 60)
    print("=== Complete! ===")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "prepare":
        asset_ids = None
        if "--asset-ids" in sys.argv:
            idx = sys.argv.index("--asset-ids")
            asset_ids = sys.argv[idx + 1:]
        prepare(asset_ids)
    elif cmd == "submit":
        submit()
    elif cmd == "fetch":
        fetch()
    elif cmd == "status":
        status()
    elif cmd == "monitor":
        monitor()
    elif cmd == "run":
        asset_ids = None
        if "--asset-ids" in sys.argv:
            idx = sys.argv.index("--asset-ids")
            asset_ids = sys.argv[idx + 1:]
        run(asset_ids)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
