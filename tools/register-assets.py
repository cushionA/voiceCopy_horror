#!/usr/bin/env python3
"""BLADE TRIGGER 必要アセットを一括登録するスクリプト"""
import subprocess
import sys

def add(asset_id, feature, asset_type, desc, priority="medium", path=None):
    cmd = [sys.executable, "tools/feature-db.py", "add-asset",
           asset_id, feature, asset_type, desc, "--priority", priority]
    if path:
        cmd.extend(["--path", path])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  SKIP: {asset_id} ({result.stderr.strip()})")
    else:
        print(f"  OK: {asset_id}")

print("=== スプライト（キャラクター） ===")
add("SPR_PLAYER_IDLE", "PlayerMovement_Core", "Sprite",
    "プレイヤーidle 32x32 SFアーマー装甲戦士", "high",
    "Assets/Sprites/Player/player_idle.png")
add("SPR_PLAYER_RUN", "PlayerMovement_Core", "Sprite",
    "プレイヤーrun 32x32 走行アニメーション用シート", "high",
    "Assets/Sprites/Player/player_run.png")
add("SPR_PLAYER_JUMP", "PlayerMovement_Advanced", "Sprite",
    "プレイヤーjump 32x32 ジャンプポーズ", "high",
    "Assets/Sprites/Player/player_jump.png")
add("SPR_PLAYER_SWORD", "SwordCombat_BasicAttack", "Sprite",
    "プレイヤー剣攻撃 32x32 斬撃モーション", "high",
    "Assets/Sprites/Player/player_sword.png")
add("SPR_PLAYER_GUN", "GunCombat_BasicShot", "Sprite",
    "プレイヤー銃構え 32x32 射撃ポーズ", "high",
    "Assets/Sprites/Player/player_gun.png")
add("SPR_NPC", "AllyNPC_Core", "Sprite",
    "味方NPC 32x32 SFサポートロボ", "medium",
    "Assets/Sprites/NPC/npc_ally.png")

print("\n=== スプライト（敵） ===")
add("SPR_SLIME", "EnemyBase_Types", "Sprite",
    "スライム 16x16 緑色の有機生物兵器", "medium",
    "Assets/Sprites/Enemies/slime.png")
add("SPR_FLYER", "EnemyBase_Types", "Sprite",
    "フライヤー 16x16 浮遊する生物兵器", "medium",
    "Assets/Sprites/Enemies/flyer.png")
add("SPR_SHOOTER", "EnemyBase_Types", "Sprite",
    "シューター 16x16 遠距離射撃する生物兵器", "medium",
    "Assets/Sprites/Enemies/shooter.png")
add("SPR_BOSS_ALPHA", "BossAI_Core", "Sprite",
    "ボスアルファ 96x96 巨大生体兵器 培養カプセルから出現", "high",
    "Assets/Sprites/Enemies/boss_alpha.png")
add("SPR_BOSS_OMEGA", "BossAI_Core", "Sprite",
    "ボスオメガ 96x96 制御装置融合型最終兵器", "high",
    "Assets/Sprites/Enemies/boss_omega.png")

print("\n=== スプライト（アイテム） ===")
add("SPR_HEALTH", "ItemSystem_Core", "Sprite",
    "回復アイテム 16x16 緑色のエネルギーカプセル", "medium",
    "Assets/Sprites/Items/health.png")
add("SPR_ENERGY", "EnergySystem_Core", "Sprite",
    "エネルギーチャージ 16x16 青色のエネルギー結晶", "medium",
    "Assets/Sprites/Items/energy_charge.png")
add("SPR_KEY", "InventorySystem_Core", "Sprite",
    "鍵アイテム 16x16 SF風デジタルキー", "medium",
    "Assets/Sprites/Items/key.png")

print("\n=== スプライト（弾丸・エフェクト） ===")
add("SPR_BULLET_PLAYER", "GunCombat_BasicShot", "Sprite",
    "プレイヤー弾 8x8 エネルギー弾", "medium",
    "Assets/Sprites/Projectiles/bullet_player.png")
add("SPR_BULLET_NPC", "NPCShooting_Core", "Sprite",
    "NPC弾 8x8 支援射撃弾", "low",
    "Assets/Sprites/Projectiles/bullet_npc.png")
