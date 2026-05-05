---
name: bind-assets
description: Bind placed assets to placeholder GameObjects, replacing temporary references
user-invocable: true
disable-model-invocation: true
---

# Bind Assets

配置済みアセットをプレースホルダーGameObjectにバインドする。

## 手順

1. **プレースホルダー検出**: シーン内の `[PLACEHOLDER]` 付きGameObjectを列挙
2. **アセット照合**: `python tools/feature-db.py assets --status pending` で未配置アセットと配置先マッピングを確認
3. **ファイル存在確認**: マッピングされたパスにアセットファイルが存在するか確認
4. **バインド実行**: `.claude/rules/asset-workflow.md` の「本番アセット差替え手順」に従い実行
5. **feature-db更新**: `python tools/feature-db.py bind` で配置完了アセットを記録
6. **結果レポート**:

```
=== Asset Binding Results ===

BOUND:
- player_idle.png → Player.SpriteRenderer.sprite ✓
- walk.anim → PlayerAnimator.Walk.motion ✓

STILL PENDING:
- footstep.wav — file not found at Assets/Audio/SFX/footstep.wav

Summary: 2 bound, 1 still pending
```

## 注意
- バインド前にシーンのバックアップを取ることを推奨
- MCP unity tools 経由で実行（利用可能な場合）
- 手動の場合はC#エディタスクリプトを生成して実行
