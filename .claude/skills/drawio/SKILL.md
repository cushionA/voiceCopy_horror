---
name: drawio
description: draw.io ダイアグラムを生成する。MCP ツール（open_drawio_xml / open_drawio_mermaid / open_drawio_csv）を使い分けてブラウザ上の draw.io エディタで開く。
disable-model-invocation: true
argument-hint: [diagram-type] [description]
---

# draw.io ダイアグラム生成スキル

MCP ツールを使ってダイアグラムを生成し、ブラウザ上の draw.io エディタで開く。
**状況に応じて 3つの MCP ツールを使い分ける。**

## 引数

```
$0 = 図の種別（省略可）: architecture / flowchart / sequence / er / network / state / class / mindmap / org / gantt
$1+ = 図の説明（自然言語）
```

例: `/drawio architecture AWS上のサーバーレスAPIシステム`、`/drawio flowchart ユーザー登録フロー`

---

## 3つの MCP ツール

| MCP ツール | 最適な用途 | 自動レイアウト |
|-----------|-----------|--------------|
| `open_drawio_xml` | AWSアーキテクチャ図、精密な配置、カスタムアイコン | なし（手動座標） |
| `open_drawio_mermaid` | フローチャート、シーケンス図、ER図、ステート図、クラス図 | あり（自動） |
| `open_drawio_csv` | 組織図、ツリー構造、データ駆動の図、大量ノード | あり（自動） |

共通引数: `content`（必須: XML/Mermaid/CSV文字列）、`lightbox`（任意: 読み取り専用）、`dark`（任意: `"auto"`/`"true"`/`"false"`）

### 方式の選択フロー

```
AWSアイコン / カスタムスタイル / 精密な座標配置が必要？
  → YES → open_drawio_xml
  → NO ↓
ノード数が多い（20+）/ データ駆動 / 組織図・ツリー構造？
  → YES → open_drawio_csv
  → NO ↓
Mermaid がサポートする図？（flowchart/sequence/er/state/class/gantt/pie/mindmap）
  → YES → open_drawio_mermaid
  → NO → open_drawio_xml
```

### 図の種別ごとの推奨方式

| 図の種別 | 第1推奨 | 第2推奨 |
|---------|---------|---------|
| AWSアーキテクチャ | xml | — |
| フローチャート | mermaid | xml |
| シーケンス図 | mermaid | — |
| ER図 | mermaid | xml |
| ステート図 | mermaid | xml |
| クラス図 | mermaid | xml |
| 組織図 | csv | xml |
| ネットワーク図 | xml | csv |
| マインドマップ | mermaid | — |
| データ駆動の図（20+ノード） | csv | — |
| ガントチャート | mermaid | — |
| パイプライン図 | mermaid | xml |

---

## 実行手順

### Step 1: 要件の確認
1. ユーザーの説明から図の種別・構成要素・関係性を特定
2. 不明点があれば質問してから作成開始
3. 上記の選択フローに従い最適な方式を選択

### Step 2: コンテンツの生成
選択した方式に応じて content 文字列を組み立てる。各方式の構文・テンプレートは `references/mcp-tools-guide.md` を参照。

### Step 3: MCP ツールで開く
```
open_drawio_xml(content="<mxfile>...</mxfile>")
open_drawio_mermaid(content="flowchart TD\n    A-->B")
open_drawio_csv(content="# label: %name%\n...")
```

---

## デザイン原則（全方式共通）

1. **標準記法を使う**: 広く認知されたアイコン・記号を使用
2. **全要素にラベルを付ける**: アイコン、グループ、コネクタすべてに明確なラベル
3. **一貫性を維持**: 色・サイズ・線の太さ・矢印の形状を統一
4. **正確性を優先**: 見た目のために正確さを犠牲にしない
5. **凡例を提供する**: 独自の表記ルールは必ず説明
6. **1枚に詰め込まない**: 複雑な図は段階的に分割
7. **コネクタ種別で意味を区別**: 実線=同期、破線=非同期、太線=メインフロー

---

## 参照ドキュメント

詳細は `references/` フォルダ内のファイルを参照。

| ファイル | 内容 |
|---------|------|
| [references/mcp-tools-guide.md](references/mcp-tools-guide.md) | MCP ツール詳細（Mermaid構文、CSV構文、XML必須ルール） |
| [references/xml-templates.md](references/xml-templates.md) | XML テンプレート集（図形・矢印・グループ） |
| [references/aws-icons.md](references/aws-icons.md) | AWS アイコンカタログ（80+ サービス） |
| [references/layout-guidelines.md](references/layout-guidelines.md) | レイアウトパターン・配色パレット |
| [scripts/find_drawio_icon.py](scripts/find_drawio_icon.py) | AWSアイコン検索スクリプト |

**重要**: 参照ファイルを丸ごと読み込まず、必要な部分のみ参照すること。
AWSアイコンは `find_drawio_icon.py` で必要なもののみ取得する。
