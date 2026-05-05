---
name: create-ui
description: Create Unity UI screens using UI Toolkit (UXML/USS) or uGUI. Generates layout definitions, stylesheets, and backing scripts.
user-invocable: true
argument-hint: <UI screen name> [HUD|Menu|Dialog|Settings|Inventory|custom]
---

# Create UI: $ARGUMENTS

Unity UIの画面を作成する。UI Toolkit (UXML/USS) で実装。

## サブドキュメント（段階的に参照）

このSkillは以下のサブドキュメントと連携する。必要になった段階で参照する（全部を一度に読まない）:

- `uitoolkit-design-rules.md` — カラー、タイポグラフィ、レイアウト、アニメーションのデザインルール
- `uitoolkit-uss-reference.md` — USSプロパティの制約一覧、CSSとの違い
- `game-ui-patterns.md` — ゲームUI種別ごとの設計パターン、USS変数テーマ
- `instruction-formats/ui-request.md` — ヒアリングフォームのテンプレート

## 手順

### ステップ0: 入力の判定

ユーザーの入力を確認し、以下のいずれかに分岐する:

**A. UIリクエストフォーム (`instruction-formats/ui-request.md`) が記入済みで渡された場合:**
→ 必須項目チェック（ステップ1B）に進む

**B. 画面名のみ、または自然言語での依頼の場合:**
→ ヒアリングフロー（ステップ1A）に進む

### ステップ1A: ヒアリングフロー（フォーム未記入の場合）

以下の必須項目を対話で収集する。一度に全部聞かず、回答に応じて掘り下げる。

**第1段階 — 基本情報（必ず聞く）:**
```
UI画面を作成します。以下を教えてください:

1. 画面種別は？
   → HUD / メニュー / ダイアログ / インベントリ / 設定 / その他

2. この画面で何をしますか？（1-2文で）
```

**第2段階 — コンテンツ（第1段階の回答後）:**
```
3. 画面に表示する情報は？
   例: HP, MP, アイテム一覧, キャラ名...

4. ユーザーが操作できる要素は？
   例: ボタン、スライダー、ドロップダウン...

5. 操作方法は？
   → マウス+キーボード / ゲームパッド / 両対応
```

**第3段階 — 見た目・動き（回答が薄い場合はデフォルトを提案）:**
```
6. 見た目のイメージは？
   → ダーク半透明 / ライト / カスタム
   （未指定の場合: プロジェクトの既存テーマに合わせます）

7. アニメーションは必要？
   → なし / 最小限 / 標準 / リッチ
   （未指定の場合: 最小限で進めます）

8. 参考にしたいゲームや画像はありますか？
```

**ヒアリング完了判定:**
以下が全て揃ったらステップ2に進む:
- [ ] 画面種別
- [ ] 目的
- [ ] 表示要素（1つ以上）
- [ ] 操作要素（0個でも明示的に確認済み）
- [ ] 入力方式

### ステップ1B: 必須項目チェック（フォーム記入済みの場合）

UIリクエストフォームの必須項目を検証:

| 項目 | 未記入時の対応 |
|------|--------------|
| 画面種別 | 質問して確認 |
| 目的 | 質問して確認 |
| 表示要素 | 質問して確認 |
| 操作要素 | 「操作要素なし」で確認を取る |
| 入力方式 | 「両対応」をデフォルト提案 |

推奨項目が未記入の場合は、プロジェクトの既存パターンからデフォルト値を提案:
- カラースキーム → `game-ui-patterns.md` の共通テーマ変数
- アニメーション → 「最小限」
- フォーカスナビゲーション → 画面種別に応じた推奨パターン

### ステップ2: 設計サマリー提示

ヒアリング結果を構造化して提示し、承認を得る:

```
## 設計サマリー: [画面名]

### 基本
- 種別: [種別]
- 目的: [目的]

### コンテンツ
- 表示: [要素リスト]
- 操作: [要素リスト]

### スタイル
- カラー: [スキーム + アクセント]
- アニメーション: [レベル + 具体内容]
- 入力: [方式 + ナビゲーション]

### 画面遷移
- 入: [方法]
- 出: [方法]

この内容で進めてよいですか？ 修正があれば指摘してください。
```

### ステップ3: デザインルール参照

承認後、画面種別に応じてサブドキュメントを参照:

