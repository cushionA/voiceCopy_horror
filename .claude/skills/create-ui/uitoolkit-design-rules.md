# UI Toolkit デザインルール

Web UIデザインのベストプラクティスをUI Toolkit (UXML/USS)向けに翻訳したルール集。
`/create-ui` 実行時にメインSkillから参照される。

---

## 1. カラー & テーマ

### 原則
- **支配色+アクセント戦略**: 均等配色よりも、1つの支配色に鋭いアクセントを1色加える
- アクセントカラーは **1ビュー（1画面）に1色まで**
- 既存のカラートークン（USS変数）を優先。新色追加は最小限に
- ダーク/ライト切替が必要な場合はUSS変数で管理

### USS変数によるテーマ管理
```css
:root {
    --color-bg-primary: rgba(0, 0, 0, 0.7);
    --color-bg-secondary: rgba(40, 40, 40, 0.8);
    --color-text-primary: rgb(255, 255, 255);
    --color-text-secondary: rgb(180, 180, 180);
    --color-accent: rgb(79, 195, 247);
    --color-danger: rgb(244, 67, 54);
    --color-success: rgb(76, 175, 80);
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 40px;
}
```

### 禁止事項
- 紫グラデーション（「AIが作った感」の典型）
- マルチカラーグラデーション（USS非対応でもあり、画像で代替する場合も控える）
- グロー効果を主要なアフォーダンスとして使わない
- 色だけに頼った状態表現（色覚多様性対応）

---

## 2. タイポグラフィ

### 原則
- **見出し**と**本文**でフォントウェイトを明確に分ける
- 数値データ（HP、金額、スコア等）には等幅数字（tabular-nums相当）を使用
- テキスト切り詰め: 長い名前やアイテム説明には `text-overflow: ellipsis` + `overflow: hidden`

### USSでの実装
```css
/* 見出し */
.heading {
    font-size: 24px;
    -unity-font-style: bold;
    color: var(--color-text-primary);
    letter-spacing: 2px;
}

/* 本文 */
.body-text {
    font-size: 14px;
    -unity-font-style: normal;
    color: var(--color-text-secondary);
}

/* 数値データ — 幅が安定する */
.numeric-text {
    font-size: 16px;
    -unity-font-style: bold;
    -unity-text-align: middle-right;
}

/* テキスト切り詰め */
.truncated-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
```

### 禁止事項
- USS で `letter-spacing` の過度な変更（明確な意図がない限り）
- フォントサイズの乱立（画面内で3-4サイズに絞る）

---

## 3. レイアウト

### 原則
- UI ToolkitはデフォルトでFlexbox（Yogaエンジン）→ `flex-direction`, `align-items`, `justify-content` を活用
- 正方形要素は `width` + `height` をセットで指定
- 余白は一貫した**スペーシングスケール**（4の倍数: 4, 8, 12, 16, 24, 32, 40px）
- 階層はVisualElementのネスト順で制御（USSに `z-index` は存在しない）

### パターン
```css
/* 縦並びコンテナ */
.vertical-container {
    flex-direction: column;
    align-items: stretch;
    padding: var(--spacing-md);
}

/* 横並びコンテナ */
.horizontal-container {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
}

/* 画面中央配置 */
.centered-container {
    position: absolute;
    width: 100%;
    height: 100%;
    align-items: center;
    justify-content: center;
}

/* セーフエリア考慮の端固定 */
.edge-anchored {
    position: absolute;
    left: 20px;
    top: 20px;
}
```

### 禁止事項
- 任意の `z-index` 値（USS非対応。UXMLの記述順で制御する）
- `height: 100vh` 等のviewport単位（USS非対応。`height: 100%` を使用）
- マジックナンバーによる位置指定（USS変数で管理）

---

## 4. アニメーション & トランジション

### 原則
- **明示的に要求された場合のみ**アニメーションを追加（デフォルトはなし）
- USS Transitionで対応可能なプロパティ: `opacity`, `translate`, `rotate`, `scale`, `width`, `height`, `background-color`, `border-color`
- インタラクションフィードバックは **200ms以下**
- バーの増減やフェードは **300ms程度**
- 複雑なアニメーションは **LitMotion** をC#側で使用（USS Transitionの限界を超える場合）

### USSでの実装
```css
/* ボタンホバーフィードバック */
.interactive-button {
    transition-property: scale, opacity;
    transition-duration: 0.15s;
    transition-timing-function: ease-out;
}

.interactive-button:hover {
    scale: 1.05 1.05;
}

.interactive-button:active {
    scale: 0.95 0.95;
    opacity: 0.8;
}

/* バー増減アニメーション */
.bar-fill {
    transition-property: width;
    transition-duration: 0.3s;
    transition-timing-function: ease-out;
}

/* 画面フェードイン */
.fade-in {
    opacity: 0;
    transition-property: opacity;
    transition-duration: 0.2s;
}

.fade-in--visible {
    opacity: 1;
}
```

### LitMotion連携（C#側）
```csharp
// USS Transitionで不足する場合のみLitMotionを使用
// - 連鎖アニメーション
// - イージングの細かい制御
// - コールバック付きアニメーション
// - パンチスケール等の特殊エフェクト
```

### 禁止事項
- `transition-property: all`（意図しないプロパティまでアニメーションされる）
- 大きな要素の `blur()` / `backdrop-filter`（USS非対応）
- ループアニメーション（USS Transitionでは不可。必要ならC#で実装）
- アニメーション要求がないのに勝手にアニメーションを追加する

---

## 5. コンポーネント設計

### 原則
- VisualElementの階層は **最大4段** を目安に（深すぎるネストは可読性を損なう）
- 再利用するUI部品は **UXMLテンプレート** (`<Template>`) として分離
- USS クラス名は **kebab-case**、BEM風の命名
  - ブロック: `status-panel`
  - 要素: `status-panel__bar`
  - 修飾子: `status-panel__bar--critical`

### 命名パターン
```
[画面名]-[ブロック]              → pause-menu-root
[画面名]-[ブロック]__[要素]      → pause-menu-button__label
[画面名]-[ブロック]--[状態]      → pause-menu-button--selected
[共通ブロック]                    → bar-container, bar-fill
[共通ブロック]--[バリエーション]  → bar-fill--hp, bar-fill--mp
```

### 空の状態（Empty State）
- リストやインベントリが空の時は、**明確な次アクション**を1つ提示する
- 例: 「アイテムがありません。ショップで購入しましょう」+ ショップボタン

---

## 6. インタラクション & アクセシビリティ

### 原則
- アイコンのみのボタンには必ず **Tooltip** を設定（`tooltip` 属性）
- 破壊的操作（セーブデータ削除、タイトルに戻る等）には **確認ダイアログ** を挟む
- フォーカス可能な要素は `focusable="true"` を明示
- ゲームパッド対応時は **フォーカスリング**（`:focus` スタイル）を視覚的に明確にする

### フォーカススタイル
```css
/* フォーカスリング — パッド操作時に選択中の要素を示す */
.focusable:focus {
    border-width: 2px;
    border-color: var(--color-accent);
    border-radius: 4px;
}

/* ナビゲーション可能なボタン */
.nav-button:focus {
    scale: 1.05 1.05;
    border-width: 2px;
    border-color: var(--color-accent);
}
```

### 禁止事項
- フォーカスアウトラインの除去（代替の視覚表現なしに）
- ホバーのみで伝達される情報（パッド操作で到達不能になる）
- `paste` イベントのブロック（テキスト入力フィールド）
