#!/usr/bin/env python3
"""
fal.ai + JANKU v6.9 タイルマップ生成プロンプト体系テスト

Usage:
  python tools/test-tile-prompts.py [test_group]

  test_group: keyword_compare | grid_vs_single | tile_types | transparency | all
  Default: all
"""
import fal_client
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# fal.ai auth
os.environ["FAL_KEY"] = os.getenv("FAL_KEY", "")

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "tile_prompt_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- JANKU v6.9 model config ---
MODEL_NAME = "LillyCherry/JANKUTrainedNoobaiRouwei_v69"

# NoobAI vpred base settings
BASE_PARAMS = {
    "model_name": MODEL_NAME,
    "num_inference_steps": 28,
    "guidance_scale": 5.0,
    "scheduler": "Euler",
    "clip_skip": 2,
    "enable_safety_checker": False,
    "image_format": "png",
    "num_images": 1,
}

# Map素材用ネガティブ
NEG_TILES = "person, character, human, 1girl, 1boy, figure, face, text, watermark, signature, logo, UI, HUD, frame, border, worst quality, low quality, lowres, jpeg artifacts, 3d render, realistic photo, nsfw"
NEG_OBJECTS = "person, character, human, 1girl, 1boy, figure, face, text, watermark, signature, logo, background, scenery, multiple objects, group, worst quality, low quality, lowres, jpeg artifacts, 3d render, realistic photo, nsfw"

SEED = 256  # 固定seed for comparison


def generate(name: str, prompt: str, negative: str, width: int = 512, height: int = 512, seed: int = SEED):
    """1枚生成してファイル保存"""
    print(f"  [{name}] generating {width}x{height}...")

    params = {
        **BASE_PARAMS,
        "prompt": prompt,
        "negative_prompt": negative,
        "image_size": {"width": width, "height": height},
        "seed": seed,
    }

    try:
        result = fal_client.subscribe("fal-ai/lora", arguments=params)
        url = result["images"][0]["url"]
        actual_seed = result.get("seed", seed)

        # Download image
        out_path = OUTPUT_DIR / f"{name}.png"
        urllib.request.urlretrieve(url, str(out_path))
        print(f"    -> saved: {out_path.name} (seed={actual_seed})")

        return {"name": name, "prompt": prompt, "url": url, "seed": actual_seed, "path": str(out_path)}
    except Exception as e:
        print(f"    -> ERROR: {e}")
        return {"name": name, "prompt": prompt, "error": str(e)}


def test_keyword_compare():
    """テスト1: タイル系キーワードの効果比較
    同じ「石の地面」で、キーワードだけ変えて効果を比較"""
    print("\n=== TEST 1: Keyword Compare (stone floor) ===")

    base_desc = "stone floor texture, cracked rock surface, dark dungeon"

    tests = {
        # キーワードなし (baseline)
        "kw_01_baseline": f"best quality, newest, no humans, {base_desc}, top down view, square format",

        # seamless pattern
        "kw_02_seamless": f"best quality, newest, no humans, seamless pattern, {base_desc}, top down view, square format",

        # tileable
        "kw_03_tileable": f"best quality, newest, no humans, tileable, {base_desc}, top down view, square format",

        # seamless + tileable
        "kw_04_seamless_tileable": f"best quality, newest, no humans, seamless pattern, tileable, {base_desc}, top down view, square format",

        # RPG Maker tileset
        "kw_05_rpgmaker": f"best quality, newest, no humans, RPG Maker tileset, {base_desc}, top down view, square format",

        # game tile sprite
        "kw_06_game_tile": f"best quality, newest, no humans, game tile, pixel art, {base_desc}, top down view, square format",

        # game asset + texture
        "kw_07_game_asset": f"best quality, newest, no humans, game asset, texture, {base_desc}, top down view, square format",

        # square tile (explicit)
        "kw_08_square_tile": f"best quality, newest, no humans, seamless pattern, tileable, square tile, {base_desc}, top down view",

        # sprite sheet keyword
        "kw_09_sprite_sheet": f"best quality, newest, no humans, sprite sheet, game tileset, {base_desc}, top down view, grid layout",

        # 2D game + flat color
        "kw_10_2d_flat": f"best quality, newest, no humans, 2d game, flat color, seamless pattern, {base_desc}, top down view",
    }

    results = []
    for name, prompt in tests.items():
        r = generate(name, prompt, NEG_TILES, 512, 512)
        results.append(r)
        time.sleep(1)

    return results


