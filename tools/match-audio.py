#!/usr/bin/env python3
"""音声アセットマッチング — 手持ちライブラリから最適な音声を選定"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# アセットID → 検索クエリと選定条件のマッピング
AUDIO_MATCHES = {
    # SFX
    "SFX_SWORD_SLASH": {
        "query": "sword slash designed impact",
        "prefer_folder": "Designed/Sword Slash",
        "target": "Assets/Audio/SFX/sfx_sword_slash.wav"
    },
    "SFX_GUN_SHOT": {
        "query": "laser gun shot sci-fi",
        "prefer_folder": "Sci-Fi",
        "target": "Assets/Audio/SFX/sfx_gun_shot.wav"
    },
    "SFX_GUN_CHARGE": {
        "query": "charge energy power up sci-fi",
        "prefer_folder": "Sci-Fi",
        "target": "Assets/Audio/SFX/sfx_gun_charge.wav"
    },
    "SFX_ENEMY_HIT": {
        "query": "hit impact body soft",
        "prefer_folder": "Impact",
        "target": "Assets/Audio/SFX/sfx_enemy_hit.wav"
    },
    "SFX_ENEMY_DEATH": {
        "query": "death dissolve destroy creature",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_enemy_death.wav"
    },
    "SFX_PLAYER_DAMAGE": {
        "query": "hit damage pain impact",
        "prefer_folder": "Impact",
        "target": "Assets/Audio/SFX/sfx_player_damage.wav"
    },
    "SFX_PLAYER_DEATH": {
        "query": "death game over fail",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_player_death.wav"
    },
    "SFX_ITEM_PICKUP": {
        "query": "pickup collect coin gem item",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_item_pickup.wav"
    },
    "SFX_WEAPON_SWITCH": {
        "query": "switch click mechanical weapon",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_weapon_switch.wav"
    },
    "SFX_JUMP": {
        "query": "jump bounce whoosh light",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_jump.wav"
    },
    "SFX_DASH": {
        "query": "dash whoosh wind fast",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_dash.wav"
    },
    "SFX_ELEVATOR": {
        "query": "elevator mechanical motor hum",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_elevator.wav"
    },
    "SFX_WARP": {
        "query": "teleport warp portal sci-fi",
        "prefer_folder": "Sci-Fi",
        "target": "Assets/Audio/SFX/sfx_warp.wav"
    },
    "SFX_DOOR_OPEN": {
        "query": "door open metal heavy gate",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_door_open.wav"
    },
    "SFX_BOSS_ROAR": {
        "query": "roar monster creature boss growl",
        "prefer_folder": "",
        "target": "Assets/Audio/SFX/sfx_boss_roar.wav"
    },
    # BGM — search in Gamemaster Audio library
    "BGM_AREA1": {
        "query": "action dark theme loop electronic",
        "prefer_folder": "Music",
        "target": "Assets/Audio/BGM/bgm_area1.mp3"
    },
    "BGM_BOSS1": {
        "query": "boss battle intense fight",
        "prefer_folder": "Music",
        "target": "Assets/Audio/BGM/bgm_boss1.mp3"
    },
    "BGM_AREA2": {
        "query": "underground dark ambient cave",
        "prefer_folder": "Music",
        "target": "Assets/Audio/BGM/bgm_area2.mp3"
    },
    "BGM_BOSS2": {
        "query": "final boss epic battle intense",
        "prefer_folder": "Music",
        "target": "Assets/Audio/BGM/bgm_boss2.mp3"
    },
    "BGM_TITLE": {
        "query": "title menu theme sci-fi",
        "prefer_folder": "Music",
        "target": "Assets/Audio/BGM/bgm_title.mp3"
    },
    "BGM_ENDING": {
        "query": "ending victory calm peaceful",
        "prefer_folder": "Music",
        "target": "Assets/Audio/BGM/bgm_ending.mp3"
    },
}


def search_audio(query):
    """asset-index.py search を呼び出して結果を返す"""
    result = subprocess.run(
        [sys.executable, "tools/asset-index.py", "search", query],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return data.get("results", [])
    except json.JSONDecodeError:
        return []


def select_best_match(results, prefer_folder=""):
    """結果から最適な1つを選定（prefer_folderを優先、なければ先頭）"""
    if not results:
        return None

    if prefer_folder:
        for r in results:
            if prefer_folder.lower() in r.get("folder", "").lower():
                return r

    # prefer_folder なしの場合は先頭（最も関連性が高い）
    return results[0]


def main():
    os.makedirs(PROJECT_ROOT / "Assets" / "Audio" / "SFX", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "Assets" / "Audio" / "BGM", exist_ok=True)

    matched = 0
    failed = 0
    results_log = []

    for asset_id, config in AUDIO_MATCHES.items():
        query = config["query"]
        prefer = config.get("prefer_folder", "")
        target = config["target"]

        results = search_audio(query)
        best = select_best_match(results, prefer)

        if best:
            source = PROJECT_ROOT / best["path"]
            dest = PROJECT_ROOT / target

            # 拡張子を揃える（sourceと同じにする）
            src_ext = os.path.splitext(str(source))[1]
            dest_ext = os.path.splitext(str(dest))[1]
            if src_ext != dest_ext:
                dest = dest.with_suffix(src_ext)

            try:
                shutil.copy2(source, dest)
                matched += 1
                results_log.append({
                    "asset_id": asset_id,
                    "status": "matched",
                    "source": best["name"],
                    "library": best["library"],
                    "target": str(dest.relative_to(PROJECT_ROOT))
                })
                print(f"  OK: {asset_id} <- {best['name'][:60]}")
            except Exception as e:
                failed += 1
                results_log.append({"asset_id": asset_id, "status": "error", "error": str(e)})
                print(f"  ERR: {asset_id} - {e}")
        else:
            failed += 1
            results_log.append({"asset_id": asset_id, "status": "no_match"})
            print(f"  MISS: {asset_id} (no match for '{query}')")

    # Save results
    with open(PROJECT_ROOT / "designs" / "audio-match-results.json", "w", encoding="utf-8") as f:
        json.dump({"matched": matched, "failed": failed, "results": results_log}, f, indent=2, ensure_ascii=False)

    print(f"\nTotal: {matched} matched, {failed} failed")


if __name__ == "__main__":
    main()
