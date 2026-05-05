# USS クイックリファレンス & 制約

UI Toolkit の USS (Unity Style Sheets) で使用可能なプロパティと、
CSSとの違い・制約をまとめたリファレンス。

---

## USS で使用可能な主要プロパティ

### ボックスモデル
| プロパティ | 例 | 備考 |
|-----------|-----|------|
| `width`, `height` | `200px`, `50%`, `auto` | `vw`/`vh`単位は非対応 |
| `min-width`, `max-width` | `100px`, `none` | |
| `min-height`, `max-height` | `50px`, `none` | |
| `margin` | `8px`, `4px 8px` | 四辺個別指定可 |
| `padding` | `12px`, `8px 16px` | 四辺個別指定可 |
| `border-width` | `2px` | 四辺個別指定可 |
| `border-color` | `rgb(255,0,0)` | 四辺個別指定可 |
| `border-radius` | `6px` | 四隅個別指定可 |

### Flexbox
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `flex-direction` | `row`, `column`, `row-reverse`, `column-reverse` | デフォルト: `column` |
| `flex-wrap` | `nowrap`, `wrap` | |
| `flex-grow` | `1` | |
| `flex-shrink` | `0` | |
| `flex-basis` | `auto`, `100px` | |
| `align-items` | `flex-start`, `center`, `flex-end`, `stretch` | |
| `align-self` | `auto`, `flex-start`, `center`, `flex-end`, `stretch` | |
| `justify-content` | `flex-start`, `center`, `flex-end`, `space-between`, `space-around` | |

### 位置
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `position` | `relative`, `absolute` | `fixed`, `sticky` は非対応 |
| `left`, `right`, `top`, `bottom` | `20px`, `50%` | |
| `translate` | `-50% 0` | 中央寄せに使用 |
| `rotate` | `45deg` | |
| `scale` | `1.05 1.05` | |
| `transform-origin` | `center`, `50% 50%` | |

### 背景 & 色
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `background-color` | `rgb()`, `rgba()`, `#hex` | |
| `background-image` | `url("path/to/image.png")` | リソースパスまたはURL |
| `-unity-background-image-tint-color` | `rgb()` | 画像のティント色 |
| `-unity-background-scale-mode` | `stretch-to-fill`, `scale-and-crop`, `scale-to-fit` | |
| `opacity` | `0` ~ `1` | |

### テキスト
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `font-size` | `14px` | `rem`/`em`は非対応 |
| `color` | `rgb()`, `#hex` | テキスト色 |
| `-unity-font-style` | `normal`, `bold`, `italic`, `bold-and-italic` | |
| `-unity-text-align` | `upper-left`, `middle-center`, `lower-right` 等 | 9方向 |
| `letter-spacing` | `2px` | |
| `word-spacing` | `4px` | |
| `white-space` | `normal`, `nowrap` | |
| `text-overflow` | `clip`, `ellipsis` | |
| `text-shadow` | `1px 1px 2px rgb(0,0,0)` | |
| `-unity-font` | `url("path/to/font.ttf")` | |
| `-unity-font-definition` | `url("path/to/font.asset")` | SDF Font推奨 |
| `-unity-paragraph-spacing` | `8px` | |

### Overflow
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `overflow` | `visible`, `hidden` | ScrollViewは別要素 |

### トランジション
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `transition-property` | `opacity`, `scale`, `translate`, `width` 等 | カンマ区切りで複数指定可 |
| `transition-duration` | `0.3s`, `300ms` | |
| `transition-timing-function` | `ease`, `ease-in`, `ease-out`, `ease-in-out`, `linear` | カスタムcubic-bezierは非対応 |
| `transition-delay` | `0.1s` | |

### カーソル
| プロパティ | 値 | 備考 |
|-----------|-----|------|
| `cursor` | `url("path/to/cursor.png") hotspot_x hotspot_y` | カスタムカーソル |

---

## USS 擬似クラス

| 擬似クラス | トリガー |
|-----------|---------|
| `:hover` | マウスオーバー時 |
| `:active` | クリック/タップ中 |
| `:focus` | フォーカス取得時（キーボード/パッド） |
| `:disabled` | `SetEnabled(false)` 時 |
| `:checked` | Toggle系がON時 |
| `:root` | ルートVisualElement |

**非対応**: `:first-child`, `:last-child`, `:nth-child`, `::before`, `::after`, `@media`

---

## USS セレクタ

| セレクタ | 例 | 備考 |
|---------|-----|------|
| 型セレクタ | `Button { }` | VisualElementのC#型名 |
| クラスセレクタ | `.menu-button { }` | 複数クラス付与可 |
| 名前セレクタ | `#start-button { }` | UXML の `name` 属性 |
| 子孫セレクタ | `.panel Label { }` | スペースで子孫 |
| 子セレクタ | `.panel > Button { }` | `>` で直接の子 |
| 複合セレクタ | `Button.primary:hover { }` | 組み合わせ |

**非対応**: `+`（隣接兄弟）, `~`（一般兄弟）, `*`（全称）, 属性セレクタ `[attr]`

---

## CSSとの主な違い（よくあるミス）

| CSS | USS | 対応方法 |
|-----|-----|---------|
| `box-shadow` | 非対応 | `border` + 背景画像で代替 |
| `gradient` | 非対応 | 背景画像で代替 |
| `backdrop-filter` | 非対応 | 半透明背景色で代替 |
| `z-index` | 非対応 | UXML記述順（後が上） |
| `display: none/flex/grid` | `display: none/flex` のみ | `grid` 非対応 |
| `position: fixed/sticky` | 非対応 | `absolute` で代替 |
| `vh`/`vw`/`rem`/`em` | 非対応 | `px` または `%` |
| `@media` | 非対応 | C#でPanelSettings.scaleMode設定 |
| `@keyframes` | 非対応 | C# (LitMotion等) で実装 |
| `::before`/`::after` | 非対応 | 追加VisualElementで代替 |
| `cubic-bezier()` | 非対応 | 既定の5種のみ |
| `font-weight: 100-900` | 非対応 | `-unity-font-style` で `normal`/`bold` のみ |
| `text-decoration` | 非対応 | なし |
| `overflow: scroll` | 非対応 | `ScrollView` 要素を使用 |

---

## 解像度 & スケーリング対応

### PanelSettings
```
- Scale Mode: Scale With Screen Size（推奨）
- Reference Resolution: asset-spec.json の画面サイズに合わせる
- Match: Width Or Height (0.5)
```

### レイアウトのベストプラクティス
- 固定サイズ (`px`) は小要素（ボタン、アイコン）に限定
- コンテナは `%` + Flex で伸縮可能にする
- 画面端に固定する要素は `position: absolute` + マージンで安全領域を確保
- `designs/asset-spec.json` の画面サイズ・タイルサイズを参照してレイアウトを決定
