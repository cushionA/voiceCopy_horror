---
name: create-event
description: Create an event scene (cutscene) from dialog data and character definitions. Generates Timeline + Dialog UI + camera setup.
user-invocable: true
argument-hint: <event_id or description>
---

# Create Event: $ARGUMENTS

会話データとキャラクター指定からイベントシーンを構築する。

## 前提
- ユーザーが会話データ（セリフ・話者・地の文）を提供すること
- `instruction-formats/event-scene.md` フォーマットに従うこと

## 手順

1. **会話データ受け取り**:
   - ユーザーから会話データを受け取る
   - 形式は自由（テキスト、箇条書き、台本形式など）
   - キャラクター定義（名前、表示位置）を確認する
   - 地の文がある場合はそれも含める

2. **イベントデータ構成**:
   - `instruction-formats/event-scene.md` フォーマットに変換する
   - 会話データから自動で以下を生成:
     - camera: 話者に応じたautoフォーカス
     - effect: シーンの開始/終了にfade_in/fade_out
     - wait: 基本はclick、地の文の末尾はtime指定
   - ユーザーが指定していない項目はデフォルト値で埋める

3. **フォーマット出力**: `designs/events/[event_id].md` に保存

4. **C#アセット生成**:
   - `EventSceneData` ScriptableObjectを生成（StageDataParserと同様のアプローチ）
   - Unity Editor メニュー `GameMakePipeline/Import Event From Text` で変換可能

5. **Timeline構築**:
   - EventSceneBuilderでTimeline + DialogUI + カメラ制御を自動構築
   - 各キャラクターに空のAnimationTrackを追加（人間が後から設定）
   - ダイアログテキストはSignalEmitterまたはカスタムDialogTrackで管理

6. **ユーザーに確認**:
   - 構築されたイベントデータを提示して確認を取る
   - 「カメラワークや演出の調整が必要ですか？」と聞く

## ルール
- セリフの内容は変更しない（ユーザーが提供したまま使用）
- 地の文もそのまま使用
- キャラクターの追加・削除は行わない
- camera/effectのデフォルト生成は控えめに（過度な演出は避ける）
- アニメーショントラックは空で作成し、人間に委ねる

## 出力先
- `designs/events/[event_id].md`
