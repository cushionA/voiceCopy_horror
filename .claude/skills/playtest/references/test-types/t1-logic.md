# T1: EditModeロジックテスト — ロジック単体検証の専門家

## 役割
機能の実装コードを読み、純粋ロジックの正しさを検証するEditModeテストを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能名と実装ファイルパス
- public API一覧（メソッドシグネチャ）
- 状態変数（フィールド、プロパティ）
- 依存する既存ユーティリティ（HpArmorLogic, DamageCalculator等）

### 設計手順
1. **公開メソッドを列挙**: 実装ファイルのpublicメソッドを全て洗い出す
2. **分岐条件を抽出**: 各メソッド内のif/switch/三項演算子から条件を列挙
3. **境界値を特定**: 各条件の境界（0, 負数, 最大値, null, 空コレクション）
4. **ユーティリティ経由の効果を確認**: メソッドが呼ぶ既存ユーティリティの効果まで検証対象にする
   - 例: `ApplyDamage` がHpArmorLogicを呼ぶなら「HP >= 0 クランプ」「アーマー消費」も検証
5. **状態遷移パスを列挙**: 状態を持つクラスなら A→B, B→A, A→B→A の遷移を設計
6. **副作用を列挙**: イベント発火、他コンポーネントへの通知、SoAデータ書き込み

### 設計品質基準
- 全publicメソッドに最低1テスト
- 全分岐条件に正常系+異常系
- 境界値テスト必須: 0, 負数, 最大値, null
- 既存ユーティリティ経由の効果が末端まで検証されている
- 連続操作（A→B→A）で状態が壊れない検証がある
- イベント購読/解除の対称性テストがある（該当時）

## 実行手段
- `/unicli`: `TestRunner.RunEditMode`
- フィルタ付き: `TestRunner.RunEditMode --filter "機能名"`

## テスト命名
- `[機能名]_[条件]_[期待結果]`
- 例: `HpArmorLogic_WhenDamageExceedsHp_ShouldClampToZero`

## テストファイル配置
- `Tests/EditMode/[機能名]Tests.cs`
- 結合テスト: `Tests/EditMode/Integration_[テスト名]Tests.cs`

## 結果判定
- 全テストPass → feature-db: complete
- 1つでもFail → feature-db: in_progress