def test_grid_vs_single():
    """テスト2: グリッドレイアウト（複数タイル1枚）vs 個別タイル"""
    print("\n=== TEST 2: Grid Layout vs Single Tile ===")

    results = []

    # 2A: グリッド指示いろいろ
    grid_tests = {
        "grid_01_4x4": "best quality, newest, no humans, game tileset sheet, 4x4 grid layout, dungeon tiles, stone wall, stone floor, ceiling, door, top down view, organized grid, pixel art, dark fantasy",
        "grid_02_rpgmaker_sheet": "best quality, newest, no humans, RPG Maker tileset, multiple tiles arranged in grid, dungeon terrain set, stone textures, dark cave, organized rows and columns, sprite sheet",
        "grid_03_tilesheet": "best quality, newest, no humans, tile sheet, game asset, (4 rows:1.2) (4 columns:1.2), dungeon floor variations, stone brick wall variations, cave ceiling, organized grid layout",
        "grid_04_item_sheet": "best quality, newest, no humans, item sheet, game sprite sheet, multiple game objects on white background, torch, barrel, chains, skull, treasure chest, organized grid, pixel art, dark fantasy",
    }

    for name, prompt in grid_tests.items():
        r = generate(name, prompt, NEG_TILES, 1024, 1024)
        results.append(r)
        time.sleep(1)

    # 2B: 個別タイル（高品質）
    single_tests = {
        "single_01_wall": "best quality, newest, no humans, seamless pattern, tileable, stone wall texture, rough brick surface, dark dungeon wall, front view, square tile",
        "single_02_floor": "best quality, newest, no humans, seamless pattern, tileable, stone floor texture, cobblestone, dark dungeon floor, top down view, square tile",
        "single_03_ceiling": "best quality, newest, no humans, seamless pattern, tileable, stone ceiling texture, rough cave ceiling, stalactites, top down view, square tile",
    }

    for name, prompt in single_tests.items():
        r = generate(name, prompt, NEG_TILES, 512, 512)
        results.append(r)
        time.sleep(1)

    return results


def test_tile_types():
    """テスト3: 素材タイプ別の最適プロンプト"""
    print("\n=== TEST 3: Tile Types (Wall/Floor/Ceiling/Platform/Env/BG) ===")

    results = []

    # 3A: 壁タイル
    walls = {
        "type_wall_stone": "best quality, newest, no humans, seamless pattern, tileable, stone wall texture, rough rock surface, dark dungeon, front view, square tile, dark fantasy",
        "type_wall_brick": "best quality, newest, no humans, seamless pattern, tileable, old brick wall texture, crumbling mortar, prison wall, moss, front view, square tile, dark fantasy",
        "type_wall_cave": "best quality, newest, no humans, seamless pattern, tileable, cave wall texture, jagged rock, wet surface, stalactites, dim lighting, front view, square tile",
    }

    # 3B: 地面タイル
    floors = {
        "type_floor_stone": "best quality, newest, no humans, seamless pattern, tileable, stone floor texture, cobblestone, cracked, dark dungeon, top down view, square tile",
        "type_floor_dirt": "best quality, newest, no humans, seamless pattern, tileable, dirt ground texture, cave floor, rocks and gravel, puddles, dark, top down view, square tile",
        "type_floor_prison": "best quality, newest, no humans, seamless pattern, tileable, prison floor texture, rusty iron grate, stone slab, bloodstains, dark, top down view, square tile",
    }

    # 3C: 天井タイル
    ceilings = {
        "type_ceiling_cave": "best quality, newest, no humans, seamless pattern, tileable, cave ceiling texture, stalactites hanging down, rough rock, dark, bottom up view, square tile",
        "type_ceiling_dungeon": "best quality, newest, no humans, seamless pattern, tileable, dungeon ceiling texture, stone arch, old brick, cobwebs, dim torchlight, bottom up view, square tile",
    }

    # 3D: 足場（プラットフォーム）- 横長、透過想定
    platforms = {
        "type_platform_stone": "best quality, newest, no humans, stone platform, rock ledge, side view, game asset, isolated object, simple dark background, dark fantasy, 2d game",
        "type_platform_wood": "best quality, newest, no humans, wooden platform, old plank bridge, rope, side view, game asset, isolated object, simple dark background, dark fantasy, 2d game",
        "type_platform_chain": "best quality, newest, no humans, hanging chain platform, iron grate, suspended by chains, side view, game asset, isolated object, simple dark background, dark fantasy, 2d game",
    }

    # 3E: 環境オブジェクト - 透過前提
    env_objects = {
        "type_obj_torch": "best quality, newest, no humans, wall mounted torch, iron bracket, flickering flame, warm light, game prop, isolated object, simple dark background, dark fantasy",
        "type_obj_barrel": "best quality, newest, no humans, old wooden barrel, rusty iron bands, cracked wood, game prop, isolated object, simple dark background, dark fantasy",
        "type_obj_chains": "best quality, newest, no humans, iron chains and shackles, hanging from above, rusty old metal, game prop, isolated object, simple dark background, dungeon",
        "type_obj_skeleton": "best quality, newest, no humans, skeleton remains in rusted armor, leaning pose, cobwebs, old bones, game prop, isolated object, simple dark background, dark fantasy",
        "type_obj_mushroom": "best quality, newest, no humans, glowing mushrooms cluster, bioluminescent fungi, green blue glow, cave decoration, game prop, isolated object, simple dark background",
    }

    # 3F: 背景レイヤー（横長 パララックス用）
    backgrounds = {
        "type_bg_far": "best quality, newest, no humans, scenery, dark cave far background, distant rock formations, hazy, atmospheric perspective, desaturated, cool tones, wide shot, panoramic, dark fantasy",
        "type_bg_mid": "best quality, newest, no humans, scenery, dark dungeon mid ground, stone pillars, arched doorways, moderate detail, dim torchlight, wide shot, dark fantasy",
        "type_bg_near": "best quality, newest, no humans, scenery, dark dungeon foreground, detailed stone wall, iron bars, chains, sharp detail, warm torch glow, side view, dark fantasy",
    }

    all_tests = {**walls, **floors, **ceilings}
    for name, prompt in all_tests.items():
        r = generate(name, prompt, NEG_TILES, 512, 512)
        results.append(r)
        time.sleep(1)

    for name, prompt in platforms.items():
        r = generate(name, prompt, NEG_OBJECTS, 1024, 512)
        results.append(r)
        time.sleep(1)

    for name, prompt in env_objects.items():
        r = generate(name, prompt, NEG_OBJECTS, 1024, 1024)
        results.append(r)
        time.sleep(1)

    for name, prompt in backgrounds.items():
        r = generate(name, prompt, NEG_TILES, 1536, 768)
        results.append(r)
        time.sleep(1)

    return results


