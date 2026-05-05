# Asset Request 指示フォーマット

このフォーマットを使用して、必要アセットをリストアップする。

## フォーマット

```
# Asset Request: [機能名/シーン名]

## Required Assets

| ID | Type | Description | Format | Priority |
|----|------|-------------|--------|----------|
| A### | [Sprite/Model/Audio/Animation/Material/Texture] | [説明] | [ファイル形式+仕様] | [High/Medium/Low] |

## Placement Map

- [AssetID]: [配置パス] → [対象GameObject].[対象コンポーネント].[対象プロパティ]

## Notes
- [補足情報]
```

## Type 一覧

| Type | 説明 | 一般的なFormat |
|------|------|---------------|
| Sprite | 2Dスプライト画像 | PNG, 2^n px |
| Model | 3Dモデル | FBX, embedded materials |
| Audio | 音声ファイル | WAV(SFX), MP3(BGM) |
| Animation | アニメーションクリップ | .anim |
| AnimatorController | アニメーターコントローラー | .controller |
| Material | マテリアル | .mat |
| Texture | テクスチャ | PNG/TGA, 2^n px |
| Font | フォント | TTF/OTF |
| ScriptableObject | データアセット | .asset |

## 使用例

```
# Asset Request: PlayerCharacter

## Required Assets

| ID | Type | Description | Format | Priority |
|----|------|-------------|--------|----------|
| A001 | Sprite | プレイヤー待機ポーズ | 64x64 PNG, sRGB | High |
| A002 | Sprite | プレイヤー歩行スプライトシート | 256x64 PNG (4frame) | High |
| A003 | Animation | 歩行アニメーション | .anim, 12fps | High |
| A004 | Animation | 待機アニメーション | .anim, 8fps | High |
| A005 | AnimatorController | プレイヤーAnimator | .controller | High |
| A006 | AudioClip | 足音SE | .wav, 44.1kHz, mono | Medium |
| A007 | AudioClip | ジャンプSE | .wav, 44.1kHz, mono | Medium |

## Placement Map

- A001: Assets/Sprites/Player/idle.png → Player.SpriteRenderer.sprite
- A002: Assets/Sprites/Player/walk_sheet.png → (SpriteSheet for A003)
- A003: Assets/Animations/Player/walk.anim → PlayerAnimator.Walk.motion
- A004: Assets/Animations/Player/idle.anim → PlayerAnimator.Idle.motion
- A005: Assets/Animations/Player/PlayerAnimator.controller → Player.Animator.runtimeAnimatorController
- A006: Assets/Audio/SFX/footstep.wav → PlayerMovement.footstepClip
- A007: Assets/Audio/SFX/jump.wav → PlayerMovement.jumpClip

## Notes
- A002 は4フレームの等幅スプライトシート（各64x64）
- A006, A007 は短いワンショットSE（0.5秒以内推奨）
```
