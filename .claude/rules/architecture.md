---
description: Game architecture rules based on SisterGame design docs (Architect/). Updated by /design-systems.
paths:
  - "Assets/MyAsset/**/*.cs"
  - "Assets/Tests/**/*.cs"
---

# アーキテクチャルール

## コア設計原則（Architect/00_アーキテクチャ概要.md 準拠）

### SoA（Structure of Arrays）+ SourceGenerator
- キャラクターデータをフィールドごとの配列で管理し、キャッシュ効率を最大化
- SourceGeneratorにより情報クラスに属性を付けるだけでSoAコンテナ・アクセサが自動生成
- 手書きボイラープレートを排除する

### GameManager シングルトン（中央ハブ）
- GameManagerが全マネージャーとデータコンテナへの唯一の参照点
- すべてのゲームシステムは `GameManager` 経由でアクセスする
- 散在するシングルトンを排除し、依存関係を一元管理する

### ハッシュベースデータアクセス（GetComponent排除）
- GameObjectのhashCodeをキーとして `GameManager.Data` 経由でO(1)データアクセス
- GetComponentによる毎フレーム検索コストを完全に排除
- `GetComponent` / `FindObjectOfType` はAwake/Start以外で使用禁止

### コンポーネント拡張（Abilityシステム）
- ベースキャラクターは最小限の責務のみ持つ
- ジャンプ・ダッシュ等はAbilityコンポーネントとして追加・組み合わせ可能
- 新しい行動の追加が既存コードに影響しない（IAbility インターフェース）

### データ駆動（ScriptableObject）
- ゲームバランスに関わる値はすべてScriptableObject上の情報クラスで定義
- ハードコーディング禁止。Inspectorから調整可能にする

## 入力
- Input SystemパッケージのPlayerInputコンポーネントを使用
- 入力の受け取りは専用のInputHandlerクラスに集約
- ゲームロジックは入力ソースに依存しない（テスト時にモック可能）

## 状態管理
- ゲーム全体の状態（メニュー、プレイ中、ポーズ等）はステートマシンで管理
- 各状態はクラスとして分離（State パターン）

## レイヤー構成
```
[Input Layer]      — 入力受付、イベント発行
    ↓ events
[Game Logic Layer] — メカニクス、ルール、状態管理（GameManager中央ハブ）
    ↓ data (SoAコンテナ経由)
[Presentation Layer] — 表示、アニメーション、エフェクト、サウンド
```
- 上位レイヤーは下位を知らない
- 下位レイヤーはイベント購読で上位の変化を受け取る

## コンポーネント粒度
- 1コンポーネント = 1つの明確な責務
- 「このコンポーネントは何をするか」を1文で説明できること
- 説明に「〜と〜」が含まれる場合は分割を検討

## Section 1 固有ルール（/design-systems section-1 で追記）

### 装備システム
- 装備スロット: 武器(右手) / 盾(左手) / コア(1スロット)
- GripMode: OneHanded（盾併用） / TwoHanded（盾無効化）
- スキル優先: TwoHanded or shield.weaponArts → 武器スキル、else → 盾スキル
- 片手持ち盾スキルの攻撃は盾の攻撃力を参照する
- 装備変更時に全ステータス再計算（攻撃力、防御力、AbilityFlag、重量比率）

### AbilityFlag
- 拡張移動（壁蹴り等）はAbilityFlagで管理
- フラグは装備（武器+盾+コア+コンビネーション効果）から合算
- Section1ではフラグシステムのみ実装、壁蹴り装備はSection2

### 重量システム
- weightRatio = totalEquipWeight / maxWeightCapacity
- AnimationCurveで性能変動（回避速度、スタミナ回復、攻撃速度、回避距離）
- 過負荷（1.0超過）も可能だが大ペナルティ

### 戦闘
- ダメージ式: 各属性チャネルごとに (atk² × motionValue) / (atk + def) を計算し合算
- isAutoChain: 入力なしで自動的に次モーションへ遷移するフラグ
- maxHitCount: モーションごとの最大ヒット数
- justGuardResistance: ジャストガード時のアーマー削り軽減 (0-100)
- AttackFeature.JustGuardImmune: ジャストガード不可攻撃

