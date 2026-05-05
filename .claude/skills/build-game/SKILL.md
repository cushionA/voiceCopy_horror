---
name: build-game
description: Build the Unity game for a target platform
user-invocable: true
disable-model-invocation: true
argument-hint: <Platform> (WebGL|Windows|Android|iOS)
---

# Build Game: $ARGUMENTS

Unityプロジェクトを指定プラットフォーム向けにビルドする。

## 手順

1. **テスト実行**: ビルド前に全テストを実行
   - Edit Mode テスト
   - Play Mode テスト
   - テストが1つでもFailしたらビルドを中止

2. **シーン検証**: `/validate-scene` で全シーンの整合性を確認
   - 参照切れがないか
   - Placeholder残存の警告

3. **ビルド実行**:
   ```
   Unity.exe -quit -batchmode -projectPath "[プロジェクトパス]" \
     -executeMethod BuildScript.Build \
     -buildTarget $0 \
     -logFile build.log
   ```

4. **結果報告**:
   - ビルド成功/失敗
   - ビルドサイズ
   - 警告/エラーの要約

## 対応プラットフォーム
- `WebGL` — ブラウザ向け
- `Windows` — Windows Standalone (Win64)
- `Android` — Android APK/AAB
- `iOS` — iOS Xcode Project