add("SPR_BULLET_ENEMY", "EnemyBase_Combat", "Sprite",
    "敵弾 8x8 赤色の汚染弾", "medium",
    "Assets/Sprites/Projectiles/bullet_enemy.png")

print("\n=== スプライト（UI） ===")
add("SPR_HEALTHBAR", "UIBase_HUD", "Sprite",
    "HPバー 128x16 赤→緑のグラデーション", "medium",
    "Assets/Sprites/UI/healthbar.png")
add("SPR_ENERGYBAR", "UIBase_HUD", "Sprite",
    "エネルギーバー 128x16 青のグラデーション", "medium",
    "Assets/Sprites/UI/energybar.png")

print("\n=== タイルセット ===")
add("TILE_SF_INDUSTRIAL", "StageSystem_Core", "Sprite",
    "タイルセット sf_industrial 16x16 汚染区域工業地帯タイル（地面+壁+プラットフォーム+水+はしご）", "high",
    "Assets/Sprites/Tiles/sf_industrial.png")
add("TILE_SF_LAB", "StageSystem_Core", "Sprite",
    "タイルセット sf_lab 16x16 研究棟ボスエリア用タイル", "medium",
    "Assets/Sprites/Tiles/sf_lab.png")
add("TILE_SF_UNDERGROUND", "StageSystem_Core", "Sprite",
    "タイルセット sf_underground 16x16 地下水路タイル", "medium",
    "Assets/Sprites/Tiles/sf_underground.png")
add("TILE_SF_CONTROL", "StageSystem_Core", "Sprite",
    "タイルセット sf_control 16x16 制御室タイル", "medium",
    "Assets/Sprites/Tiles/sf_control.png")

print("\n=== 背景 ===")
add("BG_DARK_SKY", "StageSystem_Core", "Sprite",
    "パララックス背景 暗い空 汚染された空 960x540", "medium",
    "Assets/Sprites/Backgrounds/dark_sky.png")
add("BG_RUINED_BUILDINGS", "StageSystem_Core", "Sprite",
    "パララックス背景 廃墟ビル群 960x540", "medium",
    "Assets/Sprites/Backgrounds/ruined_buildings.png")
add("BG_LAB_WALLS", "StageSystem_Core", "Sprite",
    "パララックス背景 研究棟の壁 960x540", "medium",
    "Assets/Sprites/Backgrounds/lab_walls.png")
add("BG_CAVE_CEILING", "StageSystem_Core", "Sprite",
    "パララックス背景 洞窟天井 960x540", "medium",
    "Assets/Sprites/Backgrounds/cave_ceiling.png")
add("BG_MONITORS", "StageSystem_Core", "Sprite",
    "パララックス背景 制御室モニター群 960x540", "medium",
    "Assets/Sprites/Backgrounds/monitors.png")

print("\n=== イベント立ち絵 ===")
add("SPR_PORTRAIT_PLAYER", "EventScene_Core", "Sprite",
    "プレイヤー立ち絵 256x512 バストアップ", "medium",
    "Assets/Sprites/Characters/player_portrait.png")
add("SPR_PORTRAIT_NPC", "EventScene_Core", "Sprite",
    "NPC立ち絵 256x512 バストアップ", "medium",
    "Assets/Sprites/Characters/npc_portrait.png")
add("SPR_PORTRAIT_BOSS_ALPHA", "EventScene_Core", "Sprite",
    "ボスアルファ立ち絵 256x512", "low",
    "Assets/Sprites/Characters/boss_alpha_portrait.png")
add("SPR_PORTRAIT_BOSS_OMEGA", "EventScene_Core", "Sprite",
    "ボスオメガ立ち絵 256x512", "low",
    "Assets/Sprites/Characters/boss_omega_portrait.png")

print("\n=== BGM ===")
add("BGM_AREA1", "StageSystem_Core", "Audio",
    "エリア1 BGM 汚染区域テーマ アクション系 ループ可", "high",
    "Assets/Audio/BGM/bgm_area1.mp3")
add("BGM_BOSS1", "BossAI_Core", "Audio",
    "エリア1ボス BGM 緊迫したボスバトル ループ可", "high",
    "Assets/Audio/BGM/bgm_boss1.mp3")