### 属性システム（7属性統一）
- Element = Slash(斬撃)/Strike(打撃)/Pierce(刺突)/Fire(炎)/Thunder(雷)/Light(聖)/Dark(闇)
- [Flags] byte で複合属性を表現可能（例: 炎+斬撃の剣）
- WeaponPhysicalType は廃止。物理タイプ（斬撃/打撃/刺突）もElementに統合
- ElementalStatus: 7属性別のint値（slash, strike, pierce, fire, thunder, light, dark）
- CombatStats: ElementalStatus attack / ElementalStatus defense（属性別攻防）
- ダメージ計算は7属性チャネル別に (atk² × motionValue) / (atk + def) を算出し合算
- GuardStats: 属性別カット率（slashCut, strikeCut, pierceCut, fireCut, thunderCut, lightCut, darkCut）

### 能力値スケーリング
- 武器は STR/DEX/INT の AnimationCurve を持つ
- STR → 斬撃・聖、DEX → 刺突・闇、INT → 炎・雷
- レベルアップで能力値ポイントを振り分け（セーブポイントで）

### Assembly構成
- Game.Core ← Game.Character ← Game.Combat / Game.AI / Game.World / Game.Economy ← Game.UI
- 循環参照禁止。上位は下位を参照しない
- システム間通信はGameManager.Eventsの C# event を使用

### レベルストリーミング
- エリア境界にTrigger配置 → Additive Scene Loading
- GameScene（永続） + エリアシーン（Additive）構成
- プレイヤー・仲間・UIは永続シーンに属する

## Section 2 固有ルール（/design-systems section-2 で追記）

### 統一行動システム（ActionSlot）
- **全行動をActionSlotで統一**。旧ActionData（ActState+param）は廃止
- 敵AIも仲間AIも同じActionSlot/AIMode/ActionExecutorで動作
- 実行パターン5分類（ActionExecType）:
  - **Attack**: AttackMotionData参照、ヒットボックス・motionValue・コンボ管理
  - **Cast**: 詠唱→発動→ProjectileSystem（魔法、チャージ攻撃、武器スキル飛翔体）
  - **Instant**: アニメ1回再生（ワープ、回避、アイテム使用、環境物利用）
  - **Sustained**: 開始→Tick→終了条件（移動、ガード、追従、挟撃等）。reactionTriggerでカウンター系
  - **Broadcast**: 他キャラAI状態を操作（ターゲット指示、集合、挑発等）
- ActionBase基底クラス: 共通フィールド（mpCost, staminaCost, cooldown）+ CanExecute/Execute/Interrupt/Tick
- ActionExecutorはDictionary<ActionExecType, ActionBase>（switch文排除）

### AI判定システム（Architect/07_AI判定システム再設計.md 準拠）
- 3層判定: ターゲット切替 → 行動切替 → デフォルト行動（棒立ち防止）
- AIConditionType(12種) + CompareOp(6種) で全条件を統一表現
- AIRule.conditions は AND 結合、AIRule[] は優先度順（先勝ち = OR結合）
- ヘイトシステム廃止 → DamageScore（累積ダメージ×倍率+時間減衰）で代替
- TargetFilter のビット演算でCharacterFlagsを高速フィルタリング

### AIBrain
- AIBrainはMonoBehaviour。3層判定のEvaluate()を毎判定間隔で実行
- ConditionEvaluator, TargetSelector, ActionExecutor はピュアロジック（MonoBehaviour非依存）
- CompanionControllerはAIBrainを継承（モード手動切替+自動切替対応）

### 仲間AIカスタム（AIRuleBuilder）
- CompanionAIConfig: 最大4モード + モード自動切替条件 + ショートカット手動切替
- ActionSlotの行動タイプは探索報酬で段階的に解放（メトロイドヴァニアの新能力=新戦術）
- システムプリセット入手 = 完成済みパターン + 新ActionType解放（二重報酬）
- 手動切替が最優先、タイムアウトで自動切替に復帰

### 仲間MPシステム
- 仲間はHPを使用しない。被ダメージはバリア（盾判定 = ダメージ計算式準拠）でMP消費
- MP 0 → 消滅（ワープ退場）。死亡ではなく一時退場
- currentMP が maxMP の50%に回復したら復帰
- 消滅中: 連携使用不可、MP回復倍率 1.3x（CompanionMpSettings.vanishRecoveryMultiplier で設定可変）
- **二重MPプール**: currentMP は reserveMP から自然補充。reserveMP はアイテム/チェックポイントのみ回復
- **MP回復行動**: SustainedAction.MpRecover。停止してMP加速回復。怯みで中断、再開可

