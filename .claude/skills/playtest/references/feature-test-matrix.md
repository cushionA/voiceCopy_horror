# 機能-テスト組み合わせマトリクス

feature-dbの機能カテゴリに対して、どのテスト種別を適用するかを定義する。
SCENE_DESIGN / AUTO_INPUT_DESIGN / batch-test はこのマトリクスを参照してテスト計画を立てる。

## 凡例
- **◎** 必須 — この機能カテゴリでは必ず実行する
- **○** 推奨 — 時間があれば実行する、Failでもcomplete可能
- **△** 任意 — 特別な理由がある場合のみ

## マトリクス

| 機能カテゴリ | T1 Logic | T2 AutoInput | T3 Snapshot | T4 Animator | T5 Perf | T6 Preflight | T7 Dynamic | T8 UI | T9 Screenshot |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **移動系** (Movement, Jump, Sprint) | ◎ | ◎ | ○ | ○ | △ | ◎ | ○ | △ | △ |
| **攻撃系** (LightAttack, HeavyAttack, Combo) | ◎ | ◎ | ◎ | ○ | △ | ◎ | ◎ | △ | △ |
| **防御系** (Guard, Dodge, Parry) | ◎ | ◎ | ◎ | ○ | △ | ◎ | ○ | △ | △ |
| **リソース系** (HP, MP, Stamina, Armor) | ◎ | ○ | ◎ | △ | △ | ○ | ○ | ◎ | △ |
| **AI系** (EnemyAI, CompanionAI) | ◎ | △ | ◎ | ○ | ○ | ◎ | ◎ | △ | △ |
| **チャージ/特殊入力** (Charge, WeaponSwitch) | ◎ | ◎ | ○ | ○ | △ | ○ | △ | △ | △ |
| **UI/HUD系** (HPBar, DamagePopup, Menu) | △ | △ | ○ | △ | △ | ○ | △ | ◎ | ◎ |
| **物理/衝突系** (Collision, Hitbox, Layer) | ○ | ○ | ◎ | △ | △ | ◎ | ◎ | △ | △ |
| **イベント系** (EventScene, Dialog) | △ | △ | ○ | △ | △ | ○ | △ | ◎ | ◎ |
| **レベル/ステージ系** (LevelStreaming, Spawn) | ○ | △ | ◎ | △ | ◎ | ◎ | ○ | △ | ○ |

## 適用ルール

### 判定基準
1. **◎（必須）が1つでもFailなら feature-db ステータスを `in_progress` に設定**
2. **○（推奨）はFailでもcomplete可能だが、レポートに警告として記載**
3. **△（任意）は時間が許す場合のみ実行**
4. **T6（プリフライト）は全テストの前に実行し、Failなら他テストを中断**

### カテゴリ判定方法
feature-dbの機能名からカテゴリを推定する:
- 機能名に `Movement`, `Jump`, `Sprint`, `Walk`, `Run` → 移動系
- 機能名に `Attack`, `Combat`, `Combo`, `Slash`, `Hit` → 攻撃系
- 機能名に `Guard`, `Dodge`, `Parry`, `Block`, `Evade` → 防御系
- 機能名に `HP`, `MP`, `Stamina`, `Health`, `Mana`, `Armor` → リソース系
- 機能名に `AI`, `Enemy`, `Companion`, `Brain` → AI系
- 機能名に `Charge`, `Weapon`, `Switch` → チャージ/特殊入力
- 機能名に `UI`, `HUD`, `Bar`, `Popup`, `Menu` → UI/HUD系
- 機能名に `Physics`, `Collision`, `Hitbox`, `Layer`, `Trigger` → 物理/衝突系
- 機能名に `Event`, `Dialog`, `Cutscene`, `Story` → イベント系
- 機能名に `Level`, `Stage`, `Spawn`, `Stream`, `Load` → レベル/ステージ系
- 複数カテゴリに該当する場合: 全該当カテゴリの◎を合算
- **該当なしの場合（フォールバック）**:
  1. feature-db get で実装ファイルを確認し、コード内容からカテゴリを推定
  2. それでも判定不能なら **T1(Logic) + T6(Preflight) を必須、他は全て○推奨** として扱う
  3. レポートに「カテゴリ未判定: 機能名」として記載し、ユーザーにカテゴリ追加を提案

### キーワード補完（判定精度向上）
よくある機能名とカテゴリの追加マッピング:
- `Projectile`, `Bullet`, `Arrow` → 攻撃系
- `Spawner`, `Wave`, `Generator` → レベル/ステージ系
- `Dash` → 移動系
- `Inventory`, `Item`, `Equip`, `Pickup` → アイテム系（→ リソース系に準ずる）
- `Camera`, `Shake`, `Follow` → 物理/衝突系に準ずる
- `Animation`, `Anim`, `Motion` → 移動系 or 攻撃系（実装内容で判断）
- `Save`, `Load`, `Persist` → イベント系に準ずる
- `Sound`, `Audio`, `BGM`, `SFX` → UI/HUD系に準ずる（再生制御の検証）

### バッチテスト時のグルーピング
複数機能を同時テストする場合、テスト種別ごとにグルーピングして実行効率を上げる:
1. **T6 Preflight**: 全機能一括で1回（EditMode）
2. **T1 Logic**: 全機能のEditModeテスト一括（TestRunner.RunEditMode）
3. **T4 Animator**: Animator検証一括（PlayMode 1セッション目）
4. **PlayMode統合**: T2 + T3 + T5 + T7 + T8 + T9 を1セッションにまとめる
5. **レポート集約**: 機能×テストタイプのマトリクスで結果を整理

詳細は `batch-test.md` を参照。