add("BGM_AREA2", "StageSystem_Core", "Audio",
    "エリア2 BGM 地下水路テーマ 暗い雰囲気 ループ可", "high",
    "Assets/Audio/BGM/bgm_area2.mp3")
add("BGM_BOSS2", "BossAI_Core", "Audio",
    "最終ボス BGM 壮大で激しいバトル曲 ループ可", "high",
    "Assets/Audio/BGM/bgm_boss2.mp3")
add("BGM_TITLE", "TitleScreen_Core", "Audio",
    "タイトル画面 BGM SF雰囲気のメインテーマ", "medium",
    "Assets/Audio/BGM/bgm_title.mp3")
add("BGM_ENDING", "GameFlow_Core", "Audio",
    "エンディング BGM 穏やかな希望の曲", "medium",
    "Assets/Audio/BGM/bgm_ending.mp3")

print("\n=== SFX ===")
add("SFX_SWORD_SLASH", "SwordCombat_BasicAttack", "Audio",
    "剣斬撃音 シャープな金属音", "high",
    "Assets/Audio/SFX/sfx_sword_slash.wav")
add("SFX_GUN_SHOT", "GunCombat_BasicShot", "Audio",
    "銃撃音 エネルギー弾発射音", "high",
    "Assets/Audio/SFX/sfx_gun_shot.wav")
add("SFX_GUN_CHARGE", "GunCombat_Advanced", "Audio",
    "チャージショット溜め音 徐々に高まるエネルギー音", "medium",
    "Assets/Audio/SFX/sfx_gun_charge.wav")
add("SFX_ENEMY_HIT", "EnemyBase_Combat", "Audio",
    "敵被弾音 柔らかい衝撃音", "medium",
    "Assets/Audio/SFX/sfx_enemy_hit.wav")
add("SFX_ENEMY_DEATH", "EnemyBase_Combat", "Audio",
    "敵死亡音 崩壊・消滅音", "medium",
    "Assets/Audio/SFX/sfx_enemy_death.wav")
add("SFX_PLAYER_DAMAGE", "HealthSystem_Core", "Audio",
    "プレイヤー被弾音", "high",
    "Assets/Audio/SFX/sfx_player_damage.wav")
add("SFX_PLAYER_DEATH", "HealthSystem_Core", "Audio",
    "プレイヤー死亡音", "medium",
    "Assets/Audio/SFX/sfx_player_death.wav")
add("SFX_ITEM_PICKUP", "ItemSystem_Core", "Audio",
    "アイテム取得音 明るいキラキラ音", "medium",
    "Assets/Audio/SFX/sfx_item_pickup.wav")
add("SFX_WEAPON_SWITCH", "WeaponSwitch_Core", "Audio",
    "武器切替音 メカニカルなクリック音", "medium",
    "Assets/Audio/SFX/sfx_weapon_switch.wav")
add("SFX_JUMP", "PlayerMovement_Core", "Audio",
    "ジャンプ音 軽快な跳躍音", "medium",
    "Assets/Audio/SFX/sfx_jump.wav")
add("SFX_DASH", "PlayerMovement_Advanced", "Audio",
    "ダッシュ音 風を切る音", "medium",
    "Assets/Audio/SFX/sfx_dash.wav")
add("SFX_ELEVATOR", "StageGimmick_Elevator", "Audio",
    "エレベーター稼働音 機械的な動作音", "low",
    "Assets/Audio/SFX/sfx_elevator.wav")
add("SFX_WARP", "StageGimmick_WarpGate", "Audio",
    "ワープ音 SF転送音", "low",
    "Assets/Audio/SFX/sfx_warp.wav")
add("SFX_DOOR_OPEN", "AreaGate_Core", "Audio",
    "ゲート開放音 重い金属ドア", "low",
    "Assets/Audio/SFX/sfx_door_open.wav")
add("SFX_BOSS_ROAR", "BossAI_Core", "Audio",
    "ボス登場咆哮 重低音の威嚇音", "medium",
    "Assets/Audio/SFX/sfx_boss_roar.wav")

print("\n=== 登録完了 ===")
