---
name: design-systems
description: Design systems for a specific section of the GDD and break them down into implementable features registered in feature-db. Integrates the former plan-sprint skill.
user-invocable: true
argument-hint: <section-name or section-number>
model: opus
---

<!-- Wave 4 Phase 15 P15-T7 (Advisor Strategy): design-systems は Opus 固定。理由: GDD 解釈 + 既存機能との重複検出 + 設計判断が複合する非実行型アドバイザー領域 -->


# Design Systems: $ARGUMENTS

GDDの指定セクションに含まれるシステムの設計書を作成し、**実装可能な機能単位まで分解して feature-db に登録する**まで一気通貫で行う。

**旧 `/plan-sprint` の責務（既存機能との重複検出・機能分解・依存解決・feature-db登録・スプリント計画）は本スキルに統合された**（2026-04-24）。

## 前提
- `designs/game-design.md` が存在すること（`/design-game` で作成）
- `designs/dependency-graph.md` が存在すること
- `feature-log.db` が初期化済みであること

## 手順

### ステップ1: GDD読込と対象確認

`designs/game-design.md` から指定セクションのシステム一覧を取得し、設計対象を確認する。

### ステップ2: 既存機能の棚卸し（重複検出）

**新しいシステム/機能を登録する前に、既存機能との重複を必ずチェックする。**

```bash
python tools/feature-db.py list
python tools/feature-db.py summary
```

チェック項目:
- **完全重複**: 同じ機能が既に存在する → 新規登録しない
- **拡張で対応可能**: 既存機能に少し手を加えれば実現できる → 「拡張」として設計する
- **依存先が既に完成済み**: 依存リストから除外

結果をユーザーに報告:
```
## 既存機能との照合結果
- InputSystem ✅ 既に完成済み → スキップ
- PlayerMovement_Dash → PlayerMovement を拡張して対応可能
- EnemyAI_Chase → 新規作成が必要
```

### ステップ3: 共通設計の抽出

セクション内の複数システムにまたがる共通パターンを抽出する。

確認ポイント:
- **共通インターフェース**: 複数システムが実装すべき共通契約（IDamageable, IInteractable等）
- **共通基盤クラス**: 似た処理パターンの抽象化（EntityBase, StateMachineBase等）
- **共有データ**: 複数システムが参照するScriptableObject
- **イベント定義**: システム間通信のイベント一覧
- **定数・Enum**: 共通で使う列挙型や定数

→ 共通要素は `designs/systems/Common_[セクション名].md` に記載

### ステップ4: asmdef設計

プロジェクトのアセンブリ構成を設計・更新する。

```markdown
## Assembly Definitions

| asmdef | 含むスクリプト | 参照先asmdef | 用途 |
|--------|-------------|-------------|------|
| Game.Runtime | Assets/Scripts/ | Unity.InputSystem | ランタイムコード |
| Game.Editor | Assets/Editor/ | Game.Runtime | Editor拡張 |
| Game.Tests.EditMode | Assets/Tests/EditMode/ | Game.Runtime | EditModeテスト |
| Game.Tests.PlayMode | Assets/Tests/PlayMode/ | Game.Runtime | PlayModeテスト |
```

- 新しいシステムが既存asmdefに収まるか確認
- 大規模システムは独立asmdefを検討（循環参照を避ける）
- テスト用asmdefの参照設定を確認

### ステップ5: システム設計書作成

各システムについて `designs/systems/[システム名].md` を作成する。

```markdown
# System: [システム名]
Section: [所属セクション名]

## 責務
[このシステムが何をするか、1-2文]

## 依存
- 入力: [このシステムが必要とするもの]
- 出力: [このシステムが提供するもの]

## コンポーネント構成
| コンポーネント | 責務 | MonoBehaviour? |
|--------------|------|---------------|
| [名前] | [役割] | Yes/No |

## インタフェース
[他システムとの接続点。イベント、publicメソッド、ScriptableObject等]

## データフロー
[入力 → 処理 → 出力 の流れ]

## 機能分解
| 機能名 | 説明 | テスト種別 | 優先度 | カテゴリ |
|--------|------|-----------|--------|---------|
| [名前] | [何をするか] | EditMode/PlayMode | High/Medium/Low | system/content |

## 設計メモ
[判断の理由、代替案、注意点]
```

### ステップ6: 依存グラフ更新

`designs/dependency-graph.md` にこのセクションのシステム依存関係を追記する。

```markdown
# System Dependency Graph

## Section 1: [セクション名]
### 実装順序
1. [依存なし] InputSystem
2. [依存なし] EventBus
3. [← InputSystem] PlayerMovement
4. [← PlayerMovement, EventBus] CombatSystem

### システム間通信
| 発信 | → | 受信 | 方式 | 内容 |
|------|---|------|------|------|
| CombatSystem | → | UISystem | C# event | ダメージ表示 |
```

### ステップ7: アセット仕様の拡充

システム設計で具体値が確定したら `designs/asset-spec.json` を更新する。

