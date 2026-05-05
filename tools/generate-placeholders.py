#!/usr/bin/env python3
"""カラーコード付きプレースホルダー画像を生成する（Kaggle未使用時の代替）"""
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent

# アセットID → (幅, 高さ, 色, ラベル, 出力パス)
PLACEHOLDER_IMAGES = {
    # プレイヤー
    "SPR_PLAYER_IDLE":    (32, 32, (0, 120, 255),  "P:IDLE",  "Sprites/Player/player_idle.png"),
    "SPR_PLAYER_RUN":     (32, 32, (0, 120, 255),  "P:RUN",   "Sprites/Player/player_run.png"),
    "SPR_PLAYER_JUMP":    (32, 32, (0, 120, 255),  "P:JUMP",  "Sprites/Player/player_jump.png"),
    "SPR_PLAYER_SWORD":   (32, 32, (0, 120, 255),  "P:SWD",   "Sprites/Player/player_sword.png"),
    "SPR_PLAYER_GUN":     (32, 32, (0, 120, 255),  "P:GUN",   "Sprites/Player/player_gun.png"),
    "SPR_NPC":            (32, 32, (0, 200, 100),  "NPC",     "Sprites/NPC/npc_ally.png"),
    # 敵
    "SPR_SLIME":          (16, 16, (50, 200, 50),  "SLM",     "Sprites/Enemies/slime.png"),
    "SPR_FLYER":          (16, 16, (200, 100, 200),"FLY",     "Sprites/Enemies/flyer.png"),
    "SPR_SHOOTER":        (16, 16, (200, 50, 50),  "SHT",     "Sprites/Enemies/shooter.png"),
    "SPR_BOSS_ALPHA":     (96, 96, (200, 0, 0),    "BOSS A",  "Sprites/Enemies/boss_alpha.png"),
    "SPR_BOSS_OMEGA":     (96, 96, (150, 0, 200),  "BOSS O",  "Sprites/Enemies/boss_omega.png"),
    # アイテム
    "SPR_HEALTH":         (16, 16, (0, 255, 0),    "HP",      "Sprites/Items/health.png"),
    "SPR_ENERGY":         (16, 16, (0, 150, 255),  "EN",      "Sprites/Items/energy_charge.png"),
    "SPR_KEY":            (16, 16, (255, 215, 0),  "KEY",     "Sprites/Items/key.png"),
    # 弾丸
    "SPR_BULLET_PLAYER":  (8, 8,   (100, 200, 255),"",        "Sprites/Projectiles/bullet_player.png"),
    "SPR_BULLET_NPC":     (8, 8,   (100, 255, 100),"",        "Sprites/Projectiles/bullet_npc.png"),
    "SPR_BULLET_ENEMY":   (8, 8,   (255, 50, 50),  "",        "Sprites/Projectiles/bullet_enemy.png"),
    # UI
    "SPR_HEALTHBAR":      (128, 16,(255, 50, 50),  "HP BAR",  "Sprites/UI/healthbar.png"),
    "SPR_ENERGYBAR":      (128, 16,(50, 100, 255), "EN BAR",  "Sprites/UI/energybar.png"),
    # タイルセット (タイルシート4x2)
    "TILE_SF_INDUSTRIAL": (64, 32, (100, 80, 60),  "INDSTRL", "Sprites/Tiles/sf_industrial.png"),
    "TILE_SF_LAB":        (64, 32, (120, 120, 150),"LAB",     "Sprites/Tiles/sf_lab.png"),
    "TILE_SF_UNDERGROUND":(64, 32, (60, 80, 100),  "UNDER",   "Sprites/Tiles/sf_underground.png"),
    "TILE_SF_CONTROL":    (64, 32, (80, 100, 120), "CTRL",    "Sprites/Tiles/sf_control.png"),
    # 背景
    "BG_DARK_SKY":        (960, 540,(20, 20, 40),  "DARK SKY",       "Sprites/Backgrounds/dark_sky.png"),
    "BG_RUINED_BUILDINGS":(960, 540,(50, 40, 35),  "RUINS",          "Sprites/Backgrounds/ruined_buildings.png"),
    "BG_LAB_WALLS":       (960, 540,(80, 80, 100), "LAB WALLS",      "Sprites/Backgrounds/lab_walls.png"),
    "BG_CAVE_CEILING":    (960, 540,(40, 50, 60),  "CAVE",           "Sprites/Backgrounds/cave_ceiling.png"),
    "BG_MONITORS":        (960, 540,(30, 50, 60),  "MONITORS",       "Sprites/Backgrounds/monitors.png"),
    # 立ち絵
    "SPR_PORTRAIT_PLAYER":     (256, 512,(0, 120, 255),   "PLAYER",         "Sprites/Characters/player_portrait.png"),
    "SPR_PORTRAIT_NPC":        (256, 512,(0, 200, 100),   "NPC",            "Sprites/Characters/npc_portrait.png"),
    "SPR_PORTRAIT_BOSS_ALPHA": (256, 512,(200, 0, 0),     "BOSS ALPHA",     "Sprites/Characters/boss_alpha_portrait.png"),
    "SPR_PORTRAIT_BOSS_OMEGA": (256, 512,(150, 0, 200),   "BOSS OMEGA",     "Sprites/Characters/boss_omega_portrait.png"),
}


def create_placeholder(width, height, color, label, output_path):
    """カラーコード付きプレースホルダー画像を生成"""
    img = Image.new("RGBA", (width, height), (*color, 200))
    draw = ImageDraw.Draw(img)

    # 枠線
    draw.rectangle([(0, 0), (width-1, height-1)], outline=(255, 255, 255, 128), width=1)

    # ラベルテキスト
    if label and width >= 16:
        font_size = min(width // max(len(label), 1), height // 2, 14)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (width - text_w) // 2
        y = (height - text_h) // 2
        draw.text((x, y), label, fill=(255, 255, 255, 255), font=font)

    full_path = PROJECT_ROOT / "Assets" / output_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(full_path)
    return full_path


def main():
    count = 0
    for asset_id, (w, h, color, label, path) in PLACEHOLDER_IMAGES.items():
        out = create_placeholder(w, h, color, label, path)
        print(f"  OK: {asset_id} -> {path}")
        count += 1

    print(f"\nGenerated {count} placeholder images")


if __name__ == "__main__":
    main()
