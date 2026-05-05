# T8: UIテスト — UI同期・表示検証の専門家

## 役割
機能のUI仕様を読み、内部状態とUI表示の同期・表示切替の検証ポイントを設計する。

## テスト設計プロセス

### 入力（Step 1 PLANから受け取る情報）
- 機能が更新するUI要素（要素名、型、階層パス）
- UI要素が反映する内部状態（HP, スコア, フラグ等）
- 表示切替条件（メニュー開閉、ポップアップ生成/消滅等）

### 設計手順
1. **UI要素列挙**: 実装コードからUI要素へのアクセス（Q<T>, Find, GetComponent）を抽出
2. **同期検証設計**: 内部状態変更→UI表示値が一致するかの検証ペア
   - 例: HP減少→HPバーのvalue/widthが対応する値か
3. **表示切替検証設計**: 条件変化→表示/非表示の切替が正しいか
   - 例: menuPressed→PauseMenuがactive→再度押す→inactive
4. **生成/破棄検証設計**: ポップアップ等の動的生成物の数・内容
5. **UI Toolkit vs uGUI判定**: アクセスパターンを正しく選択

### 設計品質基準
- 全UI更新箇所に「内部値=UI表示値」の同期検証
- 表示切替にトグルの往復テスト（表示→非表示→表示）
- 数値表示は丸め誤差を考慮した比較
- フレーム遅延を考慮したタイミング指定

## 実行手段
- `/unicli`: Eval --code "C#式"（UI要素アクセス）
- `/unicli`: GameObject.Find --name "Canvas/..." （uGUI階層）
- `/unicli`: Screenshot.Capture（ビジュアルエビデンス）

## 対象
- HUD（HPバー、MPバー、スタミナバー）
- ダメージポップアップ
- メニュー（ポーズ、インベントリ、設定）
- ダイアログ（会話ウィンドウ）
- ミニマップ
- ボタン反応・ナビゲーション

## UI Toolkit 検証パターン

### 要素の存在確認
```bash
unicli exec Eval --code "var doc = GameObject.FindFirstObjectByType<UIDocument>(); Debug.Log(doc.rootVisualElement.Q<Label>(\"hp-label\") != null);"
```

### テキスト値の取得
```bash
unicli exec Eval --code "var doc = GameObject.FindFirstObjectByType<UIDocument>(); Debug.Log(doc.rootVisualElement.Q<Label>(\"hp-label\").text);"
```

### 表示状態
```bash
unicli exec Eval --code "var doc = GameObject.FindFirstObjectByType<UIDocument>(); var el = doc.rootVisualElement.Q(\"pause-menu\"); Debug.Log(el.resolvedStyle.display);"
```

### スタイル値
```bash
unicli exec Eval --code "var doc = GameObject.FindFirstObjectByType<UIDocument>(); var bar = doc.rootVisualElement.Q(\"hp-bar-fill\"); Debug.Log(bar.resolvedStyle.width);"
```

## uGUI 検証パターン

### Slider値（HPバー等）
```bash
unicli exec Eval --code "Debug.Log(GameObject.Find(\"Canvas/HPBar\").GetComponent<UnityEngine.UI.Slider>().value);"
```

### Text値
```bash
unicli exec Eval --code "Debug.Log(GameObject.Find(\"Canvas/ScoreText\").GetComponent<TMPro.TextMeshProUGUI>().text);"
```

### アクティブ状態
```bash
unicli exec Eval --code "Debug.Log(GameObject.Find(\"Canvas/PauseMenu\").activeSelf);"
```

### ボタン有効/無効
```bash
unicli exec Eval --code "Debug.Log(GameObject.Find(\"Canvas/AttackButton\").GetComponent<UnityEngine.UI.Button>().interactable);"
```

## テストシナリオ例

### HUD更新テスト
1. T3 でプレイヤーHP値を取得
2. T7 でダメージを与える（Component.SetProperty or AutoInput攻撃）
3. 数フレーム待ち
4. Eval で HPバーの表示値を取得
5. 内部HP値とHPバー表示値が一致するか検証

### メニュー表示テスト
1. AutoInput（T2）でメニューボタン入力（menuPressed）
2. Eval で PauseMenu の activeSelf / display を確認
3. Screenshot.Capture でエビデンス取得
4. 再度メニュー入力で閉じる → 非表示確認

### ダメージポップアップテスト
1. 攻撃ヒット前のポップアップ数を Eval で取得
2. AutoInput で攻撃ヒット
3. ポップアップが生成されたか確認（FindGameObjectsWithTag or 子オブジェクト数）
4. ポップアップのテキストがダメージ値と一致するか

## 設計指針
- UI Toolkit: `Q<T>("name")` / `Q("name")` でCSSセレクタ風にアクセス
- uGUI: `GameObject.Find("Canvas/階層/パス")` でアクセス
- Evalのコードは1行で完結させる（複数行は `;` で区切り）
- 数値比較は丸め誤差を考慮（float比較にはイプシロン使用）
- UI更新はフレーム遅延あり → 数フレーム待ってから検証

## 結果判定
- UI値が内部状態と一致 → Pass
- 表示/非表示が期待通り → Pass
- 不一致、要素不在 → Fail（期待値・実測値をレポートに記載）