- PlayerMovementシステム設計時 → `world.maxJumpHeight`, `world.maxJumpWidth` を設定
- スプライトカテゴリが明確になったら `sprites.categories` に追加
- まだ不明な項目はnullのまま残す

### ステップ8: アーキテクチャルール更新

設計から導出されるプロジェクト固有ルールを `.claude/rules/architecture.md` に追記する。

### ステップ9: 機能のカテゴリ分類（旧 plan-sprint ステップ3）

ステップ5 で抽出した各機能を以下の基準で分類する。

**システム系 (system)**:
- 入力処理、移動・物理、カメラ、衝突判定
- HP・ダメージ等のコアメカニクス
- UI基盤（HUD、メニューフレームワーク）
- データ管理（セーブ、フラグ、状態管理）
- オーディオ基盤、エフェクト基盤
- 判定基準: 他の機能から「使われる」側。ゲーム内容に依存しない汎用処理

**コンテンツ系 (content)**:
- ステージ構成、敵種・配置パターン
- アイテム・報酬設計、イベント・演出
- レベルデザイン固有のパラメータ調整
- 判定基準: システムを「使う」側。ゲーム内容に固有の具体的データ・設定

### ステップ10: 依存解決と実装順序決定（旧 plan-sprint ステップ4）

`dependency-graph.md` を参照し、実装順序を決定する。

```
実装順序の決定ルール:
- システム系機能をコンテンツ系機能より先に配置
- 各カテゴリ内では:
  - 依存なしの機能を先に
  - 同一システム内は優先度順
  - システム間依存がある場合は依存先を先に
```

### ステップ11: feature-db登録（旧 plan-sprint ステップ5）

各機能を依存順でDBに登録する。

```bash
python tools/feature-db.py add "SystemName_FeatureName" \
  --tests "Assets/Tests/EditMode/FeatureTests.cs" \
  --impl "Assets/Scripts/System/Feature.cs" \
  --category system \
  --section section-1 \
  --depends "DependencyFeature1" "DependencyFeature2"
```

### ステップ12: スプリント計画出力（旧 plan-sprint ステップ6）

`designs/sprints/[セクション名].md` に実装計画を記録する。

```markdown
# Sprint: [セクション名]

## 完了条件
[このセクションが完了した時に何が動くか]

## 既存機能の活用
| 既存機能 | 対応方法 | 備考 |
|----------|---------|------|
| [機能名] | スキップ/拡張 | [理由] |

## 実装順序 — システム系
| # | 機能名 | システム | カテゴリ | 依存 | 状態 |
|---|--------|---------|----------|------|------|
| 1 | InputSystem_Setup | Input | system | なし | pending |
| 2 | PlayerMovement_Horizontal | Player | system | Input | pending |

## 実装順序 — コンテンツ系
| # | 機能名 | システム | カテゴリ | 依存 | 状態 |
|---|--------|---------|----------|------|------|
| 3 | EnemyTypes_Slime | Enemy | content | PlayerMovement | pending |

## 動作確認手順
[全機能完了後にどうやってセクション完了を確認するか]
```

### ステップ13: GDD更新とユーザー確認

`designs/game-design.md` のセクション状態を「計画済み」に更新し、以下をユーザーに確認する:

- カテゴリ分類は正しいか
- 実装順序に問題はないか
- 既存機能の活用方針は妥当か
- 不要な機能はないか

### ステップ14: pipeline-state.json 更新

`/build-pipeline` 経由で呼ばれている場合、`designs/pipeline-state.json` を以下のように更新する:

```python
state["phase"] = "implementation"
state["currentSection"] = <section 番号>
state["pendingFeatures"] = [feature-db から取得した未実装機能名リスト]
state["lastAction"] = f"section-{N} の設計・計画完了"
state["lastUpdated"] = <ISO8601 UTC>
```

単独実行時はスキップしてよい。

## ルール
- **指定セクションのシステム/機能のみ**を対象とする。他セクションには触れない
- 1システム = 1設計書、1機能 = `/create-feature` で実装可能な粒度（テスト5個以内が目安）
- システム間の直接参照は禁止。イベントまたはインタフェース経由
- 前セクションで作成済みのシステムは依存先として参照可能
- ScriptableObjectをデータ共有・設定値管理に活用する
- **既存機能の重複作成/登録は絶対に避ける**
- 機能名は `[システム名]_[機能名]` フォーマット
- セクションの「完了条件」と「動作確認手順」を必ず定義する

## 出力先
- `designs/systems/[システム名].md`（システム別）
- `designs/systems/Common_[セクション名].md`（共通設計）
- `designs/dependency-graph.md`（追記）
- `.claude/rules/architecture.md`（追記）
- `designs/game-design.md`（セクション状態更新）
- `designs/asset-spec.json`（更新）
- `designs/sprints/[セクション名].md`（スプリント計画）
- `feature-log.db`（機能登録）
- `designs/pipeline-state.json`（build-pipeline 経由時のみ）

## 次のステップ
スプリント計画の先頭から実装開始:
```
/create-feature [最初の機能名]
```