def test_transparency():
    """テスト4: 透過背景・シームレス指示の比較"""
    print("\n=== TEST 4: Transparency & Seamless Instructions ===")

    results = []

    # 4A: 背景指示の違い（同じオブジェクト）
    bg_tests = {
        "trans_01_dark_bg": "best quality, newest, no humans, wall mounted torch, flickering flame, game prop, isolated object, simple dark background",
        "trans_02_white_bg": "best quality, newest, no humans, wall mounted torch, flickering flame, game prop, isolated object, white background",
        "trans_03_black_bg": "best quality, newest, no humans, wall mounted torch, flickering flame, game prop, isolated object, black background",
        "trans_04_transparent": "best quality, newest, no humans, wall mounted torch, flickering flame, game prop, isolated object, transparent background, alpha channel",
        "trans_05_checkered": "best quality, newest, no humans, wall mounted torch, flickering flame, game prop, isolated object, checkered background, transparency grid",
    }

    for name, prompt in bg_tests.items():
        r = generate(name, prompt, NEG_OBJECTS, 512, 512)
        results.append(r)
        time.sleep(1)

    # 4B: シームレス指示のバリエーション
    seam_tests = {
        "seam_01_none": "best quality, newest, no humans, stone wall texture, rough brick, dark dungeon, front view",
        "seam_02_seamless": "best quality, newest, no humans, seamless, stone wall texture, rough brick, dark dungeon, front view",
        "seam_03_seamless_pattern": "best quality, newest, no humans, seamless pattern, stone wall texture, rough brick, dark dungeon, front view",
        "seam_04_tileable": "best quality, newest, no humans, tileable texture, stone wall texture, rough brick, dark dungeon, front view",
        "seam_05_repeating": "best quality, newest, no humans, repeating pattern, seamless tileable, stone wall texture, rough brick, dark dungeon, front view",
    }

    for name, prompt in seam_tests.items():
        r = generate(name, prompt, NEG_TILES, 512, 512)
        results.append(r)
        time.sleep(1)

    return results


def save_results(all_results: list, test_name: str):
    """結果をJSONで保存"""
    report = {
        "test_name": test_name,
        "model": MODEL_NAME,
        "timestamp": datetime.now().isoformat(),
        "base_params": {k: v for k, v in BASE_PARAMS.items() if k != "model_name"},
        "results": all_results,
    }

    report_path = OUTPUT_DIR / f"results_{test_name}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {report_path}")


def main():
    test_group = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"=== Tile Prompt Test ({test_group}) ===")
    print(f"Model: {MODEL_NAME}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Seed: {SEED}")
    print()

    all_results = []

    if test_group in ("keyword_compare", "all"):
        all_results.extend(test_keyword_compare())
        save_results(all_results, "keyword_compare")

    if test_group in ("grid_vs_single", "all"):
        all_results.extend(test_grid_vs_single())
        save_results(all_results, "grid_vs_single")

    if test_group in ("tile_types", "all"):
        all_results.extend(test_tile_types())
        save_results(all_results, "tile_types")

    if test_group in ("transparency", "all"):
        all_results.extend(test_transparency())
        save_results(all_results, "transparency")

    # Final summary
    save_results(all_results, "all")

    success = sum(1 for r in all_results if "error" not in r)
    fail = sum(1 for r in all_results if "error" in r)
    print(f"\n=== DONE: {success} success, {fail} failed, {len(all_results)} total ===")


if __name__ == "__main__":
    main()
