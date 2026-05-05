# Event Scene 指示フォーマット

会話データとキャラクター指定からイベントシーン（カットシーン）を構築するためのフォーマット。
Timeline上にダイアログ・カメラワーク・演出を配置する。
アニメーションの設定は人間が行う（Timelineに空トラックを用意）。

## 概要
- 会話データ（セリフ・話者・地の文）を入力として受け取る
- キャラクターの登場位置と表示設定を定義する
- カメラワークは自動生成（話者フォーカス、パン等）。人間が後から調整可能
- アニメーショントラックは空で作成 → 人間が設定

## フォーマット

```
# Event: [イベントID]

## Meta
- name: [イベント表示名]
- trigger: [トリガー条件: zone/story_flag/manual]
- skippable: [true/false]
- stage: [関連ステージID（任意）]

## Characters
- [キャラクターID]:
  - display_name: [表示名]
  - position: [left/center/right/off]
  - sprite: [立ち絵パス or PLACEHOLDER]

## Dialog

### [連番]
- type: [dialog/narration/choice]
- speaker: [キャラクターID or null（地の文）]
- text: "[セリフまたは地の文]"
- camera: [auto/stay/pan_to:[キャラクターID]/zoom:[in/out]/shake]
- effect: [none/fade_in/fade_out/flash/screen_shake]
- wait: [auto/click/time:[秒数]]

## Camera Defaults
- dialog_focus: [true/false — 話者に自動フォーカスするか]
- default_zoom: [値]
- transition_speed: [秒数]
```

## type 一覧

| type | 説明 |
|------|------|
| dialog | キャラクターのセリフ。speaker必須 |
| narration | 地の文。speakerはnull |
| choice | 選択肢（将来拡張用） |

## camera 一覧

| camera | 説明 |
|--------|------|
| auto | 話者に自動フォーカス（デフォルト） |
| stay | カメラ移動なし |
| pan_to:[ID] | 指定キャラクターにパン |
| zoom:in | ズームイン |
| zoom:out | ズームアウト |
| shake | 画面揺れ |

## effect 一覧

| effect | 説明 |
|--------|------|
| none | 効果なし（デフォルト） |
| fade_in | フェードイン |
| fade_out | フェードアウト |
| flash | 白フラッシュ |
| screen_shake | 画面揺れ |

## 使用例

```
# Event: event_1_1_opening

## Meta
- name: 森の入口
- trigger: zone
- skippable: true
- stage: stage_1_1

## Characters
- hero:
  - display_name: ユウキ
  - position: left
  - sprite: Assets/Sprites/Characters/hero_portrait.png
- guide:
  - display_name: 妖精ミル
  - position: right
  - sprite: [PLACEHOLDER]

## Dialog

### 1
- type: narration
- speaker: null
- text: "深い森の入口に立つと、どこからか小さな光が近づいてきた。"
- camera: stay
- effect: fade_in
- wait: click

### 2
- type: dialog
- speaker: guide
- text: "あっ、やっと来た！ずっと待ってたんだよ！"
- camera: auto
- effect: none
- wait: click

### 3
- type: dialog
- speaker: hero
- text: "…君は？"
- camera: auto
- effect: none
- wait: click

### 4
- type: dialog
- speaker: guide
- text: "ボクはミル！この森の案内役さ。先に進むなら、ボクについてきて！"
- camera: auto
- effect: none
- wait: click

### 5
- type: narration
- speaker: null
- text: "小さな光は弾むように森の奥へ飛んでいった。"
- camera: zoom:out
- effect: fade_out
- wait: time:2

## Camera Defaults
- dialog_focus: true
- default_zoom: 5
- transition_speed: 0.5
```

## 注意事項
- Dialog の連番は1から連続で振る
- speaker が null の場合は地の文（narration）として扱う
- キャラクターの sprite が `[PLACEHOLDER]` の場合、仮の色付き四角で表示
- アニメーション設定は空トラックとして作成される。人間がTimeline上で設定する
- camera: auto は dialog_focus: true の場合のみ話者フォーカス。false なら stay と同じ