1. **`game-ui-patterns.md`** を読み、該当する画面種別のパターンを確認
2. **`uitoolkit-design-rules.md`** を読み、デザインルールに従ってスタイルを設計
3. **`uitoolkit-uss-reference.md`** を読み、USSの制約内で実装可能か確認

### ステップ4: UI構造定義

`instruction-formats/ui-structure.md` フォーマットに従い、UI構造を定義する。

```
# UI: [画面名]

## Layout
- Root (type: VisualElement)
  - style: [ルートスタイル]
  - children:
    - [要素名] (type: [タイプ])
      ...

## Styles (USS)
- .[クラス名]:
  - [プロパティ]: [値]

## Events
- [要素名].[イベント名] → [ハンドラ説明]

## Data Binding
- [要素名] ← [データソース].[プロパティ]
```

### ステップ5: UI構造をユーザーに提示

構造をユーザーに提示し、レイアウトやスタイルの修正を受け付ける。

### ステップ6: ファイル生成

承認後、以下のファイルを生成:

- `Assets/MyAsset/UI/[画面名]/[画面名].uxml` — レイアウト定義
- `Assets/MyAsset/UI/[画面名]/[画面名].uss` — スタイルシート
- `Assets/MyAsset/Runtime/UI/[画面名]Controller.cs` — イベントハンドリング・データバインディング

**生成時のルール:**
- `game-ui-patterns.md` の共通テーマ変数を `@import` する（USS冒頭）
- クラス命名は kebab-case、BEM風（`uitoolkit-design-rules.md` 参照）
- C#コントローラは `[RequireComponent(typeof(UIDocument))]`
- UI要素参照は `rootVisualElement.Q<T>("name")` でクエリ
- イベント登録は `OnEnable`、解除は `OnDisable`
- `MenuStackManager` との連携が必要な画面は統合する
- バーアニメーションが必要な場合は LitMotion を使用
- パッド対応が必要な場合はフォーカスナビゲーションを実装

### ステップ7: MCP経由でプレビュー（エディタ起動中の場合）

```python
# UIDocumentをシーンに配置して確認
manage_scene(action="screenshot", include_image=True, max_resolution=512)
```

## 画面テンプレート早見表

| 種別 | 典型的要素 | 位置 | パッド対応 | アニメ |
|------|----------|------|:---------:|:-----:|
| HUD | HP,MP,ミニマップ,スロット | 画面端固定 | 不要 | バーTween |
| メニュー | タイトル,ボタン群 | 画面中央 | 必須 | フェード |
| ダイアログ（会話）| 立絵,名前,テキスト,選択肢 | 画面下部 | 必須 | テキスト送り |
| ダイアログ（確認）| メッセージ,はい/いいえ | 画面中央モーダル | 必須 | フェード |
| 設定 | スライダー,トグル,ドロップダウン | 画面中央 | 必須 | なし |
| インベントリ | グリッド,詳細,タブ | 画面中央 | 必須 | なし |

## テスト

UI機能のテストは Edit Mode で:
- データバインディングの正確性
- イベントハンドラの呼び出し確認
- 表示/非表示の状態遷移
- MenuStackManagerとの連携

## 出力先
- `Assets/MyAsset/UI/[画面名]/` — UXML + USS
- `Assets/MyAsset/Runtime/UI/[画面名]Controller.cs` — バッキングスクリプト
- `designs/ui/[画面名].md` — UI構造定義（テキスト）

---

# UI Toolkit Anti-Patterns（Unity 6 知見）

> Sources: nice-wolf-studio/unity-claude-skills (MIT) — unity-ui

| Anti-Pattern | 問題 | 正しい対応 |
|---|---|---|
| inline style を多用 | 要素単位のメモリオーバヘッド | USS ファイルで共通スタイルを定義 |
| 複雑な universal selector (`A * B`) | スケール時のセレクタ性能劣化 | BEM クラス命名 + 子セレクタ |
| 多孫要素を持つ要素への重い `:hover` | マウス移動でツリー全体が無効化 | leaf 要素にのみ `:hover` を限定 |
| `CreateInspectorGUI()` 内で `Bind()` を呼ぶ | 二重バインド（return 後に自動バインドが走る） | 自動バインドに任せる、手動 UI のみ Bind を呼ぶ |
| 毎フレーム UI 全体をリビルド | retained-mode の利点を消す | 変更要素のみ更新 |
| 動的コンテンツを持つ複数 Canvas（uGUI） | 子変更で Canvas rebuild がバッチ処理 | 静的 / 動的 UI を別 Canvas に分離 |
| `UnregisterCallback` 忘れ | メモリリーク・stale reference | `OnDisable` か `OnDestroy` で必ず解除 |
| 毎フレーム IMGUI でゲーム UI 描画 | 性能低 | UI Toolkit / uGUI を使う |
| EventSystem を Scene に置き忘れ（uGUI） | 入力イベントが処理されない | Scene に EventSystem が 1 つあること |