### 行動特殊効果（ActionEffect）
- 全行動（攻撃・回避・ガード・スキル・魔法）に「開始時間+持続時間」の特殊効果を複数設定可能
- ActionEffectType: Armor / SuperArmor / Invincible / DamageReduction / GuardPoint / GuardAttack / KnockbackImmunity
- 設定箇所: AttackInfo.motionInfo.actionEffects, AttackMotionData.actionEffects, AbilityData
- Armor は合算、DamageReduction は最大値、その他は OR
- 旧 DashAbility の _invincibleStart/_invincibleEnd は ActionEffect に統合
- GuardAttack: ガード中にブレイク不可（GuardBreak→Guardedに昇格）
- KnockbackImmunity: 吹き飛ばし→怯みに変換。一部の敵は永続、プレイヤーはコア装備で付与

### アーマーシステム
- 二層構造: ベースアーマー（CharacterInfo.maxArmor） + 行動アーマー（ActionEffect.Armor）
- 被弾時は行動アーマーから優先消費 → 残りがベースアーマーへ
- 両方 0 でアーマーブレイク（1.3倍ダメージボーナス）
- ベースアーマー自然回復: armorRecoveryDelay 経過後に armorRecoveryRate/秒で回復
- 行動アーマーは回復しない（ActionEffect の有効区間のみ存在）

### 被弾リアクションシステム
- HitReactionLogic（static class）がアーマー・特殊効果・攻撃属性からリアクション判定
- HitReaction: None / Flinch / Knockback / GuardBreak
- アーマー > 0 → 怯まない、アーマー = 0 → Flinch、吹き飛ばし力あり → Knockback
- ヒットスタン中（Flinch/GuardBroken/Stunned）に吹き飛ばし → アーマー無視でKnockback
- SuperArmor → 絶対怯まない（ヒットスタン中の吹き飛ばしも無効）
- 吹き飛ばし判定: knockbackForce.sqrMagnitude > 0.01（方向違いで打ち上げも包含）

### ガード方向
- GuardStats.guardDirection: Front / Back / Both
- 攻撃方向とガード方向不一致 → GuardResult.NoGuard
- ジャストガード成功時: スタミナ+15、アーマー+10 回復

### 状況ダメージボーナス
- SituationalBonusLogic: Counter(1.3x)/Backstab(1.25x)/StaggerHit(1.2x)
- 重複なし: 複数条件満たす場合は最大倍率のみ適用
- ガード成功時は適用しない（NoGuard/GuardBreak時のみ）
- DamageResult.situationalBonus にUI表示用の種別を記録

### 連携ボタンスキル（CoopAction）
- 連携 = 仲間への指示スキル。CoopActionBase継承で多様な連携を追加
- コンボ対応: 連打で最大N回連続発動（MP消費は初回のみ）
- 各コンボ段ごとにAITargetSelectでターゲット条件を個別設定
- 行動割り込み: 怯み中でなければ仲間の現在行動を中断→連携終了後に再開
- クールタイム消化済み→MP無料、未消化→MP消費（タイマーは変えない）

### 飛翔体システム（ProjectileSystem）
- 全飛翔体の共通基盤（魔法弾、スキル衝撃波、チャージ弾、敵遠距離攻撃）
- 弾丸はcasterHashのみ記録、命中時にコンテナから最新ステータス取得
- キャスター死亡→弾丸自動消滅

### 敵AI
- 行動パターンはAIInfo（ScriptableObject）のAIMode配列（ActionSlot[]含む）で定義
- DamageScoreTrackerで「最もダメージを与えてくる相手」をターゲットに選択
- スポーンはEnemySpawner（activateRange外は非アクティブ、休息でリスポーン）

### ゲートシステム
- GateType: Clear / Ability / Key / Elemental の4種
- 永続ゲート（ボスクリア等）はグローバルフラグ、一時ゲートはマップローカルフラグ
- ISaveable実装でSaveSystemと連携

## Section 3 固有ルール（/design-systems section-3 で追記）

### ボスシステム
- BossControllerはAIBrainをコンポジションで保持（継承ではない）
- フェーズ遷移: BossPhaseManagerがHP閾値/タイマー/行動回数で判定
- フェーズ遷移時にAIBrainのモード配列を差し替え（AIBrainコード変更なし）
- フェーズ遷移中は無敵時間（既存DamageSystemのinvincibleフラグ）
- アリーナロック: BossArenaManagerが出入口コライダー管理
- 撃破後: ClearGate永続開放 + DropTable報酬

### 召喚システム
- MagicType.Summon で召喚魔法を定義（既存MagicCasterのCast()フローに乗る）
- 召喚枠: 最大2枠（PartyManager.k_MaxSummonSlots）、パーティ最大4人
- 枠満杯時は最古の召喚獣を解除して入れ替え
- 召喚獣はSoAコンテナに通常キャラクターとして登録
- 追従ロジックはFollowBehaviorを再利用（コンポジション）
- SummonType: Combat（戦闘用）, Utility（足場/照明）, Decoy（囮/ヘイト集め）

