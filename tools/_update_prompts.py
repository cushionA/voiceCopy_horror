#!/usr/bin/env python3
"""One-shot script to update asset-gen-request.json with FLUX.1-schnell optimized prompts."""
import json
from pathlib import Path

REQUEST_PATH = Path(__file__).parent.parent / "designs" / "asset-gen-request.json"

with open(REQUEST_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

prompts = {
    "SPR_PLAYER_IDLE": "pixel art game sprite, sci-fi armored knight standing idle, 32x32 pixel character, side view profile, futuristic power armor with glowing visor, dark blue and silver color scheme, clean pixel art style, transparent background, 2D game asset",
    "SPR_PLAYER_RUN": "pixel art game sprite sheet, sci-fi armored knight running animation, 32x32 pixel character, side view profile, dynamic running pose with motion blur effect, dark blue power armor, clean pixel art style, transparent background, 2D game asset",
    "SPR_PLAYER_JUMP": "pixel art game sprite, sci-fi armored knight jumping in mid-air, 32x32 pixel character, side view profile, legs bent upward, arms reaching up, dark blue power armor with glowing jets, clean pixel art, transparent background",
    "SPR_PLAYER_SWORD": "pixel art game sprite, sci-fi armored knight swinging an energy sword, 32x32 pixel character, side view profile, dynamic slash motion with energy trail, dark blue armor, cyan glowing blade, clean pixel art, transparent background",
    "SPR_PLAYER_GUN": "pixel art game sprite, sci-fi armored knight aiming a plasma gun forward, 32x32 pixel character, side view profile, shooting stance, dark blue power armor, weapon with cyan glow, clean pixel art, transparent background",
    "SPR_NPC": "pixel art game sprite, small friendly support robot companion, 32x32 pixel character, side view profile, round body with antenna, blue LED eyes, hovering slightly, white and blue color scheme, clean pixel art, transparent background",
    "SPR_SLIME": "pixel art game sprite, toxic green slime monster blob, 16x16 pixel enemy, side view, semi-transparent gelatinous body, dripping, menacing eyes, vibrant green color, clean pixel art, transparent background",
    "SPR_FLYER": "pixel art game sprite, small flying alien bio-weapon creature with insect wings, 16x16 pixel enemy, side view, purple and red organic body, glowing eyes, hovering, clean pixel art, transparent background",
    "SPR_SHOOTER": "pixel art game sprite, small robotic turret enemy with cannon, 16x16 pixel enemy, side view, mechanical design, red warning lights, gun barrel pointing forward, metallic gray, clean pixel art, transparent background",
    "SPR_BOSS_ALPHA": "pixel art game sprite, massive mutant bio-weapon boss creature emerging from broken capsule, 96x96 pixel boss, side view, grotesque organic body with exposed muscle and tubes, green toxic glow, menacing, detailed pixel art, transparent background",
    "SPR_BOSS_OMEGA": "pixel art game sprite, massive mechanical final boss robot fused with control systems, 96x96 pixel boss, side view, heavy armored body with cables and monitors, red glowing core, intimidating, detailed pixel art, transparent background",
    "SPR_HEALTH": "pixel art game item, small health recovery capsule, 16x16 pixel item, green glowing energy capsule with cross symbol, sci-fi medical item, clean pixel art, transparent background",
    "SPR_ENERGY": "pixel art game item, small blue energy crystal charge, 16x16 pixel item, glowing blue crystalline structure, electric sparks, sci-fi power cell, clean pixel art, transparent background",
    "SPR_KEY": "pixel art game item, digital holographic key card, 16x16 pixel item, sci-fi access card with glowing circuit pattern, cyan holographic effect, clean pixel art, transparent background",
    "SPR_BULLET_PLAYER": "pixel art game projectile, small cyan energy bullet, 8x8 pixels, horizontal plasma bolt with glow trail, bright cyan color, clean pixel art, transparent background",
    "SPR_BULLET_NPC": "pixel art game projectile, small blue laser bolt, 8x8 pixels, horizontal blue energy shot, clean pixel art, transparent background",
    "SPR_BULLET_ENEMY": "pixel art game projectile, small red toxic bullet, 8x8 pixels, horizontal red energy shot with particle trail, clean pixel art, transparent background",
    "SPR_HEALTHBAR": "pixel art game UI element, horizontal health bar, 128x16 pixels, segmented bar with red to green gradient fill, dark border frame, clean pixel art design, transparent background",
    "SPR_ENERGYBAR": "pixel art game UI element, horizontal energy bar, 128x16 pixels, segmented bar with blue gradient glow fill, dark border frame, clean pixel art design, transparent background",
    "TILE_SF_INDUSTRIAL": "pixel art tileset for 2D platformer game, sci-fi industrial zone tiles, 16x16 pixel grid, includes ground tiles metal platforms pipes walls ladders, dark industrial color palette with rust and steel, seamless tileable, top-down and side view mixed",
    "TILE_SF_LAB": "pixel art tileset for 2D platformer game, sci-fi laboratory tiles, 16x16 pixel grid, includes clean white walls floor ceiling panels glass windows, sterile lab environment, seamless tileable",
    "TILE_SF_UNDERGROUND": "pixel art tileset for 2D platformer game, underground waterway sewer tiles, 16x16 pixel grid, includes dark stone walls water surface drain pipes moss, damp dark atmosphere, seamless tileable",
    "TILE_SF_CONTROL": "pixel art tileset for 2D platformer game, sci-fi control room tiles, 16x16 pixel grid, includes monitor screens console panels floor ceiling with cables, green screen glow, seamless tileable",
    "BG_DARK_SKY": "game background art, dark polluted dystopian sky with toxic clouds, ruined city skyline silhouette in distance, post-apocalyptic atmosphere, purple and dark gray color palette, parallax scrolling background layer, 960x540",
    "BG_RUINED_BUILDINGS": "game background art, destroyed city buildings in ruins, broken skyscrapers with exposed steel frames, post-apocalyptic sci-fi scene, dark moody atmosphere, parallax scrolling background layer, 960x540",
    "BG_LAB_WALLS": "game background art, sterile white laboratory interior walls, sci-fi research facility, clean panels with subtle blue lighting, medical equipment silhouettes, parallax scrolling background layer, 960x540",
    "BG_CAVE_CEILING": "game background art, underground cave ceiling with stalactites and dripping water, dark damp atmosphere, bioluminescent fungi spots, rocky texture, parallax scrolling background layer, 960x540",
    "BG_MONITORS": "game background art, sci-fi control room with wall of glowing monitors and terminals, green data streams on screens, dark room with screen glow, cyberpunk atmosphere, parallax scrolling background layer, 960x540",
    "SPR_PORTRAIT_PLAYER": "anime style character portrait, sci-fi armored knight hero, bust-up shot from waist, determined confident expression, dark blue power armor with glowing visor lifted showing young male face, detailed shading, transparent background, 256x512 vertical",
    "SPR_PORTRAIT_NPC": "anime style character portrait, friendly support robot companion, bust-up shot, round friendly design with blue LED face display showing happy expression, white and blue body, cute robot aesthetic, transparent background, 256x512 vertical",
    "SPR_PORTRAIT_BOSS_ALPHA": "anime style character portrait, grotesque mutant bio-weapon boss creature, bust-up shot, exposed muscle tissue and tubes, multiple glowing green eyes, menacing snarling expression, horror sci-fi aesthetic, transparent background, 256x512 vertical",
    "SPR_PORTRAIT_BOSS_OMEGA": "anime style character portrait, massive mechanical final boss, bust-up shot, heavy chrome armor with red glowing core in chest, cold calculating robotic face with single red eye, intimidating presence, transparent background, 256x512 vertical",
}

for asset in data["assets"]:
    aid = asset["asset_id"]
    if aid in prompts:
        asset["prompt"] = prompts[aid]

with open(REQUEST_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Updated {len(prompts)} prompts for FLUX.1-schnell")