## UI Toolkit Event Propagation（必須知識）

UI Toolkit のイベントは 2 段階で伝播する:

1. **Trickle-down**（root → target、親が先に反応）
2. **Bubble-up**（target → root、子が先に反応、デフォルト）

```csharp
// デフォルト = Bubble-up
element.RegisterCallback<PointerDownEvent>(OnPointerDown);

// Trickle-down 指定（親で先取り処理）
element.RegisterCallback<PointerDownEvent>(OnPointerDown, TrickleDown.TrickleDown);

// コールバックにユーザーデータを渡す
element.RegisterCallback<ClickEvent, string>(OnClickWithData, "my-data");

// ChangeEvent を発火させずに値設定
myControl.SetValueWithoutNotify(newValue);
```

**重要**: `OnDisable` で **必ず `UnregisterCallback`** を呼ぶ。MonoBehaviour 全般の対称性ルール（unity-conventions.md）と同じ理由。

## カスタムコントロール（Unity 6+）

`UxmlFactory` / `UxmlTraits` は非推奨。**`[UxmlElement]` 属性 + `partial class`** を使う:

```csharp
[UxmlElement]
public partial class HealthBar : VisualElement
{
    [UxmlAttribute]
    public float MaxHealth { get; set; } = 100f;

    private VisualElement _fillBar;
    private float _currentHealth;

    public float CurrentHealth
    {
        get => _currentHealth;
        set
        {
            _currentHealth = Mathf.Clamp(value, 0, MaxHealth);
            _fillBar.style.width = Length.Percent(_currentHealth / MaxHealth * 100f);
        }
    }
}
```

UXML 側:
```xml
<ui:UXML xmlns:ui="UnityEngine.UIElements">
  <HealthBar max-health="200" />
</ui:UXML>
```

## Manipulator パターン

イベントハンドリングのロジックを UI コードから分離:

```csharp
public class DragManipulator : PointerManipulator
{
    private Vector3 _startPosition;
    private bool _isDragging;

    public DragManipulator(VisualElement target) { this.target = target; }

    protected override void RegisterCallbacksOnTarget()
    {
        target.RegisterCallback<PointerDownEvent>(OnPointerDown);
        target.RegisterCallback<PointerMoveEvent>(OnPointerMove);
        target.RegisterCallback<PointerUpEvent>(OnPointerUp);
    }

    protected override void UnregisterCallbacksFromTarget()
    {
        target.UnregisterCallback<PointerDownEvent>(OnPointerDown);
        target.UnregisterCallback<PointerMoveEvent>(OnPointerMove);
        target.UnregisterCallback<PointerUpEvent>(OnPointerUp);
    }

    private void OnPointerDown(PointerDownEvent evt) { /* ... */ }
    private void OnPointerMove(PointerMoveEvent evt) { /* ... */ }
    private void OnPointerUp(PointerUpEvent evt) { /* ... */ }
}

// 使用:
myElement.AddManipulator(new DragManipulator(myElement));
```

組込: `Manipulator` (基底), `PointerManipulator`, `MouseManipulator`, `Clickable`, `ContextualMenuManipulator`, `KeyboardNavigationManipulator`

## TextMeshPro（必須）

すべてのテキスト描画は **TextMeshPro (TMP)** を使う。レガシー `UI.Text` 禁止。
- Canvas UI: `TextMeshProUGUI`
- 3D ワールドテキスト: `TextMeshPro`
- ゼロ allocation 更新: `SetText("Score: {0}", value)`（`text = "Score: " + value` は GC alloc 発生）

## 詳細リファレンス

- UI Toolkit / uGUI 完全 API: `@.claude/refs/external/nice-wolf-studio/unity-ui/SKILL.md`
- USS リファレンス: 既存の `uitoolkit-uss-reference.md`