### 混乱魔術
- 既存蓄積型状態異常モデルに統合（StatusEffectManager.AccumulateEffect）
- 蓄積閾値超過→CharacterFlagsの陣営フラグ反転（Faction.Enemy → Faction.Ally）
- AIの行動パターンは変更なし。TargetFilterの陣営条件だけ反転
- 混乱敵はパーティ枠外。同時最大3体（PartyManager.k_MaxConfusedEnemies）
- ボスは混乱耐性1.0（完全耐性）
- confusionBreakDamage: 味方誤爆で混乱解除

### 属性ゲート（環境パズル）
- GateTypeにElemental追加。ElementalRequirementで7属性対応
- 属性攻撃のヒット検知は専用（IDamageableではなく環境オブジェクトレイヤー）
- multiHitRequired対応（弱点を数回殴る等のギミック）
- 仲間の属性攻撃でも開放可能（連携パズル）

### バックトラック報酬
- AbilityFlag獲得時にBacktrackRewardManagerが全報酬を再評価
- 能力獲得前はマップマーカー非表示（ネタバレ防止）
- AbilityOrbを回収→新能力→更にバックトラック報酬が解放される連鎖
- BacktrackRewardTableはエリアごとのScriptableObject
- ISaveable実装で回収状態を永続化

### パーティ管理
- PartyManager静的クラスで枠管理
- 最大パーティ: 4人（プレイヤー1 + 常駐仲間1 + 召喚最大2）
- 混乱敵はパーティ枠外（別カウント、最大3体）

## Section 4 固有ルール（/design-systems section-4 で追記）

### チャレンジモード
- ChallengeRunner は純ロジック（MonoBehaviour非依存）。状態管理・タイマー・勝敗判定
- ボスラッシュは BossControllerLogic.StartEncounter() を順番に呼ぶ（新戦闘ロジック不要）
- スコア計算は ChallengeScoreCalculator（static class）に集約
- ChallengeManager は ISaveable でアンロック状態を永続化
- チャレンジイベントは GameEvents の R3 Subject パターンに統一

### AIテンプレート
- 既存 CompanionAIConfig（Section 2）をそのまま内包する AITemplateData で管理
- AITemplateManager は PresetManager を内部活用（重複構造を作らない）
- ImportExport は YAGNI で除外。将来のオンライン共有時に別途設計
- テンプレート適用後は GameEvents.FireCustomRulesChanged() で既存AI更新フローに乗せる
- Revert は直前1回分のみ保持（スタックにしない）

### リーダーボード
- LeaderboardManager は ISaveable で記録永続化
- 新記録時は GameEvents.FireNewRecord() でUI通知
- ローカルのみ（オンラインランキングは対象外）

---

# データ設計

> Sources: nice-wolf-studio/unity-claude-skills (MIT) — unity-data-driven / unity-foundations

## ゲーム設定データの保存方式選択

| 方式 | 用途 | 特徴 |
|---|---|---|
| **ScriptableObject (デフォルト)** | 敵ステータス、アイテム表、ロケール設定等 | Designer が Inspector で編集可、type-safe、refactor-safe、YAML として version control 可 |
| **JSON / CSV** | スプレッドシート連携、modding、bulk 編集が必要な場合 | 外部ツール生成、ランタイム読込 |
| **埋め込み定数** | 真に固定の値（物理定数、プロトコルバージョン） | `static readonly` / `const` |

SisterGame の方針:
- 敵 / アイテム / ステージ設定は **ScriptableObject 第一候補**
- バランスシート由来の bulk データは `/create-balance-sheet` で CSV/Excel → ScriptableObject 変換
- 動的 / オンラインデータは Easy Save 3 経由

## ScriptableObject 設計: 継承 vs 構成

### 継承パターン
親 SO を抽象化、サブタイプで具体化:

```csharp
public abstract class EnemyConfig : ScriptableObject
{
    [Min(1)] public int maxHealth = 100;
    [Range(0f, 20f)] public float moveSpeed = 5f;
}

[CreateAssetMenu(menuName = "Game/Enemies/Melee")]
public class MeleeEnemyConfig : EnemyConfig
{
    [Range(0f, 50f)] public float meleeDamage = 15f;
}
```

注意: 継承では基底クラスのフィールドが**全て表示**される。`[HideInInspector]` か Custom Editor で制御。

