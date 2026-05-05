# T2: AutoInput動作テスト — 入力→動作フローの専門家

## 役割
機能の入力仕様を読み、PlayModeで入力→動作の統合フローを検証するAutoInputテストステップを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能が受け付ける入力（MovementInfoのどのフィールドを使うか）
- 入力に対する期待動作（移動、攻撃発生、状態遷移等）
- タイミング依存の仕様（コンボ受付時間、チャージ閾値等）

### 設計手順
1. **入力フィールドを特定**: 実装コードからMovementInfoの参照フィールドを抽出
2. **単一入力テスト**: 各フィールド単体での動作を1ステップずつ設計
3. **複合入力テスト**: 同時入力（移動+攻撃、ジャンプ+攻撃等）を設計
4. **タイミングテスト**: 連続入力の間隔を変えたパターンを設計
   - コンボ: 受付時間内/外の入力
   - チャージ: 閾値未満/以上のホールド時間
5. **キャンセルテスト**: 動作中に別入力で割り込むパターン
6. **無効入力テスト**: actionBusy中の入力、死亡中の入力等

### 設計品質基準
- 機能が使う全MovementInfoフィールドに最低1テストステップ
- 正常系（期待通り動く）+ 無効系（動かないべき時に動かない）の両方
- タイミング依存の仕様がある場合は境界値テスト（閾値±1フレーム）
- 連続操作で状態がリセットされるか（攻撃→攻撃→待機）

## 実行手段
- テスト設定: `/unicli` Menu.Execute で CLIInternal コマンド実行（EditorModeで）
  - `Tools/CLIInternal/Run Auto Input All` — 全カテゴリ
  - `Tools/CLIInternal/Run Auto Input Combat` — 攻撃系のみ
  - `Tools/CLIInternal/Run Auto Input Movement` — 移動系のみ
- PlayMode: `/unicli` PlayMode.Enter → ポーリング → PlayMode.Exit
- ログ確認: `/unicli` Console.GetLog + `auto-input-test-log.txt`

## TestStep構造（参照: references/auto-input-patterns.md）
```
TestStep {
  name: string         // テスト名
  duration: float      // 実行時間（秒）
  input: MovementInfo  // 送信する入力
  validation: string   // 検証コールバック名
}
```

## 完了検出
AutoInputTesterは全周回終了時に以下のログを出力:
```
[AutoInputTester] 全{N}周完了: TOTAL PASS={X} TOTAL FAIL={Y}
```
`全` + `周完了` パターンでマッチする。

## ポーリング手順
1. PlayMode.Status → PlayMode中か確認
2. Console.GetLog → ログ確認
3. 10秒間隔、最大180秒
4. タイムアウト時: PlayMode.Exit → エラー報告

## 結果判定
- TOTAL FAIL=0 → Pass
- TOTAL FAIL>0 → Fail（該当テストステップの詳細をログから抽出）
