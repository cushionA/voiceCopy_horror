# T4: Animator状態テスト — アニメーション遷移の専門家

## 役割
機能のアニメーション仕様を読み、Animator状態遷移・パラメータ値の検証ポイントを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能が使うAnimatorパラメータ（IsAttacking, Speed等）
- 期待する状態遷移パス（Idle → Attack → Idle等）
- AnimatorControllerのレイヤー構成

### 設計手順
1. **パラメータ列挙**: 実装コードからAnimator.SetXxx呼び出しを抽出
2. **遷移パス列挙**: 各入力/アクションに対応する状態遷移を特定
3. **正常遷移テスト**: 入力→パラメータ変化→状態遷移の順序を検証
4. **異常遷移テスト**: 不正なタイミングでの入力で意図しない遷移が起きないか
5. **レイヤー干渉テスト**: 複数レイヤーのパラメータが相互に矛盾しないか

### 設計品質基準
- 機能が設定する全Animatorパラメータの変化を検証
- 遷移の始点と終点だけでなく、遷移中の状態も確認（normalizedTime）
- T2（AutoInput）とセットで設計（入力→アニメーション遷移の因果関係）

## 実行手段
- `/unicli`: Animator.Inspect --name "オブジェクト名"
- `/unicli`: Animator.SetParameter --name "オブジェクト名" --parameterName "パラメータ" --value "値"
- `/unicli`: Animator.CrossFade --name "オブジェクト名" --stateName "状態名"
- `/unicli`: Animator.Play --name "オブジェクト名" --stateName "状態名"

## 対象
- 攻撃アニメーション遷移（Idle → Attack → Idle）
- 移動アニメーション（Idle ↔ Run ↔ Jump）
- 被弾アニメーション（Hit → Recovery）
- パラメータ値（IsGrounded, IsAttacking, Speed 等）
- アニメーション完了タイミング（normalizedTime）

## 検証パターン

### 現在の状態確認
```bash
unicli exec Animator.Inspect --name "Player"
# → currentState, parameters, layerInfo を返す
```

### パラメータ検証
```bash
# Inspectの結果からパラメータ値を確認
# IsGrounded = true, Speed = 0, IsAttacking = false 等
```

### 状態遷移シーケンス
1. AutoInput（T2）で入力を送信
2. 数フレーム待機
3. Animator.Inspect で状態を確認
4. 期待するstate名と一致するか検証

### 強制遷移テスト
```bash
# 特定状態を強制的に再生してパラメータ反応を見る
unicli exec Animator.CrossFade --name "Player" --stateName "Attack01" --transitionDuration 0.1
```

## 設計指針
- 遷移直後はnormalizedTimeが0に近いことを確認
- レイヤー番号に注意: 基本動作=Layer0、上半身=Layer1 等
- Animator.Inspect はPlayMode中のみ有効（EditModeではデフォルト状態のみ）
- AutoInput（T2）と必ずセットで使う（入力→アニメーション遷移の検証）

## 結果判定
- 期待state名と一致 → Pass
- パラメータ値が期待通り → Pass
- 不一致 → Fail（現在state名・パラメータ値をレポートに記載）