### 構成パターン（推奨）
`[Serializable]` struct を `[SerializeField]` で組み合わせる:

```csharp
[System.Serializable]
public struct MovementConfig { public float speed; public bool canFly; }

[System.Serializable]
public struct AttackConfig { public AttackType type; public float damage; public float cooldown; }

[CreateAssetMenu(menuName = "Game/Enemy")]
public class EnemyConfig : ScriptableObject
{
    [Header("Movement")] public MovementConfig movement;
    [Header("Combat")]   public AttackConfig attack;
    [Min(1)] public int maxHealth = 100;
}
```

**SisterGame は構成パターンを推奨**:
- 機能の組み合わせを柔軟に変えられる（飛ぶ／飛ばない、近接／遠隔の組み合わせ）
- struct 単位で他の SO に再利用しやすい
- 継承の「2-3 段以上で分かりにくくなる」問題を回避

## Inspector 属性早見表

| 属性 | 用途 |
|---|---|
| `[Header("Section")]` | セクションラベル |
| `[Tooltip("Help")]` | hover ヒント（非自明な場面に必須）|
| `[Range(min, max)]` | スライダー（範囲が決まっている数値）|
| `[Min(value)]` | 下限クランプ（負値禁止フィールド）|
| `[TextArea(min, max)]` | 複数行テキスト |
| `[Space(pixels)]` | 縦スペース |
| `[HideInInspector]` | Inspector から隠す |
| `[FormerlySerializedAs("oldName")]` | リネーム時の旧名指定（既存アセット保持）|
| `[ColorUsage(alpha, hdr)]` | カラーピッカー設定 |
| `[CreateAssetMenu(menuName = ...)]` | Right click → Create メニュー登録 |

## データバージョニング

### 加算的変更（フィールド追加 / 削除）
Unity が serialize を吸収する範囲なので**特別な対応不要**:
- フィールド追加 → 既存アセットはデフォルト値を持つ
- フィールド削除 → 旧データは silent drop

### 破壊的変更（リネーム / 構造変更）
`[FormerlySerializedAs("oldName")]` で既存 SO アセットを保持:

```csharp
using UnityEngine.Serialization;

public class EnemyConfig : ScriptableObject
{
    [FormerlySerializedAs("hp")]
    [Min(1)] public int maxHealth = 100;
}
```

**注意**: `[FormerlySerializedAs]` は **Unity serialization のみ**（Inspector / .asset / prefab）。**JSON や独自 serialization では機能しない**。JSON 移行時は raw JSON を解析してから deserialize する。

### バージョン番号 + マイグレータ（JSON / Easy Save 3）
SO 以外の永続データは明示的なバージョン管理:

```csharp
[System.Serializable]
public class PlayerData
{
    public int version = 2; // 現在のスキーマバージョン
    public string playerName;
    public float[] position; // v2: Vector3 から float[] に変更（JSON 互換）

    public static PlayerData MigrateFromV1(string json) { /* v1→v2 変換 */ }
}
```

SisterGame は Easy Save 3 を使うため、保存形式の変更時は ES3 の Type Reference や明示マイグレータ関数を使う。

## ランタイム制約（重要）

ScriptableObject はプレイヤービルドでは **read-only** に近い扱い:
- Editor プレイ中の変更 → ディスクに**保存される**（注意: 誤って変更が保存される）
- ビルドでの変更 → アプリ終了時に**失われる**（永続化されない）

→ **保存対象データを SO に置かない**。`PlayerData` 等のセーブデータは ScriptableObject ではなく **Easy Save 3 経由のクラスインスタンス**として扱う。

## Transform / GameObject の落とし穴

### 非均等スケール禁止
`(2, 4, 2)` のような非均等スケールは:
- Collider / Light / AudioSource の挙動を歪める
- 子オブジェクトの rotated 表示が skew する
- Instantiate のパフォーマンス劣化

**アセット側で実寸モデリング**を徹底する。やむを得ず必要な場合は当該 GameObject を「孫」階層に逃がし、親で位置・回転、孫でスケールに分離。

### 親の位置を `(0,0,0)` にする
スポーン基準点・コンテナとして使う親オブジェクトは原点配置。親の位置がずれていると、子の local 座標が想定と一致せずバグの原因。

## 詳細リファレンス

- `unity-data-driven` 完全版: `@.claude/refs/external/nice-wolf-studio/unity-data-driven/SKILL.md`
- `unity-foundations` 完全版: `@.claude/refs/external/nice-wolf-studio/unity-foundations/SKILL.md`
