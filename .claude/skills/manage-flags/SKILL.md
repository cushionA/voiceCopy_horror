---
name: manage-flags
description: Manage game flags (global & stage-local). Track, plan, and generate flag definitions for story progression, events, and gimmicks.
user-invocable: true
argument-hint: <list|plan|add|generate> [args]
---

# Manage Flags: $ARGUMENTS

ゲームフラグ（グローバル＆ステージローカル）の管理・計画・生成を補助する。

## 既存フラグシステムの構造

```
GameFlagRegistry (ScriptableObject)    — グローバルフラグ定義
├── FlagCategory (カテゴリ単位)
│   └── FlagEntry (名前 + bit位置 + 説明)
│
StageFlagRegistry (ScriptableObject)   — ステージローカルフラグ定義
├── stageId
└── FlagEntry[] (名前 + bit位置 + 説明)

FlagManager (MonoBehaviour)            — ランタイム状態管理
├── globalState: uint[] (カテゴリ別)
├── currentStageState: uint
├── allStageStates: Dictionary<string, uint>
└── SaveData → JSON永続化

FlagCondition (Serializable)           — 条件チェック（Inspector設定可能）
├── category + requiredFlags + excludedFlags
└── mode: All / Any
```

ビットパッキング: 1カテゴリ = 1 uint = 最大32フラグ

## サブコマンド

### `list` — 現在のフラグ定義を一覧表示

既存のフラグ定義ファイルを読み取り、全フラグを一覧表示する。

出力:
```
=== グローバルフラグ ===
[story] ストーリー進行
  bit0: intro_completed — オープニング完了
  bit1: boss1_defeated — ボス1撃破
  ...

[affinity] 好感度
  bit0: npc_ally_met — NPC仲間と会話済み
  ...

=== ステージローカルフラグ ===
[stage_1_1]
  bit0: chest_opened — 宝箱を開けた
  bit1: event_01_played — イベント01再生済み
  ...
```

### `plan` — フラグ計画を対話で作成

ユーザーと対話して、必要なフラグを洗い出す。

確認項目:
1. **ストーリー進行フラグ**: ボス撃破、エリア解放、キーアイテム入手
2. **イベントフラグ**: 会話イベント再生済み、選択肢結果
3. **収集フラグ**: 宝箱開封、アイテム取得、シークレット発見
4. **ギミックフラグ**: スイッチ操作済み、ドア解錠済み
5. **実績フラグ**: ノーダメージクリア、タイムアタック等

出力: `designs/flags/flag-plan.md`

```markdown
# フラグ計画

## グローバルフラグ
| カテゴリ | フラグ名 | bit | 説明 | 設定タイミング | 参照タイミング |
|----------|---------|-----|------|--------------|--------------|
| story | intro_completed | 0 | オープニング完了 | オープニングイベント終了時 | ステージ1開始条件 |

## ステージローカルフラグ
| ステージ | フラグ名 | bit | 説明 | 設定タイミング |
|----------|---------|-----|------|--------------|
| stage_1_1 | chest_01 | 0 | 宝箱A | 宝箱接触時 |
```

### `add` — フラグ定義を追加

既存のScriptableObjectに新しいフラグを追加する。

手順:
1. `designs/flags/flag-plan.md` から追加対象を確認
2. 既存フラグとのbit位置重複チェック（1カテゴリ最大32フラグ）
3. MCP経由でScriptableObjectを更新、またはコード生成で追加

```python
# MCP経由でScriptableObjectのプロパティを確認
manage_components(action="get", target="GameFlagRegistryのinstance_id")
```

### `generate` — フラグ関連コードの自動生成

フラグ計画から以下を生成:

1. **定数クラス** — フラグ名の文字列定数
```csharp
public static class FlagNames
{
    public static class Story
    {
        public const string IntroCompleted = "intro_completed";
        public const string Boss1Defeated = "boss1_defeated";
    }
    public static class Stage_1_1
    {
        public const string Chest01 = "chest_01";
        public const string Event01Played = "event_01_played";
    }
}
```

2. **EventZoneTriggerの設定値** — イベントゾーンに設定するフラグ情報の一覧

3. **フラグ依存グラフ** — フラグ間の依存関係（設定→参照の流れ）

## ルール

- **bit位置は手動管理しない**: planで自動採番し、重複を防ぐ
- **1カテゴリ32フラグ上限**: 超えたら新カテゴリに分割
- **ローカルフラグはステージ単位**: ステージをまたぐフラグはグローバルに昇格
- **命名規則**: `snake_case`、動詞+名詞（例: `boss1_defeated`, `chest_opened`）
- **フラグ計画はGDDと連動**: ストーリー進行はGDDのセクション構成と整合させる

## 出力先
- `designs/flags/flag-plan.md` — フラグ計画
- `designs/flags/flag-dependencies.md` — フラグ依存グラフ
- コード生成: `Assets/Scripts/Constants/FlagNames.cs`

## 関連ファイル
- `unity-bridge/Runtime/GameFlags.cs` — GameFlagRegistry, StageFlagRegistry, FlagEntry
- `unity-bridge/Runtime/FlagManager.cs` — FlagManager, SaveData
- `unity-bridge/Runtime/FlagCondition.cs` — FlagCondition, ConditionMode
- `unity-bridge/Runtime/EventZoneTrigger.cs` — イベントゾーンのフラグ連携
